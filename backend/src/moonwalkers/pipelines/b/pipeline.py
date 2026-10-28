"""Pipeline B: machine photos to a scaled, jointed twin geometry (decisions 0012 and 0022).

In one run folder under ``data/`` (data/README.md):

1. ``generator/``: the image-to-3D generator turns the photos into a mesh (recorded in
   ``run.json``). One photo runs the single-image model; two to four, each with its view in the
   request's ``photos`` map, run the multi-view model (``photos.py``). Evidence photos stay in
   the result's sources, but the generator does not get them.
2. ``geometry_spec.json``: the agent or a person inspects the mesh and writes down how to orient,
   split and scale it. Until that file exists, the pipeline renders views of the mesh into
   ``inspect_raw/`` and stops with ``GeometrySpecMissing``.
3. ``meshes/``: the body and the spindle, oriented, split and scaled (recorded in
   ``assembly.json``).
4. The ``PipelineResult``: those parts, the spindle joint, the scale calibration and the reference
   facts read from documents (identity, specifications, control), all cited.

A run folder never changes what it has produced. A re-run with the same photos, generator settings
and spec reuses the earlier output; a re-run with different ones is refused, so the files that a
stored twin points to stay as they were. Use a new run folder instead.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from moonwalkers.clock import Clock, utc_now
from moonwalkers.contracts.pipeline_result import (
    Citation,
    ControlBehavior,
    Fact,
    Generator,
    InputType,
    Issue,
    Joint,
    MachineIdentity,
    Part,
    PipelineId,
    PipelineResult,
    ScaleCalibration,
    Source,
)
from moonwalkers.generators.base import GeneratorRequest, GeneratorRun, ImageTo3DGenerator
from moonwalkers.orchestrator.photos import InputPhoto

from ..base import Pipeline, result_id_for
from .assemble import AssembledParts, GeometrySpec, Vec3, assemble
from .mesh_tools import load_mesh, render_views
from .parts_spec import AssembledModel, PartsSpec, assemble_parts
from .photos import PhotoPlan, photo_issues, plan_photos

VERSION = "0.1.0"
SPEC_FILE = "geometry_spec.json"
GENERATOR_DIR = "generator"
GENERATOR_RECORD = "run.json"
MESHES_DIR = "meshes"
ASSEMBLY_RECORD = "assembly.json"
INSPECT_DIR = "inspect_raw"
PARTS_PREVIEW_DIR = "preview_parts"  # a several-part spec's preview: views and meshes

SPEC_SOURCE_ID = "src-geometry-spec"
JOINT_ID = "spindle_rotation"
SCALE_FACT = "center_height"  # the spindle axis height above the base
SPEED_FACT = "max_spindle_speed"
# Reference facts compared with the assembled model's overall size: fact key -> twin axis.
SIZE_CHECKS = {"overall_depth": 0, "overall_width": 1, "overall_height": 2}
SIZE_WARNING = 0.10  # a size check differing by more than this is a warning [INFERENCE]


class RunFolderConflict(RuntimeError):
    """The run folder already holds output made from different inputs."""


class GeometrySpecMissing(RuntimeError):
    """The mesh exists, but nobody has written its geometry spec yet."""

    def __init__(self, spec_path: Path, views: Path) -> None:
        super().__init__(
            f"no geometry spec yet: look at {views}, then write {spec_path} "
            "(fields: moonwalkers.pipelines.b.assemble.GeometrySpec; method: decision 0012)"
        )
        self.spec_path = spec_path
        self.views = views


class ReferenceFacts(BaseModel):
    """What the agent read about the machine in documents; every item cites its sources."""

    model_config = ConfigDict(extra="forbid")

    sources: list[Source] = Field(min_length=1)
    identity: MachineIdentity | None = None
    facts: list[Fact] = Field(default_factory=list)
    control: list[ControlBehavior] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> ReferenceFacts:
        keys = [f.key for f in self.facts]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate fact keys")
        cited = [c for f in self.facts for c in f.citations]
        cited += [c for b in self.control for c in b.citations]
        cited += self.identity.citations if self.identity else []
        unknown = sorted({c.source_id for c in cited} - {s.source_id for s in self.sources})
        if unknown:
            raise ValueError(f"citations of unknown sources: {unknown}")
        return self

    def fact(self, key: str) -> Fact | None:
        return next((f for f in self.facts if f.key == key), None)


def load_reference(path: Path) -> ReferenceFacts:
    return ReferenceFacts.model_validate_json(Path(path).read_text(encoding="utf-8"))


class PipelineB(Pipeline):
    """Pipeline B: a job's machine photos (decision 0022), one run folder per build. ``photos``
    is the request's map of each photo's view and use."""

    pipeline_id = PipelineId.B

    def __init__(
        self,
        generator: ImageTo3DGenerator,
        data_dir: Path,
        run_dir: Path,
        reference: ReferenceFacts | None = None,
        clock: Clock = utc_now,
        photos: Mapping[str, InputPhoto] | None = None,
    ) -> None:
        self.generator = generator
        self.data_dir = Path(data_dir).resolve()
        self.run_dir = Path(run_dir).resolve()
        if not self.run_dir.is_relative_to(self.data_dir):
            raise ValueError(f"run folder {self.run_dir} is not inside data folder {self.data_dir}")
        self.reference = reference
        self.clock = clock
        self.photos = dict(photos or {})

    def run(self, job_id: str, sources: list[Source]) -> PipelineResult:
        plan, generated = self._photos_and_mesh(sources)
        spec_path = self.run_dir / SPEC_FILE
        if not spec_path.is_file():
            views = render_views(load_mesh(generated.mesh_path), self.run_dir / INSPECT_DIR)
            raise GeometrySpecMissing(spec_path, views["sheet"])
        spec = read_spec(spec_path)
        if isinstance(spec, PartsSpec):  # several parts and joints (decisions 0023 and 0027)
            known = cited_length(self.reference, spec.scale.fact, "the scale")
            model = self._assemble_parts(generated.mesh_path, spec_path, spec, known)
            return self._parts_result(job_id, plan, generated, spec, spec_path, model)
        self._check_scale_reference(spec)
        parts = self._assemble(generated.mesh_path, spec_path, spec)
        return self._result(job_id, plan, generated, spec, spec_path, parts)

    def generate(self, sources: list[Source]) -> GeneratorRun:
        """Step 1 alone: the job's mesh, generated now or reused from this run folder."""
        return self._photos_and_mesh(sources)[1]

    def plan(self, sources: list[Source]) -> PhotoPlan:
        """Which photos the generator gets, in which slot, without generating anything."""
        return self._photos(sources)[0]

    # ------------------------------------------------------------------------------------ steps
    def _photos_and_mesh(self, sources: list[Source]) -> tuple[PhotoPlan, GeneratorRun]:
        plan, paths = self._photos(sources)
        return plan, self._generate(plan, paths)

    def _photos(self, sources: list[Source]) -> tuple[PhotoPlan, dict[str, Path]]:
        """The generator's plan for the job's machine photos, each with its SHA-256 filled in
        (checked where the request gave one), and each photo's file by source id."""
        others = sorted(
            {s.input_type.value for s in sources if s.input_type != InputType.MACHINE_PHOTO}
        )
        if others:
            raise ValueError(f"Pipeline B takes machine photos; got {others} too")
        checked, paths = [], {}
        for photo in sources:
            path = (self.data_dir / photo.uri).resolve()
            if photo.kind != "file" or not path.is_relative_to(self.data_dir) or not path.is_file():
                raise ValueError(
                    f"photo {photo.source_id}: {photo.uri!r} is not a file in the data folder"
                )
            sha256 = _sha256(path)
            if photo.sha256 is not None and photo.sha256 != sha256:
                raise ValueError(
                    f"photo {photo.source_id} has changed since it was added (SHA-256)"
                )
            checked.append(photo.model_copy(update={"sha256": sha256}))
            paths[photo.source_id] = path
        return plan_photos(checked, self.photos), paths

    def _generate(self, plan: PhotoPlan, paths: Mapping[str, Path]) -> GeneratorRun:
        """Run the generator, or reuse this run folder's mesh for the same photos and settings.

        One photo keeps the PoC's key (``photo_sha256``), so earlier run folders still match."""
        out_dir = self.run_dir / GENERATOR_DIR
        record_path = out_dir / GENERATOR_RECORD
        images = plan.images(paths)
        generator = self.generator.for_views(images)
        if plan.grid == "single":
            key = {"photo_sha256": plan.fed[0].source.sha256}
        else:
            key = {"photos": {f.slot: f.source.sha256 for f in plan.fed}}
        key = _json_values({**key, "generator": generator.fingerprint()})
        if record_path.is_file():
            record = _read_json(record_path)
            if record["key"] != key:
                raise RunFolderConflict(
                    f"{out_dir} holds a mesh made from other photos or other generator "
                    "settings; use a new run folder"
                )
            mesh_path = out_dir / record["mesh_file"]
            if not mesh_path.is_file():
                raise RunFolderConflict(f"generated mesh {mesh_path} is missing; use a new run")
            return GeneratorRun(
                mesh_path=mesh_path,
                generator=Generator.model_validate(record["generator"]),
                seconds=record["seconds"],
                peak_vram_gb=record["peak_vram_gb"],
                log_path=out_dir / record["log_file"],
                details=record["details"],
            )
        run = generator.generate(GeneratorRequest(images=images, out_dir=out_dir))
        # Which photo filled which slot travels with the generator into every part's provenance.
        slots = {f.slot: f.source.source_id for f in plan.fed}
        params = {**run.generator.params, "photos": slots}
        generator_used = run.generator.model_copy(update={"params": params})
        run = dataclasses.replace(run, generator=generator_used)
        _write_json(
            record_path,
            {
                "key": key,
                "mesh_file": _relative_or_absolute(run.mesh_path, out_dir),
                "log_file": _relative_or_absolute(run.log_path, out_dir),
                "generator": run.generator.model_dump(mode="json"),
                "seconds": run.seconds,
                "peak_vram_gb": run.peak_vram_gb,
                "details": run.details,
                "photos": plan.record(),
            },
        )
        return run

    def _check_scale_reference(self, spec: GeometrySpec) -> None:
        """The spec's centre height must be the cited one, so the scale traces to a document."""
        fact = self.reference.fact(SCALE_FACT) if self.reference else None
        if fact is None:
            return
        cited = _number(fact, "m")
        if cited is None or not math.isclose(cited, spec.center_height_m, rel_tol=1e-9):
            raise ValueError(
                f"the geometry spec's centre height ({spec.center_height_m} m) is not the cited "
                f"'{SCALE_FACT}' ({fact.value} {fact.unit})"
            )

    def _assemble(self, mesh_path: Path, spec_path: Path, spec: GeometrySpec) -> AssembledParts:
        """Orient, split and scale, unless this run folder holds parts from other inputs."""
        out_dir = self.run_dir / MESHES_DIR
        record_path = out_dir / ASSEMBLY_RECORD
        key = {"mesh_sha256": _sha256(mesh_path), "spec_sha256": _sha256(spec_path)}
        if record_path.is_file() and _read_json(record_path)["key"] != key:
            raise RunFolderConflict(
                f"{out_dir} holds parts made from another mesh or geometry spec; "
                "use a new run folder"
            )
        parts = assemble(mesh_path, spec, out_dir)  # the same inputs give the same files
        _write_json(
            record_path,
            {
                "key": key,
                "produced_by": f"pipeline-b {VERSION}",
                "scale_factor_m_per_unit": parts.scale_factor,
                "center_height_model_units": parts.center_height_model,
                "overall_extents_m": parts.overall_extents_m,
                "faces": {"body": parts.body_faces, "spindle": parts.spindle_faces},
            },
        )
        return parts

    def _assemble_parts(
        self, mesh_path: Path, spec_path: Path, spec: PartsSpec, known_length_m: float
    ) -> AssembledModel:
        """Cut, place the stand-ins and scale, unless this run folder holds parts from other
        inputs. The scale's cited length is part of the key: it sets every size."""
        out_dir = self.run_dir / MESHES_DIR
        record_path = out_dir / ASSEMBLY_RECORD
        key = {
            "mesh_sha256": _sha256(mesh_path),
            "spec_sha256": _sha256(spec_path),
            "scale_length_m": known_length_m,
        }
        if record_path.is_file() and _read_json(record_path)["key"] != key:
            raise RunFolderConflict(
                f"{out_dir} holds parts made from another mesh, geometry spec or scale; "
                "use a new run folder"
            )
        model = assemble_parts(mesh_path, spec, known_length_m, out_dir)
        _write_json(
            record_path,
            {
                "key": key,
                "produced_by": f"pipeline-b {VERSION}",
                "scale_factor_m_per_unit": model.scale_factor,
                "scale": {
                    "fact": spec.scale.fact,
                    "measured_model_units": model.scale_measured_model_units,
                },
                "overall_extents_m": model.overall_extents_m,
                "parts": {p.part_id: {"kind": p.kind, "faces": p.faces} for p in model.parts},
                "removed_faces": model.removed_faces,
                "seams": {
                    s.part: {"faces": s.faces, "pieces": s.pieces, "stray_faces": s.stray_faces}
                    for s in model.seams
                },
            },
        )
        return model

    # ----------------------------------------------------------------------------------- result
    def _result(
        self,
        job_id: str,
        plan: PhotoPlan,
        generated: GeneratorRun,
        spec: GeometrySpec,
        spec_path: Path,
        parts: AssembledParts,
    ) -> PipelineResult:
        now = self.clock()
        ref = self.reference
        spec_source = Source(
            source_id=SPEC_SOURCE_ID,
            kind="file",
            uri=self._relative(spec_path),
            title=f"Geometry spec by {spec.decided_by}: {spec.method}",
            sha256=_sha256(spec_path),
            retrieved_at=now,
        )
        photos = [f.source for f in plan.fed] + [source for source, _ in plan.evidence]
        part_citations = [Citation(source_id=f.source.source_id) for f in plan.fed]
        part_citations.append(Citation(source_id=SPEC_SOURCE_ID))

        def part(part_id: str, name: str, path: Path, bounds: tuple[Vec3, Vec3]) -> Part:
            return Part(
                part_id=part_id,
                name=name,
                geometry_file=self._relative(path),
                geometry_format="glb",
                generator=generated.generator,
                bbox_min_m=bounds[0],
                bbox_max_m=bounds[1],
                citations=part_citations,
            )

        speed = ref.fact(SPEED_FACT) if ref else None
        max_velocity = _number(speed, "rad/s") if speed else None
        height = ref.fact(SCALE_FACT) if ref else None
        return PipelineResult(
            result_id=result_id_for(job_id, PipelineId.B),
            job_id=job_id,
            pipeline=PipelineId.B,
            input_types=[InputType.MACHINE_PHOTO],
            produced_at=now,
            produced_by=f"pipeline-b {VERSION} ({generated.generator.name} "
            f"{generated.generator.version or 'version unknown'})",
            sources=[*photos, spec_source, *(ref.sources if ref else [])],
            identity=ref.identity if ref else None,
            facts=list(ref.facts) if ref else [],
            parts=[
                part(
                    "body",
                    "Body: the whole mesh except the spindle (fixed)",
                    parts.body_path,
                    parts.body_bounds_m,
                ),
                part(
                    "spindle",
                    "Spindle: the mesh in front of the body within the spindle radius",
                    parts.spindle_path,
                    parts.spindle_bounds_m,
                ),
            ],
            scale=ScaleCalibration(
                method="known_dimension",
                reference=SCALE_FACT,
                known_value_m=spec.center_height_m,
                measured_model_units=parts.center_height_model,
                scale_factor=parts.scale_factor,
                citations=[
                    Citation(source_id=SPEC_SOURCE_ID, locator="spindle_axis_yz, base_z"),
                    *(height.citations if height else []),
                ],
            ),
            joints=[
                Joint(
                    joint_id=JOINT_ID,
                    joint_type="revolute",
                    parent_part="body",
                    child_part="spindle",
                    axis=(1.0, 0.0, 0.0),
                    origin_m=parts.joint_origin_m,
                    max_velocity=max_velocity,
                    confidence=0.6,
                    citations=[
                        Citation(source_id=SPEC_SOURCE_ID, locator="spindle_axis_yz, front"),
                        *(speed.citations if speed and max_velocity is not None else []),
                    ],
                )
            ],
            control=list(ref.control) if ref else [],
            issues=[
                *photo_issues(plan),
                *_method_issues(spec, plan),
                *size_checks(parts, ref),
                *(ref.issues if ref else []),
            ],
            needs_human_review=True,
        )

    def _parts_result(
        self,
        job_id: str,
        plan: PhotoPlan,
        generated: GeneratorRun,
        spec: PartsSpec,
        spec_path: Path,
        model: AssembledModel,
    ) -> PipelineResult:
        """The result for a several-part spec: every twin part, its joints with their cited
        behaviour (contract v0.2.0), the scale from a cited length, and what a reviewer needs
        to know as issues."""
        now = self.clock()
        ref = self.reference
        spec_source = Source(
            source_id=SPEC_SOURCE_ID,
            kind="file",
            uri=self._relative(spec_path),
            title=f"Geometry spec by {spec.decided_by}: {spec.method}",
            sha256=_sha256(spec_path),
            retrieved_at=now,
        )
        photos = [f.source for f in plan.fed] + [source for source, _ in plan.evidence]
        fed = [Citation(source_id=f.source.source_id) for f in plan.fed]

        parts = []
        for built in model.parts:
            item = spec.part(built.part_id)
            here = Citation(source_id=SPEC_SOURCE_ID, locator=f"parts[{built.part_id}]")
            stand_in = item.kind == "stand_in"
            parts.append(
                Part(
                    part_id=built.part_id,
                    name=stand_in_name(item.name) if stand_in else item.name,
                    geometry_file=self._relative(built.path),
                    geometry_format="glb",
                    generator=None if stand_in else generated.generator,
                    bbox_min_m=built.bounds_m[0],
                    bbox_max_m=built.bounds_m[1],
                    citations=[here, *item.citations] if stand_in else [*fed, here],
                )
            )
        joints = []
        for item, built in zip(spec.joints, model.joints, strict=True):
            speed = cited_fact(ref, item.max_velocity_fact) if item.max_velocity_fact else None
            unit = "m/s" if item.joint_type == "prismatic" else "rad/s"
            max_velocity = _number(speed, unit) if speed else None
            if speed is not None and max_velocity is None:
                raise ValueError(f"joint '{item.joint_id}': '{speed.key}' is not a speed in {unit}")
            joints.append(
                Joint(
                    joint_id=item.joint_id,
                    joint_type=item.joint_type,
                    parent_part=item.parent,
                    child_part=item.child,
                    axis=built.axis,
                    origin_m=built.origin_m,
                    lower_limit=item.lower,
                    upper_limit=item.upper,
                    max_velocity=max_velocity,
                    confidence=item.confidence,
                    citations=[
                        Citation(source_id=SPEC_SOURCE_ID, locator=f"joints[{item.joint_id}]"),
                        *item.citations,
                        *(speed.citations if speed else []),
                    ],
                    mode=item.mode,
                    adjustable_stop=item.adjustable_stop,
                    follows=item.follows,
                )
            )
        scale_fact = cited_fact(ref, spec.scale.fact)
        return PipelineResult(
            result_id=result_id_for(job_id, PipelineId.B),
            job_id=job_id,
            pipeline=PipelineId.B,
            input_types=[InputType.MACHINE_PHOTO],
            produced_at=now,
            produced_by=f"pipeline-b {VERSION} ({generated.generator.name} "
            f"{generated.generator.version or 'version unknown'})",
            sources=[*photos, spec_source, *(ref.sources if ref else [])],
            identity=ref.identity if ref else None,
            facts=list(ref.facts) if ref else [],
            parts=parts,
            scale=ScaleCalibration(
                method="known_dimension",
                reference=spec.scale.fact,
                known_value_m=float(scale_fact.value),
                measured_model_units=model.scale_measured_model_units,
                scale_factor=model.scale_factor,
                citations=[
                    Citation(source_id=SPEC_SOURCE_ID, locator="scale"),
                    *scale_fact.citations,
                ],
            ),
            joints=joints,
            control=list(ref.control) if ref else [],
            issues=[
                *photo_issues(plan),
                *_turn_issues(spec.yaw_deg, plan),
                *parts_issues(spec, model),
                *size_checks(model, ref),
                *spec_size_checks(spec, model.scale_factor, ref),
                *(ref.issues if ref else []),
            ],
            needs_human_review=True,
        )

    def _relative(self, path: Path) -> str:
        return Path(path).resolve().relative_to(self.data_dir).as_posix()


