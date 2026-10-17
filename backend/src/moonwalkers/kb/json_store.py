"""Knowledge base stored as one pretty-printed JSON file per record (decision 0008).

Layout under ``root`` (``data/kb/`` in normal use)::

    results/<result_id>.json
    twins/<manufacturer>/<model>/v0001.json

Assumes one writer at a time (the PoC is single-user); a second process saving the same record at
the same moment could overwrite it.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from moonwalkers.contracts.pipeline_result import PipelineResult, TwinRecord

from .base import AlreadyExistsError, InvalidIdError, KnowledgeBase
from .keys import validate_machine_key

ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class JsonKnowledgeBase(KnowledgeBase):
    """A knowledge base kept as JSON files under ``root``."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    # ---------------------------------------------------------------- results
    def save_result(self, result: PipelineResult) -> None:
        _write_new(self._result_path(result.result_id), result.model_dump_json(indent=2))

    def get_result(self, result_id: str) -> PipelineResult | None:
        path = self._result_path(result_id)
        if not path.is_file():
            return None
        return PipelineResult.model_validate_json(path.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------ twins
    def save_twin(self, twin: TwinRecord) -> None:
        path = self._twin_dir(twin.machine_key) / _version_file(twin.version)
        _write_new(path, twin.model_dump_json(indent=2))

    def get_twin(self, machine_key: str, version: int | None = None) -> TwinRecord | None:
        if version is None:
            versions = self.list_versions(machine_key)
            return versions[-1] if versions else None
        path = self._twin_dir(machine_key) / _version_file(version)
        if not path.is_file():
            return None
        return TwinRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def list_versions(self, machine_key: str) -> list[TwinRecord]:
        twin_dir = self._twin_dir(machine_key)
        if not twin_dir.is_dir():
            return []
        twins = [
            TwinRecord.model_validate_json(p.read_text(encoding="utf-8"))
            for p in twin_dir.glob("v*.json")
        ]
        return sorted(twins, key=lambda t: t.version)

    def list_machines(self) -> list[str]:
        twins_root = self.root / "twins"
        if not twins_root.is_dir():
            return []
        return sorted(
            f"{maker.name}/{model.name}"
            for maker in twins_root.iterdir()
            if maker.is_dir()
            for model in maker.iterdir()
            if model.is_dir() and any(model.glob("v*.json"))
        )

    # ---------------------------------------------------------------- helpers
    def _result_path(self, result_id: str) -> Path:
        if not ID_PATTERN.fullmatch(result_id):
            raise InvalidIdError(
                f"invalid result id {result_id!r}: use letters, digits, '.', '_' and '-', "
                "starting with a letter or digit"
            )
        return self.root / "results" / f"{result_id}.json"

    def _twin_dir(self, machine_key: str) -> Path:
        manufacturer, model = validate_machine_key(machine_key).split("/")
        return self.root / "twins" / manufacturer / model


def _version_file(version: int) -> str:
    return f"v{version:04d}.json"


def _write_new(path: Path, text: str) -> None:
    """Write a new file, never overwriting one.

    The text goes to a temporary file first and is then moved into place with ``os.replace``, so a
    crash mid-write leaves no half-written record.
    """
    if path.exists():
        raise AlreadyExistsError(f"already stored, not overwritten: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
