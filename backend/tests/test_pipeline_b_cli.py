"""Pipeline B's command line: inspect a mesh, preview a spec, build and reuse a twin."""

import json
import re
from pathlib import Path

import pytest

from moonwalkers.contracts.pipeline_result import TwinRecord
from moonwalkers.orchestrator import JobRequest, MachineHint
from moonwalkers.pipelines.b import GeometrySpecMissing, PipelineB, cli
from moonwalkers.usd.validate import validate_file


@pytest.fixture
def generated(photo_run, fake_generator):
    """A run folder whose mesh has been generated (the build stopped for the spec)."""
    generator = fake_generator()
    with pytest.raises(GeometrySpecMissing):
        PipelineB(generator, photo_run.data_dir, photo_run.run_dir).run("job-1", [photo_run.photo])
    return photo_run


@pytest.fixture
def build_args(photo_run, fake_generator, test_reference, tmp_path, monkeypatch):
    """``build`` arguments for the test run, with the fake generator in place of Hunyuan3D-2."""
    generator = fake_generator()
    monkeypatch.setattr(cli, "Hunyuan3DGenerator", lambda config: generator)
    reference = tmp_path / "reference.json"
    reference.write_text(test_reference.model_dump_json(indent=2), encoding="utf-8")
    photo_run.run_dir.mkdir(parents=True)
    request = JobRequest(job_id="job-1", sources=[photo_run.photo])
    (photo_run.run_dir / "request.json").write_text(request.model_dump_json(), encoding="utf-8")
    args = ["build", str(photo_run.run_dir), "--reference", str(reference)]
    return args + ["--gen-root", str(tmp_path / "gen")], generator


def test_inspect_shows_raw_then_oriented_measurements(generated, capsys) -> None:
    run_dir = generated.run_dir
    assert cli.main(["inspect", str(run_dir)]) == 0
    assert "generator axes" in capsys.readouterr().out
    assert (run_dir / "inspect_raw" / "views.png").is_file()

    assert cli.main(["inspect", str(run_dir), "--up", "+y", "--front", "+z"]) == 0
    out = capsys.readouterr().out
    assert "twin axes: x front, y left, z up" in out
    assert "centre (y, z) = (+0.0000, +0.2000), radius 0.4000" in out  # the spindle's tip
    assert "axis height above the lowest point: 1.2000" in out
    assert (run_dir / "inspect_oriented" / "views.png").is_file()


def test_inspect_with_circle_x_uses_the_fitted_axis(generated, capsys) -> None:
    run_dir = str(generated.run_dir)
    args = ["inspect", run_dir, "--up", "+y", "--front", "+z", "--circle-x", "1.2", "1.4"]
    assert cli.main(args) == 0
    out = capsys.readouterr().out
    assert "circle fits at circle_x:" in out and "x = +1.200: centre (y, z) = (" in out
    assert "axis in use, from the round circle fits" in out
    assert cli.main(["inspect", run_dir, "--circle-x", "1.2"]) == 1
    assert "--circle-x needs --up and --front" in capsys.readouterr().err


def test_inspect_turns_the_mesh_by_yaw_and_reports_its_footprint(generated, capsys) -> None:
    def footprint(out: str) -> tuple[float, float]:
        found = re.search(r"turned by yaw_deg ([-+\d.]+); base footprint: ([-+\d.]+) deg", out)
        assert found, out
        return float(found[1]), float(found[2])

    run_dir = str(generated.run_dir)
    assert cli.main(["inspect", run_dir, "--up", "+y", "--front", "+z"]) == 0
    yaw, angle = footprint(capsys.readouterr().out)
    assert yaw == 0.0 and abs(angle - 90.0) < 1.0  # the indexer's 3-unit width along y
    assert cli.main(["inspect", run_dir, "--up", "+y", "--front", "+z", "--yaw", "90"]) == 0
    yaw, angle = footprint(capsys.readouterr().out)
    assert yaw == 90.0 and abs(angle) < 1.0  # turned back by 90: the width along x
    assert cli.main(["inspect", run_dir, "--yaw", "45"]) == 1
    assert "--yaw needs --up and --front" in capsys.readouterr().err


