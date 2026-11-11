"""A geometry spec for several parts and joints (decisions 0023 and 0027), on the Phase 1
box-and-cylinder drill press as the generated mesh: its parts are known, so the cuts, the
stand-ins, the scale and the joints can be checked exactly."""

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import trimesh
from pydantic import ValidationError

from moonwalkers.contracts.pipeline_result import (
    Citation,
    Fact,
    Joint,
    JointMode,
    MachineIdentity,
    Source,
)
from moonwalkers.control import ProgramFile, packaged_programs
from moonwalkers.orchestrator import JobRequest
from moonwalkers.pipelines.b import build
from moonwalkers.pipelines.b.mesh_tools import load_mesh
from moonwalkers.pipelines.b.part_spike import SYNTHETIC_CUTS
from moonwalkers.pipelines.b.parts_spec import (
    PartsSpec,
    assemble_parts,
    boundary_loops,
    open_loops,
    oriented_mesh,
    patch_hole,
    simple_loops,
)
from moonwalkers.pipelines.b.pipeline import (
    GeometrySpecMissing,
    PipelineB,
    parts_issues,
    read_spec,
)
from moonwalkers.pipelines.b.synthetic_parts import drill_press
from moonwalkers.usd import primitive_drill_press as dp
from moonwalkers.usd.validate import validate_file

NOW = datetime(2026, 10, 27, tzinfo=UTC)
TABLE_AT = (0.0, 0.0, dp.TABLE_LOW_TOP)
RACK_AT = (dp.COLUMN_X, 0.0, 0.1)
REMOVED_TABLE = "generated_table"


def reference_facts() -> Any:
    from moonwalkers.pipelines.b.pipeline import ReferenceFacts

    cite = [Citation(source_id=dp.SYNTHETIC)]
    return ReferenceFacts(
        sources=[
            Source(source_id=dp.MANUAL, kind="file", uri=dp.MANUAL_URI, retrieved_at=NOW),
            Source(source_id=dp.SYNTHETIC, kind="user_input", uri="user", retrieved_at=NOW),
        ],
        identity=MachineIdentity(manufacturer=dp.MANUFACTURER, model=dp.MODEL, confidence=1.0,
                                 citations=cite),
        facts=[
            Fact(key="overall_height", value=dp.OVERALL_HEIGHT, unit="m", confidence=1.0,
                 citations=cite),
            Fact(key="column_diameter", value=2 * dp.COLUMN_RADIUS, unit="m", confidence=1.0,
                 citations=cite),
            Fact(key="max_spindle_speed", value=300.0, unit="rad/s", confidence=1.0,
                 citations=cite),
        ],
    )  # fmt: skip


def spec_joint(joint: Joint) -> dict[str, Any]:
    """A Phase 1 joint as a spec joint: the test mesh is in metres, so model units are too."""
    data = joint.model_dump(mode="json")
    return {
        "joint_id": data["joint_id"],
        "joint_type": data["joint_type"],
        "parent": data["parent_part"],
        "child": data["child_part"],
        "axis": data["axis"],
        "point": data["origin_m"],
        "lower": data["lower_limit"],
        "upper": data["upper_limit"],
        "mode": data["mode"],
        "adjustable_stop": data["adjustable_stop"],
        "follows": data["follows"],
        "note": "from the Phase 1 drill press",
        "inaccuracy": "Stand-in ratio." if data["follows"] else None,
        "citations": data["citations"],
    }


