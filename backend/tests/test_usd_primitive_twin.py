"""The box-and-cylinder test twin and its command."""

import math
from datetime import datetime
from pathlib import Path

from pxr import Usd, UsdPhysics

from moonwalkers.kb import machine_key
from moonwalkers.usd.primitive_twin import build_test_twin, main

JOINT = "/moonwalkers_testindexer/joints/spindle_rotation"


def test_test_twin_is_labelled_synthetic(fixed_time: datetime) -> None:
    twin, result = build_test_twin(fixed_time)
    assert twin.machine_key == "moonwalkers/testindexer"
    assert machine_key(result.identity.manufacturer, result.identity.model) == twin.machine_key
    assert twin.built_from == [result.result_id]
    assert any("Synthetic test model" in i.message for i in result.issues)
    assert "made up" in result.sources[0].title
    assert result.needs_human_review is True


def test_command_writes_both_files_and_run_notes(tmp_path: Path, capsys) -> None:
    assert main([str(tmp_path)]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "RUN.md",
        "quarter_turn.usda",
        "spin.usda",
    ]
    assert capsys.readouterr().out.count("0 error(s)") == 2

    spin = Usd.Stage.Open(str(tmp_path / "spin.usda"))
    drive = UsdPhysics.DriveAPI(spin.GetPrimAtPath(JOINT), "angular")
    assert math.isclose(drive.GetTargetVelocityAttr().Get(), 30.0, abs_tol=1e-4)

    quarter = Usd.Stage.Open(str(tmp_path / "quarter_turn.usda"))
    drive = UsdPhysics.DriveAPI(quarter.GetPrimAtPath(JOINT), "angular")
    assert math.isclose(drive.GetTargetPositionAttr().Get(), 90.0, abs_tol=1e-4)

    notes = (tmp_path / "RUN.md").read_text(encoding="utf-8")
    assert "usd-core" in notes and "## Isaac Sim check (fill in)" in notes
