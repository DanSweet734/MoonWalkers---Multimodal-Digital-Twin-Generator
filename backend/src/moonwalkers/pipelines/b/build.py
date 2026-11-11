"""Build, or reuse, the twin for one run folder through the orchestrator (decisions 0012, 0013).

The command line (``cli.py``) and the MCP server (``moonwalkers.mcp``) both use ``build_run``, so
a twin is built the same way whoever asks for it:

- Pipeline B runs on the run's request: it generates the mesh, or stops with
  ``GeometrySpecMissing`` until the spec exists, then assembles the parts.
- The orchestrator stores the result, or reuses a stored twin, following decision 0009.
- A new twin is exported first, as ``twin.usdc`` plus its check files (``check_files``), and
  validated. The run folder then gets copies of the stored records and ``RUN.md``; a twin of
  several parts also gets the coloured views and the photo overlays (``views/``) and the joint
  recorder (``record_joints.py``).
"""

from __future__ import annotations

import json
import math
import platform
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any, Literal

from moonwalkers.contracts.pipeline_result import (
    Citation,
    InputType,
    Issue,
    JobResult,
    Joint,
    JointMode,
    PipelineId,
    PipelineResult,
    Source,
    TwinRecord,
)
from moonwalkers.control.controls_export import CONTROLS_FILE, controls_files, write_controls_folder
from moonwalkers.control.export import write_program_folder
from moonwalkers.control.program import ProgramFile, runnable_behaviors
from moonwalkers.generators.base import ImageTo3DGenerator
from moonwalkers.kb import KnowledgeBase
from moonwalkers.orchestrator import JobRequest, Orchestrator
from moonwalkers.pipelines import Pipeline, default_pipelines
from moonwalkers.usd.exporter import (
    DriveSettings,
    ExportError,
    JointSettings,
    export_twin,
    stopped_limits,
)
from moonwalkers.usd.validate import validate_file

from .part_views import fit_fed_photos, write_spec_views
from .parts_spec import PartsSpec, oriented_mesh
from .pipeline import (
    GENERATOR_DIR,
    GENERATOR_RECORD,
    SPEC_FILE,
    SPEC_SOURCE_ID,
    PipelineB,
    ReferenceFacts,
    RunFolderConflict,
    generated_mesh,
    read_spec,
)

RECORDER = Path(__file__).parents[2] / "usd" / "isaac_recorder.py"

REQUEST_FILE = "request.json"
JOB_RESULT_SUFFIX = ".job_result.json"
TWIN_FILE = "twin.usdc"  # binary: a generated mesh is too big for text USD (decision 0012)
CHECKS_DIR = "checks"
PROGRAMS_DIR = "programs"  # one folder per control behaviour with a program (decision 0016)
VIEWS_DIR = "views"  # coloured views and photo overlays of a several-part twin (decision 0023)
RECORDER_FILE = "record_joints.py"  # the joint recorder for the Isaac Sim check (Phase 1)
SLOW_SPIN = math.radians(30.0)  # for the eye; chosen by us, not a machine fact
SETTING_TURN = math.radians(30.0)  # where a check locks a turning joint, within its limits
# A driven sliding joint's check runs it at its cited top speed, else at this one (chosen by us).
SLIDE_SPEED = 0.025  # m/s
# The slide check's velocity drive (an acceleration drive, like the exporter's): its speed error
# under gravity is g / damping, 1 mm/s here, where the spin check's damping of 20 would let a
# rising head fall (lab's machines plan, Phase 4). Chosen by us, not a machine fact.
SLIDE_DAMPING = 10_000.0


