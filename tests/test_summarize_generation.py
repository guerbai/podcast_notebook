from pathlib import Path

from backend.db import create_task, init_db, list_task_events, update_task
from backend.summarizer import (
    OpenAICompatibleSummaryClient,
    SummaryAlreadyExistsError,
    SummaryConfig,
    build_summary_prompt,
    generate_task_summarize,
)
from backend.transcription import sanitize_filename


class FakeSummaryClient:
    def __init__(self, markdown: str = "# 总结\n\n- 来自模型的要点\n") -> None:
        self.markdown = markdown
        self.prompt = ""
        self.language = ""

    def generate(self, prompt: str, language: str) -> str:
        self.prompt = prompt
        self.language = language
        return self.markdown


def _create_completed_task(tmp_path: Path):
    db_path = tmp_path / "app.db"
    init_db(db_path)
    task = create_task(
        {
            "podcast_title": "大内密谈",
            "rss_url": "http://example.com/feed.xml",
            "episode_title": "vol.1385 从小龙虾跑路到 Codex",
            "audio_url": "http://example.com/audio.mp3",
        },
        db_path,
    )
    transcript_path = tmp_path / "transcripts" / "episode.txt"
    shownotes_path = tmp_path / "shownotes" / "episode.txt"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    shownotes_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text("完整转写内容，讨论 Codex 和工作流。", encoding="utf-8")
    shownotes_path.write_text("Shownotes 里的本期介绍。", encoding="utf-8")
    task = update_task(
        task["id"],
        {
            "status": "completed",
            "progress_stage": "completed",
            "output_txt_path": str(transcript_path),
            "shownotes": str(shownotes_path),
        },
        db_path,
    )
    return db_path, task


def test_generate_task_summarize_writes_chinese_file_and_updates_task(tmp_path):
    db_path, task = _create_completed_task(tmp_path)
    client = FakeSummaryClient()

    updated = generate_task_summarize(
        task["id"],
        "zh-CN",
        db_path,
        client=client,
        summaries_dir=tmp_path / "summaries",
    )

    assert updated["summarize"].endswith("-summarize.md")
    assert Path(updated["summarize"]).read_text(encoding="utf-8").startswith("# 总结")
    assert updated["summarize_en"] == ""
    assert client.language == "zh-CN"
    assert "完整转写内容" in client.prompt
    assert "Shownotes 里的本期介绍" in client.prompt
    assert "podcast-task-summarize" in client.prompt
    assert "Keep the summary under 3000 Chinese characters." in client.prompt
    assert "Choose Summary Template" in client.prompt
    events = [event["message"] for event in list_task_events(task["id"], db_path)]
    assert "Generating summarize for zh-CN" in events
    assert "Summarize generated for zh-CN" in events


def test_generate_task_summarize_writes_english_field(tmp_path):
    db_path, task = _create_completed_task(tmp_path)
    client = FakeSummaryClient("# Summary\n\n- Model point\n")

    updated = generate_task_summarize(
        task["id"],
        "en",
        db_path,
        client=client,
        summaries_dir=tmp_path / "summaries",
    )

    assert updated["summarize"] == ""
    assert updated["summarize_en"].endswith("-summarize.en.md")
    assert Path(updated["summarize_en"]).read_text(encoding="utf-8").startswith("# Summary")
    assert client.language == "en"


def test_generate_task_summarize_refuses_existing_summary(tmp_path):
    db_path, task = _create_completed_task(tmp_path)
    existing_path = tmp_path / "summaries" / "existing.md"
    existing_path.parent.mkdir(parents=True, exist_ok=True)
    existing_path.write_text("# 已有总结\n", encoding="utf-8")
    update_task(task["id"], {"summarize": str(existing_path)}, db_path)

    try:
        generate_task_summarize(
            task["id"],
            "zh-CN",
            db_path,
            client=FakeSummaryClient(),
            summaries_dir=tmp_path / "summaries",
        )
    except SummaryAlreadyExistsError as exc:
        assert str(exc) == "Summarize already exists"
    else:
        raise AssertionError("expected existing summary to be refused")


