"""Input pipelines A-D. Each returns a ``PipelineResult``; only the orchestrator stores results."""

from moonwalkers.contracts.pipeline_result import PipelineId

from . import a, c, d
from .base import Pipeline, result_id_for


def default_pipelines() -> dict[PipelineId, Pipeline]:
    """The pipelines available today: stubs for A, C and D. Pipeline B arrives in Phase 3."""
    return {
        p.pipeline_id: p for p in (a.create_pipeline(), c.create_pipeline(), d.create_pipeline())
    }


__all__ = ["Pipeline", "default_pipelines", "result_id_for"]