@dataclass(frozen=True)
class CheckFile:
    """One file for the Isaac Sim check: the twin with only this scenario added, as the Phase 1
    drill press's checks are (``usd.primitive_drill_press.Check``). ``machine`` changes the
    contract (a lock loosened, a stop moved); ``settings`` and ``starts`` are simulation choices.
    Every value here is chosen for the check, not a fact about the machine."""

    name: str
    shows: str
    look_for: str
    drive: DriveSettings | None = None  # None: the twin's own hold (``hold_drive``)
    machine: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    settings: Mapping[str, JointSettings] = field(default_factory=dict)
    starts: Mapping[str, float] = field(default_factory=dict)
    collide_unjoined: bool | None = None  # None: as the twin (decision 0032)

    def results(self, results: Sequence[PipelineResult]) -> list[PipelineResult]:
        """The results with this check's machine changes, validated again."""
        if not self.machine:
            return list(results)
        changed = []
        for result in results:
            data = result.model_dump()
            for joint in data["joints"]:
                joint.update(self.machine.get(joint["joint_id"], {}))
            changed.append(PipelineResult.model_validate(data))
        return changed


def check_files(results: Sequence[PipelineResult]) -> list[CheckFile]:
    """The check files for a twin. A twin whose joints state no v0.2.0 behaviour (the HA5C, the
    TH240) gets the PoC's two: a spin and a quarter turn of every joint. Otherwise there is a
    file per behaviour its joints state, as the Phase 1 drill press had (decision 0020)."""
    joints = [j for r in results for j in r.joints]
    if not any(j.mode or j.follows or j.adjustable_stop for j in joints):
        return [
            CheckFile(
                "spin.usdc", "the spindle turns at 30 deg/s", "", DriveSettings.spin(SLOW_SPIN)
            ),
            CheckFile(
                "quarter_turn.usdc",
                "the spindle turns to 90 deg and holds",
                "",
                DriveSettings.hold(math.radians(90.0)),
            ),
        ]
    # A value chosen for a check cites the geometry spec, when the joint's result has one.
    with_spec = {
        j.joint_id
        for r in results
        if SPEC_SOURCE_ID in {source.source_id for source in r.sources}
        for j in r.joints
    }

    def chosen(joint: Joint) -> list[Citation]:
        if joint.joint_id not in with_spec:
            return []
        return [
            Citation(source_id=SPEC_SOURCE_ID, locator="set for the Isaac Sim check, not a fact")
        ]

    def kind(j: Joint, name: str) -> bool:
        return j.mode is not None and j.mode.kind == name

    driven = [j for j in joints if kind(j, "driven") and j.joint_type == "revolute"]
    sliding = [
        j
        for j in joints
        if kind(j, "driven") and j.joint_type == "prismatic" and None not in stopped_limits(j)
    ]
    springs = [j for j in joints if kind(j, "spring_return")]
    stops = [j for j in joints if j.adjustable_stop is not None and j.lower_limit is not None]
    locked = [j for j in joints if kind(j, "locked")]
    followers = ", ".join(f"'{j.joint_id}'" for j in joints if j.follows) or "nothing"
    spin = {j.joint_id: JointSettings(drive=DriveSettings.spin(SLOW_SPIN)) for j in driven}
    far = {j.joint_id: _far_end(j) for j in springs}
    settings = {j.joint_id: _lock_setting(j) for j in locked}
    at_setting = {
        j.joint_id: {
            "mode": JointMode(
                kind="locked",
                position=settings[j.joint_id],
                citations=[*j.mode.citations, *chosen(j)],
            )
        }
        for j in locked
        if j.mode is not None
    }
    checks = []
    if driven:
        checks.append(
            CheckFile(
                "spin.usdc",
                f"the driven joints ({_names(driven)}) turn at 30 deg/s, for the eye",
                "They turn slowly and steadily; nothing else moves.",
                settings=spin,
            )
        )
    if sliding:
        checks.append(
            CheckFile(
                "slide.usdc",
                f"the driven sliding joints ({_names(sliding)}) run their whole travel",
                "On Play "
                + "; ".join(
                    f"'{j.joint_id}' starts at {_amount(j, stopped_limits(j)[0])} and slides to "
                    f"{_amount(j, stopped_limits(j)[1])} at {_slide_speed(j) * 1000:.1f} mm/s"
                    for j in sliding
                )
                + ". Each stops at its upper limit and stays there; nothing else moves.",
                settings={
                    j.joint_id: JointSettings(
                        drive=DriveSettings(
                            mode="velocity",
                            target=_slide_speed(j),
                            stiffness=0.0,
                            damping=SLIDE_DAMPING,
                        ),
                        note="a run through the whole travel, for the check",
                    )
                    for j in sliding
                },
                starts={j.joint_id: stopped_limits(j)[0] for j in sliding},
            )
        )
    if springs:
        checks.append(
            CheckFile(
                "spring_return.usdc",
                f"the spring-return joints ({_names(springs)}) start at the far end of travel",
                "On Play "
                + "; ".join(
                    f"'{j.joint_id}' jumps to {_amount(j, far[j.joint_id])}" for j in springs
                )
                + f"; then the spring returns it to its rest position. Following: {followers}.",
                starts=far,
            )
        )
    for j in stops:
        middle = (j.lower_limit + _far_end(j)) / 2
        stop = j.adjustable_stop
        assert stop is not None
        checks.append(
            CheckFile(
                "adjustable_stop.usdc",
                f"'{j.joint_id}' is fed past its adjustable stop, set half way",
                f"On Play '{j.joint_id}' moves to {_amount(j, middle)} and stops there, short of "
                f"its full {_amount(j, _far_end(j))}.",
                machine={
                    j.joint_id: {
                        "adjustable_stop": stop.model_copy(
                            update={"position": middle, "citations": [*stop.citations, *chosen(j)]}
                        )
                    }
                },
                settings={
                    j.joint_id: JointSettings(
                        drive=DriveSettings.hold(_far_end(j)), note="a feed past the stop"
                    )
                },
            )
        )
        break  # one stop file; a machine with several gets one check of the first
    if locked:
        checks += [
            CheckFile(
                "unlocked.usdc",
                f"the locked joints ({_names(locked)}) loosened",
                "On Play gravity moves what a loosened lock no longer holds: a slide up a column "
                "drops to its lowest point (decision 0018), and a part whose weight sits off a "
                "loosened turning axis swings to its limit. Then Shift+drag each loosened part: "
                "it moves freely within its limits.",
                machine={
                    j.joint_id: {"mode": JointMode(kind="free", citations=j.mode.citations)}
                    for j in locked
                    if j.mode is not None
                },
            ),
            CheckFile(
                "locked_at_setting.usdc",
                f"the locked joints ({_names(locked)}) set away from the modelled pose",
                "On Play "
                + "; ".join(
                    f"'{j.joint_id}' is at {_amount(j, settings[j.joint_id])}" for j in locked
                )
                + ". Each holds there under gravity and a Shift+drag.",
                machine=at_setting,
            ),
        ]
    checks.append(
        CheckFile(
            "all_motions.usdc",
            "everything at once",
            "The driven joints turn slowly, the springs return their joints with the followers "
            "following, and the locked joints hold at their settings.",
            machine=at_setting,
            settings=spin,
            starts=far,
        )
    )
    return checks


