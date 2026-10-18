"""Agent orchestrator core: run a job's pipelines, then reuse or version the machine's twin.

One job (README, "Twin reuse: the request flow"; decision 0009):

1. If the request names the machine and its twin exists, reuse it without running any pipeline.
2. Otherwise route the inputs to their pipelines and run them.
3. Work out the machine key from the results; if that machine's twin exists, reuse it.
4. Otherwise, or when the user asks for a new version, store the results and a new twin version.
   With an ``exporter``, the new version is written out (for example as USD) first and its file
   becomes the twin's ``usd_path``; if the export fails, nothing is stored.

The orchestrator is the only component that writes to the knowledge base (CLAUDE.md rule 6).
New twins always get status ``needs_review``: v1 keeps a human in the loop (docs/methodology.md).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from moonwalkers.clock import Clock, utc_now
from moonwalkers.contracts.pipeline_result import (
    JobResult,
    PipelineId,
    PipelineResult,
    Source,
    TwinRecord,
)
from moonwalkers.kb import KnowledgeBase, machine_key
from moonwalkers.pipelines import Pipeline

from .router import route

Exporter = Callable[[TwinRecord, Sequence[PipelineResult]], str]
"""Writes a new twin version out and returns the file's path relative to the data folder."""


class MachineHint(BaseModel):
    """The machine, when the user or agent already knows it (for example from a nameplate)."""

    model_config = ConfigDict(extra="forbid")

    manufacturer: str
    model: str


class JobRequest(BaseModel):
    """One request to build, or find, a machine's twin."""

    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    sources: list[Source] = Field(default_factory=list)
    machine: MachineHint | None = None
    new_version: bool = False  # the user asked for a rebuild even though a twin exists


class OrchestratorError(Exception):
    """A job could not be completed."""


class NoInputsError(OrchestratorError):
    """No source has an input type that a pipeline handles."""


class PipelineUnavailableError(OrchestratorError):
    """An input needs a pipeline that is not available yet."""


class UnidentifiedMachineError(OrchestratorError):
    """Neither the request nor any pipeline result names the machine."""


class Orchestrator:
    """Runs jobs against a knowledge base and a set of pipelines."""

    def __init__(
        self,
        kb: KnowledgeBase,
        pipelines: Mapping[PipelineId, Pipeline],
        clock: Clock = utc_now,
        exporter: Exporter | None = None,
    ) -> None:
        self.kb = kb
        self.pipelines = dict(pipelines)
        self.clock = clock
        self.exporter = exporter

    def run_job(self, request: JobRequest) -> JobResult:
        hinted_key = None
        if request.machine is not None:
            hinted_key = machine_key(request.machine.manufacturer, request.machine.model)
            if not request.new_version:
                existing = self.kb.get_twin(hinted_key)
                if existing is not None:
                    return _reused(request.job_id, existing)

        results = self._run_pipelines(request)
        key, notes = _choose_machine_key(hinted_key, results)

        if not request.new_version:
            existing = self.kb.get_twin(key)
            if existing is not None:
                detail = (
                    f" It was identified after running {_pipeline_list(results)}; "
                    "those results were not stored."
                )
                return _reused(request.job_id, existing, detail)
        return self._store_new_version(request.job_id, key, results, notes)

    def _run_pipelines(self, request: JobRequest) -> list[PipelineResult]:
        routed = route(request.sources)
        if not routed:
            raise NoInputsError(
                f"job {request.job_id}: no input that a pipeline can process "
                "(each input source needs an input type)"
            )
        missing = [pid for pid in routed if pid not in self.pipelines]
        if missing:
            needs = "; ".join(
                f"Pipeline {pid.value} for "
                + ", ".join(sorted({s.input_type.value for s in routed[pid] if s.input_type}))
                for pid in missing
            )
            raise PipelineUnavailableError(f"job {request.job_id}: not available yet: {needs}")

        results = []
        for pid, sources in routed.items():
            result = self.pipelines[pid].run(request.job_id, sources)
            if result.pipeline != pid or result.job_id != request.job_id:
                raise OrchestratorError(
                    f"Pipeline {pid.value} returned a result for Pipeline {result.pipeline.value}, "
                    f"job {result.job_id} (expected job {request.job_id})"
                )
            results.append(result)
        return results

    def _store_new_version(
        self, job_id: str, key: str, results: list[PipelineResult], notes: str | None
    ) -> JobResult:
        previous = self.kb.get_twin(key)
        version = previous.version + 1 if previous is not None else 1
        twin = TwinRecord(
            twin_id=f"{key}@v{version}",
            machine_key=key,
            version=version,
            status="needs_review",
            built_from=[r.result_id for r in results],
            created_at=self.clock(),
            notes=notes,
        )
        if self.exporter is not None:  # before storing anything, so a failed export leaves no trace
            usd_path = self.exporter(twin, results)
            twin = TwinRecord.model_validate({**twin.model_dump(), "usd_path": usd_path})
        for result in results:  # results first, so a stored twin never points at missing results
            self.kb.save_result(result)
        self.kb.save_twin(twin)

        ran = _pipeline_list(results)
        if previous is None:
            message = f"No twin found for {key}; built version 1 from {ran}."
        else:
            message = (
                f"Built version {version} of the {key} twin as requested "
                f"(previous: v{previous.version}) from {ran}."
            )
        if twin.usd_path:
            message += f" Exported to {twin.usd_path}."
        message += " It needs human review."
        if notes:
            message += f" Note: {notes}"
        return JobResult(job_id=job_id, twin=twin, reused_existing=False, message=message)


def _choose_machine_key(
    hinted_key: str | None, results: list[PipelineResult]
) -> tuple[str, str | None]:
    """The machine key to use, plus a note when the request and pipelines disagree.

    The request's machine wins; otherwise the most confident identity (ties: earliest pipeline).
    """
    candidates = [
        (r.identity.confidence, r.pipeline, machine_key(r.identity.manufacturer, r.identity.model))
        for r in results
        if r.identity is not None and r.identity.manufacturer and r.identity.model
    ]
    if hinted_key is not None:
        chosen = hinted_key
    elif candidates:
        chosen = max(candidates, key=lambda c: c[0])[2]
    else:
        raise UnidentifiedMachineError(
            "no pipeline identified the machine (manufacturer and model) and the request does not "
            "name it; add a nameplate photo or name the machine in the request"
        )

    others = [
        f"Pipeline {pid.value} said {key} (confidence {conf:.2f})"
        for conf, pid, key in candidates
        if key != chosen
    ]
    if not others:
        return chosen, None
    where = " (named in the request)" if hinted_key is not None else ""
    return chosen, f"Machine identity disagreement; used {chosen}{where}. {'; '.join(others)}."


def _reused(job_id: str, twin: TwinRecord, detail: str = "") -> JobResult:
    status = twin.status.replace("_", " ")
    return JobResult(
        job_id=job_id,
        twin=twin,
        reused_existing=True,
        message=(
            f"Found an existing twin (v{twin.version}, {status}) for {twin.machine_key}; "
            f"reused it.{detail} Ask for a new version to rebuild it."
        ),
    )


def _pipeline_list(results: list[PipelineResult]) -> str:
    ids = [r.pipeline.value for r in results]
    return ("Pipeline " if len(ids) == 1 else "Pipelines ") + ", ".join(ids)
