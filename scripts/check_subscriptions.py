#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config import CONFIG_PATH, DB_PATH, ConfigError, load_project_config  # noqa: E402
from backend.db import init_db  # noqa: E402
from backend.subscriptions import check_subscriptions_once  # noqa: E402


def make_api_task_creator(api_base_url: str):
    def create_task(payload: dict):
        with httpx.Client(timeout=20, trust_env=False) as client:
            response = client.post(
                f"{api_base_url.rstrip('/')}/api/tasks",
                json=payload,
            )
        response.raise_for_status()
        return response.json()["task"]

    return create_task


def ensure_app_is_running(api_base_url: str) -> None:
    with httpx.Client(timeout=5, trust_env=False) as client:
        response = client.get(f"{api_base_url.rstrip('/')}/api/health")
    response.raise_for_status()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check configured podcast subscriptions once.")
    parser.add_argument("--config-path", type=Path, default=CONFIG_PATH, help="YAML config path.")
    parser.add_argument("--db-path", type=Path, default=DB_PATH, help="SQLite database path.")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000", help="Running app base URL.")
    args = parser.parse_args(argv)

    try:
        config = load_project_config(args.config_path)
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    if not args.config_path.exists():
        print(f"configuration file not found: {args.config_path}", file=sys.stderr)
        print("copy config/podcast_notebook.example.yaml to config/podcast_notebook.yaml first", file=sys.stderr)
        return 2
    if not config.subscriptions.podcasts:
        print("no podcast subscriptions configured", file=sys.stderr)
        return 2

    init_db(args.db_path)
    print(f"using config: {args.config_path}")
    print(f"using database: {args.db_path}")
    print(f"using app api: {args.api_base_url}")
    print("mode: create tasks through the running app API, like clicking the frontend button")
    try:
        ensure_app_is_running(args.api_base_url)
    except httpx.HTTPError as exc:
        print(f"app api is not reachable: {exc}", file=sys.stderr)
        print("start the app first, for example: .venv/bin/uvicorn backend.app:create_app --factory --reload", file=sys.stderr)
        return 2

    result = check_subscriptions_once(
        config,
        args.db_path,
        create_task_func=make_api_task_creator(args.api_base_url),
        reporter=print,
    )
    print(
        "subscription check complete: "
        f"podcasts={len(config.subscriptions.podcasts)} "
        f"created={result.created_count} "
        f"skipped_existing={result.skipped_existing_count} "
        f"skipped_old={result.skipped_old_count} "
        f"skipped_missing_time={result.skipped_missing_time_count} "
        f"skipped_unmatched_podcast={result.skipped_unmatched_podcast_count} "
        f"skipped_incomplete={result.skipped_incomplete_count} "
        f"failed={len(result.failed_podcasts)}"
    )
    if result.created_tasks:
        print("created tasks:")
        for task in result.created_tasks:
            print(f"- {task['podcast_title']} | {task['episode_title']}")
    if result.failed_podcasts:
        print("failed podcasts:")
        for podcast_name, reason in result.failed_podcasts:
            print(f"- {podcast_name}: {reason}")
    return 1 if result.failed_podcasts else 0


if __name__ == "__main__":
    raise SystemExit(main())