def _far_end(joint: Joint) -> float:
    """The end of a joint's travel farthest from its rest position, its adjustable stop
    included."""
    lower, upper = stopped_limits(joint)
    rest = joint.mode.position if joint.mode and joint.mode.position is not None else 0.0
    ends = [e for e in (lower, upper) if e is not None]
    if not ends:
        raise ExportError(f"joint '{joint.joint_id}' has no limits to start a check from")
    return max(ends, key=lambda e: abs(e - rest))


def _slide_speed(joint: Joint) -> float:
    """A sliding joint's speed in the slide check: its cited top speed, else ``SLIDE_SPEED``."""
    return joint.max_velocity if joint.max_velocity else SLIDE_SPEED


def _lock_setting(joint: Joint) -> float:
    """Where a check locks a joint: 30 deg on a turning joint, half way to its upper limit on a
    sliding one, kept within its limits."""
    lower, upper = stopped_limits(joint)
    if joint.joint_type == "prismatic":
        target = (upper or 0.0) / 2 if (upper or 0.0) > 0 else (lower or 0.0) / 2
    else:
        target = SETTING_TURN
    if upper is not None:
        target = min(target, upper)
    if lower is not None:
        target = max(target, lower)
    return target


def _amount(joint: Joint, value: float) -> str:
    if joint.joint_type == "prismatic":
        return f"{value:+.4f} m ({value / 0.0254:+.2f} in)"
    return f"{math.degrees(value):+.1f} deg"


