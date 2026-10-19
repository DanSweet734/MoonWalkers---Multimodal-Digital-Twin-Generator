"""Build and write the JSON Schema for the shared contract.

``pipeline_result.schema.json`` is generated from the Pydantic models and never edited by hand. It
is the contract's schema for pipeline authors. The dashboard's TypeScript types come from the same
models through the API's OpenAPI schema (``moonwalkers.api.typescript``, decision 0014).
Regenerate both after any contract change (run from ``backend/``)::

    uv run python -m moonwalkers.contracts.json_schema
    uv run python -m moonwalkers.api.typescript
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .pipeline_result import JobResult, PipelineResult

SCHEMA_PATH = Path(__file__).with_name("pipeline_result.schema.json")

# TwinRecord is included through JobResult's $defs.
TOP_LEVEL_MODELS = (PipelineResult, JobResult)


def contract_json_schema() -> dict[str, Any]:
    """JSON Schema for each top-level contract model, keyed by model name."""
    return {model.__name__: model.model_json_schema() for model in TOP_LEVEL_MODELS}


def write_contract_json_schema(path: Path = SCHEMA_PATH) -> Path:
    """Write the schema with LF line endings on every platform; returns the path written."""
    path.write_text(json.dumps(contract_json_schema(), indent=2), encoding="utf-8", newline="\n")
    return path


if __name__ == "__main__":
    print(f"wrote {write_contract_json_schema()}")
