"""Cutting the machine out of each photo (decision 0029): the request's settings, the generator
job's helpers, the adapter, Pipeline B's reuse key and record, and the preview."""

import hashlib
import importlib.util
import json
import os
import sys
from collections.abc import Collection
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from pydantic import ValidationError

from moonwalkers.generators.base import (
    CutoutRun,
    GeneratorError,
    GeneratorRequest,
    GeneratorRun,
    ImageTo3DGenerator,
)
from moonwalkers.generators.hunyuan3d import (
    DEFAULT_SCRIPT,
    Hunyuan3DConfig,
    Hunyuan3DGenerator,
    Hunyuan3DSettings,
)
from moonwalkers.orchestrator import Cutout, InputPhoto
from moonwalkers.orchestrator.photos import SAM_MODEL
from moonwalkers.pipelines.b import PipelineB, RunFolderConflict
from moonwalkers.pipelines.b.mesh_tools import read_png, write_png
from moonwalkers.pipelines.b.pipeline import describe_cutout

FAKE_SCRIPT = Path(__file__).parent / "fixtures" / "fake_generator_job.py"
SAM = {
    "method": "sam",
    "box": [0.1, 0.2, 0.9, 0.95],
    "points": [{"x": 0.5, "y": 0.5, "keep": True}],
}


def job_script() -> Any:
    """The generator job, imported for its pure helpers (it imports PIL and rembg only inside
    the functions that need them)."""
    spec = importlib.util.spec_from_file_location("hunyuan3d_shape_job", DEFAULT_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ------------------------------------------------------------------------------- the request
def test_a_sam_cutout_needs_a_box_and_takes_points() -> None:
    cutout = Cutout.model_validate(SAM)
    assert cutout.box == (0.1, 0.2, 0.9, 0.95)
    assert cutout.points[0].keep
    assert cutout.min_piece == 0.02
    with pytest.raises(ValidationError, match="needs a box"):
        Cutout.model_validate({"method": "sam", "points": SAM["points"]})


def test_a_box_runs_from_top_left_to_bottom_right_in_fractions() -> None:
    with pytest.raises(ValidationError, match="top left"):
        Cutout.model_validate({"method": "crop", "box": [0.9, 0.2, 0.1, 0.95]})
    with pytest.raises(ValidationError):
        Cutout.model_validate({"method": "crop", "box": [0, 0, 1.5, 1]})  # pixels, not fractions
    with pytest.raises(ValidationError):
        Cutout.model_validate({**SAM, "points": [{"x": 0.5, "y": -0.1, "keep": True}]})


def test_a_crop_takes_no_points_and_a_mask_takes_only_its_png() -> None:
    with pytest.raises(ValidationError, match="takes no points"):
        Cutout.model_validate({**SAM, "method": "crop"})
    Cutout.model_validate({"method": "mask", "mask": "machines/m/runs/r/masks/front.png"})
    with pytest.raises(ValidationError, match="no box or points"):
        Cutout.model_validate({"method": "mask", "mask": "front.png", "box": [0, 0, 1, 1]})
    with pytest.raises(ValidationError, match="must be a PNG"):
        Cutout.model_validate({"method": "mask", "mask": "front.jpg"})
    with pytest.raises(ValidationError, match="takes no mask"):
        Cutout.model_validate({**SAM, "mask": "front.png"})
    with pytest.raises(ValidationError):
        Cutout.model_validate({"method": "lasso", "box": [0, 0, 1, 1]})


def test_a_photo_without_a_cutout_is_saved_as_before() -> None:
    plain = InputPhoto(view="front")  # type: ignore[call-arg]
    assert plain.model_dump(mode="json") == {"view": "front", "use": "generator"}
    cut = InputPhoto.model_validate({"view": "front", "cutout": SAM})
    assert cut.model_dump(mode="json")["cutout"]["method"] == "sam"
    assert InputPhoto.model_validate_json(cut.model_dump_json()) == cut


# ------------------------------------------------------------------- edits (decision 0041)
EDITS = [
    {"op": "add", "points": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5]], "note": "the pendant"},
    {"op": "add", "points": [[0.2, 0.8], [0.6, 0.7]], "width": 0.02, "note": "the conduit"},
    {"op": "remove", "points": [[0.0, 0.0], [0.2, 0.0], [0.2, 0.1], [0.0, 0.1]]},
]