def _names(joints: Sequence[Joint]) -> str:
    return ", ".join(f"'{j.joint_id}'" for j in joints)


@dataclass(frozen=True)
class BuildOutcome:
    job: JobResult
    validation: list[Issue] = field(default_factory=list)  # findings on the exported twin
    twin_file: Path | None = None  # None when the stored twin was reused
    check_files: list[Path] = field(default_factory=list)


def build_run(
    run_dir: Path,
    data_dir: Path,
    request_path: Path,
    reference: ReferenceFacts | None,
    reference_path: Path | None,
    generator: ImageTo3DGenerator,
    kb: KnowledgeBase,
    pipelines: Mapping[PipelineId, Pipeline] | None = None,
) -> BuildOutcome:
    """Send the run's request through the orchestrator with Pipeline B, and with the other
    pipelines that are in (``default_pipelines()`` unless ``pipelines`` is given; decision 0021).

    Raises what the pipeline and the orchestrator raise, for example ``GeometrySpecMissing``
    before the spec exists, or ``RunFolderConflict`` when the run folder already holds a twin.
    """
    run_dir, data_dir = Path(run_dir).resolve(), Path(data_dir).resolve()
    request = JobRequest.model_validate_json(Path(request_path).read_text(encoding="utf-8"))
    pipeline_b = PipelineB(generator, data_dir, run_dir, reference, photos=request.photos)
    findings: list[Issue] = []
    exported: list[Path] = []

    def export(twin: TwinRecord, results: Sequence[PipelineResult]) -> str:
        path = run_dir / TWIN_FILE
        earlier = sorted(p.name for p in run_dir.glob("twin.usd*"))
        if earlier:
            raise RunFolderConflict(
                f"{run_dir} already holds an exported twin ({', '.join(earlier)}); "
                "build a new version in a new run folder"
            )
        programs = program_files(results)  # a program that cannot run fails before any file
        controls = controls_files(results)  # so do controls whose specs cannot be read
        hold = hold_drive(run_dir)
        collide = self_collision(run_dir) == "on"
        export_twin(twin, results, path, hold, data_dir, collide_unjoined=collide)
        written = [path]
        try:
            findings.extend(validate_file(path))
            errors = [i for i in findings if i.severity == "error"]
            if errors:
                raise ExportError(f"the exported twin failed validation: {errors[0].message}")
            for check in run_checks(run_dir, results):
                path_ = run_dir / CHECKS_DIR / check.name
                written.append(path_)
                export_twin(
                    twin,
                    check.results(results),
                    path_,
                    check.drive or hold,
                    data_dir,
                    joint_settings=check.settings,
                    starts=check.starts,
                    collide_unjoined=(
                        collide if check.collide_unjoined is None else check.collide_unjoined
                    ),
                )
                failed = [i for i in validate_file(path_) if i.severity == "error"]
                if failed:
                    raise ExportError(f"{check.name} failed validation: {failed[0].message}")
            for program in programs:  # level 3: the program drives the joint (decision 0016)
                folder = run_dir / PROGRAMS_DIR / program.name
                written.append(folder)
                write_program_folder(  # holding and colliding as the twin does (0032, 0033)
                    folder, program, twin, results, data_dir, hold=hold, collide_unjoined=collide
                )
            for control in controls:  # level 3 for a manual machine (decision 0025)
                folder = run_dir / PROGRAMS_DIR / control.name
                written.append(folder)
                write_controls_folder(folder, control, twin, results, data_dir, hold, collide)
        except BaseException:  # nothing is stored, so leave no files that claim otherwise
            for item in written:
                shutil.rmtree(item) if item.is_dir() else item.unlink(missing_ok=True)
            raise
        exported.extend(p for p in written if p.is_file())
        return path.relative_to(data_dir).as_posix()

    others = default_pipelines() if pipelines is None else pipelines
    job = Orchestrator(kb, {**others, PipelineId.B: pipeline_b}, exporter=export).run_job(request)
    write_job_result(run_dir, Path(request_path), job)
    if job.reused_existing:
        return BuildOutcome(job)
    views = write_views(run_dir)
    _write_run_files(
        run_dir, kb, job, request, Path(request_path), reference_path, reference, findings, views
    )
    return BuildOutcome(job, findings, exported[0], exported[1:])


