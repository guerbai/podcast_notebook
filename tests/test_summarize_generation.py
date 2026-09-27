import json
from pathlib import Path
from subprocess import CompletedProcess

from backend.db import create_task, init_db, list_task_events, update_task
from backend.summarizer import (
    MessagesSummaryClient,
    SummaryAlreadyExistsError,
    SummaryConfig,
    SummaryProviderError,
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


class FailingSummaryClient:
    def generate(self, prompt: str, language: str) -> str:
        raise SummaryProviderError(
            "Summarize provider request failed: Messages request curl exit 28: operation timed out"
        )


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


def test_generate_task_summarize_records_provider_failure_reason(tmp_path):
    db_path, task = _create_completed_task(tmp_path)

    try:
        generate_task_summarize(
            task["id"],
            "zh-CN",
            db_path,
            client=FailingSummaryClient(),
            summaries_dir=tmp_path / "summaries",
        )
    except SummaryProviderError:
        pass
    else:
        raise AssertionError("expected provider failure")

    error_events = [
        event
        for event in list_task_events(task["id"], db_path)
        if event["level"] == "error"
    ]
    assert error_events[-1]["message"] == (
        "Summarize failed for zh-CN: SummaryProviderError: "
        "Summarize provider request failed: Messages request curl exit 28: operation timed out"
    )


def test_generate_task_summarize_converts_chinese_summary_to_simplified(tmp_path):
    db_path, task = _create_completed_task(tmp_path)
    client = FakeSummaryClient("# AI短劇\n\n## 核心判斷\n\n對於創作者而言，技術正在改寫規則。")

    updated = generate_task_summarize(
        task["id"],
        "zh-CN",
        db_path,
        client=client,
        summaries_dir=tmp_path / "summaries",
    )

    markdown = Path(updated["summarize"]).read_text(encoding="utf-8")
    assert "# AI短剧" in markdown
    assert "## 核心判断" in markdown
    assert "对于创作者而言，技术正在改写规则。" in markdown
    assert "短劇" not in markdown
    assert "判斷" not in markdown


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


def test_generate_task_summarize_normalizes_numbered_bold_lead_labels(tmp_path):
    db_path, task = _create_completed_task(tmp_path)
    client = FakeSummaryClient(
        "# 标题\n\n"
        "## 主题线索\n\n"
        "1. **冠军悬念的解开**  \n\n"
        "阿森纳释放压力。\n\n"
        "2. **瓜迪奥拉留下的空白**\n\n"
        "曼城进入新阶段。\n"
    )

    updated = generate_task_summarize(
        task["id"],
        "zh-CN",
        db_path,
        client=client,
        summaries_dir=tmp_path / "summaries",
    )

    markdown = Path(updated["summarize"]).read_text(encoding="utf-8")
    assert "1. **冠军悬念的解开**" not in markdown
    assert "2. **瓜迪奥拉留下的空白**" not in markdown
    assert "**冠军悬念的解开**" in markdown
    assert "**瓜迪奥拉留下的空白**" in markdown


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


def test_summary_prompt_includes_sports_music_technology_templates():
    prompt = build_summary_prompt(
        {
            "podcast_title": "The Rest Is Football",
            "episode_title": "ARSENAL: PREMIER LEAGUE CHAMPIONS",
        },
        "完整转写内容",
        "单集介绍内容",
        "zh-CN",
    )

    assert "Sports / football commentary" in prompt
    assert "Music / artist / album / industry" in prompt
    assert "Technology / AI / product / developer practice" in prompt
    assert "Do not use numbered-list items as subsection lead labels" in prompt
    assert "Make the H1 faithful to the episode title" in prompt


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


def test_messages_request_contract(monkeypatch):
    captured = {}
    _mock_curl_requests(
        monkeypatch,
        captured,
        {"content": [{"type": "text", "text": "# 总结\n\n内容"}]},
    )
    client = MessagesSummaryClient(
        SummaryConfig(api_key="test-key", base_url="http://MacBook-Work.local:15723")
    )

    assert client.generate("prompt", "zh-CN") == "# 总结\n\n内容"
    assert captured["health_command"][-1] == "http://MacBook-Work.local:15723/health"
    assert captured["messages_command"][-1] == "http://MacBook-Work.local:15723/v1/messages"
    assert "-4" in captured["health_command"]
    assert "-4" in captured["messages_command"]
    assert "test-key" not in " ".join(captured["messages_command"])
    assert "x-api-key: test-key" in captured["headers_input"]
    assert "anthropic-version: 2023-06-01" in captured["headers_input"]
    assert captured["json"]["model"] == "kimi-k3"
    assert captured["json"]["max_tokens"] == 32768
    assert captured["json"]["output_config"] == {"effort": "high"}
    assert captured["json"]["stream"] is True
    assert captured["json"]["messages"] == [{"role": "user", "content": "prompt"}]
    system_prompt = captured["json"]["system"]
    assert "detailed" in system_prompt
    assert "never include operational notes" in system_prompt
    assert "concise" not in system_prompt


def test_messages_client_joins_text_content_blocks(monkeypatch):
    _mock_curl_requests(
        monkeypatch,
        {},
        {
            "content": [
                {"type": "text", "text": "第一段"},
                {"type": "tool_use", "id": "tool-1", "name": "ignored"},
                {"type": "text", "text": " 第二段 "},
            ]
        },
    )
    client = MessagesSummaryClient(
        SummaryConfig(api_key="test-key", base_url="http://MacBook-Work.local:15723")
    )

    assert client.generate("prompt", "zh-CN") == "第一段\n\n第二段"


def test_messages_client_collects_text_from_streaming_sse(monkeypatch):
    def fake_run(command, **kwargs):
        if command[-1].endswith("/health"):
            return CompletedProcess(command, 0, stdout='{"ok":true}\n200', stderr="")

        stream = "\n".join(
            [
                "event: message_start",
                'data: {"type":"message_start","message":{"content":[]}}',
                "",
                "event: content_block_delta",
                'data: {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"分析"}}',
                "",
                "event: content_block_delta",
                'data: {"type":"content_block_delta","index":1,"delta":{"type":"text_delta","text":"第一段"}}',
                "",
                "event: content_block_delta",
                'data: {"type":"content_block_delta","index":1,"delta":{"type":"text_delta","text":"第二段"}}',
                "",
                "event: message_stop",
                'data: {"type":"message_stop"}',
                "",
                "200",
            ]
        )
        return CompletedProcess(command, 0, stdout=stream, stderr="")

    monkeypatch.setattr("backend.summarizer.subprocess.run", fake_run)
    client = MessagesSummaryClient(
        SummaryConfig(api_key="test-key", base_url="http://MacBook-Work.local:15723")
    )

    assert client.generate("prompt", "zh-CN") == "第一段第二段"


def test_messages_client_reports_provider_status_without_request_headers(monkeypatch):
    _mock_curl_requests(
        monkeypatch,
        {},
        {"error": {"message": "upstream unavailable"}},
        status_code=502,
    )
    client = MessagesSummaryClient(
        SummaryConfig(api_key="secret-key", base_url="http://MacBook-Work.local:15723")
    )

    try:
        client.generate("prompt", "zh-CN")
    except SummaryProviderError as error:
        assert str(error) == (
            'Summarize provider request failed: HTTP 502: {"error": {"message": "upstream unavailable"}}'
        )
        assert "secret-key" not in str(error)
    else:
        raise AssertionError("expected provider error")


def _mock_curl_requests(monkeypatch, captured, response_payload, status_code=200):
    def fake_run(command, **kwargs):
        if command[-1].endswith("/health"):
            captured["health_command"] = command
            return CompletedProcess(command, 0, stdout='{"ok":true}\n200', stderr="")

        captured["messages_command"] = command
        captured["headers_input"] = kwargs["input"]
        body_argument = command[command.index("--data-binary") + 1]
        captured["json"] = json.loads(Path(body_argument.removeprefix("@")).read_text(encoding="utf-8"))
        response_body = json.dumps(response_payload, ensure_ascii=False)
        return CompletedProcess(command, 0, stdout=f"{response_body}\n{status_code}", stderr="")

    monkeypatch.setattr("backend.summarizer.subprocess.run", fake_run)


def test_summary_config_uses_environment_key_and_yaml_connection_settings(tmp_path, monkeypatch):
    from backend.summarizer import summary_config_from_env

    config_path = tmp_path / "podcast_notebook.yaml"
    config_path.write_text(
        """
llm:
  api_key: yaml-key
  base_url: http://proxy.local:15723
  timeout_seconds: 9
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("PODCAST_NOTEBOOK_LLM_API_KEY", "env-key")
    monkeypatch.setenv("PODCAST_NOTEBOOK_LLM_BASE_URL", "https://env.example.com/v1")
    monkeypatch.setenv("PODCAST_NOTEBOOK_CONFIG", str(config_path))

    config = summary_config_from_env()

    assert config.api_key == "env-key"
    assert config.base_url == "http://proxy.local:15723"
    assert config.timeout_seconds == 9


def test_summary_config_default_allows_slow_max_effort_generation(tmp_path, monkeypatch):
    from backend.summarizer import summary_config_from_env

    monkeypatch.setenv("PODCAST_NOTEBOOK_LLM_API_KEY", "env-key")
    monkeypatch.setenv("PODCAST_NOTEBOOK_CONFIG", str(tmp_path / "missing.yaml"))

    config = summary_config_from_env()

    assert config.timeout_seconds == 600
