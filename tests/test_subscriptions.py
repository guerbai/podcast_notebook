from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from backend.config import ProjectConfig, SubscriptionsConfig
from backend.db import create_task, init_db, list_tasks
from backend.subscriptions import SubscriptionCheckResult, check_subscriptions_once


def _episode(title: str, published_at: datetime | None):
    return {
        "title": title,
        "guid": title,
        "audio_url": f"https://example.com/{title}.mp3",
        "published": published_at.isoformat() if published_at else "",
        "published_parsed": published_at.timetuple() if published_at else None,
        "shownotes": f"{title} shownotes",
    }


def test_check_subscriptions_creates_tasks_for_recent_podcast_matches(tmp_path):
    db_path = tmp_path / "app.db"
    init_db(db_path)
    now = datetime(2026, 5, 6, 10, 0, 0)
    config = ProjectConfig(
        subscriptions=SubscriptionsConfig(
            podcasts=["商业就是这样", "半拿铁"],
        )
    )

    def search_podcasts(query: str):
        if query == "商业就是这样":
            return [{"title": "商业就是这样", "rss_url": "https://example.com/business.xml"}]
        if query == "半拿铁":
            return [{"title": "半拿铁 | 商业沉浮录", "rss_url": "https://example.com/coffee.xml"}]
        return []

    def fetch_episodes(rss_url: str):
        assert rss_url == "https://example.com/business.xml"
        return [
            _episode("今日新节目", now),
            _episode("昨天旧节目", now - timedelta(days=1)),
            _episode("缺少发布时间", None),
        ]

    result = check_subscriptions_once(
        config,
        db_path,
        now=now,
        search_podcasts_func=search_podcasts,
        fetch_episodes_func=fetch_episodes,
    )

    tasks = list_tasks(db_path)
    assert [task["episode_title"] for task in tasks] == ["昨天旧节目", "今日新节目"]
    assert tasks[0]["podcast_title"] == "商业就是这样"
    assert result.created_count == 2
    assert result.skipped_old_count == 0
    assert result.skipped_missing_time_count == 1
    assert result.skipped_unmatched_podcast_count == 1


def test_check_subscriptions_creates_tasks_for_recent_three_local_dates(tmp_path):
    db_path = tmp_path / "app.db"
    init_db(db_path)
    now = datetime(2026, 5, 6, 10, 0, 0)
    config = ProjectConfig(subscriptions=SubscriptionsConfig(podcasts=["商业就是这样"]))

    result = check_subscriptions_once(
        config,
        db_path,
        now=now,
        search_podcasts_func=lambda query: [
            {"title": "商业就是这样", "rss_url": "https://example.com/business.xml"}
        ],
        fetch_episodes_func=lambda rss_url: [
            _episode("今天节目", now),
            _episode("昨天节目", now - timedelta(days=1)),
            _episode("前天节目", now - timedelta(days=2)),
            _episode("三天前旧节目", now - timedelta(days=3)),
        ],
    )

    tasks = list_tasks(db_path)
    assert [task["episode_title"] for task in tasks] == ["前天节目", "昨天节目", "今天节目"]
    assert result.created_count == 3
    assert result.skipped_old_count == 1


def test_check_subscriptions_skips_existing_episode_tasks(tmp_path):
    db_path = tmp_path / "app.db"
    init_db(db_path)
    now = datetime(2026, 5, 6, 10, 0, 0)
    create_task(
        {
            "podcast_title": "商业就是这样",
            "rss_url": "https://example.com/business.xml",
            "episode_title": "今日新节目",
            "audio_url": "https://example.com/audio.mp3",
        },
        db_path,
    )
    config = ProjectConfig(subscriptions=SubscriptionsConfig(podcasts=["商业就是这样"]))

    result = check_subscriptions_once(
        config,
        db_path,
        now=now,
        search_podcasts_func=lambda query: [
            {"title": "商业就是这样", "rss_url": "https://example.com/business.xml"}
        ],
        fetch_episodes_func=lambda rss_url: [_episode("今日新节目", now)],
    )

    tasks = list_tasks(db_path)
    assert len(tasks) == 1
    assert result.created_count == 0
    assert result.skipped_existing_count == 1


def test_check_subscriptions_logs_apple_search_failures(tmp_path):
    db_path = tmp_path / "app.db"
    init_db(db_path)
    messages = []

    def search_podcasts(query: str):
        raise RuntimeError("itunes timeout")

    result = check_subscriptions_once(
        ProjectConfig(subscriptions=SubscriptionsConfig(podcasts=["商业就是这样"])),
        db_path,
        reporter=messages.append,
        search_podcasts_func=search_podcasts,
    )

    assert result.failed_podcasts == [("商业就是这样", "apple_search_failed: itunes timeout")]
    assert "apple_search_failed: 商业就是这样 reason=itunes timeout" in messages


def test_check_subscriptions_logs_missing_exact_podcast_match(tmp_path):
    db_path = tmp_path / "app.db"
    init_db(db_path)
    messages = []

    result = check_subscriptions_once(
        ProjectConfig(subscriptions=SubscriptionsConfig(podcasts=["商业就是这样"])),
        db_path,
        reporter=messages.append,
        search_podcasts_func=lambda query: [
            {"title": "商业就是这样 Plus", "rss_url": "https://example.com/business.xml"}
        ],
    )

    assert result.failed_podcasts == []
    assert result.skipped_unmatched_podcast_count == 1
    assert "podcast_match_not_found: 商业就是这样" in messages


