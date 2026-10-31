"""The MoonWalkers MCP server: the platform's actions as tools for an agent (decision 0013).

Claude Code starts it through the project's ``.mcp.json`` and talks to it over stdio. By hand,
from ``backend/``::

    uv run python -m moonwalkers.mcp [--data ../data]

Every tool is a thin wrapper over the platform's own code. It goes through the orchestrator, the
knowledge base and Pipeline B with the same rules as the command line, and keeps its state in the
run folder (``workspace.py``). Expected failures come back to the agent as tool errors with a
readable message. The agent's procedure is in ``docs/agent-procedure.md``.
"""

import argparse
import os
import threading
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import ValidationError

from moonwalkers.clock import Clock, utc_now
from moonwalkers.contracts.pipeline_result import (
    Citation,
    ControlBehavior,
    Fact,
    InputType,
    Issue,
    MachineIdentity,
    PipelineId,
    Source,
    TwinRecord,
)
from moonwalkers.control.manual import check_behavior
from moonwalkers.control.program import IndexProgram, runnable_behaviors
from moonwalkers.generators.base import (
    GeneratorError,
    GeneratorRequest,
    GeneratorRun,
    ImageTo3DGenerator,
)
from moonwalkers.generators.hunyuan3d import (
    GEN_ROOT_ENV,
    Hunyuan3DConfig,
    Hunyuan3DGenerator,
)
from moonwalkers.kb import (
    JsonKnowledgeBase,
    KnowledgeBase,
    KnowledgeBaseError,
    machine_key,
    validate_machine_key,
)
from moonwalkers.orchestrator import (
    InputPhoto,
    JobRequest,
    MachineHint,
    NoInputsError,
    Orchestrator,
    OrchestratorError,
    PhotoUse,
    PhotoView,
)
from moonwalkers.orchestrator.router import ROUTES
from moonwalkers.pipelines import OWNERS, Pipeline, default_pipelines
from moonwalkers.pipelines.b.assemble import AxisName
from moonwalkers.pipelines.b.build import REQUEST_FILE, build_run
from moonwalkers.pipelines.b.inspection import inspect_mesh, preview_parts, preview_parts_spec
from moonwalkers.pipelines.b.mesh_tools import (
    CircleFit,
    fit_circles_along,
    load_mesh,
    orientation_matrix,
    render_views,
    transformed,
)
from moonwalkers.pipelines.b.part_cuts import PartCut
from moonwalkers.pipelines.b.parts_spec import (
    EXTENT_FACTS,
    PartsSpec,
    SizeCheck,
    SpecJoint,
    SpecPart,
)
from moonwalkers.pipelines.b.photos import PhotoPlan, check_photos
from moonwalkers.pipelines.b.pipeline import (
    GENERATOR_DIR,
    GENERATOR_RECORD,
    INSPECT_DIR,
    PARTS_PREVIEW_DIR,
    SCALE_FACT,
    GeometrySpecMissing,
    PipelineB,
    ReferenceFacts,
    RunFolderConflict,
    generated_mesh,
    size_checks,
)
from moonwalkers.usd.exporter import ExportError
from moonwalkers.workspace import (
    OPEN_STAGES,
    REFERENCE_FILE,
    RunStatus,
    Workspace,
    WorkspaceError,
    default_data_dir,
    list_runs,
    sha256_of,
)

from .reports import (
    CircleAlongReport,
    CircleFitReport,
    CirclesReport,
    GenerationReport,
    HoleReport,
    InspectionReport,
    JobBrief,
    JobList,
    JointPreview,
    KnowledgeBaseReport,
    PartPreview,
    PartsPreviewReport,
    PreviewReport,
    ProfileSliceReport,
    ReferenceSummary,
    RequestOutcome,
    RunInfo,
    SourceAdded,
    SpecStatus,
    SubmitReport,
    TipSlabReport,
    TwinSummary,
)

SERVER_NAME = "moonwalkers"
INSTRUCTIONS = """\
MoonWalkers platform: build a functional digital twin of a machine from its photos, with every
fact cited. Follow docs/agent-procedure.md. The usual order is:
- check_knowledge_base; then request_twin if a twin exists and no rebuild was asked for;
- start_run, then add_input for each machine photo, with its view in the operator's words when
  there are several (decision 0022). Photos uploaded in the dashboard are already a job:
  list_jobs finds it, and you continue it from add_reference_source;
- add_reference_source, identify_machine, add_fact and add_control (cited reading notes);
- generate_geometry, then inspect_geometry (open the PNG views it returns);
- one moving part about +x (decision 0012): add_joint and set_scale;
- several parts and joints (decisions 0027, 0028): set_spec_frame, set_cut_list, set_spec_part
  and set_spec_joint for each, set_scale_length, set_size_checks; fit_circles measures round
  parts along any axis;
- then preview_twin (look at every part's view), then submit_twin.
Runs and files live in the data folder; tool paths are relative to it."""

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)
LOCAL_WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)
EXPECTED_ERRORS: tuple[type[BaseException], ...] = (
    ValueError,  # includes WorkspaceError and pydantic's ValidationError
    RunFolderConflict,
    GeometrySpecMissing,
    GeneratorError,
    OrchestratorError,
    ExportError,
    KnowledgeBaseError,
    FileNotFoundError,
)
# What an open job does next, by the first step it has not done (moonwalkers.workspace.status).
NEXT_STEPS = {
    "photo": "add_input with the machine photos (each with its view)",
    "notes": "the cited reading notes: add_reference_source, identify_machine, add_fact",
    "mesh": "generate_geometry, then inspect_geometry",
    "spec": "add_joint and set_scale, or the several-part spec tools (set_spec_frame ...)",
    "preview": "preview_twin",
    "twin": "submit_twin",
}


