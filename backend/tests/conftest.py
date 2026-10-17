"""Shared fixtures."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from moonwalkers.contracts.pipeline_result import InputType, PipelineResult, Source
from moonwalkers.kb import JsonKnowledgeBase, KnowledgeBase

FIXTURES = Path(__file__).parent / "fixtures"
FIXED_TIME = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)

SourceFactory = Callable[[str, InputType | None], Source]


@pytest.fixture
def clock() -> Callable[[], datetime]:
    """A clock that always returns FIXED_TIME."""
    return lambda: FIXED_TIME


@pytest.fixture
def fixed_time() -> datetime:
    return FIXED_TIME


@pytest.fixture
def b_fixture_path() -> Path:
    """The illustrative Pipeline B result for the HA5C."""
    return FIXTURES / "ha5c_pipeline_b.example.json"


@pytest.fixture
def example_result(b_fixture_path: Path) -> PipelineResult:
    return PipelineResult.model_validate_json(b_fixture_path.read_text(encoding="utf-8"))


@pytest.fixture
def make_source() -> SourceFactory:
    """Build an input source; ``input_type=None`` makes a user-typed source."""

    def make(source_id: str, input_type: InputType | None) -> Source:
        if input_type is None:
            return Source(
                source_id=source_id, kind="user_input", uri="user", retrieved_at=FIXED_TIME
            )
        return Source(
            source_id=source_id,
            kind="file",
            input_type=input_type,
            uri=f"machines/haas-ha5c/inputs/{source_id}",
            retrieved_at=FIXED_TIME,
        )

    return make


@pytest.fixture(params=["json"])
def kb(request: pytest.FixtureRequest, tmp_path: Path) -> KnowledgeBase:
    """Each knowledge base implementation in turn (add Neo4j here when it exists)."""
    if request.param == "json":
        return JsonKnowledgeBase(tmp_path / "kb")
    raise ValueError(request.param)
