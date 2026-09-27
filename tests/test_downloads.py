import subprocess
from pathlib import Path

from backend.downloads import build_download_record
from backend import downloads


def test_build_download_record_includes_progress_defaults():
    record = build_download_record("http://example.com/audio.mp3", "/tmp/audio.mp3")
    assert record["status"] == "queued"
    assert record["bytes_downloaded"] == 0


def test_download_audio_prefers_curl_when_available(monkeypatch, tmp_path):
    destination = tmp_path / "episode.mp3"
    calls = []

    monkeypatch.setattr(downloads.shutil, "which", lambda name: "/usr/bin/curl" if name == "curl" else None)

    def fake_curl(audio_url, destination, progress_callback=None):
        calls.append(("curl", audio_url, destination))
        destination.write_bytes(b"ok")
        if progress_callback:
            progress_callback(2, 2)
        return destination

    def fake_httpx(audio_url, destination, progress_callback=None, chunk_size=0):
        calls.append(("httpx", audio_url, destination))
        destination.write_bytes(b"bad")
        return destination

    monkeypatch.setattr(downloads, "_download_with_curl", fake_curl)
    monkeypatch.setattr(downloads, "_download_with_httpx", fake_httpx)

    result = downloads.download_audio("https://example.com/audio.mp3", destination)

    assert result == destination
    assert calls[0][0] == "curl"


def test_download_audio_retries_lizhi_url_on_numbered_cdn_fallback(monkeypatch, tmp_path):
    destination = tmp_path / "episode.mp3"
    calls = []
    success_url = "https://cdn5.lizhi.fm/audio/2026/04/09/example.mp3"

    monkeypatch.setattr(downloads.shutil, "which", lambda name: "/usr/bin/curl" if name == "curl" else None)

    def fake_curl(audio_url, destination, progress_callback=None):
        calls.append(audio_url)
        if audio_url != success_url:
            raise subprocess.CalledProcessError(56, ["curl", audio_url])
        destination.write_bytes(b"ok")
        if progress_callback:
            progress_callback(2, 2)
        return destination

    monkeypatch.setattr(downloads, "_download_with_curl", fake_curl)

    result = downloads.download_audio("https://cdn.lizhi.fm/audio/2026/04/09/example.mp3", destination)

    assert result == destination
    assert calls == [
        "https://cdn.lizhi.fm/audio/2026/04/09/example.mp3",
        success_url,
    ]


def test_download_url_candidates_adds_lizhi_numbered_cdn_fallbacks():
    assert downloads._download_url_candidates("https://cdn.lizhi.fm/audio/2026/04/09/example.mp3") == [
        "https://cdn.lizhi.fm/audio/2026/04/09/example.mp3",
        "https://cdn5.lizhi.fm/audio/2026/04/09/example.mp3",
        "http://cdn5.lizhi.fm/audio/2026/04/09/example.mp3",
        "http://cdn.lizhi.fm/audio/2026/04/09/example.mp3",
    ]


def test_download_with_curl_sets_browser_like_user_agent(monkeypatch, tmp_path):
    destination = tmp_path / "episode.mp3"
    commands = []

    monkeypatch.setattr(downloads.shutil, "which", lambda name: "/usr/bin/curl" if name == "curl" else None)
    monkeypatch.setattr(downloads, "_probe_content_length_with_curl", lambda audio_url: 2)

    class FakeProcess:
        def __init__(self, command):
            commands.append(command)
            output_path = Path(command[command.index("--output") + 1])
            output_path.write_bytes(b"ok")

        def poll(self):
            return 0

    monkeypatch.setattr(downloads.subprocess, "Popen", FakeProcess)

    downloads._download_with_curl("https://example.com/audio.mp3", destination)

    command = commands[0]
    assert "--user-agent" in command
    assert "Mozilla/5.0" in command


def test_download_with_curl_enables_resume(monkeypatch, tmp_path):
    destination = tmp_path / "episode.mp3"
    commands = []

    monkeypatch.setattr(downloads.shutil, "which", lambda name: "/usr/bin/curl" if name == "curl" else None)
    monkeypatch.setattr(downloads, "_probe_content_length_with_curl", lambda audio_url: 2)

    class FakeProcess:
        def __init__(self, command):
            commands.append(command)
            output_path = Path(command[command.index("--output") + 1])
            output_path.write_bytes(b"ok")

        def poll(self):
            return 0

    monkeypatch.setattr(downloads.subprocess, "Popen", FakeProcess)

    downloads._download_with_curl("https://example.com/audio.mp3", destination)

    command = commands[0]
    assert command[command.index("--continue-at") + 1] == "-"
    assert Path(command[command.index("--output") + 1]).name == "episode.mp3.part"
    assert destination.read_bytes() == b"ok"


def test_download_with_curl_retries_failed_partial_download(monkeypatch, tmp_path):
    destination = tmp_path / "episode.mp3"
    commands = []
    return_codes = [18, 0]

    monkeypatch.setattr(downloads.shutil, "which", lambda name: "/usr/bin/curl" if name == "curl" else None)
    monkeypatch.setattr(downloads, "_probe_content_length_with_curl", lambda audio_url: 4)
    monkeypatch.setattr(downloads.time, "sleep", lambda seconds: None)

    class FakeProcess:
        def __init__(self, command):
            commands.append(command)
            self.return_code = return_codes.pop(0)
            output_path = Path(command[command.index("--output") + 1])
            if self.return_code == 0:
                output_path.write_bytes(b"done")
            else:
                output_path.write_bytes(b"do")

        def poll(self):
            return self.return_code

    monkeypatch.setattr(downloads.subprocess, "Popen", FakeProcess)

    result = downloads._download_with_curl("https://example.com/audio.mp3", destination)

    assert result == destination
    assert len(commands) == 2
    assert all(command[command.index("--continue-at") + 1] == "-" for command in commands)
    assert destination.read_bytes() == b"done"
    assert not downloads._partial_download_path(destination).exists()


def test_probe_content_length_with_curl_sets_browser_like_user_agent(monkeypatch):
    commands = []

    monkeypatch.setattr(downloads.shutil, "which", lambda name: "/usr/bin/curl" if name == "curl" else None)

    class FakeCompletedProcess:
        returncode = 0
        stdout = "HTTP/1.1 200 OK\nContent-Length: 141174059\n"

    def fake_run(command, capture_output, text, check):
        commands.append(command)
        return FakeCompletedProcess()

    monkeypatch.setattr(downloads.subprocess, "run", fake_run)

    total = downloads._probe_content_length_with_curl("https://example.com/audio.mp3")

    assert total == 141174059
    command = commands[0]
    assert "--user-agent" in command
    assert "Mozilla/5.0" in command
