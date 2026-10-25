"""Contract v0.2.0 (decision 0020): joint modes, adjustable stops and linked joints, and stored
v0.1.0 results that stay valid."""

import copy
import json
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from moonwalkers.contracts import SCHEMA_VERSION, PipelineResult

FIXTURE = Path(__file__).parent / "fixtures" / "ha5c_pipeline_b.example.json"
STUBS = Path(__file__).parents[1] / "src" / "moonwalkers" / "pipelines"

MANUAL = {"source_id": "manual", "locator": "PDF p. 7"}
STAND_IN = {"source_id": "user", "locator": "stand-in"}


def joint(joint_id: str, joint_type: str, child: str, **fields) -> dict:
    return {
        "joint_id": joint_id,
        "joint_type": joint_type,
        "parent_part": "frame",
        "child_part": child,
        "axis": [0, 0, -1],
        "origin_m": [0, 0, 0.7],
        "confidence": 1.0,
        "citations": [MANUAL],
        **fields,
    }


@pytest.fixture
def drill_press() -> dict:
    """A small drill press in v0.2.0: a spring-returned quill with a depth stop, handles that
    follow it at a stand-in ratio, a locked table and a driven spindle."""
    return {
        "result_id": "res-1",
        "job_id": "job-1",
        "pipeline": "C",
        "input_types": ["schematic"],
        "produced_at": "2026-10-23T12:00:00Z",
        "produced_by": "test",
        "sources": [
            {"source_id": "manual", "kind": "file", "uri": "m.pdf",
             "retrieved_at": "2026-10-20T00:00:00Z"},
            {"source_id": "user", "kind": "user_input", "uri": "user",
             "retrieved_at": "2026-10-23T00:00:00Z"},
        ],
        "parts": [
            {"part_id": p, "name": p, "geometry_format": "primitive"}
            for p in ("frame", "quill", "hub", "table", "spindle")
        ],
        "joints": [
            joint(
                "quill_travel", "prismatic", "quill", lower_limit=0.0, upper_limit=0.08255,
                mode={"kind": "spring_return", "position": 0.0, "citations": [MANUAL]},
                adjustable_stop={"position": 0.0381, "side": "upper", "citations": [MANUAL]},
            ),
            joint(
                "downfeed_handles", "revolute", "hub", lower_limit=-0.05, upper_limit=4.76,
                follows={"leader": "quill_travel", "ratio": 57.085, "stand_in": True,
                         "citations": [STAND_IN]},
            ),
            joint(
                "table_around_center", "revolute", "table",
                mode={"kind": "locked", "position": 0.7854, "citations": [MANUAL]},
            ),
            joint("spindle_rotation", "revolute", "spindle",
                  mode={"kind": "driven", "citations": [MANUAL]}),
        ],
        "issues": [{"severity": "warning", "ref": "downfeed_handles", "message": "Stand-in ratio"}],
    }  # fmt: skip


def joints_by_id(result: dict) -> dict[str, dict]:
    return {j["joint_id"]: j for j in result["joints"]}


# ------------------------------------------------------------------------------- versions
def test_new_results_write_0_2_0(drill_press: dict) -> None:
    assert SCHEMA_VERSION == "0.2.0"
    result = PipelineResult.model_validate(drill_press)
    assert result.schema_version == "0.2.0"
    assert PipelineResult.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize(
    "path",
    [FIXTURE, *sorted(STUBS.glob("*/haas_ha5c.stub.json"))],
    ids=lambda p: p.parent.name if p.name.endswith("stub.json") else p.name,
)
def test_0_1_0_results_stay_valid_and_keep_their_version(path: Path) -> None:
    """Stored results are never rewritten (decisions 0008 and 0012), so a 0.1.0 result loads as
    it is and still says 0.1.0."""
    result = PipelineResult.model_validate_json(path.read_text(encoding="utf-8"))
    assert result.schema_version == "0.1.0"
    assert json.loads(result.model_dump_json())["schema_version"] == "0.1.0"


@pytest.mark.parametrize(
    ("joint_id", "field", "value"),
    [
        ("spindle_rotation", "mode", {"kind": "driven", "citations": [MANUAL]}),
        ("quill_travel", "adjustable_stop",
         {"position": 0.02, "side": "upper", "citations": [MANUAL]}),
        ("downfeed_handles", "follows",
         {"leader": "quill_travel", "ratio": 57.085, "citations": [MANUAL]}),
    ],
)  # fmt: skip
def test_a_0_1_0_result_may_not_use_the_new_fields(
    drill_press: dict, joint_id: str, field: str, value: dict
) -> None:
    drill_press["schema_version"] = "0.1.0"
    for j in drill_press["joints"]:
        for name in ("mode", "adjustable_stop", "follows"):
            j.pop(name, None)
    PipelineResult.model_validate(drill_press)  # without them, it is a valid 0.1.0 result
    joints_by_id(drill_press)[joint_id][field] = value
    with pytest.raises(ValidationError, match="needs schema_version 0.2.0"):
        PipelineResult.model_validate(drill_press)


def test_an_unknown_version_is_refused(drill_press: dict) -> None:
    drill_press["schema_version"] = "0.3.0"
    with pytest.raises(ValidationError):
        PipelineResult.model_validate(drill_press)


