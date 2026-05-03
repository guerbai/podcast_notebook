#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config import DB_PATH  # noqa: E402
from backend.maintenance import maintain_tasks  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Maintain podcast notebook tasks for cron.")
    parser.add_argument("--db-path", type=Path, default=DB_PATH, help="SQLite database path.")
    args = parser.parse_args(argv)

    result = maintain_tasks(db_path=args.db_path)
    print(
        "maintenance complete: "
        f"restarted={len(result.restarted_task_ids)} "
        f"deleted_audio={len(result.deleted_audio_paths)}"
    )
    if result.restarted_task_ids:
        print(f"restarted task ids: {', '.join(str(task_id) for task_id in result.restarted_task_ids)}")
    if result.deleted_audio_paths:
        print("deleted audio files:")
        for path in result.deleted_audio_paths:
            print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