def test_edits_are_polygons_or_lines_with_a_width_in_their_order() -> None:
    cutout = Cutout.model_validate({**SAM, "edits": EDITS})
    assert [e.op for e in cutout.edits] == ["add", "add", "remove"]
    assert cutout.edits[1].width == 0.02 and cutout.edits[0].width is None
    dumped = cutout.model_dump(mode="json")["edits"]
    assert dumped == EDITS  # no "width": null or "note": null written
    with pytest.raises(ValidationError, match="a polygon needs at least 3 points"):
        Cutout.model_validate({**SAM, "edits": [{"op": "add", "points": [[0, 0], [1, 1]]}]})
    with pytest.raises(ValidationError, match="a line needs at least 2 points"):
        Cutout.model_validate({**SAM, "edits": [{"op": "add", "points": [[0, 0]], "width": 0.1}]})
    for width in (0.0, 0.25):  # above 0, at most 0.2 of the photo's width
        with pytest.raises(ValidationError):
            Cutout.model_validate(
                {**SAM, "edits": [{"op": "add", "points": [[0, 0], [1, 1]], "width": width}]}
            )
    with pytest.raises(ValidationError):  # fractions, not pixels
        Cutout.model_validate({**SAM, "edits": [{"op": "add", "points": [[0, 0], [9, 9], [0, 1]]}]})
    with pytest.raises(ValidationError):
        Cutout.model_validate({**SAM, "edits": [{"op": "paint", "points": [[0, 0]] * 3}]})


def test_edits_go_on_any_method_and_auto_needs_them() -> None:
    Cutout.model_validate({"method": "crop", "box": [0, 0, 1, 1], "edits": EDITS})
    Cutout.model_validate({"method": "mask", "mask": "m.png", "edits": EDITS})
    auto = Cutout.model_validate({"method": "auto", "edits": EDITS})
    assert auto.box is None and auto.min_piece == 0.02
    with pytest.raises(ValidationError, match="leave the cut-out out"):
        Cutout.model_validate({"method": "auto"})
    with pytest.raises(ValidationError, match="no box, points or mask"):
        Cutout.model_validate({"method": "auto", "box": [0, 0, 1, 1], "edits": EDITS})


def test_a_cutout_without_edits_is_written_as_before() -> None:
    assert "edits" not in Cutout.model_validate(SAM).model_dump(mode="json")
    photo = InputPhoto.model_validate({"view": "front", "cutout": {**SAM, "edits": EDITS}})
    assert InputPhoto.model_validate_json(photo.model_dump_json()) == photo


def test_the_jobs_edits_are_in_pixels_and_lines_at_least_one_wide() -> None:
    job = job_script()
    assert job.edit_pixels([[0.5, 0.25], [1.0, 1.0]], (400, 200)) == [(200.0, 50.0), (400.0, 200.0)]
    assert job.line_pixels(0.024, (4000, 3000)) == 96  # make_masks.py's int(width * w)
    assert job.line_pixels(0.001, (100, 100)) == 1


def test_the_jobs_iou_compares_kept_pixels() -> None:
    job = job_script()
    a = np.zeros((4, 4), dtype=np.uint8)
    b = a.copy()
    assert job.iou(a, b) == 1.0  # both empty
    a[:2, :] = 255  # 8 pixels
    b[:, :2] = 200  # 8 pixels, 4 shared
    assert job.iou(a, b) == pytest.approx(4 / 12)
    assert job.iou(a, a) == 1.0


# ------------------------------------------------------------------------- the job's helpers
def test_the_jobs_box_and_prompt_are_in_pixels_of_the_upright_photo() -> None:
    job = job_script()
    assert job.box_pixels([0.1, 0.2, 0.9, 0.95], (3000, 4000)) == (300, 800, 2700, 3800)
    cutout = {
        **SAM,
        "points": [{"x": 0.5, "y": 0.25, "keep": True}, {"x": 0.1, "y": 0.9, "keep": False}],
    }
    assert job.sam_prompt(cutout, (1000, 2000)) == [
        {"type": "rectangle", "label": 1, "data": [100, 400, 900, 1900]},
        {"type": "point", "label": 1, "data": [500.0, 500.0]},
        {"type": "point", "label": 0, "data": [100.0, 1800.0]},
    ]


def test_photos_are_shrunk_to_sams_input_before_it_sees_them() -> None:
    job = job_script()
    assert job.sam_size((3000, 4000)) == (513, 684)  # portrait: the height fits 684
    assert job.sam_size((4000, 3000)) == (912, 684)
    assert job.sam_size((4000, 2000)) == (1024, 512)  # wide: the width fits 1024
    assert job.sam_size((500, 300)) == (500, 300)  # never enlarged


