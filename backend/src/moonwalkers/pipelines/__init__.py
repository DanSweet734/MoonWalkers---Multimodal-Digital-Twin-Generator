"""Input pipelines A-D. Each returns a ``PipelineResult``; only the orchestrator stores results."""

from moonwalkers.contracts.pipeline_result import PipelineId

from . import a, c, d
from .base import Pipeline, result_id_for


def default_pipelines() -> dict[PipelineId, Pipeline]:
    """The stubs for A, C and D. Pipeline B needs a generator and a run folder, so its caller
    builds it (``moonwalkers.pipelines.b``)."""
    return {
        p.pipeline_id: p for p in (a.create_pipeline(), c.create_pipeline(), d.create_pipeline())
    }


__all__ = ["Pipeline", "default_pipelines", "result_id_for"]