def test_generate_task_summarize_does_not_overwrite_stale_summary_file(tmp_path):
    db_path, task = _create_completed_task(tmp_path)
    stale_path = tmp_path / "summaries" / f"{sanitize_filename(task['episode_title'])}-summarize.md"
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    stale_path.write_text("# 旧文件\n", encoding="utf-8")

    updated = generate_task_summarize(
        task["id"],
        "zh-CN",
        db_path,
        client=FakeSummaryClient("# 新总结\n"),
        summaries_dir=tmp_path / "summaries",
    )

    assert stale_path.read_text(encoding="utf-8") == "# 旧文件\n"
    assert Path(updated["summarize"]) != stale_path
    assert Path(updated["summarize"]).read_text(encoding="utf-8") == "# 新总结\n"


def test_generate_task_summarize_normalizes_nested_markdown_headings(tmp_path):
    db_path, task = _create_completed_task(tmp_path)
    client = FakeSummaryClient(
        "# 标题\n\n"
        "## 核心判断\n\n"
        "正文\n\n"
        "### 地缘政治的传导时滞\n\n"
        "小节正文\n\n"
        "#### 更深层标题\n\n"
        "更多正文\n"
    )

    updated = generate_task_summarize(
        task["id"],
        "zh-CN",
        db_path,
        client=client,
        summaries_dir=tmp_path / "summaries",
    )

    markdown = Path(updated["summarize"]).read_text(encoding="utf-8")
    assert "### 地缘政治的传导时滞" not in markdown
    assert "#### 更深层标题" not in markdown
    assert "**地缘政治的传导时滞**" in markdown
    assert "**更深层标题**" in markdown


def test_summary_prompt_excludes_agent_operational_steps():
    prompt = build_summary_prompt(
        {
            "podcast_title": "第一财经",
            "episode_title": "提前布局能源股，巴菲特又赢麻了？|巴菲特时间01",
        },
        "完整转写内容",
        "单集介绍内容",
        "zh-CN",
    )

    assert "description: Use when generating" in prompt
    assert "Read Sources" in prompt
    assert "Choose Summary Template" in prompt
    assert "Draft Requirements" in prompt
    assert "Completion Response" not in prompt
    assert "Tell the user:" not in prompt
    assert "Update The Database" not in prompt
    assert "/api/tasks/{id}/summarize" not in prompt
    assert "Return only the requested summary Markdown" in prompt
    assert "Do not mention task ids, file paths, database updates, API verification" in prompt
    assert "Use only two heading levels" in prompt
    assert "Do not use ###" in prompt


def test_english_summary_prompt_requires_english_section_headings():
    prompt = build_summary_prompt(
        {
            "podcast_title": "第一财经",
            "episode_title": "提前布局能源股，巴菲特又赢麻了？|巴菲特时间01",
        },
        "完整转写内容",
        "单集介绍内容",
        "en",
    )

    assert "Output language: English" in prompt
    assert "Translate section headings into natural English" in prompt
    assert "Do not use Chinese section headings" in prompt
    assert "Core Thesis / Market Variables / Asset or Industry Views / Actionable Takeaways / Conclusion and Implications" in prompt


def test_openai_client_system_prompt_asks_for_detailed_summary_without_operational_text(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "# 总结\n\n内容"}}]}

    def fake_post(*args, **kwargs):
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("backend.summarizer.httpx.post", fake_post)
    client = OpenAICompatibleSummaryClient(SummaryConfig(api_key="test-key"))

    assert client.generate("prompt", "zh-CN") == "# 总结\n\n内容"
    system_prompt = captured["json"]["messages"][0]["content"]
    assert "detailed" in system_prompt
    assert "never include operational notes" in system_prompt
    assert "concise" not in system_prompt


def test_summary_config_prefers_yaml_config_over_env(tmp_path, monkeypatch):
    from backend.summarizer import summary_config_from_env

    config_path = tmp_path / "podcast_notebook.yaml"
    config_path.write_text(
        """
llm:
  api_key: yaml-key
  base_url: https://yaml.example.com/v1
  model: yaml-model
  timeout_seconds: 9
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("PODCAST_NOTEBOOK_LLM_API_KEY", "env-key")
    monkeypatch.setenv("PODCAST_NOTEBOOK_LLM_BASE_URL", "https://env.example.com/v1")
    monkeypatch.setenv("PODCAST_NOTEBOOK_CONFIG", str(config_path))

    config = summary_config_from_env()

    assert config.api_key == "yaml-key"
    assert config.base_url == "https://yaml.example.com/v1"
    assert config.model == "yaml-model"
    assert config.timeout_seconds == 9
