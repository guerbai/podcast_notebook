# Podcast Task Favorites Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent per-episode favorites and a one-click view containing every favorited task.

**Architecture:** Store favorite state as an `is_favorite` integer column on the existing `tasks` table and expose one idempotent task update endpoint. The frontend updates the matching item in `state.tasks`; both the card star and favorites view derive from that single source of truth.

**Tech Stack:** Python 3, SQLite, FastAPI, Pydantic, vanilla JavaScript, HTML, CSS, pytest, FastAPI TestClient

**Spec:** `docs/superpowers/specs/2026-08-29-task-favorites-design.md`

## Global Constraints

- Existing tasks migrate to `is_favorite=0`; new tasks always start unfavorited.
- `PUT /api/tasks/{task_id}/favorite` accepts only `{"favorite": true|false}` and is idempotent.
- The favorites view includes archived tasks and all dates and bypasses status, date, and podcast filters without clearing their selections.
- Use a GitHub-style five-point star: muted outline when inactive and the existing `--teal` color when active.
- Localize labels and empty-state copy in Chinese and English.
- Keep download, transcription, summary, archive, and restart behavior unchanged.
- Add no tags, notes, folders, favorite ordering, bulk actions, dependencies, or separate favorites cache.

---

### Task 1: Persist Favorite State

**Files:**
- Modify: `backend/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Consumes: existing `init_db(db_path)`, `create_task(task, db_path)`, and `get_task(task_id, db_path)` database helpers.
- Produces: every task dictionary contains `is_favorite: int`, where SQLite values are `0` or `1`.

- [ ] **Step 1: Write failing migration and default tests**

Add `sqlite3` and `SCHEMA` imports, then add:

```python
import sqlite3

from backend.db import SCHEMA, create_task, get_task, init_db, list_tasks


def test_init_db_migrates_existing_tasks_to_unfavorited(tmp_path):
    db_path = tmp_path / "app.db"
    legacy_schema = SCHEMA.replace(
        "    is_favorite INTEGER NOT NULL DEFAULT 0,\n",
        "",
    )
    with sqlite3.connect(db_path) as connection:
        connection.executescript(legacy_schema)
        connection.execute(
            """
            INSERT INTO tasks (podcast_title, rss_url, episode_title, audio_url)
            VALUES (?, ?, ?, ?)
            """,
            ("旧播客", "https://example.com/feed", "旧单集", "https://example.com/audio.mp3"),
        )

    init_db(db_path)

    task = list_tasks(db_path)[0]
    assert task["episode_title"] == "旧单集"
    assert task["is_favorite"] == 0


def test_new_tasks_default_to_unfavorited(tmp_path):
    db_path = tmp_path / "app.db"
    init_db(db_path)
    task = create_task(
        {
            "podcast_title": "大内密谈",
            "rss_url": "https://example.com/feed",
            "episode_title": "新单集",
            "audio_url": "https://example.com/audio.mp3",
        },
        db_path,
    )

    assert task["is_favorite"] == 0
    assert get_task(task["id"], db_path)["is_favorite"] == 0
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
.venv/bin/pytest tests/test_db.py::test_init_db_migrates_existing_tasks_to_unfavorited tests/test_db.py::test_new_tasks_default_to_unfavorited -v
```

Expected: both tests fail because `is_favorite` is absent.

- [ ] **Step 3: Add the schema column and startup migration**

In `SCHEMA`, place the column near other task state fields:

```sql
    is_favorite INTEGER NOT NULL DEFAULT 0,