def write_views(run_dir: Path) -> dict[str, Path]:
    """For a several-part spec: the reviewer's views in ``views/`` (decision 0023), with each
    fed photo placed on the mesh (about a minute a photo), and the joint recorder. Nothing for
    decision 0012's single spindle."""
    spec = read_spec(Path(run_dir) / SPEC_FILE)
    if not isinstance(spec, PartsSpec):
        return {}
    model_record = json.loads((Path(run_dir) / "meshes" / "assembly.json").read_text("utf-8"))
    mesh = oriented_mesh(generated_mesh(run_dir), spec)
    photos = fit_fed_photos(mesh, Path(run_dir) / GENERATOR_DIR / "prepared", spec.yaw_deg)
    scale = float(model_record["scale_factor_m_per_unit"])
    views = write_spec_views(mesh, spec, scale, Path(run_dir) / VIEWS_DIR, photos)
    shutil.copyfile(RECORDER, Path(run_dir) / RECORDER_FILE)
    return views


def self_collision(run_dir: Path) -> Literal["off", "check", "on"]:
    """Whether parts that no joint joins collide: a several-part spec's ``self_collision``
    (decision 0032), else "off" (decision 0017)."""
    spec = read_spec(Path(run_dir) / SPEC_FILE)
    return spec.self_collision if isinstance(spec, PartsSpec) else "off"


def run_checks(run_dir: Path, results: Sequence[PipelineResult]) -> list[CheckFile]:
    """The run's check files: ``check_files``, and with ``self_collision`` "check" one more
    where the parts no joint joins collide while the driven joints turn (decision 0032)."""
    checks = check_files(results)
    if self_collision(run_dir) != "check":
        return checks
    spin = next((c for c in checks if c.name == "spin.usdc"), None)
    checks.append(
        CheckFile(
            "self_collision.usdc",
            "the parts that no joint joins collide with each other"
            + (", while the driven joints turn at 30 deg/s" if spin else ""),
            "On Play nothing jumps or flies apart (no two parts' convex hulls overlap in the "
            "modelled pose); as the joints turn, parts stop where they meet instead of passing "
            "through each other.",
            settings=spin.settings if spin else {},
            collide_unjoined=True,
        )
    )
    return checks


def hold_drive(run_dir: Path) -> DriveSettings:
    """How the twin's driven joints hold a position: the spec's ``hold_drive`` when a
    several-part spec gives one (decision 0032), else the exporter's default drive."""
    spec = read_spec(Path(run_dir) / SPEC_FILE)
    if isinstance(spec, PartsSpec) and spec.hold_drive is not None:
        return DriveSettings(
            mode="position",
            target=0.0,
            stiffness=spec.hold_drive.stiffness,
            damping=spec.hold_drive.damping,
        )
    return DriveSettings.hold(0.0)


def program_files(results: Sequence[PipelineResult]) -> list[ProgramFile]:
    """A program file for each control behaviour that carries a program to run, with the
    sources its citations name (decision 0016)."""
    programs = []
    for result in results:
        for behavior in runnable_behaviors(result.control):
            cited = {c.source_id for c in behavior.citations}
            programs.append(
                ProgramFile(
                    name=behavior.behavior_id.lower().replace("_", "-"),
                    sources=[s for s in result.sources if s.source_id in cited],
                    behavior=behavior,
                )
            )
    return programs


def job_result_file(request_path: Path) -> str:
    """The file name for what a request returned: ``request.json`` gives
    ``request.job_result.json``, written next to it in the run folder."""
    return f"{Path(request_path).stem}{JOB_RESULT_SUFFIX}"


def write_job_result(run_dir: Path, request_path: Path, job: JobResult) -> Path:
    path = Path(run_dir) / job_result_file(request_path)
    _write_json(path, job.model_dump(mode="json"))
    return path


