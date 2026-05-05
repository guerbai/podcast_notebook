from pathlib import Path


def test_frontend_script_uses_chinese_ui_copy():
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    script = Path("frontend/app.js").read_text(encoding="utf-8")
    assert "还没有找到任何内容" in script
    assert "先选择播客" in script
    assert "转写中" in script
    assert "最近 10 期" in script
    assert "节目源" not in script
    assert "节目源" not in html


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


def test_summary_modal_resets_scroll_on_open():
    script = Path("frontend/app.js").read_text(encoding="utf-8")

    assert "function resetSummaryScroll()" in script
    assert "summaryModal.scrollTop = 0" in script
    assert "summaryContent.scrollTop = 0" in script
    assert "window.requestAnimationFrame?.(resetSummaryScroll)" in script


def test_frontend_exposes_language_toggle_and_i18n_dictionaries():
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    script = Path("frontend/app.js").read_text(encoding="utf-8")

    assert 'class="top-controls"' in html
    assert 'class="language-control"' in html
    assert 'class="language-switch"' in html
    assert 'data-language-option="zh-CN"' in html
    assert 'data-language-option="en"' in html
    assert html.index('data-language-option="en"') < html.index('data-language-option="zh-CN"')
    assert '<html lang="en">' in html
    assert '<span data-i18n="languageLabel">Language:</span>' in html
    assert 'language: localStorage.getItem("podcast-notebook-language") || DEFAULT_LANGUAGE' in script
    assert 'const DEFAULT_LANGUAGE = "en"' in script
    assert 'state.language = SUPPORTED_LANGUAGES.has(language) ? language : DEFAULT_LANGUAGE' in script
    assert '<wa-select id="language-toggle"' not in html
    assert '<select id="language-toggle"' not in html
    assert "const TRANSLATIONS" in script
    assert "zh-CN" in script
    assert "en" in script
    assert "const languageOptions" in script
    assert 'button.dataset.languageOption === state.language' in script
    assert 'button.setAttribute("aria-pressed", String(isSelected))' in script
    assert "setLanguage" in script
    assert "localStorage" in script
    assert 'lang=${state.language}' in script
    assert "播客笔记本" in script
    assert "Podcast Notebook" in script
    assert "/static/app.js?v=20260503-summarize-lock-fix" in html
    assert "/static/styles.css?v=20260503-summarize-lock-fix" in html


def test_frontend_chinese_copy_omits_sentence_periods():
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    script = Path("frontend/app.js").read_text(encoding="utf-8")

    assert "。" not in html
    assert "。" not in script
    assert "Find the right show first" in html
    assert "先找到正确播客" in script


def test_frontend_renders_brand_logo_asset_in_masthead():
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    styles = Path("frontend/styles.css").read_text(encoding="utf-8")
    logo_path = Path("frontend/assets/logo.svg")

    assert logo_path.exists()
    logo = logo_path.read_text(encoding="utf-8")

    assert '<link rel="icon" href="/static/assets/logo.svg" type="image/svg+xml" />' in html
    assert '<div class="brand-lockup">' in html
    assert '<div class="brand-copy">' in html
    assert 'class="brand-logo"' in html
    assert 'src="/static/assets/logo.svg"' in html
    assert 'alt=""' in html
    assert '<p class="eyebrow">Podcast Notebook</p>' not in html
    assert html.index('<h1 data-i18n="heroTitle">Podcast Notebook</h1>') < html.index('<p class="lede" data-i18n="heroLede"')
    assert ".brand-lockup" in styles
    assert ".brand-copy" in styles
    assert ".brand-logo" in styles
    assert ".masthead-copy {\n  padding: 42px 26px 24px;" in styles
    assert "top: 20px;" in styles
    assert ".brand-lockup {\n  display: flex;\n  align-items: flex-start;" in styles
    assert "color: var(--teal);" in styles
    assert 'viewBox="0 0 142 142"' in logo
    assert 'color="#235f62"' in logo
    assert "<circle" in logo
    assert "currentColor" in logo


def test_frontend_renders_github_repository_link():
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    styles = Path("frontend/styles.css").read_text(encoding="utf-8")
    github_logo_path = Path("frontend/assets/github.svg")

    assert github_logo_path.exists()
    github_logo = github_logo_path.read_text(encoding="utf-8")

    assert 'class="masthead-actions"' not in html
    assert html.index('class="language-switch"') < html.index('class="github-link"')
    assert 'class="masthead-note__body"' in html
    assert 'class="github-link"' in html
    assert 'href="https://github.com/guerbai/podcast_notebook"' in html
    assert 'target="_blank"' in html
    assert 'rel="noreferrer"' in html
    assert 'aria-label="GitHub repository"' in html
    assert 'src="/static/assets/github.svg"' in html
    assert ".masthead-actions" not in styles
    assert ".top-controls" in styles
    assert ".masthead-note__body" in styles
    assert ".language-switch" in styles
    assert ".language-option.is-active" in styles
    assert ".github-link" in styles
    assert ".github-logo" in styles
    assert "border-radius: 999px;" in styles
    assert "width: 26px;" in styles
    assert "width: 17px;" in styles
    assert ".top-controls {\n  display: flex;\n  align-items: center;\n  justify-content: flex-end;\n  gap: 10px;\n}" in styles
    assert ".language-option {\n  min-width: 34px;\n  padding: 4px 7px;" in styles
    assert 'viewBox="0 0 98 96"' in github_logo
    assert 'fill="#7a7d72"' in github_logo


def test_frontend_localizes_task_action_toasts():
    script = Path("frontend/app.js").read_text(encoding="utf-8")

    assert "createdTask" in script
    assert "taskRestarted" in script
    assert 'result.result === "existing" ? t("existingTask") : t("createdTask")' in script
    assert 'showToast(t("taskRestarted"), "success")' in script
    assert 'showToast(result.message, "success")' not in script


