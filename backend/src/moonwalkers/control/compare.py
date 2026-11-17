"""Measure a joint recording from Isaac Sim against a scenario's plan (decision 0025).

The recording is the joint recorder's CSV (``record_joints.py``): ``time_s``, each joint's
position (``<joint> (m)`` or ``(rad)``) and, from Phase 6, its velocity (``(m/s)``, ``(rad/s)``).
The plan is a controls folder's ``trajectory_<scenario>.json``. The measures are the functional
check of level 3 (methodology, "Evaluation"):

- the quill: when it reached the depth stop, where it rested there, when it was home after the
  release, how long it took to settle, and how far it strayed from the reference response while
  the hand held it;
- the spindle: its steady speed against the setting, and how long it took to reach it and to stop;
- each joint that follows the quill (the downfeed handles): the ratio it kept.

An arm's iRC program (decision 0033) is measured joint by joint; a Haas mill program (decision
0035) by the tool tip: its distance from the plan and from the programmed path, in mm, when each
block's move arrived, and the time against the plan. A mill is measured from positions only: the
recorder's velocity column is not trusted under the stiff hold (Phase 4's hand-off), except the
spindle's, whose position wraps.
"""

from __future__ import annotations

import csv
import itertools
import math
import statistics
from bisect import bisect_left
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HOME_TOLERANCE_M = 0.001  # within 1 mm of the rest position counts as home
STOP_TOLERANCE_M = 0.0005  # within 0.5 mm of the stop counts as at the stop
ARM_KIND = "irc_joint_program"  # an arm's trajectory.json (decision 0033)
ARRIVE_DEG = 0.5  # within half a degree of a move's target counts as arrived
MILL_KIND = "haas_gcode_program"  # a mill's trajectory.json (decision 0035)
ARRIVE_MM = 0.1  # a sliding axis's arrival: the tip within 0.1 mm of a block's end point
PATH_WINDOW_S = 1.0  # the programmed path near a sample: the plan within a second of its time
SPEED_SPAN_S = 0.05  # top speeds from positions this far apart (3 physics steps at 60 per s)


@dataclass(frozen=True)
class Measure:
    what: str
    recorded: str
    planned: str


def read_recording(path: Path) -> dict[str, list[float]]:
    """The recording's columns by name."""
    with Path(path).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows or rows[0][0] != "time_s":
        raise ValueError(f"{path}: not a joint recording (its first column is not time_s)")
    columns: dict[str, list[float]] = {name: [] for name in rows[0]}
    for row in rows[1:]:
        for name, value in zip(rows[0], row, strict=True):
            columns[name].append(float(value))
    return columns


def compare(recording: Mapping[str, Sequence[float]], plan: Mapping[str, Any]) -> list[Measure]:
    """The measures of ``recording`` against ``plan`` (a trajectory JSON, loaded): an arm's iRC
    program (decision 0033), else a manual machine's scenario (decision 0025)."""
    if plan.get("kind") == ARM_KIND:
        return compare_arm(recording, plan)
    if plan.get("kind") == MILL_KIND:
        return compare_mill(recording, plan)
    times = list(recording["time_s"])
    quill = plan["quill"]
    spindle = plan["spindle"]
    m = plan["milestones"]
    out: list[Measure] = []
    x = _column(recording, f"{quill['joint_id']} (m)")
    if x is not None:
        out += _quill_measures(times, x, plan, quill, m)
    w = _column(recording, f"{spindle['joint_id']} (rad/s)")
    if w is not None:
        out += _spindle_measures(times, [abs(v) * 60 / (2 * math.pi) for v in w], plan, m)
    elif _column(recording, f"{spindle['joint_id']} (rad)") is not None:
        out.append(
            Measure("spindle speed", "not recorded (positions only)", f"{m['top_rpm']:g} RPM")
        )
    for follower in plan.get("followers", []):
        y = _column(recording, f"{follower['joint_id']} (rad)")
        if x is not None and y is not None:
            ratio = _slope(x, y)
            label = " (a stand-in)" if follower.get("stand_in") else ""
            out.append(
                Measure(
                    f"{follower['joint_id']} per m of {quill['joint_id']}",
                    "n/a" if ratio is None else f"{ratio:.2f} rad/m",
                    f"{follower['ratio']:.2f} rad/m{label}",
                )
            )
    return out


