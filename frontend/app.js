const state = {
  language: localStorage.getItem("podcast-notebook-language") || "zh-CN",
  selectedPodcast: null,
  tasksPoller: null,
  taskDetails: new Map(),
  expandedTaskIds: new Set(),
  pendingActionTaskIds: new Set(),
  highlightedTaskId: null,
  highlightTimer: null,
  isCreatingTask: false,
  confirmDeleteTaskId: null,
  summaries: new Map(),
  taskFiles: new Map(),
  podcastResults: [],
  tasks: [],
  taskFilters: {
    podcastTitle: "",
    status: "",
  },
};

const SUMMARIZE_LOCK_TTL_MS = 10 * 60 * 1000;

const podcastQueryInput = document.querySelector("#podcast-query");
const episodeQueryInput = document.querySelector("#episode-query");
const podcastResults = document.querySelector("#podcast-results");
const episodeResults = document.querySelector("#episode-results");
const taskResults = document.querySelector("#task-results");
const taskPodcastFilter = document.querySelector("#task-podcast-filter");
const taskStatusFilter = document.querySelector("#task-status-filter");
const selectedPodcastLabel = document.querySelector("#selected-podcast");
const episodeSubhead = document.querySelector("#episode-subhead");
const toastRegion = document.querySelector('[data-role="toast-region"]');
const confirmModal = document.querySelector('[data-role="confirm-modal"]');
const confirmDeleteButton = document.querySelector("#confirm-delete-task");
const summaryModal = document.querySelector('[data-role="summary-modal"]');
const summaryContent = document.querySelector("#summary-content");
const summaryKicker = summaryModal.querySelector(".modal-kicker");
const summaryTitle = document.querySelector("#summary-title");
const languageOptions = document.querySelectorAll("[data-language-option]");