def test_preview_tries_the_spec_without_recording_it(
    generated, write_spec, test_reference, tmp_path, capsys
) -> None:
    write_spec(generated.run_dir)
    reference = tmp_path / "reference.json"
    reference.write_text(test_reference.model_dump_json(), encoding="utf-8")
    args = ["inspect", str(generated.run_dir), "--preview", "--reference", str(reference)]
    assert cli.main(args) == 0
    out = capsys.readouterr().out
    assert "scale: 0.084667 m per model unit" in out
    assert "warning: Size check: the model's overall height" in out
    assert (generated.run_dir / "preview" / "spindle" / "views.png").is_file()
    assert not (generated.run_dir / "meshes").exists()  # nothing a build would reuse


def test_inspect_fits_circles_along_any_axis(generated, capsys) -> None:
    run_dir = str(generated.run_dir)
    oriented = ["inspect", run_dir, "--up", "+y", "--front", "+z"]
    assert cli.main([*oriented, "--circles-along", "x", "--at", "1.3"]) == 0
    out = capsys.readouterr().out
    assert "x = +1.300: centre (+1.3000, +0.0000, +0.2000), radius 0.39" in out
    assert cli.main(["inspect", run_dir, "--circles-along", "z", "--at", "0"]) == 1
    assert "--circles-along needs --up, --front and --at" in capsys.readouterr().err


def test_preview_of_several_parts_writes_the_reviewers_views(
    generated, test_reference, tmp_path, capsys
) -> None:
    spec = {
        "up": "+y",
        "front": "+z",
        "origin_xy": [1.0, 0.0],
        "scale": {"fact": "overall_width", "how": "the mesh's width"},
        "fixed_part": "body",
        "cuts": [
            {
                "part": "spindle",
                "shapes": [{"shape": "cylinder", "point": [1.0, 0.0, 0.2], "axis": [1, 0, 0],
                            "radius": 0.45, "start": 0.0}],
            }
        ],
        "parts": [
            {"part_id": "body", "name": "body", "kind": "cut", "note": "the box"},
            {"part_id": "spindle", "name": "spindle", "kind": "cut", "note": "the cylinder"},
        ],
        "joints": [
            {"joint_id": "spindle_rotation", "joint_type": "revolute", "parent": "body",
             "child": "spindle", "axis": [1, 0, 0], "point": [1.0, 0.0, 0.2], "note": "its axis",
             "citations": [{"source_id": "src-test-sheet"}]}
        ],
        "decided_by": "test",
        "method": "test",
    }  # fmt: skip
    draft = tmp_path / "draft_spec.json"
    draft.write_text(json.dumps(spec), encoding="utf-8")
    reference = tmp_path / "reference.json"
    reference.write_text(test_reference.model_dump_json(), encoding="utf-8")
    args = ["inspect", str(generated.run_dir), "--preview", "--spec", str(draft)]
    assert cli.main([*args, "--reference", str(reference), "--no-photos"]) == 0
    out = capsys.readouterr().out
    assert "scale: 0.084667 m per model unit (3.0000 model units)" in out  # 0.254 m / 3 units
    assert "spindle (cut):" in out and "spindle_rotation: axis (+1.0000" in out
    preview = generated.run_dir / "preview_parts"
    assert (preview / "parts.png").is_file() and (preview / "part_spindle.png").is_file()
    assert not (generated.run_dir / "meshes").exists()  # nothing a build would reuse
    assert not (generated.run_dir / "geometry_spec.json").exists()


def test_inspect_needs_a_generated_mesh(photo_run, capsys) -> None:
    assert cli.main(["inspect", str(photo_run.run_dir)]) == 1
    assert "no generated mesh" in capsys.readouterr().err