def generated_mesh(run_dir: Path) -> Path:
    """The run folder's generated mesh: the one ``generator/run.json`` records, else
    ``generator/mesh.glb`` (runs made before the record existed)."""
    out_dir = Path(run_dir) / GENERATOR_DIR
    record = out_dir / GENERATOR_RECORD
    mesh = out_dir / _read_json(record)["mesh_file"] if record.is_file() else out_dir / "mesh.glb"
    if not mesh.is_file():
        raise FileNotFoundError(f"no generated mesh in {out_dir}; generate it first")
    return mesh


def read_spec(path: Path) -> GeometrySpec | PartsSpec:
    """A run's geometry spec: several parts (``PartsSpec``, decision 0027) when it lists
    ``parts``, else decision 0012's single spindle."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "parts" in data:
        return PartsSpec.model_validate(data)
    return GeometrySpec.model_validate(data)


def cited_fact(reference: ReferenceFacts | None, key: str) -> Fact:
    fact = reference.fact(key) if reference else None
    if fact is None:
        raise ValueError(f"the reference facts have no '{key}'; record it with its citation first")
    return fact


def cited_length(reference: ReferenceFacts | None, key: str, use: str) -> float:
    """The cited length ``key`` in metres, for ``use`` (the scale, a size check)."""
    fact = cited_fact(reference, key)
    value = _number(fact, "m")
    if value is None or value <= 0:
        raise ValueError(f"{use} needs '{key}' as a length in m; it is {fact.value!r} {fact.unit}")
    return value


def stand_in_name(name: str) -> str:
    """A stand-in's part name says it is one, so the twin labels it wherever the name shows."""
    return name if name.lower().startswith("stand-in") else f"Stand-in: {name}"