# ---------------------------------------------------------------------------- the adapter
def fake_hunyuan(tmp_path: Path) -> Hunyuan3DGenerator:
    config = Hunyuan3DConfig(
        python=Path(sys.executable),
        models_dir=tmp_path / "models",
        u2net_home=tmp_path / "u2net",
        settings=Hunyuan3DSettings(),
    )
    return Hunyuan3DGenerator(config, script=FAKE_SCRIPT)


@pytest.fixture
def photo(tmp_path: Path) -> Path:
    path = tmp_path / "photo.png"
    path.write_bytes(b"not really a png; the fake job never opens it")
    return path


def test_cutouts_reach_the_job_with_masks_made_absolute(
    tmp_path: Path, photo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "front.png").write_bytes(b"mask")
    mask = {"method": "mask", "mask": "front.png", "min_piece": 0.0}
    run = fake_hunyuan(tmp_path).generate(
        GeneratorRequest(
            images={"single": photo}, out_dir=tmp_path / "out", cutouts={"single": mask}
        )
    )
    assert run.details["cutouts_seen"] == {"single": {**mask, "mask": str(tmp_path / "front.png")}}


def test_a_job_without_cutouts_is_written_as_before(tmp_path: Path, photo: Path) -> None:
    run = fake_hunyuan(tmp_path).generate(
        GeneratorRequest(images={"single": photo}, out_dir=tmp_path / "out")
    )
    assert run.details["cutouts_seen"] is None
    job = json.loads((tmp_path / "out" / "job.json").read_text(encoding="utf-8"))
    assert "cutouts" not in job


def test_a_request_refuses_cutouts_it_cannot_apply(tmp_path: Path, photo: Path) -> None:
    with pytest.raises(ValueError, match="no image"):
        GeneratorRequest(images={"single": photo}, out_dir=tmp_path, cutouts={"front": SAM})
    with pytest.raises(FileNotFoundError, match="mask"):
        GeneratorRequest(
            images={"single": photo},
            out_dir=tmp_path,
            cutouts={"single": {"method": "mask", "mask": str(tmp_path / "none.png")}},
        )


def test_cut_out_runs_only_the_first_step(tmp_path: Path, photo: Path) -> None:
    done = fake_hunyuan(tmp_path).cut_out(
        GeneratorRequest(images={"src-a": photo}, out_dir=tmp_path / "cut", cutouts={"src-a": SAM})
    )
    assert done.prepared == {"src-a": tmp_path / "cut" / "prepared" / "src-a.png"}
    assert done.sheet == tmp_path / "cut" / "sheet.png"
    assert done.done["src-a"]["method"] == "sam"
    job = json.loads((tmp_path / "cut" / "job.json").read_text(encoding="utf-8"))
    assert job["cutout_only"] is True and "seed" not in job  # no 3D model settings


def test_cut_out_passes_masks_to_compare_and_returns_each_mask(tmp_path: Path, photo: Path) -> None:
    drawn = tmp_path / "drawn.png"
    drawn.write_bytes(b"a mask drawn before")
    done = fake_hunyuan(tmp_path).cut_out(
        GeneratorRequest(
            images={"src-a": photo}, out_dir=tmp_path / "cut", compare={"src-a": drawn}
        )
    )
    assert done.masks == {"src-a": tmp_path / "cut" / "masks" / "src-a.png"}
    assert done.done["src-a"]["iou"] == 0.9
    job = json.loads((tmp_path / "cut" / "job.json").read_text(encoding="utf-8"))
    assert job["compare"] == {"src-a": str(drawn.resolve())}
    with pytest.raises(ValueError, match="no image"):
        GeneratorRequest(images={"src-a": photo}, out_dir=tmp_path, compare={"src-b": drawn})
    with pytest.raises(FileNotFoundError, match="to compare"):
        GeneratorRequest(
            images={"src-a": photo}, out_dir=tmp_path, compare={"src-a": tmp_path / "none.png"}
        )


def test_a_preview_line_names_edits_specks_and_iou() -> None:
    info = {"method": "sam", "kept_share": 0.4321, "edits": 3, "pieces_dropped": 2, "iou": 0.97}
    assert describe_cutout("src-a", info) == (
        "src-a: sam, 43.2% kept, 3 edits, 2 specks dropped, IoU 0.970 against the mask compared"
    )
    assert describe_cutout("src-b", {"method": "auto", "kept_share": 0.5}) == (
        "src-b: auto, 50.0% kept"
    )
    one = {"method": "auto", "kept_share": 0.5, "edits": 1, "pieces_dropped": 1}
    assert describe_cutout("src-c", one) == "src-c: auto, 50.0% kept, 1 edit, 1 speck dropped"