```

Add the migration entry:

```python
TASK_MIGRATIONS = {
    "is_favorite": "ALTER TABLE tasks ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0",
    # existing migrations remain unchanged
}
```

Do not add `is_favorite` to the public `TaskCreate` request model; rely on the database default so external task creation cannot create favorites.

- [ ] **Step 4: Run database tests**

Run:

```bash
.venv/bin/pytest tests/test_db.py -v
```

Expected: all database tests pass.

- [ ] **Step 5: Commit the persistence slice**

```bash
git add backend/db.py tests/test_db.py
git commit -m "feat: persist task favorites"
```

---

### Task 2: Add the Favorite API

**Files:**
- Modify: `backend/tasks.py`
- Modify: `backend/app.py`
- Test: `tests/test_tasks_api.py`

**Interfaces:**
- Consumes: `update_task(task_id: int, values: dict[str, Any], db_path) -> dict[str, Any]` from `backend.db`.
- Produces: `set_task_favorite(task_id: int, favorite: bool, db_path: str | Path) -> dict[str, Any] | None` and `PUT /api/tasks/{task_id}/favorite`.

- [ ] **Step 1: Write failing API contract tests**

Add these tests after the task creation tests:

```python
def test_favorite_endpoint_sets_clears_and_is_idempotent(tmp_path):
    client = TestClient(create_app(db_path=tmp_path / "app.db", executor=NoopExecutor()))
    task = client.post(
        "/api/tasks",
        json={
            "podcast_title": "大内密谈",
            "rss_url": "https://example.com/feed",
            "episode_title": "收藏测试",
            "audio_url": "https://example.com/audio.mp3",
        },
    ).json()["task"]

    favorite = client.put(f"/api/tasks/{task['id']}/favorite", json={"favorite": True})
    repeated = client.put(f"/api/tasks/{task['id']}/favorite", json={"favorite": True})
    unfavorite = client.put(f"/api/tasks/{task['id']}/favorite", json={"favorite": False})

    assert favorite.status_code == 200
    assert favorite.json()["result"] == "updated"
    assert favorite.json()["task"]["is_favorite"] == 1
    assert repeated.status_code == 200
    assert repeated.json()["task"]["is_favorite"] == 1
    assert unfavorite.status_code == 200
    assert unfavorite.json()["task"]["is_favorite"] == 0
    assert client.get(f"/api/tasks/{task['id']}").json()["is_favorite"] == 0


def test_favorite_endpoint_returns_404_for_missing_task(tmp_path):
    client = TestClient(create_app(db_path=tmp_path / "app.db", executor=NoopExecutor()))

    response = client.put("/api/tasks/999/favorite", json={"favorite": True})

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_favorite_endpoint_rejects_non_boolean_values(tmp_path):
    client = TestClient(create_app(db_path=tmp_path / "app.db", executor=NoopExecutor()))

    response = client.put("/api/tasks/1/favorite", json={"favorite": "yes"})

    assert response.status_code == 422


def test_task_list_and_detail_include_favorite_state(tmp_path):
    client = TestClient(create_app(db_path=tmp_path / "app.db", executor=NoopExecutor()))
    task = client.post(
        "/api/tasks",
        json={
            "podcast_title": "大内密谈",
            "rss_url": "https://example.com/feed",
            "episode_title": "列表收藏状态",
            "audio_url": "https://example.com/audio.mp3",
        },
    ).json()["task"]
    client.put(f"/api/tasks/{task['id']}/favorite", json={"favorite": True})

    assert client.get("/api/tasks").json()["items"][0]["is_favorite"] == 1
    assert client.get(f"/api/tasks/{task['id']}").json()["is_favorite"] == 1


def test_archive_and_restart_preserve_favorite_state(tmp_path):
    client = TestClient(create_app(db_path=tmp_path / "app.db", executor=NoopExecutor()))
    task = client.post(
        "/api/tasks",
        json={
            "podcast_title": "大内密谈",
            "rss_url": "https://example.com/feed",
            "episode_title": "收藏后归档重启",
            "audio_url": "https://example.com/audio.mp3",
        },
    ).json()["task"]
    client.put(f"/api/tasks/{task['id']}/favorite", json={"favorite": True})

    archived = client.delete(f"/api/tasks/{task['id']}").json()["task"]
    restarted = client.post(f"/api/tasks/{task['id']}/restart").json()["task"]

    assert archived["is_favorite"] == 1
    assert restarted["id"] != task["id"]
    assert restarted["is_favorite"] == 1
```

- [ ] **Step 2: Run the API tests and verify they fail**

Run:

```bash
.venv/bin/pytest tests/test_tasks_api.py::test_favorite_endpoint_sets_clears_and_is_idempotent tests/test_tasks_api.py::test_favorite_endpoint_returns_404_for_missing_task tests/test_tasks_api.py::test_favorite_endpoint_rejects_non_boolean_values tests/test_tasks_api.py::test_task_list_and_detail_include_favorite_state tests/test_tasks_api.py::test_archive_and_restart_preserve_favorite_state -v
```

Expected: favorite requests return HTTP 404 because the route does not exist.

- [ ] **Step 3: Add the domain update helper**

In `backend/tasks.py`, add:

```python
def set_task_favorite(
    task_id: int,
    favorite: bool,
    db_path: str | Path,
) -> dict[str, Any] | None:
    if get_task(task_id, db_path) is None:
        return None
    return update_task(task_id, {"is_favorite": int(favorite)}, db_path)
