# Podcast Transcriber Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local web app that lets the user search podcasts by name, search episodes by keyword, select a concrete episode, run a download and transcription task, store task history in SQLite, and write the full transcript to a `.txt` file.

**Architecture:** A local `FastAPI` backend will serve both APIs and a lightweight frontend. The backend will manage podcast discovery, RSS parsing, task orchestration, SQLite persistence, and local transcription with `faster-whisper`. The frontend will provide search, selection, task monitoring, and transcript result views.

**Tech Stack:** Python 3.12+, FastAPI, SQLite, SQLAlchemy or sqlite3, Jinja/vanilla JS or lightweight static frontend, faster-whisper, pytest, httpx/feedparser or equivalent RSS parsing tools.

---

### Task 1: Scaffold the project structure

**Files:**
- Create: `backend/__init__.py`
- Create: `backend/app.py`
- Create: `backend/config.py`
- Create: `backend/models.py`
- Create: `backend/db.py`
- Create: `frontend/index.html`
- Create: `frontend/app.js`
- Create: `frontend/styles.css`
- Create: `tests/test_smoke.py`

**Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from backend.app import create_app


def test_app_starts_and_serves_healthcheck():
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_smoke.py -v`
Expected: FAIL because `backend.app` or `create_app` does not exist yet.

**Step 3: Write minimal implementation**

Create a minimal FastAPI app factory, a basic health endpoint, and static file mounting placeholders.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_smoke.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend frontend tests
git commit -m "feat: scaffold podcast transcriber app"
```

### Task 2: Add SQLite initialization and task models

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/db.py`
- Create: `tests/test_db.py`

**Step 1: Write the failing test**

```python
from backend.db import init_db, list_tasks


def test_init_db_creates_task_storage(tmp_path):
    db_path = tmp_path / "app.db"
    init_db(db_path)
    tasks = list_tasks(db_path)
    assert tasks == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py -v`
Expected: FAIL because DB initialization or task listing is not implemented.

**Step 3: Write minimal implementation**

Add SQLite schema creation for `tasks` and `task_events`, plus helpers to read and write task records.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_db.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend tests
git commit -m "feat: add sqlite task storage"
```

### Task 3: Implement podcast search provider

**Files:**
- Create: `backend/podcast_search.py`
- Create: `tests/test_podcast_search.py`

**Step 1: Write the failing test**

```python
from backend.podcast_search import normalize_search_results


def test_normalize_search_results_keeps_title_and_rss():
    raw = [{"title": "大内密谈", "rss_url": "http://rss.example.com/feed.xml"}]
    result = normalize_search_results(raw)
    assert result[0]["title"] == "大内密谈"
    assert result[0]["rss_url"] == "http://rss.example.com/feed.xml"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_podcast_search.py -v`
Expected: FAIL because the search module does not exist yet.

**Step 3: Write minimal implementation**

Create a search provider abstraction and an initial implementation that can query a podcast directory source and normalize results to a stable internal shape.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_podcast_search.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend tests
git commit -m "feat: add podcast search provider"
```

### Task 4: Implement RSS parsing and episode filtering

**Files:**
- Create: `backend/rss.py`
- Create: `tests/test_rss.py`

**Step 1: Write the failing test**

```python
from backend.rss import filter_episodes


def test_filter_episodes_matches_episode_keyword():
    episodes = [
        {"title": "vol.1385 从小龙虾跑路到Codex", "audio_url": "https://example.com/a.mp3"},
        {"title": "vol.1384 别的话题", "audio_url": "https://example.com/b.mp3"},
    ]
    result = filter_episodes(episodes, "Codex")
    assert len(result) == 1
    assert result[0]["title"].startswith("vol.1385")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_rss.py -v`
Expected: FAIL because RSS parsing and filtering are not implemented.

**Step 3: Write minimal implementation**

Implement:
- RSS fetch and parse
- normalized episode records
- keyword filtering over title and optional description

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_rss.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend tests
git commit -m "feat: add rss episode discovery"
```

### Task 5: Expose search APIs for podcasts and episodes

**Files:**
- Modify: `backend/app.py`
- Create: `tests/test_search_api.py`

**Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from backend.app import create_app


def test_search_endpoints_exist():
    client = TestClient(create_app())
    assert client.get("/api/search/podcasts", params={"q": "大内密谈"}).status_code == 200
    assert client.get("/api/search/episodes", params={"rss_url": "http://example.com/feed.xml", "q": "Codex"}).status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_search_api.py -v`
Expected: FAIL because the API routes do not exist yet.

**Step 3: Write minimal implementation**

Add API routes that call the podcast search and RSS filtering modules and return normalized JSON.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_search_api.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend tests
git commit -m "feat: add discovery api endpoints"
```

### Task 6: Implement task creation and lifecycle persistence

**Files:**
- Create: `backend/tasks.py`
- Modify: `backend/app.py`
- Create: `tests/test_tasks_api.py`

**Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from backend.app import create_app


def test_create_task_returns_queued_task():
    client = TestClient(create_app())
    payload = {
        "podcast_title": "大内密谈",
        "rss_url": "http://example.com/feed.xml",
        "episode_title": "vol.1385 从小龙虾跑路到Codex",
        "audio_url": "http://example.com/audio.mp3",
    }
    response = client.post("/api/tasks", json=payload)
    body = response.json()
    assert response.status_code == 201
    assert body["status"] == "queued"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_tasks_api.py -v`
Expected: FAIL because task creation is not implemented.

**Step 3: Write minimal implementation**

Implement task creation, task listing, task detail retrieval, and persisted lifecycle fields in SQLite.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_tasks_api.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend tests
git commit -m "feat: add task api and persistence"
```

### Task 7: Implement audio download with progress tracking

**Files:**
- Modify: `backend/tasks.py`
- Create: `backend/downloads.py`
- Create: `tests/test_downloads.py`

**Step 1: Write the failing test**

```python
from backend.downloads import build_download_record


def test_build_download_record_includes_progress_defaults():
    record = build_download_record("http://example.com/audio.mp3", "/tmp/audio.mp3")
    assert record["status"] == "queued"
    assert record["bytes_downloaded"] == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_downloads.py -v`
Expected: FAIL because the download helper does not exist.

**Step 3: Write minimal implementation**

Implement a downloader that:
- streams the audio file to disk
- updates task progress and task events
- captures total bytes when available

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_downloads.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend tests
git commit -m "feat: add audio download tracking"
```

### Task 8: Implement transcription pipeline and `.txt` output

**Files:**
- Create: `backend/transcription.py`
- Modify: `backend/tasks.py`
- Create: `tests/test_transcription.py`

**Step 1: Write the failing test**

```python
from backend.transcription import transcript_output_path


def test_transcript_output_path_uses_txt_suffix():
    path = transcript_output_path("vol.1385 从小龙虾跑路到Codex")
    assert str(path).endswith(".txt")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_transcription.py -v`
Expected: FAIL because the transcription module does not exist.

**Step 3: Write minimal implementation**

Implement:
- transcription service wrapper
- transcript assembly from segments
- final transcript write to `data/transcripts/`
- task progress updates for transcription and file output

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_transcription.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend tests
git commit -m "feat: add transcription pipeline"
```

### Task 9: Build the first frontend workflow

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/app.js`
- Modify: `frontend/styles.css`
- Create: `tests/test_frontend_routes.py`

**Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from backend.app import create_app


def test_frontend_page_is_served():
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert "Podcast Name" in response.text
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_frontend_routes.py -v`
Expected: FAIL because the UI is not implemented yet.

**Step 3: Write minimal implementation**

Build a page that:
- searches podcasts
- searches episodes within the selected podcast
- creates a task from a selected episode
- lists tasks with status and progress

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_frontend_routes.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend backend tests
git commit -m "feat: add search and task monitoring ui"
```

### Task 10: Add project-local runtime bootstrap

**Files:**
- Create: `scripts/bootstrap_runtime.sh`
- Create: `requirements.txt`
- Create: `README.md`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

```python
from pathlib import Path


def test_requirements_file_exists():
    assert Path("requirements.txt").exists()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL because the runtime bootstrap files do not exist yet.

**Step 3: Write minimal implementation**

Add:
- dependency manifest
- project-local setup instructions for `.venv`
- script to prepare directories and optional local tool downloads

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scripts requirements.txt README.md tests
git commit -m "chore: add local runtime bootstrap"
```

### Task 11: Add end-to-end task verification

**Files:**
- Create: `tests/test_e2e_task_flow.py`
- Modify: `backend/app.py`
- Modify: `backend/tasks.py`

**Step 1: Write the failing test**

```python
def test_placeholder_end_to_end_task_flow():
    assert False, "replace with a mocked task-flow integration test"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_e2e_task_flow.py -v`
Expected: FAIL because the placeholder test is intentionally failing.

**Step 3: Write minimal implementation**

Replace the placeholder with a mocked end-to-end test that verifies:
- a task can be created
- the task advances through phases
- the transcript path is persisted

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_e2e_task_flow.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend tests
git commit -m "test: add end-to-end task flow coverage"
```

### Task 12: Optional follow-up for summary integration

**Files:**
- Future work only

**Step 1: Decide whether to include summary in v1**

Question: should the first implementation include a model-backed summary stage, or only reserve the extension point and UI placeholder?

**Step 2: If enabled later**

Implement:
- summary provider config
- backend summary job stage
- summary output persistence
- task detail UI rendering

**Step 3: Verify**

Run the app with a configured provider and confirm the transcript and summary both appear in the task detail view.

**Step 4: Commit**

```bash
git commit -m "feat: add transcript summary stage"
```
