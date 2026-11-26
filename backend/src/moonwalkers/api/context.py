"""What every endpoint shares: the data folder, the knowledge base, and one lock for writes."""

from __future__ import annotations

import hashlib
import os
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from moonwalkers.clock import Clock, utc_now
from moonwalkers.generators.base import GeneratorError, ImageTo3DGenerator
from moonwalkers.generators.hunyuan3d import GEN_ROOT_ENV, Hunyuan3DConfig, Hunyuan3DGenerator
from moonwalkers.kb import AlreadyExistsError, KnowledgeBase
from moonwalkers.orchestrator import Orchestrator, TwinNotFoundError
from moonwalkers.pipelines import default_pipelines
from moonwalkers.pipelines.b.pipeline import RunFolderConflict
from moonwalkers.workspace import UnsupportedPhotoError, Workspace

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # [INFERENCE] ample for one photo; the HA5C's is 454 KB


def default_cutter() -> ImageTo3DGenerator | None:
    """The generator whose job cuts photos out for a preview (decision 0041), from
    ``MOONWALKERS_GEN_ROOT``; None when it is not set. The API runs only its cut-out step, never
    the 3D model (decision 0014)."""
    root = os.environ.get(GEN_ROOT_ENV, "").strip()
    return Hunyuan3DGenerator(Hunyuan3DConfig.under(Path(root))) if root else None


@dataclass
class ApiContext:
    workspace: Workspace
    kb: KnowledgeBase
    clock: Clock = utc_now
    max_upload_bytes: int = MAX_UPLOAD_BYTES
    cutter: Callable[[], ImageTo3DGenerator | None] = default_cutter
    # Endpoints run in worker threads; one write at a time keeps the files consistent. The MCP
    # server is another process with its own lock, and writes other files (decision 0014).
    lock: threading.Lock = field(default_factory=threading.Lock)
    _hashes: dict[tuple[str, int, int], str] = field(default_factory=dict)

    @property
    def data_dir(self) -> Path:
        return Path(self.workspace.data_dir).resolve()

    def orchestrator(self) -> Orchestrator:
        return Orchestrator(self.kb, default_pipelines(), clock=self.clock)

    def input_files_by_hash(self) -> dict[str, str]:
        """SHA-256 to path (relative to the data folder) for every machine input file, so a URL
        source whose local copy was hashed can be opened from the dashboard."""
        found: dict[str, str] = {}
        for path in sorted((self.data_dir / "machines").glob("*/inputs/**/*")):
            if path.is_file() and not path.name.startswith("."):
                stat = path.stat()
                key = (str(path), stat.st_size, stat.st_mtime_ns)
                if key not in self._hashes:
                    self._hashes[key] = hashlib.sha256(path.read_bytes()).hexdigest()
                found.setdefault(self._hashes[key], self.workspace.relative(path))
        return found


def context(request: Request) -> ApiContext:
    return request.app.state.context


Context = Annotated[ApiContext, Depends(context)]


@contextmanager
def expected_errors() -> Iterator[None]:
    """The platform's expected failures as HTTP errors with a readable ``detail``."""
    try:
        yield
    except TwinNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (RunFolderConflict, AlreadyExistsError) as exc:
        raise HTTPException(409, str(exc)) from exc
    except UnsupportedPhotoError as exc:
        raise HTTPException(415, str(exc)) from exc
    except GeneratorError as exc:  # the cut-out preview's job failed (decision 0041)
        raise HTTPException(
            502, str(exc).splitlines()[0] if str(exc) else "the job failed"
        ) from exc
    except ValueError as exc:  # includes WorkspaceError, InvalidMachineKeyError, ValidationError
        raise HTTPException(400, str(exc).splitlines()[0] if str(exc) else "bad request") from exc
