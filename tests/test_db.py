from backend.db import create_task, get_task, init_db, list_tasks


def test_init_db_creates_task_storage(tmp_path):
    db_path = tmp_path / "app.db"
    init_db(db_path)
    tasks = list_tasks(db_path)
    assert tasks == []


def test_create_task_reuses_existing_episode_row(tmp_path):
    db_path = tmp_path / "app.db"
    init_db(db_path)

    payload = {
        "podcast_title": "商业就是这样",
        "rss_url": "http://example.com/feed.xml",
        "episode_title": "商业小样38 | 拿什么回馈你，我的股东",
        "audio_url": "http://example.com/audio.mp3",
    }

    first = create_task(payload, db_path)
    second = create_task(payload, db_path)

    assert second["id"] == first["id"]
    tasks = list_tasks(db_path)
    assert len(tasks) == 1


def test_new_task_progress_fields_default_to_zero(tmp_path):
    db_path = tmp_path / "app.db"
    init_db(db_path)

    task = create_task(
        {
            "podcast_title": "大内密谈",
            "rss_url": "http://example.com/feed.xml",
            "episode_title": "vol.1385 从小龙虾跑路到Codex",
            "audio_url": "http://example.com/audio.mp3",
        },
        db_path,
    )

    refreshed = get_task(task["id"], db_path)
    assert refreshed["download_percent"] == 0
    assert refreshed["transcription_percent"] == 0
    assert refreshed["cancel_requested"] == 0
    assert refreshed["summary_md_path"] is None
    assert refreshed["summarize"] == ""


def test_create_task_stores_shownotes_reference(tmp_path):
    db_path = tmp_path / "app.db"
    init_db(db_path)

    task = create_task(
        {
            "podcast_title": "商业就是这样",
            "rss_url": "http://example.com/feed.xml",
            "episode_title": "商业小样38 | 拿什么回馈你，我的股东",
            "audio_url": "http://example.com/audio.mp3",
            "shownotes": "/tmp/shownotes.txt",
            "summarize": "/tmp/summarize.md",
        },
        db_path,
    )

    assert task["shownotes"] == "/tmp/shownotes.txt"
    assert task["summarize"] == "/tmp/summarize.md"