def drill_press_spec(**changes: Any) -> dict[str, Any]:
    """The Phase 1 drill press cut by the Phase 4 spike's synthetic cut list, its table swapped
    for a slotted stand-in, and a stand-in rack bar held to the rack by a fixed joint."""
    cuts = [c.model_dump(mode="json") for c in SYNTHETIC_CUTS]
    for cut in cuts:
        cut["part"] = REMOVED_TABLE if cut["part"] == "table" else cut["part"]
    cut_parts = ["frame", "quill", "spindle", "handle_hub", "column_rack", "table_bracket",
                 "table_arm"]  # fmt: skip
    cited = [{"source_id": dp.SYNTHETIC, "locator": "test"}]
    parts = [{"part_id": p, "name": p, "kind": "cut", "note": "test"} for p in cut_parts]
    parts += [
        {"part_id": REMOVED_TABLE, "name": "table as generated", "kind": "removed",
         "note": "replaced by a stand-in"},
        {"part_id": "table", "name": "slotted table", "kind": "stand_in",
         "replaces": REMOVED_TABLE, "at": list(TABLE_AT), "note": "a test stand-in",
         "citations": cited,
         "shape": {"kind": "slotted_table", "side_m": dp.TABLE_SIDE,
                   "thickness_m": dp.TABLE_THICKNESS, "corner_radius_m": 0.03,
                   "rim_width_m": 0.02, "gutter_width_m": 0.012, "gutter_depth_m": 0.01,
                   "slot_width_m": 0.014, "slot_depth_m": 0.012, "slot_start_m": 0.04,
                   "hole_diameter_m": 0.025, "cell_m": 0.006}},
        {"part_id": "rack_teeth", "name": "Stand-in: rack teeth", "kind": "stand_in",
         "at": list(RACK_AT), "turn_deg": 90.0, "note": "test teeth", "citations": cited,
         "shape": {"kind": "solids", "pieces": [
             {"shape": "box", "size_m": [0.004, 0.01, 0.002], "center_m": [0.05, 0.0, 0.0],
              "repeat": 10, "step_m": [0.0, 0.0, 0.004]}]}},
    ]  # fmt: skip
    joints = [spec_joint(j) for j in dp.build_joints()]
    joints.append(
        {"joint_id": "rack_teeth_mount", "joint_type": "fixed", "parent": "column_rack",
         "child": "rack_teeth", "axis": [0, 0, 1], "point": list(RACK_AT), "note": "test",
         "citations": cited}
    )  # fmt: skip
    joints[1]["max_velocity_fact"] = "max_spindle_speed"  # the spindle
    spec = {
        "up": "+y",
        "front": "+z",
        "origin_xy": [0.0, 0.0],
        "scale": {"fact": "overall_height", "how": "the mesh's height"},
        "fixed_part": "frame",
        "cuts": cuts,
        "parts": parts,
        "joints": joints,
        "size_checks": [
            {"fact": "column_diameter", "measured_model_units": 2 * dp.COLUMN_RADIUS,
             "how": "the primitive's radius"}
        ],
        "decided_by": "test",
        "method": "the Phase 1 drill press, cut by the spike's synthetic cut list",
    }  # fmt: skip
    return spec | changes


@pytest.fixture
def drill_press_generator(generator_for):
    return generator_for(lambda: drill_press("separate").mesh)


@pytest.fixture
def spec_run(photo_run):
    """The photo run with the drill press's several-part spec written."""

    def write(**changes: Any) -> Path:
        path = photo_run.run_dir / "geometry_spec.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(drill_press_spec(**changes)), encoding="utf-8")
        return path

    return write


# ---------------------------------------------------------------------------------- the spec
def test_a_spec_with_parts_is_read_as_several_parts(tmp_path: Path, write_spec) -> None:
    path = tmp_path / "geometry_spec.json"
    path.write_text(json.dumps(drill_press_spec()), encoding="utf-8")
    assert isinstance(read_spec(path), PartsSpec)
    assert not isinstance(read_spec(write_spec(tmp_path / "old")), PartsSpec)  # decision 0012


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda s: s["parts"].pop(0), "fixed part"),
        (lambda s: s["cuts"][0].update(part="nowhere"), "not a cut or removed part"),
        (lambda s: s["cuts"][0].update(part="table"), "not a cut or removed part"),
        (lambda s: s["parts"][-1].pop("shape"), "needs a shape"),
        (lambda s: s["parts"][-1].update(citations=[]), "needs citations"),
        (lambda s: s["parts"][0].update(at=[0, 0, 0]), "only a stand-in"),
        (lambda s: s["parts"][-2].update(replaces="frame"), "not a removed part"),
        (lambda s: s["joints"][0].update(child=REMOVED_TABLE), "not a twin part"),
        (lambda s: s["joints"].append(dict(s["joints"][0])), "duplicate joint ids"),
        (lambda s: s["joints"][0].update(axis=[0, 0, 0]), "no axis"),
        (
            lambda s: s["parts"][-1].update(patches=[{"near": [0, 0, 0], "note": "t"}]),
            "only a cut part",
        ),
    ],
)
def test_a_spec_that_cannot_be_built_is_refused(change, message: str) -> None:
    spec = drill_press_spec()
    change(spec)
    with pytest.raises(ValidationError, match=message):
        PartsSpec.model_validate(spec)


