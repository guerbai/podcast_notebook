from concurrent.futures import Executor, Future
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.db import add_task_event, create_task, get_task, init_db, update_task


class NoopExecutor(Executor):
    def submit(self, fn, *args, **kwargs):
        future = Future()
        future.set_result(None)
        return future


def test_create_task_returns_queued_task(tmp_path):
    client = TestClient(create_app(db_path=tmp_path / "app.db", executor=NoopExecutor()))
    payload = {
        "podcast_title": "大内密谈",
        "rss_url": "http://example.com/feed.xml",
        "episode_title": "vol.1385 从小龙虾跑路到Codex",
        "audio_url": "http://example.com/audio.mp3",
    }
    response = client.post("/api/tasks", json=payload)
    body = response.json()
    assert response.status_code == 201
    assert body["result"] == "created"
    assert body["task"]["status"] == "queued"


def test_create_task_accepts_and_returns_shownotes(tmp_path, monkeypatch):
    import backend.tasks as task_module

    monkeypatch.setattr(task_module, "SHOWNOTES_DIR", tmp_path / "shownotes")
    client = TestClient(create_app(db_path=tmp_path / "app.db", executor=NoopExecutor()))
    payload = {
        "podcast_title": "大内密谈",
        "rss_url": "http://example.com/feed.xml",
        "episode_title": "vol.1385 从小龙虾跑路到Codex",
        "audio_url": "http://example.com/audio.mp3",
        "shownotes": "<p>本期聊 Codex 和工作流。</p>",
    }

    response = client.post("/api/tasks", json=payload)

    assert response.status_code == 201
    shownotes_path = response.json()["task"]["shownotes"]
    assert shownotes_path.endswith(".txt")
    assert (tmp_path / "shownotes").joinpath(shownotes_path.rsplit("/", 1)[-1]).exists()
    assert "<p>" not in (tmp_path / "shownotes").joinpath(shownotes_path.rsplit("/", 1)[-1]).read_text(encoding="utf-8")
    assert "本期聊 Codex 和工作流。" in (tmp_path / "shownotes").joinpath(shownotes_path.rsplit("/", 1)[-1]).read_text(encoding="utf-8")

    shownotes_response = client.get(f"/api/tasks/{response.json()['task']['id']}/shownotes")
    assert shownotes_response.status_code == 200
    assert shownotes_response.json()["content"] == "本期聊 Codex 和工作流。"
    assert shownotes_response.json()["path"] == shownotes_path


def test_create_task_fetches_shownotes_when_payload_omits_them(tmp_path, monkeypatch):
    import backend.tasks as task_module

    monkeypatch.setattr(task_module, "SHOWNOTES_DIR", tmp_path / "shownotes")
    monkeypatch.setattr(
        task_module,
        "fetch_episodes",
        lambda rss_url, keyword="": [
            {
                "title": "Vol.254 大牌的创意总监为什么成了高危职业？",
                "guid": "xmly_track_972008291",
                "audio_url": "http://example.com/audio.mp3",
                "shownotes": "<p>服务端补抓 shownotes。</p>",
            }
        ],
    )
    client = TestClient(create_app(db_path=tmp_path / "app.db", executor=NoopExecutor()))
    payload = {
        "podcast_title": "商业就是这样",
        "rss_url": "http://example.com/feed.xml",
        "episode_title": "Vol.254 大牌的创意总监为什么成了高危职业？",
        "episode_guid": "xmly_track_972008291",
        "audio_url": "http://example.com/audio.mp3",
    }

    response = client.post("/api/tasks", json=payload)

    assert response.status_code == 201
    shownotes_path = response.json()["task"]["shownotes"]
    assert shownotes_path.endswith(".txt")
    assert "服务端补抓 shownotes。" in (tmp_path / "shownotes").joinpath(shownotes_path.rsplit("/", 1)[-1]).read_text(encoding="utf-8")


