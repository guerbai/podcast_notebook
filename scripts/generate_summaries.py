"""Fill missing Chinese podcast summaries in one bounded, cron-friendly run."""
from __future__ import annotations

import argparse
import fcntl
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.codex_summaries import (
    CodexSummaryClient, HUMANIZER_SKILL, SUMMARY_FIELDS, generate_task_summary, needs_summary,
)
from backend.config import DB_PATH
from backend.db import init_db, list_tasks


MIN_AUTO_SUMMARY_DURATION_SECONDS = 30 * 60
MAX_AUTO_SUMMARY_DURATION_SECONDS = 3 * 60 * 60


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def non_negative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--task-id", type=int, action="append", help="repeat to select several tasks")
    selection.add_argument("--all", action="store_true", help="fill all eligible tasks")
    selection.add_argument(
        "--after-task-id", type=non_negative_int,
        help="only fill tasks created after this fixed ID; use for scheduled runs",
    )
    parser.add_argument("--db-path", type=Path, default=DB_PATH)
    parser.add_argument("--workers", type=positive_int, default=1)
    parser.add_argument("--kind", choices=SUMMARY_FIELDS, help="generate only this kind; default: brief then detail, in separate calls")
    parser.add_argument("--timeout", type=positive_int, default=600, help="seconds per Codex call")
    parser.add_argument("--humanizer-skill", type=Path, default=HUMANIZER_SKILL)
    args = parser.parse_args(argv)
    kinds = (args.kind,) if args.kind else tuple(SUMMARY_FIELDS)
    db_path = args.db_path.expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # Keep the file in place: unlinking it could let another process lock a new inode.
    with db_path.with_suffix(".summaries.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another summary run is active; skipped.")
            return 0
        init_db(db_path)
        if args.all or args.after_task_id is not None:
            minimum_task_id = args.after_task_id if args.after_task_id is not None else 0
            task_ids = []
            for task in list_tasks(db_path):
                if task["id"] <= minimum_task_id or not any(needs_summary(task, kind) for kind in kinds):
                    continue
                if args.after_task_id is not None:
                    duration = task.get("audio_duration_seconds")
                    if not isinstance(duration, (int, float)) or not (
                        MIN_AUTO_SUMMARY_DURATION_SECONDS <= duration <= MAX_AUTO_SUMMARY_DURATION_SECONDS
                    ):
                        print(
                            f"Task {task['id']}: skipped (automatic summaries require 30–180 minutes; "
                            f"audio_duration_seconds={duration!r}).", flush=True,
                        )
                        continue
                task_ids.append(task["id"])
        else:
            task_ids = list(dict.fromkeys(args.task_id))
        print(f"Selected {len(task_ids)} task(s).", flush=True)
        client = CodexSummaryClient(timeout_seconds=args.timeout, skill_path=args.humanizer_skill)

        def generate(task_id: int) -> bool:
            succeeded = True
            for kind in kinds:
                try:
                    task = generate_task_summary(task_id, kind, db_path, client=client)
                    print(f"Task {task_id} {kind}: {'generated' if task else 'skipped'}", flush=True)
                except Exception as exc:
                    print(f"Task {task_id} {kind}: failed: {exc}", file=sys.stderr, flush=True)
                    succeeded = False
            return succeeded

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            results = list(pool.map(generate, task_ids))
        return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