def test_build_stops_for_the_spec_then_builds_then_reuses(
    build_args, photo_run, write_spec, capsys
) -> None:
    args, generator = build_args
    run_dir, data_dir = photo_run.run_dir, photo_run.data_dir

    assert cli.main(args) == 2
    assert "stopped: no geometry spec yet" in capsys.readouterr().out

    write_spec(run_dir)
    assert cli.main(args) == 0
    out = capsys.readouterr().out
    assert out.startswith(
        "No twin found for moonwalkers/testindexer; built version 1 from Pipeline B. Exported to "
        "machines/moonwalkers-testindexer/runs/run-001/twin.usdc. It needs human review."
    )
    for name in ("twin.usdc", "checks/spin.usdc", "checks/quarter_turn.usdc"):
        assert not [i for i in validate_file(run_dir / name) if i.severity == "error"], name
    twin = TwinRecord.model_validate_json((run_dir / "twin_record.json").read_text("utf-8"))
    assert twin.twin_id == "moonwalkers/testindexer@v1"
    assert (data_dir / "kb").is_dir()  # the knowledge base lives in the data folder
    notes = (run_dir / "RUN.md").read_text(encoding="utf-8")
    assert "# Run: moonwalkers/testindexer@v1 (Pipeline B, one photo)" in notes
    assert "Scale: 0.084667 m per model unit" in notes
    assert "## Isaac Sim check (fill in)" in notes
    assert json.loads((run_dir / "request.job_result.json").read_text("utf-8"))["twin"] == (
        twin.model_dump(mode="json")
    )

    # A second request naming the machine reuses the stored twin without running anything.
    named = JobRequest(
        job_id="job-2",
        sources=[photo_run.photo],
        machine=MachineHint(manufacturer="MoonWalkers", model="Test Indexer"),
    )
    (run_dir / "request-2.json").write_text(named.model_dump_json(), encoding="utf-8")
    assert cli.main([*args, "--request", str(run_dir / "request-2.json")]) == 0
    assert capsys.readouterr().out.startswith(
        "Found an existing twin (v1, needs review) for moonwalkers/testindexer; reused it."
    )
    # The photo alone also finds it, after the pipeline reuses its mesh and parts.
    assert cli.main(args) == 0
    assert "It was identified after running Pipeline B" in capsys.readouterr().out
    assert generator.calls == 1
    assert (run_dir / "RUN.md").read_text(encoding="utf-8") == notes


def test_build_does_not_overwrite_an_exported_twin(
    build_args, photo_run, write_spec, capsys
) -> None:
    args, _ = build_args
    write_spec(photo_run.run_dir)
    assert cli.main(args) == 0
    rebuild = JobRequest(job_id="job-2", sources=[photo_run.photo], new_version=True)
    path = photo_run.run_dir / "rebuild.json"
    path.write_text(rebuild.model_dump_json(), encoding="utf-8")

    assert cli.main([*args, "--request", str(path)]) == 1
    assert "already holds an exported twin" in capsys.readouterr().err
    assert not (photo_run.run_dir / "rebuild.job_result.json").exists()


def test_build_needs_the_generator_folder(build_args, monkeypatch, capsys) -> None:
    args, _ = build_args
    monkeypatch.delenv(cli.GEN_ROOT_ENV, raising=False)
    assert cli.main(args[:-2]) == 1
    assert "pass --gen-root or set MOONWALKERS_GEN_ROOT" in capsys.readouterr().err


def test_build_needs_the_data_folder_layout(build_args, tmp_path: Path, capsys) -> None:
    args, _ = build_args
    elsewhere = tmp_path / "loose-run"
    elsewhere.mkdir()
    assert cli.main([args[0], str(elsewhere), *args[2:]]) == 1
    assert "pass --data" in capsys.readouterr().err
