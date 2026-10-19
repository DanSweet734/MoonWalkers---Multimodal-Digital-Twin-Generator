"""The images and output files a run folder offers a person, in a fixed order."""

from pathlib import Path

from moonwalkers.workspace import Workspace, run_images, run_outputs

RUN = "machines/haas-ha5c/runs/2026-10-18_run-001"


def test_images_and_outputs_are_listed_with_labels(tmp_path: Path) -> None:
    ws = Workspace(tmp_path)
    run_dir = tmp_path / RUN
    for name in (
        "generator/prepared/single.png",
        "generator/mesh.glb",
        "generator/generator.log",
        "inspect_raw/views.png",
        "inspect_raw/view_front.png",  # single views are not listed
        "preview/assembled/views.png",
        "isaac-sim/2026-10-18_measurements.png",
        "isaac-sim/notes.txt",  # not an image
        "twin.usdc",
        ".twin.tmp.usdc",  # a temporary file is never listed
        "checks/spin.usdc",
        "RUN.md",
        "request.json",
        "meshes/body.glb",
    ):
        path = run_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")

    images = run_images(ws, run_dir)
    assert [(i.label, i.path) for i in images] == [
        ("Generator input (single)", f"{RUN}/generator/prepared/single.png"),
        ("Generated mesh, generator axes", f"{RUN}/inspect_raw/views.png"),
        ("Preview: assembled", f"{RUN}/preview/assembled/views.png"),
        (
            "Isaac Sim check: 2026-10-18_measurements.png",
            f"{RUN}/isaac-sim/2026-10-18_measurements.png",
        ),
    ]
    outputs = run_outputs(ws, run_dir)
    assert [(o.kind, o.path.removeprefix(f"{RUN}/")) for o in outputs] == [
        ("usd", "twin.usdc"),
        ("check", "checks/spin.usdc"),
        ("notes", "RUN.md"),
        ("record", "request.json"),
        ("mesh", "meshes/body.glb"),
        ("mesh", "generator/mesh.glb"),
        ("log", "generator/generator.log"),
    ]
    assert outputs[0].label == "Twin (twin.usdc)"


def test_an_empty_run_folder_offers_nothing(tmp_path: Path) -> None:
    run_dir = tmp_path / RUN
    run_dir.mkdir(parents=True)
    ws = Workspace(tmp_path)
    assert run_images(ws, run_dir) == [] and run_outputs(ws, run_dir) == []