# ------------------------------------------------------------------------------- assembling
def test_assembly_cuts_places_stand_ins_and_scales(tmp_path: Path) -> None:
    mesh_path = tmp_path / "mesh.glb"
    drill_press("separate").mesh.export(mesh_path)  # already in the twin's axes
    spec = PartsSpec.model_validate(drill_press_spec(up="+z", front="+x"))
    model = assemble_parts(mesh_path, spec, 2 * dp.OVERALL_HEIGHT, tmp_path / "out")

    assert model.scale_factor == pytest.approx(2.0)  # the cited height is twice the mesh's
    built = {p.part_id: p for p in model.parts}
    assert set(built) == {"frame", "quill", "spindle", "handle_hub", "column_rack",
                          "table_bracket", "table_arm", "table", "rack_teeth"}  # fmt: skip
    assert model.removed_faces[REMOVED_TABLE] > 0
    # A stand-in keeps its own size in metres; only where it goes is in model units, so scaled.
    table = load_mesh(built["table"].path)
    assert table.extents[:2] == pytest.approx([dp.TABLE_SIDE] * 2, abs=0.012)
    assert table.bounds[1][2] == pytest.approx(2 * dp.TABLE_LOW_TOP, abs=0.006)
    teeth = load_mesh(built["rack_teeth"].path)  # turned 90 degrees: the teeth stand at +Y
    assert teeth.bounds[0][1] == pytest.approx(0.048, abs=1e-6)
    assert teeth.bounds[0][0] == pytest.approx(2 * dp.COLUMN_X - 0.005, abs=1e-6)
    origins = {j.joint_id: j.origin_m for j in model.joints}
    assert origins["quill_travel"] == pytest.approx((0.0, 0.0, 2 * dp.HEAD_BOTTOM))


# ---------------------------------------------------------------------------------- patches
def open_box() -> trimesh.Trimesh:
    """A unit cube, subdivided, without its top: one square hole at z = 0.5."""
    cube = trimesh.creation.box(extents=(1.0, 1.0, 1.0)).subdivide().subdivide()
    sides = np.flatnonzero(cube.face_normals[:, 2] < 0.9)
    return cube.submesh([sides], append=True)


def test_a_patch_closes_the_open_loop_nearest_its_point() -> None:
    mesh = open_box()
    loops = boundary_loops(mesh)
    assert len(loops) == 1 and len(loops[0]) == 16  # four edges per side after two subdivisions
    patched = patch_hole(mesh, (0.0, 0.0, 0.49))
    assert patched.is_watertight and patched.is_winding_consistent
    assert patched.volume == pytest.approx(1.0)  # flat over the hole, and facing out
    with pytest.raises(ValueError, match="no open edge loop within"):
        patch_hole(mesh, (0.0, 0.0, -0.5))
    with pytest.raises(ValueError, match="no open edge loop to patch"):
        patch_hole(patched, (0.0, 0.0, 0.5))


def test_a_loop_through_one_vertex_twice_is_split_at_it() -> None:
    loops = simple_loops(np.array([1, 2, 3, 1, 4, 5]))
    assert [loop.tolist() for loop in loops] == [[1, 2, 3], [1, 4, 5]]
    # a back-and-forth (1 -> 2 -> 1) encloses nothing, so it is not fanned
    assert [loop.tolist() for loop in simple_loops(np.array([1, 2, 1, 3, 4]))] == [[1, 3, 4]]


