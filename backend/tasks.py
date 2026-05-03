from __future__ import annotations

import html
import sqlite3
from concurrent.futures import Executor
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.config import DOWNLOADS_DIR, SHOWNOTES_DIR
from backend.db import (
    add_task_event,
    create_task,
    delete_task,
    find_task_by_episode,
    get_task,
    list_task_events,
    list_tasks,
    update_task,
)
from backend.downloads import download_audio, guess_audio_filename
from backend.rss import fetch_episodes
from backend.transcription import sanitize_filename, transcribe_audio


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    podcast_title: str = Field(min_length=1)
    rss_url: str = Field(min_length=1)
    episode_title: str = Field(min_length=1)
    audio_url: str = Field(min_length=1)
    episode_guid: str | None = None
    shownotes: str = ""


class TaskCancelledError(RuntimeError):
    """Raised when a running task is cancelled cooperatively."""


class _ShownotesTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"br", "p", "div", "li", "section", "article", "h1", "h2", "h3"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "li", "section", "article", "h1", "h2", "h3"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def text(self) -> str:
        lines = [" ".join(line.split()) for line in "".join(self._parts).splitlines()]
        return "\n\n".join(line for line in lines if line)


def enqueue_task(payload: TaskCreate, db_path: str | Path, executor: Executor) -> dict[str, Any]:
    raw_payload = payload.model_dump()
    existing = find_task_by_episode(payload.podcast_title, payload.episode_title, db_path)
    if existing is not None:
        if not existing.get("shownotes"):
            task_payload = _ensure_shownotes(raw_payload)
        else:
            task_payload = raw_payload
        if not existing.get("shownotes") and task_payload.get("shownotes"):
            existing = update_task(existing["id"], {"shownotes": task_payload["shownotes"]}, db_path)
        return {
            "task": existing,
            "result": "existing",
            "message": "已定位到现有任务。",
        }

    task_payload = _ensure_shownotes(raw_payload)
    task = create_task(task_payload, db_path)
    add_task_event(task["id"], "Task queued", db_path=db_path)
    executor.submit(run_task, task["id"], db_path, executor)
    return {
        "task": task,
        "result": "created",
        "message": "任务已创建，开始处理。",
    }


def get_task_detail(task_id: int, db_path: str | Path) -> dict[str, Any] | None:
    task = get_task(task_id, db_path)
    if task is None:
        return None
    task["events"] = list_task_events(task_id, db_path)
    return task


def get_task_summary(task_id: int, db_path: str | Path) -> dict[str, str] | None:
    task = get_task(task_id, db_path)
    if task is None:
        return None
    summary_path = task.get("summary_md_path")
    if not summary_path:
        return None
    path = Path(summary_path)
    if not path.exists():
        return None
    return {
        "title": task["episode_title"],
        "markdown": path.read_text(encoding="utf-8"),
        "path": str(path),
    }


def get_task_text_file(task_id: int, field: str, db_path: str | Path) -> dict[str, str] | None:
    task = get_task(task_id, db_path)
    if task is None:
        return None
    file_path = task.get(field)
    if not file_path:
        return None
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return None
    content = path.read_text(encoding="utf-8")
    return {
        "title": _markdown_title(content) or task["episode_title"],
        "content": content,
        "path": str(path),
    }


def _markdown_title(markdown: str) -> str:
    for line in markdown.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line.removeprefix("# ").strip()
    return ""


def list_task_details(db_path: str | Path) -> list[dict[str, Any]]:
    return list_tasks(db_path)


def migrate_shownotes_to_files(db_path: str | Path) -> None:
    for task in list_tasks(db_path):
        shownotes = task.get("shownotes", "")
        if not shownotes or _is_existing_shownotes_file(shownotes):
            continue
        path = _write_shownotes_file(task, shownotes)
        update_task(task["id"], {"shownotes": path}, db_path)


def remove_task(task_id: int, db_path: str | Path) -> dict[str, Any] | None:
    task = get_task(task_id, db_path)
    if task is None:
        return None

    _cleanup_task_files(task)
    delete_task(task_id, db_path)
    return {
        "task": task,
        "result": "deleted",
        "message": "任务已删除。",
    }


