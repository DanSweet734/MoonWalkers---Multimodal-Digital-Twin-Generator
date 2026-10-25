"""Shared pipeline output contract (DRAFT v0.2.0).

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

Versions
--------
* 0.1.0 (decision 0004): the first contract.
* 0.2.0 (decision 0020): a joint may also state its ``mode``, an
  ``adjustable_stop`` and the joint it ``follows``. All three are optional, and
  a result that says "0.1.0" may not use them, so stored 0.1.0 results stay
  valid as they are. The contract says what the machine does; how it is
  simulated (stiffness, damping, mimic or rack and pinion) is the exporter's.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "0.2.0"  # what new results write
SchemaVersion = Literal["0.1.0", "0.2.0"]  # what a result may say (decision 0020)

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
    input_type: InputType | None = None  # None for user_input
    uri: str  # relative path under data/, a URL, or "user"
    title: str | None = None
    sha256: str | None = None  # for files, so a re-run can detect changes
    retrieved_at: datetime
    license_note: str | None = None


class Citation(_Strict):
    source_id: str
    locator: str | None = None  # e.g. "p. 12", "Specifications table"
    quote: str | None = None  # short verbatim excerpt when available


# --------------------------------------------------------------------------
# What the pipeline learned
# --------------------------------------------------------------------------
class MachineIdentity(_Strict):
    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None
    category: str | None = None  # e.g. "rotary indexer"
    aliases: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    citations: list[Citation] = Field(min_length=1)


class Fact(_Strict):
    """One specification value, always with where it came from."""

    key: str  # snake_case, e.g. "center_height"
    value: float | int | str | bool
    unit: str | None = None  # SI where numeric ("m", "rad/s", "kg")
    original: str | None = None  # value as written in the source, e.g. '4.000"'
    confidence: float = Field(ge=0.0, le=1.0)
    citations: list[Citation] = Field(min_length=1)


class Generator(_Strict):
    name: str  # e.g. "stable-fast-3d"
    version: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class Part(_Strict):
    """A rigid piece of the machine. Joints connect parts."""

    part_id: str
    name: str
    geometry_file: str | None = None  # relative path; None if primitive
    geometry_format: Literal["glb", "obj", "usd", "usda", "usdc", "primitive"]
    primitive: dict[str, Any] | None = None  # e.g. {"shape": "cylinder", "radius_m": 0.03}
    generator: Generator | None = None
    bbox_min_m: Vec3 | None = None
    bbox_max_m: Vec3 | None = None
    citations: list[Citation] = Field(default_factory=list)


class ScaleCalibration(_Strict):
    """How model units were tied to real-world size (C10: scale-calibration input)."""

    method: Literal["known_dimension", "reference_object", "none"]
    reference: str | None = None  # Fact key or object name used
    known_value_m: float | None = None
    measured_model_units: float | None = None
    scale_factor: float | None = None
    citations: list[Citation] = Field(default_factory=list)


class JointMode(_Strict):
    """How a joint is moved or held when nothing commands it (v0.2.0, decision 0020).

    * ``driven``: a motor or actuator moves it; a control behaviour may say how.
    * ``spring_return``: a spring returns it to ``position`` when let go.
    * ``locked``: held at ``position`` until a person changes the setting (a lock handle or bolt).
    * ``free``: it moves when pushed; nothing holds it.

    ``position`` is in the joint's units (rad or m); None means the modelled pose, 0. Only
    ``spring_return`` and ``locked`` take one.
    """

    kind: Literal["driven", "spring_return", "locked", "free"]
    position: float | None = None
    citations: list[Citation] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_position(self) -> JointMode:
        if self.position is not None and self.kind not in ("spring_return", "locked"):
            raise ValueError(f"a '{self.kind}' joint takes no position")
        return self


class AdjustableStop(_Strict):
    """A stop a person sets inside a joint's limits, such as a drill press's depth stop (v0.2.0)."""

    position: float  # rad or m, within the joint's limits
    side: Literal["lower", "upper"]  # the end of the travel it shortens
    citations: list[Citation] = Field(min_length=1)


class JointLink(_Strict):
    """The joint moves with ``leader``: position = ``ratio`` * leader's position + ``offset``
    (v0.2.0).

    ``ratio`` is in the follower's units per leader unit (rad per m for a turning joint that
    follows a sliding one), signed by each joint's own axis. ``stand_in`` marks a ratio that no
    source gives; the result must then carry an issue on the follower.
    """

    leader: str  # joint_id
    ratio: float
    offset: float = 0.0  # in the follower's units
    stand_in: bool = False
    citations: list[Citation] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_ratio(self) -> JointLink:
        if self.ratio == 0:
            raise ValueError("a link with ratio 0 does not move the follower")
        return self


class Joint(_Strict):
    """A moving connection between two parts (parent = body0, child = body1)."""

    joint_id: str
    joint_type: Literal["revolute", "prismatic", "fixed"]
    parent_part: str
    child_part: str
    axis: Vec3
    origin_m: Vec3
    lower_limit: float | None = None  # rad (revolute) or m (prismatic); None = unlimited
    upper_limit: float | None = None
    max_velocity: float | None = None  # rad/s or m/s
    confidence: float = Field(ge=0.0, le=1.0)
    citations: list[Citation] = Field(min_length=1)
    # v0.2.0 (decision 0020); None = not stated
    mode: JointMode | None = None
    adjustable_stop: AdjustableStop | None = None
    follows: JointLink | None = None

    @model_validator(mode="after")
    def _check_behaviour(self) -> Joint:
        where = f"joint '{self.joint_id}'"
        if self.joint_type == "fixed" and (self.mode or self.adjustable_stop or self.follows):
            raise ValueError(f"{where} is fixed, so it takes no mode, adjustable stop or link")
        if self.follows is not None:
            if self.follows.leader == self.joint_id:
                raise ValueError(f"{where} cannot follow itself")
            if self.mode is not None:
                raise ValueError(f"{where} follows another joint, so it takes no mode")
        if self.mode is not None and self.mode.kind in ("spring_return", "locked"):
            position = self.mode.position if self.mode.position is not None else 0.0
            self._check_within_limits(position, f"{where}: the {self.mode.kind} position")
        if self.adjustable_stop is not None:
            stop = self.adjustable_stop.position
            self._check_within_limits(stop, f"{where}: the adjustable stop")
        return self

    def _check_within_limits(self, position: float, what: str) -> None:
        if self.lower_limit is not None and position < self.lower_limit:
            raise ValueError(f"{what} {position} is below the lower limit {self.lower_limit}")
        if self.upper_limit is not None and position > self.upper_limit:
            raise ValueError(f"{what} {position} is above the upper limit {self.upper_limit}")


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
    ref: str | None = None  # id of the part/joint/fact concerned


# --------------------------------------------------------------------------
# The contract itself
# --------------------------------------------------------------------------
class PipelineResult(_Strict):
    schema_version: SchemaVersion = SCHEMA_VERSION
    result_id: str
    job_id: str
    pipeline: PipelineId
    input_types: list[InputType] = Field(min_length=1)
    produced_at: datetime
    produced_by: str  # pipeline name + version, e.g. "pipeline-b 0.1.0"

    sources: list[Source] = Field(min_length=1)
    identity: MachineIdentity | None = None
    facts: list[Fact] = Field(default_factory=list)
    parts: list[Part] = Field(default_factory=list)
    scale: ScaleCalibration | None = None
    joints: list[Joint] = Field(default_factory=list)
    control: list[ControlBehavior] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    needs_human_review: bool = True

    @model_validator(mode="after")
    def _check_references(self) -> PipelineResult:
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
        self._check_joint_behaviour()
        for b in self.control:
            cited(b.citations, f"control '{b.behavior_id}'")
            for jid in b.drives_joints:
                if jid not in joint_ids:
                    raise ValueError(f"control '{b.behavior_id}' drives unknown joint '{jid}'")
        return self

    def _check_joint_behaviour(self) -> None:
        """Modes, adjustable stops and links (v0.2.0, decision 0020)."""
        source_ids = {s.source_id for s in self.sources}
        joints = {j.joint_id: j for j in self.joints}
        issue_refs = {i.ref for i in self.issues}
        for j in self.joints:
            where = f"joint '{j.joint_id}'"
            stated = {
                "mode": j.mode,
                "adjustable_stop": j.adjustable_stop,
                "follows": j.follows,
            }
            for name, item in stated.items():
                if item is None:
                    continue
                if self.schema_version == "0.1.0":
                    raise ValueError(f"{where} uses '{name}', which needs schema_version 0.2.0")
                for c in item.citations:
                    if c.source_id not in source_ids:
                        unknown = c.source_id
                        raise ValueError(f"{where}: its {name} cites unknown source '{unknown}'")
            link = j.follows
            if link is None:
                continue
            leader = joints.get(link.leader)
            if leader is None:
                raise ValueError(f"{where} follows unknown joint '{link.leader}'")
            if leader.joint_type == "fixed":
                raise ValueError(f"{where} cannot follow the fixed joint '{link.leader}'")
            if link.stand_in and j.joint_id not in issue_refs:
                raise ValueError(f"{where}: its ratio is a stand-in, so it needs an issue on it")
            # Links may chain (PhysX: "no restriction on the number of mimic joints referenced by
            # any individual joint"), but a loop would make a joint follow itself.
            seen = {j.joint_id}
            while link is not None:
                if link.leader in seen:
                    raise ValueError(f"{where}: its links loop back through '{link.leader}'")
                seen.add(link.leader)
                next_joint = joints.get(link.leader)  # an unknown one is reported on its own turn
                link = next_joint.follows if next_joint else None


# --------------------------------------------------------------------------
# What the orchestrator stores and returns (knowledge base side)
# --------------------------------------------------------------------------
class TwinRecord(_Strict):
    twin_id: str
    machine_key: str  # normalised "manufacturer/model", used for reuse lookups
    version: int = Field(ge=1)  # re-versioned when the user asks for an update (C6)
    status: Literal["draft", "needs_review", "approved"]
    usd_path: str | None = None
    built_from: list[str] = Field(default_factory=list)  # PipelineResult.result_id values
    created_at: datetime
    notes: str | None = None


class JobResult(_Strict):
    """Returned to the user/agent when a job finishes."""

    job_id: str
    twin: TwinRecord
    reused_existing: bool  # True when the twin was already in the knowledge base (C6)
    message: str  # e.g. "Found an existing twin (v2) for haas/ha5c; reused it."
