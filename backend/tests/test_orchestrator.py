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
    TwinNotFoundError,
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


def test_exporter_sets_the_usd_path_before_the_twin_is_stored(
    kb: KnowledgeBase, pipeline_b: CountingPipeline, photo_inputs, clock
) -> None:
    exported: list[str] = []

    def exporter(twin, results) -> str:
        assert kb.get_twin(twin.machine_key) is None  # not stored yet
        exported.append(twin.twin_id)
        return f"machines/haas-ha5c/runs/run-1/{twin.version}.usda"

    orchestrator = Orchestrator(kb, {PipelineId.B: pipeline_b}, clock=clock, exporter=exporter)
    job = orchestrator.run_job(JobRequest(job_id="job-1", sources=photo_inputs))

    assert exported == ["haas/ha5c@v1"]
    assert job.twin.usd_path == "machines/haas-ha5c/runs/run-1/1.usda"
    assert kb.get_twin("haas/ha5c") == job.twin
    assert "Exported to machines/haas-ha5c/runs/run-1/1.usda." in job.message

    again = orchestrator.run_job(JobRequest(job_id="job-2", sources=photo_inputs, machine=HA5C))
    assert again.reused_existing and exported == [
        "haas/ha5c@v1"
    ]  # a reused twin is not re-exported


# ------------------------------------------------------------------- reviews (decision 0015)
def test_a_review_is_recorded_and_named_when_the_twin_is_reused(
    orchestrator: Orchestrator, kb: KnowledgeBase, document_inputs, fixed_time: datetime
) -> None:
    orchestrator.run_job(JobRequest(job_id="job-1", sources=document_inputs))
    first = orchestrator.review_twin("haas/ha5c", 1, "approved", "Daniel Sweet", "Moved as cited.")
    second = orchestrator.review_twin("haas/ha5c", 1, "approved", "Dr. Li", "Agreed.")

    assert (first.number, second.number) == (1, 2)
    assert first.reviewed_at == fixed_time and first.twin_id == "haas/ha5c@v1"
    assert kb.list_reviews("haas/ha5c", 1) == [first, second]
    assert kb.get_twin("haas/ha5c").status == "needs_review"  # the stored record is unchanged
    again = orchestrator.run_job(JobRequest(job_id="job-2", sources=[], machine=HA5C))
    assert again.message.startswith("Found an existing twin (v1, approved) for haas/ha5c;")


def test_a_rejected_version_is_never_reused(
    orchestrator: Orchestrator, pipeline_b: CountingPipeline, document_inputs, photo_inputs
) -> None:
    orchestrator.run_job(JobRequest(job_id="job-1", sources=document_inputs))
    orchestrator.run_job(
        JobRequest(job_id="job-2", sources=photo_inputs, machine=HA5C, new_version=True)
    )
    orchestrator.review_twin("haas/ha5c", 2, "rejected", "Daniel Sweet", "Spindle split wrong.")

    assert orchestrator.reusable_twin("haas/ha5c").version == 1  # type: ignore[union-attr]
    again = orchestrator.run_job(JobRequest(job_id="job-3", sources=photo_inputs, machine=HA5C))
    assert again.reused_existing and again.twin.version == 1
    assert "(v1, needs review)" in again.message
    assert "Newer versions were rejected in review: v2." in again.message
    assert pipeline_b.calls == 1  # reuse still runs no pipeline


def test_a_later_review_can_reverse_a_rejection(
    orchestrator: Orchestrator, document_inputs
) -> None:
    orchestrator.run_job(JobRequest(job_id="job-1", sources=document_inputs))
    orchestrator.review_twin("haas/ha5c", 1, "rejected", "Daniel Sweet", "Wrong scale.")
    assert orchestrator.reusable_twin("haas/ha5c") is None
    orchestrator.review_twin("haas/ha5c", 1, "approved", "Daniel Sweet", "Scale was right.")
    assert orchestrator.reusable_twin("haas/ha5c").version == 1  # type: ignore[union-attr]


def test_when_every_version_is_rejected_a_request_builds_a_new_one(
    orchestrator: Orchestrator, kb: KnowledgeBase, document_inputs
) -> None:
    orchestrator.run_job(JobRequest(job_id="job-1", sources=document_inputs))
    orchestrator.review_twin("haas/ha5c", 1, "rejected", "Daniel Sweet", "Not the HA5C.")

    assert orchestrator.reuse(JobRequest(job_id="job-2", machine=HA5C)) is None
    rebuilt = orchestrator.run_job(JobRequest(job_id="job-2", sources=document_inputs))
    assert not rebuilt.reused_existing and rebuilt.twin.version == 2
    assert rebuilt.message.startswith(
        "Every stored version of the haas/ha5c twin was rejected in review, so built version 2 "
        "(previous: v1) from Pipelines A, C, D."
    )
    assert [t.version for t in kb.list_versions("haas/ha5c")] == [1, 2]


def test_reuse_alone_runs_and_stores_nothing(
    orchestrator: Orchestrator, kb: KnowledgeBase, pipeline_b: CountingPipeline, photo_inputs
) -> None:
    named = JobRequest(job_id="job-2", sources=photo_inputs, machine=HA5C)
    assert orchestrator.reuse(named) is None  # nothing stored yet
    orchestrator.run_job(JobRequest(job_id="job-1", sources=photo_inputs))

    reused = orchestrator.reuse(named)
    assert reused is not None and reused.reused_existing and reused.job_id == "job-2"
    assert orchestrator.reuse(named.model_copy(update={"new_version": True})) is None
    assert orchestrator.reuse(JobRequest(job_id="job-3", sources=photo_inputs)) is None
    assert pipeline_b.calls == 1 and kb.get_result("res-job-2-b") is None


def test_reviewing_a_version_that_is_not_stored_fails(orchestrator: Orchestrator) -> None:
    with pytest.raises(TwinNotFoundError, match="haas/ha5c@v1"):
        orchestrator.review_twin("haas/ha5c", 1, "approved", "Daniel Sweet", "Looks right.")


def test_failed_export_stores_nothing(
    kb: KnowledgeBase, pipeline_b: CountingPipeline, photo_inputs, clock
) -> None:
    def exporter(twin, results) -> str:
        raise ValueError("export failed")

    orchestrator = Orchestrator(kb, {PipelineId.B: pipeline_b}, clock=clock, exporter=exporter)
    with pytest.raises(ValueError, match="export failed"):
        orchestrator.run_job(JobRequest(job_id="job-1", sources=photo_inputs))
    assert kb.list_machines() == []
    assert kb.get_result("res-job-1-b") is None
