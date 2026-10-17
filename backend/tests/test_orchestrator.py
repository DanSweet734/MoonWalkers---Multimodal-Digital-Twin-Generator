"""Orchestrator: build a twin once, reuse it after that, and re-version only on request."""

from datetime import datetime
from pathlib import Path

import pytest

from moonwalkers.contracts.pipeline_result import (
    Citation,
    InputType,
    MachineIdentity,
    PipelineId,
    PipelineResult,
    Source,
)
from moonwalkers.kb import KnowledgeBase
from moonwalkers.orchestrator import (
    JobRequest,
    MachineHint,
    NoInputsError,
    Orchestrator,
    OrchestratorError,
    PipelineUnavailableError,
    UnidentifiedMachineError,
)
from moonwalkers.pipelines import Pipeline, default_pipelines, result_id_for
from moonwalkers.pipelines.fixture_stub import FixturePipeline

HA5C = MachineHint(manufacturer="Haas Automation", model="HA5C")


class CountingPipeline(Pipeline):
    """Wraps a pipeline and counts how often it runs."""

    def __init__(self, inner: Pipeline) -> None:
        self.inner = inner
        self.pipeline_id = inner.pipeline_id
        self.calls = 0

    def run(self, job_id: str, sources: list[Source]) -> PipelineResult:
        self.calls += 1
        return self.inner.run(job_id, sources)


class FakePipeline(Pipeline):
    """Returns a minimal result with the given identity (or none)."""

    def __init__(
        self,
        pipeline_id: PipelineId,
        fixed_time: datetime,
        identity: tuple[str, str, float] | None,
        job_id: str | None = None,
    ) -> None:
        self.pipeline_id = pipeline_id
        self.fixed_time = fixed_time
        self.identity = identity
        self.job_id = job_id

    def run(self, job_id: str, sources: list[Source]) -> PipelineResult:
        identity = None
        if self.identity is not None:
            manufacturer, model, confidence = self.identity
            identity = MachineIdentity(
                manufacturer=manufacturer,
                model=model,
                confidence=confidence,
                citations=[Citation(source_id=sources[0].source_id)],
            )
        return PipelineResult(
            result_id=result_id_for(job_id, self.pipeline_id),
            job_id=self.job_id or job_id,
            pipeline=self.pipeline_id,
            input_types=[s.input_type for s in sources],
            produced_at=self.fixed_time,
            produced_by="fake",
            sources=sources,
            identity=identity,
        )


@pytest.fixture
def pipeline_b(b_fixture_path: Path, clock) -> CountingPipeline:
    return CountingPipeline(FixturePipeline(PipelineId.B, b_fixture_path, clock=clock))


@pytest.fixture
def orchestrator(kb: KnowledgeBase, pipeline_b: CountingPipeline, clock) -> Orchestrator:
    return Orchestrator(kb, {**default_pipelines(), PipelineId.B: pipeline_b}, clock=clock)


@pytest.fixture
def document_inputs(make_source) -> list[Source]:
    """Inputs for the A, C and D stubs."""
    return [
        make_source("nameplate", InputType.NAMEPLATE_PHOTO),
        make_source("drawing", InputType.LAYOUT_DRAWING),
        make_source("product-page", InputType.ONLINE_RESOURCE),
    ]


@pytest.fixture
def photo_inputs(make_source) -> list[Source]:
    return [make_source("photo-1", InputType.MACHINE_PHOTO)]


def test_first_request_builds_version_1(
    orchestrator: Orchestrator, kb: KnowledgeBase, document_inputs, fixed_time: datetime
) -> None:
    job = orchestrator.run_job(JobRequest(job_id="job-1", sources=document_inputs))

    assert job.reused_existing is False
    assert job.message.startswith(
        "No twin found for haas/ha5c; built version 1 from Pipelines A, C, D."
    )
    twin = job.twin
    assert (twin.twin_id, twin.machine_key, twin.version) == ("haas/ha5c@v1", "haas/ha5c", 1)
    assert twin.status == "needs_review"
    assert twin.created_at == fixed_time
    assert twin.built_from == ["res-job-1-a", "res-job-1-c", "res-job-1-d"]
    assert kb.get_twin("haas/ha5c") == twin
    assert all(kb.get_result(rid) is not None for rid in twin.built_from)


def test_second_request_reuses_the_stored_twin_and_says_so(
    orchestrator: Orchestrator, kb: KnowledgeBase, document_inputs
) -> None:
    # PoC pass criterion (docs/poc-plan.md): a second request reuses the stored twin and says so.
    first = orchestrator.run_job(JobRequest(job_id="job-1", sources=document_inputs))
    second = orchestrator.run_job(JobRequest(job_id="job-2", sources=document_inputs))

    assert second.reused_existing is True
    assert second.twin == first.twin
    assert second.message.startswith(
        "Found an existing twin (v1, needs review) for haas/ha5c; reused it."
    )
    assert "those results were not stored" in second.message
    assert [t.version for t in kb.list_versions("haas/ha5c")] == [1]
    assert kb.get_result("res-job-2-a") is None


