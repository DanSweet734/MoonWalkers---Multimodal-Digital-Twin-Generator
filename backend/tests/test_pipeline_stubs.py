"""Pipeline stubs A, C and D return valid, clearly labelled fixture results."""

from datetime import datetime
from pathlib import Path

import pytest

from moonwalkers.contracts.pipeline_result import InputType, PipelineId
from moonwalkers.kb import machine_key
from moonwalkers.pipelines import default_pipelines, result_id_for
from moonwalkers.pipelines.fixture_stub import STUB_NOTICE, FixturePipeline

STUB_INPUTS = {
    PipelineId.A: [InputType.NAMEPLATE_PHOTO],
    PipelineId.C: [InputType.LAYOUT_DRAWING, InputType.SCHEMATIC],
    PipelineId.D: [InputType.ONLINE_RESOURCE],
}


def test_default_pipelines_are_the_three_stubs() -> None:
    assert set(default_pipelines()) == {PipelineId.A, PipelineId.C, PipelineId.D}


@pytest.mark.parametrize("pipeline_id", sorted(STUB_INPUTS))
def test_stub_returns_labelled_ha5c_result(pipeline_id: PipelineId, make_source) -> None:
    sources = [make_source(f"in-{t.value}", t) for t in STUB_INPUTS[pipeline_id]]

    result = default_pipelines()[pipeline_id].run("job-7", sources)

    assert result.pipeline == pipeline_id
    assert result.job_id == "job-7"
    assert result.result_id == result_id_for("job-7", pipeline_id)
    assert result.input_types == sorted(STUB_INPUTS[pipeline_id], key=lambda t: t.value)
    assert result.produced_at.tzinfo is not None
    assert result.needs_human_review is True
    assert STUB_NOTICE in [i.message for i in result.issues]
    assert machine_key(result.identity.manufacturer, result.identity.model) == "haas/ha5c"
    assert result.facts, "each stub carries at least one cited fact"


def test_fixture_pipeline_fills_in_run_details(
    b_fixture_path: Path, clock, fixed_time: datetime, make_source
) -> None:
    stub = FixturePipeline(PipelineId.B, b_fixture_path, clock=clock)
    result = stub.run("job-9", [make_source("photo", InputType.MACHINE_PHOTO)])
    assert (result.result_id, result.job_id, result.produced_at) == (
        "res-job-9-b",
        "job-9",
        fixed_time,
    )


def test_fixture_input_types_are_kept_without_typed_inputs(b_fixture_path: Path) -> None:
    result = FixturePipeline(PipelineId.B, b_fixture_path).run("job-1", [])
    assert result.input_types == [InputType.MACHINE_PHOTO]


def test_fixture_for_another_pipeline_is_refused(b_fixture_path: Path) -> None:
    with pytest.raises(ValueError, match="Pipeline B data"):
        FixturePipeline(PipelineId.A, b_fixture_path).run("job-1", [])