def test_a_generator_that_cannot_cut_out_says_so(
    photo: Path, tmp_path: Path, fake_generator
) -> None:
    with pytest.raises(GeneratorError, match="cannot cut photos out"):
        fake_generator().cut_out(GeneratorRequest(images={"single": photo}, out_dir=tmp_path))


# ---------------------------------------------------------------------------- Pipeline B
class CuttingGenerator(ImageTo3DGenerator):
    """Wraps the fake generator: records each request and cuts out as a placeholder."""

    name = "cutting-generator"

    def __init__(self, inner: ImageTo3DGenerator, log: list[GeneratorRequest]) -> None:
        self.inner, self.log = inner, log

    def fingerprint(self) -> dict[str, Any]:
        return self.inner.fingerprint()

    def for_views(self, views: Collection[str]) -> ImageTo3DGenerator:
        return self

    def generate(self, request: GeneratorRequest) -> GeneratorRun:
        self.log.append(request)
        return self.inner.generate(request)

    def cut_out(self, request: GeneratorRequest) -> CutoutRun:
        self.log.append(request)
        return CutoutRun({}, request.out_dir / "sheet.png", {}, 0.0, request.out_dir / "log")


@pytest.fixture
def two_photos(photo_run) -> tuple[list[Any], Path]:
    """The test photo and a second one beside it; returns the sources and the mask's file."""
    second = photo_run.data_dir / Path(photo_run.photo.uri).parent / "side.png"
    second.write_bytes(b"a second photo")
    sources = [
        photo_run.photo,
        photo_run.photo.model_copy(
            update={
                "source_id": "src-side",
                "uri": Path(photo_run.photo.uri).with_name("side.png").as_posix(),
            }
        ),
    ]
    mask = photo_run.run_dir / "masks" / "front.png"
    mask.parent.mkdir(parents=True)
    mask.write_bytes(b"a mask drawn by hand")
    return sources, mask


def pipeline_with(photo_run, generator, photos: dict[str, InputPhoto]) -> PipelineB:
    return PipelineB(generator, photo_run.data_dir, photo_run.run_dir, photos=photos)


def test_cutouts_join_the_reuse_key_and_the_record(photo_run, two_photos, fake_generator) -> None:
    sources, mask = two_photos
    mask_uri = mask.relative_to(photo_run.data_dir).as_posix()
    photos = {
        "src-photo": InputPhoto.model_validate(
            {"view": "front", "cutout": {"method": "mask", "mask": mask_uri}}
        ),
        "src-side": InputPhoto.model_validate({"view": "operator_right", "cutout": SAM}),
    }
    log: list[GeneratorRequest] = []
    pipeline_with(photo_run, CuttingGenerator(fake_generator(), log), photos).generate(sources)

    (request,) = log
    assert request.cutouts["front"]["mask"] == str(mask.resolve())
    assert request.cutouts["left"]["box"] == [0.1, 0.2, 0.9, 0.95]  # operator_right: its left
    record = json.loads((photo_run.run_dir / "generator" / "run.json").read_text("utf-8"))
    front = {
        k: v for k, v in photos["src-photo"].cutout.model_dump(mode="json").items() if k != "mask"
    }  # type: ignore[union-attr]
    assert record["key"]["cutouts"] == {
        "front": {**front, "mask_sha256": hashlib.sha256(mask.read_bytes()).hexdigest()},
        "left": {
            **Cutout.model_validate(SAM).model_dump(mode="json", exclude={"mask"}),
            "sam_model": SAM_MODEL,
        },
    }
    assert record["photos"]["fed"][0]["cutout"]["mask"] == mask_uri


def test_a_run_without_cutouts_keeps_its_earlier_key(photo_run, fake_generator) -> None:
    log: list[GeneratorRequest] = []
    pipeline_with(photo_run, CuttingGenerator(fake_generator(), log), {}).generate(
        [photo_run.photo]
    )
    record = json.loads((photo_run.run_dir / "generator" / "run.json").read_text("utf-8"))
    assert set(record["key"]) == {"photo_sha256", "generator"}
    assert "cutout" not in record["photos"]["fed"][0]
    assert log[0].cutouts == {}


