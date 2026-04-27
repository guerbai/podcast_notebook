from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    podcast_title TEXT NOT NULL,
    rss_url TEXT NOT NULL,
    episode_title TEXT NOT NULL,
    episode_guid TEXT,
    audio_url TEXT NOT NULL,
    shownotes TEXT NOT NULL DEFAULT '',
    summarize TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'queued',
    progress_stage TEXT NOT NULL DEFAULT 'queued',
    progress_percent REAL NOT NULL DEFAULT 0,
    download_percent REAL NOT NULL DEFAULT 0,
    transcription_percent REAL NOT NULL DEFAULT 0,
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    pending_action TEXT NOT NULL DEFAULT '',
    audio_file_path TEXT,
    output_txt_path TEXT,
    summary_md_path TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    level TEXT NOT NULL DEFAULT 'info',
    message TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
"""


TASK_MIGRATIONS = {
    "download_percent": "ALTER TABLE tasks ADD COLUMN download_percent REAL NOT NULL DEFAULT 0",
    "transcription_percent": "ALTER TABLE tasks ADD COLUMN transcription_percent REAL NOT NULL DEFAULT 0",
    "cancel_requested": "ALTER TABLE tasks ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0",
    "pending_action": "ALTER TABLE tasks ADD COLUMN pending_action TEXT NOT NULL DEFAULT ''",
    "summary_md_path": "ALTER TABLE tasks ADD COLUMN summary_md_path TEXT",
    "shownotes": "ALTER TABLE tasks ADD COLUMN shownotes TEXT NOT NULL DEFAULT ''",
    "summarize": "ALTER TABLE tasks ADD COLUMN summarize TEXT NOT NULL DEFAULT ''",
}


def _normalize_db_path(db_path: str | Path | None = None) -> Path:
    return Path(db_path) if db_path is not None else DB_PATH


def connect_db(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = _normalize_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: str | Path | None = None) -> None:
    with connect_db(db_path) as connection:
        connection.executescript(SCHEMA)
        _migrate_tasks_table(connection)


def _migrate_tasks_table(connection: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
    }
    for column, statement in TASK_MIGRATIONS.items():
        if column not in columns:
            connection.execute(statement)
    connection.execute(
        """
        DELETE FROM tasks
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM tasks
            GROUP BY podcast_title, episode_title
        )
        """
    )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_unique_episode ON tasks (podcast_title, episode_title)"
    )


def list_tasks(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    with connect_db(db_path) as connection:
        rows = connection.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]


def get_task(task_id: int, db_path: str | Path | None = None) -> dict[str, Any] | None:
    with connect_db(db_path) as connection:
        row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(row) if row else None


def find_task_by_episode(
    podcast_title: str,
    episode_title: str,
    db_path: str | Path | None = None,
) -> dict[str, Any] | None:
    with connect_db(db_path) as connection:
        row = connection.execute(
            """
            SELECT * FROM tasks
            WHERE podcast_title = ? AND episode_title = ?
            """,
            (podcast_title, episode_title),
        ).fetchone()
    return dict(row) if row else None


def create_task(task: dict[str, Any], db_path: str | Path | None = None) -> dict[str, Any]:
    existing = find_task_by_episode(task["podcast_title"], task["episode_title"], db_path)
    if existing is not None:
        return existing

    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "podcast_title": task["podcast_title"],
        "rss_url": task["rss_url"],
        "episode_title": task["episode_title"],
        "episode_guid": task.get("episode_guid"),
        "audio_url": task["audio_url"],
        "shownotes": task.get("shownotes", ""),
        "summarize": task.get("summarize", ""),
        "status": task.get("status", "queued"),
        "progress_stage": task.get("progress_stage", "queued"),
        "progress_percent": task.get("progress_percent", 0.0),
        "download_percent": task.get("download_percent", 0.0),
        "transcription_percent": task.get("transcription_percent", 0.0),
        "cancel_requested": int(task.get("cancel_requested", 0)),
        "pending_action": task.get("pending_action", ""),
        "audio_file_path": task.get("audio_file_path"),
        "output_txt_path": task.get("output_txt_path"),
        "summary_md_path": task.get("summary_md_path"),
        "error_message": task.get("error_message"),
        "created_at": now,
        "started_at": task.get("started_at"),
        "finished_at": task.get("finished_at"),
    }
    with connect_db(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO tasks (
                podcast_title, rss_url, episode_title, episode_guid, audio_url,
                shownotes, summarize, status, progress_stage, progress_percent, download_percent,
                transcription_percent, cancel_requested, pending_action, audio_file_path,
                output_txt_path, summary_md_path, error_message, created_at, started_at, finished_at
            )
            VALUES (
                :podcast_title, :rss_url, :episode_title, :episode_guid, :audio_url,
                :shownotes, :summarize, :status, :progress_stage, :progress_percent, :download_percent,
                :transcription_percent, :cancel_requested, :pending_action, :audio_file_path,
                :output_txt_path, :summary_md_path, :error_message, :created_at, :started_at, :finished_at
            )
            """,
            payload,
        )
        task_id = cursor.lastrowid
    return get_task(task_id, db_path)


def update_task(
    task_id: int,
    values: dict[str, Any],
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    if not values:
        task = get_task(task_id, db_path)
        if task is None:
            raise KeyError(task_id)
        return task

    assignments = ", ".join(f"{column} = :{column}" for column in values)
    payload = dict(values)
    payload["task_id"] = task_id
    with connect_db(db_path) as connection:
        connection.execute(
            f"UPDATE tasks SET {assignments} WHERE id = :task_id",
            payload,
        )
    task = get_task(task_id, db_path)
    if task is None:
        raise KeyError(task_id)
    return task


def add_task_event(
    task_id: int,
    message: str,
    level: str = "info",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    with connect_db(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO task_events (task_id, level, message, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (task_id, level, message, now),
        )
        event_id = cursor.lastrowid
        row = connection.execute(
            "SELECT * FROM task_events WHERE id = ?",
            (event_id,),
        ).fetchone()
    return dict(row)


def list_task_events(task_id: int, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    with connect_db(db_path) as connection:
        rows = connection.execute(
            "SELECT * FROM task_events WHERE task_id = ? ORDER BY id ASC",
            (task_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_task(task_id: int, db_path: str | Path | None = None) -> bool:
    with connect_db(db_path) as connection:
        cursor = connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    return cursor.rowcount > 0
