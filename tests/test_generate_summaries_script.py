import fcntl
from threading import Barrier, Lock

import pytest

from scripts import generate_summaries as script
from backend.db import create_task, init_db, update_task


def test_worker_limit_and_failure_does_not_stop_remaining_tasks(tmp_path, monkeypatch):
    barrier = Barrier(2)
    lock = Lock()
    active = 0
    peak = 0
    seen = []

    def generate(task_id, kind, *args, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            seen.append((task_id, kind))
        barrier.wait(timeout=5)
        with lock:
            active -= 1
        if task_id == 1 and kind == "brief":
            raise RuntimeError("provider failed")
        return {"id": task_id}

    monkeypatch.setattr(script, "generate_task_summary", generate)
    result = script.main([
        "--db-path", str(tmp_path / "app.db"), "--workers", "2",
        "--task-id", "1", "--task-id", "2", "--task-id", "3", "--task-id", "4",
    ])
    assert result == 1
    assert peak == 2
    assert sorted(seen) == [(task_id, kind) for task_id in range(1, 5) for kind in ("brief", "detail")]


def test_overlapping_run_is_skipped(tmp_path, monkeypatch):
    def unexpected_call(*args, **kwargs):
        pytest.fail("A locked run must not generate")

    monkeypatch.setattr(script, "generate_task_summary", unexpected_call)
    with (tmp_path / "app.summaries.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert script.main(["--db-path", str(tmp_path / "app.db"), "--all"]) == 0


def test_all_selects_only_completed_tasks_with_transcript_and_missing_summary(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    init_db(db_path)
    transcript = tmp_path / "transcript.txt"
    transcript.write_text("节目转写。", encoding="utf-8")
    selected = []
    eligible = []
    for index, values in enumerate([
        {},
        {"summarize": "/existing.md"},
        {"summarize": "/existing.md", "summarize_brief": "/brief.md"},
        {"status": "queued"},
        {"status": "archived"},
        {"output_txt_path": "/missing-transcript.txt"},
    ]):
        task = create_task({
            "podcast_title": "测试播客", "episode_title": f"节目 {index}",
            "rss_url": "https://example.com/feed", "audio_url": f"https://example.com/{index}.mp3",
            "status": "completed", "output_txt_path": str(transcript), **values,
        }, db_path)
        if index < 2:
            eligible.append(task["id"])

    def generate(task_id, kind, *args, **kwargs):
        selected.append((task_id, kind))
        return {"id": task_id}

    monkeypatch.setattr(script, "generate_task_summary", generate)
    assert script.main(["--db-path", str(db_path), "--all"]) == 0
    assert sorted(selected) == [(task_id, kind) for task_id in eligible for kind in ("brief", "detail")]


def test_after_task_id_excludes_existing_tasks_even_if_they_complete_later(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    init_db(db_path)
    transcript = tmp_path / "transcript.txt"
    transcript.write_text("节目转写。", encoding="utf-8")
    tasks = []
    for index, status in enumerate(["completed", "queued", "completed", "queued"]):
        tasks.append(create_task({
            "podcast_title": "测试播客", "episode_title": f"节目 {index}",
            "rss_url": "https://example.com/feed", "audio_url": f"https://example.com/{index}.mp3",
            "status": status, "output_txt_path": str(transcript), "audio_duration_seconds": 3600,
        }, db_path))
    boundary = tasks[1]["id"]
    selected = []

    def generate(task_id, kind, *args, **kwargs):
        selected.append((task_id, kind))
        update_task(task_id, {script.SUMMARY_FIELDS[kind]: f"/{kind}.md"}, db_path)
        return {"id": task_id}

    monkeypatch.setattr(script, "generate_task_summary", generate)
    argv = ["--db-path", str(db_path), "--after-task-id", str(boundary)]
    assert script.main(argv) == 0
    assert selected == [(tasks[2]["id"], "brief"), (tasks[2]["id"], "detail")]

    update_task(tasks[1]["id"], {"status": "completed"}, db_path)
    update_task(tasks[3]["id"], {"status": "completed"}, db_path)
    selected.clear()
    assert script.main(argv) == 0
    assert selected == [(tasks[3]["id"], "brief"), (tasks[3]["id"], "detail")]
    selected.clear()
    assert script.main(argv) == 0
    assert selected == []


def test_scheduled_duration_limits_skip_ineligible_tasks_and_continue(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "app.db"
    init_db(db_path)
    transcript = tmp_path / "transcript.txt"
    transcript.write_text("节目转写。", encoding="utf-8")
    eligible_ids = []
    skipped_ids = []
    durations = [None, 0, 1799.9, 1800, "unknown", 3600, 10800.1, 10800, float("inf")]
    for index, duration in enumerate(durations):
        task = create_task({
            "podcast_title": "测试播客", "episode_title": f"节目 {index}",
            "rss_url": "https://example.com/feed", "audio_url": f"https://example.com/{index}.mp3",
            "status": "completed", "output_txt_path": str(transcript),
            "audio_duration_seconds": duration,
        }, db_path)
        (eligible_ids if index in (3, 5, 7) else skipped_ids).append(task["id"])
    calls = []
    monkeypatch.setattr(script, "generate_task_summary", lambda task_id, kind, *args, **kwargs: calls.append((task_id, kind)))
    assert script.main(["--db-path", str(db_path), "--after-task-id", "0", "--workers", "2"]) == 0
    assert sorted(calls) == [(task_id, kind) for task_id in eligible_ids for kind in ("brief", "detail")]
    output = capsys.readouterr().out
    for task_id in skipped_ids:
        assert f"Task {task_id}: skipped" in output


@pytest.mark.parametrize("selection", ["--all", "--task-id"])
def test_manual_selection_is_not_limited_by_duration(tmp_path, monkeypatch, selection):
    db_path = tmp_path / "app.db"
    init_db(db_path)
    transcript = tmp_path / "transcript.txt"
    transcript.write_text("节目转写。", encoding="utf-8")
    task = create_task({
        "podcast_title": "测试播客", "episode_title": "短节目",
        "rss_url": "https://example.com/feed", "audio_url": "https://example.com/a.mp3",
        "status": "completed", "output_txt_path": str(transcript), "audio_duration_seconds": 600,
    }, db_path)
    calls = []
    monkeypatch.setattr(script, "generate_task_summary", lambda task_id, kind, *args, **kwargs: calls.append((task_id, kind)))
    argv = ["--db-path", str(db_path), selection]
    if selection == "--task-id":
        argv.append(str(task["id"]))
    assert script.main(argv) == 0
    assert calls == [(task["id"], "brief"), (task["id"], "detail")]


def test_zero_boundary_is_valid_for_a_new_database(tmp_path):
    assert script.main([
        "--db-path", str(tmp_path / "app.db"), "--after-task-id", "0",
    ]) == 0


@pytest.mark.parametrize("argv", [
    [], ["--all", "--task-id", "1"], ["--all", "--workers", "0"],
    ["--after-task-id", "-1"], ["--all", "--after-task-id", "1"],
    ["--task-id", "2", "--after-task-id", "1"], ["--all", "--kind", "both"],
])
def test_requires_explicit_selection_and_positive_workers(argv):
    with pytest.raises(SystemExit):
        script.main(argv)


@pytest.mark.parametrize("kind", ["brief", "detail"])
def test_kind_selects_one_summary_per_task(tmp_path, monkeypatch, kind):
    calls = []
    monkeypatch.setattr(script, "generate_task_summary", lambda task_id, selected, *args, **kwargs: calls.append((task_id, selected)))
    assert script.main(["--db-path", str(tmp_path / "app.db"), "--task-id", "1", "--kind", kind]) == 0
    assert calls == [(1, kind)]
