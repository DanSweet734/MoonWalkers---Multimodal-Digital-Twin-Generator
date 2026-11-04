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
"""

from __future__ import annotations

import csv
import math
import statistics
from bisect import bisect_left
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HOME_TOLERANCE_M = 0.001  # within 1 mm of the rest position counts as home
STOP_TOLERANCE_M = 0.0005  # within 0.5 mm of the stop counts as at the stop


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
    """The measures of ``recording`` against ``plan`` (a trajectory JSON, loaded)."""
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