class _Extents(Protocol):
    overall_extents_m: Vec3


def size_checks(parts: _Extents, reference: ReferenceFacts | None) -> list[Issue]:
    """The model's overall size against the cited dimensions (``SIZE_CHECKS``), one issue each.

    The scale comes from one dimension, so these test the generator's proportions; a difference
    above ``SIZE_WARNING`` is a warning.
    """
    issues = []
    for key, axis in SIZE_CHECKS.items():
        fact = reference.fact(key) if reference else None
        cited = _number(fact, "m") if fact else None
        if cited is None:
            continue
        issues.append(_size_issue(key, parts.overall_extents_m[axis], cited, fact, ""))
    return issues


def spec_size_checks(
    spec: PartsSpec, scale: float, reference: ReferenceFacts | None
) -> list[Issue]:
    """The spec's own size checks: each cited length against the inspector's measurement."""
    issues = []
    for check in spec.size_checks:
        cited = cited_length(reference, check.fact, "a size check")
        fact = cited_fact(reference, check.fact)
        measured = check.measured_model_units * scale
        issues.append(_size_issue(check.fact, measured, cited, fact, f" Measured: {check.how}."))
    return issues


def _size_issue(key: str, measured: float, cited: float, fact: Fact, how: str) -> Issue:
    difference = (measured - cited) / cited
    return Issue(
        severity="warning" if abs(difference) > SIZE_WARNING else "info",
        message=f"Size check: the model's {key.replace('_', ' ')} is {measured:.4f} m; "
        f"the cited value is {cited:.4f} m ({difference:+.1%}; the cited value's "
        f"confidence is {fact.confidence:g}).{how}",
        ref=key,
    )


