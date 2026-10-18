"""Shared fixtures."""

import math
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
import trimesh

from moonwalkers.contracts.pipeline_result import InputType, PipelineResult, Source
from moonwalkers.kb import JsonKnowledgeBase, KnowledgeBase

FIXTURES = Path(__file__).parent / "fixtures"
FIXED_TIME = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)

SourceFactory = Callable[[str, InputType | None], Source]


@pytest.fixture
def indexer() -> Callable[[], trimesh.Trimesh]:
    """Builds a synthetic indexer in the twin frame: a 2 x 3 x 2 box centred at the origin (base at
    z = -1) with a spindle of radius 0.4 from x = 1 to x = 1.6 on the axis y = 0, z = 0.2."""

    def build() -> trimesh.Trimesh:
        body = trimesh.creation.box(extents=(2.0, 3.0, 2.0))
        spindle = trimesh.creation.cylinder(radius=0.4, height=0.6, sections=32)
        spindle.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, (0, 1, 0)))
        spindle.apply_translation((1.3, 0.0, 0.2))
        return trimesh.util.concatenate([body, spindle])

    return build


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
