"""Pipeline B with several photos (decision 0022): the generator's slots, the run record, the
result's provenance, and the turn that squares a mesh made from corner photos."""

import hashlib
import json
import math
from collections.abc import Callable, Collection
from pathlib import Path
from typing import Any

import pytest
import trimesh

from moonwalkers.contracts.pipeline_result import InputType, Source
from moonwalkers.generators.base import GeneratorRequest, GeneratorRun, ImageTo3DGenerator
from moonwalkers.orchestrator import InputPhoto
from moonwalkers.pipelines.b import PipelineB, RunFolderConflict
from moonwalkers.pipelines.b.inspection import inspect_mesh
from moonwalkers.pipelines.b.photos import PhotoPlanError
from moonwalkers.pipelines.b.pipeline import generated_mesh


class ViewsGenerator(ImageTo3DGenerator):
    """Wraps a fake generator: records each generation's model and images, and picks a model
    for the views as the Hunyuan3D adapter does."""

    name = "views-generator"

    def __init__(self, inner: ImageTo3DGenerator, log: list, model: str = "single") -> None:
        self.inner, self.log, self.model = inner, log, model

    def fingerprint(self) -> dict[str, Any]:
        return {**self.inner.fingerprint(), "model": self.model}

    def for_views(self, views: Collection[str]) -> ImageTo3DGenerator:
        model = "single" if set(views) == {"single"} else "multi-view"
        return ViewsGenerator(self.inner, self.log, model)

    def generate(self, request: GeneratorRequest) -> GeneratorRun:
        self.log.append((self.model, dict(request.images)))
        return self.inner.generate(request)


@pytest.fixture
def corner_run(photo_run) -> tuple[list[Source], dict[str, InputPhoto], dict[str, Path]]:
    """Three photos beside the test photo: two front corners and a close-up."""
    folder = photo_run.data_dir / photo_run.photo.uri
    sources, paths = [], {}
    for source_id in ("src-ol", "src-or", "src-table"):
        path = folder.parent / f"{source_id}.png"
        path.write_bytes(f"photo {source_id}".encode())
        paths[source_id] = path
        sources.append(
            photo_run.photo.model_copy(
                update={
                    "source_id": source_id,
                    "uri": f"{Path(photo_run.photo.uri).parent.as_posix()}/{path.name}",
                }
            )
        )
    photos = {
        "src-ol": InputPhoto(view="front_operator_left"),  # type: ignore[call-arg]
        "src-or": InputPhoto(view="front_operator_right"),  # type: ignore[call-arg]
        "src-table": InputPhoto(view="detail"),  # type: ignore[call-arg]
    }
    return sources, photos, paths


def make_pipeline(photo_run, generator, reference, clock, photos) -> PipelineB:
    return PipelineB(
        generator, photo_run.data_dir, photo_run.run_dir, reference, clock=clock, photos=photos
    )


def test_corner_photos_feed_the_multi_view_model_and_are_recorded(
    photo_run, corner_run, fake_generator, test_reference, clock, write_spec
) -> None:
    sources, photos, paths = corner_run
    log: list = []
    pipeline = make_pipeline(
        photo_run, ViewsGenerator(fake_generator(), log), test_reference, clock, photos
    )
    pipeline.generate(sources)
    assert log == [("multi-view", {"front": paths["src-ol"], "left": paths["src-or"]})]

    record = json.loads((photo_run.run_dir / "generator" / "run.json").read_text("utf-8"))
    sha = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in paths.items()}
    assert record["key"] == {
        "photos": {"front": sha["src-ol"], "left": sha["src-or"]},
        "generator": {"name": "fake-generator", "seed": 0, "model": "multi-view"},
    }
    assert record["photos"]["grid"] == "corners"
    assert record["photos"]["expected_turn_deg"] == 45.0
    assert record["generator"]["params"]["photos"] == {"front": "src-ol", "left": "src-or"}

    write_spec(photo_run.run_dir)
    result = pipeline.run("job-1", sources)
    assert len(log) == 1  # the mesh was reused
    ids = [s.source_id for s in result.sources]
    assert ids[:3] == ["src-ol", "src-or", "src-table"]  # every machine photo, evidence too
    assert all(s.sha256 == sha[s.source_id] for s in result.sources[:3])
    for part in result.parts:
        assert [c.source_id for c in part.citations] == ["src-ol", "src-or", "src-geometry-spec"]
        assert part.generator.params["photos"] == {"front": "src-ol", "left": "src-or"}
    messages = [i.message for i in result.issues]
    assert any("Guessed by the generator: the back." in m for m in messages)
    assert "Evidence photos, which the generator did not get: src-table (detail)." in messages
    assert not any(m.startswith("Made from one photo") for m in messages)


