from __future__ import annotations

from concurrent.futures import Executor, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.config import DB_PATH
from backend.db import add_task_event, init_db, list_tasks, update_task
from backend.tasks import restart_task


@dataclass(slots=True)
class MaintenanceResult:
    restarted_task_ids: list[int]
    replacement_task_ids: list[int]
    deleted_audio_paths: list[str]


def maintain_tasks(
    *,
    db_path: str | Path = DB_PATH,
    now: datetime | None = None,
    restart_after: timedelta = timedelta(hours=1),
    audio_retention_after_summary: timedelta = timedelta(hours=24),
    executor: Executor | None = None,
    max_workers: int = 2,
) -> MaintenanceResult:
    current_time = _as_utc(now or datetime.now(timezone.utc))
    init_db(db_path)

    owned_executor = executor is None
    task_executor = executor or ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="podcast-maintenance")
    restarted_task_ids: list[int] = []
    replacement_task_ids: list[int] = []
    deleted_audio_paths: list[str] = []

    try:
        for task in list_tasks(db_path):
            if not _should_restart(task, current_time, restart_after):
                continue
            result = restart_task(task["id"], db_path, task_executor)
            if result is None:
                continue
            restarted_task_ids.append(task["id"])
            replacement_task_ids.append(result["task"]["id"])

        for task in list_tasks(db_path):
            deleted_path = _delete_audio_if_summary_is_old(task, db_path, current_time, audio_retention_after_summary)
            if deleted_path:
                deleted_audio_paths.append(deleted_path)
    finally:
        if owned_executor:
            task_executor.shutdown(wait=True)

    return MaintenanceResult(
        restarted_task_ids=restarted_task_ids,
        replacement_task_ids=replacement_task_ids,
        deleted_audio_paths=deleted_audio_paths,
    )


def _should_restart(task: dict[str, Any], now: datetime, restart_after: timedelta) -> bool:
    started_at = _parse_datetime(task.get("started_at"))
    if started_at is None or now - started_at <= restart_after:
        return False
    return not _download_and_transcription_completed(task)


def _download_and_transcription_completed(task: dict[str, Any]) -> bool:
    return (
        task.get("status") == "completed"
        and task.get("progress_stage") == "completed"
        and float(task.get("transcription_percent") or 0) >= 100.0
        and bool(task.get("output_txt_path"))
    )


def _delete_audio_if_summary_is_old(
    task: dict[str, Any],
    db_path: str | Path,
    now: datetime,
    retention: timedelta,
) -> str | None:
    audio_path_value = task.get("audio_file_path")
    if not audio_path_value:
        return None

    if not _has_old_summary(task, now, retention):
        return None

    try:
        audio_path = Path(audio_path_value)
    except (OSError, ValueError):
        return None

    if not audio_path.is_file():
        return None

    try:
        audio_path.unlink()
    except OSError:
        return None

    update_task(task["id"], {"audio_file_path": None}, db_path)
    add_task_event(task["id"], "Deleted audio after summarize aged past retention window", db_path=db_path)
    return str(audio_path)


def _has_old_summary(task: dict[str, Any], now: datetime, retention: timedelta) -> bool:
    for key in ("summarize", "summarize_en", "summary_md_path"):
        summary_path = _existing_file(task.get(key))
        if summary_path is None:
            continue
        summary_time = datetime.fromtimestamp(summary_path.stat().st_mtime, timezone.utc)
        if now - summary_time > retention:
            return True
    return False


def _existing_file(value: str | None) -> Path | None:
    if not value:
        return None
    try:
        path = Path(value)
    except (OSError, ValueError):
        return None
    return path if path.is_file() else None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc(parsed)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
