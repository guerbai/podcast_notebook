from concurrent.futures import Executor, Future

from fastapi.testclient import TestClient

from backend.app import create_app


class ImmediateExecutor(Executor):
    def submit(self, fn, *args, **kwargs):  # noqa: D401
        future = Future()
        future.set_result(fn(*args, **kwargs))
        return future


def test_mocked_end_to_end_task_flow(tmp_path, monkeypatch):
    import backend.tasks as task_module

    def fake_download(audio_url, destination, progress_callback=None, chunk_size=0):
        if progress_callback:
            progress_callback(10, 10)
        path = tmp_path / "downloads" / "episode.mp3"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"audio")
        return path

    def fake_transcribe(audio_path, title, progress_callback=None, model_size="base"):
        if progress_callback:
            progress_callback(30.0, 30.0, "done")
        output = tmp_path / "transcripts" / "episode.txt"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("full transcript", encoding="utf-8")
        return output

    monkeypatch.setattr(task_module, "download_audio", fake_download)
    monkeypatch.setattr(task_module, "transcribe_audio", fake_transcribe)

    client = TestClient(create_app(db_path=tmp_path / "app.db", executor=ImmediateExecutor()))
    response = client.post(
        "/api/tasks",
        json={
            "podcast_title": "大内密谈",
            "rss_url": "http://example.com/feed.xml",
            "episode_title": "vol.1385 从小龙虾跑路到Codex",
            "audio_url": "http://example.com/audio.mp3",
        },
    )
    task_id = response.json()["task"]["id"]

    detail = client.get(f"/api/tasks/{task_id}").json()
    assert detail["status"] == "completed"
    assert detail["output_txt_path"].endswith(".txt")
    assert detail["download_percent"] == 100
    assert detail["transcription_percent"] == 100
    assert detail["audio_duration_seconds"] == 30.0