def _quill_measures(
    times: list[float], x: list[float], plan: Mapping[str, Any], quill: Mapping[str, Any], m: Any
) -> list[Measure]:
    stop, rest = quill["stop_m"], quill["rest_m"]
    out = []
    at_stop = _first(times, x, lambda v: v >= stop - STOP_TOLERANCE_M)
    out.append(Measure("quill reaches the stop", _s(at_stop), _s(m.get("quill_at_stop_s"))))
    released = m.get("released_s")
    if at_stop is not None and released is not None and released > at_stop:
        held = [v for t, v in zip(times, x, strict=True) if at_stop <= t <= released]
        if held:
            out.append(
                Measure(
                    "quill at the stop, median",
                    f"{statistics.median(held) * 1000:.2f} mm",
                    f"{stop * 1000:.2f} mm",
                )
            )
    if released is not None:
        after = [(t, v) for t, v in zip(times, x, strict=True) if t > released]
        home = next((t for t, v in after if v <= rest + HOME_TOLERANCE_M), None)
        out.append(Measure("quill home after the release", _s(home), _s(m.get("quill_home_s"))))
        settled = _settled(after, rest)
        out.append(Measure("quill settled within 1 mm of home", _s(settled), "(no bounce planned)"))
        peaks = _bounces(after, rest)
        out.append(
            Measure(
                "bounces off the top after the release",
                f"{len(peaks)}"
                + (f" ({', '.join(f'{p * 1000:.1f}' for p in peaks)} mm)" if peaks else ""),
                "0",
            )
        )
    first_pull = next((e["t"] for e in plan["events"] if e["do"] == "pull"), None)
    if first_pull is not None and released is not None:
        predicted = list(zip(plan["times"], plan["predicted_quill_m"], strict=True))
        worst = 0.0
        for t, v in zip(times, x, strict=True):
            if first_pull <= t <= released:
                worst = max(worst, abs(v - _at(predicted, t)))
        out.append(
            Measure(
                "quill's largest distance from the reference while pulled",
                f"{worst * 1000:.2f} mm",
                "0",
            )
        )
    return out


def _spindle_measures(
    times: list[float], rpm: list[float], plan: Mapping[str, Any], m: Any
) -> list[Measure]:
    top, on, off = m.get("top_rpm") or 0.0, m.get("motor_on_s"), m.get("motor_off_s")
    if not top or on is None:
        peak = max(rpm, default=0.0)
        return [Measure("spindle's top speed", f"{peak:.1f} RPM", "0 RPM (the motor never runs)")]
    up = _first(times, rpm, lambda v: v >= 0.95 * top)
    out = [Measure("spindle at 95% of its speed after the start", _s(_minus(up, on)), "run-up")]
    end = off if off is not None else times[-1]
    steady = [v for t, v in zip(times, rpm, strict=True) if (up or on) + 0.5 <= t <= end]
    if steady:
        out.append(
            Measure(
                "spindle's steady speed, median",
                f"{statistics.median(steady):.1f} RPM",
                f"{top:g} RPM",
            )
        )
    if off is not None:
        stopped = next(
            (t for t, v in zip(times, rpm, strict=True) if t > off and v < 0.01 * top), None
        )
        out.append(
            Measure("spindle below 1% after the stop", _s(_minus(stopped, off)), "coast-down")
        )
    return out


