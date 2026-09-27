from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol

from opencc import OpenCC

from backend.config import ROOT_DIR, SUMMARIES_DIR, load_project_config
from backend.db import add_task_event, get_task, update_task
from backend.transcription import sanitize_filename


class SummaryError(RuntimeError):
    """Base error for user-facing summarize generation failures."""


class SummaryNotConfiguredError(SummaryError):
    pass


class SummaryTaskNotFoundError(SummaryError):
    pass


class SummaryTranscriptMissingError(SummaryError):
    pass


class SummaryAlreadyExistsError(SummaryError):
    pass


class SummaryProviderError(SummaryError):
    pass


class SummaryClient(Protocol):
    def generate(self, prompt: str, language: str) -> str:
        ...


@dataclass(slots=True)
class SummaryConfig:
    api_key: str
    base_url: str = "http://MacBook-Work.local:15723"
    timeout_seconds: float = 600.0


MESSAGES_MODEL = "kimi-k3"
MESSAGES_MAX_TOKENS = 32768
MESSAGES_EFFORT = "high"
ANTHROPIC_VERSION = "2023-06-01"
SUMMARY_SYSTEM_PROMPT = (
    "You write detailed, accurate, source-grounded podcast episode summaries in Markdown. "
    "Use only one H1 title and H2 section headings; never use H3 or deeper headings. "
    "Return only the final summary Markdown; never include operational notes, file paths, "
    "database updates, API verification, or chatty completion text."
)


class MessagesSummaryClient:
    def __init__(self, config: SummaryConfig) -> None:
        self.config = config

    def generate(self, prompt: str, language: str) -> str:
        try:
            payload = _request_messages(
                self.config,
                {
                    "model": MESSAGES_MODEL,
                    "max_tokens": MESSAGES_MAX_TOKENS,
                    "output_config": {"effort": MESSAGES_EFFORT},
                    "system": SUMMARY_SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": True,
                },
            )
            blocks = payload["content"]
            content = "\n\n".join(
                block["text"].strip()
                for block in blocks
                if block.get("type") == "text"
                and isinstance(block.get("text"), str)
                and block["text"].strip()
            )
        except SummaryProviderError:
            raise
        except Exception as exc:
            raise SummaryProviderError(_provider_error_message(exc)) from exc

        if not isinstance(content, str) or not content.strip():
            raise SummaryProviderError("Summarize provider returned empty content")
        return content.strip()


def _provider_error_message(error: Exception) -> str:
    return f"Summarize provider request failed: {type(error).__name__}: {error}"


def _request_messages(config: SummaryConfig, payload: dict) -> dict:
    _verify_proxy_health(config.base_url)
    messages_url = f"{config.base_url.rstrip('/')}/v1/messages"
    header_input = "\n".join(
        [
            f"x-api-key: {config.api_key}",
            f"anthropic-version: {ANTHROPIC_VERSION}",
            "content-type: application/json",
            "",
        ]
    )
    with NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json") as request_file:
        json.dump(payload, request_file, ensure_ascii=False)
        request_file.flush()
        result = subprocess.run(
            [
                "curl",
                "-sS",
                "-4",
                "--noproxy",
                "*",
                "--max-time",
                f"{config.timeout_seconds:g}",
                "--header",
                "@-",
                "--data-binary",
                f"@{request_file.name}",
                "--write-out",
                "\n%{http_code}",
                messages_url,
            ],
            input=header_input,
            capture_output=True,
            text=True,
            timeout=config.timeout_seconds + 5,
            check=False,
        )
    response_body, status_code = _parse_curl_response(result, "Messages request")
    if not 200 <= status_code < 300:
        response_text = response_body.strip() or "<empty response>"
        raise SummaryProviderError(
            f"Summarize provider request failed: HTTP {status_code}: {response_text[:500]}"
        )
    return _parse_messages_response(response_body)


def _parse_messages_response(response_body: str) -> dict:
    if response_body.lstrip().startswith("{"):
        return json.loads(response_body)

    text_parts = []
    message_stopped = False
    for line in response_body.splitlines():
        if not line.startswith("data:"):
            continue
        event = json.loads(line.removeprefix("data:").strip())
        event_type = event.get("type")
        if event_type == "content_block_start":
            block = event.get("content_block", {})
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                text_parts.append(block["text"])
        elif event_type == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta" and isinstance(delta.get("text"), str):
                text_parts.append(delta["text"])
        elif event_type == "error":
            error = event.get("error", {})
            message = error.get("message") or "unknown streaming error"
            raise SummaryProviderError(f"Summarize provider stream failed: {message}")
        elif event_type == "message_stop":
            message_stopped = True

    if not message_stopped:
        raise SummaryProviderError("Summarize provider stream ended before message_stop")
    return {"content": [{"type": "text", "text": "".join(text_parts)}]}


