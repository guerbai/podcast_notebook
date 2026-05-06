from __future__ import annotations

import os
from concurrent.futures import Executor, Future
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.db import create_task, get_task, init_db, list_task_events, update_task
from backend.maintenance import maintain_tasks


class NoopExecutor(Executor):
    def submit(self, fn, *args, **kwargs):
        future = Future()
        future.set_result(None)
        return future


def test_maintain_tasks_restarts_stale_incomplete_task(tmp_path):
    db_path = tmp_path / "app.db"
    init_db(db_path)
    task = create_task(
        {
            "podcast_title": "大内密谈",
            "rss_url": "http://example.com/feed.xml",
            "episode_title": "vol.1385 从小龙虾跑路到 Codex",
            "audio_url": "http://example.com/audio.mp3",
        },
        db_path,
    )
    now = datetime(2026, 5, 3, 12, 0, tzinfo=timezone.utc)
    update_task(
        task["id"],
        {
            "status": "running",
            "progress_stage": "transcribing",
            "started_at": (now - timedelta(hours=2)).isoformat(),
            "transcription_percent": 50.0,
        },
        db_path,
    )

    result = maintain_tasks(db_path=db_path, now=now, executor=NoopExecutor())

    assert result.restarted_task_ids == [task["id"]]
    assert len(result.replacement_task_ids) == 1
    assert result.replacement_task_ids[0] != task["id"]
    assert get_task(task["id"], db_path) is None
    replacement = get_task(result.replacement_task_ids[0], db_path)
    assert replacement["status"] == "queued"
    assert replacement["started_at"] is None


def test_maintain_tasks_can_restart_stale_task_through_injected_restarter(tmp_path):
    db_path = tmp_path / "app.db"
    init_db(db_path)
    task = create_task(
        {
            "podcast_title": "大内密谈",
            "rss_url": "http://example.com/feed.xml",
            "episode_title": "vol.1385 从小龙虾跑路到 Codex",
            "audio_url": "http://example.com/audio.mp3",
        },
        db_path,
    )
    now = datetime(2026, 5, 3, 12, 0, tzinfo=timezone.utc)
    update_task(
        task["id"],
        {
            "status": "running",
            "progress_stage": "transcribing",
            "started_at": (now - timedelta(hours=2)).isoformat(),
            "transcription_percent": 50.0,
        },
        db_path,
    )
    restarted_ids = []

    def restart_task_func(task_id: int):
        restarted_ids.append(task_id)
        return {"task": {"id": 99}}

    result = maintain_tasks(db_path=db_path, now=now, restart_task_func=restart_task_func)

    assert restarted_ids == [task["id"]]
    assert result.restarted_task_ids == [task["id"]]
    assert result.replacement_task_ids == [99]


def test_maintain_tasks_keeps_completed_task_with_old_start_time(tmp_path):
    db_path = tmp_path / "app.db"
    init_db(db_path)
    task = create_task(
        {
            "podcast_title": "商业就是这样",
            "rss_url": "http://example.com/feed.xml",
            "episode_title": "商业小样38 | 拿什么回馈你，我的股东",
            "audio_url": "http://example.com/audio.mp3",
        },
        db_path,
    )
    now = datetime(2026, 5, 3, 12, 0, tzinfo=timezone.utc)
    transcript_path = tmp_path / "transcripts" / "episode.txt"
    transcript_path.parent.mkdir(parents=True)
    transcript_path.write_text("full transcript", encoding="utf-8")
    update_task(
        task["id"],
        {
            "status": "completed",
            "progress_stage": "completed",
            "started_at": (now - timedelta(hours=2)).isoformat(),
            "transcription_percent": 100.0,
            "output_txt_path": str(transcript_path),
        },
        db_path,
    )

    result = maintain_tasks(db_path=db_path, now=now, executor=NoopExecutor())

    assert result.restarted_task_ids == []
    assert get_task(task["id"], db_path)["status"] == "completed"


