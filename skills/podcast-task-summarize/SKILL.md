---
name: podcast-task-summarize
description: Use when generating or updating the summarize file for an existing Podcast Notebook task, especially when the user asks to summarize a podcast episode from its shownotes and transcript, then write the summarize file path back into the SQLite tasks.summarize column.
---

# Podcast Task Summarize

## Purpose

Generate a reusable episode summary for an existing task in this project, store it as a Markdown file, and update the task row so the UI can show it through the `查看 Summarize` button.

Use this when the user asks to create, regenerate, or revise `summarize` for a task already present in the Podcast Notebook database.

## Project Storage Contract

- SQLite database: `data/db/podcast_notebook.db`
- Table: `tasks`
- Task lookup: usually by `id`, exact `episode_title`, or a title keyword such as `Vol.254`
- Source columns:
  - `shownotes`: absolute path to the cleaned shownotes text file
  - `output_txt_path`: absolute path to the ASR transcript text file
- Destination column:
  - `summarize`: absolute path to the generated Markdown summarize file
- Destination directory:
  - `data/summaries/`
- Recommended filename:
  - `<sanitized-episode-title>-summarize.md`
  - Match the project's existing filename style, for example `Vol254-大牌的创意总监为什么成了高危职业-summarize.md`.

## Workflow

### 1. Locate the task

Use the project DB helpers when possible:

```bash
.venv/bin/python - <<'PY'
from backend.config import DB_PATH
from backend.db import connect_db

keyword = "Vol.254"
with connect_db(DB_PATH) as con:
    rows = con.execute("""
        SELECT id, podcast_title, episode_title, shownotes, summarize, output_txt_path, status
        FROM tasks
        WHERE episode_title LIKE ?
        ORDER BY id DESC
    """, (f"%{keyword}%",)).fetchall()
for row in rows:
    print(dict(row))
PY
```

Before writing, verify:

- `status` is usually `completed`
- `shownotes` points to an existing file
- `output_txt_path` points to an existing transcript file
- `summarize` may be empty or may point to an existing file to overwrite only if the user asked to regenerate/revise it
- episode duration, when available from the audio file or metadata, so the summary length can follow the duration rule

### 2. Read sources

Use the transcript as the primary source and shownotes as the correction source.

- Read the full transcript, not just the start.
- Use shownotes to correct ASR mistakes in episode title, section timeline, people, brands, publications, and product names.
- Expect ASR mistakes in Chinese and English names. Prefer spellings from shownotes when available.
- If the transcript is long, scan by chunks across the whole file and search for repeated keywords to verify coverage.
- If `audio_file_path` exists, estimate duration with `ffprobe`/`ffmpeg` when available. If duration cannot be read, estimate from transcript length and state the assumption internally before drafting.

### 3. Extract before drafting

Create an internal extraction inventory before writing the final summary:

- episode thesis
- main outline or topic sequence
- major claims or viewpoints
- concrete examples, companies, people, products, or cases
- conclusions and caveats
- uncertain terms likely caused by ASR errors

Do not include this inventory in the final file unless the user asks.

### 4. Draft requirements

The summarize file should be Markdown. Unless the user asks otherwise, choose length by episode duration:

- If duration is 1.5 hours or less: keep the summary under 1000 Chinese characters.
- If duration is longer than 1.5 hours: write more than 1500 and less than 2000 Chinese characters.
- If duration is unknown but the transcript is clearly long-form, use judgment from transcript size and topic density; prefer the longer range when the episode likely exceeds 1.5 hours.

Default structure:

```markdown
# <episode title>

## 核心判断

<one concise paragraph>

## 大纲

1. <main thread>
2. <main thread>
3. <main thread>

## 主要例子

- **<example>**：<why it matters>
- **<example>**：<why it matters>

## 结论

<one concise paragraph>
```

Content requirements:

- Keep the outline, main viewpoints, and main examples.
- Ground claims in the transcript; use shownotes for correction and framing.
- Normalize obvious ASR errors silently when confidence is high.
- Mark uncertainty only if a term or claim cannot be resolved from context and shownotes.
- Avoid ad copy unless it materially affects the episode content.
- Do not over-summarize into generic business lessons; preserve the episode's specific logic.

### 5. Write the file

Create or update the Markdown file under `data/summaries/`.

Use `apply_patch` for manual file creation or edits.

### 6. Update the database

After the file is written, update the exact task row's `summarize` column to the absolute file path:

```bash
.venv/bin/python - <<'PY'
from backend.config import DB_PATH
from backend.db import update_task

task_id = 21
summarize_path = "/Users/hubao/my/podcast_notebook/data/summaries/Vol254-大牌的创意总监为什么成了高危职业-summarize.md"
updated = update_task(task_id, {"summarize": summarize_path}, DB_PATH)
print(updated["id"])
print(updated["episode_title"])
print(updated["summarize"])
PY
```

Never update by title alone if multiple matching rows exist. Resolve the exact `id` first.

### 7. Verify

Verify both DB and API:

```bash
.venv/bin/python - <<'PY'
from fastapi.testclient import TestClient
from backend.app import create_app

task_id = 21
client = TestClient(create_app())
resp = client.get(f"/api/tasks/{task_id}/summarize")
print(resp.status_code)
data = resp.json()
print(data["title"])
print(data["path"])
print(data["content"][:120].replace("\n", " "))
PY
```

Expected:

- status code `200`
- `path` equals the `tasks.summarize` file path
- content starts with the generated Markdown title

## Completion Response

Tell the user:

- which task id was updated
- the summarize file path
- that `tasks.summarize` was updated
- whether `/api/tasks/{id}/summarize` returned `200`

Keep the response concise and mention that the list page should show `查看 Summarize` after refresh.