# -------------------------------------------------------------------------- what is kept
def test_the_fields_are_kept_as_given(drill_press: dict) -> None:
    joints = {j.joint_id: j for j in PipelineResult.model_validate(drill_press).joints}
    quill, handles = joints["quill_travel"], joints["downfeed_handles"]
    assert quill.mode is not None and quill.mode.kind == "spring_return"
    assert quill.adjustable_stop is not None and quill.adjustable_stop.side == "upper"
    assert handles.follows is not None
    assert (handles.follows.leader, handles.follows.ratio, handles.follows.offset) == (
        "quill_travel",
        57.085,
        0.0,
    )
    assert handles.follows.stand_in is True and handles.mode is None
    assert joints["spindle_rotation"].mode.position is None


def test_a_locked_joint_without_a_position_is_held_at_the_modelled_pose(drill_press: dict) -> None:
    del joints_by_id(drill_press)["table_around_center"]["mode"]["position"]
    table = PipelineResult.model_validate(drill_press).joints[2]
    assert table.joint_id == "table_around_center"
    assert table.mode is not None and table.mode.kind == "locked" and table.mode.position is None


def test_links_may_chain(drill_press: dict) -> None:
    """PhysX: "there is no restriction on the number of mimic joints referenced by any individual
    joint" (research note 2026-10-23)."""
    drill_press["parts"].append({"part_id": "dial", "name": "dial", "geometry_format": "primitive"})
    drill_press["joints"].append(
        joint("depth_dial", "revolute", "dial", lower_limit=-1.0, upper_limit=10.0,
              follows={"leader": "downfeed_handles", "ratio": 2.0, "citations": [MANUAL]})
    )  # fmt: skip
    PipelineResult.model_validate(drill_press)


# -------------------------------------------------------------------------------- refusals
def _set(joint_id: str, **fields) -> Callable[[dict], None]:
    return lambda d: joints_by_id(d)[joint_id].update(fields)


def _loop(d: dict) -> None:
    quill = joints_by_id(d)["quill_travel"]
    del quill["mode"]
    quill["follows"] = {"leader": "downfeed_handles", "ratio": 0.0175, "citations": [MANUAL]}


def _fixed_leader(d: dict) -> None:
    d["parts"].append({"part_id": "guard", "name": "guard", "geometry_format": "primitive"})
    d["joints"].append(joint("guard_fixed", "fixed", "guard"))
    joints_by_id(d)["downfeed_handles"]["follows"]["leader"] = "guard_fixed"


UNKNOWN = {"source_id": "nowhere"}


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (_set("downfeed_handles", follows={"leader": "missing", "ratio": 1.0,
                                           "citations": [MANUAL]}), "follows unknown joint"),
        (_set("downfeed_handles", follows={"leader": "downfeed_handles", "ratio": 1.0,
                                           "citations": [MANUAL]}), "cannot follow itself"),
        (_fixed_leader, "cannot follow the fixed joint"),
        (_set("spindle_rotation", joint_type="fixed"), "is fixed, so it takes no mode"),
        (_set("downfeed_handles", mode={"kind": "free", "citations": [MANUAL]}),
         "takes no mode"),
        (_set("spindle_rotation", mode={"kind": "driven", "position": 1.0,
                                        "citations": [MANUAL]}), "takes no position"),
        (_set("table_around_center", lower_limit=-0.5, upper_limit=0.5),
         "above the upper limit"),
        (_set("quill_travel", mode={"kind": "spring_return", "position": -0.03,
                                    "citations": [MANUAL]}), "below the lower limit"),
        (_set("quill_travel", adjustable_stop={"position": 0.1, "side": "upper",
                                               "citations": [MANUAL]}), "adjustable stop"),
        (_loop, "loop back"),
        (lambda d: d.update(issues=[]), "so it needs an issue on it"),
        (lambda d: d["issues"][0].update(ref="quill_travel"), "so it needs an issue on it"),
        (_set("downfeed_handles", follows={"leader": "quill_travel", "ratio": 0.0,
                                           "citations": [MANUAL]}), "ratio 0"),
        (_set("spindle_rotation", mode={"kind": "driven", "citations": [UNKNOWN]}),
         "mode cites unknown source"),
        (_set("quill_travel", adjustable_stop={"position": 0.02, "side": "upper",
                                               "citations": [UNKNOWN]}),
         "adjustable_stop cites unknown source"),
        (_set("downfeed_handles", follows={"leader": "quill_travel", "ratio": 1.0,
                                           "citations": [UNKNOWN]}),
         "follows cites unknown source"),
        (_set("quill_travel", mode={"kind": "spring_return", "citations": []}), "at least 1"),
        (_set("quill_travel", adjustable_stop={"position": 0.02, "side": "middle",
                                               "citations": [MANUAL]}), "side"),
        (_set("spindle_rotation", mode={"kind": "braked", "citations": [MANUAL]}), "kind"),
    ],
    ids=[
        "unknown-leader", "follows-itself", "fixed-leader", "fixed-with-mode",
        "follower-with-mode", "driven-with-position", "locked-outside-limits",
        "rest-outside-limits", "stop-outside-limits", "loop", "stand-in-without-issue",
        "stand-in-issue-elsewhere", "ratio-zero", "mode-unknown-source", "stop-unknown-source",
        "link-unknown-source", "mode-without-citation", "unknown-side", "unknown-kind",
    ],
)  # fmt: skip
def test_bad_joint_behaviour_is_refused(drill_press: dict, mutate, message: str) -> None:
    bad = copy.deepcopy(drill_press)
    mutate(bad)
    with pytest.raises(ValidationError, match=message):
        PipelineResult.model_validate(bad)
