"""Contract tests: the example validates, and bad references are rejected."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from moonwalkers.contracts import PipelineResult

FIXTURE = Path(__file__).parent / "fixtures" / "ha5c_pipeline_b.example.json"


@pytest.fixture
def example() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_example_validates(example: dict) -> None:
    result = PipelineResult.model_validate(example)
    assert result.pipeline.value == "B"
    assert result.needs_human_review is True


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["joints"][0].update(child_part="missing-part"),
        lambda d: d["facts"][0]["citations"][0].update(source_id="missing-source"),
        lambda d: d["facts"][0].update(citations=[]),
        lambda d: d.update(unexpected_field=1),
        lambda d: d["control"][0].update(drives_joints=["missing-joint"]),
    ],
    ids=["unknown-part", "unknown-source", "no-citation", "extra-field", "unknown-joint"],
)
def test_bad_results_are_rejected(example: dict, mutate) -> None:
    bad = copy.deepcopy(example)
    mutate(bad)
    with pytest.raises(ValidationError):
        PipelineResult.model_validate(bad)
