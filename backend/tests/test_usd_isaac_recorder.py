"""The joint recorder's parts that run outside Isaac Sim."""

import math
from datetime import datetime
from pathlib import Path

import pytest

from moonwalkers.usd import isaac_recorder as rec
from moonwalkers.usd.exporter import build_stage


def test_a_recording_is_csv_with_units_per_joint() -> None:
    recording = rec.Recording(["quill_travel", "downfeed_handles"], [1, 0])
    recording.add(0.0, [0.08255, 4.712])
    recording.add(1 / 60, [0.07, math.nan])
    lines = recording.csv_text().splitlines()
    assert lines[0] == "time_s,quill_travel (m),downfeed_handles (rad)"
    assert lines[1] == "0.0,0.08255,4.712"
    assert lines[2].endswith(",0.07,nan")


@pytest.mark.parametrize(
    ("names", "kinds", "positions"), [(["a"], [0, 1], [0.0]), (["a"], [0], [])]
)
def test_mismatched_columns_are_refused(names, kinds, positions) -> None:
    with pytest.raises(ValueError):
        recording = rec.Recording(names, kinds)
        recording.add(0.0, positions)


def test_the_recorder_starts_a_new_run_when_time_goes_back(tmp_path: Path) -> None:
    recorder = rec.Recorder(["slide"], [1], lambda run: tmp_path / f"run{run}.csv")
    writes = []
    for step in range(rec.WRITE_EVERY):
        writes += recorder.step(step / 60, [step * 0.001])
    assert [path.name for path, _ in writes] == ["run1.csv"]  # every WRITE_EVERY steps
    assert writes[0][1].count("\n") == rec.WRITE_EVERY + 1  # header and rows
    writes = recorder.step(0.0, [0.0])  # Stop, then Play
    assert [path.name for path, _ in writes] == ["run1.csv"]  # the finished run
    assert recorder.runs == 2 and recorder.path.name == "run2.csv"
    assert [path.name for path, text in recorder.flush()] == ["run2.csv"]


def test_recordings_go_beside_the_opened_file() -> None:
    now = datetime(2026, 10, 22, 19, 5, 7)
    first = rec.recording_path(Path("runs/r1/all_motions.usdc"), 1, now)
    assert first == Path("runs/r1/recordings/all_motions_2026-10-22_190507.csv")
    assert rec.recording_path(Path("x/t.usdc"), 3, now).name == "t_2026-10-22_190507_run3.csv"


def test_it_finds_the_twins_articulation(slider) -> None:
    twin, result = slider
    stage = build_stage(twin, [result])
    assert rec.find_articulation(stage) == "/test_slider"


def test_importing_it_outside_isaac_sim_starts_nothing() -> None:
    import builtins

    assert getattr(builtins, rec.HANDLE, None) is None