def test_named_machine_is_reused_without_running_pipelines(
    orchestrator: Orchestrator, pipeline_b: CountingPipeline, photo_inputs
) -> None:
    orchestrator.run_job(JobRequest(job_id="job-1", sources=photo_inputs))
    assert pipeline_b.calls == 1

    again = orchestrator.run_job(JobRequest(job_id="job-2", sources=photo_inputs, machine=HA5C))

    assert again.reused_existing is True
    assert pipeline_b.calls == 1  # the expensive photo pipeline did not run again
    assert "identified after running" not in again.message


def test_new_version_only_on_request_and_old_version_is_kept(
    orchestrator: Orchestrator, kb: KnowledgeBase, document_inputs
) -> None:
    first = orchestrator.run_job(JobRequest(job_id="job-1", sources=document_inputs))
    rebuilt = orchestrator.run_job(
        JobRequest(job_id="job-2", sources=document_inputs, machine=HA5C, new_version=True)
    )

    assert rebuilt.reused_existing is False
    assert (rebuilt.twin.twin_id, rebuilt.twin.version) == ("haas/ha5c@v2", 2)
    assert rebuilt.twin.built_from == ["res-job-2-a", "res-job-2-c", "res-job-2-d"]
    assert "Built version 2 of the haas/ha5c twin as requested (previous: v1)" in rebuilt.message
    assert kb.list_versions("haas/ha5c") == [first.twin, rebuilt.twin]
    assert kb.get_twin("haas/ha5c") == rebuilt.twin


def test_machine_photos_go_to_pipeline_b(
    orchestrator: Orchestrator, pipeline_b: CountingPipeline, photo_inputs
) -> None:
    job = orchestrator.run_job(JobRequest(job_id="job-1", sources=photo_inputs))
    assert pipeline_b.calls == 1
    assert job.twin.built_from == ["res-job-1-b"]
    assert job.message.startswith("No twin found for haas/ha5c; built version 1 from Pipeline B.")


def test_missing_pipeline_is_reported_and_nothing_is_stored(
    kb: KnowledgeBase, photo_inputs, clock
) -> None:
    orchestrator = Orchestrator(kb, default_pipelines(), clock=clock)  # no Pipeline B yet
    with pytest.raises(PipelineUnavailableError, match="Pipeline B for machine_photo"):
        orchestrator.run_job(JobRequest(job_id="job-1", sources=photo_inputs))
    assert kb.list_machines() == []


def test_inputs_without_an_input_type_are_rejected(orchestrator: Orchestrator, make_source) -> None:
    with pytest.raises(NoInputsError):
        orchestrator.run_job(JobRequest(job_id="job-1", sources=[make_source("note", None)]))


def test_unidentified_machine_is_rejected_and_nothing_is_stored(
    kb: KnowledgeBase, make_source, fixed_time: datetime, clock
) -> None:
    pipelines = {PipelineId.A: FakePipeline(PipelineId.A, fixed_time, identity=None)}
    orchestrator = Orchestrator(kb, pipelines, clock=clock)
    with pytest.raises(UnidentifiedMachineError):
        orchestrator.run_job(
            JobRequest(job_id="job-1", sources=[make_source("plate", InputType.NAMEPLATE_PHOTO)])
        )
    assert kb.list_machines() == []


def test_identity_disagreement_uses_most_confident_and_says_so(
    kb: KnowledgeBase, make_source, fixed_time: datetime, clock
) -> None:
    pipelines = {
        PipelineId.A: FakePipeline(PipelineId.A, fixed_time, ("Haas Automation", "HA5C", 0.9)),
        PipelineId.D: FakePipeline(PipelineId.D, fixed_time, ("Haas Automation", "HRT160", 0.5)),
    }
    sources = [
        make_source("plate", InputType.NAMEPLATE_PHOTO),
        make_source("catalog", InputType.PDF_CATALOG),
    ]
    job = Orchestrator(kb, pipelines, clock=clock).run_job(
        JobRequest(job_id="job-1", sources=sources)
    )

    assert job.twin.machine_key == "haas/ha5c"
    assert "Pipeline D said haas/hrt160 (confidence 0.50)" in job.twin.notes
    assert "Note: Machine identity disagreement" in job.message


def test_machine_named_in_the_request_wins(orchestrator: Orchestrator, document_inputs) -> None:
    hint = MachineHint(manufacturer="Grizzly Industrial", model="T33901")
    job = orchestrator.run_job(JobRequest(job_id="job-1", sources=document_inputs, machine=hint))

    assert job.twin.machine_key == "grizzly-industrial/t33901"
    assert "(named in the request)" in job.twin.notes
    assert "Pipeline A said haas/ha5c" in job.twin.notes


def test_result_for_the_wrong_job_is_rejected(
    kb: KnowledgeBase, make_source, fixed_time: datetime, clock
) -> None:
    rogue = FakePipeline(PipelineId.A, fixed_time, ("Haas", "HA5C", 0.9), job_id="other-job")
    orchestrator = Orchestrator(kb, {PipelineId.A: rogue}, clock=clock)
    with pytest.raises(OrchestratorError, match="expected job job-1"):
        orchestrator.run_job(
            JobRequest(job_id="job-1", sources=[make_source("plate", InputType.NAMEPLATE_PHOTO)])
        )
    assert kb.list_machines() == []
