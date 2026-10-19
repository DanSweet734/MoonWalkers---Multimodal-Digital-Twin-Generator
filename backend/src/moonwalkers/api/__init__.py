"""The API for the dashboard (Phase 5, decision 0014): jobs, twins, sources and files.

Start it with ``uv run python -m moonwalkers.api`` from ``backend/``; see ``app.py``.
"""

from .app import create_app

__all__ = ["create_app"]
