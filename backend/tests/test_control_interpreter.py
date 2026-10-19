"""The interpreter runs a program into the joint's target angle over time (decision 0016).

The manual's own claims are the strongest checks: Example #3 "could have also been done using
Circle Division", and Example #5 with a subroutine "is the same program".
"""

import pytest

from moonwalkers.control import (
    IndexProgram,
    ProgramError,
    ProgramFile,
    RunSettings,
    packaged_programs,
    run_program,
)


def example(name: str, settings: RunSettings | None = None):
    program = ProgramFile.load(packaged_programs()[f"ha5c-manual-{name}"]).program()
    return run_program(program, settings)


def angles(trajectory) -> list[float]:
    return [round(w.deg, 6) for w in trajectory.waypoints]


def test_example_3_indexes_four_then_five_holes() -> None:
    trajectory = example("example-3")
    moves = [e for e in trajectory.events if e.end_deg != e.start_deg]
    assert [round(e.end_deg - e.start_deg, 6) for e in moves] == [90.0] * 4 + [72.0] * 5
    assert trajectory.final_deg == pytest.approx(720.0)
    # 270 deg/s, and 1 s after each step (Parameter 16): 4 x (1/3 + 1) + 5 x (72/270 + 1)
    assert trajectory.duration_s == pytest.approx(4 * (1 / 3 + 1) + 5 * (72 / 270 + 1))


def test_the_manuals_equivalent_programs_give_the_same_motion() -> None:
    assert example("example-3").waypoints == example("example-3-circle-division").waypoints
    assert example("example-5").waypoints == example("example-5-subroutine").waypoints


def test_example_2_feeds_back_slowly_and_returns_home() -> None:
    trajectory = example("example-2", RunSettings(step_dwell_s=0))
    moves = [(e.step, e.g, round(e.end_deg, 3)) for e in trajectory.events]
    assert moves == [(1, 91, 90.0), (2, 91, 79.75), (3, 88, 0.0)]
    # steps 1 and 3 have no F, so they run at the maximum feed rate (270 deg/s)
    assert trajectory.duration_s == pytest.approx(90 / 270 + 10.25 / 5 + 79.75 / 270)


def test_subroutine_passes_and_their_return() -> None:
    trajectory = example("example-6", RunSettings(step_dwell_s=0))
    subroutine = [e for e in trajectory.events if "subroutine" in e.what]
    assert len(subroutine) == 16 and subroutine[0].what.endswith("pass 1) at 80 deg/s")
    division = [e for e in trajectory.events if e.g == 98]
    assert [round(e.end_deg - e.start_deg, 6) for e in division] == [72.0] * 5
    assert trajectory.final_deg == pytest.approx(720.0)


def test_absolute_moves_go_straight_or_the_shorter_way() -> None:
    direct, shortest = (
        example("example-4", RunSettings(absolute=mode)) for mode in ("direct", "shortest")
    )
    assert direct.final_deg == pytest.approx(0.0)  # 450.12 back to 0: -450.12
    assert shortest.final_deg == pytest.approx(360.0)  # 450.12 to 360: -90.12, the same on the dial
    home = next(e for e in shortest.events if e.g == 88)
    assert home.end_deg - home.start_deg == pytest.approx(-90.12)


def test_dwells_signals_and_the_g94_delay() -> None:
    table = [
        [1, 0, None, 15, 97],  # dwell 1.5 s
        [2, 0, None, 1, 86],  # relay on: no motion, no time
        [3, 0, None, 1, 89],  # wait for the mill: the simulation goes on
        [4, 0, None, 1, 94],  # pulse the relay: 0.25 s before the next step
        [5, 45, 90, 1, 91],
        [6, 0, None, 1, 99],
    ]
    trajectory = run_program(IndexProgram.from_rows(table), RunSettings(step_dwell_s=0))
    starts = [(e.g, e.start_s) for e in trajectory.events]
    assert starts == [(97, 0.0), (86, 1.5), (89, 1.5), (94, 1.5), (91, 1.75)]
    assert trajectory.duration_s == pytest.approx(1.75 + 0.5)


def test_feeds_above_the_joints_cited_top_speed_are_capped() -> None:
    trajectory = example("example-3", RunSettings(step_dwell_s=0, joint_max_deg_s=100))
    assert trajectory.duration_s == pytest.approx(720 / 100)
    assert trajectory.notes == [
        "step 01: feed 270 deg/s is above the joint's cited top speed 100 deg/s, so it runs at 100",
        "step 02: feed 270 deg/s is above the joint's cited top speed 100 deg/s, so it runs at 100",
    ]


def test_a_runaway_program_is_stopped() -> None:
    table = [[1, 0, 3, 999, 96], [2, 0, None, 1, 95], [3, 1, 270, 999, 91], [4, 0, None, 1, 99]]
    with pytest.raises(ProgramError, match="more than 10000 moves"):
        run_program(IndexProgram.from_rows(table))


def test_targets_between_waypoints() -> None:
    trajectory = example("example-5", RunSettings(step_dwell_s=1.0))
    assert trajectory.angle_at(-1) == 0.0 and trajectory.velocity_at(-1) == 0.0
    assert trajectory.angle_at(0.5) == pytest.approx(40.0)  # 90 deg at 80 deg/s
    assert trajectory.velocity_at(0.5) == pytest.approx(80.0)
    assert trajectory.angle_at(1.6) == pytest.approx(90.0)  # the pause after step 1
    assert trajectory.velocity_at(1.6) == 0.0
    assert trajectory.velocity_at(2.4) == pytest.approx(25.0)  # the slow feed
    assert trajectory.angle_at(1e6) == trajectory.final_deg == pytest.approx(0.0)
    assert angles(trajectory)[:3] == [0.0, 90.0, 90.0]
