import json
import subprocess
from pathlib import Path

import pytest

import backend.codex_summaries as summaries
from backend.db import create_task, get_task, init_db, list_task_events, update_task
from backend.summarizer import SummaryNotConfiguredError, SummaryProviderError, SummaryTranscriptMissingError


@pytest.fixture
def completed_task(tmp_path):
    db_path = tmp_path / "app.db"
    init_db(db_path)
    transcript = tmp_path / "transcript.txt"
    transcript.write_text("嘉宾认为增长来自复购，但只讨论了两家门店。", encoding="utf-8")
    task = create_task({
        "podcast_title": "测试播客", "episode_title": "复购与增长",
        "rss_url": "https://example.com/feed", "audio_url": "https://example.com/a.mp3",
        "status": "completed", "output_txt_path": str(transcript),
    }, db_path)
    return db_path, task


class FakeClient:
    skill_path = Path("/test/humanizer-zh/SKILL.md")

    def __init__(self, result=None, before_return=None):
        self.result = result if result is not None else {"brief": "增长靠复购，但样本仅两家门店。", "detail": "# 复购与增长\n\n嘉宾认为增长来自复购，样本仅两家门店。"}
        self.before_return = before_return
        self.calls = []

    def generate(self, prompt, kind):
        self.calls.append((prompt, kind))
        if self.before_return:
            self.before_return()
        return {kind: self.result[kind]}


@pytest.mark.parametrize("kind,other", [("brief", "detail"), ("detail", "brief")])
def test_generates_only_requested_kind_from_transcript_and_is_idempotent(completed_task, tmp_path, kind, other):
    db_path, task = completed_task
    client = FakeClient()
    updated = summaries.generate_task_summary(task["id"], kind, db_path, client=client, summaries_dir=tmp_path / "out")
    assert len(client.calls) == 1
    prompt, requested_kind = client.calls[0]
    assert requested_kind == kind
    assert "$humanizer-zh" in prompt and str(client.skill_path) in prompt
    assert "嘉宾认为增长来自复购，但只讨论了两家门店。" in prompt
    assert ("长版 detail：" in prompt) == (kind == "detail")
    assert ("短版 brief：" in prompt) == (kind == "brief")
    assert "不添加个人经历" in prompt
    assert Path(updated[summaries.SUMMARY_FIELDS[kind]]).read_text(encoding="utf-8").strip() == client.result[kind]
    assert not updated[summaries.SUMMARY_FIELDS[other]]
    assert summaries.generate_task_summary(task["id"], kind, db_path, client=client) is None
    assert len(client.calls) == 1


def test_existing_long_summary_stays_byte_for_byte_unchanged(completed_task, tmp_path):
    db_path, task = completed_task
    old = tmp_path / "existing.md"
    original = b"# Existing\r\n\r\nAn existing summary.\r\n"
    old.write_bytes(original)
    update_task(task["id"], {"summarize": str(old)}, db_path)
    client = FakeClient()
    updated = summaries.generate_task_summary(task["id"], "brief", db_path, client=client, summaries_dir=tmp_path / "out")
    assert client.calls[0][1] == "brief"
    assert "长版 detail：" not in client.calls[0][0]
    assert updated["summarize"] == str(old)
    assert old.read_bytes() == original


def test_long_chinese_title_fits_filename_limit(completed_task, tmp_path):
    db_path, task = completed_task
    update_task(task["id"], {"episode_title": "中文标题" * 50}, db_path)
    for kind, field in summaries.SUMMARY_FIELDS.items():
        updated = summaries.generate_task_summary(
            task["id"], kind, db_path, client=FakeClient(), summaries_dir=tmp_path / "out",
        )
        path = Path(updated[field])
        assert path.exists()
        assert len(path.name.encode("utf-8")) <= 255


@pytest.mark.parametrize("mutation", ["manual", "archived", "new_transcript", "deleted"])
def test_concurrent_changes_win_and_unused_files_are_removed(completed_task, tmp_path, mutation):
    from backend.db import delete_task

    db_path, task = completed_task

    def change_task():
        if mutation == "deleted":
            delete_task(task["id"], db_path)
        else:
            values = {
                "manual": {"summarize": "/manual.md"},
                "archived": {"status": "archived"},
                "new_transcript": {"output_txt_path": "/new-transcript.txt"},
            }[mutation]
            update_task(task["id"], values, db_path)

    out = tmp_path / "out"
    updated = summaries.generate_task_summary(task["id"], "detail", db_path, client=FakeClient(before_return=change_task), summaries_dir=out)
    assert updated is None
    assert not list(out.iterdir())
    if mutation == "manual":
        assert get_task(task["id"], db_path)["summarize"] == "/manual.md"


