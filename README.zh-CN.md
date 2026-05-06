# Podcast Notebook / 播客笔记本

<p align="center">
  <img src="frontend/assets/logo.svg" width="96" alt="Podcast Notebook logo" />
</p>

播客笔记本是一个本地优先的 Web 应用，用来把播客单集变成本地全文稿、单集介绍和可复用的 Markdown 总结。

[English README](README.md)

## 截图

![播客笔记本桌面端界面](docs/assets/podcast-notebook-zh-CN.png)

## 为什么需要它

播客笔记本主要解决播客收听者的常见痛点：

- 关注的播客很多，现实中听不完，而 shownotes 往往信息不足，无法判断某一期是否值得投入时间。
- 有些单集干货很多，很值得做笔记，但节目时间长，手动听、暂停、回退、记录的效率很低。

这个应用会把单集变成可搜索的本地全文稿、清理后的单集介绍和可复用总结，让你更高效地筛选、排序、回看和写笔记。

它提供一个小型本地播客研究工作台：

- 通过 Apple Podcasts / iTunes 搜索播客
- 从 RSS 中选择具体单集
- 把单集音频下载到本地
- 使用 `faster-whisper` 本地转写
- 用 SQLite 保存任务历史、进度、事件和文件路径
- 把清理后的单集介绍和生成的 Markdown 总结关联到同一条任务
- 可选使用 OpenAI-compatible LLM 接口生成中文或英文总结

它更适合个人资料库和研究流程，不是面向多用户的托管服务。

## 工作流

```text
搜索播客 -> 选择单集 -> 创建任务
      -> 下载音频 -> 本地转写 -> 查看全文稿
      -> 生成总结 -> 文件继续关联在任务上
```

浏览器界面也按这个流程组织：播客搜索、单集选择、任务归档，并展示下载和转写进度。

## 功能

- 通过公开 iTunes Search API 搜索播客。
- 读取 RSS 单集，并带有六小时内存缓存。
- 下载音频并追踪下载进度。
- 通过 `faster-whisper` 在本地 CPU 转写。
- 分开展示下载进度和转写进度。
- 用 SQLite 保存任务历史和事件日志。
- 按 `播客名 + 单集名` 防止重复任务。
- 支持删除和重新开始任务，运行中任务会先协作取消。
- 本地保存音频、全文稿、单集介绍和总结文件。
- 支持中文 / 英文界面切换。
- 可选通过 OpenAI-compatible API key 或项目 agent skill 生成 Markdown 总结。

## 环境要求

- Python 3.10+
- macOS 或 Linux
- 搜索播客、读取 RSS、下载音频、下载模型和可选 LLM 总结需要网络访问
- 需要足够磁盘空间保存音频、全文稿和 Whisper 模型文件

bootstrap 脚本会创建项目虚拟环境和本地运行目录。

## 快速开始

```bash
bash scripts/bootstrap_runtime.sh
```

如果默认 `python3` 低于 3.10，可以显式指定新版 Python：

```bash
PYTHON_BIN=/opt/homebrew/bin/python3.12 bash scripts/bootstrap_runtime.sh
```

本地启动应用：

```bash
.venv/bin/uvicorn backend.app:create_app --factory --reload
```

打开：

```text
http://127.0.0.1:8000
```

第一次转写可能会更慢，因为 Whisper 模型需要先下载到 `data/models/`。

## 局域网访问

如果想从同一网络里的另一台设备打开应用：

```bash
.venv/bin/uvicorn backend.app:create_app --factory --reload --host 0.0.0.0 --port 58049
```

在 macOS 上查看局域网 IP：

```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

然后打开：

```text
http://<your-lan-ip>:58049
```

## 总结生成

转写是本地完成的。总结生成是可选功能，项目支持两种方式。

### 方式一：在应用内使用 API key 生成

应用可以通过 OpenAI-compatible chat completions 接口生成总结。

推荐把模型配置写入项目私有配置文件：

```bash
cp config/podcast_notebook.example.yaml config/podcast_notebook.yaml
```

然后编辑 `config/podcast_notebook.yaml`：

```yaml
llm:
  api_key: "..."
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o-mini"
  timeout_seconds: 60