def parts_issues(spec: PartsSpec, model: AssembledModel) -> list[Issue]:
    """What a several-part result tells its reviewer: each stand-in, each part cut out, each
    logged inaccuracy, the pieces each cut part is in, and the seams (decisions 0023, 0027)."""
    issues = []
    pieces = {s.part: s for s in model.seams}
    for part in spec.parts:
        if part.kind == "stand_in":
            replaced = (
                f" It replaces the generated '{part.replaces}' "
                f"({model.removed_faces[part.replaces]} faces cut out of the twin)."
                if part.replaces
                else ""
            )
            note = part.note if part.note.endswith(".") else f"{part.note}."
            issues.append(
                Issue(severity="warning", ref=part.part_id, message=f"Stand-in: {note}{replaced}")
            )
        elif part.kind == "removed":
            issues.append(
                Issue(
                    severity="info",
                    ref=part.part_id,
                    message=f"Cut out of the twin ({model.removed_faces[part.part_id]} faces "
                    f"of the generated mesh): {part.note}",
                )
            )
        elif pieces[part.part_id].pieces > 1:
            seam = pieces[part.part_id]
            issues.append(
                Issue(
                    severity="info",
                    ref=part.part_id,
                    message=f"Part '{part.part_id}' is in {seam.pieces} pieces of the generated "
                    f"mesh ({seam.stray_faces} faces in small ones). {part.note}",
                )
            )
        if part.inaccuracy:
            issues.append(Issue(severity="warning", ref=part.part_id, message=part.inaccuracy))
        if part.patches:
            notes = "; ".join(p.note for p in part.patches)
            issues.append(
                Issue(
                    severity="warning",
                    ref=part.part_id,
                    message=f"Patched: {len(part.patches)} hole(s) in '{part.part_id}' where "
                    f"faces cut out of the twin met it, closed flat, since the surface under them "
                    f"is not known: {notes}.",
                )
            )
    issues += [
        Issue(severity="warning", ref=j.joint_id, message=j.inaccuracy)
        for j in spec.joints
        if j.inaccuracy
    ]
    seam_edges = sum(s.open_edges for s in model.seams) // 2
    issues += [
        Issue(
            severity="info",
            message=f"The cuts follow the generated mesh's faces, so the cut parts have open "
            f"edges along their {seam_edges} seam edges (decision 0023).",
        ),
        Issue(
            severity="info",
            message="Masses are not authored: Isaac Sim infers each part's mass from its convex "
            "hull at 1000 kg/m^3 (decision 0010), not from any cited weight.",
        ),
    ]
    return issues