const TRANSLATIONS = {
  "zh-CN": {
    pageTitle: "播客笔记本",
    modalDeleteKicker: "删除确认",
    modalDeleteTitle: "要删除这个任务吗？",
    modalDeleteCopy: "关联的本地音频、全文稿和事件日志也会一起删除，运行中的任务会先停止，再完成清理",
    keepTask: "先保留",
    confirmDelete: "确认删除",
    summaryKicker: "节目总结",
    summaryTitle: "总结内容",
    close: "关闭",
    heroTitle: "播客笔记本",
    heroLede: "检索、转写、总结，集中管理本地播客笔记",
    noteTitle: "本地任务",
    noteBody: "全文、单集介绍和总结文件会关联到同一条任务",
    languageLabel: "语言：",
    searchPodcastTitle: "播客",
    searchPodcastIntro: "先找到正确播客",
    searchPodcastAction: "搜索播客",
    podcastName: "播客",
    podcastPlaceholder: "大内密谈",
    chooseEpisodeTitle: "单集",
    chooseEpisodeIntro: "选择一集创建任务",
    episodeInitial: "先选择播客",
    episodeKeyword: "关键词",
    episodePlaceholder: "Codex",
    searchEpisode: "筛选单集",
    recentTen: "最近 10 期",
    archiveTitle: "任务",
    archiveIntro: "查看进度、文件和结果",
    allPodcasts: "全部播客",
    podcastFilterPlaceholder: "播客",
    statusFilterPlaceholder: "状态",
    statusOptionAll: "状态",
    statusInProgress: "进行中",
    statusCompleted: "已完成",
    emptyDefault: "还没有找到任何内容",
    requestFailed: "请求失败：{status}",
    noFilteredTasks: "当前筛选条件下没有任务",
    searchingPodcasts: "正在搜索播客…",
    podcastKicker: "播客",
    currentSelected: "已选：{title}",
    switchedPodcast: "已选择《{title}》",
    selectPodcastFirst: "先选择播客",
    loadingRecent: "正在加载最近 10 期…",
    noEpisodes: "这个播客暂时没有可用的单集记录",
    episodeSearchResults: "搜索结果：{query}",
    searchingEpisodes: "正在搜索单集…",
    noMatchingEpisodes: "当前条件下还没有找到匹配单集",
    episodeKicker: "单集",
    creating: "正在创建…",
    createTask: "创建任务",
    taskDeleted: "任务已删除",
    noContent: "暂无内容",
    taskKicker: "任务 {id}",
    restart: "重新开始",
    delete: "删除",
    listStatus: "列表状态",
    stage: "阶段",
    downloadProgress: "下载进度",
    transcriptionProgress: "转写进度",
    summarize: "总结",
    generated: "已生成",
    notGenerated: "未生成",
    collapseDetails: "收起详情",
    viewDetails: "查看详情",
    viewSummary: "查看摘要",
    viewShownotes: "单集介绍",
    viewSummarize: "查看总结",
    generateSummarize: "生成总结",
    generatingSummarize: "正在生成总结…",
    summarizeGenerated: "总结已生成",
    loadingDetails: "正在加载详情…",
    files: "文件",
    transcriptPending: "转写全文尚未生成",
    audioPending: "当前没有保留音频文件",
    notes: "备注",
    noError: "当前没有异常信息",
    shownotesFile: "单集介绍",
    noShownotes: "当前没有单集介绍",
    summarizeFile: "中文总结",
    summarizeEnFile: "英文总结",
    noSummarize: "当前没有中文总结",
    noSummarizeEn: "当前没有英文总结",
    recentLogs: "最近日志",
    noEvents: "还没有记录到任何事件",
    timeMissing: "未记录时间",
    unknownStage: "未知阶段",
    existingTask: "已定位到现有任务",
    createdTask: "任务已创建，开始处理",
    taskRestarted: "任务已重新开始",
    status: {
      queued: "排队中",
      running: "执行中",
      cancelling: "停止中",
      completed: "已完成",
      failed: "失败",
    },
    stageLabels: {
      queued: "等待开始",
      downloading_audio: "下载音频中",
      transcribing: "转写中",
      finalizing: "正在收尾",
      completed: "已完成",
      failed: "执行失败",
      cancelled: "已取消",
    },
  },
  en: {
    pageTitle: "Podcast Notebook",
    modalDeleteKicker: "Delete",
    modalDeleteTitle: "Delete this task?",
    modalDeleteCopy: "Local audio, transcript files, and event logs linked to this task will be removed too. Running tasks will stop before cleanup.",
    keepTask: "Keep task",
    confirmDelete: "Delete",
    summaryKicker: "Episode Summary",
    summaryTitle: "Summary",
    close: "Close",
    heroTitle: "Podcast Notebook",
    heroLede: "Search, transcribe, summarize, and keep local podcast notes in one place.",
    noteTitle: "Local Tasks",
    noteBody: "Transcript, original notes, and summaries stay linked to the same task.",
    languageLabel: "Language:",
    searchPodcastTitle: "Podcast",
    searchPodcastIntro: "Find the right podcast feed.",
    searchPodcastAction: "Search podcast",
    podcastName: "Podcast",
    podcastPlaceholder: "The Tim Ferriss Show",
    chooseEpisodeTitle: "Episode",
    chooseEpisodeIntro: "Pick one episode to create a task.",
    episodeInitial: "Choose a podcast first",
    episodeKeyword: "Keyword",
    episodePlaceholder: "Codex",
    searchEpisode: "Filter episodes",
    recentTen: "Latest 10",
    archiveTitle: "Tasks",
    archiveIntro: "Track progress, files, and results.",
    allPodcasts: "All podcasts",
    podcastFilterPlaceholder: "Podcast",
    statusFilterPlaceholder: "Status",
    statusOptionAll: "Status",
    statusInProgress: "In progress",
    statusCompleted: "Completed",
    emptyDefault: "Nothing here yet.",
    requestFailed: "Request failed: {status}",
    noFilteredTasks: "No tasks match the current filters.",
    searchingPodcasts: "Searching podcasts...",
    podcastKicker: "Podcast",
    currentSelected: "Selected: {title}",
    switchedPodcast: "Selected {title}",
    selectPodcastFirst: "Choose a podcast first.",
    loadingRecent: "Loading the latest 10...",
    noEpisodes: "No episodes are available for this podcast yet.",
    episodeSearchResults: "Search results: {query}",
    searchingEpisodes: "Searching episodes...",
    noMatchingEpisodes: "No matching episodes found.",
    episodeKicker: "Episode",
    creating: "Creating...",
    createTask: "Create task",
    taskDeleted: "Task deleted.",
    noContent: "No content.",
    taskKicker: "Task {id}",
    restart: "Restart",
    delete: "Delete",
    listStatus: "List status",
    stage: "Stage",
    downloadProgress: "Download",
    transcriptionProgress: "Transcription",
    summarize: "Summary",
    generated: "Generated",
    notGenerated: "Not generated",
    collapseDetails: "Hide details",
    viewDetails: "View details",
    viewSummary: "View digest",
    viewShownotes: "Shownotes",
    viewSummarize: "View summary",
    generateSummarize: "Generate summary",
    generatingSummarize: "Generating summary...",
    summarizeGenerated: "Summary generated.",
    loadingDetails: "Loading details...",
    files: "Files",
    transcriptPending: "Transcript has not been generated yet.",
    audioPending: "No local audio file is retained.",
    notes: "Notes",
    noError: "No errors recorded.",
    shownotesFile: "Shownotes file",
    noShownotes: "No shownotes recorded.",
    summarizeFile: "Chinese summary file",
    summarizeEnFile: "English summary file",
    noSummarize: "No Chinese summary recorded.",
    noSummarizeEn: "No English summary recorded.",
    recentLogs: "Recent logs",
    noEvents: "No events recorded yet.",
    timeMissing: "No timestamp",
    unknownStage: "Unknown stage",
    existingTask: "Found an existing task.",
    createdTask: "Task created and processing has started.",
    taskRestarted: "Task restarted.",
    status: {
      queued: "Queued",
      running: "Running",
      cancelling: "Stopping",
      completed: "Completed",
      failed: "Failed",
    },
    stageLabels: {
      queued: "Queued",
      downloading_audio: "Downloading audio",
      transcribing: "Transcribing",
      finalizing: "Finalizing",
      completed: "Completed",
      failed: "Failed",
      cancelled: "Cancelled",
    },
  },
};