def restart_task(task_id: int, db_path: str | Path, executor: Executor) -> dict[str, Any] | None:
    task = get_task(task_id, db_path)
    if task is None:
        return None

    shownotes = _read_shownotes_reference(task.get("shownotes", ""))
    payload = {
        "podcast_title": task["podcast_title"],
        "rss_url": task["rss_url"],
        "episode_title": task["episode_title"],
        "episode_guid": task.get("episode_guid"),
        "audio_url": task["audio_url"],
        "shownotes": shownotes,
    }
    _cleanup_task_files(task)
    delete_task(task_id, db_path)
    payload = _ensure_shownotes(payload)
    task = create_task(payload, db_path)
    add_task_event(task["id"], f"Task restarted from {task_id}", db_path=db_path)
    executor.submit(run_task, task["id"], db_path, executor)
    return {
        "task": task,
        "replaced_task_id": task_id,
        "result": "restarted",
        "message": "任务已重新开始。",
    }


def _ensure_shownotes(payload: dict[str, Any]) -> dict[str, Any]:
    if _is_existing_shownotes_file(payload.get("shownotes", "")):
        return payload

    shownotes = payload.get("shownotes") or _fetch_shownotes(payload)
    if not shownotes:
        return payload

    enriched = dict(payload)
    enriched["shownotes"] = _write_shownotes_file(enriched, shownotes)
    return enriched


def _is_existing_shownotes_file(value: str) -> bool:
    if not value or any(marker in value for marker in ("\n", "\r", "<", ">")):
        return False
    try:
        path = Path(value)
    except (OSError, ValueError):
        return False
    return path.is_file()


def _read_shownotes_reference(value: str) -> str:
    if not _is_existing_shownotes_file(value):
        return value
    try:
        return Path(value).read_text(encoding="utf-8")
    except OSError:
        return ""


def _write_shownotes_file(payload: dict[str, Any], shownotes: str) -> str:
    SHOWNOTES_DIR.mkdir(parents=True, exist_ok=True)
    path = SHOWNOTES_DIR / f"{sanitize_filename(payload.get('episode_title', 'shownotes'))}.txt"
    path.write_text(_shownotes_to_text(shownotes), encoding="utf-8")
    return str(path)


def _shownotes_to_text(shownotes: str) -> str:
    parser = _ShownotesTextExtractor()
    parser.feed(shownotes)
    parser.close()
    text = parser.text() or shownotes
    return html.unescape(text).strip()


def _fetch_shownotes(payload: dict[str, Any]) -> str:
    rss_url = payload.get("rss_url", "")
    episode_title = payload.get("episode_title", "")
    episode_guid = payload.get("episode_guid", "")
    if not rss_url or not episode_title:
        return ""

    try:
        episodes = fetch_episodes(rss_url, episode_title)
    except Exception:
        return ""

    for episode in episodes:
        if episode_guid and episode.get("guid") == episode_guid:
            return episode.get("shownotes", "")
        if episode.get("title") == episode_title:
            return episode.get("shownotes", "")
    return ""


