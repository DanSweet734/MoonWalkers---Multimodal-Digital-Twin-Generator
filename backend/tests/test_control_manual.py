"""A manual machine's controls (decision 0025): the specs, the controller's rules, the scenarios."""

import copy
import json
import math

import pytest
from conftest import PHOTO_STOP_M, T33901_REFERENCE

from moonwalkers.contracts.pipeline_result import ControlBehavior
from moonwalkers.control import ProgramError, manual_controls, plan_scenario
from moonwalkers.control.isaac_controls import Controller, Refused, ScenarioPlayer
from moonwalkers.control.manual import check_behavior, controller_spec


def behaviors() -> list[ControlBehavior]:
    data = json.loads(T33901_REFERENCE.read_text(encoding="utf-8"))
    return [ControlBehavior.model_validate(b) for b in data["control"]]


@pytest.fixture
def spec(controlled_drill_press) -> dict:
    _, result = controlled_drill_press
    (controls,) = manual_controls(result.control)
    joints = {j.joint_id: j for j in result.joints}
    return controller_spec(controls, joints, {j: f"/twin/joints/{j}" for j in joints}, "test")


def on(controller: Controller) -> None:
    for name, state in (("power", "connected"), ("key", "in"), ("paddle", "up")):
        controller.set_input(name, state)


# ----------------------------------------------------------------------------- the specs
def test_the_t33901_reference_carries_one_operator_command_set() -> None:
    (controls,) = manual_controls(behaviors())
    assert controls.name == "operator-controls"
    assert [b.behavior_id for b in controls.behaviors] == [
        "power_switch",
        "spindle_speed",
        "operator_controls",
    ]
    assert [r.rpm for r in controls.speed_spec.rows] == [
        340, 500, 530, 660, 740, 790, 1380, 1420, 1680, 1860, 2200, 2860,
    ]  # fmt: skip
    assert [r.belts for r in controls.speed_spec.rows if r.belts] == ["B-3"]
    assert set(controls.operator_spec.scenarios) == {"drilling-stroke", "no-key-no-start"}


def edited(behavior_id: str, change) -> list[ControlBehavior]:
    out = []
    for b in behaviors():
        if b.behavior_id == behavior_id:
            spec = copy.deepcopy(b.spec)
            change(spec)
            b = b.model_copy(update={"spec": spec})
        out.append(b)
    return out


@pytest.mark.parametrize(
    ("behavior_id", "change", "message"),
    [
        ("power_switch", lambda s: s["on_when"].update(lamp="on"), "no input 'lamp'"),
        ("power_switch", lambda s: s["off_why"].pop("key"), "off_why"),
        ("spindle_speed", lambda s: s.update(initial_rpm=800), "not in the table"),
        ("spindle_speed", lambda s: s.update(switch="other"), "names the switch"),
        ("operator_controls", lambda s: s.update(speed="power_switch"), "not a lookup_table"),
        (
            "operator_controls",
            lambda s: s["scenarios"].update(live=s["scenarios"]["drilling-stroke"]),
            "not 'live'",
        ),
        (
            "operator_controls",
            lambda s: s["scenarios"]["drilling-stroke"]["steps"].append({"do": "wait"}),
            r"a 'wait' step takes \['s'\]",
        ),
    ],
)
def test_a_spec_that_cannot_be_read_is_refused(behavior_id, change, message) -> None:
    with pytest.raises(ProgramError, match=message):
        manual_controls(edited(behavior_id, change))


def test_add_control_checks_each_behaviour_alone_and_with_the_ones_it_names() -> None:
    switch, speed, operator = behaviors()
    check_behavior(switch)
    check_behavior(speed)
    check_behavior(operator)  # its switch and speed table are not recorded yet
    check_behavior(operator, [switch, speed])
    broken = switch.model_copy(update={"spec": {**switch.spec, "start_input": "lamp"}})
    with pytest.raises(ProgramError, match="start_input"):
        check_behavior(broken)


def test_the_hand_drives_a_sprung_slide_and_the_speed_table_a_turning_joint(
    controlled_drill_press,
) -> None:
    _, result = controlled_drill_press
    (controls,) = manual_controls(result.control)
    joints = {j.joint_id: j for j in result.joints}
    paths = {j: j for j in joints}
    unsprung = {**joints, "quill_travel": joints["quill_travel"].model_copy(update={"mode": None})}
    with pytest.raises(ProgramError, match="no spring"):
        controller_spec(controls, unsprung, paths, "test")
    del joints["spindle_rotation"]
    with pytest.raises(ProgramError, match="not a turning joint"):
        controller_spec(controls, joints, paths, "test")