const SUPPORTED_LANGUAGES = new Set(Object.keys(TRANSLATIONS));

function currentTranslations() {
  return TRANSLATIONS[state.language] || TRANSLATIONS["zh-CN"];
}

function t(key, values = {}) {
  const parts = key.split(".");
  let value = currentTranslations();
  for (const part of parts) {
    value = value?.[part];
  }
  const fallback = parts.reduce((source, part) => source?.[part], TRANSLATIONS["zh-CN"]);
  const template = typeof value === "string" ? value : fallback || key;
  return Object.entries(values).reduce(
    (message, [name, replacement]) => message.replaceAll(`{${name}}`, String(replacement)),
    template,
  );
}

function emptyState(message) {
  return `<p class="empty">${escapeHtml(message)}</p>`;
}

function applyStaticTranslations() {
  document.documentElement.lang = state.language;
  document.title = t("pageTitle");
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.setAttribute("placeholder", t(node.dataset.i18nPlaceholder));
  });
  document.querySelectorAll("[data-i18n-title]").forEach((node) => {
    node.setAttribute("title", t(node.dataset.i18nTitle));
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach((node) => {
    node.setAttribute("aria-label", t(node.dataset.i18nAriaLabel));
  });
  languageOptions.forEach((button) => {
    const isSelected = button.dataset.languageOption === state.language;
    button.classList.toggle("is-active", isSelected);
    button.setAttribute("aria-pressed", String(isSelected));
  });
}

function setLanguage(language) {
  state.language = SUPPORTED_LANGUAGES.has(language) ? language : "zh-CN";
  localStorage.setItem("podcast-notebook-language", state.language);
  state.taskFiles.clear();
  applyStaticTranslations();
  if (state.selectedPodcast) {
    selectedPodcastLabel.textContent = t("currentSelected", { title: state.selectedPodcast.title });
  }
  syncTaskPodcastFilter(state.tasks);
  renderTasks();
}

const PROGRESS_CLASSES = {
  download: "task-progress--download",
  transcription: "task-progress--transcription",
};

const TASK_FILE_ENDPOINTS = {
  shownotes: (taskId) => `/api/tasks/${taskId}/shownotes`,
  summarize: (taskId) => `/api/tasks/${taskId}/summarize`,
};

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (response.status === 204) {
    return null;
  }
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.message || t("requestFailed", { status: response.status }));
  }
  return payload;
}

function renderList(container, items, renderItem, emptyMessage = t("emptyDefault")) {
  container.innerHTML = "";
  if (!items.length) {
    container.innerHTML = emptyState(emptyMessage);
    return;
  }
  const list = document.createElement("div");
  list.className = "list";
  items.forEach((item) => list.append(renderItem(item)));
  container.append(list);
}

function showToast(message, tone = "info") {
  const toast = document.createElement("div");
  toast.className = `toast toast--${tone}`;
  toast.textContent = message;
  toastRegion?.append(toast);
  window.setTimeout(() => {
    toast.classList.add("toast--leaving");
    window.setTimeout(() => toast.remove(), 220);
  }, 2600);
}

function openDeleteModal(taskId) {
  state.confirmDeleteTaskId = taskId;
  confirmModal?.removeAttribute("hidden");
}

function closeDeleteModal() {
  state.confirmDeleteTaskId = null;
  confirmModal?.setAttribute("hidden", "hidden");
}

function openSummaryModal() {
  summaryModal?.removeAttribute("hidden");
  resetSummaryScroll();
  window.requestAnimationFrame?.(resetSummaryScroll);
}

function closeSummaryModal() {
  summaryModal?.setAttribute("hidden", "hidden");
}

function resetSummaryScroll() {
  if (summaryModal) {
    summaryModal.scrollTop = 0;
  }
  if (summaryContent) {
    summaryContent.scrollTop = 0;
  }
}

function setTaskPending(taskId, isPending) {
  if (isPending) {
    state.pendingActionTaskIds.add(taskId);
  } else {
    state.pendingActionTaskIds.delete(taskId);
  }
}