```

- [ ] **Step 4: Add the request model and route**

In `backend/app.py`, import `StrictBool` from Pydantic and `set_task_favorite` from `backend.tasks`. Add `FavoriteUpdateRequest` at module scope, and add the route inside `create_app` beside the other task mutation routes:

```python
class FavoriteUpdateRequest(BaseModel):
    favorite: StrictBool


@app.put("/api/tasks/{task_id}/favorite")
def task_favorite(task_id: int, payload: FavoriteUpdateRequest) -> dict[str, Any]:
    task = set_task_favorite(task_id, payload.favorite, app.state.db_path)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": task, "result": "updated"}
```

Place the route before `DELETE /api/tasks/{task_id}` so task mutation routes remain grouped.

- [ ] **Step 5: Preserve favorite state when restart replaces the task row**

In `restart_task`, capture the state before deleting the old row and restore it on the newly created row:

```python
is_favorite = bool(task.get("is_favorite"))
# existing cleanup, delete, shownotes, and create_task calls remain unchanged
task = create_task(payload, db_path)
if is_favorite:
    task = update_task(task["id"], {"is_favorite": 1}, db_path)
```

Archiving already updates the existing row, so it requires no production change; the API test protects that behavior.

- [ ] **Step 6: Run focused and full API tests**

Run:

```bash
.venv/bin/pytest tests/test_tasks_api.py -v
```

Expected: all task API tests pass.

- [ ] **Step 7: Commit the API slice**

```bash
git add backend/tasks.py backend/app.py tests/test_tasks_api.py
git commit -m "feat: expose task favorite API"
```

---

### Task 3: Add the Favorites View

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/app.js`
- Modify: `frontend/styles.css`
- Test: `tests/test_frontend_copy.py`

**Interfaces:**
- Consumes: task objects with `is_favorite: 0|1` from `GET /api/tasks`.
- Produces: `state.taskFilters.favoritesOnly: boolean`, `favoriteTasks()`, a localized favorites toggle, and favorites-specific empty state.

- [ ] **Step 1: Write the failing favorites-view test**

Add:

```python
def test_frontend_exposes_favorites_view_that_bypasses_other_filters():
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    script = Path("frontend/app.js").read_text(encoding="utf-8")
    styles = Path("frontend/styles.css").read_text(encoding="utf-8")

    assert 'id="favorites-filter"' in html
    assert 'data-action="toggle-favorites"' in html
    assert 'data-i18n="favorites"' in html
    assert "favoritesOnly: false" in script
    assert "function favoriteTasks()" in script
    assert "return state.tasks.filter((task) => Boolean(task.is_favorite));" in script
    assert "if (state.taskFilters.favoritesOnly) return favoriteTasks();" in script
    assert 't("noFavoriteTasks")' in script
    assert "state.taskFilters.favoritesOnly = !state.taskFilters.favoritesOnly" in script
    assert ".favorites-filter.is-active" in styles
    assert "收藏" in script
    assert "Favorites" in script
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
.venv/bin/pytest tests/test_frontend_copy.py::test_frontend_exposes_favorites_view_that_bypasses_other_filters -v
```

Expected: fail because the favorites filter and state do not exist.

- [ ] **Step 3: Add the quick-filter markup**

Add this button as the first child of `.time-filter`, before the date options:

```html
<button type="button" class="time-filter__option favorites-filter" id="favorites-filter" data-action="toggle-favorites" aria-pressed="false">
  <svg class="favorite-icon" viewBox="0 0 16 16" aria-hidden="true">
    <path d="M8 1.5l2.02 4.09 4.51.66-3.27 3.18.77 4.49L8 11.8l-4.03 2.12.77-4.49L1.47 6.25l4.51-.66L8 1.5z"></path>
  </svg>
  <span data-i18n="favorites">Favorites</span>
</button>
```

Update the script cache key in `frontend/index.html` to `/static/app.js?v=20260829-task-favorites` so running browsers load the new behavior immediately after deployment.

- [ ] **Step 4: Add state, localization, derivation, and toggle wiring**

Add `favoritesOnly: false` inside `state.taskFilters`. Add these keys to both language dictionaries:

```javascript
favorites: "收藏",
noFavoriteTasks: "还没有收藏的单集",
```