def test_one_photo_keeps_the_pocs_record_key(photo_run, fake_generator, clock) -> None:
    log: list = []
    pipeline = make_pipeline(photo_run, ViewsGenerator(fake_generator(), log), None, clock, {})
    pipeline.generate([photo_run.photo])
    record = json.loads((photo_run.run_dir / "generator" / "run.json").read_text("utf-8"))
    sha = hashlib.sha256((photo_run.data_dir / photo_run.photo.uri).read_bytes()).hexdigest()
    assert record["key"] == {
        "photo_sha256": sha,
        "generator": {"name": "fake-generator", "seed": 0, "model": "single"},
    }
    assert [model for model, _ in log] == ["single"]
    assert list(log[0][1]) == ["single"]
    assert record["photos"]["fed"] == [{"slot": "single", "source_id": "src-photo", "view": None}]


def test_a_run_made_before_several_photos_is_still_reused(photo_run, fake_generator, clock) -> None:
    """A PoC run folder's record has no photos entry, only the one-photo key."""
    inner = fake_generator()
    pipeline = make_pipeline(photo_run, inner, None, clock, {})
    pipeline.generate([photo_run.photo])
    path = photo_run.run_dir / "generator" / "run.json"
    record = json.loads(path.read_text("utf-8"))
    del record["photos"]
    del record["generator"]["params"]["photos"]
    path.write_text(json.dumps(record), encoding="utf-8")
    again = make_pipeline(photo_run, inner, None, clock, {}).generate([photo_run.photo])
    assert inner.calls == 1
    assert again.mesh_path == generated_mesh(photo_run.run_dir)


def test_other_photos_in_the_same_run_folder_are_refused(
    photo_run, corner_run, fake_generator, clock
) -> None:
    sources, photos, _ = corner_run
    make_pipeline(photo_run, fake_generator(), None, clock, photos).generate(sources)
    swapped = {**photos, "src-or": InputPhoto(view="front_operator_right", use="evidence")}
    with pytest.raises(RunFolderConflict, match="other photos"):
        make_pipeline(photo_run, fake_generator(), None, clock, swapped).generate(sources)


def test_photos_that_break_the_rules_are_refused_before_generating(
    photo_run, corner_run, fake_generator, clock
) -> None:
    sources, photos, _ = corner_run
    generator = fake_generator()
    without_view = {k: v for k, v in photos.items() if k != "src-or"}
    with pytest.raises(PhotoPlanError, match="have no view"):
        make_pipeline(photo_run, generator, None, clock, without_view).generate(sources)
    document = photo_run.photo.model_copy(
        update={"source_id": "src-doc", "input_type": InputType.PDF_CATALOG}
    )
    with pytest.raises(ValueError, match="takes machine photos"):
        make_pipeline(photo_run, generator, None, clock, {}).generate([photo_run.photo, document])
    assert generator.calls == 0


# --------------------------------------------------------------------------------- the turn
@pytest.fixture
def turned_indexer(indexer) -> Callable[[], trimesh.Trimesh]:
    """The test indexer with its front turned 30° from +X towards +Y, as corner photos leave it."""

    def build() -> trimesh.Trimesh:
        mesh = indexer()
        mesh.apply_transform(trimesh.transformations.rotation_matrix(math.radians(30), (0, 0, 1)))
        return mesh

    return build


def test_yaw_deg_squares_a_turned_mesh_for_inspection_and_assembly(
    photo_run, turned_indexer, generator_for, test_reference, clock, write_spec, tmp_path
) -> None:
    pipeline = make_pipeline(photo_run, generator_for(turned_indexer), test_reference, clock, {})
    mesh = pipeline.generate([photo_run.photo]).mesh_path

    turned = inspect_mesh(mesh, tmp_path / "turned", "+y", "+z")
    assert turned.footprint_deg == pytest.approx(-60.0, abs=1.0)  # the 3-unit width, turned
    squared = inspect_mesh(mesh, tmp_path / "squared", "+y", "+z", yaw_deg=30.0)
    assert squared.footprint_deg is not None
    assert abs(abs(squared.footprint_deg) - 90.0) < 1.0  # square again: the width along y
    assert squared.axis_yz == pytest.approx((0.0, 0.2), abs=1e-3)

    write_spec(photo_run.run_dir, yaw_deg=30.0)
    result = pipeline.run("job-1", [photo_run.photo])
    spindle = next(p for p in result.parts if p.part_id == "spindle")
    scale = 0.1016 / 1.2
    assert spindle.bbox_max_m[0] == pytest.approx(0.6 * scale, abs=1e-6)  # nose 0.6 ahead
    assert spindle.bbox_min_m[1] == pytest.approx(-0.4 * scale, abs=1e-3)  # centred on y = 0
    turn = [i for i in result.issues if "turned back" in i.message]
    assert len(turn) == 1 and "+30°" in turn[0].message
