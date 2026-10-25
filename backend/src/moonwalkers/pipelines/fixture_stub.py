"""A stand-in pipeline that returns stored fixture data (decision 0002: A, C and D are stubs)."""

from __future__ import annotations

import json
from pathlib import Path

from moonwalkers.clock import Clock, utc_now
from moonwalkers.contracts.pipeline_result import PipelineId, PipelineResult, Source

from .base import Pipeline, result_id_for

STUB_NOTICE = (
    "Stub output: fixture data for the Haas HA5C, not derived from this job's inputs "
    "(decision 0002)."
)


class FixturePipeline(Pipeline):
    """Returns the ``PipelineResult`` stored in ``fixture`` for every job.

    The fixture's facts are real and cited, but they do not come from the job's inputs, so each
    result carries an ``info`` issue saying so and always needs human review. The job id, result
    id, timestamp and input types are filled in per run. Only the tests run it (decision 0021).
    """

    stub = True

    def __init__(self, pipeline_id: PipelineId, fixture: Path, clock: Clock = utc_now) -> None:
        self.pipeline_id = pipeline_id
        self.fixture = Path(fixture)
        self.clock = clock

    def run(self, job_id: str, sources: list[Source]) -> PipelineResult:
        payload = json.loads(self.fixture.read_text(encoding="utf-8"))
        if payload.get("pipeline") != self.pipeline_id.value:
            raise ValueError(
                f"{self.fixture.name} holds Pipeline {payload.get('pipeline')} data, "
                f"not Pipeline {self.pipeline_id.value}"
            )
        input_types = sorted({s.input_type.value for s in sources if s.input_type is not None})
        payload.update(
            result_id=result_id_for(job_id, self.pipeline_id),
            job_id=job_id,
            produced_at=self.clock().isoformat(),
            input_types=input_types or payload["input_types"],
            needs_human_review=True,
        )
        payload.setdefault("issues", []).append({"severity": "info", "message": STUB_NOTICE})
        return PipelineResult.model_validate(payload)
