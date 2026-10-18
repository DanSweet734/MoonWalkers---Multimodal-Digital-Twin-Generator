"""The MoonWalkers API (Phase 5, decision 0014): jobs, twins, sources and files for the dashboard.

From ``backend/`` (it listens on 127.0.0.1 only)::

    uv run python -m moonwalkers.api [--data ../data] [--port 8000]

or, with reloading while developing: ``uv run uvicorn moonwalkers.api.app:app --reload``. The
interactive API documentation is at ``/api/docs``. When ``dashboard/dist`` exists (``npm run
build``), the API also serves the dashboard at ``/``; while developing it, ``npm run dev`` serves
the dashboard and forwards ``/api`` here.

It works on the same data folder as the agent's MCP server (``moonwalkers.workspace``) and writes
the knowledge base only through the orchestrator (CLAUDE.md rule 6).
"""

from __future__ import annotations

from collections.abc import Sequence
from importlib.metadata import version as package_version
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from moonwalkers.clock import Clock, utc_now
from moonwalkers.kb import JsonKnowledgeBase, KnowledgeBase
from moonwalkers.workspace import OPEN_STAGES, Workspace, default_data_dir, list_runs

from . import files, jobs, sources, twins
from .context import MAX_UPLOAD_BYTES, ApiContext, Context
from .models import ApiStatus
from .security import LOCAL_HOSTS, guard_writes

DASHBOARD_DIR = Path(__file__).resolve().parents[4] / "dashboard" / "dist"
DESCRIPTION = (
    "Jobs (run folders), twins with their sources and reviews, and files from the data folder, "
    "for the MoonWalkers dashboard. Local use only: no login, 127.0.0.1 only. Requests that "
    "change something need the X-MoonWalkers-Client header."
)

status_router = APIRouter(tags=["status"])


@status_router.get("/api/status")
def get_status(ctx: Context) -> ApiStatus:
    """The data folder in use and how much it holds."""
    machines = ctx.kb.list_machines()
    return ApiStatus(
        version=package_version("moonwalkers"),
        data_dir=str(ctx.data_dir),
        machines=len(machines),
        twin_versions=sum(len(ctx.kb.list_versions(key)) for key in machines),
        open_jobs=sum(s.stage in OPEN_STAGES for s in list_runs(ctx.workspace)),
    )


def create_app(
    workspace: Workspace | None = None,
    kb: KnowledgeBase | None = None,
    clock: Clock = utc_now,
    dashboard_dir: Path | None = DASHBOARD_DIR,
    allowed_hosts: Sequence[str] = LOCAL_HOSTS,
    max_upload_bytes: int = MAX_UPLOAD_BYTES,
) -> FastAPI:
    """The app for one data folder (by default the one the MCP server uses)."""
    workspace = workspace or Workspace(default_data_dir(), clock)
    data_dir = Path(workspace.data_dir).resolve()
    app = FastAPI(
        title="MoonWalkers API",
        version=package_version("moonwalkers"),
        description=DESCRIPTION,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.context = ApiContext(
        workspace=workspace,
        kb=kb or JsonKnowledgeBase(data_dir / "kb"),
        clock=clock,
        max_upload_bytes=max_upload_bytes,
    )
    app.add_middleware(BaseHTTPMiddleware, dispatch=guard_writes)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(allowed_hosts))  # outermost
    for router in (status_router, jobs.router, twins.router, sources.router, files.router):
        app.include_router(router)
    if dashboard_dir is not None and (dashboard_dir / "index.html").is_file():
        app.mount("/", StaticFiles(directory=dashboard_dir, html=True), name="dashboard")
    return app


app = create_app()