def test_two_holes_touching_at_a_point_are_patched_without_a_non_manifold_edge() -> None:
    cube = trimesh.creation.box(extents=(0.1, 0.1, 0.1)).subdivide().subdivide()
    top = np.flatnonzero(cube.face_normals[:, 2] > 0.9)
    first = top[0]
    second = next(f for f in top if len(set(cube.faces[f]) & set(cube.faces[first])) == 1)
    shared = (set(cube.faces[first]) & set(cube.faces[second])).pop()
    keep = np.setdiff1d(np.arange(len(cube.faces)), [first, second])
    mesh = cube.submesh([keep], append=True)
    point = tuple(cube.vertices[shared])
    while boundary_loops(mesh):  # one loop through the shared point, or two, by walking order
        mesh = patch_hole(mesh, point)
    assert mesh.is_watertight and mesh.is_winding_consistent
    _, faces_per_edge = np.unique(mesh.edges_sorted, axis=0, return_counts=True)
    assert faces_per_edge.max() == 2


def test_a_cut_part_is_patched_where_a_removed_part_met_it(tmp_path: Path) -> None:
    mesh_path = tmp_path / "mesh.glb"
    trimesh.creation.box(extents=(1.0, 1.0, 1.0)).subdivide().subdivide().export(mesh_path)
    cited = [{"source_id": dp.SYNTHETIC, "locator": "test"}]
    spec = PartsSpec.model_validate(
        {"up": "+z", "front": "+x", "origin_xy": [0.0, 0.0],
         "scale": {"fact": "overall_height", "how": "the mesh's height"},
         "fixed_part": "frame",
         "cuts": [{"part": "lid", "note": "the top",
                   "shapes": [{"shape": "box", "min": [-1, -1, 0.45], "max": [1, 1, 1]}]}],
         "parts": [
             {"part_id": "frame", "name": "frame", "kind": "cut", "note": "the rest",
              "patches": [{"near": [0.0, 0.0, 0.5], "note": "where the lid was"}]},
             {"part_id": "lid", "name": "lid", "kind": "removed", "note": "cut out"},
             {"part_id": "cap", "name": "Stand-in: cap", "kind": "stand_in", "at": [0, 0, 0.5],
              "note": "test", "citations": cited,
              "shape": {"kind": "solids", "pieces": [{"shape": "box", "size_m": [1, 1, 0.1]}]}},
         ],
         "joints": [], "decided_by": "test", "method": "test"}
    )  # fmt: skip
    model = assemble_parts(mesh_path, spec, 1.0, tmp_path / "out")
    frame = load_mesh(next(p.path for p in model.parts if p.part_id == "frame"))
    assert frame.is_watertight
    mesh = oriented_mesh(mesh_path, spec)
    assert open_loops(mesh, spec) == []  # the patch closed the only one
    unpatched = PartsSpec.model_validate(
        spec.model_dump() | {"parts": [p.model_copy(update={"patches": []}) for p in spec.parts]}
    )
    (hole,) = open_loops(mesh, unpatched)
    assert hole.part == "frame" and hole.across == ("lid",) and hole.edges == 16
    assert hole.centre == pytest.approx((0.0, 0.0, 0.5))  # the lid's rim, which the patch closed
    patched = [i for i in parts_issues(spec, model) if i.message.startswith("Patched")]
    assert len(patched) == 1 and patched[0].severity == "warning" and patched[0].ref == "frame"
    assert "where the lid was" in patched[0].message


