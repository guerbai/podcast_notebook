from __future__ import annotations

import calendar
from concurrent.futures import Executor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import struct_time
from typing import Any, Callable

from backend.config import ProjectConfig
from backend.db import create_task, find_task_by_episode
from backend.podcast_search import search_podcasts
from backend.rss import fetch_episodes_strict
from backend.tasks import TaskCreate, enqueue_task


@dataclass(slots=True)
class SubscriptionCheckResult:
    created_tasks: list[dict[str, Any]] = field(default_factory=list)
    skipped_existing_count: int = 0
    skipped_old_count: int = 0
    skipped_missing_time_count: int = 0
    skipped_unmatched_podcast_count: int = 0
    skipped_incomplete_count: int = 0
    failed_podcasts: list[tuple[str, str]] = field(default_factory=list)

    @property
    def created_count(self) -> int:
        return len(self.created_tasks)


SearchPodcasts = Callable[[str], list[dict[str, Any]]]
FetchEpisodes = Callable[[str], list[dict[str, Any]]]
Reporter = Callable[[str], None]
CreateTask = Callable[[dict[str, Any]], dict[str, Any]]


def check_subscriptions_once(
    config: ProjectConfig,
    db_path: str | Path,
    *,
    now: datetime | None = None,
    executor: Executor | None = None,
    reporter: Reporter | None = None,
    create_task_func: CreateTask | None = None,
    search_podcasts_func: SearchPodcasts = search_podcasts,
    fetch_episodes_func: FetchEpisodes = fetch_episodes_strict,
) -> SubscriptionCheckResult:
    checked_at = now or datetime.now().astimezone()
    result = SubscriptionCheckResult()
    _report(reporter, f"loaded subscriptions: {', '.join(config.subscriptions.podcasts)}")

    for index, podcast_name in enumerate(config.subscriptions.podcasts):
        try:
            if index > 0:
                _report(reporter, "----------------------")
            _report(reporter, f"processing podcast: {podcast_name}")
            _report(reporter, f"searching podcast: {podcast_name}")
            try:
                candidates = search_podcasts_func(podcast_name)
            except Exception as exc:
                _report(reporter, f"apple_search_failed: {podcast_name} reason={exc}")
                result.failed_podcasts.append((podcast_name, f"apple_search_failed: {exc}"))
                continue
            podcast = _find_exact_podcast_match(podcast_name, candidates)
            if podcast is None:
                _report(reporter, f"podcast_match_not_found: {podcast_name}")
                result.skipped_unmatched_podcast_count += 1
                continue
            _report(reporter, f"matched podcast: {podcast.get('title', podcast_name)}")
            _check_podcast_feed(
                podcast_name,
                podcast,
                db_path,
                checked_at,
                executor,
                fetch_episodes_func,
                result,
                reporter,
                create_task_func,
            )
        except Exception as exc:
            _report(reporter, f"failed podcast: {podcast_name} reason={exc}")
            result.failed_podcasts.append((podcast_name, str(exc)))

    return result


def _find_exact_podcast_match(podcast_name: str, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    for candidate in candidates:
        if str(candidate.get("title", "")).strip() == podcast_name:
            return candidate
    return None


def _check_podcast_feed(
    podcast_name: str,
    podcast: dict[str, Any],
    db_path: str | Path,
    checked_at: datetime,
    executor: Executor | None,
    fetch_episodes_func: FetchEpisodes,
    result: SubscriptionCheckResult,
    reporter: Reporter | None,
    create_task_func: CreateTask | None,
) -> None:
    rss_url = str(podcast.get("rss_url", "")).strip()
    if not rss_url:
        _report(reporter, f"missing rss url: {podcast_name}")
        result.skipped_unmatched_podcast_count += 1
        return

    _report(reporter, f"fetching rss: {rss_url}")
    try:
        episodes = fetch_episodes_func(rss_url)
    except Exception as exc:
        _report(reporter, f"rss_fetch_failed: {podcast_name} rss={rss_url} reason={exc}")
        result.failed_podcasts.append((podcast_name, f"rss_fetch_failed: {exc}"))
        return
    _report(reporter, f"fetched episodes: {podcast_name} count={len(episodes)}")

    for episode in episodes:
        title = str(episode.get("title", "")).strip()
        audio_url = str(episode.get("audio_url", "")).strip()
        if not title or not audio_url:
            result.skipped_incomplete_count += 1
            continue
        if not _is_recent_publish(episode, checked_at):
            if episode.get("published_parsed"):
                result.skipped_old_count += 1
            else:
                result.skipped_missing_time_count += 1
            continue
        if find_task_by_episode(podcast_name, title, db_path) is not None:
            result.skipped_existing_count += 1
            continue

        payload = {
            "podcast_title": podcast_name,
            "rss_url": rss_url,
            "episode_title": title,
            "episode_guid": episode.get("guid"),
            "audio_url": audio_url,
            "shownotes": episode.get("shownotes", ""),
        }
        if create_task_func is not None:
            task = create_task_func(payload)
        elif executor is None:
            task = create_task(payload, db_path)
        else:
            task = enqueue_task(TaskCreate(**payload), db_path, executor)["task"]
        result.created_tasks.append(task)
        _report(reporter, f"created task: {podcast_name} | {title}")


def _is_recent_publish(episode: dict[str, Any], checked_at: datetime) -> bool:
    published = _published_datetime(episode.get("published_parsed"))
    if published is None:
        return False
    checked_date = checked_at.astimezone().date()
    first_recent_date = checked_date - timedelta(days=2)
    published_date = published.astimezone().date()
    return first_recent_date <= published_date <= checked_date


def _published_datetime(value: Any) -> datetime | None:
    if isinstance(value, struct_time):
        return datetime.fromtimestamp(calendar.timegm(value), tz=timezone.utc).astimezone()
    if isinstance(value, tuple) and len(value) >= 6:
        return datetime.fromtimestamp(calendar.timegm(value), tz=timezone.utc).astimezone()
    return None


def _report(reporter: Reporter | None, message: str) -> None:
    if reporter is not None:
        reporter(message)