def _turn_issues(yaw_deg: float, plan: PhotoPlan) -> list[Issue]:
    if not yaw_deg:
        return []
    expected = plan.expected_turn_deg
    expectation = (
        "one photo, so no turn was expected"
        if expected is None
        else f"{expected:+g}° expected for a {plan.grid} grid"
    )
    return [
        Issue(
            severity="info",
            message=f"The mesh's front pointed {yaw_deg:+g}° from the generator's front "
            f"(measured; {expectation}), and was turned back by that much about the up axis "
            "(geometry spec yaw_deg; decision 0022).",
        )
    ]


def _method_issues(spec: GeometrySpec, plan: PhotoPlan) -> list[Issue]:
    """What every Pipeline B result should tell its reviewer about the method (the photos'
    own issues come from ``photo_issues``)."""
    return [
        *_turn_issues(spec.yaw_deg, plan),
        Issue(
            severity="warning",
            message="[INFERENCE] The spindle part is every face in front of the body's front face "
            f"(x = {spec.spindle_start_x} model units) within {spec.spindle_radius} model units "
            "of the spindle axis; which parts turn on the real machine is not confirmed.",
            ref="spindle",
        ),
        Issue(
            severity="info",
            message="The body/spindle cut follows the mesh's faces, so both parts have open edges "
            "along the cut.",
        ),
    ]


def _number(fact: Fact, unit: str) -> float | None:
    """The fact's value if it is a number in ``unit``."""
    value = fact.value
    if fact.unit != unit or isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _json_values(value: dict[str, Any]) -> dict[str, Any]:
    """``value`` as it reads back from JSON (tuples become lists), for comparing records."""
    return json.loads(json.dumps(value))


def _relative_or_absolute(path: Path, base: Path) -> str:
    path = Path(path).resolve()
    return path.relative_to(base).as_posix() if path.is_relative_to(base) else str(path)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