def _write_run_files(
    run_dir: Path,
    kb: KnowledgeBase,
    job: JobResult,
    request: JobRequest,
    request_path: Path,
    reference_path: Path | None,
    reference: ReferenceFacts | None,
    findings: list[Issue],
    views: Mapping[str, Path],
) -> None:
    """Copies of the stored records, and ``RUN.md`` for the run's details and the review."""
    results = [kb.get_result(rid) for rid in job.twin.built_from]
    stored = [r for r in results if r is not None]
    _write_json(run_dir / "twin_record.json", job.twin.model_dump(mode="json"))
    for result in stored:
        name = f"pipeline_result_{result.pipeline.value.lower()}.json"
        _write_json(run_dir / name, result.model_dump(mode="json"))
    record_path = run_dir / GENERATOR_DIR / GENERATOR_RECORD
    generator = json.loads(record_path.read_text(encoding="utf-8"))
    lines = _run_notes(
        job, stored, generator, request, request_path, reference_path, reference, findings, views,
        checks=run_checks(run_dir, stored),
    )  # fmt: skip
    (run_dir / "RUN.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _run_notes(
    job: JobResult,
    results: list[PipelineResult],
    generator: dict[str, Any],
    request: JobRequest,
    request_path: Path,
    reference_path: Path | None,
    reference: ReferenceFacts | None,
    findings: list[Issue],
    views: Mapping[str, Path] | None = None,
    checks: Sequence[CheckFile] | None = None,
) -> list[str]:
    twin = job.twin
    details = generator["details"]
    versions = details.get("versions", {})
    backend = ", ".join(
        f"{name} {package_version(name)}"
        for name in ("moonwalkers", "usd-core", "trimesh", "numpy", "pydantic")
    )
    facts = (
        f"`{reference_path.as_posix()}` ({len(reference.facts)} facts)"
        if reference is not None and reference_path is not None
        else "none"
    )
    photos = [s for s in request.sources if s.input_type == InputType.MACHINE_PHOTO]
    count = "one photo" if len(photos) == 1 else f"{len(photos)} photos"
    lines = [
        f"# Run: {twin.twin_id} (Pipeline B, {count})",
        "",
        f"- Twin: {twin.twin_id}, status {twin.status}, USD `{twin.usd_path}`",
        f"- Created (UTC): {twin.created_at.isoformat(timespec='seconds')}",
        f"- Request: `{request_path.name}`, job `{job.job_id}`",
        f"- Reference facts: {facts}",
        f"- Backend: {backend}, Python {platform.python_version()}",
        f"- Generator: {generator['generator']['name']} {generator['generator'].get('version')}"
        f" on {details.get('device')}, Python {details.get('python')}; "
        + ", ".join(f"{k} {v}" for k, v in versions.items()),
        f"- Generator settings: {_settings(generator['generator']['params'])}",
        (
            f"- Generation: {generator['seconds']:.1f} s "
            f"({_timings(details.get('timings_s', {}))}); "
            f"peak VRAM {details.get('peak_vram_allocated_gb')} GB allocated, "
            f"{details.get('peak_vram_reserved_gb')} GB reserved"
        ),
    ]
    for result in results:
        if result.scale is not None and result.scale.scale_factor is not None:
            lines.append(
                f"- Scale: {result.scale.scale_factor:.6f} m per model unit "
                f"({result.scale.reference} {result.scale.known_value_m} m = "
                f"{result.scale.measured_model_units:.4f} model units)"
            )
        for part in result.parts:
            lines.append(
                f"- Part `{part.part_id}`: `{part.geometry_file}`, bounds (m) "
                f"{_triple(part.bbox_min_m)} to {_triple(part.bbox_max_m)}"
            )
        for joint in result.joints:
            lines.append(
                f"- Joint `{joint.joint_id}`: {joint.joint_type} about {list(joint.axis)} at "
                f"{list(joint.origin_m)} m, {joint.parent_part} -> {joint.child_part}"
            )
        lines += ["", f"## Issues in the Pipeline {result.pipeline.value} result", ""]
        lines += [f"- {i.severity}: {i.message}" for i in result.issues]
    lines += _photo_table(generator.get("photos"), photos)
    lines += ["", "## Validation (moonwalkers.usd.validate)", ""]
    lines += [f"- {i.severity}: {i.message} ({i.ref or '-'})" for i in findings] or [
        "- no findings"
    ]
    programs = program_files(results)
    controls = controls_files(results)
    if programs or controls:
        lines += ["", "## Programs and controls (decisions 0016, 0025)", ""]
        lines += [
            f"- `{PROGRAMS_DIR}/{p.name}/`: {p.behavior.name}; see its PROGRAM.md" for p in programs
        ]
        lines += [
            f"- `{PROGRAMS_DIR}/{c.name}/`: "
            + ", ".join(b.name for b in c.behaviors)
            + "; see its PROGRAM.md"
            for c in controls
        ]
    warnings = [i for r in results for i in r.issues if i.severity == "warning"]
    if views:
        lines += ["", "## Stand-ins and known inaccuracies (the warnings above)", ""]
        lines += [f"- `{i.ref or '-'}`: {i.message}" for i in warnings]
        lines += ["", f"## Views (`{VIEWS_DIR}/`, decision 0023)", ""]
        lines += [f"- `{VIEWS_DIR}/{path.name}`" for path in views.values()]
    checks = check_files(results) if checks is None else checks
    lines += ["", "## Isaac Sim check (fill in)", "", "- Isaac Sim version/build:"]
    if checks and all(not c.look_for for c in checks):  # the PoC's single spindle
        lines += [
            f"- `{TWIN_FILE}` (spindle holds 0 deg):",
            "- `checks/spin.usdc` (spindle turns at 30 deg/s):",
            "- `checks/quarter_turn.usdc` (spindle turns to 90 deg and holds):",
        ]
    else:
        lines += [
            (
                f"- Measuring: before Play, paste `{RECORDER_FILE}` into Window > Script Editor "
                "and click Run; it writes every joint's position over time to `recordings/`."
            ),
            "- Pushing parts: hold Shift and drag with the left mouse button while it runs.",
            (
                f"- `{TWIN_FILE}` (the twin as the contract states it: driven joints hold, "
                "springs rest, followers follow, locks hold the modelled pose):"
            ),
        ]
        for check in checks:
            lines += [f"- `{CHECKS_DIR}/{check.name}`: {check.shows}. Look for: {check.look_for}"]
            lines.append("  - Seen:")
    lines += [
        *(
            f"- `{PROGRAMS_DIR}/{p.name}/program.usdc` with run_program.py (the program "
            "drives the spindle):"
            for p in programs
        ),
        *(
            f"- `{PROGRAMS_DIR}/{c.name}/{CONTROLS_FILE}` with run_controls.py (scenarios and live "
            "controls in the Property panel; level 3):"
            for c in controls
        ),
        "- Success level reached (1-3):",
        "- Reviewer notes:",
    ]
    return lines


