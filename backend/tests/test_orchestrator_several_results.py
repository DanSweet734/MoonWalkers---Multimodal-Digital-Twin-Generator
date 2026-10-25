"""One twin from several pipelines' results, and inputs for pipelines not in yet (decision 0021).

The pipelines here are fakes, not the stubs: the stubs run only in the tests that are about them.
"""

from collections.abc import Sequence
from datetime import datetime

import pytest

from moonwalkers.contracts.pipeline_result import (
    Citation,
    Fact,
    InputType,
    MachineIdentity,
    Part,
    PipelineId,
    PipelineResult,
    Source,
)
from moonwalkers.kb import KnowledgeBase
from moonwalkers.orchestrator import (
    JobRequest,
    Orchestrator,
    OrchestratorError,
    PipelineUnavailableError,
)
from moonwalkers.pipelines import Pipeline, default_pipelines, result_id_for

FactSpec = tuple[str, float | int | str | bool, str | None]


class FakePipeline(Pipeline):
    """A result with the given facts, and a part when ``geometry`` is true."""

    def __init__(
        self,
        pipeline_id: PipelineId,
        fixed_time: datetime,
        facts: Sequence[FactSpec] = (),
        geometry: bool = False,
    ) -> None:
        self.pipeline_id = pipeline_id
        self.fixed_time = fixed_time
        self.facts = list(facts)
        self.geometry = geometry

    def run(self, job_id: str, sources: list[Source]) -> PipelineResult:
        cite = [Citation(source_id=sources[0].source_id, locator="p. 1")]
        body = Part(
            part_id=f"body-{self.pipeline_id.value.lower()}",
            name="body",
            geometry_format="primitive",
            citations=cite,
        )
        parts = [body] if self.geometry else []
        return PipelineResult(
            result_id=result_id_for(job_id, self.pipeline_id),
            job_id=job_id,
            pipeline=self.pipeline_id,
            input_types=[s.input_type for s in sources],
            produced_at=self.fixed_time,
            produced_by="fake",
            sources=sources,
            identity=MachineIdentity(
                manufacturer="Grizzly Industrial, Inc.",
                model="T33901",
                confidence=0.9,
                citations=cite,
            ),
            facts=[
                Fact(key=key, value=value, unit=unit, confidence=0.9, citations=cite)
                for key, value, unit in self.facts
            ],
            parts=parts,
        )


@pytest.fixture
def inputs(make_source) -> list[Source]:
    return [
        make_source("datasheet", InputType.BROCHURE_DATASHEET),  # Pipeline A
        make_source("catalog", InputType.PDF_CATALOG),  # Pipeline D
    ]


def run(kb: KnowledgeBase, clock, sources: list[Source], *pipelines: FakePipeline):
    orchestrator = Orchestrator(kb, {p.pipeline_id: p for p in pipelines}, clock=clock)
    return orchestrator.run_job(JobRequest(job_id="job-1", sources=sources))


def test_a_document_for_a_pipeline_not_in_yet_is_refused_and_names_its_owner(
    kb: KnowledgeBase, make_source, clock
) -> None:
    orchestrator = Orchestrator(kb, default_pipelines(), clock=clock)
    request = JobRequest(job_id="job-1", sources=[make_source("manual", InputType.PDF_CATALOG)])
    with pytest.raises(PipelineUnavailableError) as raised:
        orchestrator.run_job(request)
    message = str(raised.value)
    assert "Pipeline D for pdf_catalog (Sarkis Nazaryan's)" in message
    assert "decision 0021" in message
    assert kb.list_machines() == []


def test_two_pipelines_build_one_version_and_agreeing_facts_add_no_note(
    kb: KnowledgeBase, clock, fixed_time: datetime, inputs
) -> None:
    """3-1/4 in is 0.08255 m; a catalogue's 82.5 mm differs by 0.06%, which is rounding."""
    job = run(
        kb,
        clock,
        inputs,
        FakePipeline(PipelineId.A, fixed_time, [("spindle_travel", 0.08255, "m")], geometry=True),
        FakePipeline(PipelineId.D, fixed_time, [("spindle_travel", 0.0825, "m")]),
    )
    assert job.twin.built_from == ["res-job-1-a", "res-job-1-d"]
    assert job.twin.machine_key == "grizzly-industrial/t33901"
    assert job.twin.notes is None
    assert all(kb.get_result(r) is not None for r in job.twin.built_from)


@pytest.mark.parametrize(
    ("a_fact", "d_fact", "listed"),
    [
        (("spindle_travel", 0.08255, "m"), ("spindle_travel", 0.0889, "m"), True),
        (("spindle_travel", 0.08255, "m"), ("spindle_travel", 3.25, "in"), True),
        (("switch", "Keyed", None), ("switch", " keyed ", None), False),
        (("has_laser", True, None), ("has_laser", False, None), True),
        (("speeds", 12, None), ("speeds", 12, None), False),
    ],
    ids=["values-differ", "units-differ", "text-agrees", "booleans-differ", "numbers-agree"],
)
def test_disagreeing_facts_are_listed_for_the_reviewer_and_none_is_picked(
    kb: KnowledgeBase, clock, fixed_time: datetime, inputs, a_fact, d_fact, listed: bool
) -> None:
    job = run(
        kb,
        clock,
        inputs,
        FakePipeline(PipelineId.A, fixed_time, [a_fact]),
        FakePipeline(PipelineId.D, fixed_time, [d_fact]),
    )
    if not listed:
        assert job.twin.notes is None
        return
    assert job.twin.notes.startswith("Fact disagreements, for the reviewer: ")
    assert f"{a_fact[0]}: Pipeline A" in job.twin.notes and ", Pipeline D " in job.twin.notes
    assert f"Note: {job.twin.notes}" in job.message
    stored = {r.pipeline: r for r in map(kb.get_result, job.twin.built_from)}  # both kept
    assert stored[PipelineId.A].facts[0].value == a_fact[1]
    assert stored[PipelineId.D].facts[0].value == d_fact[1]


def test_the_note_names_each_value_with_its_unit(
    kb: KnowledgeBase, clock, fixed_time: datetime, inputs
) -> None:
    job = run(
        kb,
        clock,
        inputs,
        FakePipeline(PipelineId.A, fixed_time, [("spindle_travel", 0.08255, "m")]),
        FakePipeline(PipelineId.D, fixed_time, [("spindle_travel", 0.0889, "m")]),
    )
    assert job.twin.notes == (
        "Fact disagreements, for the reviewer: spindle_travel: Pipeline A 0.08255 m, "
        "Pipeline D 0.0889 m."
    )


def test_two_results_with_parts_are_refused_and_nothing_is_stored(
    kb: KnowledgeBase, clock, fixed_time: datetime, inputs
) -> None:
    with pytest.raises(OrchestratorError, match="one result per twin carries the geometry"):
        run(
            kb,
            clock,
            inputs,
            FakePipeline(PipelineId.A, fixed_time, geometry=True),
            FakePipeline(PipelineId.D, fixed_time, geometry=True),
        )
    assert kb.list_machines() == []
    assert kb.get_result("res-job-1-a") is None