def compare_arm(recording: Mapping[str, Sequence[float]], plan: Mapping[str, Any]) -> list[Measure]:
    """An arm's iRC program (decision 0033): each joint against its planned angle over time, its
    top speed against the cited one, where it ended, and when each move's joints all arrived."""
    times = list(recording["time_s"])
    plan_t = list(plan["times"])
    end = plan["duration_s"]
    out: list[Measure] = []
    arrived: dict[str, list[float]] = {}
    for joint in plan["joints"]:
        joint_id = joint["joint_id"]
        rad = _column(recording, f"{joint_id} (rad)")
        if rad is None:
            out.append(Measure(f"{joint_id}", "not recorded", "a column '<joint> (rad)'"))
            continue
        deg = [math.degrees(v) for v in rad]
        arrived[joint_id] = deg
        planned = list(zip(plan_t, plan["twin_deg"][joint_id], strict=True))
        during = [(t, v) for t, v in zip(times, deg, strict=True) if t <= end]
        worst = max(((abs(v - _at(planned, t)), t) for t, v in during), default=(0.0, 0.0))
        out.append(
            Measure(
                f"{joint_id}: largest distance from the plan",
                f"{worst[0]:.2f} deg (at {worst[1]:.2f} s)",
                "0",
            )
        )
        after = [v for t, v in zip(times, deg, strict=True) if t >= end]
        final = planned[-1][1]
        out.append(
            Measure(
                f"{joint_id}: where it ended",
                "not recorded (the recording stops before the plan ends)"
                if not after
                else f"{statistics.median(after):.2f} deg",
                f"{final:.2f} deg",
            )
        )
        speed = _column(recording, f"{joint_id} (rad/s)")
        if speed is not None:
            peak = max((abs(math.degrees(v)) for v in speed), default=0.0)
            pieces = itertools.pairwise(planned)
            top = max(
                (abs(b - a) / (t1 - t0) for (t0, a), (t1, b) in pieces if t1 > t0), default=0.0
            )
            out.append(
                Measure(
                    f"{joint_id}: top speed",
                    f"{peak:.2f} deg/s",
                    f"{top:.2f} deg/s (cited top speed {joint['top_speed_deg_s']:g})",
                )
            )
    for event in plan["events"]:
        if event["command"] != "Joint" or event["end_s"] <= event["start_s"]:
            continue
        targets = [
            v - p for v, p in zip(event["to_deg"], plan["pose_deg"], strict=True)
        ]  # the twin's angles
        ids = [j for j in plan["joint_ids"] if j in arrived]
        if not ids:
            break
        index = {j: i for i, j in enumerate(plan["joint_ids"])}
        at = next(
            (
                t
                for k, t in enumerate(times)
                if t >= event["start_s"]
                and all(abs(arrived[j][k] - targets[index[j]]) <= ARRIVE_DEG for j in ids)
            ),
            None,
        )
        out.append(
            Measure(
                f"move Nr {event['nr']}: all joints within {ARRIVE_DEG:g} deg of its target",
                _s(at),
                _s(event["end_s"]),
            )
        )
    return out


