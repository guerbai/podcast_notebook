# Podcast Task Favorites Design

## Goal

Let the user favorite any podcast episode task from its card and open one dedicated view containing every favorite. Favorites persist across browser refreshes and service restarts.

## Scope

- Favorite and unfavorite an existing task.
- Show favorite state on every task returned by the existing task APIs.
- Add a one-click favorites view.
- Include archived tasks and tasks from every date in the favorites view.
- Keep download, transcription, summary, archive, and restart behavior unchanged.

Tags, notes, folders, favorite ordering, and bulk actions are out of scope.

## Data Model

Add `is_favorite INTEGER NOT NULL DEFAULT 0` to `tasks`.

The existing startup migration adds the column to older databases. Existing tasks become unfavorited. Task creation accepts no favorite input; new tasks always start unfavorited.

## Backend API

Add:

```http
PUT /api/tasks/{task_id}/favorite
Content-Type: application/json

{"favorite": true}
```

The endpoint updates only `is_favorite` and returns:

```json
{"task": {"id": 123, "is_favorite": 1}, "result": "updated"}
```

Sending `false` removes the favorite. A missing task returns HTTP 404. The endpoint is idempotent: setting the current value again still succeeds.

## Frontend Interaction

Each task card gets a GitHub-style five-point star icon in its top-right action row.

- Unfavorited: outlined star using the current muted foreground/border color.
- Favorited: filled star using the project's existing teal accent color, with a matching outline.
- The button uses the existing icon-button dimensions so the task layout does not shift.
- Tooltip and `aria-label` are localized as `Favorite` / `Unfavorite` and `收藏` / `取消收藏`.
- The button is disabled while its request is pending.
- On success, the returned task replaces the local task item and the current list rerenders.
- On failure, the displayed state remains unchanged and the existing toast shows the error.

Add a `Favorites` quick-filter button beside the existing task filters. It uses the same star icon and active styling as the current time-filter controls.

When favorites view is active:

- Show every task with `is_favorite=1`.
- Include archived tasks and all dates.
- Ignore status, date, and podcast filters without erasing their saved selections.
- Clicking Favorites again exits the view and restores the previous filters.
- Show the existing empty-state treatment with favorites-specific copy when no favorites exist.

## Data Flow

1. User clicks a card star.
2. Frontend sends the desired boolean value to the favorite endpoint.
3. Backend validates the task, persists `is_favorite`, and returns the updated task.
4. Frontend replaces that task in `state.tasks` and rerenders.
5. Favorites view derives its list from `state.tasks`; no separate fetch or duplicated favorite cache is needed.

## Error Handling

- Missing task: HTTP 404 with `Task not found`.
- Database/update failure: normal FastAPI 500 behavior; frontend displays the response error.
- A failed request never flips the local star state.
- Archiving or restarting a task preserves its favorite value because those operations update the existing record or archive it in place.

## Testing

- Database migration adds `is_favorite` with default `0` and preserves existing rows.
- Favorite API sets and clears the field and is idempotent.
- Favorite API returns 404 for a missing task.
- Task list/detail responses include `is_favorite`.
- Frontend renders the star action, localized labels, active visual state, and request handler.
- Favorites view bypasses status, date, and podcast filters and includes archived favorites.
- Favorites empty state uses dedicated copy.
- Full backend and frontend regression suites pass.
