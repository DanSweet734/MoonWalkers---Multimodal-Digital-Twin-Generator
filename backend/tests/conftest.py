"""Shared fixtures."""

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import trimesh

from moonwalkers.contracts.pipeline_result import (
    Citation,
    ControlBehavior,
    Fact,
    Generator,
    InputType,
    Issue,
    MachineIdentity,
    PipelineResult,
    Source,
)
from moonwalkers.generators.base import GeneratorRequest, GeneratorRun, ImageTo3DGenerator
from moonwalkers.kb import JsonKnowledgeBase, KnowledgeBase
from moonwalkers.pipelines.b.mesh_tools import orientation_matrix, transformed
from moonwalkers.pipelines.b.pipeline import ReferenceFacts

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
def rotary_table() -> Callable[[], trimesh.Trimesh]:
    """A synthetic rotary table in the twin frame whose base reaches past its spindle, like the
    TH240: a 2 x 3 x 2 box body (base at z = -1), a round platter of radius 0.6 from x = 1 to
    x = 1.3 on the axis y = 0, z = 0.2, and two feet along the bottom (z = -1 to -0.8, at
    y = +-1.2) that reach to x = 1.6, past the platter. The tip slabs measure the feet."""

    def build() -> trimesh.Trimesh:
        body = trimesh.creation.box(extents=(2.0, 3.0, 2.0))
        platter = trimesh.creation.cylinder(radius=0.6, height=0.3, sections=64)
        platter.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, (0, 1, 0)))
        platter.apply_translation((1.15, 0.0, 0.2))
        feet = []
        for y in (-1.2, 1.2):
            foot = trimesh.creation.box(extents=(2.6, 0.4, 0.2))
            foot.apply_translation((0.3, y, -0.9))
            feet.append(foot)
        return trimesh.util.concatenate([body, platter, *feet])

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


# ------------------------------------------------------------------------------- Pipeline B
class FakeGenerator(ImageTo3DGenerator):
    """Writes the synthetic indexer the way a glTF generator would (+Y up, front facing +Z)."""

    name = "fake-generator"

    def __init__(self, build: Callable[[], trimesh.Trimesh], seed: int = 0) -> None:
        self.build = build
        self.seed = seed
        self.calls = 0

    def fingerprint(self) -> dict[str, Any]:
        return {"name": self.name, "seed": self.seed}

    def generate(self, request: GeneratorRequest) -> GeneratorRun:
        self.calls += 1
        out_dir = Path(request.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        mesh_path, log_path = out_dir / "mesh.glb", out_dir / "generator.log"
        to_gltf = np.linalg.inv(orientation_matrix(up="+y", front="+z"))
        transformed(self.build(), to_gltf).export(mesh_path)
        log_path.write_text("fake generator ran", encoding="utf-8")
        details = {"timings_s": {"generate": 0.1}, "versions": {"fake": "0"}, "device": "cpu"}
        return GeneratorRun(
            mesh_path=mesh_path,
            generator=Generator(name=self.name, version="0", params=self.fingerprint()),
            seconds=0.1,
            peak_vram_gb=None,
            log_path=log_path,
            details=details,
        )


@pytest.fixture
def fake_generator(indexer: Callable[[], trimesh.Trimesh]) -> Callable[..., FakeGenerator]:
    return lambda seed=0: FakeGenerator(indexer, seed)


@pytest.fixture
def generator_for() -> Callable[..., FakeGenerator]:
    """A fake generator for another synthetic machine, such as ``rotary_table``."""
    return lambda build, seed=0: FakeGenerator(build, seed)


@dataclass(frozen=True)
class PhotoRun:
    data_dir: Path
    run_dir: Path
    photo: Source


@pytest.fixture
def photo_run(tmp_path: Path) -> PhotoRun:
    """A data folder with one photo of the test indexer and an empty run folder for it."""
    data_dir = tmp_path / "data"
    machine = data_dir / "machines" / "moonwalkers-testindexer"
    photo_path = machine / "inputs" / "photos" / "indexer.png"
    photo_path.parent.mkdir(parents=True)
    photo_path.write_bytes(b"not really a photo; the fake generator never opens it")
    photo = Source(
        source_id="src-photo",
        kind="file",
        input_type=InputType.MACHINE_PHOTO,
        uri=photo_path.relative_to(data_dir).as_posix(),
        title="Test photo",
        retrieved_at=FIXED_TIME,
    )
    return PhotoRun(data_dir, machine / "runs" / "run-001", photo)


@pytest.fixture
def write_spec() -> Callable[..., Path]:
    """Writes the test indexer's geometry spec (spindle axis y = 0, z = 0.2; base z = -1)."""

    def write(run_dir: Path, **changes: Any) -> Path:
        spec = {
            "up": "+y",
            "front": "+z",
            "spindle_axis_yz": [0.0, 0.2],
            "spindle_radius": 0.45,
            "spindle_start_x": 1.0,
            "center_height_m": 0.1016,
            "decided_by": "test",
            "method": "known synthetic geometry",
        } | changes
        path = run_dir / "geometry_spec.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(spec), encoding="utf-8")
        return path

    return write


@pytest.fixture
def test_reference() -> ReferenceFacts:
    """Synthetic reference facts for the test indexer. With the scale 0.1016 / 1.2 m per unit,
    its 3-unit width is 0.254 m (matches) and its 2-unit height is 0.169 m (0.3 m is cited)."""
    cite = [Citation(source_id="src-test-sheet")]
    return ReferenceFacts(
        sources=[
            Source(
                source_id="src-test-sheet",
                kind="user_input",
                uri="user",
                title="Synthetic data sheet for the test indexer",
                retrieved_at=FIXED_TIME,
            )
        ],
        identity=MachineIdentity(
            manufacturer="MoonWalkers", model="Test Indexer", confidence=1.0, citations=cite
        ),
        facts=[
            Fact(key="center_height", value=0.1016, unit="m", confidence=1.0, citations=cite),
            Fact(key="max_spindle_speed", value=1.5, unit="rad/s", confidence=1.0, citations=cite),
            Fact(key="overall_width", value=0.254, unit="m", confidence=1.0, citations=cite),
            Fact(key="overall_height", value=0.3, unit="m", confidence=0.5, citations=cite),
        ],
        control=[
            ControlBehavior(
                behavior_id="index_program",
                name="Test program",
                kind="program_interpreter",
                description="Steps the spindle.",
                drives_joints=["spindle_rotation"],
                confidence=1.0,
                citations=cite,
            )
        ],
        issues=[Issue(severity="info", message="Synthetic reference facts for tests.")],
    )