def test_podcast_result_selected_state_is_visible_and_accessible():
    script = Path("frontend/app.js").read_text(encoding="utf-8")
    styles = Path("frontend/styles.css").read_text(encoding="utf-8")

    assert "podcast-result--selected" in script
    assert 'button.setAttribute("aria-pressed", String(isSelected))' in script
    assert "state.podcastResults = data.items || []" in script
    assert "renderPodcastResults()" in script
    assert "selectedPodcastBadge" not in script
    assert "podcast-result__badge" not in script
    assert ".podcast-result--selected" in styles
    assert ".podcast-result__badge" not in styles


def test_shownotes_copy_uses_episode_intro_and_file_modal_kicker_is_distinct():
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    script = Path("frontend/app.js").read_text(encoding="utf-8")

    assert "Shownotes" in script
    assert "单集介绍" in script
    assert "原始备注" not in html
    assert "原始备注" not in script
    assert "const summaryKicker" in script
    assert "summaryKicker.textContent = t(\"summaryKicker\")" in script
    assert "summaryKicker.textContent = labels[type] || type" in script


def test_created_task_does_not_auto_expand_details():
    script = Path("frontend/app.js").read_text(encoding="utf-8")
    create_task_body = script.split("async function createTask", 1)[1].split("async function deleteTask", 1)[0]

    assert "state.expandedTaskIds.add(result.task.id)" not in create_task_body
    assert "highlightTask(result.task.id)" in create_task_body
    assert "scrollToTask(result.task.id)" in create_task_body


def test_restarted_task_does_not_auto_expand_details():
    script = Path("frontend/app.js").read_text(encoding="utf-8")
    restart_task_body = script.split("async function restartTask", 1)[1].split("async function openTaskSummary", 1)[0]

    assert "state.expandedTaskIds.add(newTaskId)" not in restart_task_body
    assert "highlightTask(newTaskId)" in restart_task_body
    assert "scrollToTask(newTaskId)" in restart_task_body


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
    assert "单集介绍" in script
    assert "播客" in script
    assert "taskListStatus" in script
    assert "filteredTasks" in script
    assert "All podcasts" in html
    assert "In progress" in html
    assert "Completed" in html
    assert "icon-button" in styles
    assert "task-filters" in styles
    assert "下载进度" in script
    assert "转写进度" in script
    assert "workflow-stack" in styles
    assert "position: sticky;" not in styles
    assert "episode-browser" in styles
    assert "episode-card__actions" in styles
    assert "Create task" in script
    assert "white-space: normal;" in styles
    assert "transcriptReady" not in script
    assert "audioReady" not in script
    assert "ledger-summary" not in script
    assert ".ledger-summary" not in styles
    assert "task.output_txt_path || task.audio_file_path" not in script
    assert 'class="episode-toolbar__hint"' not in html
    assert ".episode-toolbar {\n  display: block;\n}" in styles
    assert "font-size: 1.3rem;" in styles
    assert "task-progress--download" in script
    assert "task-progress--transcription" in script
    assert "shownotes: episode.summary" not in script
    assert 'limit: "10"' in script
    assert ".slice(0, 10)" not in script
    assert "detail.shownotes" in script
    assert "detail.summarize" in script
    assert "/shownotes" in script
    assert "/summarize" in script


def test_frontend_exposes_manual_summarize_generation_for_eligible_tasks():
    script = Path("frontend/app.js").read_text(encoding="utf-8")

    assert "generateSummarize" in script
    assert "生成总结" in script
    assert "正在生成总结…" in script
    assert "总结已生成" in script
    assert "Generate summary" in script
    assert "Generating summary..." in script
    assert "Summary generated." in script
    assert 'data-action="generate-summarize"' in script
    assert "const SUMMARIZE_LOCK_TTL_MS = 10 * 60 * 1000" in script
    assert "function summarizeLockKey(taskId, language)" in script
    assert "function isSummarizeLocked(taskId, language)" in script
    assert "function setSummarizeLock(taskId, language)" in script
    assert "function clearSummarizeLock(taskId, language)" in script
    assert "localStorage.setItem(summarizeLockKey(taskId, language), String(Date.now() + SUMMARIZE_LOCK_TTL_MS))" in script
    assert "Boolean(task.output_txt_path) && !hasLocalizedSummarize && !isSummarizeLockedForLanguage" in script
    assert 'isSummarizeLockedForLanguage ? t("generatingSummarize")' in script
    assert 'fetchJson(`/api/tasks/${task.id}/summarize`, {' in script
    assert "body: JSON.stringify({ lang: state.language })" in script
    assert "setSummarizeLock(task.id, state.language)" in script
    assert "clearSummarizeLock(task.id, state.language)" in script
    assert 'showToast(t("summarizeGenerated"), "success")' in script


def test_frontend_generated_summary_takes_priority_over_local_lock():
    script = Path("frontend/app.js").read_text(encoding="utf-8")

    assert "const isSummarizeLockedForLanguage = !hasLocalizedSummarize && isSummarizeLocked(task.id, state.language)" in script
    assert "if (hasLocalizedSummarize) {\n    clearSummarizeLock(task.id, state.language);\n  }" in script


def test_podcast_search_results_use_stable_layout():
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    script = Path("frontend/app.js").read_text(encoding="utf-8")
    styles = Path("frontend/styles.css").read_text(encoding="utf-8")

    assert "/static/app.js?v=" in html
    assert "/static/styles.css?v=" in html
    assert "list-item podcast-result" in script
    assert ".list-item {" in styles
    assert "align-items: flex-start;" in styles
    assert "justify-content: flex-start;" in styles