function clearTaskFileCache(taskId) {
  state.summaries.delete(taskId);
  state.taskFiles.delete(`shownotes:${taskId}`);
  state.taskFiles.delete(`summarize:${taskId}:zh-CN`);
  state.taskFiles.delete(`summarize:${taskId}:en`);
}

function summarizeLockKey(taskId, language) {
  return `podcast-notebook-summarize-lock:${taskId}:${language}`;
}

function isSummarizeLocked(taskId, language) {
  const expiresAt = Number(localStorage.getItem(summarizeLockKey(taskId, language)) || 0);
  if (!expiresAt) {
    return false;
  }
  if (Date.now() >= expiresAt) {
    clearSummarizeLock(taskId, language);
    return false;
  }
  return true;
}

function setSummarizeLock(taskId, language) {
  localStorage.setItem(summarizeLockKey(taskId, language), String(Date.now() + SUMMARIZE_LOCK_TTL_MS));
}

function clearSummarizeLock(taskId, language) {
  localStorage.removeItem(summarizeLockKey(taskId, language));
}

function highlightTask(taskId) {
  state.highlightedTaskId = taskId;
  window.clearTimeout(state.highlightTimer);
  state.highlightTimer = window.setTimeout(() => {
    state.highlightedTaskId = null;
    loadTasks();
  }, 2200);
}

function scrollToTask(taskId) {
  window.requestAnimationFrame(() => {
    const target = document.querySelector(`[data-task-id="${taskId}"]`);
    target?.scrollIntoView({ behavior: "smooth", block: "center" });
  });
}

function formatStatus(task) {
  return taskListStatus(task) === "completed" ? t("statusCompleted") : t("statusInProgress");
}

function formatStage(task) {
  return currentTranslations().stageLabels?.[task.progress_stage] || TRANSLATIONS["zh-CN"].stageLabels[task.progress_stage] || task.progress_stage || t("unknownStage");
}