def test_maintain_tasks_deletes_audio_when_summary_file_is_older_than_24_hours(tmp_path):
    db_path = tmp_path / "app.db"
    init_db(db_path)
    task = create_task(
        {
            "podcast_title": "第一财经",
            "rss_url": "http://example.com/feed.xml",
            "episode_title": "提前布局能源股，巴菲特又赢麻了？",
            "audio_url": "http://example.com/audio.mp3",
        },
        db_path,
    )
    now = datetime(2026, 5, 3, 12, 0, tzinfo=timezone.utc)
    audio_path = tmp_path / "downloads" / "episode.mp3"
    summary_path = tmp_path / "summaries" / "episode-summarize.md"
    audio_path.parent.mkdir(parents=True)
    summary_path.parent.mkdir(parents=True)
    audio_path.write_bytes(b"audio")
    summary_path.write_text("# 总结\n", encoding="utf-8")
    old_timestamp = (now - timedelta(hours=25)).timestamp()
    os.utime(summary_path, (old_timestamp, old_timestamp))
    update_task(
        task["id"],
        {
            "status": "completed",
            "progress_stage": "completed",
            "audio_file_path": str(audio_path),
            "summarize": str(summary_path),
        },
        db_path,
    )

    result = maintain_tasks(db_path=db_path, now=now, executor=NoopExecutor())

    assert result.deleted_audio_paths == [str(audio_path)]
    assert not audio_path.exists()
    assert summary_path.exists()
    assert get_task(task["id"], db_path)["audio_file_path"] is None
    events = [event["message"] for event in list_task_events(task["id"], db_path)]
    assert "Deleted audio after summarize aged past retention window" in events


def test_maintain_tasks_keeps_audio_when_summary_file_is_recent(tmp_path):
    db_path = tmp_path / "app.db"
    init_db(db_path)
    task = create_task(
        {
            "podcast_title": "第一财经",
            "rss_url": "http://example.com/feed.xml",
            "episode_title": "提前布局能源股，巴菲特又赢麻了？",
            "audio_url": "http://example.com/audio.mp3",
        },
        db_path,
    )
    now = datetime(2026, 5, 3, 12, 0, tzinfo=timezone.utc)
    audio_path = tmp_path / "downloads" / "episode.mp3"
    summary_path = tmp_path / "summaries" / "episode-summarize.md"
    audio_path.parent.mkdir(parents=True)
    summary_path.parent.mkdir(parents=True)
    audio_path.write_bytes(b"audio")
    summary_path.write_text("# 总结\n", encoding="utf-8")
    recent_timestamp = (now - timedelta(hours=23)).timestamp()
    os.utime(summary_path, (recent_timestamp, recent_timestamp))
    update_task(
        task["id"],
        {
            "status": "completed",
            "progress_stage": "completed",
            "audio_file_path": str(audio_path),
            "summarize": str(summary_path),
        },
        db_path,
    )

    result = maintain_tasks(db_path=db_path, now=now, executor=NoopExecutor())

    assert result.deleted_audio_paths == []
    assert audio_path.exists()
    assert get_task(task["id"], db_path)["audio_file_path"] == str(audio_path)


def test_maintenance_script_restarts_tasks_through_app_api(tmp_path, monkeypatch, capsys):
    from scripts import maintain_tasks as script

    db_path = tmp_path / "app.db"
    seen = {}
    fake_restarter = object()

    def fake_maintain_tasks(**kwargs):
        seen["db_path"] = Path(kwargs["db_path"])
        seen["restart_task_func"] = kwargs.get("restart_task_func")
        return script.MaintenanceResult(
            restarted_task_ids=[1],
            replacement_task_ids=[2],
            deleted_audio_paths=["/tmp/podcast_notebook_logs/episode.mp3"],
        )

    monkeypatch.setattr(script, "ensure_app_is_running", lambda api_base_url: None)
    monkeypatch.setattr(script, "make_api_task_restarter", lambda api_base_url: fake_restarter)
    monkeypatch.setattr(script, "maintain_tasks", fake_maintain_tasks)

    exit_code = script.main(["--db-path", str(db_path)])

    assert exit_code == 0
    assert seen["db_path"] == db_path
    assert seen["restart_task_func"] is fake_restarter
    output = capsys.readouterr().out
    assert "mode: restart stale tasks through the running app API, like clicking retry in the frontend" in output
    assert "restarted task ids: 1" in output
    assert "replacement task ids: 2" in output
    assert "- /tmp/podcast_notebook_logs/episode.mp3" in output


def test_maintenance_script_app_api_ignores_environment_proxy(monkeypatch):
    from scripts import maintain_tasks as script

    captured = []
    posted_urls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"task": {"id": 2}}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.append(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            return FakeResponse()

        def post(self, url):
            posted_urls.append(url)
            return FakeResponse()

    monkeypatch.setattr(script.httpx, "Client", FakeClient)

    script.ensure_app_is_running("http://127.0.0.1:8000")
    result = script.make_api_task_restarter("http://127.0.0.1:8000")(12)

    assert result == {"task": {"id": 2}}
    assert posted_urls == ["http://127.0.0.1:8000/api/tasks/12/restart"]
    assert captured == [
        {"timeout": 5, "trust_env": False},
        {"timeout": 20, "trust_env": False},
    ]