@pytest.mark.parametrize("result", [{"brief": "ok", "detail": " "}, {"brief": "ok", "detail": 42}])
def test_failed_long_summary_preserves_previously_generated_brief(completed_task, tmp_path, result):
    db_path, task = completed_task
    brief = summaries.generate_task_summary(task["id"], "brief", db_path, client=FakeClient(), summaries_dir=tmp_path / "out")
    with pytest.raises(SummaryProviderError):
        summaries.generate_task_summary(task["id"], "detail", db_path, client=FakeClient(result), summaries_dir=tmp_path / "out")
    updated = get_task(task["id"], db_path)
    assert not updated["summarize"]
    assert updated["summarize_brief"] == brief["summarize_brief"]
    assert len(list((tmp_path / "out").iterdir())) == 1
    assert list_task_events(task["id"], db_path)[-1]["level"] == "error"


def test_empty_transcript_fails_before_call(completed_task):
    db_path, task = completed_task
    Path(task["output_txt_path"]).write_text(" ", encoding="utf-8")
    client = FakeClient()
    with pytest.raises(SummaryTranscriptMissingError, match="Transcript is empty"):
        summaries.generate_task_summary(task["id"], "brief", db_path, client=client)
    assert not client.calls


@pytest.mark.parametrize("installation", ["user_and_global", "user_only", "path_only"])
def test_codex_cli_uses_fixed_model_effort_skill_and_schema(tmp_path, monkeypatch, installation):
    skill = tmp_path / "SKILL.md"
    skill.write_text("Edit natural Chinese.", encoding="utf-8")
    calls = []
    local_codex = tmp_path / ".local/bin/codex"
    if installation != "path_only":
        local_codex.parent.mkdir(parents=True)
        local_codex.touch()
        local_codex.chmod(0o700)
    global_codex = "/global/bin/codex"
    executable = global_codex if installation == "path_only" else str(local_codex)
    monkeypatch.setattr(summaries.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(summaries.shutil, "which", lambda name: None if installation == "user_only" else global_codex)

    class Process:
        returncode = 0

        def __init__(self, command, **kwargs):
            self.command = command
            calls.append((command, kwargs))

        def communicate(self, prompt, timeout):
            assert "$humanizer-zh" in prompt
            schema = json.loads(Path(self.command[self.command.index("--output-schema") + 1]).read_text())
            assert schema["required"] == ["brief"]
            assert not schema["additionalProperties"]
            Path(self.command[self.command.index("--output-last-message") + 1]).write_text('{"brief":"观点。"}', encoding="utf-8")

    monkeypatch.setattr(summaries.subprocess, "Popen", Process)
    result = summaries.CodexSummaryClient(skill_path=skill).generate("Use $humanizer-zh", "brief")
    assert result == {"brief": "观点。"}
    command, kwargs = calls[0]
    assert command[0] == executable
    assert command[command.index("--model") + 1] == "gpt-6.1-sol"
    assert 'model_reasoning_effort="low"' in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "--ephemeral" in command
    assert kwargs["start_new_session"]


def test_missing_skill_prevents_codex_call(tmp_path, monkeypatch):
    def unexpected_call(*args, **kwargs):
        pytest.fail("Codex should not start without the skill")

    monkeypatch.setattr(summaries.subprocess, "Popen", unexpected_call)
    with pytest.raises(SummaryNotConfiguredError):
        summaries.CodexSummaryClient(skill_path=tmp_path / "missing.md").generate("prompt", "brief")


def test_timeout_kills_codex_process_group(tmp_path, monkeypatch):
    skill = tmp_path / "SKILL.md"
    skill.write_text("Edit.")
    killed = []

    class Process:
        pid = 12345
        returncode = None

        def __init__(self, *args, **kwargs):
            self.waiting = True

        def communicate(self, *args, **kwargs):
            if self.waiting:
                self.waiting = False
                raise subprocess.TimeoutExpired("codex", 5)

    monkeypatch.setattr(summaries.subprocess, "Popen", Process)
    monkeypatch.setattr(summaries.shutil, "which", lambda name: "/test/codex")
    monkeypatch.setattr(summaries.os, "killpg", lambda pid, sig: killed.append(pid))
    with pytest.raises(SummaryProviderError, match="timed out"):
        summaries.CodexSummaryClient(skill_path=skill, timeout_seconds=5).generate("prompt", "brief")
    assert killed == [12345]


def test_missing_cli_is_reported_as_configuration_error(tmp_path, monkeypatch):
    skill = tmp_path / "SKILL.md"
    skill.write_text("Edit.")
    monkeypatch.setattr(summaries.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(summaries.shutil, "which", lambda name: None)
    with pytest.raises(SummaryNotConfiguredError, match="Codex CLI is not installed"):
        summaries.CodexSummaryClient(skill_path=skill).generate("prompt", "brief")


@pytest.mark.parametrize("value", [None, [], {"brief": "ok", "extra": "no"}, {"brief": ""}])
def test_rejects_bad_structured_results(value):
    with pytest.raises(SummaryProviderError):
        summaries.validate_summary(value, "brief")