function formatDate(value) {
  if (!value) return t("timeMissing");
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(state.language, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function statusTone(task) {
  if (taskListStatus(task) === "completed") return "status-completed";
  if (task.status === "failed") return "status-failed";
  if (task.status === "cancelling") return "status-cancelling";
  if (task.status === "running") return "status-running";
  return "status-queued";
}

function progressValue(value) {
  return Math.max(0, Math.min(Number(value || 0), 100));
}

function taskListStatus(task) {
  const downloadDone = progressValue(task.download_percent) >= 100;
  const transcriptionDone = progressValue(task.transcription_percent) >= 100;
  return downloadDone && transcriptionDone && Boolean(task.summarize) ? "completed" : "in_progress";
}

function filteredTasks() {
  return state.tasks.filter((task) => {
    if (state.taskFilters.podcastTitle && task.podcast_title !== state.taskFilters.podcastTitle) {
      return false;
    }
    if (state.taskFilters.status && taskListStatus(task) !== state.taskFilters.status) {
      return false;
    }
    return true;
  });
}

function syncTaskPodcastFilter(tasks) {
  if (!taskPodcastFilter) return;
  const titles = [...new Set(tasks.map((task) => task.podcast_title).filter(Boolean))].sort((a, b) => a.localeCompare(b, state.language));
  if (state.taskFilters.podcastTitle && !titles.includes(state.taskFilters.podcastTitle)) {
    state.taskFilters.podcastTitle = "";
  }
  const currentValue = state.taskFilters.podcastTitle;
  taskPodcastFilter.innerHTML = [
    `<wa-option value="">${escapeHtml(t("allPodcasts"))}</wa-option>`,
    ...titles.map((title) => `<wa-option value="${escapeAttribute(title)}">${escapeHtml(title)}</wa-option>`),
  ].join("");
  taskPodcastFilter.value = currentValue;
}

function renderTasks() {
  renderList(taskResults, filteredTasks(), renderTask, t("noFilteredTasks"));
}

async function searchPodcasts() {
  const q = podcastQueryInput.value.trim();
  if (!q) return;
  podcastResults.innerHTML = emptyState(t("searchingPodcasts"));
  try {
    const data = await fetchJson(`/api/search/podcasts?q=${encodeURIComponent(q)}`);
    state.podcastResults = data.items || [];
    renderPodcastResults();
  } catch (error) {
    podcastResults.innerHTML = `<p class="empty">${error.message}</p>`;
    showToast(error.message, "error");
  }
}

function renderPodcastResults() {
  renderList(podcastResults, state.podcastResults, renderPodcastResult);
}

function renderPodcastResult(item) {
  const button = document.createElement("button");
  const isSelected = state.selectedPodcast?.rss_url === item.rss_url;
  button.className = `list-item podcast-result ${isSelected ? "podcast-result--selected" : ""}`;
  button.type = "button";
  button.setAttribute("aria-pressed", String(isSelected));
  button.innerHTML = `
    <span class="podcast-result__topline">
      <span class="kicker">${escapeHtml(t("podcastKicker"))}</span>
    </span>
    <strong>${escapeHtml(item.title)}</strong>
    <span>${escapeHtml(item.author || item.rss_url)}</span>
  `;
  button.addEventListener("click", () => {
    state.selectedPodcast = item;
    selectedPodcastLabel.textContent = t("currentSelected", { title: item.title });
    renderPodcastResults();
    loadRecentEpisodes();
    showToast(t("switchedPodcast", { title: item.title }), "info");
  });
  return button;
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll('"', "&quot;");
}

function renderInlineMarkdown(text) {
  return text
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

function renderMarkdown(markdown) {
  const lines = markdown.split("\n");
  const html = [];
  let listType = null;
  let paragraph = [];
  let hasRenderedPrimaryHeading = false;

  const flushParagraph = () => {
    if (paragraph.length) {
      html.push(`<p>${paragraph.join("<br>")}</p>`);
      paragraph = [];
    }
  };

  const closeList = () => {
    if (listType) {
      html.push(listType === "ol" ? "</ol>" : "</ul>");
      listType = null;
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    const safe = escapeHtml(line.trim());
    const rich = renderInlineMarkdown(safe);

    if (!line.trim()) {
      flushParagraph();
      closeList();
      continue;
    }

    if (safe.startsWith("### ")) {
      flushParagraph();
      closeList();
      html.push(`<h3>${renderInlineMarkdown(safe.slice(4))}</h3>`);
      continue;
    }
    if (safe.startsWith("## ")) {
      flushParagraph();
      closeList();
      html.push(`<h2>${renderInlineMarkdown(safe.slice(3))}</h2>`);
      continue;
    }
    if (safe.startsWith("# ")) {
      flushParagraph();
      closeList();
      if (!hasRenderedPrimaryHeading) {
        hasRenderedPrimaryHeading = true;
        continue;
      }
      html.push(`<h1>${renderInlineMarkdown(safe.slice(2))}</h1>`);
      continue;
    }
    if (/^\d+\.\s+/.test(safe)) {
      flushParagraph();
      if (listType !== "ol") {
        closeList();
        listType = "ol";
        html.push("<ol>");
      }
      html.push(`<li>${renderInlineMarkdown(safe.replace(/^\d+\.\s+/, ""))}</li>`);
      continue;
    }
    if (safe.startsWith("- ")) {
      flushParagraph();
      if (listType !== "ul") {
        closeList();
        listType = "ul";
        html.push("<ul>");
      }
      html.push(`<li>${renderInlineMarkdown(safe.slice(2))}</li>`);
      continue;
    }

    closeList();
    paragraph.push(rich);
  }

  flushParagraph();
  closeList();
  return html.join("");
}

function renderPlainText(text) {
  const blocks = text
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean);
  if (!blocks.length) {
    return emptyState(t("noContent"));
  }
  return blocks
    .map((block) => `<p>${escapeHtml(block).replaceAll("\n", "<br>")}</p>`)
    .join("");
}

async function loadRecentEpisodes() {
  if (!state.selectedPodcast) {
    episodeResults.innerHTML = emptyState(t("selectPodcastFirst"));
    return;
  }
  episodeSubhead.textContent = t("loadingRecent");
  episodeResults.innerHTML = emptyState(t("loadingRecent"));
  try {
    const params = new URLSearchParams({
      rss_url: state.selectedPodcast.rss_url,
      q: "",
      limit: "10",
    });
    const data = await fetchJson(`/api/search/episodes?${params.toString()}`);
    episodeSubhead.textContent = t("recentTen");
    renderList(
      episodeResults,
      data.items || [],
      renderEpisodeResult,
      t("noEpisodes"),
    );
  } catch (error) {
    episodeSubhead.textContent = error.message;
    episodeResults.innerHTML = `<p class="empty">${error.message}</p>`;
    showToast(error.message, "error");
  }
}

async function searchEpisodes() {
  if (!state.selectedPodcast) {
    episodeResults.innerHTML = emptyState(t("selectPodcastFirst"));
    return;
  }
  const q = episodeQueryInput.value.trim();
  if (!q) {
    await loadRecentEpisodes();
    return;
  }
  episodeSubhead.textContent = t("episodeSearchResults", { query: q });
  episodeResults.innerHTML = emptyState(t("searchingEpisodes"));
  try {
    const params = new URLSearchParams({
      rss_url: state.selectedPodcast.rss_url,
      q,
    });
    const data = await fetchJson(`/api/search/episodes?${params.toString()}`);
    renderList(
      episodeResults,
      data.items || [],
      renderEpisodeResult,
      t("noMatchingEpisodes"),
    );
  } catch (error) {
    episodeResults.innerHTML = `<p class="empty">${error.message}</p>`;
    showToast(error.message, "error");
  }
}

function renderEpisodeResult(item) {
  const wrapper = document.createElement("article");
  wrapper.className = "episode-card";

  const body = document.createElement("div");
  body.className = "episode-card__body";
  body.innerHTML = `
    <span class="kicker">${escapeHtml(t("episodeKicker"))}</span>
    <strong>${escapeHtml(item.title)}</strong>
    <span>${formatDate(item.published || "")}</span>
  `;

  const actions = document.createElement("div");
  actions.className = "episode-card__actions";
  const action = document.createElement("button");
  action.type = "button";
  action.className = "secondary-button";
  action.textContent = state.isCreatingTask ? t("creating") : t("createTask");
  action.disabled = state.isCreatingTask;
  action.addEventListener("click", () => createTask(item, action));
  actions.append(action);

  wrapper.append(body, actions);
  return wrapper;
}

async function createTask(episode, button) {
  if (!state.selectedPodcast || state.isCreatingTask) return;
  state.isCreatingTask = true;
  button.disabled = true;
  button.textContent = t("creating");

  try {
    const result = await fetchJson("/api/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        podcast_title: state.selectedPodcast.title,
        rss_url: state.selectedPodcast.rss_url,
        episode_title: episode.title,
        episode_guid: episode.guid,
        audio_url: episode.audio_url,
      }),
    });
    await loadTasks();
    highlightTask(result.task.id);
    scrollToTask(result.task.id);
    const message = result.result === "existing" ? t("existingTask") : t("createdTask");
    showToast(message, result.result === "existing" ? "warning" : "success");
    await loadTasks();
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    state.isCreatingTask = false;
    button.disabled = false;
    button.textContent = t("createTask");
  }
}

