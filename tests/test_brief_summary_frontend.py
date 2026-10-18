import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest


def run_javascript(code):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is needed for frontend behavior checks")
    result = subprocess.run([node, "-e", code], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def source_function(name):
    source = Path("frontend/app.js").read_text(encoding="utf-8")
    return re.search(rf"(?:async )?function {name}\([^\n]*\) \{{.*?\n\}}", source, re.S).group()


def test_short_summary_is_default_full_summary_collapses_and_legacy_english_still_render():
    result = run_javascript("""
const state = {language: 'zh-CN'};
const renderMarkdown = value => `<p>${value}</p>`;
const escapeHtml = value => value;
const t = () => '长版总结';
""" + source_function("renderSummarize") + """
const file = {content: '长版', brief_content: '几句话'};
const chinese = renderSummarize(file);
const legacy = renderSummarize({content: '原长版'});
const briefOnly = renderSummarize({content: '', brief_content: '只有短版'});
state.language = 'en';
console.log(JSON.stringify({chinese, legacy, briefOnly, english: renderSummarize(file)}));
""")
    assert result["chinese"].startswith("<p>几句话</p>")
    assert '<details class="summary-detail">' in result["chinese"]
    assert "<summary>长版总结</summary>" in result["chinese"]
    assert "<p>长版</p>" in result["chinese"]
    assert " open" not in result["chinese"]
    assert result["legacy"] == "<p>原长版</p>"
    assert result["briefOnly"] == "<p>只有短版</p>"
    assert result["english"] == "<p>长版</p>"


def test_polling_invalidates_cached_summary_when_brief_arrives():
    result = run_javascript("""
const state = {tasks: [{id: 1, summarize: 'long.md', summarize_brief: ''}, {id: 2, summarize: 'old.md'}]};
const deleted = [];
const clearTaskFileCache = id => deleted.push(id);
const syncTaskFilterControls = () => {};
const syncTimeFilterOptions = () => {};
const syncFavoritesFilter = () => {};
const renderTasks = () => {};
const taskResults = {};
const fetchJson = async () => ({items: [{id: 1, summarize: 'long.md', summarize_brief: 'brief.md'}, {id: 2, summarize: 'old.md'}]});
""" + source_function("loadTasks") + """
loadTasks().then(() => console.log(JSON.stringify(deleted)));
""")
    assert result == [1]


@pytest.mark.parametrize("kind", ["brief", "detail"])
def test_generate_button_posts_selected_kind_and_clears_its_lock_after_language_switch(kind):
    result = run_javascript("""
const state = {language: 'zh-CN', taskDetails: new Map()};
const locks = [];
const setSummarizeLock = (...args) => locks.push(['set', ...args]);
const clearSummarizeLock = (...args) => locks.push(['clear', ...args]);
const setTaskPending = () => {};
const renderTasks = () => {};
const clearTaskFileCache = () => {};
const showToast = () => {};
const t = value => value;
const loadTasks = async () => {};
const highlightTask = () => {};
let body;
const fetchJson = async (url, options) => {
  body = JSON.parse(options.body);
  state.language = 'en';
  return {task: {id: 1}};
};
""" + source_function("generateSummarize") + f"""
generateSummarize({{id: 1}}, {json.dumps(kind)}).then(() => console.log(JSON.stringify({{body, locks}})));
""")
    assert result["body"] == {"lang": "zh-CN", "kind": kind}
    assert result["locks"] == [["set", 1, "zh-CN", kind], ["clear", 1, "zh-CN", kind]]


def test_chinese_card_has_independent_buttons_and_brief_alone_can_be_viewed():
    functions = "\n".join(source_function(name) for name in ("summaryVersions", "renderTask"))
    result = run_javascript("""
const state = {language: 'zh-CN', expandedTaskIds: new Set(), pendingActionTaskIds: new Set()};
const clearSummarizeLock = () => {};
const isSummarizeLocked = () => false;
const hasAudioDuration = () => true;
const escapeHtml = value => value;
const escapeAttribute = value => value;
const t = key => ({generateBriefSummary:'生成短版',generateFullSummary:'生成长版',viewSummarize:'查看总结'}[key] || key);
const statusTone = () => '';
const formatStatus = () => '';
const formatDate = () => '';
const formatAudioDurationMeta = () => '';
const formatStage = () => '';
const renderProgressRow = () => '';
const renderDetailBody = () => '';
const document = {createElement: () => ({dataset: {}, querySelector: () => null, querySelectorAll: () => []})};
""" + functions + """
const task = {id: 1, status:'completed',output_txt_path:'/transcript.txt'};
console.log(JSON.stringify({
  missing: renderTask(task).innerHTML,
  briefOnly: renderTask({...task, summarize_brief:'/brief.md'}).innerHTML,
  archived: renderTask({...task, status:'archived'}).innerHTML,
}));
""")
    assert 'data-summary-kind="brief"' in result["missing"]
    assert 'data-summary-kind="detail"' in result["missing"]
    assert "生成短版" in result["missing"] and "生成长版" in result["missing"]
    assert 'data-summary-kind="brief"' not in result["briefOnly"]
    assert 'data-summary-kind="detail"' in result["briefOnly"]
    assert "查看总结" in result["briefOnly"]
    assert 'data-action="generate-summarize"' not in result["archived"]


def test_existing_short_summary_only_clears_short_lock():
    functions = "\n".join(source_function(name) for name in (
        "summarizeLockKey", "isSummarizeLocked", "setSummarizeLock", "clearSummarizeLock", "summaryVersions",
    ))
    result = run_javascript("""
const state = {language: 'zh-CN'};
const SUMMARIZE_LOCK_TTL_MS = 600000;
const storage = new Map();
const localStorage = {getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key)};
""" + functions + """
setSummarizeLock(1, 'zh-CN', 'brief');
setSummarizeLock(1, 'zh-CN', 'detail');
const versions = summaryVersions({id: 1, summarize_brief: '/brief.md'});
console.log(JSON.stringify({versions, briefLocked: isSummarizeLocked(1, 'zh-CN', 'brief'), detailLocked: isSummarizeLocked(1, 'zh-CN', 'detail')}));
""")
    assert result["briefLocked"] is False
    assert result["detailLocked"] is True
    assert result["versions"][0]["exists"] is True
    assert result["versions"][1]["locked"] is True