def test_check_subscriptions_logs_rss_fetch_failures(tmp_path):
    db_path = tmp_path / "app.db"
    init_db(db_path)
    messages = []

    def fetch_episodes(rss_url: str):
        raise RuntimeError("rss 503")

    result = check_subscriptions_once(
        ProjectConfig(subscriptions=SubscriptionsConfig(podcasts=["商业就是这样"])),
        db_path,
        reporter=messages.append,
        search_podcasts_func=lambda query: [
            {"title": "商业就是这样", "rss_url": "https://example.com/business.xml"}
        ],
        fetch_episodes_func=fetch_episodes,
    )

    assert result.failed_podcasts == [("商业就是这样", "rss_fetch_failed: rss 503")]
    assert "rss_fetch_failed: 商业就是这样 rss=https://example.com/business.xml reason=rss 503" in messages


def test_check_subscriptions_separates_podcast_log_blocks(tmp_path):
    db_path = tmp_path / "app.db"
    init_db(db_path)
    messages = []

    check_subscriptions_once(
        ProjectConfig(subscriptions=SubscriptionsConfig(podcasts=["商业就是这样", "忽左忽右"])),
        db_path,
        reporter=messages.append,
        search_podcasts_func=lambda query: [
            {"title": query, "rss_url": f"https://example.com/{query}.xml"}
        ],
        fetch_episodes_func=lambda rss_url: [],
    )

    assert messages == [
        "loaded subscriptions: 商业就是这样, 忽左忽右",
        "processing podcast: 商业就是这样",
        "searching podcast: 商业就是这样",
        "matched podcast: 商业就是这样",
        "fetching rss: https://example.com/商业就是这样.xml",
        "fetched episodes: 商业就是这样 count=0",
        "----------------------",
        "processing podcast: 忽左忽右",
        "searching podcast: 忽左忽右",
        "matched podcast: 忽左忽右",
        "fetching rss: https://example.com/忽左忽右.xml",
        "fetched episodes: 忽左忽右 count=0",
    ]


def test_check_subscriptions_reports_step_by_step_progress(tmp_path):
    db_path = tmp_path / "app.db"
    init_db(db_path)
    now = datetime(2026, 5, 6, 10, 0, 0)
    create_task(
        {
            "podcast_title": "商业就是这样",
            "rss_url": "https://example.com/business.xml",
            "episode_title": "已有节目",
            "audio_url": "https://example.com/existing.mp3",
        },
        db_path,
    )
    messages = []

    check_subscriptions_once(
        ProjectConfig(subscriptions=SubscriptionsConfig(podcasts=["商业就是这样"])),
        db_path,
        now=now,
        reporter=messages.append,
        search_podcasts_func=lambda query: [
            {"title": "商业就是这样", "rss_url": "https://example.com/business.xml"}
        ],
        fetch_episodes_func=lambda rss_url: [
            _episode("已有节目", now),
            _episode("昨天旧节目", now - timedelta(days=1)),
            _episode("缺少发布时间", None),
            _episode("今日新节目", now),
        ],
    )

    assert messages == [
        "loaded subscriptions: 商业就是这样",
        "processing podcast: 商业就是这样",
        "searching podcast: 商业就是这样",
        "matched podcast: 商业就是这样",
        "fetching rss: https://example.com/business.xml",
        "fetched episodes: 商业就是这样 count=4",
        "created task: 商业就是这样 | 昨天旧节目",
        "created task: 商业就是这样 | 今日新节目",
    ]


def test_subscription_script_creates_tasks_through_app_api(tmp_path, monkeypatch, capsys):
    from scripts import check_subscriptions as script

    config_path = tmp_path / "podcast_notebook.yaml"
    db_path = tmp_path / "app.db"
    config_path.write_text(
        """
subscriptions:
  podcasts:
    - 商业就是这样
""".strip(),
        encoding="utf-8",
    )
    seen = {}
    fake_task_creator = object()

    def fake_check_subscriptions_once(config, received_db_path, **kwargs):
        seen["podcasts"] = config.subscriptions.podcasts
        seen["db_path"] = Path(received_db_path)
        seen["executor"] = kwargs.get("executor")
        seen["create_task_func"] = kwargs.get("create_task_func")
        return SubscriptionCheckResult()

    monkeypatch.setattr(script, "check_subscriptions_once", fake_check_subscriptions_once)
    monkeypatch.setattr(script, "make_api_task_creator", lambda api_base_url: fake_task_creator)
    monkeypatch.setattr(script, "ensure_app_is_running", lambda api_base_url: None)

    exit_code = script.main(["--config-path", str(config_path), "--db-path", str(db_path)])

    assert exit_code == 0
    assert seen["podcasts"] == ["商业就是这样"]
    assert seen["db_path"] == db_path
    assert seen["executor"] is None
    assert seen["create_task_func"] is fake_task_creator
    assert "mode: create tasks through the running app API, like clicking the frontend button" in capsys.readouterr().out


def test_subscription_script_app_api_ignores_environment_proxy(monkeypatch):
    from scripts import check_subscriptions as script

    captured = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"task": {"id": 1}}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.append(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            return FakeResponse()

        def post(self, url, json):
            return FakeResponse()

    monkeypatch.setattr(script.httpx, "Client", FakeClient)

    script.ensure_app_is_running("http://127.0.0.1:8000")
    script.make_api_task_creator("http://127.0.0.1:8000")({"podcast_title": "商业就是这样"})

    assert captured == [
        {"timeout": 5, "trust_env": False},
        {"timeout": 20, "trust_env": False},
    ]
