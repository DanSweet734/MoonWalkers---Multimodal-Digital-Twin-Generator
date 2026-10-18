"""Pipeline B on the synthetic indexer: generate, stop for the spec, assemble, cite, export."""

import json
import math
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from pydantic import ValidationError

from moonwalkers.contracts.pipeline_result import (
    Citation,
    Fact,
    PipelineId,
    PipelineResult,
    TwinRecord,
)
from moonwalkers.kb import KnowledgeBase
from moonwalkers.orchestrator import JobRequest, MachineHint, Orchestrator
from moonwalkers.pipelines.b import (
    HA5C_REFERENCE,
    GeometrySpecMissing,
    PipelineB,
    ReferenceFacts,
    RunFolderConflict,
    load_reference,
)
from moonwalkers.pipelines.b.mesh_tools import load_mesh
from moonwalkers.usd.exporter import export_twin
from moonwalkers.usd.validate import validate_file

SCALE = 0.1016 / 1.2  # the spec's centre height over the indexer's axis height (z 0.2 - base -1)


@pytest.fixture
def pipeline(photo_run, fake_generator, test_reference, clock) -> PipelineB:
    return PipelineB(
        fake_generator(), photo_run.data_dir, photo_run.run_dir, test_reference, clock=clock
    )


def test_first_run_generates_the_mesh_and_stops_for_the_spec(pipeline, photo_run) -> None:
    with pytest.raises(GeometrySpecMissing) as stopped:
        pipeline.run("job-1", [photo_run.photo])
    assert stopped.value.views.is_file()  # views of the mesh, to write the spec from
    assert stopped.value.spec_path == photo_run.run_dir / "geometry_spec.json"
    record = json.loads((photo_run.run_dir / "generator" / "run.json").read_text("utf-8"))
    assert record["mesh_file"] == "mesh.glb"
    assert record["key"]["generator"] == {"name": "fake-generator", "seed": 0}
    assert pipeline.generator.calls == 1


def test_result_has_cited_parts_joint_scale_and_facts(pipeline, photo_run, write_spec) -> None:
    write_spec(photo_run.run_dir)
    result = pipeline.run("job-1", [photo_run.photo])

    assert (result.result_id, result.pipeline, result.needs_human_review) == (
        "res-job-1-b",
        PipelineId.B,
        True,
    )
    assert result.produced_by == "pipeline-b 0.1.0 (fake-generator 0)"
    photo, spec, sheet = result.sources
    assert photo.sha256 is not None and photo.uri == photo_run.photo.uri
    assert spec.uri == "machines/moonwalkers-testindexer/runs/run-001/geometry_spec.json"
    assert spec.sha256 is not None and "known synthetic geometry" in (spec.title or "")
    assert sheet.source_id == "src-test-sheet"
    assert result.identity is not None and result.identity.model == "Test Indexer"

    body, spindle = result.parts
    assert body.geometry_file == "machines/moonwalkers-testindexer/runs/run-001/meshes/body.glb"
    assert (photo_run.data_dir / spindle.geometry_file).is_file()
    assert body.generator is not None and body.generator.name == "fake-generator"
    assert [c.source_id for c in spindle.citations] == ["src-photo", "src-geometry-spec"]
    assert spindle.bbox_min_m[0] == pytest.approx(0.0, abs=1e-9)  # the spindle starts at the joint

    (joint,) = result.joints
    assert (joint.parent_part, joint.child_part, joint.axis) == ("body", "spindle", (1, 0, 0))
    assert joint.origin_m == (0.0, 0.0, 0.1016)
    assert joint.max_velocity == 1.5  # from the cited max_spindle_speed
    assert result.scale is not None and result.scale.scale_factor == pytest.approx(SCALE)
    assert result.scale.measured_model_units == pytest.approx(1.2)
    assert result.control[0].drives_joints == ["spindle_rotation"]
    # the result survives a round trip through JSON (what the knowledge base stores)
    assert PipelineResult.model_validate_json(result.model_dump_json()) == result


