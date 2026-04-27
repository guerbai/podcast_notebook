# Podcast Notebook

Local web app for searching podcasts, choosing a specific episode, downloading the audio, and generating a full transcript `.txt` file with tracked task progress.

## What it does

- search podcasts by podcast name
- search one podcast's episodes by keyword
- create a transcription task for one selected episode
- track download and transcription progress in the browser
- persist task history in SQLite
- attach optional Markdown summaries to tasks
- keep shownotes and manually generated summarize notes as local files linked from SQLite

## Runtime

This project keeps its runtime local to the repo:

- Python virtual environment: `.venv/`
- database: `data/db/`
- downloaded audio: `data/downloads/`
- transcripts: `data/transcripts/`
- cleaned episode shownotes: `data/shownotes/`
- summaries and summarize files: `data/summaries/`
- downloaded models: `data/models/`
- optional local ffmpeg binary: `tools/ffmpeg`

## Bootstrap

Requires Python 3.10+.

```bash
bash scripts/bootstrap_runtime.sh
```

If your default `python3` is older, point bootstrap at a newer interpreter explicitly:

```bash
PYTHON_BIN=/opt/homebrew/bin/python3.12 bash scripts/bootstrap_runtime.sh
```

## Run tests

```bash
.venv/bin/pytest -v
```

## Run the app

```bash
.venv/bin/uvicorn backend.app:create_app --factory --reload
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Notes

- `faster-whisper` is used for local transcription.
- The first model download may take a while.
- Long podcast transcription on CPU can also take a while, so the browser task list is intended to make progress visible.
- The same `播客名 + 单集名` only keeps one task record. Creating it again will focus the existing task instead of making a duplicate.
- Running tasks can be deleted or restarted. The app will request a cooperative stop first, then finish deleting or rerunning.
- The task card shows separate `下载进度` and `转写进度`, rather than one mixed percentage.
- If a task already has a generated Markdown summary, the card will expose a `查看总结` button and open it in a large modal.
- If a task has shownotes or summarize file paths, the card exposes `查看 Shownotes` and `查看 Summarize` buttons.
