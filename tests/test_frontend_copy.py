from pathlib import Path


def test_frontend_script_uses_chinese_ui_copy():
    script = Path("frontend/app.js").read_text(encoding="utf-8")
    assert "还没有找到任何内容。" in script
    assert "请选择一个播客。" in script
    assert "转写中" in script
    assert "最近 10 期" in script


def test_frontend_uses_custom_feedback_ui():
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    script = Path("frontend/app.js").read_text(encoding="utf-8")

    assert 'data-role="toast-region"' in html
    assert 'data-role="confirm-modal"' in html
    assert 'data-role="summary-modal"' in html
    assert 'id="task-podcast-filter"' in html
    assert 'id="task-status-filter"' in html
    assert "window.confirm" not in script
    assert "window.alert" not in script


def test_frontend_includes_split_progress_and_layout_markers():
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    script = Path("frontend/app.js").read_text(encoding="utf-8")
    styles = Path("frontend/styles.css").read_text(encoding="utf-8")

    assert "expandedTaskIds" in script
    assert "isCreatingTask" in script
    assert "已定位到现有任务" in script
    assert "loadRecentEpisodes" in script
    assert "renderMarkdown" in script
    assert "查看总结" in script
    assert "查看 Shownotes" in script
    assert "查看 Summarize" in script
    assert "taskListStatus" in script
    assert "filteredTasks" in script
    assert "全部播客" in html
    assert "进行中" in html
    assert "已完成" in html
    assert "icon-button" in styles
    assert "task-filters" in styles
    assert "下载进度" in script
    assert "转写进度" in script
    assert "workflow-stack" in styles
    assert "episode-browser" in styles
    assert "episode-card__actions" in styles
    assert "task-progress--download" in script
    assert "task-progress--transcription" in script
    assert "shownotes: episode.summary || \"\"" in script
    assert "detail.shownotes" in script
    assert "detail.summarize" in script
    assert "/shownotes" in script
    assert "/summarize" in script