def test_issues_explain_the_method_and_check_the_size(pipeline, photo_run, write_spec) -> None:
    write_spec(photo_run.run_dir)
    issues = {i.ref or i.message[:20]: i for i in pipeline.run("job-1", [photo_run.photo]).issues}

    assert issues["spindle"].severity == "warning"
    assert issues["spindle"].message.startswith("[INFERENCE]")
    assert issues["overall_width"].severity == "info"  # 3 units x SCALE = 0.254 m, as cited
    assert "(+0.0%" in issues["overall_width"].message
    assert issues["overall_height"].severity == "warning"  # 0.169 m against 0.3 m cited
    assert "confidence is 0.5" in issues["overall_height"].message
    assert "overall_depth" not in issues  # not cited, so not checked
    assert "Synthetic reference" in issues["Synthetic reference "].message


def test_rerun_reuses_the_generated_mesh(pipeline, photo_run, write_spec) -> None:
    with pytest.raises(GeometrySpecMissing):
        pipeline.run("job-1", [photo_run.photo])
    write_spec(photo_run.run_dir)
    first = pipeline.run("job-1", [photo_run.photo])
    body = (photo_run.data_dir / first.parts[0].geometry_file).read_bytes()
    again = pipeline.run("job-2", [photo_run.photo])

    assert pipeline.generator.calls == 1
    assert again.parts[0].generator == first.parts[0].generator
    # re-assembling the same mesh with the same spec rewrites identical files
    assert (photo_run.data_dir / again.parts[0].geometry_file).read_bytes() == body


def test_other_generator_settings_are_refused(photo_run, fake_generator, write_spec) -> None:
    write_spec(photo_run.run_dir)
    PipelineB(fake_generator(seed=1), photo_run.data_dir, photo_run.run_dir).run(
        "job-1", [photo_run.photo]
    )
    other = PipelineB(fake_generator(seed=2), photo_run.data_dir, photo_run.run_dir)
    with pytest.raises(RunFolderConflict, match="other generator settings"):
        other.run("job-2", [photo_run.photo])
    assert other.generator.calls == 0


def test_a_changed_spec_is_refused_once_parts_exist(pipeline, photo_run, write_spec) -> None:
    write_spec(photo_run.run_dir)
    pipeline.run("job-1", [photo_run.photo])
    write_spec(photo_run.run_dir, spindle_radius=0.5)
    with pytest.raises(RunFolderConflict, match="another mesh or geometry spec"):
        pipeline.run("job-2", [photo_run.photo])


def test_spec_centre_height_must_be_the_cited_one(pipeline, photo_run, write_spec) -> None:
    write_spec(photo_run.run_dir, center_height_m=0.1)
    with pytest.raises(ValueError, match="not the cited 'center_height'"):
        pipeline.run("job-1", [photo_run.photo])


def test_without_reference_facts_the_result_has_geometry_only(
    photo_run, fake_generator, write_spec
) -> None:
    write_spec(photo_run.run_dir)
    result = PipelineB(fake_generator(), photo_run.data_dir, photo_run.run_dir).run(
        "job-1", [photo_run.photo]
    )
    assert result.identity is None and result.facts == [] and result.control == []
    assert result.joints[0].max_velocity is None
    assert [s.source_id for s in result.sources] == ["src-photo", "src-geometry-spec"]


@pytest.mark.parametrize("problem", ["no photo", "two photos", "outside data", "changed"])
def test_photo_problems_are_reported(pipeline, photo_run, problem: str) -> None:
    photo = photo_run.photo
    sources = {
        "no photo": [],
        "two photos": [photo, photo.model_copy(update={"source_id": "src-photo-2"})],
        "outside data": [photo.model_copy(update={"uri": "../outside.png"})],
        "changed": [photo.model_copy(update={"sha256": "0" * 64})],
    }[problem]
    with pytest.raises(ValueError):
        pipeline.run("job-1", sources)
    assert pipeline.generator.calls == 0


