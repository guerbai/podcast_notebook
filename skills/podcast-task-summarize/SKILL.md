---
name: podcast-task-summarize
description: Use when generating, regenerating, revising, or analyzing a Podcast Notebook task summary from its cleaned shownotes and ASR transcript, then writing the Markdown summary file path back into the SQLite tasks.summarize column.
---

# Podcast Task Summarize

## Purpose

Generate or update a reusable Markdown summary for an existing Podcast Notebook task.

This is the single podcast summary workflow for this project. It covers:

- locating the exact DB task row
- reading cleaned shownotes and the ASR transcript
- analyzing the full transcript despite ASR noise
- choosing an appropriate summary structure
- writing the summary file under `data/summaries/`
- updating `tasks.summarize`
- verifying the API can read the summary

## Storage Contract

- SQLite database: `data/db/podcast_notebook.db`
- Table: `tasks`
- Source columns:
  - `shownotes`: absolute path to cleaned shownotes text
  - `output_txt_path`: absolute path to ASR transcript text
  - `audio_file_path`: audio path for duration checks when available
- Destination column:
  - `summarize`: absolute path to generated Markdown summary
- Destination directory:
  - `data/summaries/`
- Recommended filename:
  - `<sanitized-episode-title>-summarize.md`
  - Match existing project filename style.

## Workflow

### 1. Locate The Exact Task

Use project DB helpers where possible:

```bash
.venv/bin/python - <<'PY'
from backend.config import DB_PATH
from backend.db import connect_db

keyword = "Vol.254"
with connect_db(DB_PATH) as con:
    rows = con.execute("""
        SELECT id, podcast_title, episode_title, status, shownotes,
               summarize, output_txt_path, audio_file_path
        FROM tasks
        WHERE episode_title LIKE ?
        ORDER BY id DESC
    """, (f"%{keyword}%",)).fetchall()

for row in rows:
    print(dict(row))
PY
```

Before writing, verify:

- Use the exact `id`; never update by title alone if duplicates exist.
- `shownotes` exists when available.
- `output_txt_path` exists.
- `summarize` may be empty or may point to an existing file.
- Overwrite an existing summary only when the user asks to regenerate or revise it.

### 2. Read Sources

Principle: full transcript first, shownotes second, inference last.

- Treat `output_txt_path` as the primary source.
- Read enough of the full transcript to cover beginning, middle, and end; never summarize only from the opening segment.
- For very long transcripts, scan by chunks across the whole file, then re-read dense or ambiguous sections.
- Use `shownotes` to correct episode title, chapter timeline, people, brands, publications, products, places, and English names.
- Do not let shownotes replace the transcript; they are correction and framing metadata.

### 3. Handle ASR Noise

- Expect wrong Chinese homophones, broken punctuation, wrong speaker turns, and malformed English names.
- Prefer repeated transcript mentions plus shownotes spelling when resolving terms.
- Normalize obvious ASR errors silently when confidence is high.
- Mark uncertainty only when a term or claim cannot be resolved from context and shownotes.
- Separate explicitly stated claims from reasonable synthesis.

### 4. Extract Before Drafting

Create an internal extraction inventory before writing:

- episode thesis
- topic sequence or outline
- major claims and viewpoints
- concrete examples, companies, people, products, tools, places, or cases
- conclusions and caveats
- unclear terms likely caused by ASR errors

For every important example, extract an internal example card:

- What exactly happened: the person, company, product, place, or scene.
- Key mechanism: why the example works or matters, such as monopoly, information gap, cost structure, channel, regulation, user psychology, technology, or timing.
- Claim supported: which episode argument this example proves or complicates.
- Memorable details: concrete numbers, counterintuitive facts, turning points, execution details, or constraints.
- Boundary or risk: whether the example depends on gray areas, fraud, regulation, luck, non-repeatable context, or ethical tradeoffs.

Do not write examples as labels only. A reader should understand the essence of a key example without needing the original audio.