```

`config/podcast_notebook.yaml` 会被 git 忽略，适合保存本地 API key。

如果没有配置 API key，应用仍然可以搜索、下载、转写和查看已有文件。只是新的总结生成会返回配置错误。

### 方式二：使用 agent + 项目 skill 生成

也可以让 agent 使用项目内置 skill 来生成或修改总结：

```text
skills/podcast-task-summarize/SKILL.md
```

该 skill 的工作流会：

- 在 `data/db/podcast_notebook.db` 中定位准确任务
- 读取清理后的单集介绍和 ASR 全文稿
- 在 `data/summaries/` 下生成中文和英文 Markdown 总结
- 更新 `tasks.summarize` 和 `tasks.summarize_en`
- 验证应用能读取两份总结

## 订阅巡检

如果希望项目自动发现关注播客最近 3 天新发布的节目，可以在私有配置里维护完整播客名：

```yaml
subscriptions:
  podcasts:
    - "商业就是这样"
    - "半拿铁 | 商业沉浮录"
```

脚本会用完整播客名搜索播客，只接受名称全匹配的结果。没有全匹配时会跳过并提示检查配置名称。

该脚本会通过正在运行的本地 Web 服务创建任务，效果等同于在前端点击创建任务：任务会进入现有下载/转写流程，但脚本不会等待下载或转写完成。

先启动应用：

```bash
.venv/bin/uvicorn backend.app:create_app --factory --reload
```

手动检查一次：

```bash
.venv/bin/python scripts/check_subscriptions.py
```

这个脚本也可以配到 crontab 中执行，见下面的自动化脚本说明。

新内容判断口径：

- RSS 条目发布时间按本机时区判断在最近 3 个自然日内（含当天）
- 本地任务库中不存在相同 `podcast_title + episode_title`
- 条目有标题和音频地址

## 本地数据目录

运行时文件都保存在仓库内，并且会被 git 忽略。

| 路径 | 用途 |
| --- | --- |
| `data/db/` | SQLite 数据库 |
| `data/downloads/` | 下载的单集音频 |
| `data/transcripts/` | 全文稿 `.txt` 文件 |
| `data/shownotes/` | 清理后的单集介绍 |
| `data/summaries/` | 生成的 Markdown 总结 |
| `data/models/` | Hugging Face / faster-whisper 模型缓存 |

## 开发

安装运行依赖：

```bash
bash scripts/bootstrap_runtime.sh
```

运行测试：

```bash
.venv/bin/pytest -v
```

运行维护脚本：

```bash
.venv/bin/python scripts/maintain_tasks.py
```

项目里有两个适合 crontab 调度的脚本：

- `scripts/check_subscriptions.py` 会检查配置里的播客订阅，并通过正在运行的本地 Web 服务为新单集创建任务。
- `scripts/maintain_tasks.py` 会通过正在运行的本地 Web 服务重启超时任务，效果等同于在前端点击重试；脚本不会等待下载或转写完成。它还会删除总结生成超过 24 小时的任务音频。

可以配到 crontab 中执行。把 `<schedule>` 替换成你需要的执行时间：

```cron
<schedule> cd /path/to/podcast_notebook && .venv/bin/python scripts/check_subscriptions.py >> /tmp/podcast_notebook_logs/check_subscriptions.log 2>&1
<schedule> cd /path/to/podcast_notebook && .venv/bin/python scripts/maintain_tasks.py >> /tmp/podcast_notebook_logs/maintain_tasks.log 2>&1
```

## 项目结构

```text
backend/
  app.py             FastAPI 应用和 HTTP 路由
  podcast_search.py  iTunes 播客搜索
  rss.py             RSS 获取和单集标准化
  downloads.py       音频下载工具
  transcription.py   faster-whisper 转写
  summarizer.py      OpenAI-compatible 总结生成
  tasks.py           任务生命周期编排
  db.py              SQLite schema 和持久化

frontend/
  index.html         浏览器 UI 外壳
  app.js             UI 状态、API 调用、渲染和 i18n
  styles.css         应用样式
  assets/            Logo 和图标资源

scripts/
  bootstrap_runtime.sh
  check_subscriptions.py
  maintain_tasks.py

tests/
  覆盖后端行为、API 路由、前端文案和任务流程的 pytest 测试
```

## 常见问题

### 第一次转写很慢

第一次使用时会下载模型，并缓存到 `data/models/`。长播客在 CPU 上转写也会比较慢。

### 播客搜索没有结果

应用使用公开 iTunes Search API。先检查网络，再尝试输入准确的播客名称。

### 单集搜索没有结果

有些 RSS feed 不提供音频 enclosure，或者元数据结构不常见。应用只会列出同时有标题和音频 URL 的条目。

### 总结生成失败

检查 `config/podcast_notebook.yaml` 里的 `llm` 配置。搜索、下载和转写不依赖总结配置。

### 局域网访问失败

启动 uvicorn 时需要加 `--host 0.0.0.0`，访问时使用机器的局域网 IP，并检查本机防火墙设置。

## License

MIT License。详见 [LICENSE](LICENSE)。
