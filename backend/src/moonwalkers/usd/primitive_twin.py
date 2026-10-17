"""A box-and-cylinder test twin for checking the exporter in Isaac Sim (docs/poc-plan.md, Phase 2).

This is not the HA5C: the shapes and sizes are made up for the test, and the twin says so. The
spindle is an 8-sided cylinder, so its rotation is easy to see. Run from ``backend/`` with a run
folder (for example ``../data/machines/moonwalkers-testindexer/runs/2026-10-17_run-001``)::

    uv run python -m moonwalkers.usd.primitive_twin <run-folder>

That writes ``spin.usda`` (the spindle turns at 30 deg/s when you press Play),
``quarter_turn.usda`` (it turns to 90 deg and holds), validates both, and writes ``RUN.md`` for the
reviewer's notes.
"""

from __future__ import annotations

import argparse
import math
import platform
import sys
from collections.abc import Sequence
from datetime import datetime
from importlib.metadata import version as package_version
from pathlib import Path

from moonwalkers.clock import utc_now
from moonwalkers.contracts.pipeline_result import (
    Citation,
    InputType,
    Issue,
    Joint,
    MachineIdentity,
    Part,
    PipelineId,
    PipelineResult,
    Source,
    TwinRecord,
)
from moonwalkers.kb import machine_key

from .exporter import DriveSettings, export_twin
from .validate import validate_file

MANUFACTURER = "MoonWalkers"
MODEL = "Test Indexer"
SPIN_SPEED_RAD_S = math.radians(30.0)
QUARTER_TURN_RAD = math.radians(90.0)

DRIVES = {
    "spin.usda": DriveSettings.spin(SPIN_SPEED_RAD_S),
    "quarter_turn.usda": DriveSettings.hold(QUARTER_TURN_RAD),
}


def build_test_twin(created_at: datetime) -> tuple[TwinRecord, PipelineResult]:
    """The test twin and the one result it is built from. All sizes are synthetic."""
    source = Source(
        source_id="src-synthetic",
        kind="user_input",
        uri="user",
        title="Synthetic box-and-cylinder test model for the Phase 2 exporter check; "
        "sizes are made up, not the HA5C's",
        retrieved_at=created_at,
    )
    cite = [Citation(source_id=source.source_id)]
    result = PipelineResult(
        result_id="res-test-model-c",
        job_id="test-model",
        pipeline=PipelineId.C,  # hand-written geometry and kinematics, like a schematic reading
        input_types=[InputType.SCHEMATIC],
        produced_at=created_at,
        produced_by="moonwalkers.usd.primitive_twin (synthetic test model)",
        sources=[source],
        identity=MachineIdentity(
            manufacturer=MANUFACTURER,
            model=MODEL,
            category="test model",
            confidence=1.0,
            citations=cite,
        ),
        parts=[
            Part(
                part_id="body",
                name="Test body (box)",
                geometry_format="primitive",
                primitive={"shape": "box", "size_m": [0.20, 0.16, 0.16], "center_m": [0, 0, 0.08]},
                citations=cite,
            ),
            Part(
                part_id="spindle",
                name="Test spindle (8-sided cylinder)",
                geometry_format="primitive",
                primitive={
                    "shape": "cylinder",
                    "radius_m": 0.03,
                    "length_m": 0.06,
                    "axis": [1, 0, 0],
                    "center_m": [0.13, 0, 0.10],
                    "segments": 8,
                },
                citations=cite,
            ),
        ],
        joints=[
            Joint(
                joint_id="spindle_rotation",
                joint_type="revolute",
                parent_part="body",
                child_part="spindle",
                axis=(1.0, 0.0, 0.0),
                origin_m=(0.10, 0.0, 0.10),  # centre of the box's +x face, on the spindle axis
                confidence=1.0,
                citations=cite,
            )
        ],
        issues=[
            Issue(
                severity="info",
                message="Synthetic test model written by hand to check the USD exporter; "
                "not derived from a real schematic.",
            )
        ],
    )
    key = machine_key(MANUFACTURER, MODEL)
    twin = TwinRecord(
        twin_id=f"{key}@v1",
        machine_key=key,
        version=1,
        status="needs_review",
        built_from=[result.result_id],
        created_at=created_at,
    )
    return twin, result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write and validate the box-and-cylinder test twin."
    )
    parser.add_argument(
        "out_dir", type=Path, help="run folder, e.g. data/machines/<machine>/runs/<run>"
    )
    args = parser.parse_args(argv)

    created_at = utc_now()
    twin, result = build_test_twin(created_at)
    report: list[str] = []
    failed = False
    for name, drive in DRIVES.items():
        path = export_twin(twin, [result], args.out_dir / name, drive)
        issues = validate_file(path)
        errors = [i for i in issues if i.severity == "error"]
        failed = failed or bool(errors)
        status = f"{len(errors)} error(s), {len(issues) - len(errors)} other finding(s)"
        print(f"{path}: {status}")
        report.append(f"- `{name}`: {_describe(drive)}. Validation: {status}.")
        for issue in issues:
            print(f"  {issue.severity}: {issue.message} ({issue.ref or '-'})")
            report.append(f"  - {issue.severity}: {issue.message} ({issue.ref or '-'})")
    _write_run_notes(args.out_dir, created_at, report)
    return 1 if failed else 0


def _describe(drive: DriveSettings) -> str:
    if drive.mode == "velocity":
        return f"spindle turns at {math.degrees(drive.target):g} deg/s (velocity drive)"
    return f"spindle moves to {math.degrees(drive.target):g} deg and holds (position drive)"


def _write_run_notes(out_dir: Path, created_at: datetime, report: list[str]) -> None:
    versions = (
        f"moonwalkers {package_version('moonwalkers')}, usd-core {package_version('usd-core')}, "
        f"Python {platform.python_version()}"
    )
    lines = [
        "# Run: box-and-cylinder test twin (Phase 2 exporter check)",
        "",
        f"- Created (UTC): {created_at.isoformat(timespec='seconds')}",
        f"- Command: `uv run python -m moonwalkers.usd.primitive_twin {out_dir.as_posix()}`",
        f"- Versions: {versions}",
        "- Input: synthetic primitives (no photos, no generator); sizes are made up.",
        "",
        "## Files",
        *report,
        "",
        "## Isaac Sim check (fill in)",
        "- Isaac Sim version/build:",
        "- What was seen (per file):",
        "- Success level reached (1-3):",
        "- Reviewer notes:",
        "",
    ]
    (out_dir / "RUN.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sys.exit(main())