def test_app_start_migrates_inline_shownotes_to_file(tmp_path, monkeypatch):
    import backend.tasks as task_module

    db_path = tmp_path / "app.db"
    monkeypatch.setattr(task_module, "SHOWNOTES_DIR", tmp_path / "shownotes")
    init_db(db_path)
    task = create_task(
        {
            "podcast_title": "商业就是这样",
            "rss_url": "http://example.com/feed.xml",
            "episode_title": "Vol.254 大牌的创意总监为什么成了高危职业？",
            "audio_url": "http://example.com/audio.mp3",
            "shownotes": "<p>旧格式 shownotes。</p>",
        },
        db_path,
    )

    create_app(db_path=db_path, executor=NoopExecutor())
    migrated = get_task(task["id"], db_path)

    assert migrated["shownotes"].endswith(".txt")
    assert Path(migrated["shownotes"]).read_text(encoding="utf-8") == "旧格式 shownotes。"


def test_create_task_returns_existing_result_for_duplicate(tmp_path):
    client = TestClient(create_app(db_path=tmp_path / "app.db", executor=NoopExecutor()))
    payload = {
        "podcast_title": "商业就是这样",
        "rss_url": "http://example.com/feed.xml",
        "episode_title": "商业小样38 | 拿什么回馈你，我的股东",
        "audio_url": "http://example.com/audio.mp3",
    }

    first = client.post("/api/tasks", json=payload)
    second = client.post("/api/tasks", json=payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["result"] == "created"
    assert second.json()["result"] == "existing"
    assert second.json()["task"]["id"] == first.json()["task"]["id"]


def test_existing_task_with_shownotes_does_not_refetch_shownotes(tmp_path, monkeypatch):
    import backend.tasks as task_module

    monkeypatch.setattr(task_module, "SHOWNOTES_DIR", tmp_path / "shownotes")
    client = TestClient(create_app(db_path=tmp_path / "app.db", executor=NoopExecutor()))
    payload = {
        "podcast_title": "商业就是这样",
        "rss_url": "http://example.com/feed.xml",
        "episode_title": "商业小样38 | 拿什么回馈你，我的股东",
        "audio_url": "http://example.com/audio.mp3",
        "shownotes": "已有 shownotes。",
    }
    first = client.post("/api/tasks", json=payload)
    calls = []
    monkeypatch.setattr(task_module, "fetch_episodes", lambda rss_url, keyword="": calls.append((rss_url, keyword)) or [])

    second = client.post(
        "/api/tasks",
        json={key: value for key, value in payload.items() if key != "shownotes"},
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["result"] == "existing"
    assert calls == []


def test_delete_task_removes_record_and_files(tmp_path):
    client = TestClient(create_app(db_path=tmp_path / "app.db", executor=NoopExecutor()))
    payload = {
        "podcast_title": "大内密谈",
        "rss_url": "http://example.com/feed.xml",
        "episode_title": "vol.1385 从小龙虾跑路到Codex",
        "audio_url": "http://example.com/audio.mp3",
    }
    task = client.post("/api/tasks", json=payload).json()["task"]

    audio_path = tmp_path / "downloads" / "episode.mp3"
    transcript_path = tmp_path / "transcripts" / "episode.txt"
    summarize_path = tmp_path / "summaries" / "episode-summarize.md"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    summarize_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"audio")
    transcript_path.write_text("transcript", encoding="utf-8")
    summarize_path.write_text("# summarize", encoding="utf-8")

    update_task(
        task["id"],
        {
            "status": "failed",
            "progress_stage": "failed",
            "audio_file_path": str(audio_path),
            "output_txt_path": str(transcript_path),
            "summarize": str(summarize_path),
        },
        tmp_path / "app.db",
    )
    add_task_event(task["id"], "Task failed", db_path=tmp_path / "app.db")

    response = client.delete(f"/api/tasks/{task['id']}")

    assert response.status_code == 204
    assert client.get(f"/api/tasks/{task['id']}").status_code == 404
    assert not audio_path.exists()
    assert not transcript_path.exists()
    assert not summarize_path.exists()


def test_delete_running_task_removes_record_immediately(tmp_path):
    client = TestClient(create_app(db_path=tmp_path / "app.db", executor=NoopExecutor()))
    payload = {
        "podcast_title": "大内密谈",
        "rss_url": "http://example.com/feed.xml",
        "episode_title": "vol.1385 从小龙虾跑路到Codex",
        "audio_url": "http://example.com/audio.mp3",
    }
    task = client.post("/api/tasks", json=payload).json()["task"]
    update_task(
        task["id"],
        {
            "status": "running",
            "progress_stage": "downloading_audio",
        },
        tmp_path / "app.db",
    )

    response = client.delete(f"/api/tasks/{task['id']}")

    assert response.status_code == 204
    assert client.get(f"/api/tasks/{task['id']}").status_code == 404


def test_restart_running_task_recreates_task_immediately(tmp_path, monkeypatch):
    import backend.tasks as task_module

    monkeypatch.setattr(task_module, "SHOWNOTES_DIR", tmp_path / "shownotes")
    client = TestClient(create_app(db_path=tmp_path / "app.db", executor=NoopExecutor()))
    payload = {
        "podcast_title": "大内密谈",
        "rss_url": "http://example.com/feed.xml",
        "episode_title": "vol.1385 从小龙虾跑路到Codex",
        "audio_url": "http://example.com/audio.mp3",
        "shownotes": "保留到新任务。",
    }
    task = client.post("/api/tasks", json=payload).json()["task"]
    update_task(
        task["id"],
        {
            "status": "running",
            "progress_stage": "transcribing",
        },
        tmp_path / "app.db",
    )

    response = client.post(f"/api/tasks/{task['id']}/restart")

    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "restarted"
    assert body["task"]["id"] != task["id"]
    assert body["task"]["status"] == "queued"
    shownotes_path = body["task"]["shownotes"]
    assert shownotes_path.endswith(".txt")
    assert "保留到新任务。" in (tmp_path / "shownotes").joinpath(shownotes_path.rsplit("/", 1)[-1]).read_text(encoding="utf-8")
    assert client.get(f"/api/tasks/{task['id']}").status_code == 404


def test_task_summary_endpoint_returns_markdown_content(tmp_path):
    client = TestClient(create_app(db_path=tmp_path / "app.db", executor=NoopExecutor()))
    payload = {
        "podcast_title": "大内密谈",
        "rss_url": "http://example.com/feed.xml",
        "episode_title": "vol.1385 从小龙虾跑路到Codex",
        "audio_url": "http://example.com/audio.mp3",
    }
    task = client.post("/api/tasks", json=payload).json()["task"]

    summary_path = tmp_path / "summaries" / "vol1385.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("# 标题\n\n- 要点一\n", encoding="utf-8")

    update_task(
        task["id"],
        {"summary_md_path": str(summary_path)},
        tmp_path / "app.db",
    )

    response = client.get(f"/api/tasks/{task['id']}/summary")

    assert response.status_code == 200
    assert response.json()["markdown"].startswith("# 标题")
    assert response.json()["title"] == task["episode_title"]


def test_task_summarize_endpoint_returns_file_content(tmp_path):
    client = TestClient(create_app(db_path=tmp_path / "app.db", executor=NoopExecutor()))
    payload = {
        "podcast_title": "大内密谈",
        "rss_url": "http://example.com/feed.xml",
        "episode_title": "vol.1385 从小龙虾跑路到Codex",
        "audio_url": "http://example.com/audio.mp3",
    }
    task = client.post("/api/tasks", json=payload).json()["task"]

    summarize_path = tmp_path / "summaries" / "vol1385-summarize.md"
    summarize_path.parent.mkdir(parents=True, exist_ok=True)
    summarize_path.write_text("# 总结\n\n- 要点一\n", encoding="utf-8")

    update_task(
        task["id"],
        {"summarize": str(summarize_path)},
        tmp_path / "app.db",
    )

    response = client.get(f"/api/tasks/{task['id']}/summarize")

    assert response.status_code == 200
    assert response.json()["content"].startswith("# 总结")
    assert response.json()["path"] == str(summarize_path)


def test_task_summarize_endpoint_returns_english_content_when_requested(tmp_path):
    client = TestClient(create_app(db_path=tmp_path / "app.db", executor=NoopExecutor()))
    payload = {
        "podcast_title": "大内密谈",
        "rss_url": "http://example.com/feed.xml",
        "episode_title": "vol.1385 从小龙虾跑路到Codex",
        "audio_url": "http://example.com/audio.mp3",
    }
    task = client.post("/api/tasks", json=payload).json()["task"]

    zh_path = tmp_path / "summaries" / "vol1385-summarize.md"
    en_path = tmp_path / "summaries" / "vol1385-summarize.en.md"
    zh_path.parent.mkdir(parents=True, exist_ok=True)
    zh_path.write_text("# 总结\n\n- 要点一\n", encoding="utf-8")
    en_path.write_text("# Summary\n\n- Key point\n", encoding="utf-8")

    update_task(
        task["id"],
        {
            "summarize": str(zh_path),
            "summarize_en": str(en_path),
        },
        tmp_path / "app.db",
    )

    response = client.get(f"/api/tasks/{task['id']}/summarize", params={"lang": "en"})

    assert response.status_code == 200
    assert response.json()["title"] == "Summary"
    assert response.json()["content"].startswith("# Summary")
    assert response.json()["path"] == str(en_path)


def test_generate_summarize_endpoint_returns_503_without_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("PODCAST_NOTEBOOK_LLM_API_KEY", raising=False)
    client = TestClient(create_app(db_path=tmp_path / "app.db", executor=NoopExecutor()))
    payload = {
        "podcast_title": "大内密谈",
        "rss_url": "http://example.com/feed.xml",
        "episode_title": "vol.1385 从小龙虾跑路到Codex",
        "audio_url": "http://example.com/audio.mp3",
    }
    task = client.post("/api/tasks", json=payload).json()["task"]
    transcript_path = tmp_path / "transcripts" / "episode.txt"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text("完整转写内容", encoding="utf-8")
    update_task(
        task["id"],
        {
            "status": "completed",
            "progress_stage": "completed",
            "output_txt_path": str(transcript_path),
        },
        tmp_path / "app.db",
    )

    response = client.post(f"/api/tasks/{task['id']}/summarize", json={"lang": "zh-CN"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Summarize API key is not configured"


def test_generate_summarize_endpoint_updates_task_with_model_output(tmp_path, monkeypatch):
    import backend.summarizer as summarizer_module

    class FakeClient:
        def __init__(self, config):
            self.config = config

        def generate(self, prompt: str, language: str) -> str:
            assert "完整转写内容" in prompt
            assert language == "zh-CN"
            return "# 总结\n\n- API 生成的要点\n"

    monkeypatch.setenv("PODCAST_NOTEBOOK_LLM_API_KEY", "test-key")
    monkeypatch.setattr(summarizer_module, "SUMMARIES_DIR", tmp_path / "summaries")
    monkeypatch.setattr(summarizer_module, "OpenAICompatibleSummaryClient", FakeClient)
    client = TestClient(create_app(db_path=tmp_path / "app.db", executor=NoopExecutor()))
    payload = {
        "podcast_title": "大内密谈",
        "rss_url": "http://example.com/feed.xml",
        "episode_title": "vol.1385 从小龙虾跑路到Codex",
        "audio_url": "http://example.com/audio.mp3",
    }
    task = client.post("/api/tasks", json=payload).json()["task"]
    transcript_path = tmp_path / "transcripts" / "episode.txt"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text("完整转写内容", encoding="utf-8")
    update_task(
        task["id"],
        {
            "status": "completed",
            "progress_stage": "completed",
            "output_txt_path": str(transcript_path),
        },
        tmp_path / "app.db",
    )

    response = client.post(f"/api/tasks/{task['id']}/summarize", json={"lang": "zh-CN"})

    assert response.status_code == 200
    updated = response.json()["task"]
    assert updated["summarize"].endswith("-summarize.md")
    assert Path(updated["summarize"]).read_text(encoding="utf-8").startswith("# 总结")