def compare_mill(
    recording: Mapping[str, Sequence[float]], plan: Mapping[str, Any]
) -> list[Measure]:
    """A Haas program on a mill (decision 0035), by the tool tip: the tip's machine position is
    each axis's ``sign x (joint - home)``, the tool's length being fixed. Measured: its distance
    from the plan at the same time and from the programmed path, over the whole program and
    while cutting; when each block's move arrived within ``ARRIVE_MM``; each axis's top speed;
    where it ended; the spindle's speed while cutting."""
    times = list(recording["time_s"])
    axes = plan["axes"]
    end = plan["duration_s"]
    columns: dict[str, list[float]] = {}
    for a in axes:
        column = _column(recording, f"{a['joint_id']} (m)")
        if column is None:
            return [Measure(a["joint_id"], "not recorded", "a column '<joint> (m)'")]
        columns[a["joint_id"]] = column
    tip = [
        [a["sign"] * (columns[a["joint_id"]][k] - a["home_m"]) * 1000 for a in axes]
        for k in range(len(times))
    ]
    plan_t = list(plan["times"])
    planned = [list(p) for p in plan["machine_mm"]]
    cutting = [(c[0], c[1]) for c in plan["cutting"]]

    def cuts(t: float) -> bool:
        return any(a <= t <= b for a, b in cutting)

    out: list[Measure] = []
    during = [k for k, t in enumerate(times) if t <= end]
    for label, ks in (
        ("whole program", during),
        ("cutting (feeds and arcs)", [k for k in during if cuts(times[k])]),
    ):
        if not ks:
            continue
        for what, gap in (
            (
                "from the plan at the same time",
                lambda k: _distance(tip[k], _at_point(plan_t, planned, times[k])),
            ),
            ("from the programmed path", lambda k: _off_path(tip[k], times[k], plan_t, planned)),
        ):
            gaps = sorted((gap(k), times[k]) for k in ks)
            out.append(
                Measure(
                    f"tip's distance {what}, {label}",
                    f"largest {gaps[-1][0]:.3f} mm (at {gaps[-1][1]:.2f} s), 95% within "
                    f"{_percentile([g for g, _ in gaps], 0.95):.3f} mm",
                    "0",
                )
            )
    last_arrival: float | None = None
    for event in plan["events"]:
        if event["end_s"] <= event["start_s"] or event["from_mm"] == event["to_mm"]:
            continue
        last_arrival = next(
            (
                t
                for k, t in enumerate(times)
                if t >= event["start_s"] and _distance(tip[k], event["to_mm"]) <= ARRIVE_MM
            ),
            None,
        )
        out.append(
            Measure(
                f"line {event['line'] or '-'} {event['kind']}: tip within {ARRIVE_MM:g} mm "
                "of its end",
                _s(last_arrival),
                _s(event["end_s"]),
            )
        )
    out.append(Measure("the program's last move arrived", _s(last_arrival), _s(end)))
    for i, a in enumerate(axes):
        peak = _top_speed(times, columns[a["joint_id"]], end)
        top = max(
            (
                abs(c[i] - b[i]) / (t1 - t0)
                for (t0, b), (t1, c) in itertools.pairwise(zip(plan_t, planned, strict=True))
                if t1 > t0
            ),
            default=0.0,
        )
        out.append(
            Measure(
                f"{a['axis']} ({a['joint_id']}): top speed, from positions",
                f"{peak * 1000:.1f} mm/s",
                f"{top:.1f} mm/s (cited rapid {a['rapid_m_s'] * 1000:.1f})",
            )
        )
    after = [tip[k] for k, t in enumerate(times) if t >= end]
    out.append(
        Measure(
            "where the tip ended (machine X, Y, Z)",
            "not recorded (the recording stops before the plan ends)"
            if not after
            else ", ".join(f"{statistics.median(v[i] for v in after):.3f}" for i in range(3))
            + " mm",
            ", ".join(f"{v:.3f}" for v in planned[-1]) + " mm",
        )
    )
    spindle = plan.get("spindle")
    w = None if spindle is None else _column(recording, f"{spindle} (rad/s)")
    changes = [(r[0], r[1]) for r in plan.get("spindle_rpm", [])]
    if w is not None and changes and cutting:
        rpm = [abs(v) * 60 / (2 * math.pi) for t, v in zip(times, w, strict=True) if cuts(t)]
        if rpm:
            out.append(
                Measure(
                    "spindle's speed while cutting, median",
                    f"{statistics.median(rpm):.1f} RPM",
                    f"{_rpm_at(changes, cutting[0][0]):g} RPM",
                )
            )
    return out


def _distance(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)))


def _at_point(times: list[float], points: list[list[float]], t: float) -> list[float]:
    """The planned point at ``t``, in a straight line between the plan's points."""
    if t <= times[0]:
        return list(points[0])
    if t >= times[-1]:
        return list(points[-1])
    i = bisect_left(times, t)
    t0, t1 = times[i - 1], times[i]
    f = 1.0 if t1 <= t0 else (t - t0) / (t1 - t0)
    return [a + (b - a) * f for a, b in zip(points[i - 1], points[i], strict=True)]


def _off_path(p: Sequence[float], t: float, times: list[float], points: list[list[float]]) -> float:
    """How far ``p`` is from the planned path's segments within ``PATH_WINDOW_S`` of ``t``: off
    the path, whether early or late along it."""
    lo = max(bisect_left(times, t - PATH_WINDOW_S) - 1, 0)
    hi = min(bisect_left(times, t + PATH_WINDOW_S) + 1, len(times) - 1)
    if hi <= lo:
        return _distance(p, points[lo])
    return min(_to_segment(p, points[i], points[i + 1]) for i in range(lo, hi))


