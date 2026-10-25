"""Agent orchestrator core: run a job's pipelines, then reuse or version the machine's twin.

One job (README, "Twin reuse: the request flow"; decisions 0009 and 0015):

1. If the request names the machine and it has a reusable twin, reuse it without running any
   pipeline. The reusable version is the newest one a review approved; if none is approved, the
   newest one not rejected. A rejected version is never reused.
2. Otherwise route the inputs to their pipelines and run them.
3. Work out the machine key from the results; if that machine has a reusable twin, reuse it.
4. Otherwise, or when the user asks for a new version, store the results and a new twin version.
   With an ``exporter``, the new version is written out (for example as USD) first and its file
   becomes the twin's ``usd_path``; if the export fails, nothing is stored.

Several results build one version (decision 0021): at most one of them carries parts and joints,
and facts that two results give different values are listed in the twin's notes for the
reviewer, without picking one. An input whose pipeline is not in yet is refused.

The orchestrator is the only component that writes to the knowledge base (CLAUDE.md rule 6), and
that includes reviews. New twins always get status ``needs_review``: v1 keeps a human in the loop
(docs/methodology.md). Only a person's review approves or rejects one (``review_twin``).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from moonwalkers.clock import Clock, utc_now
from moonwalkers.contracts.pipeline_result import (
    Fact,
    InputType,
    JobResult,
    PipelineId,
    PipelineResult,
    Source,
    TwinRecord,
)
from moonwalkers.kb import (
    KnowledgeBase,
    ReviewDecision,
    TwinReview,
    machine_key,
    validate_machine_key,
)
from moonwalkers.pipelines import OWNERS, Pipeline

from .photos import InputPhoto
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
    # Each machine photo's view and use, by source id (decision 0022). A request with one machine
    # photo may leave it out, as the PoC's requests do.
    photos: dict[str, InputPhoto] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_photos(self) -> JobRequest:
        machine_photos = {
            s.source_id for s in self.sources if s.input_type == InputType.MACHINE_PHOTO
        }
        unknown = sorted(set(self.photos) - machine_photos)
        if unknown:
            raise ValueError(
                f"photos names {unknown}, which are not machine photos among the request's sources"
            )
        return self


class OrchestratorError(Exception):
    """A job could not be completed."""


class NoInputsError(OrchestratorError):
    """No source has an input type that a pipeline handles."""


class PipelineUnavailableError(OrchestratorError):
    """An input needs a pipeline that is not available yet."""


class UnidentifiedMachineError(OrchestratorError):
    """Neither the request nor any pipeline result names the machine."""


class TwinNotFoundError(OrchestratorError):
    """No twin version with that machine key and version is stored."""


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
        reused = self.reuse(request)
        if reused is not None:
            return reused
        hinted_key = None
        if request.machine is not None:
            hinted_key = machine_key(request.machine.manufacturer, request.machine.model)

        results = self._run_pipelines(request)
        key, notes = _choose_machine_key(hinted_key, results)

        if not request.new_version:
            existing = self.reusable_twin(key)
            if existing is not None:
                detail = (
                    f" It was identified after running {_pipeline_list(results)}; "
                    "those results were not stored."
                )
                return self._reused(request.job_id, existing, detail)
        return self._store_new_version(request.job_id, key, results, notes, request.new_version)

    def reuse(self, request: JobRequest) -> JobResult | None:
        """Step 1 alone: when the request names its machine, asks for no new version, and that
        machine has a reusable twin, the job's result reusing it. Otherwise None: the request
        needs its pipelines run. Stores nothing and runs nothing."""
        if request.machine is None or request.new_version:
            return None
        key = machine_key(request.machine.manufacturer, request.machine.model)
        existing = self.reusable_twin(key)
        return None if existing is None else self._reused(request.job_id, existing)

    def reusable_twin(self, key: str) -> TwinRecord | None:
        """The version a request for this machine reuses (decision 0015): the newest one a review
        approved, so an unreviewed rebuild never replaces an approved twin; if none is approved,
        the newest one not rejected. None if every version was rejected (or there is none)."""
        newest_first = [(t, self.kb.review_status(t)) for t in reversed(self.kb.list_versions(key))]
        for wanted in ({"approved"}, {"draft", "needs_review"}):
            twin = next((t for t, status in newest_first if status in wanted), None)
            if twin is not None:
                return twin
        return None

    def review_twin(
        self, key: str, version: int, decision: ReviewDecision, reviewer: str, reason: str
    ) -> TwinReview:
        """Record a person's review of one twin version (decision 0015). Reviews are added, never
        changed: a second review of the same version is stored after the first and decides its
        review status from then on."""
        key = validate_machine_key(key)
        if self.kb.get_twin(key, version) is None:
            raise TwinNotFoundError(f"no twin {key}@v{version} is stored")
        review = TwinReview(
            machine_key=key,
            version=version,
            number=len(self.kb.list_reviews(key, version)) + 1,
            decision=decision,
            reviewer=reviewer,
            reason=reason,
            reviewed_at=self.clock(),
        )
        self.kb.save_review(review)
        return review

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
                + f" ({OWNERS[pid]}'s)"
                for pid in missing
            )
            raise PipelineUnavailableError(
                f"job {request.job_id}: not available yet: {needs}. A pipeline runs once its "
                "owner's create_pipeline() returns it instead of the stub (decision 0021)."
            )

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
        self,
        job_id: str,
        key: str,
        results: list[PipelineResult],
        notes: str | None,
        requested: bool,
    ) -> JobResult:
        _check_one_geometry(results)
        notes = " ".join(n for n in (notes, _fact_disagreements(results)) if n) or None
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
        elif requested:
            message = (
                f"Built version {version} of the {key} twin as requested "
                f"(previous: v{previous.version}) from {ran}."
            )
        else:
            message = (
                f"Every stored version of the {key} twin was rejected in review, so built "
                f"version {version} (previous: v{previous.version}) from {ran}."
            )
        if twin.usd_path:
            message += f" Exported to {twin.usd_path}."
        message += " It needs human review."
        if notes:
            message += f" Note: {notes}"
        return JobResult(job_id=job_id, twin=twin, reused_existing=False, message=message)

    def _reused(self, job_id: str, twin: TwinRecord, detail: str = "") -> JobResult:
        status = self.kb.review_status(twin).replace("_", " ")
        # Newer versions are skipped when rejected, or when this one is approved and they are not.
        newer = [
            f"v{t.version} ({self.kb.review_status(t).replace('_', ' ')})"
            for t in self.kb.list_versions(twin.machine_key)
            if t.version > twin.version
        ]
        skipped = f" Newer versions were not reused: {', '.join(newer)}." if newer else ""
        return JobResult(
            job_id=job_id,
            twin=twin,
            reused_existing=True,
            message=(
                f"Found an existing twin (v{twin.version}, {status}) for {twin.machine_key}; "
                f"reused it.{skipped}{detail} Ask for a new version to rebuild it."
            ),
        )


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


def _check_one_geometry(results: list[PipelineResult]) -> None:
    """At most one result carries parts and joints (decision 0021): the contract keeps a joint's
    parts in its own result, so two results' parts could not form one tree."""
    with_geometry = [r for r in results if r.parts or r.joints]
    if len(with_geometry) > 1:
        raise OrchestratorError(
            f"{_pipeline_list(with_geometry)} each carry parts or joints; one result per twin "
            "carries the geometry (decision 0021). Nothing was stored."
        )


