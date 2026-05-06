#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config import DB_PATH  # noqa: E402
from backend.maintenance import MaintenanceResult, maintain_tasks  # noqa: E402


def make_api_task_restarter(api_base_url: str):
    def restart_task(task_id: int):
        with httpx.Client(timeout=20, trust_env=False) as client:
            response = client.post(f"{api_base_url.rstrip('/')}/api/tasks/{task_id}/restart")
        response.raise_for_status()
        return response.json()

    return restart_task


def ensure_app_is_running(api_base_url: str) -> None:
    with httpx.Client(timeout=5, trust_env=False) as client:
        response = client.get(f"{api_base_url.rstrip('/')}/api/health")
    response.raise_for_status()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Maintain podcast notebook tasks for cron.")
    parser.add_argument("--db-path", type=Path, default=DB_PATH, help="SQLite database path.")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000", help="Running app base URL.")
    args = parser.parse_args(argv)

    print(f"using database: {args.db_path}")
    print(f"using app api: {args.api_base_url}")
    print("mode: restart stale tasks through the running app API, like clicking retry in the frontend")
    try:
        ensure_app_is_running(args.api_base_url)
    except httpx.HTTPError as exc:
        print(f"app api is not reachable: {exc}", file=sys.stderr)
        print("start the app first, for example: .venv/bin/uvicorn backend.app:create_app --factory --reload", file=sys.stderr)
        return 2

    result = maintain_tasks(
        db_path=args.db_path,
        restart_task_func=make_api_task_restarter(args.api_base_url),
    )
    print(
        "maintenance complete: "
        f"restarted={len(result.restarted_task_ids)} "
        f"deleted_audio={len(result.deleted_audio_paths)}"
    )
    if result.restarted_task_ids:
        print(f"restarted task ids: {', '.join(str(task_id) for task_id in result.restarted_task_ids)}")
    if result.replacement_task_ids:
        print(f"replacement task ids: {', '.join(str(task_id) for task_id in result.replacement_task_ids)}")
    if result.deleted_audio_paths:
        print("deleted audio files:")
        for path in result.deleted_audio_paths:
            print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
