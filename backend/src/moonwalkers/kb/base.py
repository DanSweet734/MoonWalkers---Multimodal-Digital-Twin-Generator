"""The knowledge base interface (decision 0005).

Only the orchestrator writes to the knowledge base (CLAUDE.md rule 6). The PoC implementation keeps
JSON files (decision 0008); a Neo4j implementation follows in the integration phase. Records are
append-only: a stored pipeline result, twin version or review is never overwritten, so every
earlier version and decision stays available.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from moonwalkers.contracts.pipeline_result import PipelineResult, Source, TwinRecord

from .reviews import ReviewStatus, TwinReview, review_status


class KnowledgeBaseError(Exception):
    """Base class for knowledge base errors."""


class AlreadyExistsError(KnowledgeBaseError):
    """A record with the same id (or machine key and version) is already stored."""


class InvalidIdError(KnowledgeBaseError, ValueError):
    """An id cannot be used as a record name."""


class KnowledgeBase(ABC):
    """Stores pipeline results and versioned twin records."""

    @abstractmethod
    def save_result(self, result: PipelineResult) -> None:
        """Store a pipeline result. Raises ``AlreadyExistsError`` if its ``result_id`` is taken."""

    @abstractmethod
    def get_result(self, result_id: str) -> PipelineResult | None:
        """The stored result with this id, or None."""

    @abstractmethod
    def save_twin(self, twin: TwinRecord) -> None:
        """Store a twin version. Raises ``AlreadyExistsError`` if that key and version exist."""

    @abstractmethod
    def get_twin(self, machine_key: str, version: int | None = None) -> TwinRecord | None:
        """One version of a machine's twin (the latest when ``version`` is None), or None."""

    @abstractmethod
    def list_versions(self, machine_key: str) -> list[TwinRecord]:
        """Every stored version of a machine's twin, oldest first; empty if there are none."""

    @abstractmethod
    def list_machines(self) -> list[str]:
        """Machine keys that have at least one twin version, sorted."""

    @abstractmethod
    def save_review(self, review: TwinReview) -> None:
        """Store a review (decision 0015). Raises ``AlreadyExistsError`` if that twin version
        already has a review with the same number."""

    @abstractmethod
    def list_reviews(self, machine_key: str, version: int) -> list[TwinReview]:
        """A twin version's reviews, oldest first; empty if there are none."""

    def review_status(self, twin: TwinRecord) -> ReviewStatus:
        """The twin version's latest review decision, or the status it was stored with."""
        return review_status(twin, self.list_reviews(twin.machine_key, twin.version))

    def sources_for_twin(self, twin: TwinRecord) -> list[Source]:
        """Every source behind a twin, from the results it was built from.

        Sources are stored inside the results that cite them; a source that several results
        share (same id and URI) is listed once.
        """
        sources: list[Source] = []
        seen: set[tuple[str, str]] = set()
        for result_id in twin.built_from:
            result = self.get_result(result_id)
            if result is None:
                raise KnowledgeBaseError(
                    f"twin {twin.twin_id} was built from result {result_id!r}, which is not stored"
                )
            for source in result.sources:
                if (source.source_id, source.uri) not in seen:
                    seen.add((source.source_id, source.uri))
                    sources.append(source)
        return sources
