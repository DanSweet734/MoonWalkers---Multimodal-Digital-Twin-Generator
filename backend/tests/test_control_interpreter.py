"""The interpreter runs a program into the joint's target angle over time (decisions 0016, 0026).

Most tests here check decision 0016's motion, at full feed with no acceleration and a mill that
answers at once (``CONSTANT``); decision 0026's acceleration, relay and waits come at the end.

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

CONSTANT = {"acceleration_deg_s2": None, "mill_answer_s": 0.0}  # decision 0016's motion


def example(name: str, settings: RunSettings | None = None):
    program = ProgramFile.load(packaged_programs()[f"ha5c-manual-{name}"]).program()
    return run_program(program, settings or RunSettings(**CONSTANT))


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
    trajectory = example("example-2", RunSettings(step_dwell_s=0, **CONSTANT))
    moves = [(e.step, e.g, round(e.end_deg, 3)) for e in trajectory.events]
    assert moves == [(1, 91, 90.0), (2, 91, 79.75), (3, 88, 0.0)]
    # steps 1 and 3 have no F, so they run at the maximum feed rate (270 deg/s)
    assert trajectory.duration_s == pytest.approx(90 / 270 + 10.25 / 5 + 79.75 / 270)


def test_subroutine_passes_and_their_return() -> None:
    trajectory = example("example-6", RunSettings(step_dwell_s=0, **CONSTANT))
    subroutine = [e for e in trajectory.events if "subroutine" in e.what]
    assert len(subroutine) == 16 and subroutine[0].what.endswith("pass 1) at 80 deg/s")
    division = [e for e in trajectory.events if e.g == 98]
    assert [round(e.end_deg - e.start_deg, 6) for e in division] == [72.0] * 5
    assert trajectory.final_deg == pytest.approx(720.0)


def test_absolute_moves_go_straight_or_the_shorter_way() -> None:
    direct, shortest = (
        example("example-4", RunSettings(absolute=mode, **CONSTANT))
        for mode in ("direct", "shortest")
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
    trajectory = run_program(IndexProgram.from_rows(table), RunSettings(step_dwell_s=0, **CONSTANT))
    starts = [(e.g, e.start_s) for e in trajectory.events]
    assert starts == [(97, 0.0), (86, 1.5), (89, 1.5), (94, 1.5), (91, 1.75)]
    assert trajectory.duration_s == pytest.approx(1.75 + 0.5)


def test_feeds_above_the_joints_cited_top_speed_are_capped() -> None:
    trajectory = example("example-3", RunSettings(step_dwell_s=0, joint_max_deg_s=100, **CONSTANT))
    assert trajectory.duration_s == pytest.approx(720 / 100)
    assert trajectory.notes == [
        "step 01: feed 270 deg/s is above the joint's cited top speed 100 deg/s, so it runs at 100",
        "step 02: feed 270 deg/s is above the joint's cited top speed 100 deg/s, so it runs at 100",
    ]


def test_a_runaway_program_is_stopped() -> None:
    table = [[1, 0, 3, 999, 96], [2, 0, None, 1, 95], [3, 1, 270, 999, 91], [4, 0, None, 1, 99]]
    with pytest.raises(ProgramError, match="more than 10000 moves"):
        run_program(IndexProgram.from_rows(table), RunSettings(**CONSTANT))


def test_targets_between_waypoints() -> None:
    trajectory = example("example-5", RunSettings(step_dwell_s=1.0, **CONSTANT))
    assert trajectory.angle_at(-1) == 0.0 and trajectory.velocity_at(-1) == 0.0
    assert trajectory.angle_at(0.5) == pytest.approx(40.0)  # 90 deg at 80 deg/s
    assert trajectory.velocity_at(0.5) == pytest.approx(80.0)
    assert trajectory.angle_at(1.6) == pytest.approx(90.0)  # the pause after step 1
    assert trajectory.velocity_at(1.6) == 0.0
    assert trajectory.velocity_at(2.4) == pytest.approx(25.0)  # the slow feed
    assert trajectory.angle_at(1e6) == trajectory.final_deg == pytest.approx(0.0)
    assert angles(trajectory)[:3] == [0.0, 90.0, 90.0]


# ----------------------------------------------- decision 0026: acceleration and the mill's signals
def test_a_long_move_is_a_trapezoid_and_a_short_one_a_triangle() -> None:
    from moonwalkers.control.interpreter import move_profile

    long = move_profile(360.0, 270.0, 540.0)  # ramps of 0.5 s, 135 deg; 90 deg at full feed
    assert long[-1] == (pytest.approx(360 / 270 + 0.5), pytest.approx(360.0))
    short = move_profile(-72.0, 270.0, 540.0)  # never reaches 270 deg/s
    assert short[-1] == (pytest.approx(2 * (72 / 540) ** 0.5), pytest.approx(-72.0))
    for profile in (long, short):
        moved = [abs(d) for _, d in profile]
        assert moved == sorted(moved)  # it never turns back
    assert move_profile(90.0, 80.0, None) == [(0.0, 0.0), (pytest.approx(90 / 80), 90.0)]


def test_acceleration_lengthens_each_move_by_its_ramps() -> None:
    """Example #3's four 90 and five 72 degree indexes at 270 deg/s: each is too short to reach its
    feed at the 540 deg/s^2 stand-in, so each takes 2 x sqrt(angle / 540)."""
    trajectory = example("example-3", RunSettings(step_dwell_s=0))
    assert trajectory.duration_s == pytest.approx(
        4 * 2 * (90 / 540) ** 0.5 + 5 * 2 * (72 / 540) ** 0.5
    )
    assert trajectory.final_deg == pytest.approx(720.0)
    assert max(abs(trajectory.velocity_at(t / 100)) for t in range(800)) < 270.0


def test_by_default_the_relay_pulses_a_quarter_second_after_each_move() -> None:
    trajectory = example("example-3", RunSettings(step_dwell_s=0))
    moves = [e for e in trajectory.events if e.end_deg != e.start_deg]
    assert trajectory.relay_parameter == 1
    assert [(s.start_s, s.end_s) for s in trajectory.relay] == [
        (pytest.approx(m.end_s), pytest.approx(m.end_s + 0.25)) for m in moves
    ]
    during = example("example-3", RunSettings(step_dwell_s=0, relay=0))  # Parameter 1 = 0
    assert [(s.start_s, s.end_s) for s in during.relay] == [(m.start_s, m.end_s) for m in moves]


def test_relay_codes_set_parameter_1_to_2_and_drive_the_relay() -> None:
    table = [
        [1, 0, None, 1, 86],  # relay on
        [2, 90, 90, 1, 91],
        [3, 0, None, 1, 87],  # relay off
        [4, 0, None, 1, 93],  # a pulse
        [5, 0, None, 1, 89],  # wait for the mill
        [6, 0, None, 1, 99],
    ]
    trajectory = run_program(IndexProgram.from_rows(table), RunSettings(step_dwell_s=0))
    assert trajectory.relay_parameter == 2
    spans = [(round(s.start_s, 6), round(s.end_s, 6), s.why) for s in trajectory.relay]
    move_end = trajectory.events[1].end_s
    assert spans == [
        (0.0, round(move_end, 6), "G86-G87"),
        (round(move_end, 6), round(move_end + 0.25, 6), "G93"),
    ]
    (wait,) = trajectory.waits
    assert wait.start_s == pytest.approx(move_end) and wait.hold_s == 1.0
    assert trajectory.duration_s == pytest.approx(move_end + 1.0)  # the simulated mill answers
    forced = run_program(IndexProgram.from_rows(table), RunSettings(step_dwell_s=0, relay=1))
    assert "Parameter 1 = 2" in forced.notes[0]


def test_in_step_mode_each_step_waits_for_cycle_start_except_after_a_g94() -> None:
    """Parameter 10 = 0, "Stop after each step"; G94 runs "the following L steps automatically
    without waiting for start commands" (p. 36). The last step needs no cycle start."""
    table = [
        [1, 90, 270, 1, 91],
        [2, 0, None, 1, 94],
        [3, 90, 270, 1, 91],  # run at once after the G94
        [4, 90, 270, 1, 91],
        [5, 90, 270, 1, 91],
        [6, 0, None, 1, 99],
    ]
    settings = RunSettings(continue_mode="step", mill_answer_s=2.0)
    trajectory = run_program(IndexProgram.from_rows(table), settings)
    assert [w.step for w in trajectory.waits] == [1, 4]
    assert all(w.why.startswith("stopped after the step") for w in trajectory.waits)
    assert [s.why for s in trajectory.relay].count("G94: pulse at the beginning of the step") == 1
    assert trajectory.final_deg == pytest.approx(360.0)


def test_the_runners_clock_holds_at_a_wait_until_cycle_start() -> None:
    from moonwalkers.control.isaac_runner import PlanClock

    clock = PlanClock([(2.0, 1.0)])
    assert clock.advance(1.0, hold=True, pressed=False) == (1.0, False)
    assert clock.advance(2.5, hold=True, pressed=False) == (2.0, False) and clock.holding
    assert clock.advance(9.0, hold=True, pressed=False) == (2.0, False)  # still waiting
    assert clock.advance(9.5, hold=True, pressed=True) == (3.0, True)  # the wait's end
    assert clock.advance(10.0, hold=True, pressed=False) == (3.5, False) and not clock.holding
    free = PlanClock([(2.0, 1.0)])  # without holding, the simulated mill answers on plan
    assert free.advance(2.5, hold=False, pressed=False) == (2.5, False)
