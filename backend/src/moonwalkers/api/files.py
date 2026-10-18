"""Files from the data folder, for the dashboard to show or download (decision 0014).

Only machine inputs and run folders are served (``machines/<machine>/inputs/...`` and
``machines/<machine>/runs/...``), never hidden or temporary files, and only known file types:

- images, PDFs and JSON open in the browser;
- text, Markdown and saved web pages are sent as plain text, so a saved page's scripts never run
  on the API's origin;
- USD files and meshes are downloads.

Every response but a PDF's carries ``Content-Security-Policy: sandbox``. The input documents are
copyrighted (data/README.md): the API serves them only on this computer (127.0.0.1).
"""

from __future__ import annotations

from pathlib import PurePosixPath

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .context import Context

router = APIRouter(prefix="/api/files", tags=["files"])
TEXT = "text/plain; charset=utf-8"
INLINE = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".json": "application/json",
    ".md": TEXT,
    ".txt": TEXT,
    ".log": TEXT,
    ".html": TEXT,
    ".htm": TEXT,
}
DOWNLOAD = {
    ".usd": "application/octet-stream",
    ".usda": "application/octet-stream",
    ".usdc": "application/octet-stream",
    ".glb": "model/gltf-binary",
    ".obj": "application/octet-stream",
    ".ply": "application/octet-stream",
}
AREAS = frozenset({"inputs", "runs"})


@router.get("/{path:path}")
def get_file(path: str, ctx: Context) -> FileResponse:
    """A file under ``machines/<machine>/inputs/`` or ``machines/<machine>/runs/``, by its path
    relative to the data folder (the form the contract and the other endpoints use)."""
    parts = PurePosixPath(path).parts
    suffix = PurePosixPath(path).suffix.lower()
    allowed = (
        len(parts) >= 4
        and parts[0] == "machines"
        and parts[2] in AREAS
        and not any(p.startswith(".") or "\\" in p or ":" in p for p in parts)
        and (suffix in INLINE or suffix in DOWNLOAD)
    )
    full = (ctx.data_dir.joinpath(*parts)).resolve() if allowed else None
    if full is None or not full.is_relative_to(ctx.data_dir) or not full.is_file():
        raise HTTPException(404, f"no file {path!r} is served")
    headers = {"X-Content-Type-Options": "nosniff"}
    if suffix != ".pdf":  # [INFERENCE] a browser's PDF viewer may not open in a sandboxed page
        headers["Content-Security-Policy"] = "sandbox"
    if suffix in INLINE:
        return FileResponse(
            full,
            media_type=INLINE[suffix],
            headers=headers,
            filename=full.name,
            content_disposition_type="inline",
        )
    return FileResponse(full, media_type=DOWNLOAD[suffix], headers=headers, filename=full.name)