```javascript
favorites: "Favorites",
noFavoriteTasks: "No favorite episodes yet.",
```

Cache `#favorites-filter`, then implement:

```javascript
function favoriteTasks() {
  return state.tasks.filter((task) => Boolean(task.is_favorite));
}

function filteredTasks() {
  if (state.taskFilters.favoritesOnly) return favoriteTasks();
  return tasksMatchingBaseFilters().filter((task) => {
    return !state.taskFilters.podcastTitle || task.podcast_title === state.taskFilters.podcastTitle;
  });
}

function renderTasks() {
  const emptyMessage = state.taskFilters.favoritesOnly ? t("noFavoriteTasks") : t("noFilteredTasks");
  renderList(taskResults, filteredTasks(), renderTask, emptyMessage);
}
```

The toggle handler must preserve every other filter value:

```javascript
favoritesFilter.addEventListener("click", () => {
  state.taskFilters.favoritesOnly = !state.taskFilters.favoritesOnly;
  favoritesFilter.classList.toggle("is-active", state.taskFilters.favoritesOnly);
  favoritesFilter.setAttribute("aria-pressed", String(state.taskFilters.favoritesOnly));
  renderTasks();
});
```

- [ ] **Step 5: Style the favorites toggle with existing tokens**

Reuse `.time-filter__option` sizing and active treatment. Add only icon-specific rules:

```css
.favorites-filter {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.favorite-icon {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.5;
  stroke-linejoin: round;
}

.favorites-filter.is-active {
  background: var(--teal);
  color: var(--paper-strong);
  border-color: rgba(22, 72, 75, 0.18);
}

.favorites-filter.is-active .favorite-icon {
  fill: currentColor;
}
```

- [ ] **Step 6: Run frontend tests**

Run:

```bash
.venv/bin/pytest tests/test_frontend_copy.py -v
```

Expected: all frontend contract tests pass.

- [ ] **Step 7: Commit the favorites-view slice**

```bash
git add frontend/index.html frontend/app.js frontend/styles.css tests/test_frontend_copy.py
git commit -m "feat: add favorites task view"
```

---

### Task 4: Add the Task Card Star Action

**Files:**
- Modify: `frontend/app.js`
- Modify: `frontend/styles.css`
- Test: `tests/test_frontend_copy.py`

**Interfaces:**
- Consumes: `PUT /api/tasks/{task_id}/favorite` returning `{task, result}` and existing `fetchJson`, `state.pendingActionTaskIds`, `showToast`, and `renderTasks` helpers.
- Produces: `toggleTaskFavorite(task)` and an accessible star button on every rendered task card.

- [ ] **Step 1: Write the failing task-star test**

Add:

```python
def test_frontend_renders_and_updates_github_style_task_star():
    script = Path("frontend/app.js").read_text(encoding="utf-8")
    styles = Path("frontend/styles.css").read_text(encoding="utf-8")

    assert 'data-action="favorite"' in script
    assert 'class="favorite-icon" viewBox="0 0 16 16"' in script
    assert 'task.is_favorite ? t("unfavorite") : t("favorite")' in script
    assert "async function toggleTaskFavorite(task)" in script
    assert 'fetchJson(`/api/tasks/${task.id}/favorite`, {' in script
    assert 'method: "PUT"' in script
    assert "body: JSON.stringify({ favorite: !Boolean(task.is_favorite) })" in script
    assert "state.tasks = state.tasks.map" in script
    assert ".icon-button--favorite.is-active" in styles
    assert "fill: var(--teal);" in styles
    assert "取消收藏" in script
    assert "Unfavorite" in script
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
.venv/bin/pytest tests/test_frontend_copy.py::test_frontend_renders_and_updates_github_style_task_star -v
```

Expected: fail because task cards have no favorite action.

- [ ] **Step 3: Add localized card labels**

Add to both dictionaries:

```javascript
favorite: "收藏",
unfavorite: "取消收藏",
favoriteUpdated: "收藏已更新",
```

```javascript
favorite: "Favorite",
unfavorite: "Unfavorite",
favoriteUpdated: "Favorite updated.",
```

- [ ] **Step 4: Implement the request handler without optimistic mutation**

Add:

