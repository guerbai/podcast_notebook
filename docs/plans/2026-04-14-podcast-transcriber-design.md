# Podcast Transcriber Design

**Date:** 2026-04-14

## Goal

Build a local web app that:

- lets the user search for a podcast by name
- lets the user search for a specific episode within that podcast by keyword
- lets the user select one episode and create a transcription task
- downloads the episode audio and transcribes the full content to a `.txt` file
- persists task history and progress in SQLite
- shows active and completed tasks in a web UI

## Confirmed Requirements

- Input should start from `podcast name` and `episode keyword`, not only a raw RSS URL.
- The user must select a concrete episode before execution starts.
- Completed transcripts must be written to a concrete `.txt` output file.
- Long-running download and transcription work must expose progress in the UI.
- Task history must persist across restarts in SQLite.

## Recommended Architecture

### Backend

Use `FastAPI` as a local backend service because it is a simple Python web framework that can:

- serve JSON APIs for search and task execution
- host a lightweight frontend page
- manage background jobs for download and transcription

### Frontend

Use a lightweight browser UI served by the backend. The first version should provide:

- a `Podcast Name` input
- an `Episode Keyword` input
- a search action that shows matching podcasts
- a select action for one podcast
- an episode list for that podcast filtered by the keyword
- a create-task action for one selected episode
- a task list with status, phase, progress, output path, and errors

### Storage

Use `SQLite` for local persistence.

Recommended tables:

1. `podcasts_cache`
   - stores discovered podcast metadata and RSS URLs for reuse
2. `episodes_cache`
   - stores parsed RSS episode metadata for a podcast
3. `tasks`
   - stores execution history and result paths
4. `task_events`
   - stores timestamped progress and log lines for UI display

The cache tables can be kept simple and refreshed on demand.

## Task Lifecycle

Each task should move through explicit phases:

- `queued`
- `searching_episode`
- `downloading_audio`
- `transcribing`
- `writing_text`
- `completed`
- `failed`

The UI should show both:

- current phase
- progress within the phase when available

## Discovery Flow

1. User enters a podcast name.
2. Backend searches a podcast directory source and returns candidate podcasts with RSS URLs.
3. User picks one podcast.
4. User enters an episode keyword.
5. Backend fetches and parses the selected podcast's RSS feed.
6. Backend returns matching episodes.
7. User picks one episode and starts a task.

## Transcription Flow

1. Resolve the selected episode's audio URL.
2. Download the audio to the local workspace.
3. Normalize or decode audio if needed.
4. Run transcription with a local speech-to-text engine.
5. Write the final plain-text transcript to `outputs/transcripts/<episode>.txt`.
6. Persist result metadata in SQLite.

## Speech-to-Text Choice

First version recommendation:

- use `faster-whisper` for transcription
- prefer a local runtime inside the project
- keep the code structured so another provider can be added later

Reasons:

- local and open-source
- suitable for long-form podcast audio
- good engineering ergonomics for chunked progress reporting

## Runtime Layout

Recommended project layout:

- `backend/`
- `frontend/`
- `data/`
- `data/db/`
- `data/downloads/`
- `data/transcripts/`
- `data/models/`
- `tools/`
- `.venv/`

`tools/` can contain project-local binaries such as `ffmpeg` if required.

## Progress Model

Download progress should track:

- bytes downloaded
- total bytes when known
- current speed if easy to capture

Transcription progress should track:

- processed audio duration
- total duration when known
- current segment count or chunk count

When exact percentages are unavailable, the UI should still show the current phase and recent event logs.

## Summary Integration

The user also wants the ideal end state to show a summary in the browser after transcription completes.

Important constraint:

- the web app cannot directly call this current Codex desktop conversation session

Recommended design:

- treat summarization as a separate backend stage after transcription
- expose a provider interface in the backend
- first provider can call a model API using a configured API key
- store the generated summary alongside the transcript and show it in the task detail page

This keeps the app architecture correct even if summarization is implemented in a later iteration.

## Non-Goals For First Version

- direct integration with the live Codex desktop chat session
- speaker diarization
- batch execution across multiple episodes
- user accounts or multi-user support
- full-text semantic search over all transcripts

## Open Decision

One decision remains for implementation:

- whether the first version should include the summary API integration now
- or only prepare the extension point and UI placeholder for a later step

My recommendation is to build the transcript pipeline first, keep summary as a pluggable next step, and avoid blocking the first delivery on model-provider setup.
