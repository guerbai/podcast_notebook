const state = {
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
  tasks: [],
  taskFilters: {
    podcastTitle: "",
    status: "",
  },
};

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
const summaryTitle = document.querySelector("#summary-title");

const STATUS_LABELS = {
  queued: "排队中",
  running: "执行中",
  cancelling: "停止中",
  completed: "已完成",
  failed: "失败",
};

const STAGE_LABELS = {
  queued: "等待开始",
  downloading_audio: "下载音频中",
  transcribing: "转写中",
  finalizing: "正在收尾",
  completed: "已完成",
  failed: "执行失败",
  cancelled: "已取消",
};

const TOAST_MESSAGES = {
  existing: "已定位到现有任务。",
};

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
    throw new Error(payload?.detail || payload?.message || `请求失败：${response.status}`);
  }
  return payload;
}

function renderList(container, items, renderItem, emptyMessage = "还没有找到任何内容。") {
  container.innerHTML = "";
  if (!items.length) {
    container.innerHTML = `<p class="empty">${emptyMessage}</p>`;
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
}

function closeSummaryModal() {
  summaryModal?.setAttribute("hidden", "hidden");
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
  state.taskFiles.delete(`summarize:${taskId}`);
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
  return taskListStatus(task) === "completed" ? "已完成" : "进行中";
}

function formatStage(task) {
  return STAGE_LABELS[task.progress_stage] || task.progress_stage || "未知阶段";
}

function formatDate(value) {
  if (!value) return "未记录时间";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
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
  const titles = [...new Set(tasks.map((task) => task.podcast_title).filter(Boolean))].sort((a, b) => a.localeCompare(b, "zh-CN"));
  if (state.taskFilters.podcastTitle && !titles.includes(state.taskFilters.podcastTitle)) {
    state.taskFilters.podcastTitle = "";
  }
  const currentValue = state.taskFilters.podcastTitle;
  taskPodcastFilter.innerHTML = [
    '<wa-option value="">播客名</wa-option>',
    ...titles.map((title) => `<wa-option value="${escapeAttribute(title)}">${escapeHtml(title)}</wa-option>`),
  ].join("");
  taskPodcastFilter.value = currentValue;
}

function renderTasks() {
  renderList(taskResults, filteredTasks(), renderTask, "当前筛选条件下没有任务。");
}

async function searchPodcasts() {
  const q = podcastQueryInput.value.trim();
  if (!q) return;
  podcastResults.innerHTML = '<p class="empty">正在搜索播客…</p>';
  try {
    const data = await fetchJson(`/api/search/podcasts?q=${encodeURIComponent(q)}`);
    renderList(podcastResults, data.items || [], renderPodcastResult);
  } catch (error) {
    podcastResults.innerHTML = `<p class="empty">${error.message}</p>`;
    showToast(error.message, "error");
  }
}

function renderPodcastResult(item) {
  const button = document.createElement("button");
  button.className = "list-item podcast-result";
  button.type = "button";
  button.innerHTML = `
    <span class="kicker">播客</span>
    <strong>${item.title}</strong>
    <span>${item.author || item.rss_url}</span>
  `;
  button.addEventListener("click", () => {
    state.selectedPodcast = item;
    selectedPodcastLabel.textContent = `当前已选择：${item.title}`;
    loadRecentEpisodes();
    showToast(`已切换到《${item.title}》`, "info");
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
    return '<p class="empty">暂无内容。</p>';
  }
  return blocks
    .map((block) => `<p>${escapeHtml(block).replaceAll("\n", "<br>")}</p>`)
    .join("");
}

async function loadRecentEpisodes() {
  if (!state.selectedPodcast) {
    episodeResults.innerHTML = '<p class="empty">请选择一个播客。</p>';
    return;
  }
  episodeSubhead.textContent = "正在加载最近 10 期…";
  episodeResults.innerHTML = '<p class="empty">正在加载最近 10 期…</p>';
  try {
    const params = new URLSearchParams({
      rss_url: state.selectedPodcast.rss_url,
      q: "",
    });
    const data = await fetchJson(`/api/search/episodes?${params.toString()}`);
    const recentItems = (data.items || []).slice(0, 10);
    episodeSubhead.textContent = "最近 10 期";
    renderList(
      episodeResults,
      recentItems,
      renderEpisodeResult,
      "这个播客暂时没有可用的单集记录。",
    );
  } catch (error) {
    episodeSubhead.textContent = error.message;
    episodeResults.innerHTML = `<p class="empty">${error.message}</p>`;
    showToast(error.message, "error");
  }
}

async function searchEpisodes() {
  if (!state.selectedPodcast) {
    episodeResults.innerHTML = '<p class="empty">请选择一个播客。</p>';
    return;
  }
  const q = episodeQueryInput.value.trim();
  if (!q) {
    await loadRecentEpisodes();
    return;
  }
  episodeSubhead.textContent = `搜索结果：${q}`;
  episodeResults.innerHTML = '<p class="empty">正在搜索单集…</p>';
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
      "当前条件下还没有找到匹配单集。",
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
    <span class="kicker">单集</span>
    <strong>${item.title}</strong>
    <span>${formatDate(item.published || "")}</span>
  `;

  const actions = document.createElement("div");
  actions.className = "episode-card__actions";
  const action = document.createElement("button");
  action.type = "button";
  action.className = "secondary-button";
  action.textContent = state.isCreatingTask ? "正在创建…" : "创建转写任务";
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
  button.textContent = "正在创建…";

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
        shownotes: episode.summary || "",
      }),
    });
    await loadTasks();
    highlightTask(result.task.id);
    scrollToTask(result.task.id);
    state.expandedTaskIds.add(result.task.id);
    const message = result.result === "existing" ? TOAST_MESSAGES.existing : result.message;
    showToast(message, result.result === "existing" ? "warning" : "success");
    await loadTasks();
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    state.isCreatingTask = false;
    button.disabled = false;
    button.textContent = "创建转写任务";
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
      showToast("任务已删除。", "success");
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
    state.expandedTaskIds.add(newTaskId);
    showToast(result.message, "success");
    await loadTasks();
    highlightTask(newTaskId);
    scrollToTask(newTaskId);
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    setTaskPending(taskId, false);
  }
}

async function openTaskSummary(task) {
  try {
    let summary = state.summaries.get(task.id);
    if (!summary) {
      summary = await fetchJson(`/api/tasks/${task.id}/summary`);
      state.summaries.set(task.id, summary);
    }
    summaryTitle.textContent = summary.title;
    summaryContent.innerHTML = renderMarkdown(summary.markdown);
    openSummaryModal();
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function openTaskFile(task, type) {
  const labels = {
    shownotes: "Shownotes",
    summarize: "Summarize",
  };
  try {
    const cacheKey = `${type}:${task.id}`;
    let file = state.taskFiles.get(cacheKey);
    if (!file) {
      file = await fetchJson(TASK_FILE_ENDPOINTS[type](task.id));
      state.taskFiles.set(cacheKey, file);
    }
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
  const summary = task.error_message || task.output_txt_path || task.audio_file_path || "暂时还没有生成任何文件。";
  const taskStatus = taskListStatus(task);

  article.innerHTML = `
    <div class="ledger-entry__frame">
      <div class="ledger-title-group">
        <span class="kicker">任务 ${task.id}</span>
        <strong>${task.episode_title}</strong>
        <p>${task.podcast_title}</p>
      </div>

      <div class="ledger-side">
        <div class="ledger-status-row">
          <span class="status ${statusTone(task)}">${formatStatus(task)}</span>
          <button type="button" class="icon-button" data-action="restart" title="重新开始" aria-label="重新开始" ${isPending ? "disabled" : ""}>↻</button>
          <button type="button" class="icon-button icon-button--danger" data-action="delete" title="删除" aria-label="删除" ${isPending ? "disabled" : ""}>×</button>
        </div>
        <div class="ledger-side__time">${formatDate(task.created_at)}</div>
      </div>
    </div>

    <div class="ledger-meta">
      <span>列表状态：${taskStatus === "completed" ? "已完成" : "进行中"}</span>
      <span>阶段：${formatStage(task)}</span>
      <span>下载进度：${progressValue(task.download_percent).toFixed(1)}%</span>
      <span>转写进度：${progressValue(task.transcription_percent).toFixed(1)}%</span>
      <span>Summarize：${task.summarize ? "已生成" : "未生成"}</span>
    </div>

    <div class="ledger-progress">
      ${renderProgressRow("下载进度", task.download_percent, "download")}
      ${renderProgressRow("转写进度", task.transcription_percent, "transcription")}
    </div>

    <p class="ledger-summary">${summary}</p>

    <div class="ledger-actions">
      <button type="button" class="ghost-button" data-action="toggle">${isExpanded ? "收起详情" : "查看详情"}</button>
      ${task.summary_md_path ? '<button type="button" class="ghost-button" data-action="summary">查看总结</button>' : ""}
      ${task.shownotes ? '<button type="button" class="ghost-button" data-action="shownotes">查看 Shownotes</button>' : ""}
      ${task.summarize ? '<button type="button" class="ghost-button" data-action="summarize">查看 Summarize</button>' : ""}
    </div>

    <section class="ledger-detail-panel ${isExpanded ? "is-open" : ""}">
      <div class="detail-body">${renderDetailBody(task.id)}</div>
    </section>
  `;

  article.querySelector('[data-action="toggle"]')?.addEventListener("click", () => toggleTaskDetail(task.id));
  article.querySelector('[data-action="summary"]')?.addEventListener("click", () => openTaskSummary(task));
  article.querySelector('[data-action="shownotes"]')?.addEventListener("click", () => openTaskFile(task, "shownotes"));
  article.querySelector('[data-action="summarize"]')?.addEventListener("click", () => openTaskFile(task, "summarize"));
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
    return '<p class="empty">正在加载详情…</p>';
  }

  const events = (detail.events || [])
    .slice(-6)
    .map((event) => `<li><span>${formatDate(event.created_at)}</span><strong>${event.message}</strong></li>`)
    .join("");

  return `
    <div class="detail-grid">
      <div>
        <p class="detail-label">文件</p>
        <p>${detail.output_txt_path || "转写全文尚未生成。"}</p>
        <p>${detail.audio_file_path || "当前没有保留音频文件。"}</p>
      </div>
      <div>
        <p class="detail-label">备注</p>
        <p>${detail.error_message || "当前没有异常信息。"}</p>
      </div>
      <div>
        <p class="detail-label">Shownotes 文件</p>
        <p>${escapeHtml(detail.shownotes || "当前没有记录 shownotes。")}</p>
      </div>
      <div>
        <p class="detail-label">Summarize 文件</p>
        <p>${escapeHtml(detail.summarize || "当前没有记录 summarize。")}</p>
      </div>
    </div>
    <div class="detail-log">
      <p class="detail-label">最近日志</p>
      <ul>${events || "<li><strong>还没有记录到任何事件。</strong></li>"}</ul>
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

loadTasks();
state.tasksPoller = window.setInterval(loadTasks, 3000);
