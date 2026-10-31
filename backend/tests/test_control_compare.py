"""Measuring a joint recording against a scenario's plan (decision 0025)."""

import json
import math
from pathlib import Path

import pytest

from moonwalkers.control import controls_files, write_controls_folder
from moonwalkers.control.cli import main as control_cli
from moonwalkers.control.compare import compare, format_measures, read_recording
from moonwalkers.usd.isaac_recorder import Recording


@pytest.fixture
def plan(tmp_path: Path, controlled_drill_press) -> dict:
    twin, result = controlled_drill_press
    (controls,) = controls_files([result])
    out = write_controls_folder(tmp_path / "controls", controls, twin, [result], tmp_path)
    path = out.folder / "trajectory_drilling-stroke.json"
    return json.loads(path.read_text(encoding="utf-8"))


def recording_of(plan: dict, bounce_mm: float = 0.0) -> dict[str, list[float]]:
    """What the recorder would write if the twin did exactly as planned, with a bounce added
    0.5 s after the release."""
    names = ["quill_travel", "spindle_rotation", "downfeed_handles"]
    rec = Recording(names, [1, 0, 0], velocities=True)
    released = plan["milestones"]["released_s"]
    ratio = plan["followers"][0]["ratio"]  # the stand-in, 57.09 rad per m (decision 0019)
    for t, x, rpm in zip(plan["times"], plan["predicted_quill_m"], plan["rpm"], strict=True):
        if bounce_mm and released + 0.5 <= t <= released + 0.6:
            x += bounce_mm / 1000
        w = rpm * 2 * math.pi / 60
        rec.add(t, [x, (w * t) % (2 * math.pi), ratio * x], [0.0, w, 0.0])
    lines = rec.csv_text().splitlines()
    columns = {name: [] for name in lines[0].split(",")}
    for line in lines[1:]:
        for name, value in zip(columns, line.split(","), strict=True):
            columns[name].append(float(value))
    return columns


def by_what(measures) -> dict:
    return {m.what: m for m in measures}


def seconds(measure) -> float:
    return float(measure.recorded.removesuffix(" s"))


def test_a_recording_that_does_as_planned_measures_as_planned(plan) -> None:
    m = by_what(compare(recording_of(plan), plan))
    assert m["quill reaches the stop"].recorded == m["quill reaches the stop"].planned
    assert m["quill at the stop, median"].recorded == "43.00 mm"
    assert m["quill home after the release"].recorded == m["quill home after the release"].planned
    assert m["bounces off the top after the release"].recorded == "0"
    assert m["quill's largest distance from the reference while pulled"].recorded == "0.00 mm"
    assert m["spindle's steady speed, median"].recorded == "790.0 RPM"
    step = 0.025  # a 60 Hz sample, printed to 0.01 s; run-up and coast-down are stand-ins
    assert seconds(m["spindle at 95% of its speed after the start"]) == pytest.approx(
        0.95, abs=step
    )
    assert seconds(m["spindle below 1% after the stop"]) == pytest.approx(4.95, abs=step)
    handles = m["downfeed_handles per m of quill_travel"]
    assert handles.recorded == "57.09 rad/m" and handles.planned == "57.09 rad/m (a stand-in)"


def test_a_bounce_after_the_release_is_counted(plan) -> None:
    m = by_what(compare(recording_of(plan, bounce_mm=4.5), plan))
    assert m["bounces off the top after the release"].recorded == "1 (4.5 mm)"
    settled = float(m["quill settled within 1 mm of home"].recorded.removesuffix(" s"))
    assert settled > plan["milestones"]["released_s"] + 0.6


def test_a_recording_without_velocities_says_the_speed_was_not_recorded(plan) -> None:
    recording = recording_of(plan)
    del recording["spindle_rotation (rad/s)"]
    m = by_what(compare(recording, plan))
    assert m["spindle speed"].recorded == "not recorded (positions only)"


def test_the_command_line_compares_a_recording_file(tmp_path: Path, plan, capsys) -> None:
    columns = recording_of(plan)
    csv = tmp_path / "rec.csv"
    rows = zip(*columns.values(), strict=True)
    csv.write_text(
        ",".join(columns) + "\n" + "\n".join(",".join(map(repr, r)) for r in rows) + "\n",
        encoding="utf-8",
    )
    assert read_recording(csv)["time_s"][:2] == [0.0, pytest.approx(1 / 60)]
    trajectory = tmp_path / "plan.json"
    trajectory.write_text(json.dumps(plan), encoding="utf-8")
    assert control_cli(["compare", str(csv), str(trajectory)]) == 0
    out = capsys.readouterr().out
    assert "against drilling-stroke on" in out and "quill reaches the stop" in out
    assert format_measures(compare(columns, plan)).splitlines()[0].startswith("Measure")
