"""The interface every input pipeline (A-D) implements."""

from __future__ import annotations

from abc import ABC, abstractmethod

from moonwalkers.contracts.pipeline_result import PipelineId, PipelineResult, Source


class Pipeline(ABC):
    """Turns a job's input sources into one ``PipelineResult``.

    Pipelines never touch the knowledge base; the orchestrator stores what they return
    (CLAUDE.md rule 6).
    """

    pipeline_id: PipelineId

    @abstractmethod
    def run(self, job_id: str, sources: list[Source]) -> PipelineResult:
        """Process ``sources`` for job ``job_id``. Use ``result_id_for`` for the result id."""


def result_id_for(job_id: str, pipeline_id: PipelineId) -> str:
    """Result id for one pipeline's output in one job (a job runs each pipeline at most once)."""
    return f"res-{job_id}-{pipeline_id.value.lower()}"
