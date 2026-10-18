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
    status: str
    usd_path: str | None = Field(description="relative to the data folder")
    created_at: datetime
    built_from: list[str]

    @classmethod
    def of(cls, twin: TwinRecord) -> TwinSummary:
        return cls(
            twin_id=twin.twin_id,
            machine_key=twin.machine_key,
            version=twin.version,
            status=twin.status,
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


class SourceAdded(BaseModel):
    run: str
    source: Source
    inputs: list[str] = Field(default_factory=list, description="the request's input source ids")


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


class TipSlabReport(BaseModel):
    depth: float
    vertices: int
    axis_yz: tuple[float, float]
    radius: float


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
    tip_slabs: list[TipSlabReport]
    axis_yz: tuple[float, float] | None = Field(description="from the middle tip slab")
    axis_height_above_lowest: float | None
    window: float | None
    profile: list[ProfileSliceReport]


class SpecStatus(BaseModel):
    run: str
    parts_set: list[str]
    complete: bool
    spec: GeometrySpec | None
    note: str


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
    views: dict[str, str] = Field(description="PNG sheets: assembled, body, spindle")


class SubmitReport(BaseModel):
    run: str
    message: str
    reused_existing: bool
    twin: TwinSummary
    twin_file: str | None
    check_files: list[str]
    validation: list[Issue]
    issues: list[Issue] = Field(description="what the twin's result says a reviewer should know")