async function deleteTask(taskId) {
  setTaskPending(taskId, true);
  try {
    const result = await fetchJson(`/api/tasks/${taskId}`, { method: "DELETE" });
    if (result?.task?.id) {
      showToast(result.message, "warning");
      state.expandedTaskIds.delete(taskId);
    } else {
      showToast(t("taskDeleted"), "success");
      state.taskDetails.delete(taskId);
    }
    clearTaskFileCache(taskId);
    state.expandedTaskIds.delete(taskId);
    await loadTasks();
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    setTaskPending(taskId, false);
  }
}

async function restartTask(taskId) {
  setTaskPending(taskId, true);
  try {
    const result = await fetchJson(`/api/tasks/${taskId}/restart`, { method: "POST" });
    const replacedTaskId = result.replaced_task_id || taskId;
    const newTaskId = result.task.id;
    state.taskDetails.delete(replacedTaskId);
    clearTaskFileCache(replacedTaskId);
    state.expandedTaskIds.delete(replacedTaskId);
    showToast(t("taskRestarted"), "success");
    await loadTasks();
    highlightTask(newTaskId);
    scrollToTask(newTaskId);
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    setTaskPending(taskId, false);
  }
}

async function generateSummarize(task) {
  setSummarizeLock(task.id, state.language);
  setTaskPending(task.id, true);
  renderTasks();
  try {
    const result = await fetchJson(`/api/tasks/${task.id}/summarize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lang: state.language }),
    });
    state.taskDetails.delete(task.id);
    clearTaskFileCache(task.id);
    clearSummarizeLock(task.id, state.language);
    showToast(t("summarizeGenerated"), "success");
    await loadTasks();
    highlightTask(result.task.id);
  } catch (error) {
    clearSummarizeLock(task.id, state.language);
    showToast(error.message, "error");
  } finally {
    setTaskPending(task.id, false);
    renderTasks();
  }
}

async function openTaskSummary(task) {
  try {
    let summary = state.summaries.get(task.id);
    if (!summary) {
      summary = await fetchJson(`/api/tasks/${task.id}/summary`);
      state.summaries.set(task.id, summary);
    }
    summaryKicker.textContent = t("summaryKicker");
    summaryTitle.textContent = summary.title;
    summaryContent.innerHTML = renderMarkdown(summary.markdown);
    openSummaryModal();
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function openTaskFile(task, type) {
  const labels = {
    shownotes: t("viewShownotes"),
    summarize: t("summarize"),
  };
  try {
    const cacheKey = type === "summarize" ? `${type}:${task.id}:${state.language}` : `${type}:${task.id}`;
    let file = state.taskFiles.get(cacheKey);
    if (!file) {
      const languageQuery = `lang=${state.language}`;
      const url = type === "summarize" ? `${TASK_FILE_ENDPOINTS[type](task.id)}?${languageQuery}` : TASK_FILE_ENDPOINTS[type](task.id);
      file = await fetchJson(url);
      state.taskFiles.set(cacheKey, file);
    }
    summaryKicker.textContent = labels[type] || type;
    summaryTitle.textContent = `${file.title} · ${labels[type] || type}`;
    summaryContent.innerHTML = type === "summarize" ? renderMarkdown(file.content) : renderPlainText(file.content);
    openSummaryModal();
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function loadTaskDetail(taskId) {
  if (!state.taskDetails.has(taskId)) {
    state.taskDetails.set(taskId, { loading: true });
    const detail = await fetchJson(`/api/tasks/${taskId}`);
    state.taskDetails.set(taskId, detail);
  }
  return state.taskDetails.get(taskId);
}

function renderProgressRow(label, value, modifier) {
  const percent = progressValue(value);
  return `
    <div class="task-progress ${PROGRESS_CLASSES[modifier]}">
      <div class="task-progress__label-row">
        <span>${label}</span>
        <strong>${percent.toFixed(1)}%</strong>
      </div>
      <div class="task-progress__rail">
        <div class="task-progress__fill" style="width: ${percent}%"></div>
      </div>
    </div>
  `;
}

function renderTask(task) {
  const article = document.createElement("article");
  article.className = `ledger-entry ${state.highlightedTaskId === task.id ? "ledger-entry--highlighted" : ""}`;
  article.dataset.taskId = String(task.id);

  const isExpanded = state.expandedTaskIds.has(task.id);
  const isPending = state.pendingActionTaskIds.has(task.id);
  const hasLocalizedSummarize = state.language === "en" ? Boolean(task.summarize_en) : Boolean(task.summarize);
  if (hasLocalizedSummarize) {
    clearSummarizeLock(task.id, state.language);
  }
  const isSummarizeLockedForLanguage = !hasLocalizedSummarize && isSummarizeLocked(task.id, state.language);
  const canGenerateSummarize = Boolean(task.output_txt_path) && !hasLocalizedSummarize && !isSummarizeLockedForLanguage;
  const summarizeLabel = isSummarizeLockedForLanguage ? t("generatingSummarize") : hasLocalizedSummarize ? t("generated") : t("notGenerated");

  article.innerHTML = `
    <div class="ledger-entry__frame">
      <div class="ledger-title-group">
        <span class="kicker">${escapeHtml(t("taskKicker", { id: task.id }))}</span>
        <strong>${escapeHtml(task.episode_title)}</strong>
        <p>${escapeHtml(task.podcast_title)}</p>
      </div>

      <div class="ledger-side">
        <div class="ledger-status-row">
          <span class="status ${statusTone(task)}">${formatStatus(task)}</span>
          <button type="button" class="icon-button" data-action="restart" title="${escapeAttribute(t("restart"))}" aria-label="${escapeAttribute(t("restart"))}" ${isPending ? "disabled" : ""}>↻</button>
          <button type="button" class="icon-button icon-button--danger" data-action="delete" title="${escapeAttribute(t("delete"))}" aria-label="${escapeAttribute(t("delete"))}" ${isPending ? "disabled" : ""}>×</button>
        </div>
        <div class="ledger-side__time">${formatDate(task.created_at)}</div>
      </div>
    </div>

    <div class="ledger-meta">
      <span>${escapeHtml(t("stage"))}: ${escapeHtml(formatStage(task))}</span>
      <span>${escapeHtml(t("summarize"))}: ${escapeHtml(summarizeLabel)}</span>
    </div>

    <div class="ledger-progress">
      ${renderProgressRow(t("downloadProgress"), task.download_percent, "download")}
      ${renderProgressRow(t("transcriptionProgress"), task.transcription_percent, "transcription")}
    </div>

    <div class="ledger-actions">
      <button type="button" class="ghost-button" data-action="toggle">${isExpanded ? t("collapseDetails") : t("viewDetails")}</button>
      ${task.summary_md_path ? `<button type="button" class="ghost-button" data-action="summary">${escapeHtml(t("viewSummary"))}</button>` : ""}
      ${task.shownotes ? `<button type="button" class="ghost-button" data-action="shownotes">${escapeHtml(t("viewShownotes"))}</button>` : ""}
      ${hasLocalizedSummarize ? `<button type="button" class="ghost-button" data-action="summarize">${escapeHtml(t("viewSummarize"))}</button>` : ""}
      ${isSummarizeLockedForLanguage ? `<button type="button" class="ghost-button" disabled>${escapeHtml(t("generatingSummarize"))}</button>` : ""}
      ${canGenerateSummarize ? `<button type="button" class="ghost-button" data-action="generate-summarize" ${isPending ? "disabled" : ""}>${escapeHtml(isPending ? t("generatingSummarize") : t("generateSummarize"))}</button>` : ""}
    </div>

    <section class="ledger-detail-panel ${isExpanded ? "is-open" : ""}">
      <div class="detail-body">${renderDetailBody(task.id)}</div>
    </section>
  `;

  article.querySelector('[data-action="toggle"]')?.addEventListener("click", () => toggleTaskDetail(task.id));
  article.querySelector('[data-action="summary"]')?.addEventListener("click", () => openTaskSummary(task));
  article.querySelector('[data-action="shownotes"]')?.addEventListener("click", () => openTaskFile(task, "shownotes"));
  article.querySelector('[data-action="summarize"]')?.addEventListener("click", () => openTaskFile(task, "summarize"));
  article.querySelector('[data-action="generate-summarize"]')?.addEventListener("click", () => generateSummarize(task));
  article.querySelector('[data-action="restart"]')?.addEventListener("click", () => restartTask(task.id));
  article.querySelector('[data-action="delete"]')?.addEventListener("click", () => openDeleteModal(task.id));

  if (isExpanded) {
    ensureTaskDetail(task.id, article.querySelector(".detail-body"));
  }

  return article;
}

function renderDetailBody(taskId) {
  const detail = state.taskDetails.get(taskId);
  if (!detail || detail.loading) {
    return emptyState(t("loadingDetails"));
  }

  const events = (detail.events || [])
    .slice(-6)
    .map((event) => `<li><span>${formatDate(event.created_at)}</span><strong>${escapeHtml(event.message)}</strong></li>`)
    .join("");

  return `
    <div class="detail-grid">
      <div>
        <p class="detail-label">${escapeHtml(t("files"))}</p>
        <p>${escapeHtml(detail.output_txt_path || t("transcriptPending"))}</p>
        <p>${escapeHtml(detail.audio_file_path || t("audioPending"))}</p>
      </div>
      <div>
        <p class="detail-label">${escapeHtml(t("notes"))}</p>
        <p>${escapeHtml(detail.error_message || t("noError"))}</p>
      </div>
      <div>
        <p class="detail-label">${escapeHtml(t("shownotesFile"))}</p>
        <p>${escapeHtml(detail.shownotes || t("noShownotes"))}</p>
      </div>
      <div>
        <p class="detail-label">${escapeHtml(t("summarizeFile"))}</p>
        <p>${escapeHtml(detail.summarize || t("noSummarize"))}</p>
      </div>
      <div>
        <p class="detail-label">${escapeHtml(t("summarizeEnFile"))}</p>
        <p>${escapeHtml(detail.summarize_en || t("noSummarizeEn"))}</p>
      </div>
    </div>
    <div class="detail-log">
      <p class="detail-label">${escapeHtml(t("recentLogs"))}</p>
      <ul>${events || `<li><strong>${escapeHtml(t("noEvents"))}</strong></li>`}</ul>
    </div>
  `;
}

async function ensureTaskDetail(taskId, container) {
  try {
    const detail = await loadTaskDetail(taskId);
    container.innerHTML = renderDetailBody(taskId, detail);
  } catch (error) {
    container.innerHTML = `<p class="empty">${error.message}</p>`;
  }
}

function toggleTaskDetail(taskId) {
  if (state.expandedTaskIds.has(taskId)) {
    state.expandedTaskIds.delete(taskId);
  } else {
    state.expandedTaskIds.add(taskId);
  }
  loadTasks();
}

async function loadTasks() {
  try {
    const data = await fetchJson("/api/tasks");
    state.tasks = data.items || [];
    syncTaskPodcastFilter(state.tasks);
    renderTasks();
  } catch (error) {
    taskResults.innerHTML = `<p class="empty">${error.message}</p>`;
  }
}

document.querySelector("#search-podcasts")?.addEventListener("click", searchPodcasts);
document.querySelector("#search-episodes")?.addEventListener("click", searchEpisodes);
languageOptions.forEach((button) => {
  button.addEventListener("click", () => {
    setLanguage(button.dataset.languageOption);
  });
});
taskPodcastFilter?.addEventListener("change", (event) => {
  state.taskFilters.podcastTitle = event.target.value;
  renderTasks();
});
taskStatusFilter?.addEventListener("change", (event) => {
  state.taskFilters.status = event.target.value;
  renderTasks();
});

document.querySelectorAll("[data-modal-close]")?.forEach((node) => {
  node.addEventListener("click", closeDeleteModal);
});

confirmDeleteButton?.addEventListener("click", async () => {
  const taskId = state.confirmDeleteTaskId;
  closeDeleteModal();
  if (taskId != null) {
    await deleteTask(taskId);
  }
});

document.querySelectorAll("[data-summary-close]")?.forEach((node) => {
  node.addEventListener("click", closeSummaryModal);
});

setLanguage(state.language);
loadTasks();
state.tasksPoller = window.setInterval(loadTasks, 3000);
