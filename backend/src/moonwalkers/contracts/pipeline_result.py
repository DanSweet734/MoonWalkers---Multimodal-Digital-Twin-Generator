"""Shared pipeline output contract (DRAFT v0.1.0).

Every input pipeline (A-D) returns one ``PipelineResult`` to the agent
orchestrator. The orchestrator is the only component that writes to the
knowledge base, and it turns one or more results into a versioned
``TwinRecord`` that the exporter writes out as OpenUSD.

Conventions
-----------
* Units inside the contract are SI: metres, radians, seconds, kilograms.
  The USD exporter converts to whatever a target schema expects
  (for example, joint drive values in degrees).
* Every fact, joint and control behaviour cites at least one ``Source`` so a
  user can always see where information came from.
* File paths are relative to the project ``data/`` folder; URLs are kept as-is.
* ``needs_human_review`` defaults to True: v1 keeps a human in the loop.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "0.1.0"

Vec3 = tuple[float, float, float]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------
# Inputs and provenance
# --------------------------------------------------------------------------
class InputType(str, Enum):
    """The eight input types from the Oct 1, 2026 meeting."""

    WALKTHROUGH_VIDEO = "walkthrough_video"  # 1
    MACHINE_PHOTO = "machine_photo"  # 2
    NAMEPLATE_PHOTO = "nameplate_photo"  # 3
    BROCHURE_DATASHEET = "brochure_datasheet"  # 4
    LAYOUT_DRAWING = "layout_drawing"  # 5
    SCHEMATIC = "schematic"  # 6
    PDF_CATALOG = "pdf_catalog"  # 7
    ONLINE_RESOURCE = "online_resource"  # 8


class PipelineId(str, Enum):
    A = "A"  # nameplate photos + brochures/datasheets (Ava Harken)
    B = "B"  # walkthrough video + machine/component photos (Daniel Sweet)
    C = "C"  # layout drawings + schematics (Shankar Kiran Ragavender)
    D = "D"  # PDF catalogs + online catalog/spec resources (Sarkis Nazaryan)


class Source(_Strict):
    """Anything information came from: a file, a URL, or something the user typed."""

    source_id: str
    kind: Literal["file", "url", "user_input"]
    input_type: Optional[InputType] = None  # None for user_input
    uri: str  # relative path under data/, a URL, or "user"
    title: Optional[str] = None
    sha256: Optional[str] = None  # for files, so a re-run can detect changes
    retrieved_at: datetime
    license_note: Optional[str] = None


class Citation(_Strict):
    source_id: str
    locator: Optional[str] = None  # e.g. "p. 12", "Specifications table"
    quote: Optional[str] = None  # short verbatim excerpt when available


# --------------------------------------------------------------------------
# What the pipeline learned
# --------------------------------------------------------------------------
class MachineIdentity(_Strict):
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    category: Optional[str] = None  # e.g. "rotary indexer"
    aliases: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    citations: list[Citation] = Field(min_length=1)


class Fact(_Strict):
    """One specification value, always with where it came from."""

    key: str  # snake_case, e.g. "center_height"
    value: Union[float, int, str, bool]
    unit: Optional[str] = None  # SI where numeric ("m", "rad/s", "kg")
    original: Optional[str] = None  # value as written in the source, e.g. '4.000"'
    confidence: float = Field(ge=0.0, le=1.0)
    citations: list[Citation] = Field(min_length=1)


class Generator(_Strict):
    name: str  # e.g. "stable-fast-3d"
    version: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)


class Part(_Strict):
    """A rigid piece of the machine. Joints connect parts."""

    part_id: str
    name: str
    geometry_file: Optional[str] = None  # relative path; None if primitive
    geometry_format: Literal["glb", "obj", "usd", "usda", "usdc", "primitive"]
    primitive: Optional[dict[str, Any]] = None  # e.g. {"shape": "cylinder", "radius_m": 0.03}
    generator: Optional[Generator] = None
    bbox_min_m: Optional[Vec3] = None
    bbox_max_m: Optional[Vec3] = None
    citations: list[Citation] = Field(default_factory=list)


class ScaleCalibration(_Strict):
    """How model units were tied to real-world size (C10: scale-calibration input)."""

    method: Literal["known_dimension", "reference_object", "none"]
    reference: Optional[str] = None  # Fact key or object name used
    known_value_m: Optional[float] = None
    measured_model_units: Optional[float] = None
    scale_factor: Optional[float] = None
    citations: list[Citation] = Field(default_factory=list)


class Joint(_Strict):
    """A moving connection between two parts (parent = body0, child = body1)."""

    joint_id: str
    joint_type: Literal["revolute", "prismatic", "fixed"]
    parent_part: str
    child_part: str
    axis: Vec3
    origin_m: Vec3
    lower_limit: Optional[float] = None  # rad (revolute) or m (prismatic); None = unlimited
    upper_limit: Optional[float] = None
    max_velocity: Optional[float] = None  # rad/s or m/s
    confidence: float = Field(ge=0.0, le=1.0)
    citations: list[Citation] = Field(min_length=1)


class ControlBehavior(_Strict):
    """Control logic: how the machine is commanded and how it responds."""

    behavior_id: str
    name: str
    kind: Literal["state_machine", "command_set", "lookup_table", "program_interpreter", "other"]
    description: str
    drives_joints: list[str] = Field(default_factory=list)
    spec: dict[str, Any] = Field(default_factory=dict)  # structured details, kind-specific
    confidence: float = Field(ge=0.0, le=1.0)
    citations: list[Citation] = Field(min_length=1)


class Issue(_Strict):
    severity: Literal["info", "warning", "error"]
    message: str
    ref: Optional[str] = None  # id of the part/joint/fact concerned


# --------------------------------------------------------------------------
# The contract itself
# --------------------------------------------------------------------------
class PipelineResult(_Strict):
    schema_version: Literal["0.1.0"] = SCHEMA_VERSION
    result_id: str
    job_id: str
    pipeline: PipelineId
    input_types: list[InputType] = Field(min_length=1)
    produced_at: datetime
    produced_by: str  # pipeline name + version, e.g. "pipeline-b 0.1.0"

    sources: list[Source] = Field(min_length=1)
    identity: Optional[MachineIdentity] = None
    facts: list[Fact] = Field(default_factory=list)
    parts: list[Part] = Field(default_factory=list)
    scale: Optional[ScaleCalibration] = None
    joints: list[Joint] = Field(default_factory=list)
    control: list[ControlBehavior] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    needs_human_review: bool = True

    @model_validator(mode="after")
    def _check_references(self) -> "PipelineResult":
        source_ids = [s.source_id for s in self.sources]
        part_ids = [p.part_id for p in self.parts]
        joint_ids = [j.joint_id for j in self.joints]
        for label, ids in (("source", source_ids), ("part", part_ids), ("joint", joint_ids)):
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate {label} ids")

        def cited(cits: list[Citation], where: str) -> None:
            for c in cits:
                if c.source_id not in source_ids:
                    raise ValueError(f"{where} cites unknown source '{c.source_id}'")

        if self.identity:
            cited(self.identity.citations, "identity")
        for f in self.facts:
            cited(f.citations, f"fact '{f.key}'")
        for p in self.parts:
            cited(p.citations, f"part '{p.part_id}'")
        if self.scale:
            cited(self.scale.citations, "scale")
        for j in self.joints:
            cited(j.citations, f"joint '{j.joint_id}'")
            for end in (j.parent_part, j.child_part):
                if end not in part_ids:
                    raise ValueError(f"joint '{j.joint_id}' references unknown part '{end}'")
        for b in self.control:
            cited(b.citations, f"control '{b.behavior_id}'")
            for jid in b.drives_joints:
                if jid not in joint_ids:
                    raise ValueError(f"control '{b.behavior_id}' drives unknown joint '{jid}'")
        return self


# --------------------------------------------------------------------------
# What the orchestrator stores and returns (knowledge base side)
# --------------------------------------------------------------------------
class TwinRecord(_Strict):
    twin_id: str
    machine_key: str  # normalised "manufacturer/model", used for reuse lookups
    version: int = Field(ge=1)  # re-versioned when the user asks for an update (C6)
    status: Literal["draft", "needs_review", "approved"]
    usd_path: Optional[str] = None
    built_from: list[str] = Field(default_factory=list)  # PipelineResult.result_id values
    created_at: datetime
    notes: Optional[str] = None


class JobResult(_Strict):
    """Returned to the user/agent when a job finishes."""

    job_id: str
    twin: TwinRecord
    reused_existing: bool  # True when the twin was already in the knowledge base (C6)
    message: str  # e.g. "Found an existing twin (v2) for haas/ha5c; reused it."
