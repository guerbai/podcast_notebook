# Task Lifecycle And UI Polish Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make task creation duplicate-aware, allow delete and restart for running tasks, surface separate download and transcription progress, replace browser dialogs with app UI, and stabilize card layout and detail expansion.

**Architecture:** Keep the current FastAPI, SQLite, and in-process worker architecture, but extend the task model with cancellation and split progress fields. The frontend remains a backend-served static app, but switches from browser primitives and native `<details>` to explicit stateful rendering so polling no longer resets the UI.

**Tech Stack:** Python 3.12+, FastAPI, sqlite3, ThreadPoolExecutor, pytest, vanilla JavaScript, static HTML/CSS.

---

### Task 1: Add task schema support for dedupe, cancellation, and split progress

**Files:**
- Modify: `backend/db.py`
- Modify: `backend/models.py`
- Test: `tests/test_db.py`

**Step 1: Write the failing tests**

Add tests that prove:

```python
def test_create_task_reuses_existing_episode_row(tmp_path):
    ...
    first = create_task(...)
    second = create_task(...)
    assert second["id"] == first["id"]
    assert list_tasks(...) == [first]


def test_task_progress_fields_default_to_zero(tmp_path):
    ...
    task = create_task(...)
    assert task["download_percent"] == 0
    assert task["transcription_percent"] == 0
    assert task["cancel_requested"] is False
```

**Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_db.py -v`

Expected: FAIL because the current schema and helpers do not support uniqueness or the new fields.

**Step 3: Write minimal implementation**

- Add `download_percent`, `transcription_percent`, and `cancel_requested` columns.
- Add a unique index on `podcast_title` and `episode_title`.
- Update row serialization and create/update helpers to expose the new fields.

**Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_db.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/db.py backend/models.py tests/test_db.py
git commit -m "feat: add task lifecycle schema fields"
```

### Task 2: Make create-task duplicate-aware and action-oriented

**Files:**
- Modify: `backend/app.py`
- Modify: `backend/tasks.py`
- Test: `tests/test_tasks_api.py`

**Step 1: Write the failing tests**

Add tests that prove:

```python
def test_create_task_returns_existing_result_for_duplicate(...):
    first = client.post("/api/tasks", json=payload)
    second = client.post("/api/tasks", json=payload)
    assert first.json()["result"] == "created"
    assert second.json()["result"] == "existing"
    assert second.json()["task"]["id"] == first.json()["task"]["id"]
```

**Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_tasks_api.py -v`

Expected: FAIL because the current create endpoint always creates or errors instead of returning a structured duplicate result.

**Step 3: Write minimal implementation**

- Have create return `{task, result, message}`.
- Reuse the existing task row when the episode already exists.
- Do not queue a second worker for a duplicate request.

**Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_tasks_api.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/app.py backend/tasks.py tests/test_tasks_api.py
git commit -m "feat: return existing task for duplicate create"
```

### Task 3: Implement cooperative cancellation for delete and restart

**Files:**
- Modify: `backend/tasks.py`
- Modify: `backend/app.py`
- Test: `tests/test_tasks_api.py`
- Test: `tests/test_e2e_task_flow.py`

**Step 1: Write the failing tests**

Add tests that prove:

```python
def test_delete_running_task_requests_cancellation(...):
    ...
    response = client.delete(f"/api/tasks/{task_id}")
    assert response.status_code == 202
    assert response.json()["result"] == "cancelling"


def test_restart_running_task_requests_cancellation_and_requeue(...):
    ...
    response = client.post(f"/api/tasks/{task_id}/restart")
    assert response.status_code == 202
    assert response.json()["result"] == "restarting"
```

Also add an integration-style test around the worker callback path to prove a cancelled run stops before final output write and can later be restarted on the same task id.

**Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_tasks_api.py tests/test_e2e_task_flow.py -v`

Expected: FAIL because running tasks cannot currently be deleted and there is no restart endpoint.

**Step 3: Write minimal implementation**

- Add `cancel_requested` helpers.
- Make worker code check for cancellation between download and transcription callbacks.
- Add delete semantics:
  - terminal: delete immediately
  - running: mark cancelling and return accepted
- Add restart endpoint:
  - terminal: reset and queue same task id
  - running: mark cancellation and queue restart-after-cancel on same task id

**Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_tasks_api.py tests/test_e2e_task_flow.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/app.py backend/tasks.py tests/test_tasks_api.py tests/test_e2e_task_flow.py
git commit -m "feat: support task cancellation and restart"
```

### Task 4: Expose separate download and transcription progress

**Files:**
- Modify: `backend/tasks.py`
- Modify: `backend/transcription.py`
- Test: `tests/test_e2e_task_flow.py`

**Step 1: Write the failing tests**

Add tests that prove:

```python
def test_task_updates_split_progress_fields(...):
    ...
    assert task["download_percent"] == 100
    assert task["transcription_percent"] > 0
```

