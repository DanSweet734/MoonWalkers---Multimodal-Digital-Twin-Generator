"""Sources: every document, photo or statement a stored twin cites (decision 0014)."""

from __future__ import annotations

from fastapi import APIRouter

from moonwalkers.contracts.pipeline_result import Source

from .context import Context
from .models import SourceListing
from .twins import local_file

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("")
def list_sources(ctx: Context) -> list[SourceListing]:
    """Every source cited by a stored twin, listed once per document and in the order first
    cited. A document is its URI; something a person said is its id and title."""
    by_hash = ctx.input_files_by_hash()
    listings: dict[tuple[str, ...], SourceListing] = {}
    for key in ctx.kb.list_machines():
        for twin in ctx.kb.list_versions(key):  # oldest first
            for result_id in twin.built_from:
                result = ctx.kb.get_result(result_id)
                for source in result.sources if result is not None else []:
                    listing = listings.setdefault(
                        document(source),
                        SourceListing(source=source, source_ids=[], twins=[], local_file=None),
                    )
                    listing.source = source  # the newest twin's record of it
                    listing.local_file = listing.local_file or local_file(ctx, source, by_hash)
                    if source.source_id not in listing.source_ids:
                        listing.source_ids.append(source.source_id)
                    if twin.twin_id not in listing.twins:
                        listing.twins.append(twin.twin_id)
    return list(listings.values())


def document(source: Source) -> tuple[str, ...]:
    if source.kind == "user_input":
        return ("user", source.source_id, source.title or "")
    return (source.uri,)
