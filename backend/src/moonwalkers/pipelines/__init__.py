"""Input pipelines A-D. Each returns a ``PipelineResult``; only the orchestrator stores results."""

from pathlib import Path

from moonwalkers.contracts.pipeline_result import PipelineId

from . import a, c, d
from .base import Pipeline, result_id_for
from .fixture_stub import FixturePipeline

OWNERS: dict[PipelineId, str] = {
    PipelineId.A: "Ava Harken",
    PipelineId.B: "Daniel Sweet",
    PipelineId.C: "Shankar Kiran Ragavender",
    PipelineId.D: "Sarkis Nazaryan",
}


def default_pipelines() -> dict[PipelineId, Pipeline]:
    """The owners' pipelines A, C and D that are in: each folder's ``create_pipeline()``, unless it
    still returns the stub, which gives the HA5C's data for any input (decision 0021). Pipeline B
    needs a generator and a run folder, so its caller builds it (``moonwalkers.pipelines.b``)."""
    made = (a.create_pipeline(), c.create_pipeline(), d.create_pipeline())
    return {p.pipeline_id: p for p in made if not p.stub}


def stub_pipelines() -> dict[PipelineId, Pipeline]:
    """The PoC's fixture stubs for A, C and D (decision 0002), for the tests only (decision
    0021). Their fixtures stay in the owners' folders."""
    here = Path(__file__).parent
    return {
        pid: FixturePipeline(pid, here / pid.value.lower() / "haas_ha5c.stub.json")
        for pid in (PipelineId.A, PipelineId.C, PipelineId.D)
    }


__all__ = ["OWNERS", "Pipeline", "default_pipelines", "result_id_for", "stub_pipelines"]