class UnconfiguredGenerator(Hunyuan3DGenerator):
    """Stands in when ``MOONWALKERS_GEN_ROOT`` is not set. Its fingerprint is the default
    generator's, so a run's earlier mesh is still reused, but generating anything new fails."""

    def __init__(self) -> None:
        super().__init__(Hunyuan3DConfig.under(Path(".")))

    def generate(self, request: GeneratorRequest) -> GeneratorRun:
        raise GeneratorError(
            f"the image-to-3D generator is not configured: set {GEN_ROOT_ENV} for the MCP server "
            "(docs/setup/generators.md)"
        )


def default_generator() -> ImageTo3DGenerator:
    root = os.environ.get(GEN_ROOT_ENV, "").strip()
    return (
        Hunyuan3DGenerator(Hunyuan3DConfig.under(Path(root))) if root else UnconfiguredGenerator()
    )


def create_server(
    workspace: Workspace,
    generator_factory: Callable[[], ImageTo3DGenerator] = default_generator,
    kb: KnowledgeBase | None = None,
    clock: Clock = utc_now,
    pipelines: Mapping[PipelineId, Pipeline] | None = None,
) -> MCPServer:
    """The server, with every tool bound to one data folder and knowledge base. ``pipelines``
    are the input pipelines that are in besides B (default: ``default_pipelines()``)."""
    ws = workspace
    data_dir = Path(ws.data_dir).resolve()
    kb = kb or JsonKnowledgeBase(data_dir / "kb")
    available = default_pipelines() if pipelines is None else dict(pipelines)
    orchestrator = Orchestrator(kb, available, clock=clock)  # reuse rules, decision 0015
    lock = threading.Lock()  # tools run in worker threads; one at a time keeps files consistent
    server = MCPServer(SERVER_NAME, instructions=INSTRUCTIONS)

    def twin_summary(twin: TwinRecord) -> TwinSummary:
        return TwinSummary.of(twin, kb.review_status(twin))

    def job_brief(status: RunStatus) -> JobBrief:
        todo = next((s.step for s in status.steps if not s.done and s.step != "preview"), None)
        if status.stage not in OPEN_STAGES:
            next_step = f"nothing: {status.stage_label}"
        elif todo is None:
            next_step = "submit_twin"
        else:
            next_step = NEXT_STEPS[todo]
        return JobBrief(
            run=status.run,
            job_id=status.job_id,
            machine_key=status.machine_key,
            new_version=status.new_version,
            stage=status.stage,
            stage_label=status.stage_label,
            photo=status.photo.uri if status.photo else None,
            photos=len(status.photos),
            updated_at=status.updated_at,
            next_step=next_step,
        )

    @contextmanager
    def guarded() -> Iterator[None]:
        with lock:
            try:
                yield
            except ToolError:
                raise
            except EXPECTED_ERRORS as exc:
                raise ToolError(str(exc)) from exc
            except Exception as exc:  # an agent can act on any error it can read
                raise ToolError(f"unexpected {type(exc).__name__}: {exc}") from exc

    def run_name(run_dir: Path) -> str:
        return ws.relative(run_dir)

    def summary(run_dir: Path, reference: ReferenceFacts) -> ReferenceSummary:
        identity = reference.identity
        return ReferenceSummary(
            run=run_name(run_dir),
            sources=[s.source_id for s in reference.sources],
            identity=f"{identity.manufacturer} {identity.model}" if identity else None,
            facts=[f.key for f in reference.facts],
            control=[b.behavior_id for b in reference.control],
            issues=len(reference.issues),
        )

    def save_notes(run_dir: Path, change: Callable[[dict[str, Any]], None]) -> ReferenceFacts:
        """Save a change to the reading notes; explain the citation rule when one is broken."""
        try:
            return ws.update_reference(run_dir, change)
        except ValidationError as exc:
            if "citations of unknown sources" not in str(exc):
                raise
            raise ToolError(
                f"{exc} -- Reading notes can cite only the sources recorded with "
                "add_reference_source. The photo added with add_input is a job input: if a note "
                "comes from it, record it with add_reference_source too."
            ) from exc

    def need_reference(run_dir: Path) -> ReferenceFacts:
        reference = ws.reference(run_dir)
        if reference is None:
            raise ToolError("no reference facts yet: add a reference source first")
        return reference

    def when(retrieved_at: datetime | None) -> datetime:
        return retrieved_at or clock()

    # ------------------------------------------------------------------- knowledge base
    @server.tool(annotations=READ_ONLY)
    def check_knowledge_base(
        manufacturer: str | None = None, model: str | None = None
    ) -> KnowledgeBaseReport:
        """Look up stored twins. With a manufacturer and model, list that machine's twin
        versions (oldest first). Without them, list every machine that has a twin, plus the data
        folder and whether the generator is configured. Changes nothing."""
        with guarded():
            root = os.environ.get(GEN_ROOT_ENV, "").strip() or None
            machines = kb.list_machines()
            if manufacturer is None or model is None:
                return KnowledgeBaseReport(
                    data_dir=str(data_dir),
                    generator_root=root,
                    machines=machines,
                    note="Give a manufacturer and a model to see one machine's twin versions.",
                )
            key = machine_key(manufacturer, model)
            versions = [twin_summary(t) for t in kb.list_versions(key)]
            reusable = orchestrator.reusable_twin(key)
            if not versions:
                note = f"No twin for {key} yet; build one with start_run."
            elif reusable is None:
                note = (
                    f"{key} has {len(versions)} twin version(s), all rejected in review; a "
                    "request builds a new version (start_run)."
                )
            else:
                note = (
                    f"{key} has {len(versions)} twin version(s); a request for it reuses "
                    f"v{reusable.version} unless a new version is asked for (request_twin): the "
                    "newest approved version, else the newest not rejected in review."
                )
            return KnowledgeBaseReport(
                data_dir=str(data_dir),
                generator_root=root,
                machines=machines,
                machine_key=key,
                versions=versions,
                note=note,
            )

    @server.tool(annotations=LOCAL_WRITE)
    def request_twin(manufacturer: str, model: str) -> RequestOutcome:
        """Ask the platform for a machine's twin by name. If one is stored, the orchestrator
        reuses the newest approved version, else the newest not rejected in review, and says so;
        nothing is built or stored. If there is none to reuse, this fails; build one with
        start_run."""
        with guarded():
            job = JobRequest(
                job_id=f"request-{clock().strftime('%Y%m%dT%H%M%S%f')}",
                machine=MachineHint(manufacturer=manufacturer, model=model),
            )
            try:
                result = orchestrator.run_job(job)
            except NoInputsError as exc:
                key = machine_key(manufacturer, model)
                if kb.list_versions(key):
                    raise ToolError(
                        f"Every twin version of {key} was rejected in review; build a new one "
                        "with start_run."
                    ) from exc
                raise ToolError(f"No twin for {key} yet; build one with start_run.") from exc
            return RequestOutcome(
                message=result.message,
                reused_existing=result.reused_existing,
                twin=twin_summary(result.twin),
            )

    @server.tool(annotations=READ_ONLY)
    def list_jobs(machine: str | None = None, include_finished: bool = False) -> JobList:
        """List jobs (run folders), the most recently changed first. By default only open ones:
        for example a photo someone uploaded in the dashboard, waiting for you to build it.
        machine narrows the list: a machine folder (haas-ha5c) or key (haas/ha5c). Continue a
        job by passing its run to the other tools; a dashboard job already has its photo and
        its request (machine, new_version), so start at add_reference_source. Changes nothing."""
        with guarded():
            folder = None
            if machine is not None:
                folder = (
                    validate_machine_key(machine).replace("/", "-") if "/" in machine else machine
                )
            statuses = list_runs(ws, folder)
            shown = [s for s in statuses if include_finished or s.stage in OPEN_STAGES]
            waiting = sum(s.stage == "waiting_for_agent" for s in shown)
            note = (
                f"{len(shown)} job(s) shown, {waiting} waiting for the agent."
                if shown
                else "No open jobs. Start one with start_run, or ask for a photo upload."
            )
            return JobList(jobs=[job_brief(s) for s in shown], note=note)

    # --------------------------------------------------------------------------- run setup
    @server.tool(annotations=LOCAL_WRITE)
    def start_run(manufacturer: str, model: str, new_version: bool = False) -> RunInfo:
        """Start a run folder to build a twin of this machine (data/machines/<machine>/runs/).
        The request names the machine. If a twin already exists, submit_twin reuses it unless
        new_version is true. Returns the run id the other tools take."""
        with guarded():
            run_dir = ws.start_run(manufacturer, model, new_version)
            request = ws.request(run_dir)
            key = machine_key(manufacturer, model)
            existing = orchestrator.reusable_twin(key)
            if existing is not None and not new_version:
                note = (
                    f"{key} already has v{existing.version}: submit_twin will reuse it. Start "
                    "the run with new_version=true to build a new version."
                )
            else:
                note = "Next: add_input with the machine photo, then the cited reading notes."
            return RunInfo(
                run=run_name(run_dir),
                run_dir=str(run_dir),
                job_id=request.job_id,
                machine_key=key,
                new_version=new_version,
                existing_twin=twin_summary(existing) if existing else None,
                note=note,
            )

    @server.tool(annotations=LOCAL_WRITE)
    def add_input(
        run: str,
        path: str,
        source_id: str,
        title: str,
        retrieved_at: datetime | None = None,
        license_note: str | None = None,
        input_type: InputType = InputType.MACHINE_PHOTO,
        view: PhotoView | None = None,
        use: PhotoUse | None = None,
    ) -> SourceAdded:
        """Add an input file to the run's request: machine photos for Pipeline B (decision
        0022). The path is relative to the data folder (save inputs under
        machines/<machine>/inputs/ and list them in SOURCES.md first). The title should say
        where the file came from, for example the original URL. retrieved_at is when it was
        downloaded (defaults to now). Its SHA-256 is recorded.
        - view: where the camera stood, in the OPERATOR's words (facing the machine's front):
          front, back, operator_left, operator_right, the corners front_operator_left,
          front_operator_right, back_operator_left, back_operator_right, or detail (a close-up).
          Manuals use the same words ("right headstock" = operator_right). Needed for every
          photo once a run has two or more; one photo alone may leave it out, as in the PoC.
        - use: generator (default for a whole-machine view) or evidence (kept for the cuts,
          joints, size checks and the reviewer; the only use for detail). The generator takes
          one photo per view, all sides or all corners; mark extra photos evidence.
        A nameplate or a motor plate is a reference source (add_reference_source), not an input.
        A document goes to Pipeline A, C or D by its input type, and is refused while that
        pipeline is not in (decision 0021)."""
        with guarded():
            if input_type != InputType.MACHINE_PHOTO and (view or use):
                raise WorkspaceError("view and use are for machine photos only")
            if use is not None and view is None:
                raise WorkspaceError("give the photo's view along with its use")
            photo = InputPhoto(view=view, use=use) if view is not None else None
            pipeline = ROUTES[input_type]
            if pipeline != PipelineId.B and pipeline not in available:
                raise WorkspaceError(
                    f"Pipeline {pipeline.value} ({OWNERS[pipeline]}'s), which reads "
                    f"{input_type.value} inputs, is not in yet (decision 0021). Cite the document "
                    "with add_reference_source and record what it says with add_fact instead."
                )
            run_dir = ws.run_dir(run)
            file = ws.data_file(path)
            source = Source(
                source_id=source_id,
                kind="file",
                input_type=input_type,
                uri=ws.relative(file),
                title=title,
                sha256=sha256_of(file),
                retrieved_at=when(retrieved_at),
                license_note=license_note,
            )
            request = ws.add_input(run_dir, source, photo)
            is_photo = input_type == InputType.MACHINE_PHOTO
            plan = check_photos(request.sources, request.photos) if is_photo else None
            return SourceAdded(
                run=run,
                source=source,
                inputs=[s.source_id for s in request.sources],
                generator_input=generator_input(plan) if is_photo else None,
            )

    # -------------------------------------------------------------------- reading notes
    @server.tool(annotations=LOCAL_WRITE)
    def add_reference_source(
        run: str,
        source_id: str,
        kind: Literal["url", "file", "user_input"],
        uri: str,
        title: str,
        input_type: InputType | None = None,
        retrieved_at: datetime | None = None,
        local_copy: str | None = None,
        license_note: str | None = None,
    ) -> SourceAdded:
        """Record a document the facts come from, so add_fact and identify_machine can cite
        it. kind "url": uri is the URL, and local_copy (relative to the data folder) is the
        copy read, which gets hashed. kind "file": uri is a file in the data folder. kind
        "user_input": uri is "user", for something a person said. retrieved_at is when it was
        read or downloaded (defaults to now)."""
        with guarded():
            run_dir = ws.run_dir(run)
            sha256 = None
            if kind == "file":
                file = ws.data_file(uri)
                uri, sha256 = ws.relative(file), sha256_of(file)
            elif local_copy is not None:
                sha256 = sha256_of(ws.data_file(local_copy))
            if kind == "user_input":
                uri = "user"
            source = Source(
                source_id=source_id,
                kind=kind,
                input_type=input_type,
                uri=uri,
                title=title,
                sha256=sha256,
                retrieved_at=when(retrieved_at),
                license_note=license_note,
            )

            def add(data: dict[str, Any]) -> None:
                if any(s["source_id"] == source_id for s in data["sources"]):
                    raise WorkspaceError(f"the reference facts already have {source_id!r}")
                data["sources"].append(source.model_dump(mode="json"))

            reference = save_notes(run_dir, add)
            return SourceAdded(
                run=run, source=source, inputs=[s.source_id for s in reference.sources]
            )

    @server.tool(annotations=LOCAL_WRITE)
    def identify_machine(
        run: str,
        manufacturer: str,
        model: str,
        confidence: float,
        citations: list[Citation],
        category: str | None = None,
        aliases: list[str] | None = None,
    ) -> ReferenceSummary:
        """Record who made the machine and which model it is, citing the reference sources
        that say so (quote them). Replaces an earlier identity."""
        with guarded():
            run_dir = ws.run_dir(run)
            need_reference(run_dir)
            identity = MachineIdentity(
                manufacturer=manufacturer,
                model=model,
                category=category,
                aliases=aliases or [],
                confidence=confidence,
                citations=citations,
            )

            def set_identity(data: dict[str, Any]) -> None:
                data["identity"] = identity.model_dump(mode="json")

            return summary(run_dir, save_notes(run_dir, set_identity))

    @server.tool(annotations=LOCAL_WRITE)
    def add_fact(
        run: str,
        key: str,
        value: float | int | str | bool,  # noqa: PYI041 - keeps integer facts as integers
        confidence: float,
        citations: list[Citation],
        unit: str | None = None,
        original: str | None = None,
        replace: bool = False,
    ) -> ReferenceSummary:
        """Record one specification value with its sources. Use SI units ("m", "rad/s", "kg"),
        and keep the value as written in `original`. Cite with a locator (page, view, table) and
        a short verbatim quote. Pipeline B uses `center_height` (m) to scale the model,
        `max_spindle_speed` (rad/s) for the joint, and `overall_width`, `overall_height`,
        `overall_depth` (m) for size checks. Mark your own reasoning [INFERENCE]."""
        with guarded():
            run_dir = ws.run_dir(run)
            need_reference(run_dir)
            fact = Fact(
                key=key,
                value=value,
                unit=unit,
                original=original,
                confidence=confidence,
                citations=citations,
            )

            def put(data: dict[str, Any]) -> None:
                facts = [f for f in data["facts"] if f["key"] != key]
                if len(facts) != len(data["facts"]) and not replace:
                    raise WorkspaceError(f"fact {key!r} exists; pass replace=true to change it")
                data["facts"] = [*facts, fact.model_dump(mode="json")]

            return summary(run_dir, save_notes(run_dir, put))

    @server.tool(annotations=LOCAL_WRITE)
    def add_control(
        run: str,
        behavior_id: str,
        name: str,
        kind: Literal[
            "state_machine", "command_set", "lookup_table", "program_interpreter", "other"
        ],
        description: str,
        confidence: float,
        citations: list[Citation],
        drives_joints: list[str] | None = None,
        spec: dict[str, Any] | None = None,
    ) -> ReferenceSummary:
        """Record how the machine is controlled (for example its indexing program), citing
        the manual. Pipeline B's joint is named "spindle_rotation"; list it in drives_joints
        if this behaviour moves the spindle. spec holds structured details (units in the key
        names, for example step_size_deg). To make the twin run a program (success level 3,
        decision 0016), use kind "program_interpreter" and put the program in
        spec["program"]["rows"], one row per step as the manual prints it: [step,
        step_size_deg, feed_deg_s (or the Step# for G96), loop_count, g_code], for example the
        manual's programming examples. It is checked now, and the build writes a program folder
        for Isaac Sim. A manual machine (decision 0025; docs/agent-procedure.md) takes three:
        a "state_machine" switch (spec inputs, on_when, start_input, off_why, not_described), a
        "lookup_table" of speeds (spec joint, switch, rows of rpm, initial_rpm, change_only_when,
        run_up_s, coast_down_s) and a "command_set" of the operator's commands with scenarios
        (spec switch, speed, quill, commands, scenarios, default_scenario), each checked here;
        the build then writes a controls folder with live controls for Isaac Sim."""
        with guarded():
            run_dir = ws.run_dir(run)
            need_reference(run_dir)
            behavior = ControlBehavior(
                behavior_id=behavior_id,
                name=name,
                kind=kind,
                description=description,
                drives_joints=drives_joints or [],
                spec=spec or {},
                confidence=confidence,
                citations=citations,
            )
            if runnable_behaviors([behavior]):
                IndexProgram.from_behavior(behavior)  # refuses a program that cannot run

            def put(data: dict[str, Any]) -> None:
                kept = [b for b in data["control"] if b["behavior_id"] != behavior_id]
                check_behavior(behavior, [ControlBehavior.model_validate(b) for b in kept])
                data["control"] = [*kept, behavior.model_dump(mode="json")]

            return summary(run_dir, save_notes(run_dir, put))

    @server.tool(annotations=LOCAL_WRITE)
    def add_issue(
        run: str,
        severity: Literal["info", "warning", "error"],
        message: str,
        ref: str | None = None,
    ) -> ReferenceSummary:
        """Record something a reviewer should know: a disagreement between sources, an
        assumption, a doubt. ref names the fact, part or joint concerned."""
        with guarded():
            run_dir = ws.run_dir(run)
            need_reference(run_dir)
            issue = Issue(severity=severity, message=message, ref=ref)

            def put(data: dict[str, Any]) -> None:
                data["issues"].append(issue.model_dump(mode="json"))

            return summary(run_dir, save_notes(run_dir, put))

    # ---------------------------------------------------------------------------- geometry
    @server.tool(annotations=LOCAL_WRITE)
    def generate_geometry(run: str) -> GenerationReport:
        """Turn the run's photos into a mesh with the image-to-3D generator (about a minute on
        the GPU), or reuse the mesh this run already made. One photo runs the single-image
        model; two to four (each with a view) run the multi-view model. Renders six views of
        it; open the PNG to see how the generator's axes sit before calling inspect_geometry.
        Corner photos make a mesh turned about 45 deg (expected_turn_deg): measure the turn
        with inspect_geometry and pass it as yaw_deg there and to add_joint."""
        with guarded():
            run_dir = ws.run_dir(run)
            reused = (run_dir / GENERATOR_DIR / GENERATOR_RECORD).is_file()
            request = ws.request(run_dir)
            pipeline = PipelineB(generator_factory(), data_dir, run_dir, photos=request.photos)
            plan = pipeline.plan(request.sources)
            generated = pipeline.generate(request.sources)
            mesh = load_mesh(generated.mesh_path)
            views = render_views(mesh, run_dir / INSPECT_DIR)["sheet"]
            sides = plan.sides()
            return GenerationReport(
                run=run,
                mesh_file=ws.relative(generated.mesh_path),
                faces=len(mesh.faces),
                reused=reused,
                generator=f"{generated.generator.name} {generated.generator.version}",
                seconds=generated.seconds,
                peak_vram_gb=generated.peak_vram_gb,
                views=str(views),
                grid=plan.grid,
                photos=[f"{f.slot} = {f.source.source_id} ({f.view})" for f in plan.fed],
                expected_turn_deg=plan.expected_turn_deg,
                sides_guessed=None if sides is None else list(sides[2]),
            )

    @server.tool(annotations=LOCAL_WRITE)
    def inspect_geometry(
        run: str,
        up: AxisName,
        front: AxisName,
        window: float | None = None,
        circle_x: list[float] | None = None,
        yaw_deg: float = 0.0,
    ) -> InspectionReport:
        """Orient the generated mesh (the generator axis that points up, and the one the spindle
        faces) and measure it in twin axes: x front, y left (the machine's own left), z up, in
        model units. Read `warnings` first.
        - yaw_deg: where the machine's front points after orienting, from +x towards +y; the
          mesh is turned back by it. Corner photos put it near +45 (generate_geometry's
          expected_turn_deg). footprint_deg, the base footprint's long axis, is near 0 or 90
          once the mesh is square; check the views too, since it cannot tell front from back.
        - tip_slabs: the axis (y, z) from thin slabs behind the mesh's front-most point. Right
          only if the spindle is the front-most part (a nose, as on the HA5C).
        - circle_scan: a circle fitted to the surface in slices over the front of the mesh;
          `round` fits show where a round part (platter, nose, disc) is and its centre.
        - circle_x: if the warnings say the tip slabs measured something else (base feet, a
          bracket), inspect again with x positions inside the round moving part; their round
          fits' centre becomes the axis (axis_source "circle_fits").
        - profile: how far the surface reaches from the axis in use along x (samples within
          `window`): where the body's front face, any flange and the spindle are.
        Open the returned views PNG."""
        with guarded():
            run_dir = ws.run_dir(run)
            result = inspect_mesh(
                generated_mesh(run_dir),
                run_dir / "inspect_oriented",
                up,
                front,
                window,
                circle_x,
                yaw_deg,
            )
            lowest = result.bounds[0][2]
            return InspectionReport(
                run=run,
                views=str(result.views),
                faces=result.faces,
                bounds_min=result.bounds[0],
                bounds_max=result.bounds[1],
                warnings=result.warnings,
                tip_slabs=[
                    TipSlabReport(
                        depth=s.depth,
                        vertices=s.count,
                        axis_yz=s.axis_yz,
                        radius=s.radius,
                        extent_yz=s.extent_yz,
                    )
                    for s in result.tip
                ],
                circle_scan=[circle_report(f) for f in result.circle_scan],
                circle_fits=[circle_report(f) for f in result.circle_fits],
                axis_source=result.axis_source or "tip_slabs",
                axis_yz=result.axis_yz,
                axis_height_above_lowest=(
                    result.axis_yz[1] - lowest if result.axis_yz is not None else None
                ),
                window=result.window,
                profile=[
                    ProfileSliceReport(x=s.t, r_max=s.radius, samples=s.count)
                    for s in result.profile
                ],
                yaw_deg=result.yaw_deg,
                footprint_deg=result.footprint_deg,
            )

    @server.tool(annotations=READ_ONLY)
    def fit_circles(
        run: str,
        up: AxisName,
        front: AxisName,
        along: Literal["x", "y", "z"],
        at: list[float],
        yaw_deg: float = 0.0,
    ) -> CirclesReport:
        """Fit a circle to the oriented mesh's surface in a thin slice across `along` at each
        position in `at` (model units, after orienting and turning by yaw_deg, as
        inspect_geometry): where a round part's axis is when it is not along +x, such as a
        column, a quill or a guard along z, or a hub along y. `round` fits are the ones to
        trust; a fit's centre is a point in the twin's axes, a joint's `point` or a cut
        cylinder's centre. Several slices along one part agree when it is straight."""
        with guarded():
            run_dir = ws.run_dir(run)
            mesh = transformed(
                load_mesh(generated_mesh(run_dir)), orientation_matrix(up, front, yaw_deg)
            )
            fits = [
                CircleAlongReport(
                    position=fit.x,
                    samples=fit.samples,
                    centre=centre,
                    radius=fit.radius,
                    rms=fit.rms,
                    coverage=fit.coverage,
                    round=fit.round,
                )
                for fit, centre in fit_circles_along(mesh, along, at)
            ]
            return CirclesReport(run=run, along=along, fits=fits)

    def generator_input(plan: PhotoPlan | None) -> str:
        if plan is None:
            return "no photo for the generator yet"
        model = "single-image model" if plan.grid == "single" else f"multi-view model, {plan.grid}"
        fed = ", ".join(f"{f.slot} = {f.source.source_id}" for f in plan.fed)
        return f"{model}: {fed}; evidence: {len(plan.evidence)} photo(s)"

    def circle_report(fit: CircleFit) -> CircleFitReport:
        return CircleFitReport(
            x=fit.x,
            samples=fit.samples,
            centre_yz=fit.centre_yz,
            radius=fit.radius,
            inliers=fit.inliers,
            rms=fit.rms,
            coverage=fit.coverage,
            round=fit.round,
        )

    def spec_status(run: str, run_dir: Path) -> SpecStatus:
        state = ws.spec_state(run_dir)
        if state.kind == "parts":
            spec = state.spec if isinstance(state.spec, PartsSpec) else None
            pieces = ws.parts_pieces(run_dir)
            return SpecStatus(
                run=run,
                kind="parts",
                parts_set=list(state.parts),
                complete=spec is not None,
                spec=None,
                problem=state.problem,
                parts={p["part_id"]: p["kind"] for p in pieces.get("parts", {}).values()},
                joints=[
                    f"{j['joint_id']}: {j['joint_type']}, {j['parent']} -> {j['child']}"
                    for j in pieces.get("joints", {}).values()
                ],
                cuts=[f"{c['part']}: {len(c['shapes'])} shape(s)" for c in pieces.get("cuts", [])],
                note=(
                    "The geometry spec is complete; check it with preview_twin."
                    if spec is not None
                    else f"Not a spec yet: {state.problem}."
                ),
            )
        missing = [p for p in ("joint", "scale") if p not in state.parts]
        note = (
            "The geometry spec is complete; check it with preview_twin."
            if state.spec is not None and not missing
            else f"Still to set: {', '.join(missing)}."
        )
        return SpecStatus(
            run=run,
            kind=state.kind,
            parts_set=list(state.parts),
            complete=not missing,
            spec=state.spec if not isinstance(state.spec, PartsSpec) else None,
            note=note,
        )

    def need_spec(run_dir: Path) -> None:
        state = ws.spec_state(run_dir)
        if state.spec is None:
            how = state.problem if state.kind == "parts" else "call add_joint and set_scale"
            raise ToolError(f"the geometry spec is not complete: {how}")

    def cited_metres(run_dir: Path, key: str) -> float:
        fact = need_reference(run_dir).fact(key)
        if fact is None or fact.unit != "m" or isinstance(fact.value, bool | str):
            raise ToolError(f"record the cited fact '{key}' in m first (add_fact)")
        return float(fact.value)

    @server.tool(annotations=LOCAL_WRITE)
    def add_joint(
        run: str,
        up: AxisName,
        front: AxisName,
        spindle_axis_yz: tuple[float, float],
        spindle_radius: float,
        spindle_start_x: float,
        method: str,
        decided_by: str = "Claude Code (agent)",
        yaw_deg: float = 0.0,
    ) -> SpecStatus:
        """Define the spindle joint, in the model units of inspect_geometry (after orienting,
        and after turning by yaw_deg, the value inspect_geometry was given).
        The spindle part is every face within spindle_radius of the axis through
        (y, z) = spindle_axis_yz and in front of x = spindle_start_x, where the joint sits.
        The joint turns about +x. `method` says how you chose these values (cite the
        measurements, and mark judgement [INFERENCE]); it becomes part of a cited source."""
        with guarded():
            run_dir = ws.run_dir(run)
            ws.set_spec_part(
                run_dir,
                "joint",
                {
                    "up": up,
                    "front": front,
                    "spindle_axis_yz": list(spindle_axis_yz),
                    "spindle_radius": spindle_radius,
                    "spindle_start_x": spindle_start_x,
                    "yaw_deg": yaw_deg,
                    "decided_by": decided_by,
                    "method": method,
                },
            )
            return spec_status(run, run_dir)

    @server.tool(annotations=LOCAL_WRITE)
    def set_scale(run: str, base_z: float | None = None) -> SpecStatus:
        """Scale the model from the cited `center_height` fact (the spindle axis height above
        the base, in m), so the scale traces to a document. base_z is the base plane in model
        units; leave it out to use the mesh's lowest point (check it is the flat base)."""
        with guarded():
            run_dir = ws.run_dir(run)
            fact = need_reference(run_dir).fact(SCALE_FACT)
            if fact is None or fact.unit != "m" or isinstance(fact.value, bool | str):
                raise ToolError(f"record the cited fact '{SCALE_FACT}' in m first (add_fact)")
            value = float(fact.value)
            base = "the lowest point" if base_z is None else f"z = {base_z}"
            ws.set_spec_part(
                run_dir,
                "scale",
                {
                    "center_height_m": value,
                    "base_z": base_z,
                    "note": (
                        f"the cited '{SCALE_FACT}' ({value} m) over the axis height above {base}."
                    ),
                },
            )
            return spec_status(run, run_dir)

    # ------------------------------------------------------------- a several-part spec (0028)
    def parts_preview(run: str, run_dir: Path, spec: PartsSpec, photos: bool) -> PartsPreviewReport:
        prepared = run_dir / GENERATOR_DIR / "prepared" if photos else None
        preview = preview_parts_spec(
            generated_mesh(run_dir),
            spec,
            ws.reference(run_dir),
            run_dir / PARTS_PREVIEW_DIR,
            prepared,
        )
        m = preview.model
        seams = {s.part: s for s in m.seams}
        return PartsPreviewReport(
            run=run,
            scale_m_per_unit=m.scale_factor,
            scale_measured_model_units=m.scale_measured_model_units,
            overall_extents_m=m.overall_extents_m,
            parts=[
                PartPreview(
                    part_id=p.part_id,
                    kind=p.kind,
                    faces=p.faces,
                    pieces=seams[p.part_id].pieces if p.part_id in seams else None,
                    stray_faces=seams[p.part_id].stray_faces if p.part_id in seams else None,
                    bounds_m=p.bounds_m,
                )
                for p in m.parts
            ],
            removed_faces=m.removed_faces,
            joints=[
                JointPreview(joint_id=j.joint_id, axis=j.axis, origin_m=j.origin_m)
                for j in m.joints
            ],
            photos=[
                f"{f.slot}: azimuth {f.fit.azimuth_deg:+.1f} deg (slot implies "
                f"{f.expected_azimuth_deg:+.1f}), elevation {f.fit.elevation_deg:.1f}, "
                f"silhouette IoU {f.fit.iou:.3f}"
                for f in preview.photos
            ],
            size_checks=preview.size_checks,
            issues=preview.issues,
            holes=[
                HoleReport(
                    part=h.part, centre=h.centre, size=h.size, edges=h.edges, across=list(h.across)
                )
                for h in preview.holes
            ],
            views={name: str(path) for name, path in preview.views.items()},
        )

    @server.tool(annotations=LOCAL_WRITE)
    def set_spec_frame(
        run: str,
        up: AxisName,
        front: AxisName,
        origin_xy: tuple[float, float],
        fixed_part: str,
        method: str,
        yaw_deg: float = 0.0,
        base_z: float | None = None,
        decided_by: str = "Claude Code (agent)",
    ) -> SpecStatus:
        """Start or change a spec of several parts and joints (decision 0027): how the mesh is
        turned into the twin's axes (up, front and yaw_deg as for inspect_geometry: x front,
        y the machine's own left, z up), the twin's origin (on the base plane, base_z or the
        lowest point, under origin_xy in model units: the spindle's axis on a drill press), the
        part that stays fixed and keeps every face no cut takes, and `method`: how the spec was
        made, from which measurements and photos ([INFERENCE] for judgement). Then
        set_cut_list, set_spec_part and set_spec_joint for each, set_scale_length."""
        with guarded():
            run_dir = ws.run_dir(run)
            frame = {
                "up": up,
                "front": front,
                "yaw_deg": yaw_deg,
                "origin_xy": list(origin_xy),
                "base_z": base_z,
                "fixed_part": fixed_part,
                "decided_by": decided_by,
                "method": method,
            }
            ws.set_parts_piece(run_dir, "frame", frame)
            return spec_status(run, run_dir)

    @server.tool(annotations=LOCAL_WRITE)
    def set_cut_list(run: str, cuts: list[PartCut]) -> SpecStatus:
        """Set the ordered cut list (decision 0023), replacing the last one: each entry gives a
        part (cut or removed) shapes in model units on the oriented mesh, and a note naming its
        evidence. A face goes to the first entry whose shape holds its centre; faces no entry
        takes stay with the fixed part. An entry for the fixed part early in the list keeps its
        faces out of later shapes (a wall behind a removed handle). Shapes: a cylinder (point,
        axis, radius, start and end along the axis from the point) or a box (min, max)."""
        with guarded():
            run_dir = ws.run_dir(run)
            ws.set_parts_piece(run_dir, "cuts", [c.model_dump(mode="json") for c in cuts])
            return spec_status(run, run_dir)

    @server.tool(annotations=LOCAL_WRITE)
    def set_spec_part(run: str, part: SpecPart) -> SpecStatus:
        """Add a part, or replace the one with its part_id (decision 0027). kind:
        - cut: its faces come from the cut list. `patches` close holes that removed faces leave
          in it, each at a hole's centre from preview_twin's `holes` (model units);
        - removed: faces the cut list takes out of the twin (what a stand-in replaces), with why;
        - stand_in: a labelled shape for a part the mesh hides or gets wrong but that shows.
          `shape` sizes are in metres (cited sizes, or photo proportions scaled by a cited size
          in the same photo); `at` is in model units on the oriented mesh, `turn_deg` about +z;
          `citations` name the sizes and the photos it is matched to; `replaces` the removed
          part. A stand-in that does not move on its own needs a fixed joint to its part.
        `note` says what the part is and from which evidence; `inaccuracy` a known difference
        from the machine (a warning in the twin). Name a stand-in "Stand-in: ..."."""
        with guarded():
            run_dir = ws.run_dir(run)
            ws.set_parts_piece(run_dir, "parts", part.model_dump(mode="json"))
            return spec_status(run, run_dir)

    @server.tool(annotations=LOCAL_WRITE)
    def set_spec_joint(run: str, joint: SpecJoint) -> SpecStatus:
        """Add a joint, or replace the one with its joint_id (decision 0027): revolute,
        prismatic or fixed, from parent to child, along `axis` through `point` (model units on
        the oriented mesh; fit_circles finds round parts' axes). Limits are in contract units
        (rad or m) about the modelled pose. `mode` (driven, spring_return, locked, free),
        `adjustable_stop` and `follows` are the contract's v0.2.0 behaviour (decision 0020),
        each with citations; `max_velocity_fact` names a cited speed. `note` says how the axis
        and point were measured; `citations` what says it moves and how far."""
        with guarded():
            run_dir = ws.run_dir(run)
            ws.set_parts_piece(run_dir, "joints", joint.model_dump(mode="json"))
            return spec_status(run, run_dir)

    @server.tool(annotations=LOCAL_WRITE)
    def remove_spec_entry(run: str, piece: Literal["parts", "joints"], entry_id: str) -> SpecStatus:
        """Take a part or a joint out of a several-part spec, by its id."""
        with guarded():
            run_dir = ws.run_dir(run)
            ws.remove_parts_entry(run_dir, piece, entry_id)
            return spec_status(run, run_dir)

    @server.tool(annotations=LOCAL_WRITE)
    def set_scale_length(
        run: str, fact: str, how: str, measured_model_units: float | None = None
    ) -> SpecStatus:
        """Scale a several-part spec by any cited length (decision 0024): `fact` is a recorded
        fact in m (add_fact), and measured_model_units the same length measured on the oriented
        mesh, with `how` it was measured. For overall_depth, overall_width or overall_height,
        leave measured_model_units out: the pipeline measures the mesh's extent. Prefer the
        largest cited length whose two ends both show in the photos."""
        with guarded():
            run_dir = ws.run_dir(run)
            cited_metres(run_dir, fact)
            if measured_model_units is None and fact not in EXTENT_FACTS:
                raise ToolError(
                    f"give measured_model_units: the pipeline measures only {sorted(EXTENT_FACTS)}"
                )
            scale = {"fact": fact, "measured_model_units": measured_model_units, "how": how}
            ws.set_parts_piece(run_dir, "scale_length", scale)
            return spec_status(run, run_dir)

    @server.tool(annotations=LOCAL_WRITE)
    def set_size_checks(run: str, checks: list[SizeCheck]) -> SpecStatus:
        """Set the spec's size checks, replacing the last ones: other cited lengths (facts in m)
        with the same length measured in model units and how. The twin compares each with the
        model at the spec's scale, as it does the overall sizes; above 10% is a warning."""
        with guarded():
            run_dir = ws.run_dir(run)
            for check in checks:
                cited_metres(run_dir, check.fact)
            ws.set_parts_piece(run_dir, "size_checks", [c.model_dump(mode="json") for c in checks])
            return spec_status(run, run_dir)

    @server.tool(annotations=LOCAL_WRITE)
    def preview_twin(run: str, photos: bool = False) -> PreviewReport | PartsPreviewReport:
        """Try the geometry spec without storing anything, and open the PNGs it returns.
        - One spindle (decision 0012): split and scale the mesh into preview/, render the
          assembled model, the body and the spindle, and compare the size with the cited one.
        - Several parts (decision 0027): cut, place the stand-ins and scale into preview_parts/,
          with views of the cuts, the parts and each part alone (look at every one: a leftover
          shows only there), the size checks, the twin's issues, and `holes`: open edges where
          removed faces met a cut part, each to patch or to check a stand-in covers. With
          photos=true, the parts are also drawn over each photo the generator was fed (about a
          minute a photo)."""
        with guarded():
            run_dir = ws.run_dir(run)
            need_spec(run_dir)
            spec = ws.spec_state(run_dir).spec
            assert spec is not None
            if isinstance(spec, PartsSpec):
                return parts_preview(run, run_dir, spec, photos)
            preview = preview_parts(generated_mesh(run_dir), spec, run_dir / "preview")
            p = preview.parts
            return PreviewReport(
                run=run,
                scale_m_per_unit=p.scale_factor,
                center_height_model_units=p.center_height_model,
                overall_extents_m=p.overall_extents_m,
                body_bounds_m=p.body_bounds_m,
                spindle_bounds_m=p.spindle_bounds_m,
                body_faces=p.body_faces,
                spindle_faces=p.spindle_faces,
                size_checks=size_checks(p, ws.reference(run_dir)),
                views={name: str(path) for name, path in preview.views.items()},
            )

    # ------------------------------------------------------------------------------- submit
    @server.tool(annotations=LOCAL_WRITE)
    def submit_twin(run: str) -> SubmitReport:
        """Build the twin through the orchestrator. It stores the result and a new twin version
        in the knowledge base (status needs_review), exports twin.usdc and its check files (two
        for one spindle; one per behaviour the joints state for several parts), and validates
        them. If the machine's twin already exists and the run is not a new version, it reuses
        the stored twin instead and says so. A run builds once; start a new run to build
        again."""
        with guarded():
            run_dir = ws.run_dir(run)
            need_spec(run_dir)
            reference = need_reference(run_dir)
            outcome = build_run(
                run_dir,
                data_dir,
                run_dir / REQUEST_FILE,
                reference,
                run_dir / REFERENCE_FILE,
                generator_factory(),
                kb,
                pipelines=available,
            )
            results = [kb.get_result(rid) for rid in outcome.job.twin.built_from]
            issues = [i for r in results if r is not None for i in r.issues]
            return SubmitReport(
                run=run,
                message=outcome.job.message,
                reused_existing=outcome.job.reused_existing,
                twin=twin_summary(outcome.job.twin),
                twin_file=str(outcome.twin_file) if outcome.twin_file else None,
                check_files=[str(p) for p in outcome.check_files],
                validation=outcome.validation,
                issues=issues,
            )

    return server


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="MoonWalkers MCP server (stdio).")
    parser.add_argument("--data", type=Path, help="the data folder (default: see default_data_dir)")
    args = parser.parse_args(argv)
    create_server(Workspace((args.data or default_data_dir()).resolve())).run()