def test_a_cut_part_can_drop_its_loose_pieces(tmp_path: Path) -> None:
    """A box with a loose strand and a loose bit, as the arm's generated links have."""
    body = trimesh.creation.box(extents=(1.0, 1.0, 1.0)).subdivide().subdivide()
    strand = trimesh.creation.box(extents=(0.05, 0.05, 0.8))
    strand.apply_translation((0.7, 0.0, 0.0))
    bit = trimesh.creation.icosphere(subdivisions=1, radius=0.03)
    bit.apply_translation((0.0, 0.0, 1.0))
    mesh_path = tmp_path / "mesh.glb"
    trimesh.util.concatenate([body, strand, bit]).export(mesh_path)
    spec = {"up": "+z", "front": "+x", "origin_xy": [0.0, 0.0],
            "scale": {"fact": "overall_height", "how": "the mesh's height"},
            "fixed_part": "frame", "cuts": [],
            "parts": [{"part_id": "frame", "name": "frame", "kind": "cut", "note": "the body",
                       "loose_pieces": "remove"}],
            "joints": [], "decided_by": "test", "method": "test"}  # fmt: skip
    model = assemble_parts(mesh_path, PartsSpec.model_validate(spec), 1.0, tmp_path / "out")
    (frame,) = model.parts
    assert frame.faces == len(body.faces)
    assert model.removed_faces == {"frame (loose pieces)": len(strand.faces) + len(bit.faces)}
    issues = parts_issues(PartsSpec.model_validate(spec), model)
    (issue,) = [i for i in issues if i.message.startswith("Its loose")]
    assert issue.message.startswith("Its loose pieces are cut out of the twin (92 faces of")
    spec["parts"][0] |= {"kind": "removed", "name": "x"}
    with pytest.raises(ValidationError, match="only a cut part has loose pieces"):
        PartsSpec.model_validate(spec)


# ------------------------------------------------------------------------------ the pipeline
def test_the_result_has_every_part_joint_and_stand_in_cited(
    photo_run, spec_run, drill_press_generator, clock
) -> None:
    pipeline = PipelineB(
        drill_press_generator, photo_run.data_dir, photo_run.run_dir, reference_facts(), clock
    )
    with pytest.raises(GeometrySpecMissing):
        pipeline.run("job-1", [photo_run.photo])
    spec_run()
    result = pipeline.run("job-1", [photo_run.photo])

    parts = {p.part_id: p for p in result.parts}
    assert parts["table"].name == "Stand-in: slotted table"  # labelled wherever it shows
    assert parts["rack_teeth"].name == "Stand-in: rack teeth"
    assert parts["table"].generator is None and parts["frame"].generator is not None
    assert parts["frame"].citations[0].source_id == "src-photo"  # the fed photo
    assert parts["table"].citations[0].locator == "parts[table]"
    joints = {j.joint_id: j for j in result.joints}
    assert joints["spindle_rotation"].max_velocity == 300.0
    assert joints["downfeed_handles"].follows is not None
    assert joints["rack_teeth_mount"].joint_type == "fixed"
    assert result.scale is not None and result.scale.reference == "overall_height"
    assert result.scale.scale_factor == pytest.approx(1.0)
    warnings = {i.ref: i.message for i in result.issues if i.severity == "warning"}
    assert warnings["table"].startswith("Stand-in: a test stand-in. It replaces")
    assert warnings["downfeed_handles"] == "Stand-in ratio."
    checks = [i.message for i in result.issues if i.ref == "column_diameter"]
    assert checks and "(+0.0%" in checks[0] and "Measured: the primitive's radius." in checks[0]
    removed = [i for i in result.issues if i.ref == REMOVED_TABLE]
    assert removed and removed[0].message.startswith("Cut out of the twin")


def test_the_scale_needs_a_cited_length(photo_run, spec_run, drill_press_generator) -> None:
    reference = reference_facts()
    reference.facts = [f for f in reference.facts if f.key != "overall_height"]
    pipeline = PipelineB(drill_press_generator, photo_run.data_dir, photo_run.run_dir, reference)
    spec_run()
    with pytest.raises(ValueError, match="no 'overall_height'"):
        pipeline.run("job-1", [photo_run.photo])
    spec_run(scale={"fact": "column_diameter", "how": "x"})  # not an extent the mesh has
    with pytest.raises(ValueError, match="measured_model_units"):
        PipelineB(
            drill_press_generator, photo_run.data_dir, photo_run.run_dir, reference_facts()
        ).run("job-1", [photo_run.photo])