def test_another_cutout_or_mask_is_another_mesh(photo_run, two_photos, fake_generator) -> None:
    sources, mask = two_photos
    mask_uri = mask.relative_to(photo_run.data_dir).as_posix()

    def photos(cutout: dict[str, Any]) -> dict[str, InputPhoto]:
        return {
            "src-photo": InputPhoto.model_validate({"view": "front", "cutout": cutout}),
            "src-side": InputPhoto(view="operator_right"),  # type: ignore[call-arg]
        }

    generator = CuttingGenerator(fake_generator(), [])
    masked = photos({"method": "mask", "mask": mask_uri})
    pipeline_with(photo_run, generator, masked).generate(sources)
    pipeline_with(photo_run, generator, masked).generate(sources)  # the same: reused
    assert len(generator.log) == 1
    with pytest.raises(RunFolderConflict):
        pipeline_with(photo_run, generator, photos(SAM)).generate(sources)
    mask.write_bytes(b"the mask redrawn")
    with pytest.raises(RunFolderConflict):
        pipeline_with(photo_run, generator, masked).generate(sources)


def test_a_mask_must_be_in_the_data_folder(photo_run, two_photos, fake_generator, tmp_path) -> None:
    sources, _ = two_photos
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"mask")
    photos = {
        "src-photo": InputPhoto.model_validate(
            {"view": "front", "cutout": {"method": "mask", "mask": "../outside.png"}}
        ),
        "src-side": InputPhoto(view="operator_right"),  # type: ignore[call-arg]
    }
    with pytest.raises(ValueError, match="not a file in the data folder"):
        pipeline_with(photo_run, CuttingGenerator(fake_generator(), []), photos).generate(sources)


def test_the_preview_shows_fed_photos_and_evidence_given_a_cutout(
    photo_run, two_photos, fake_generator
) -> None:
    sources, _ = two_photos
    photos = {
        "src-photo": InputPhoto(view="front"),  # type: ignore[call-arg]
        "src-side": InputPhoto.model_validate(
            {"view": "operator_right", "use": "evidence", "cutout": SAM}
        ),
    }
    log: list[GeneratorRequest] = []
    pipeline = pipeline_with(photo_run, CuttingGenerator(fake_generator(), log), photos)
    pipeline.preview_cutouts(sources, photo_run.run_dir / "cutouts")
    (request,) = log
    assert set(request.images) == {"src-photo", "src-side"}  # named by source id
    assert set(request.cutouts) == {"src-side"}
    assert not (photo_run.run_dir / "generator").exists()  # nothing generated

    log.clear()
    photos["src-side"] = InputPhoto(view="operator_right", use="evidence")
    pipeline_with(photo_run, CuttingGenerator(fake_generator(), log), photos).preview_cutouts(
        sources, photo_run.run_dir / "cutouts"
    )
    assert set(log[0].images) == {"src-photo"}  # plain evidence is not shown


def test_edits_join_the_reuse_key_so_another_edit_is_another_mesh(
    photo_run, two_photos, fake_generator
) -> None:
    sources, _ = two_photos

    def photos(cutout: dict[str, Any]) -> dict[str, InputPhoto]:
        return {
            "src-photo": InputPhoto.model_validate({"view": "front", "cutout": cutout}),
            "src-side": InputPhoto(view="operator_right"),  # type: ignore[call-arg]
        }

    log: list[GeneratorRequest] = []
    generator = CuttingGenerator(fake_generator(), log)
    pipeline_with(photo_run, generator, photos({**SAM, "edits": EDITS})).generate(sources)
    assert log[0].cutouts["front"]["edits"] == EDITS
    record = json.loads((photo_run.run_dir / "generator" / "run.json").read_text("utf-8"))
    assert record["key"]["cutouts"]["front"]["edits"] == EDITS
    with pytest.raises(RunFolderConflict):
        pipeline_with(photo_run, generator, photos({**SAM, "edits": EDITS[:2]})).generate(sources)


def test_the_preview_compares_photos_with_a_mask_of_their_name(
    photo_run, two_photos, fake_generator
) -> None:
    sources, mask = two_photos
    photos = {
        "src-photo": InputPhoto(view="front"),  # type: ignore[call-arg]
        "src-side": InputPhoto(view="operator_right"),  # type: ignore[call-arg]
    }
    drawn = mask.parent / "src-side.png"
    drawn.write_bytes(b"v3's mask")
    log: list[GeneratorRequest] = []
    pipeline = pipeline_with(photo_run, CuttingGenerator(fake_generator(), log), photos)
    pipeline.preview_cutouts(sources, photo_run.run_dir / "cutouts", mask.parent)
    assert log[0].compare == {"src-side": drawn}  # front.png is no photo's name
    with pytest.raises(ValueError, match="no mask named after a shown photo"):
        pipeline.preview_cutouts(sources, photo_run.run_dir / "cutouts", photo_run.run_dir)


