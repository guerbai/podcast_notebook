# Task Lifecycle And UI Polish Design

**Date:** 2026-04-15

## Goal

Refine the podcast notebook app so task creation, monitoring, cancellation, restart, and detail viewing feel deliberate and stable instead of brittle. The main outcomes are:

- one task per `podcast_title + episode_title`
- running tasks can be deleted or restarted
- task progress shows separate download and transcription percentages
- task creation and task actions have in-page feedback
- dialogs and detail panels use custom UI instead of browser primitives
- episode cards and task cards align cleanly and keep their expanded state during polling

## Confirmed Requirements

- Creating the same `播客 + 单集` again should not create duplicates.
- When a duplicate is requested, the app should focus the existing task and visually highlight it.
- Running tasks must be deletable.
- Running tasks must be restartable with one click.
- The UI should not use `alert()` or `confirm()`.
- Download and transcription progress should be shown as two separate percentages.
- Clicking `创建转写任务` should give immediate feedback.
- The episode results and task list need alignment fixes.
- `查看详情` should stay open instead of collapsing itself during polling.

## Recommended Approach

Keep the current `FastAPI + SQLite + ThreadPoolExecutor` architecture, but make the task lifecycle explicit enough to support cancellation, restart, and stable UI rendering.

This is a light refactor rather than a platform rewrite:

- preserve one `tasks` row as the durable identity for a single episode
- treat the worker execution as the current run of that task
- store enough state in SQLite for cancellation and split progress
- let the frontend keep stable client-side UI state keyed by task id

This keeps the implementation local and understandable while removing the main UX traps.

## Data Model Changes

The `tasks` table should remain the source of truth for one unique episode task. Add or formalize these fields:

- `podcast_title`
- `episode_title`
- `status`
- `progress_stage`
- `progress_percent`
- `download_percent`
- `transcription_percent`
- `cancel_requested`
- `highlight_token` or equivalent transient response data from create/restart actions

Enforce uniqueness at the database level with a unique index on:

- `podcast_title`
- `episode_title`

`episode_guid` and `rss_url` are still useful metadata, but the user explicitly wants the dedupe rule to be podcast name plus episode name.

## Task Lifecycle

### Status

Use these statuses:

- `queued`
- `running`
- `cancelling`
- `completed`
- `failed`

### Stage

Use these stages:

- `queued`
- `downloading_audio`
- `transcribing`
- `finalizing`
- `completed`
- `failed`
- `cancelled`

### Cancellation Model

The worker cannot be force-killed safely, so cancellation should be cooperative:

1. Delete or restart marks `cancel_requested = 1`.
2. The worker checks that flag between download callbacks, before transcription starts, during transcription progress callbacks, and before writing output.
3. When cancellation is observed, the worker stops early, cleans partial outputs when appropriate, and writes a terminal cancelled/failure state.

This gives us reliable, testable behavior without introducing a heavy external queue.

## Delete And Restart Semantics

### Delete

Delete should work for every status:

- `queued`: remove record and files immediately
- `running` or `cancelling`: request cancellation, then delete after the run acknowledges it
- terminal tasks: remove record, files, and events immediately

From the user’s perspective, delete is one action. Internally the backend may respond with an accepted transitional state while the worker is winding down.

### Restart

Restart should never create a second durable task for the same episode.

- if the task is terminal, reset progress fields and queue a fresh run on the same task id
- if the task is running, request cancellation first, then automatically requeue the same task once the current run exits

This preserves history continuity and keeps task links stable in the UI.

## Create Task Semantics

On `创建转写任务`:

- if no task exists, create the task, queue it, and return `created`
- if a task already exists, do not create a new row; return `existing`

The API response should include:

- `task`
- `result` with values like `created` or `existing`
- a short message for the frontend toast

When `existing` is returned, the frontend should:

- scroll to the matching task card
- open or preserve that card
- apply a brief highlight treatment

This removes duplicate noise while keeping the user oriented.

## Progress Model

Keep the overall `progress_percent` if useful, but stop making it the only visible number.

Store and expose:

- `download_percent`
- `transcription_percent`

Rules:

- before download starts: both `0`
- during download: update only `download_percent`
- after download completes: `download_percent = 100`
- during transcription: update `transcription_percent`
- after transcription completes: both `100`

The UI should show two labeled progress tracks:

- `下载`
- `转写`

This is easier to read than one synthetic percentage and explains why a task can still be in `转写中` near the end.

## Frontend Interaction Design

### Feedback

Replace browser primitives with app UI:

- toast for success, warning, and error feedback
- modal for destructive confirmation like delete
- loading state on `创建转写任务`
- loading state on task action buttons when a request is in flight

### Stable Detail Panels

Do not rely on native `<details>` for the task body.

Instead:

- track expanded task ids in frontend state
- render detail sections from that state
- preserve expanded state across polling refreshes

This prevents the current “open, then polling rerenders and closes it again” behavior.

### Episode Card Layout

Episode search results should use a two-column grid:

- left: episode title and publish date
- right: fixed-width action button

This keeps the button aligned regardless of title wrapping.

### Task Card Layout

Task cards should use a consistent editorial grid:

- left rail for index or status tag
- center body for title, metadata, progress, and optional detail area
- right action rail for `查看详情`, `重新开始`, `删除`

This will fix the current drifting alignment in the ledger section.

## Error Handling

The frontend should display backend `detail` messages instead of only an HTTP status code.

Examples:

- `任务正在取消中，请稍候`
- `已定位到现有任务`
- `删除请求已接收，任务正在停止`

The backend should return structured JSON for action outcomes rather than relying on generic HTTP-only meaning.

## Testing Strategy

Use TDD and cover both behavior and regressions:

### Backend

- unique create behavior returns existing task instead of creating duplicates
- running delete sets cancellation and eventually removes files/records
- running restart cancels current run and requeues same task id
- progress updates expose both download and transcription percentages

### Frontend

- create button enters loading state and shows toast
- duplicate create scrolls to existing task and applies highlight class
- delete uses custom modal, not browser confirm
- expanded task details remain open after task list refresh
- action buttons and episode cards render expected structure/classes for alignment

## Non-Goals

- introducing Redis, Celery, or an external queue
- persisting multiple historical runs per task
- adding summary generation
- redesigning the app away from the current editorial visual direction

## Recommendation

Implement this as a coordinated backend/frontend refactor in one pass:

1. expand the task model for cancellation and split progress
2. add duplicate-aware create and same-task restart semantics
3. replace brittle frontend primitives with stable stateful UI
4. finish with regression tests around polling and action workflows

That sequence is the smallest change that solves all eight issues together instead of producing another patchwork round.