```javascript
async function toggleTaskFavorite(task) {
  if (state.pendingActionTaskIds.has(task.id)) return;
  state.pendingActionTaskIds.add(task.id);
  renderTasks();
  try {
    const result = await fetchJson(`/api/tasks/${task.id}/favorite`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ favorite: !Boolean(task.is_favorite) }),
    });
    state.tasks = state.tasks.map((item) => item.id === task.id ? result.task : item);
    showToast(t("favoriteUpdated"));
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    state.pendingActionTaskIds.delete(task.id);
    renderTasks();
  }
}
```

Do not mutate `task.is_favorite` before the response; failure must leave the visible state unchanged.

- [ ] **Step 5: Render and wire the star button**

In `renderTask`, derive the label and active class:

```javascript
const favoriteLabel = task.is_favorite ? t("unfavorite") : t("favorite");
const favoriteClass = task.is_favorite ? " is-active" : "";
```

Insert before restart/archive in `.ledger-status-row`:

```html
<button type="button" class="icon-button icon-button--favorite${favoriteClass}" data-action="favorite" title="${escapeAttribute(favoriteLabel)}" aria-label="${escapeAttribute(favoriteLabel)}" aria-pressed="${Boolean(task.is_favorite)}" ${isPending ? "disabled" : ""}>
  <svg class="favorite-icon" viewBox="0 0 16 16" aria-hidden="true">
    <path d="M8 1.5l2.02 4.09 4.51.66-3.27 3.18.77 4.49L8 11.8l-4.03 2.12.77-4.49L1.47 6.25l4.51-.66L8 1.5z"></path>
  </svg>
</button>
```

Wire it after assigning `article.innerHTML`:

```javascript
article.querySelector('[data-action="favorite"]')?.addEventListener("click", () => toggleTaskFavorite(task));
```

- [ ] **Step 6: Style inactive and active states**

```css
.icon-button--favorite {
  color: var(--muted);
}

.icon-button--favorite:hover:not(:disabled) {
  color: var(--teal);
  border-color: rgba(35, 95, 98, 0.34);
}

.icon-button--favorite.is-active {
  color: var(--teal);
  background: var(--teal-wash);
  border-color: rgba(35, 95, 98, 0.24);
}

.icon-button--favorite.is-active .favorite-icon {
  fill: var(--teal);
  stroke: var(--teal);
}
```

- [ ] **Step 7: Run focused and full frontend tests**

Run:

```bash
.venv/bin/pytest tests/test_frontend_copy.py -v
```

Expected: all frontend tests pass.

- [ ] **Step 8: Commit the card-action slice**

```bash
git add frontend/app.js frontend/styles.css tests/test_frontend_copy.py
git commit -m "feat: add favorite action to task cards"
```

---

### Task 5: Regression and Browser Verification

**Files:**
- Modify only files already listed if verification reveals a defect.

**Interfaces:**
- Consumes: completed persistence, API, favorites view, and card action slices.
- Produces: verified behavior in the real application at desktop and mobile widths.

- [ ] **Step 1: Run the full automated suite**

Run:

```bash
.venv/bin/pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run syntax and diff checks**

Run:

```bash
.venv/bin/python -m compileall -q backend tests
git diff --check
```

Expected: both commands exit successfully with no whitespace errors.

- [ ] **Step 3: Restart the existing service safely**

First verify no task is actively downloading, transcribing, or summarizing through `GET /api/tasks`. If all tasks are idle, restart using the recorded launcher:

```bash
scripts/start_server.sh
```

Expected: `GET /api/health` returns `{"ok": true}`.

- [ ] **Step 4: Verify the browser workflow**

At desktop and mobile widths, verify all of these in the running app:

1. Every task card shows a stable 28px star button without shifting the status row.
2. Unfavorited stars are muted outlines; favorited stars use the existing teal fill in light and dark themes.
3. Clicking a star persists after page refresh.
4. The favorites button shows only favorite tasks, including an archived favorite older than 30 days.
5. Status, date, and podcast selections remain selected while favorites is active and take effect again after favorites is closed.
6. Unfavoriting an item inside favorites removes it from the visible list.
7. Chinese and English tooltips, labels, and empty states are correct.
8. No controls or text overlap at desktop and mobile widths.

- [ ] **Step 5: Commit verification fixes only if needed**

If browser verification required corrections, run the focused tests for each corrected file, then commit only those corrections:

```bash
git add backend/db.py backend/tasks.py backend/app.py frontend/index.html frontend/app.js frontend/styles.css tests/test_db.py tests/test_tasks_api.py tests/test_frontend_copy.py
git commit -m "fix: polish task favorites workflow"
```

If no corrections were needed, do not create an empty commit.
