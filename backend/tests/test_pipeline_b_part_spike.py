"""The Phase 4 spike's runner: its cut lists, coloured views and report."""

from pathlib import Path

import pytest

from moonwalkers.pipelines.b import part_spike
from moonwalkers.pipelines.b.mesh_tools import read_png
from moonwalkers.pipelines.b.part_cuts import assign
from moonwalkers.pipelines.b.synthetic_parts import drill_press, score


def test_the_synthetic_cut_list_finds_the_parts_of_the_fused_test_mesh() -> None:
    truth = drill_press("fused", cell=0.008)
    result = score(truth, assign(truth.mesh, part_spike.SYNTHETIC_CUTS, "frame"))
    assert result.area_share > 0.97
    assert result.per_part["table"][0] > 0.95 and result.per_part["handle_hub"][0] > 0.95


def test_every_t33901_cut_says_where_it_comes_from() -> None:
    moving = {c.part for c in part_spike.T33901_CUTS} - {"frame"}
    assert moving == {
        "spindle",
        "quill",
        "handle_hub",
        "table",
        "table_arm",
        "column_rack",
        "table_bracket",
    }
    assert all(c.note for c in part_spike.T33901_CUTS)


def test_render_parts_writes_a_colour_sheet_and_legend(tmp_path: Path, indexer) -> None:
    mesh = indexer()
    parts = ["frame"] * 12 + ["spindle"] * (len(mesh.faces) - 12)
    path = part_spike.render_parts(mesh, parts, tmp_path / "parts", size=64)
    image = read_png(path)
    assert image.shape == (128, 192, 3)
    legend = (tmp_path / "parts.txt").read_text(encoding="utf-8").splitlines()
    assert legend[0].startswith("frame: rgb(190, 190, 190)") and legend[1].startswith("spindle")
    assert (image != 255).any(axis=2).sum() > 500


def test_the_report_lists_every_row() -> None:
    rows = [
        part_spike.Row("m", "(a) shapes", 0.1, 8, area_share=0.99, face_share=0.98),
        part_spike.Row("m", "(d) camera fitted to the front photo", 50.0, 0, photo_iou=0.8,
                       note="azimuth -57.6"),
    ]  # fmt: skip
    report = part_spike.format_report(rows)
    assert "| m | (a) shapes | 0.10 | 8 | 0.990 (0.980) |" in report
    assert "silhouette IoU 0.800, azimuth -57.6" in report


@pytest.mark.slow
def test_the_spike_runs_end_to_end_on_the_synthetic_mesh(tmp_path: Path) -> None:
    assert part_spike.main([str(tmp_path), "--cell", "0.016"]) == 0
    assert (tmp_path / "report.md").exists() and (tmp_path / "results.json").exists()
    assert (tmp_path / "synthetic_rounded_a.png").exists()