def test_the_runner_json_carries_what_the_exporter_writes_for_the_quill(spec) -> None:
    quill = spec["joints"]["quill"]
    assert quill["stop_m"] == PHOTO_STOP_M
    assert quill["spring_target_m"] == pytest.approx(-0.03)  # the spring's preload (0018)
    assert quill["stiffness"] == 600.0 and quill["damping"] == 49.0
    assert quill["gravity_offset_m"] == pytest.approx(9.81 / 600)  # the axis points down
    assert spec["joints"]["spindle"]["path"] == "/twin/joints/spindle_rotation"


# ---------------------------------------------------------------------------- the rules
def test_the_motor_runs_only_plugged_in_with_the_key_in_and_the_paddle_up(spec) -> None:
    c = Controller(spec)
    c.set_input("power", "connected")
    lines = c.set_input("paddle", "up")
    assert not c.motor_on
    no_key = "'Removal of yellow key disables switch so motor cannot start' (p. 6)"
    assert lines == ["paddle up", f"the motor does not start: {no_key}"]
    c.set_input("paddle", "down")
    assert c.set_input("key", "in") == ["key in"]
    assert c.set_input("paddle", "up") == ["paddle up", "motor starts"]
    assert c.motor_on
    assert c.set_input("paddle", "down") == ["paddle down", "motor stops"]


def test_unplugged_the_switch_says_so(spec) -> None:
    c = Controller(spec)
    c.set_input("key", "in")
    _, line = c.set_input("paddle", "up")
    assert "not connected to power" in line and "p. 26" in line


def test_a_change_the_manual_does_not_describe_is_refused_or_noted(spec) -> None:
    c = Controller(spec)
    on(c)
    with pytest.raises(Refused, match="removing the key while the motor runs"):
        c.set_input("key", "out")
    assert c.motor_on  # nothing changed
    lines = c.set_input("key", "out", strict=False)  # a person in the Property panel
    assert lines[1].startswith("not described by the manual: removing the key")
    assert lines[-1] == "motor stops"


def test_the_speed_is_one_of_the_twelve_and_changes_only_unplugged(spec) -> None:
    c = Controller(spec)
    assert c.rpm == 790
    assert c.set_speed(340) == ["speed set to 340 RPM"]
    assert c.set_speed(790) == ["speed set to 790 RPM (belts B-3)"]
    with pytest.raises(Refused, match="800 RPM is not one of the settings"):
        c.set_speed(800)
    c.set_input("power", "connected")
    with pytest.raises(Refused, match="DISCONNECT MACHINE FROM POWER"):
        c.set_speed(340)
    assert c.rpm == 790


def test_the_spindle_ramps_up_and_coasts_down(spec) -> None:
    c = Controller(spec)
    on(c)
    targets = [c.step(0.25) for _ in range(4)]  # run-up 1 s, a stand-in
    assert [t["rpm"] for t in targets] == pytest.approx([197.5, 395, 592.5, 790])
    assert targets[-1]["spindle_deg_s"] == pytest.approx(790 * 6)
    c.set_input("paddle", "down")
    assert c.step(2.5)["rpm"] == pytest.approx(395)  # coast-down 5 s
    assert c.step(10)["rpm"] == 0.0


def test_the_hand_pulls_to_the_stop_presses_on_it_and_lets_the_spring_return_it(spec) -> None:
    c = Controller(spec)
    quill = spec["joints"]["quill"]
    assert c.step(0.1)["quill_target_m"] == quill["spring_target_m"]
    c.pull(0.01)  # 10 mm/s, down to the stop
    t = c.step(1.0)
    assert c.hand == pytest.approx(0.01)
    assert t["quill_target_m"] == pytest.approx(0.01 - quill["gravity_offset_m"])
    assert t["quill_velocity_m_s"] == pytest.approx(0.01)
    for _ in range(10):
        t = c.step(1.0)
    assert t["quill_target_m"] == pytest.approx(PHOTO_STOP_M + 0.03)  # pressing on the stop
    assert t["quill_velocity_m_s"] == 0.0
    assert c.release()[0].startswith("release the handles: 'Spindle automatically returns")
    assert c.step(0.1)["quill_target_m"] == quill["spring_target_m"]