# ----------------------------------------------------------------------------------- the build
def test_a_build_writes_a_check_file_per_behaviour_and_the_views(
    photo_run, spec_run, drill_press_generator, kb
) -> None:
    run_dir = photo_run.run_dir
    spec_run()
    request = JobRequest(job_id="job-1", sources=[photo_run.photo])
    (run_dir / "request.json").write_text(request.model_dump_json(), encoding="utf-8")
    outcome = build.build_run(
        run_dir, photo_run.data_dir, run_dir / "request.json", reference_facts(), None,
        drill_press_generator, kb,
    )  # fmt: skip

    names = sorted(p.name for p in outcome.check_files)
    assert names == ["adjustable_stop.usdc", "all_motions.usdc", "locked_at_setting.usdc",
                     "spin.usdc", "spring_return.usdc", "unlocked.usdc"]  # fmt: skip
    for path in [outcome.twin_file, *outcome.check_files]:
        assert [i for i in validate_file(path) if i.severity == "error"] == []
    assert (run_dir / "record_joints.py").is_file()
    assert (run_dir / "views" / "parts.png").is_file()
    assert (run_dir / "views" / "part_table.png").is_file()
    notes = (run_dir / "RUN.md").read_text(encoding="utf-8")
    assert "## Stand-ins and known inaccuracies" in notes and "`views/parts.png`" in notes
    assert "`checks/unlocked.usdc`" in notes and "record_joints.py" in notes


def drive_gains(path: Path, joint_id: str) -> tuple[float, float]:
    from pxr import Usd, UsdPhysics

    stage = Usd.Stage.Open(str(path))
    prim = next(p for p in stage.Traverse() if p.GetName() == joint_id)
    drive = UsdPhysics.DriveAPI(prim, "angular")
    return drive.GetStiffnessAttr().Get(), drive.GetDampingAttr().Get()


def filtered_pairs(path: Path) -> int:
    from pxr import Usd, UsdPhysics

    stage = Usd.Stage.Open(str(path))
    return sum(p.HasAPI(UsdPhysics.FilteredPairsAPI) for p in stage.Traverse())


def test_a_specs_hold_drive_and_self_collision_check_reach_the_twin_and_its_checks(
    photo_run, spec_run, drill_press_generator, kb
) -> None:
    run_dir = photo_run.run_dir
    hold = {"stiffness": 10000.0, "damping": 200.0, "why": "test"}
    spec_run(hold_drive=hold, self_collision="check")
    request = JobRequest(job_id="job-1", sources=[photo_run.photo])
    (run_dir / "request.json").write_text(request.model_dump_json(), encoding="utf-8")
    program = ProgramFile.load(packaged_programs()["ha5c-manual-example-3"])
    reference = reference_facts()
    reference = reference.model_copy(
        update={"sources": [*reference.sources, *program.sources], "control": [program.behavior]}
    )
    outcome = build.build_run(
        run_dir, photo_run.data_dir, run_dir / "request.json", reference, None,
        drill_press_generator, kb,
    )  # fmt: skip
    checks = {p.name: p for p in outcome.check_files}
    assert drive_gains(outcome.twin_file, "spindle_rotation") == (10000.0, 200.0)
    # a program folder holds and collides as the twin does (decision 0033)
    program_usd = run_dir / "programs" / "index-program" / "program.usdc"
    assert drive_gains(program_usd, "spindle_rotation") == (10000.0, 200.0)
    assert filtered_pairs(program_usd) == filtered_pairs(outcome.twin_file)
    assert drive_gains(checks["unlocked.usdc"], "spindle_rotation") == (10000.0, 200.0)
    assert drive_gains(checks["spin.usdc"], "spindle_rotation") == (0.0, 20.0)  # its own drive
    # "check": the twin keeps decision 0017's filter; one more file lets unjoined parts collide
    assert filtered_pairs(outcome.twin_file) > 0
    assert filtered_pairs(checks["self_collision.usdc"]) == 0
    assert drive_gains(checks["self_collision.usdc"], "spindle_rotation") == (0.0, 20.0)
    assert "`checks/self_collision.usdc`" in (run_dir / "RUN.md").read_text(encoding="utf-8")


def test_without_a_hold_drive_the_exporters_default_holds(photo_run, spec_run) -> None:
    spec_run()
    assert build.hold_drive(photo_run.run_dir) == build.DriveSettings.hold(0.0)
    assert build.self_collision(photo_run.run_dir) == "off"