def test_run_folder_must_be_inside_the_data_folder(photo_run, fake_generator, tmp_path) -> None:
    with pytest.raises(ValueError, match="not inside data folder"):
        PipelineB(fake_generator(), photo_run.data_dir, tmp_path / "elsewhere")


def test_reference_facts_must_cite_their_own_sources(test_reference: ReferenceFacts) -> None:
    stray = Fact(
        key="mystery", value=1, confidence=0.1, citations=[Citation(source_id="src-unknown")]
    )
    with pytest.raises(ValidationError, match="unknown sources"):
        ReferenceFacts.model_validate(test_reference.model_dump() | {"facts": [stray.model_dump()]})
    duplicate = test_reference.facts[0].model_dump()
    with pytest.raises(ValidationError, match="duplicate fact keys"):
        ReferenceFacts.model_validate(
            test_reference.model_dump() | {"facts": [duplicate, duplicate]}
        )


def test_ha5c_reference_facts_are_cited_and_consistent() -> None:
    reference = load_reference(HA5C_REFERENCE)
    assert reference.identity is not None
    assert (reference.identity.manufacturer, reference.identity.model) == (
        "Haas Automation",
        "HA5C",
    )
    height = reference.fact("center_height")
    assert height is not None and (height.value, height.unit) == (0.1016, "m")  # 4.000 in
    speed = reference.fact("max_spindle_speed")
    assert speed is not None and speed.value == pytest.approx(math.radians(410), abs=1e-4)
    for fact in reference.facts:
        assert fact.original, f"{fact.key} keeps the value as written"
        assert all(c.quote for c in fact.citations), f"{fact.key} quotes its sources"
    assert reference.control[0].drives_joints == ["spindle_rotation"]
    documents = [s for s in reference.sources if s.uri.endswith(".pdf")]
    assert documents and all(s.sha256 for s in documents)  # which copy was read


def test_orchestrator_stores_exports_and_then_reuses_the_twin(
    photo_run, fake_generator, test_reference, write_spec, kb: KnowledgeBase, clock
) -> None:
    write_spec(photo_run.run_dir)
    pipeline = PipelineB(
        fake_generator(), photo_run.data_dir, photo_run.run_dir, test_reference, clock=clock
    )
    validation = []

    def export(twin: TwinRecord, results: Sequence[PipelineResult]) -> str:
        path = export_twin(twin, results, photo_run.run_dir / "twin.usda", None, photo_run.data_dir)
        validation.extend(validate_file(path))
        return path.relative_to(photo_run.data_dir).as_posix()

    orchestrator = Orchestrator(kb, {PipelineId.B: pipeline}, clock=clock, exporter=export)
    first = orchestrator.run_job(JobRequest(job_id="job-1", sources=[photo_run.photo]))

    assert first.twin.twin_id == "moonwalkers/testindexer@v1"
    assert first.twin.usd_path == "machines/moonwalkers-testindexer/runs/run-001/twin.usda"
    assert kb.get_twin("moonwalkers/testindexer") == first.twin
    assert [i for i in validation if i.severity == "error"] == []
    assert "Exported to machines/" in first.message

    hint = MachineHint(manufacturer="MoonWalkers", model="Test Indexer")
    second = orchestrator.run_job(
        JobRequest(job_id="job-2", sources=[photo_run.photo], machine=hint)
    )
    assert second.reused_existing and second.twin == first.twin
    assert pipeline.generator.calls == 1


def test_parts_are_written_in_metres_in_the_twin_frame(
    pipeline, photo_run, write_spec: Callable[..., Path]
) -> None:
    write_spec(photo_run.run_dir)
    result = pipeline.run("job-1", [photo_run.photo])
    body = load_mesh(photo_run.data_dir / result.parts[0].geometry_file)
    # the box body: 2 x 3 x 2 units, front face at the joint (x = 0), base at z = 0
    assert body.bounds[0] == pytest.approx([-2 * SCALE, -1.5 * SCALE, 0.0], abs=1e-6)
    assert body.bounds[1] == pytest.approx([0.0, 1.5 * SCALE, 2 * SCALE], abs=1e-6)