For focused user requests, such as “整理这几期的整体脉络” or “提取 Codex 项目”, first create a candidate inventory from the whole transcript or all relevant summaries, then synthesize.

### 5. Choose Summary Template

Classify the episode from `podcast_title`, `episode_title`, shownotes, and transcript. Use the primary type to choose structure. If an episode spans multiple types, use the primary template and borrow only the needed secondary section. If uncertain, use the default template.

- **Commercial case / method**: use `核心判断 / 机制脉络 / 关键案例 / 可复用框架 / 风险边界`.
  - Focus on how money is made, what control point or arbitrage exists, why others miss it, and what is or is not repeatable.
  - Examples must explain the business mechanism, not just name the company or case.
- **Finance / investing**: use `核心判断 / 市场变量 / 资产或行业观点 / 操作启发 / 风险提示`.
  - Focus on variables such as rates, valuation, earnings, policy, liquidity, fund flows, time horizon, and risk preference.
  - Examples must explain which variable changed the investment judgment.
- **Tech interview / AI practice**: use `核心判断 / 方法框架 / 落地流程或案例 / 对企业或个人的启发 / 局限`.
  - Focus on the problem context, workflow, implementation pattern, measurable result, and limitations.
  - Examples must explain how the technology entered the workflow and what problem it solved.
- **Culture / history / food**: use `主题线索 / 历史与地方脉络 / 关键材料或人物 / 文化含义 / 结论`.
  - Focus on historical context, locality, materials, people, memory, and how meanings changed over time.
  - Examples must explain why a dish, person, place, or object matters; avoid turning the summary into a name list.
- **Explainer / beginner education**: use `概念定义 / 类比解释 / 关键机制 / 适用人群 / 常见误区`.
  - Focus on making the concept understandable and actionable.
  - Examples must clarify the concept, not distract from it.
- **Default**: `核心判断 / 大纲 / 主要例子 / 结论`

Do not over-fit the template. Preserve the episode's actual logic.

### 6. Draft Requirements

The summary file must be Markdown.

Length rule:

- Keep the summary under 3000 Chinese characters.
- Do not force the summary toward 3000 characters. Use only as much length as the episode's information density needs.
- A simple or narrow episode can be 800-1200 Chinese characters.
- A typical substantial episode should usually be 1200-2200 Chinese characters.
- A dense episode with many important examples, concepts, or arguments can be 2200-3000 Chinese characters.
- Episode duration is only a signal. Prefer information density over duration: number of distinct arguments, case complexity, required background, and example richness.

Content requirements:

- Preserve outline, main viewpoints, and major examples.
- Ground claims in the transcript.
- Use shownotes for correction and framing.
- Avoid ad copy unless it materially affects episode content.
- Avoid generic takeaways that erase the episode's specific cases.
- Prioritize example quality over example count. Expand the most important examples; omit minor examples if they only add noise.
- Do not repeat the same example list across sections.

Writing structure rules:

- Each section must have a distinct job.
- `核心判断` should state the episode's main claim and significance. Do not list all examples here.
- `机制脉络` or `大纲` should explain the argument flow. Do not expand case details here.
- `关键案例` or `主要例子` is where examples should be explained in depth using the example card.
- `结论`, `启发`, or `风险边界` should synthesize and judge. Do not re-summarize the example list.
- If an example is fully explained in `关键案例`, other sections may refer to it only briefly when needed for reasoning.
- Avoid repeated phrasing under different headings. If two sections say the same thing, merge or delete one.
- Prefer dense, specific prose over broad summaries. The reader should finish with a clear sense of what happened, why it mattered, and what can or cannot be generalized.

### 7. Write The Summary File

Create or update the Markdown file under `data/summaries/`.

Use `apply_patch` for manual file creation or edits.

### 8. Update The Database

Update only the exact task row:

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

### 9. Verify

Verify DB and API:

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
- where the summary file was written
- that `tasks.summarize` was updated
- whether `/api/tasks/{id}/summarize` returned `200`

Keep the response concise.