def test_check_files_follow_the_joints_behaviour() -> None:
    _, result = dp.build_test_drill_press(NOW)
    checks = {c.name: c for c in build.check_files([result])}
    spring = checks["spring_return.usdc"]
    assert spring.starts == {"quill_travel": pytest.approx(dp.SPINDLE_TRAVEL)}
    stop = checks["adjustable_stop.usdc"].results([result])[0]
    quill = next(j for j in stop.joints if j.joint_id == "quill_travel")
    assert quill.adjustable_stop.position == pytest.approx(dp.SPINDLE_TRAVEL / 2)
    unlocked = checks["unlocked.usdc"].results([result])[0]
    assert {j.joint_id for j in unlocked.joints if j.mode and j.mode.kind == "free"} == set(
        dp.TABLE_SETTING
    )
    locked = checks["locked_at_setting.usdc"].results([result])[0]
    positions = {
        j.joint_id: j.mode.position for j in locked.joints if j.joint_id in dp.TABLE_SETTING
    }
    assert positions["table_height"] == pytest.approx(dp.TABLE_TRAVEL / 2)
    assert positions["table_tilt"] == pytest.approx(math.radians(30))
    assert set(checks["spin.usdc"].settings) == {"spindle_rotation"}


def test_a_driven_slide_runs_its_whole_travel_at_its_top_speed() -> None:
    _, result = dp.build_test_drill_press(NOW)
    driven = JointMode(kind="driven", citations=[Citation(source_id=dp.SYNTHETIC, locator="t")])
    joints = [
        j.model_copy(update={"mode": driven, "max_velocity": 0.08})
        if j.joint_id == "table_height"
        else j
        for j in result.joints
    ]
    checks = {c.name: c for c in build.check_files([result.model_copy(update={"joints": joints})])}
    slide = checks["slide.usdc"]
    height = next(j for j in joints if j.joint_id == "table_height")
    assert slide.starts == {"table_height": pytest.approx(height.lower_limit)}
    drive = slide.settings["table_height"].drive
    assert drive.mode == "velocity" and drive.target == pytest.approx(0.08)
    assert drive.stiffness == 0.0 and drive.damping == build.SLIDE_DAMPING
    assert "slide.usdc" not in {c.name for c in build.check_files([result])}  # none driven


def test_a_twin_without_behaviour_keeps_the_pocs_two_checks(example_result) -> None:
    checks = build.check_files([example_result])
    assert [c.name for c in checks] == ["spin.usdc", "quarter_turn.usdc"]
    assert checks[0].drive.target == pytest.approx(math.radians(30))
    assert checks[1].drive.target == pytest.approx(math.radians(90))


def test_a_build_with_the_operators_controls_writes_its_controls_folder(
    photo_run, spec_run, drill_press_generator, kb
) -> None:
    """The T33901's switch, speed table and operator's commands (decision 0025) give the twin a
    controls folder beside its check files, listed in RUN.md."""
    from moonwalkers.contracts.pipeline_result import ControlBehavior

    t33901 = json.loads(
        (Path(build.__file__).with_name("grizzly_t33901.reference.json")).read_text(
            encoding="utf-8"
        )
    )
    reference = reference_facts()
    have = {s.source_id for s in reference.sources}
    reference.sources += [
        Source.model_validate(s) for s in t33901["sources"] if s["source_id"] not in have
    ]
    reference.control = [ControlBehavior.model_validate(b) for b in t33901["control"]]
    run_dir = photo_run.run_dir
    spec_run()
    request = JobRequest(job_id="job-1", sources=[photo_run.photo])
    (run_dir / "request.json").write_text(request.model_dump_json(), encoding="utf-8")
    build.build_run(
        run_dir, photo_run.data_dir, run_dir / "request.json", reference, None,
        drill_press_generator, kb,
    )  # fmt: skip

    folder = run_dir / "programs" / "operator-controls"
    assert (folder / "controls.usdc").is_file() and (folder / "run_controls.py").is_file()
    assert [i for i in validate_file(folder / "controls.usdc") if i.severity == "error"] == []
    notes = (run_dir / "RUN.md").read_text(encoding="utf-8")
    assert "`programs/operator-controls/`: ON/OFF switch with disabling key" in notes
    assert "`programs/operator-controls/controls.usdc` with run_controls.py" in notes