# ---------------------------------------------------------- the real job, in its environment
@pytest.mark.slow
@pytest.mark.skipif(
    not os.environ.get("MOONWALKERS_GEN_ROOT"),
    reason="set MOONWALKERS_GEN_ROOT to the generator folder (e.g. C:\\mw-gen) to run",
)
def test_real_job_applies_a_drawn_mask_and_drops_specks(tmp_path: Path) -> None:
    """A grey photo, a mask with one large square and one speck: the speck is dropped."""
    photo, mask = tmp_path / "photo.png", tmp_path / "mask.png"
    write_png(photo, np.full((200, 300), 90, dtype=np.uint8))
    drawn = np.zeros((100, 150), dtype=np.uint8)  # drawn at half size: scaled up
    drawn[20:80, 30:100] = 255
    drawn[90:92, 140:142] = 255  # 4 pixels: under 2% of the square
    write_png(mask, drawn)
    config = Hunyuan3DConfig.under(Path(os.environ["MOONWALKERS_GEN_ROOT"]))
    done = Hunyuan3DGenerator(config).cut_out(
        GeneratorRequest(
            images={"src-a": photo},
            out_dir=tmp_path / "cut",
            cutouts={"src-a": Cutout(method="mask", mask=str(mask)).model_dump(mode="json")},
        )
    )
    assert done.done["src-a"]["method"] == "mask"
    assert done.done["src-a"]["pieces_dropped"] == 1
    alpha = read_png(done.prepared["src-a"])[:, :, 3]
    assert alpha.shape == (200, 300)
    assert alpha[100, 100] == 255 and alpha[10, 10] == 0
    assert alpha[181:184, 281:284].max() == 0  # the speck, scaled up, is gone
    assert done.sheet.is_file()


@pytest.mark.slow
@pytest.mark.skipif(
    not os.environ.get("MOONWALKERS_GEN_ROOT"),
    reason="set MOONWALKERS_GEN_ROOT to the generator folder (e.g. C:\\mw-gen) to run",
)
def test_real_job_draws_edits_in_order_before_dropping_specks(tmp_path: Path) -> None:
    """Decision 0041 on a drawn mask: an added square, a line across empty space, then a
    removal that wins over the square where they overlap; the preview writes each mask alone
    and its IoU against the same mask is 1."""
    photo, mask = tmp_path / "photo.png", tmp_path / "mask.png"
    write_png(photo, np.full((200, 400), 90, dtype=np.uint8))
    write_png(mask, np.zeros((200, 400), dtype=np.uint8))  # nothing kept to start with
    edits = [
        {"op": "add", "points": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.9], [0.1, 0.9]]},
        {"op": "add", "points": [[0.5, 0.5], [0.95, 0.5]], "width": 0.025},  # 10 pixels wide
        {"op": "remove", "points": [[0.0, 0.0], [0.3, 0.0], [0.3, 0.5], [0.0, 0.5]]},
    ]
    cutout = Cutout(method="mask", mask=str(mask), edits=edits, min_piece=0.0)  # type: ignore[arg-type]
    config = Hunyuan3DConfig.under(Path(os.environ["MOONWALKERS_GEN_ROOT"]))
    generator = Hunyuan3DGenerator(config)
    done = generator.cut_out(
        GeneratorRequest(
            images={"src-a": photo},
            out_dir=tmp_path / "cut",
            cutouts={"src-a": cutout.model_dump(mode="json")},
        )
    )
    assert done.done["src-a"]["edits"] == 3
    alpha = read_png(done.prepared["src-a"])[:, :, 3]
    assert alpha[150, 100] == 255  # the square, below the removal
    assert alpha[50, 100] == 0  # the square, where the later removal won
    assert alpha[100, 300] == 255 and alpha[90, 300] == 0  # the line, 10 pixels about y 100
    final = done.masks["src-a"]
    assert read_png(final)[:, :, 0].tolist() == alpha.tolist()

    again = generator.cut_out(
        GeneratorRequest(
            images={"src-a": photo},
            out_dir=tmp_path / "again",
            cutouts={"src-a": cutout.model_dump(mode="json")},
            compare={"src-a": final},
        )
    )
    assert again.done["src-a"]["iou"] == 1.0
