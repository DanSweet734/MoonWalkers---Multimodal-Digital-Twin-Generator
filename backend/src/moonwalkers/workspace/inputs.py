"""Saving a photo someone uploads as a machine input, as data/README.md asks (decision 0014).

The photo goes to ``machines/<machine>/inputs/photos/`` and gets a line in that machine's
``inputs/SOURCES.md``: file, where it came from, when it arrived, SHA-256 and license note. A file
is never overwritten. The same photo uploaded again is the file already there; a different photo
whose name is taken gets a number.
"""

from __future__ import annotations

import hashlib
import itertools
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

# The image types the generator's preparation step reads (Pillow, in the generator environment).
PHOTO_SIGNATURES = ((b"\xff\xd8\xff", ".jpg"), (b"\x89PNG\r\n\x1a\n", ".png"))
INPUTS_DIR = "inputs"
PHOTOS_DIR = "photos"
SOURCES_FILE = "SOURCES.md"
SOURCES_HEADER = """\
# Sources for {machine} inputs

One line per file (data/README.md). These files may be copyrighted by their owners: `data/` is
gitignored and must not be redistributed.

| File | Source URL | Retrieved | SHA-256 | License note |
|---|---|---|---|---|
"""


class UnsupportedPhotoError(ValueError):
    """The upload is not a JPEG or PNG image."""


@dataclass(frozen=True)
class SavedPhoto:
    path: Path
    sha256: str
    already_saved: bool  # the same bytes were already in the photos folder (and SOURCES.md)


def photo_suffix(data: bytes) -> str:
    """``.jpg`` or ``.png``, from the file's first bytes rather than its name."""
    for signature, suffix in PHOTO_SIGNATURES:
        if data.startswith(signature):
            return suffix
    raise UnsupportedPhotoError("the photo must be a JPEG or PNG image")


def save_photo(
    machine_dir: Path,
    data: bytes,
    filename: str,
    origin: str,
    license_note: str | None,
    received_at: datetime,
) -> SavedPhoto:
    """Save an uploaded photo under ``machine_dir/inputs/photos/`` and list it in SOURCES.md.

    ``origin`` says where the photo came from (a URL, or who took it and where); ``received_at``
    is when the platform received it.
    """
    suffix = photo_suffix(data)
    sha256 = hashlib.sha256(data).hexdigest()
    photos = Path(machine_dir) / INPUTS_DIR / PHOTOS_DIR
    photos.mkdir(parents=True, exist_ok=True)
    for existing in sorted(photos.iterdir()):
        if existing.is_file() and _sha256(existing) == sha256:
            return SavedPhoto(existing, sha256, already_saved=True)

    # The local date, as in run folder names; it also keeps names like "con" from being devices.
    stem = f"{received_at.astimezone().date().isoformat()}_{safe_stem(filename)}"
    for n in itertools.count(1):
        path = photos / (f"{stem}{suffix}" if n == 1 else f"{stem}-{n}{suffix}")
        try:
            with path.open("xb") as file:  # "x": fails rather than overwrite
                file.write(data)
            break
        except FileExistsError:
            continue
    _add_source_line(
        Path(machine_dir),
        path.relative_to(Path(machine_dir) / INPUTS_DIR).as_posix(),
        origin,
        received_at,
        sha256,
        license_note,
    )
    return SavedPhoto(path, sha256, already_saved=False)


def safe_stem(filename: str) -> str:
    """The upload's name without folders or extension, in letters, digits, ``.``, ``_``, ``-``."""
    stem = PurePosixPath(filename.replace("\\", "/")).stem
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-._")[:80]
    return cleaned or "photo"


def _add_source_line(
    machine_dir: Path,
    file: str,
    origin: str,
    received_at: datetime,
    sha256: str,
    license_note: str | None,
) -> None:
    sources = machine_dir / INPUTS_DIR / SOURCES_FILE
    text = sources.read_text(encoding="utf-8") if sources.is_file() else ""
    if not text.strip():
        prefix = SOURCES_HEADER.format(machine=machine_dir.name)
    else:
        prefix = "" if text.endswith("\n") else "\n"
    when = received_at.astimezone(UTC).strftime("%Y-%m-%d (%H:%M:%S UTC)")
    cells = [
        file,
        origin,
        f"{when}, uploaded through the dashboard",
        sha256,
        license_note or "not given",
    ]
    line = "| " + " | ".join(_cell(c) for c in cells) + " |\n"
    with sources.open("a", encoding="utf-8", newline="\n") as out:
        out.write(prefix + line)


def _cell(text: str) -> str:
    """Text that stays inside one Markdown table cell."""
    return " ".join(text.split()).replace("|", "\\|")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