Include a case that ensures download progress no longer distorts transcription progress and that both fields end at `100`.

**Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_e2e_task_flow.py -v`

Expected: FAIL because only one synthetic progress number is currently updated.

**Step 3: Write minimal implementation**

- Update download callbacks to set `download_percent`.
- Update transcription callbacks to set `transcription_percent`.
- Preserve `progress_percent` only as a derived overall helper if still needed.

**Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_e2e_task_flow.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/tasks.py backend/transcription.py tests/test_e2e_task_flow.py
git commit -m "feat: track split task progress"
```

### Task 5: Replace browser dialogs with custom modal and toast plumbing

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/app.js`
- Modify: `frontend/styles.css`
- Test: `tests/test_frontend_copy.py`

**Step 1: Write the failing tests**

Add tests that prove the page contains:

```python
assert "data-role=\"toast-region\"" in html
assert "data-role=\"confirm-modal\"" in html
```

and does not contain legacy browser-dialog-specific copy assumptions.

**Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_frontend_copy.py -v`

Expected: FAIL because the current page has no toast region or custom modal structure.

**Step 3: Write minimal implementation**

- Add toast host and confirmation modal markup.
- Replace `window.alert` and `window.confirm` paths with app-level UI handlers.
- Render backend `message` and `detail` text in toast content.

**Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_frontend_copy.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add frontend/index.html frontend/app.js frontend/styles.css tests/test_frontend_copy.py
git commit -m "feat: add custom feedback UI"
```

### Task 6: Preserve task detail expansion and add create-task feedback

**Files:**
- Modify: `frontend/app.js`
- Modify: `frontend/index.html`
- Modify: `frontend/styles.css`
- Test: `tests/test_frontend_routes.py`
- Test: `tests/test_frontend_copy.py`

**Step 1: Write the failing tests**

Add tests that prove the client bundle contains the markers for:

```python
assert "expandedTaskIds" in js
assert "isCreatingTask" in js
assert "已定位到现有任务" in js
```

**Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_frontend_routes.py tests/test_frontend_copy.py -v`

Expected: FAIL because the current client does not keep stable expanded state or create-action feedback.

**Step 3: Write minimal implementation**

- Track expanded tasks in explicit frontend state keyed by task id.
- Stop using native `<details>` toggle behavior.
- Add loading state to the create button and in-page toast feedback for `created` and `existing`.
- Scroll and highlight the existing task card when duplicate create returns `existing`.

**Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_frontend_routes.py tests/test_frontend_copy.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add frontend/index.html frontend/app.js frontend/styles.css tests/test_frontend_routes.py tests/test_frontend_copy.py
git commit -m "feat: stabilize task detail panels"
```

### Task 7: Rework episode and task card layouts for alignment and dual progress

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/app.js`
- Modify: `frontend/styles.css`
- Test: `tests/test_frontend_copy.py`

**Step 1: Write the failing tests**

Add assertions for the new structure markers:

```python
assert "episode-card__actions" in css_or_html
assert "task-progress task-progress--download" in html_or_js
assert "task-progress task-progress--transcription" in html_or_js
```

**Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_frontend_copy.py -v`

Expected: FAIL because the current markup and styles do not expose the aligned layout or dual progress rows.

**Step 3: Write minimal implementation**

- Use grid-based episode result cards with fixed action column.
- Use task-card sections for metadata, dual progress rows, and stable action rail.
- Keep the editorial look while tightening spacing and alignment.

**Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_frontend_copy.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add frontend/index.html frontend/app.js frontend/styles.css tests/test_frontend_copy.py
git commit -m "feat: align episode and task cards"
```

### Task 8: Run full verification and update docs if behavior changed

**Files:**
- Modify: `README.md`
- Test: `tests/test_config.py`
- Test: `tests/test_db.py`
- Test: `tests/test_downloads.py`
- Test: `tests/test_e2e_task_flow.py`
- Test: `tests/test_frontend_copy.py`
- Test: `tests/test_frontend_routes.py`
- Test: `tests/test_podcast_search.py`
- Test: `tests/test_rss.py`
- Test: `tests/test_search_api.py`
- Test: `tests/test_smoke.py`
- Test: `tests/test_tasks_api.py`
- Test: `tests/test_transcription.py`

**Step 1: Run focused verifications first**

Run:

```bash
pytest tests/test_db.py tests/test_tasks_api.py tests/test_e2e_task_flow.py tests/test_frontend_copy.py tests/test_frontend_routes.py -v
```

Expected: PASS

**Step 2: Update README if user-facing task behavior changed**

Document:

- duplicate task behavior
- delete/restart semantics
- split progress display

**Step 3: Run the full suite**

Run:

```bash
pytest -v
```

Expected: PASS

**Step 4: Commit**

```bash
git add README.md tests
git commit -m "docs: describe refined task lifecycle"
```

Plan complete and saved to `docs/plans/2026-04-15-task-lifecycle-ui-polish.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
