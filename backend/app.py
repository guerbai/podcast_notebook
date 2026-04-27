from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.db import get_task, init_db, list_task_events
from backend.podcast_search import search_podcasts
from backend.rss import fetch_episodes
from backend.tasks import (
    TaskCreate,
    enqueue_task,
    get_task_detail,
    get_task_summary,
    get_task_text_file,
    list_task_details,
    migrate_shownotes_to_files,
    remove_task,
    restart_task,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"


def create_app(db_path: str | Path | None = None, executor: ThreadPoolExecutor | None = None) -> FastAPI:
    app = FastAPI(title="Podcast Notebook")
    app.state.db_path = Path(db_path) if db_path is not None else None
    app.state.executor = executor or ThreadPoolExecutor(max_workers=2, thread_name_prefix="podcast-task")
    init_db(app.state.db_path)
    migrate_shownotes_to_files(app.state.db_path)

    @app.get("/api/health")
    def healthcheck() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/search/podcasts")
    def podcast_search(q: str) -> dict[str, list[dict[str, Any]]]:
        try:
            results = search_podcasts(q)
        except Exception:
            results = []
        return {"items": results}

    @app.get("/api/search/episodes")
    def episode_search(rss_url: str, q: str = "") -> dict[str, list[dict[str, Any]]]:
        results = fetch_episodes(rss_url, q)
        return {"items": results}

    @app.get("/api/tasks")
    def task_list() -> dict[str, list[dict[str, Any]]]:
        return {"items": list_task_details(app.state.db_path)}

    @app.get("/api/tasks/{task_id}")
    def task_detail(task_id: int) -> dict[str, Any]:
        task = get_task_detail(task_id, app.state.db_path)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    @app.get("/api/tasks/{task_id}/events")
    def task_events(task_id: int) -> dict[str, list[dict[str, Any]]]:
        if get_task(task_id, app.state.db_path) is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"items": list_task_events(task_id, app.state.db_path)}

    @app.get("/api/tasks/{task_id}/summary")
    def task_summary(task_id: int) -> dict[str, Any]:
        summary = get_task_summary(task_id, app.state.db_path)
        if summary is None:
            raise HTTPException(status_code=404, detail="Summary not found")
        return summary

    @app.get("/api/tasks/{task_id}/shownotes")
    def task_shownotes(task_id: int) -> dict[str, Any]:
        shownotes = get_task_text_file(task_id, "shownotes", app.state.db_path)
        if shownotes is None:
            raise HTTPException(status_code=404, detail="Shownotes not found")
        return shownotes

    @app.get("/api/tasks/{task_id}/summarize")
    def task_summarize(task_id: int) -> dict[str, Any]:
        summarize = get_task_text_file(task_id, "summarize", app.state.db_path)
        if summarize is None:
            raise HTTPException(status_code=404, detail="Summarize not found")
        return summarize

    @app.post("/api/tasks", status_code=201)
    def task_create(payload: TaskCreate):
        result = enqueue_task(payload, app.state.db_path, app.state.executor)
        if result["result"] == "existing":
            return JSONResponse(result, status_code=200)
        return result

    @app.delete("/api/tasks/{task_id}")
    def task_delete(task_id: int):
        result = remove_task(task_id, app.state.db_path)
        if result is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return Response(status_code=204)

    @app.post("/api/tasks/{task_id}/restart")
    def task_restart(task_id: int):
        result = restart_task(task_id, app.state.db_path, app.state.executor)
        if result is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return result

    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

    return app
