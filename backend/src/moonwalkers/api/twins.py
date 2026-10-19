"""Twins: stored versions, what they were built from and cite, and their reviews (0014, 0015)."""

from __future__ import annotations

from pathlib import PurePosixPath

from fastapi import APIRouter, HTTPException

from moonwalkers.contracts.pipeline_result import Citation, PipelineResult, Source, TwinRecord
from moonwalkers.kb import TwinReview, validate_machine_key
from moonwalkers.workspace import run_images, run_outputs

from .context import ApiContext, Context, expected_errors
from .models import CitationUse, MachineTwins, ReviewRequest, SourceUse, TwinDetail, TwinVersion

router = APIRouter(prefix="/api/twins", tags=["twins"])


@router.get("")
def list_twins(ctx: Context) -> list[MachineTwins]:
    """Every machine with a twin, and its versions newest first."""
    return [machine_twins(ctx, key) for key in ctx.kb.list_machines()]


@router.get("/{manufacturer}/{model}")
def get_machine(manufacturer: str, model: str, ctx: Context) -> MachineTwins:
    key = known_key(ctx, manufacturer, model)
    return machine_twins(ctx, key)


@router.get("/{manufacturer}/{model}/versions/{version}")
def get_version(manufacturer: str, model: str, version: int, ctx: Context) -> TwinDetail:
    """One twin version: its results, every source with what cites it, images and files."""
    key = known_key(ctx, manufacturer, model)
    twin = ctx.kb.get_twin(key, version)
    if twin is None:
        raise HTTPException(404, f"no twin {key}@v{version}")
    with expected_errors():
        results = [r for rid in twin.built_from if (r := ctx.kb.get_result(rid)) is not None]
    run = run_of(twin)
    run_dir = ctx.data_dir / run if run else None
    in_run = run_dir is not None and run_dir.is_dir()
    return TwinDetail(
        version=twin_version(ctx, twin, ctx.orchestrator().reusable_twin(key)),
        reviews=ctx.kb.list_reviews(key, version),
        results=results,
        sources=source_uses(ctx, results),
        images=run_images(ctx.workspace, run_dir) if in_run and run_dir else [],
        outputs=run_outputs(ctx.workspace, run_dir) if in_run and run_dir else [],
    )


@router.post("/{manufacturer}/{model}/versions/{version}/reviews", status_code=201)
def review_version(
    manufacturer: str, model: str, version: int, review: ReviewRequest, ctx: Context
) -> TwinReview:
    """Approve or reject a twin version, with a reason (decision 0015). Reviews are added, never
    changed; the latest one decides the version's review status."""
    with expected_errors(), ctx.lock:
        key = validate_machine_key(f"{manufacturer}/{model}")
        return ctx.orchestrator().review_twin(
            key, version, review.decision, review.reviewer, review.reason
        )


# ------------------------------------------------------------------------------------- helpers
def known_key(ctx: ApiContext, manufacturer: str, model: str) -> str:
    with expected_errors():
        key = validate_machine_key(f"{manufacturer}/{model}")
    if not ctx.kb.list_versions(key):
        raise HTTPException(404, f"no twin for {key}")
    return key


def machine_twins(ctx: ApiContext, key: str) -> MachineTwins:
    reusable = ctx.orchestrator().reusable_twin(key)
    versions = [twin_version(ctx, t, reusable) for t in reversed(ctx.kb.list_versions(key))]
    return MachineTwins(
        machine_key=key,
        reusable_version=reusable.version if reusable else None,
        versions=versions,
    )


def twin_version(ctx: ApiContext, twin: TwinRecord, reusable: TwinRecord | None) -> TwinVersion:
    """``reusable`` is the machine's reusable version (``Orchestrator.reusable_twin``)."""
    reviews = ctx.kb.list_reviews(twin.machine_key, twin.version)
    return TwinVersion(
        twin=twin,
        review_status=ctx.kb.review_status(twin),
        latest_review=reviews[-1] if reviews else None,
        reusable=reusable is not None and reusable.version == twin.version,
        run=run_of(twin),
    )


def run_of(twin: TwinRecord) -> str | None:
    """``machines/<machine>/runs/<run>`` when the twin's USD file sits in a run folder."""
    if not twin.usd_path:
        return None
    parts = PurePosixPath(twin.usd_path).parts
    if len(parts) >= 5 and parts[0] == "machines" and parts[2] == "runs":
        return "/".join(parts[:4])
    return None


def source_uses(ctx: ApiContext, results: list[PipelineResult]) -> list[SourceUse]:
    """Each source once (by id and URI), with every item in the results that cites it."""
    by_hash = ctx.input_files_by_hash()
    uses: dict[tuple[str, str], SourceUse] = {}
    for result in results:
        for source in result.sources:
            key = (source.source_id, source.uri)
            if key not in uses:
                uses[key] = SourceUse(
                    source=source, cited_by=[], local_file=local_file(ctx, source, by_hash)
                )
        uri_of = {s.source_id: s.uri for s in result.sources}
        for item, citations in cited_items(result):
            for c in citations:
                use = uses.get((c.source_id, uri_of.get(c.source_id, "")))
                if use is not None:
                    use.cited_by.append(CitationUse(item=item, locator=c.locator, quote=c.quote))
    return list(uses.values())


def cited_items(result: PipelineResult) -> list[tuple[str, list[Citation]]]:
    items: list[tuple[str, list[Citation]]] = []
    if result.identity is not None:
        items.append(("identity", result.identity.citations))
    items += [(f"fact {f.key}", f.citations) for f in result.facts]
    items += [(f"part {p.part_id}", p.citations) for p in result.parts]
    if result.scale is not None:
        items.append(("scale", result.scale.citations))
    items += [(f"joint {j.joint_id}", j.citations) for j in result.joints]
    items += [(f"control {b.behavior_id}", b.citations) for b in result.control]
    return items


def local_file(ctx: ApiContext, source: Source, by_hash: dict[str, str]) -> str | None:
    """The source's own file, or a saved copy with the same SHA-256 (for example a web page)."""
    if source.kind == "file" and (ctx.data_dir / source.uri).is_file():
        return source.uri
    return by_hash.get(source.sha256) if source.sha256 else None