def _photo_table(record: dict[str, Any] | None, photos: Sequence[Source]) -> list[str]:
    """The run's photos with their views, uses and generator slots (decision 0022), from the
    generator record; runs generated before the record kept them have no table."""
    if record is None:
        return []
    files = {s.source_id: s.uri for s in photos}
    expected = record.get("expected_turn_deg")
    lines = [
        "",
        "## Photos (decision 0022)",
        "",
        f"- Grid: {record['grid']}"
        + ("" if expected is None else f"; the machine's front is expected at {expected:+g} deg"),
        "",
        "| Source | File | View | Use | Generator slot |",
        "|---|---|---|---|---|",
    ]
    rows = [(f["source_id"], f["view"] or "none", "generator", f["slot"]) for f in record["fed"]]
    rows += [(e["source_id"], e["view"], "evidence", "-") for e in record["evidence"]]
    for source, view, use, slot in rows:
        lines.append(f"| {source} | `{files.get(source, '?')}` | {view} | {use} | {slot} |")
    return lines


def _settings(params: dict[str, Any]) -> str:
    return ", ".join(f"{k} {v}" for k, v in params.items() if k != "versions")


def _timings(timings: dict[str, float]) -> str:
    return ", ".join(f"{k} {v:.1f} s" for k, v in timings.items())


def _triple(values: Sequence[float] | None) -> str:
    return "-" if values is None else "(" + ", ".join(f"{v:+.4f}" for v in values) + ")"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