def _fact_disagreements(results: list[PipelineResult]) -> str | None:
    """A note naming each pipeline's value for every fact the results disagree on, for the
    reviewer to settle; none is picked (decision 0021)."""
    by_key: dict[str, list[tuple[PipelineId, Fact]]] = {}
    for result in results:
        for fact in result.facts:
            by_key.setdefault(fact.key, []).append((result.pipeline, fact))
    disagreements = []
    for key, given in by_key.items():
        first = given[0][1]
        if all(_agree(first, fact) for _, fact in given[1:]):
            continue
        values = ", ".join(
            f"Pipeline {pid.value} {fact.value}{' ' + fact.unit if fact.unit else ''}"
            for pid, fact in given
        )
        disagreements.append(f"{key}: {values}")
    if not disagreements:
        return None
    return "Fact disagreements, for the reviewer: " + "; ".join(disagreements) + "."


def _agree(a: Fact, b: Fact) -> bool:
    """Numbers in the same unit within 0.5% (rounding, such as 3-1/4 in and 82.5 mm), text
    ignoring case and outer spaces, anything else equal."""
    if a.unit != b.unit:
        return False
    numbers = (int, float)
    if all(isinstance(v, numbers) and not isinstance(v, bool) for v in (a.value, b.value)):
        return math.isclose(a.value, b.value, rel_tol=0.005)
    if isinstance(a.value, str) and isinstance(b.value, str):
        return a.value.strip().casefold() == b.value.strip().casefold()
    return a.value == b.value


def _pipeline_list(results: list[PipelineResult]) -> str:
    ids = [r.pipeline.value for r in results]
    return ("Pipeline " if len(ids) == 1 else "Pipelines ") + ", ".join(ids)