def _verify_proxy_health(base_url: str) -> None:
    result = subprocess.run(
        [
            "curl",
            "-sS",
            "-4",
            "--noproxy",
            "*",
            "--max-time",
            "3",
            "--write-out",
            "\n%{http_code}",
            f"{base_url.rstrip('/')}/health",
        ],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    health_body, status_code = _parse_curl_response(result, "Health check")
    health_payload = json.loads(health_body)
    if status_code != 200 or health_payload.get("ok") is not True:
        raise SummaryProviderError("Summarize proxy health check failed")


def _parse_curl_response(
    result: subprocess.CompletedProcess[str], operation: str
) -> tuple[str, int]:
    if result.returncode != 0:
        error_text = result.stderr.strip() or "<empty stderr>"
        raise SummaryProviderError(
            f"Summarize provider request failed: {operation} curl exit {result.returncode}: {error_text[:500]}"
        )
    parts = result.stdout.rsplit("\n", 1)
    if len(parts) != 2 or not parts[1].isdigit():
        raise SummaryProviderError(
            f"Summarize provider request failed: {operation} returned malformed output"
        )
    return parts[0], int(parts[1])


_TRADITIONAL_TO_SIMPLIFIED = OpenCC("t2s")


def summary_config_from_env() -> SummaryConfig:
    project_config = load_project_config()
    api_key = os.environ.get("PODCAST_NOTEBOOK_LLM_API_KEY", "").strip()
    if not api_key:
        raise SummaryNotConfiguredError("Summarize API key is not configured")
    return SummaryConfig(
        api_key=api_key,
        base_url=project_config.llm.base_url,
        timeout_seconds=project_config.llm.timeout_seconds,
    )


def generate_task_summarize(
    task_id: int,
    lang: str,
    db_path: str | Path,
    *,
    client: SummaryClient | None = None,
    summaries_dir: str | Path | None = None,
) -> dict:
    language = "en" if lang == "en" else "zh-CN"
    field = "summarize_en" if language == "en" else "summarize"
    task = get_task(task_id, db_path)
    if task is None:
        raise SummaryTaskNotFoundError("Task not found")
    if task.get(field):
        raise SummaryAlreadyExistsError("Summarize already exists")

    transcript_path = Path(task.get("output_txt_path") or "")
    if not transcript_path.is_file():
        raise SummaryTranscriptMissingError("Transcript file is missing")

    summary_client = client or MessagesSummaryClient(summary_config_from_env())
    transcript = transcript_path.read_text(encoding="utf-8")
    shownotes = _read_optional_file(task.get("shownotes", ""))
    prompt = build_summary_prompt(task, transcript, shownotes, language)

    add_task_event(task_id, f"Generating summarize for {language}", db_path=db_path)
    try:
        markdown = summary_client.generate(prompt, language)
        markdown = _normalize_summary_language(markdown, language)
        output_path = _write_summary_file(task, markdown, language, Path(summaries_dir or SUMMARIES_DIR))
    except Exception as exc:
        failure_message = f"{type(exc).__name__}: {exc}"
        add_task_event(
            task_id,
            f"Summarize failed for {language}: {failure_message}"[:1000],
            level="error",
            db_path=db_path,
        )
        raise

    updated = update_task(task_id, {field: str(output_path)}, db_path)
    add_task_event(task_id, f"Summarize generated for {language}", db_path=db_path)
    return updated


def _normalize_summary_language(markdown: str, language: str) -> str:
    if language != "zh-CN":
        return markdown
    return _TRADITIONAL_TO_SIMPLIFIED.convert(markdown)


def build_summary_prompt(task: dict, transcript: str, shownotes: str, language: str) -> str:
    output_language = "English" if language == "en" else "Simplified Chinese"
    skill_instructions = _read_summary_skill()
    language_specific_rules = _language_specific_summary_rules(language)
    return "\n\n".join(
        [
            "Generate a reusable podcast episode summary from the transcript and shownotes.",
            "Follow these podcast-task-summarize skill instructions for analysis and writing quality.",
            "Do not perform the agent workflow steps yourself; the backend will write files and update the database.",
            "Output contract:",
            "- Return only the requested summary Markdown.",
            "- Start with a single H1 title for the episode, then use H2 sections chosen from the episode type.",
            "- Make the H1 faithful to the episode title; translate it only when the output language requires it, and keep proper nouns recognizable.",
            "- Use only two heading levels: `#` for the episode title and `##` for top-level sections.",
            "- Do not use ### or deeper Markdown headings. If a section needs subdivisions, use bold lead labels inside normal paragraphs or bullets.",
            "- Do not use numbered-list items as subsection lead labels, such as `1. **Topic**`; write `**Topic**` as a standalone bold lead label instead.",
            "- Do not mention task ids, file paths, database updates, API verification, or completion status.",
            "- Match the density of existing agent-generated summaries: preserve the episode's main logic, examples, mechanisms, risks, limitations, and implications.",
            "- For a substantial Chinese episode, prefer roughly 1200-2200 Chinese characters; use 2200-3000 for dense episodes.",
            language_specific_rules,
            "Podcast task summarize skill writing instructions:",
            skill_instructions,
            f"Output language: {output_language}",
            f"Podcast: {task.get('podcast_title', '')}",
            f"Episode: {task.get('episode_title', '')}",
            "Shownotes:",
            shownotes or "(empty)",
            "Transcript:",
            transcript,
        ]
    )


def _language_specific_summary_rules(language: str) -> str:
    if language == "en":
        return (
            "English output rules:\n"
            "- Translate section headings into natural English.\n"
            "- Do not use Chinese section headings such as `核心判断`, `市场变量`, `资产或行业观点`, `操作启发`, or `结论与启发`.\n"
            "- For finance or investing episodes, prefer headings like: Core Thesis / Market Variables / Asset or Industry Views / Actionable Takeaways / Conclusion and Implications."
        )
    return (
        "Chinese output rules:\n"
        "- Use Simplified Chinese for the title, section headings, and body.\n"
        "- Prefer concise Chinese section headings chosen from the episode type."
    )


def _read_summary_skill() -> str:
    skill_path = ROOT_DIR / "skills" / "podcast-task-summarize" / "SKILL.md"
    return _extract_summary_skill_writing_instructions(skill_path.read_text(encoding="utf-8"))


def _extract_summary_skill_writing_instructions(markdown: str) -> str:
    description = _extract_frontmatter_description(markdown)
    sections = [
        _extract_markdown_section(markdown, "### 2. Read Sources"),
        _extract_markdown_section(markdown, "### 3. Handle ASR Noise"),
        _extract_markdown_section(markdown, "### 4. Extract Before Drafting"),
        _extract_markdown_section(markdown, "### 5. Choose Summary Template"),
        _extract_markdown_section(markdown, "### 6. Draft Requirements"),
    ]
    return "\n\n".join(
        [
            "Skill: podcast-task-summarize",
            f"description: {description}",
            *[section for section in sections if section],
        ]
    ).strip()


def _extract_frontmatter_description(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("description:"):
            return line.removeprefix("description:").strip()
    return ""


def _extract_markdown_section(markdown: str, heading: str) -> str:
    lines = markdown.splitlines()
    try:
        start = lines.index(heading)
    except ValueError:
        return ""

    heading_level = len(heading) - len(heading.lstrip("#"))
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if not line.startswith("#"):
            continue
        level = len(line) - len(line.lstrip("#"))
        if level <= heading_level:
            end = index
            break
    return "\n".join(lines[start:end]).strip()


def _read_optional_file(value: str) -> str:
    if not value:
        return ""
    try:
        path = Path(value)
    except (OSError, ValueError):
        return value
    if not path.is_file():
        return value
    return path.read_text(encoding="utf-8")


def _write_summary_file(task: dict, markdown: str, language: str, summaries_dir: Path) -> Path:
    summaries_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"{sanitize_filename(task.get('episode_title', 'summary'))}-summarize"
    if language == "en":
        base_name = f"{base_name}.en"
    path = _next_available_path(summaries_dir, base_name)
    path.write_text(_normalize_summary_markdown(markdown).strip() + "\n", encoding="utf-8")
    return path


def _normalize_summary_markdown(markdown: str) -> str:
    normalized_lines = []
    in_fence = False
    for line in markdown.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            normalized_lines.append(line)
            continue
        if not in_fence:
            match = re.match(r"^(#{3,})\s+(.+?)\s*$", line)
            if match:
                normalized_lines.append(f"**{match.group(2).strip()}**")
                continue
            lead_label_match = re.match(r"^\s*\d+\.\s+\*\*(.+?)\*\*\s*$", line)
            if lead_label_match:
                normalized_lines.append(f"**{lead_label_match.group(1).strip()}**")
                continue
        normalized_lines.append(line)
    return "\n".join(normalized_lines)


def _next_available_path(directory: Path, base_name: str) -> Path:
    path = directory / f"{base_name}.md"
    counter = 2
    while path.exists():
        path = directory / f"{base_name}-{counter}.md"
        counter += 1
    return path
