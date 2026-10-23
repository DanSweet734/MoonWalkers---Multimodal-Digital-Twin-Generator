"""Pipeline stubs A, C and D return valid, clearly labelled fixture results, and run only in the
tests (decision 0021)."""

from datetime import datetime
from pathlib import Path

import pytest

from moonwalkers.contracts.pipeline_result import InputType, PipelineId, PipelineResult, Source
from moonwalkers.kb import machine_key
from moonwalkers.pipelines import (
    Pipeline,
    a,
    c,
    d,
    default_pipelines,
    result_id_for,
    stub_pipelines,
)
from moonwalkers.pipelines.fixture_stub import STUB_NOTICE, FixturePipeline

STUB_INPUTS = {
    PipelineId.A: [InputType.NAMEPLATE_PHOTO],
    PipelineId.C: [InputType.LAYOUT_DRAWING, InputType.SCHEMATIC],
    PipelineId.D: [InputType.ONLINE_RESOURCE],
}


def test_stub_pipelines_are_the_three_stubs() -> None:
    stubs = stub_pipelines()
    assert set(stubs) == {PipelineId.A, PipelineId.C, PipelineId.D}
    assert all(p.stub for p in stubs.values())


class OwnersPipeline(Pipeline):
    """Stands in for an owner's real pipeline, whatever the owners have merged."""

    pipeline_id = PipelineId.D

    def run(self, job_id: str, sources: list[Source]) -> PipelineResult:
        raise NotImplementedError


def test_default_pipelines_leave_the_stubs_out(monkeypatch) -> None:
    """Each stub returns the HA5C's data for any input, so outside the tests a document for a
    pipeline that is not in yet is refused instead (decision 0021)."""
    stubs = stub_pipelines()
    monkeypatch.setattr(a, "create_pipeline", lambda: stubs[PipelineId.A])
    monkeypatch.setattr(c, "create_pipeline", lambda: stubs[PipelineId.C])
    monkeypatch.setattr(d, "create_pipeline", OwnersPipeline)
    pipelines = default_pipelines()
    assert list(pipelines) == [PipelineId.D]
    assert isinstance(pipelines[PipelineId.D], OwnersPipeline)


@pytest.mark.parametrize("pipeline_id", sorted(STUB_INPUTS))
def test_stub_returns_labelled_ha5c_result(pipeline_id: PipelineId, make_source) -> None:
    sources = [make_source(f"in-{t.value}", t) for t in STUB_INPUTS[pipeline_id]]

    result = stub_pipelines()[pipeline_id].run("job-7", sources)

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