def test_a_pull_to_a_point_holds_there_and_must_stay_above_the_stop(spec) -> None:
    c = Controller(spec)
    c.pull(0.03, to_m=0.0303)
    for _ in range(3):
        t = c.step(0.5)
    assert c.hand == pytest.approx(0.0303)
    assert t["quill_target_m"] == pytest.approx(0.0303 - 9.81 / 600)
    assert t["quill_velocity_m_s"] == 0.0
    with pytest.raises(Refused, match="above the depth stop"):
        c.pull(0.03, to_m=0.05)
    with pytest.raises(Refused, match="go down from the hand"):
        c.pull(0.03, to_m=0.01)


# ------------------------------------------------------------------------------ scenarios
def test_a_scenario_runs_its_steps_one_after_another(spec) -> None:
    c = Controller(spec)
    steps = [
        {"do": "wait", "s": 2.0},
        {"do": "pull", "to_m": 0.03, "speed_m_s": 0.03},
        {"do": "release"},
    ]
    player = ScenarioPlayer(c, steps)
    assert [n for n, *_ in player.advance(0.0)] == [1]
    assert player.advance(1.9) == []
    assert [(n, start) for n, start, *_ in player.advance(2.0)] == [(2, 2.0)]
    assert player.advance(2.9) == []
    (ran,) = player.advance(3.0)
    assert ran[:2] == (3, pytest.approx(3.0))  # 30 mm at 30 mm/s
    assert player.done


def test_a_scenario_step_the_manual_does_not_allow_names_its_number(spec) -> None:
    steps = [{"do": "set", "input": "power", "state": "connected"}, {"do": "set_speed", "rpm": 340}]
    with pytest.raises(Refused, match=r"step 2 \(set_speed\): disconnect the machine first"):
        ScenarioPlayer(Controller(spec), steps).advance(0.0)
    note = ScenarioPlayer(Controller(spec), steps, strict=False).advance(0.0)
    assert note[1][3][0].startswith("refused: disconnect the machine first")


def test_the_drilling_stroke_feeds_to_the_stop_and_the_spring_returns_the_quill(spec) -> None:
    plan = plan_scenario(spec, "drilling-stroke")
    m = plan.milestones
    assert plan.dt == pytest.approx(1 / 60)
    assert [e.do for e in plan.events][:5] == ["set_speed", "set", "set", "set", "wait"]
    assert m["motor_on_s"] == 0.0 and m["top_rpm"] == 790
    # 30.3 mm in about 1 s, then 12.7 mm at 0.004 in/rev x 790 RPM (1.338 mm/s): 9.49 s
    pulls = [e.t for e in plan.events if e.do == "pull"]
    assert pulls == pytest.approx([2.0, 3.01])
    assert m["released_s"] == pytest.approx(3.01 + 0.0127 / 0.001338 + 1.0, abs=1e-3)
    assert m["quill_at_stop_s"] < m["released_s"] < m["quill_home_s"] < m["motor_off_s"]
    # the reference quill follows the hand within half a millimetre while it is pulled
    for t, x, target in zip(plan.times, plan.predicted_quill_m, plan.quill_target_m, strict=True):
        if 2.5 <= t <= 12.0:
            assert x == pytest.approx(target + 9.81 / 600, abs=5e-4)
    assert max(plan.predicted_quill_m) <= PHOTO_STOP_M + 1e-12
    assert plan.rpm[-1] == 0.0  # it coasted to a stop before the key came out


def test_without_the_key_the_motor_does_not_start(spec) -> None:
    plan = plan_scenario(spec, "no-key-no-start")
    first = next(e for e in plan.events if e.do == "set" and e.step == 2)
    assert first.said[0] == "paddle up" and "cannot start" in first.said[1]
    assert plan.milestones["motor_on_s"] == pytest.approx(4.0)
    assert not any(plan.motor_on[: round(4.0 / plan.dt)])


def test_planning_refuses_a_scenario_the_manual_does_not_allow(spec) -> None:
    spec = copy.deepcopy(spec)
    steps = spec["scenarios"]["drilling-stroke"]["steps"]
    steps.insert(2, {"do": "set_speed", "rpm": 340})  # after plugging in
    with pytest.raises(ProgramError, match="scenario 'drilling-stroke': step 3"):
        plan_scenario(spec, "drilling-stroke")


def test_gravity_offset_follows_the_axis(controlled_drill_press) -> None:
    _, result = controlled_drill_press
    (controls,) = manual_controls(result.control)
    joints = {j.joint_id: j for j in result.joints}
    tilted = joints["quill_travel"].model_copy(update={"axis": (0.0, 1.0, -1.0)})
    joints["quill_travel"] = tilted
    spec = controller_spec(controls, joints, {j: j for j in joints}, "test")
    assert spec["joints"]["quill"]["gravity_offset_m"] == pytest.approx(9.81 / math.sqrt(2) / 600)