def _to_segment(p: Sequence[float], a: Sequence[float], b: Sequence[float]) -> float:
    ab = [y - x for x, y in zip(a, b, strict=True)]
    length2 = sum(v * v for v in ab)
    if length2 == 0:
        return _distance(p, a)
    f = sum((pi - ai) * v for pi, ai, v in zip(p, a, ab, strict=True)) / length2
    f = min(max(f, 0.0), 1.0)
    return _distance(p, [ai + f * v for ai, v in zip(a, ab, strict=True)])


def _top_speed(times: list[float], q: list[float], end: float) -> float:
    """The fastest a joint moved over at least ``SPEED_SPAN_S``, from its positions, until a
    second after the plan's end."""
    peak = 0.0
    j = 0
    for k, t in enumerate(times):
        if t > end + 1.0:
            break
        while j + 1 < k and t - times[j + 1] >= SPEED_SPAN_S:
            j += 1
        if t - times[j] >= SPEED_SPAN_S:
            peak = max(peak, abs(q[k] - q[j]) / (t - times[j]))
    return peak


def _percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    return ordered[max(min(math.ceil(share * len(ordered)) - 1, len(ordered) - 1), 0)]


def _rpm_at(changes: list[tuple[float, float]], t: float) -> float:
    rpm = 0.0
    for when, value in changes:
        if when <= t + 1e-9:
            rpm = value
    return rpm


# ---------------------------------------------------------------------------------- helpers
def _column(recording: Mapping[str, Sequence[float]], name: str) -> list[float] | None:
    values = recording.get(name)
    return None if values is None else list(values)


def _first(times: list[float], values: list[float], test: Any) -> float | None:
    return next((t for t, v in zip(times, values, strict=True) if test(v)), None)


def _settled(after: list[tuple[float, float]], rest: float) -> float | None:
    """The time after which the quill stays within 1 mm of home."""
    last_out = None
    for t, v in after:
        if abs(v - rest) > HOME_TOLERANCE_M:
            last_out = t
    if not after or (last_out is not None and last_out >= after[-1][0]):
        return None
    return after[0][0] if last_out is None else next(t for t, _ in after if t > last_out)


def _bounces(after: list[tuple[float, float]], rest: float) -> list[float]:
    """The peaks of the quill's excursions back down after it first came home."""
    home = next((i for i, (_, v) in enumerate(after) if v <= rest + HOME_TOLERANCE_M), None)
    if home is None:
        return []
    peaks, peak = [], 0.0
    for _, v in after[home:]:
        depth = v - rest
        if depth > HOME_TOLERANCE_M:
            peak = max(peak, depth)
        elif peak:
            peaks.append(peak)
            peak = 0.0
    return peaks + ([peak] if peak else [])


def _slope(x: list[float], y: list[float]) -> float | None:
    """Least-squares slope of ``y`` against ``x``, over the samples where ``x`` moves."""
    pairs = [(a, b) for a, b in zip(x, y, strict=True) if a > HOME_TOLERANCE_M]
    if len(pairs) < 2:
        return None
    mx = statistics.fmean(a for a, _ in pairs)
    my = statistics.fmean(b for _, b in pairs)
    sxx = sum((a - mx) ** 2 for a, _ in pairs)
    return None if sxx == 0 else sum((a - mx) * (b - my) for a, b in pairs) / sxx


def _at(series: list[tuple[float, float]], t: float) -> float:
    i = bisect_left(series, (t, -math.inf))
    if i <= 0:
        return series[0][1]
    if i >= len(series):
        return series[-1][1]
    (t0, v0), (t1, v1) = series[i - 1], series[i]
    return v0 + (v1 - v0) * (t - t0) / (t1 - t0) if t1 > t0 else v1


def _minus(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else a - b


def _s(value: float | None) -> str:
    return "never" if value is None else f"{value:.2f} s"


def format_measures(measures: Sequence[Measure]) -> str:
    rows = [
        ("Measure", "Recorded", "Planned"),
        *((m.what, m.recorded, m.planned) for m in measures),
    ]
    widths = [max(len(r[i]) for r in rows) for i in range(3)]
    lines = ["  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)).rstrip() for r in rows]
    lines.insert(1, "  ".join("-" * w for w in widths))
    return "\n".join(lines)
