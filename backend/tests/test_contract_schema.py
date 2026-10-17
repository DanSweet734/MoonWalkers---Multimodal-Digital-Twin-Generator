"""The committed JSON Schema must match the Pydantic contract models."""

import json
from pathlib import Path

from moonwalkers.contracts.json_schema import (
    SCHEMA_PATH,
    contract_json_schema,
    write_contract_json_schema,
)


def test_committed_schema_matches_models() -> None:
    committed = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert committed == contract_json_schema(), (
        "pipeline_result.schema.json is out of date; regenerate it from backend/ with "
        "`uv run python -m moonwalkers.contracts.json_schema`"
    )


def test_written_schema_round_trips_with_lf_endings(tmp_path: Path) -> None:
    out = write_contract_json_schema(tmp_path / "schema.json")
    assert json.loads(out.read_text(encoding="utf-8")) == contract_json_schema()
    assert b"\r\n" not in out.read_bytes()