def run_task(task_id: int, db_path: str | Path, executor: Executor | None = None) -> None:
    task = get_task(task_id, db_path)
    if task is None:
        return

    try:
        _set_task_state(
            task_id,
            db_path,
            status="running",
            progress_stage="downloading_audio",
            started_at=datetime.now(timezone.utc).isoformat(),
            progress_percent=0.0,
            download_percent=0.0,
            transcription_percent=0.0,
            cancel_requested=0,
            pending_action="",
            error_message=None,
        )
        add_task_event(task_id, "Downloading audio", db_path=db_path)

        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        download_name = guess_audio_filename(task["audio_url"], sanitize_filename(task["episode_title"]))
        download_path = DOWNLOADS_DIR / download_name

        def on_download(downloaded: int, total: int) -> None:
            _raise_if_cancel_requested(task_id, db_path)
            download_percent = min(downloaded / total, 1.0) * 100.0 if total else 0.0
            update_task(
                task_id,
                {
                    "status": _current_status(task_id, db_path),
                    "progress_stage": "downloading_audio",
                    "progress_percent": min(download_percent * 0.45, 45.0),
                    "download_percent": min(download_percent, 100.0),
                    "audio_file_path": str(download_path),
                },
                db_path,
            )

        download_audio(task["audio_url"], download_path, progress_callback=on_download)
        _raise_if_cancel_requested(task_id, db_path)

        add_task_event(task_id, "Download complete", db_path=db_path)
        _set_task_state(
            task_id,
            db_path,
            status="running",
            progress_stage="transcribing",
            progress_percent=45.0,
            download_percent=100.0,
            transcription_percent=0.0,
            audio_file_path=str(download_path),
        )
        add_task_event(task_id, "Transcribing audio", db_path=db_path)

        def on_transcription(processed_seconds: float, total_seconds: float, message: str) -> None:
            _raise_if_cancel_requested(task_id, db_path)
            transcription_percent = min(processed_seconds / total_seconds, 1.0) * 100.0 if total_seconds else 0.0
            update_task(
                task_id,
                {
                    "status": _current_status(task_id, db_path),
                    "progress_stage": "transcribing",
                    "progress_percent": min(45.0 + transcription_percent * 0.5, 95.0),
                    "transcription_percent": min(transcription_percent, 100.0),
                },
                db_path,
            )
            if message:
                add_task_event(task_id, message[:500], db_path=db_path)

        transcript_path = transcribe_audio(
            download_path,
            task["episode_title"],
            progress_callback=on_transcription,
        )
        _raise_if_cancel_requested(task_id, db_path)
        add_task_event(task_id, "Writing transcript file", db_path=db_path)
        update_task(
            task_id,
            {
                "status": "completed",
                "progress_stage": "completed",
                "progress_percent": 100.0,
                "download_percent": 100.0,
                "transcription_percent": 100.0,
                "cancel_requested": 0,
                "pending_action": "",
                "output_txt_path": str(transcript_path),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            },
            db_path,
        )
        add_task_event(task_id, "Task completed", db_path=db_path)
    except TaskCancelledError:
        _handle_cancellation(task_id, db_path, executor)
    except KeyError as exc:
        if exc.args == (task_id,):
            return
        raise
    except sqlite3.IntegrityError:
        if get_task(task_id, db_path) is None:
            return
        raise
    except Exception as exc:
        update_task(
            task_id,
            {
                "status": "failed",
                "progress_stage": "failed",
                "error_message": str(exc),
                "pending_action": "",
                "finished_at": datetime.now(timezone.utc).isoformat(),
            },
            db_path,
        )
        add_task_event(task_id, f"Task failed: {exc}", level="error", db_path=db_path)


def _set_task_state(task_id: int, db_path: str | Path, **values) -> dict[str, Any]:
    values.setdefault("progress_percent", 0.0)
    return update_task(task_id, values, db_path)


def _current_status(task_id: int, db_path: str | Path) -> str:
    task = get_task(task_id, db_path)
    if task and task.get("cancel_requested"):
        return "cancelling"
    return "running"


def _raise_if_cancel_requested(task_id: int, db_path: str | Path) -> None:
    task = get_task(task_id, db_path)
    if task is None or task.get("cancel_requested"):
        raise TaskCancelledError()


def _cleanup_task_files(task: dict[str, Any]) -> None:
    for file_key in ("audio_file_path", "output_txt_path", "summary_md_path", "shownotes", "summarize", "summarize_en"):
        file_path = task.get(file_key)
        if not file_path:
            continue
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
        except OSError:
            continue


def _reset_task_for_run() -> dict[str, Any]:
    return {
        "status": "queued",
        "progress_stage": "queued",
        "progress_percent": 0.0,
        "download_percent": 0.0,
        "transcription_percent": 0.0,
        "cancel_requested": 0,
        "pending_action": "",
        "audio_file_path": None,
        "output_txt_path": None,
        "summary_md_path": None,
        "error_message": None,
        "started_at": None,
        "finished_at": None,
    }


def _handle_cancellation(task_id: int, db_path: str | Path, executor: Executor | None) -> None:
    task = get_task(task_id, db_path)
    if task is None:
        return

    _cleanup_task_files(task)
    pending_action = task.get("pending_action", "")

    if pending_action == "delete":
        delete_task(task_id, db_path)
        return

    if pending_action == "restart":
        update_task(task_id, _reset_task_for_run(), db_path)
        add_task_event(task_id, "Task restarted after cancellation", db_path=db_path)
        if executor is not None:
            executor.submit(run_task, task_id, db_path, executor)
        return

    update_task(
        task_id,
        {
            "status": "failed",
            "progress_stage": "cancelled",
            "pending_action": "",
            "finished_at": datetime.now(timezone.utc).isoformat(),
        },
        db_path,
    )
    add_task_event(task_id, "Task cancelled", level="error", db_path=db_path)
