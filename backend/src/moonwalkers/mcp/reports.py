"""What the MCP tools return (decision 0013).

Pydantic models, so each tool advertises an output schema and returns structured content as well
as JSON text. They stay small, because Claude Code warns when a tool result passes 10,000 tokens
(docs/research/2026-10-18-mcp-server-for-claude-code.md). Images come back as file paths, which
the agent opens with its own file-reading tool.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from moonwalkers.contracts.pipeline_result import Issue, Source, TwinRecord
from moonwalkers.pipelines.b.assemble import GeometrySpec

Vec3 = tuple[float, float, float]


class TwinSummary(BaseModel):
    twin_id: str
    machine_key: str
    version: int
    status: str = Field(description="as stored when it was built")
    review_status: str = Field(description="the latest review's decision, or the stored status")
    usd_path: str | None = Field(description="relative to the data folder")
    created_at: datetime
    built_from: list[str]

    @classmethod
    def of(cls, twin: TwinRecord, review_status: str) -> TwinSummary:
        return cls(
            twin_id=twin.twin_id,
            machine_key=twin.machine_key,
            version=twin.version,
            status=twin.status,
            review_status=review_status,
            usd_path=twin.usd_path,
            created_at=twin.created_at,
            built_from=list(twin.built_from),
        )


class KnowledgeBaseReport(BaseModel):
    data_dir: str
    generator_root: str | None = Field(description="None: generation is not configured")
    machines: list[str] = Field(description="machine keys with at least one twin")
    machine_key: str | None = None
    versions: list[TwinSummary] = Field(default_factory=list)
    note: str


class RequestOutcome(BaseModel):
    message: str
    reused_existing: bool
    twin: TwinSummary


class RunInfo(BaseModel):
    run: str = Field(description="pass this to the other tools")
    run_dir: str
    job_id: str
    machine_key: str
    new_version: bool
    existing_twin: TwinSummary | None
    note: str


class JobBrief(BaseModel):
    run: str = Field(description="pass this to the other tools")
    job_id: str | None
    machine_key: str | None
    new_version: bool
    stage: str
    stage_label: str
    photo: str | None = Field(description="the first input photo, relative to the data folder")
    photos: int = Field(default=0, description="how many machine photos the request has")
    updated_at: datetime
    next_step: str


class JobList(BaseModel):
    jobs: list[JobBrief]
    note: str


class SourceAdded(BaseModel):
    run: str
    source: Source
    inputs: list[str] = Field(default_factory=list, description="the request's input source ids")
    generator_input: str | None = Field(
        default=None,
        description="for a machine photo: which model and slots the generator will use, so far",
    )


class CutoutPreview(BaseModel):
    run: str
    sheet: str = Field(
        description="PNG: each photo cut out on grey, its box in blue, its points green (keep) "
        "or red (leave out); open it"
    )
    photos: list[str] = Field(
        description="source id: method (sam, crop, mask, auto), share of the photo kept, specks "
        "dropped"
    )
    seconds: float


class ReferenceSummary(BaseModel):
    run: str
    sources: list[str]
    identity: str | None
    facts: list[str] = Field(description="fact keys")
    control: list[str] = Field(description="control behaviour ids")
    issues: int


class GenerationReport(BaseModel):
    run: str
    mesh_file: str
    faces: int
    reused: bool = Field(description="True: this run's earlier mesh was reused; no GPU work")
    generator: str
    seconds: float
    peak_vram_gb: float | None
    views: str = Field(description="PNG sheet: front, left, back / right, top, iso")
    grid: str = Field(default="single", description="single (one photo), sides or corners")
    photos: list[str] = Field(
        default_factory=list, description="generator slot = source id (view), for each fed photo"
    )
    expected_turn_deg: float | None = Field(
        default=None,
        description="where the machine's front should point after orienting, from +x towards +y "
        "(corners: +45); measure it with inspect_geometry and pass yaw_deg",
    )
    sides_guessed: list[str] | None = Field(
        default=None, description="sides no fed photo shows (None: the one photo has no view)"
    )


class TipSlabReport(BaseModel):
    depth: float
    vertices: int
    axis_yz: tuple[float, float]
    radius: float
    extent_yz: tuple[float, float] = Field(description="about equal for a round tip")


class CircleFitReport(BaseModel):
    x: float
    samples: int
    centre_yz: tuple[float, float] | None
    radius: float | None
    inliers: float = Field(description="fraction of the slice's samples on the circle")
    rms: float | None
    coverage: float = Field(description="fraction of 10-degree sectors around the centre")
    round: bool = Field(description="good enough to trust the centre")


class ProfileSliceReport(BaseModel):
    x: float
    r_max: float
    samples: int


class InspectionReport(BaseModel):
    run: str
    views: str
    faces: int
    bounds_min: Vec3 = Field(description="model units, twin axes: x front, y left, z up")
    bounds_max: Vec3
    warnings: list[str] = Field(description="read these first: when the tip slabs are wrong")
    tip_slabs: list[TipSlabReport]
    circle_scan: list[CircleFitReport] = Field(description="slices over the front of the mesh")
    circle_fits: list[CircleFitReport] = Field(description="slices at the circle_x given")
    axis_source: str = Field(description="tip_slabs, or circle_fits when circle_x found it")
    axis_yz: tuple[float, float] | None = Field(description="the axis in use")
    axis_height_above_lowest: float | None
    window: float | None
    profile: list[ProfileSliceReport] = Field(description="about the axis in use")
    yaw_deg: float = Field(default=0.0, description="the turn about +z applied after orienting")
    footprint_deg: float | None = Field(
        default=None,
        description="the base footprint's long axis after that turn, from +x towards +y, up to a "
        "multiple of 90 (None: round or square); near 0 or 90 once the mesh is square",
    )


class SpecStatus(BaseModel):
    run: str
    kind: str | None = Field(
        default=None,
        description="spindle (add_joint, set_scale; decision 0012) or parts (set_spec_frame and "
        "the others; decisions 0027, 0028)",
    )
    parts_set: list[str] = Field(description="the pieces of the spec set so far")
    complete: bool
    spec: GeometrySpec | None = Field(description="a single spindle's complete spec")
    problem: str | None = Field(
        default=None, description="why a several-part spec's pieces do not make a spec yet"
    )
    parts: dict[str, str] = Field(
        default_factory=dict, description="a several-part spec's parts: id -> kind"
    )
    joints: list[str] = Field(default_factory=list, description="id: type, parent -> child")
    cuts: list[str] = Field(default_factory=list, description="the cut list, in order")
    note: str


class CircleAlongReport(BaseModel):
    position: float = Field(description="the slice's position along the axis, model units")
    samples: int
    centre: Vec3 | None = Field(description="the circle's centre, in the twin's axes")
    radius: float | None
    rms: float | None
    coverage: float
    round: bool


class CirclesReport(BaseModel):
    run: str
    along: str | Vec3 = Field(description="an axis, or the direction the slices are across")
    within: dict[str, tuple[float, float]] | None = Field(
        default=None, description="the box the surface was kept in, model units, twin axes"
    )
    fits: list[CircleAlongReport]


class PartPreview(BaseModel):
    part_id: str
    kind: str
    faces: int
    pieces: int | None = Field(description="pieces of the generated mesh, for a cut part")
    stray_faces: int | None
    bounds_m: tuple[Vec3, Vec3]


class JointPreview(BaseModel):
    joint_id: str
    axis: Vec3
    origin_m: Vec3


class HoleReport(BaseModel):
    part: str
    centre: Vec3 = Field(description="model units, after orienting: a patch's `near`")
    size: Vec3
    edges: int
    across: list[str] = Field(description="the parts on the other side of its edge")


class PartsPreviewReport(BaseModel):
    run: str
    scale_m_per_unit: float
    scale_measured_model_units: float
    overall_extents_m: Vec3 = Field(description="depth (x), width (y), height (z)")
    parts: list[PartPreview]
    removed_faces: dict[str, int]
    joints: list[JointPreview]
    photos: list[str] = Field(description="each fed photo's fit on the mesh, when placed")
    size_checks: list[Issue]
    issues: list[Issue] = Field(
        description="stand-ins, removed parts, inaccuracies, patches, and each part whose mesh "
        "NVIDIA's asset validator would warn about (zero-area faces, non-manifold edges and "
        "points, in model units), to fix before submitting"
    )
    holes: list[HoleReport] = Field(
        description="open edges a cut part has where removed faces met it: close each with a "
        "patch on that part, or check in the views that a stand-in covers it"
    )
    views: dict[str, str] = Field(
        description="PNGs: cuts, parts, part_<id> (look at each), on_<slot>_photo"
    )


class PreviewReport(BaseModel):
    run: str
    scale_m_per_unit: float
    center_height_model_units: float
    overall_extents_m: Vec3 = Field(description="depth (x), width (y), height (z)")
    body_bounds_m: tuple[Vec3, Vec3]
    spindle_bounds_m: tuple[Vec3, Vec3]
    body_faces: int
    spindle_faces: int
    size_checks: list[Issue]
    mesh_faults: list[Issue] = Field(
        default_factory=list,
        description="what NVIDIA's asset validator would warn about in the body's or the "
        "spindle's mesh (zero-area faces, non-manifold edges and points); empty when clean",
    )
    views: dict[str, str] = Field(description="PNG sheets: assembled, body, spindle")


class FileValidation(BaseModel):
    file: str
    ours: list[Issue]
    nvidia: list[Issue] | None = Field(description="None: NVIDIA's validator is not installed")


class DryRunReport(BaseModel):
    run: str
    scratch_run: str = Field(description="the copied run, in a new folder under data/scratch/")
    message: str = Field(description="the build's message, or why it stopped")
    built: bool
    clean: bool = Field(description="built, and no error or warning from either validator")
    files: list[FileValidation]


class SubmitReport(BaseModel):
    run: str
    message: str
    reused_existing: bool
    twin: TwinSummary
    twin_file: str | None
    check_files: list[str]
    validation: list[Issue]
    issues: list[Issue] = Field(description="what the twin's result says a reviewer should know")
