"""The MCP server, driven through an in-memory MCP client as an agent would drive it.

The synthetic indexer stands in for the HA5C (conftest): the fake generator writes it with +Y up
and its spindle nose facing +Z; the spindle axis is at y = 0, z = 0.2 above a base at z = -1, and
the box's front face is at x = 1.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from mcp import Client

from moonwalkers.contracts.pipeline_result import PipelineId, PipelineResult, Source, TwinRecord
from moonwalkers.kb import JsonKnowledgeBase
from moonwalkers.mcp import Workspace, create_server, default_data_dir
from moonwalkers.mcp.server import UnconfiguredGenerator
from moonwalkers.orchestrator import Orchestrator
from moonwalkers.pipelines import Pipeline

MACHINE = {"manufacturer": "MoonWalkers", "model": "Test Indexer"}
SHEET = [{"source_id": "src-sheet", "locator": "p. 1", "quote": "centre height 0.1016 m"}]
SCALE = 0.1016 / 1.2


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def setup(photo_run, fake_generator, clock):
    generator = fake_generator()
    server = create_server(Workspace(photo_run.data_dir, clock), lambda: generator, clock=clock)
    return server, generator


async def ok(client: Client, tool: str, **arguments: Any) -> dict[str, Any]:
    result = await client.call_tool(tool, arguments)
    assert not result.is_error, result.content
    assert result.structured_content is not None
    return result.structured_content


async def fails(client: Client, tool: str, **arguments: Any) -> str:
    result = await client.call_tool(tool, arguments)
    assert result.is_error, result.structured_content
    return result.content[0].text  # type: ignore[union-attr]


async def prepared_run(client: Client, photo_run) -> str:
    """A run with its photo and cited reading notes, ready for the geometry steps."""
    run = (await ok(client, "start_run", **MACHINE))["run"]
    await ok(
        client,
        "add_input",
        run=run,
        path=photo_run.photo.uri,
        source_id="src-photo",
        title="Test photo (synthetic)",
        retrieved_at="2026-10-16T12:00:00Z",
    )
    await ok(
        client,
        "add_reference_source",
        run=run,
        source_id="src-sheet",
        kind="user_input",
        uri="ignored for user input",
        title="Synthetic data sheet for the test indexer",
    )
    await ok(client, "identify_machine", run=run, **MACHINE, confidence=1.0, citations=SHEET)
    await ok(
        client,
        "add_fact",
        run=run,
        key="center_height",
        value=0.1016,
        unit="m",
        original="0.1016 m",
        confidence=1.0,
        citations=SHEET,
    )
    return run


@pytest.mark.anyio
async def test_the_tools_are_listed_with_their_schemas(setup) -> None:
    server, _ = setup
    async with Client(server) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    assert list(tools) == [
        "check_knowledge_base",
        "request_twin",
        "list_jobs",
        "start_run",
        "add_input",
        "add_reference_source",
        "identify_machine",
        "add_fact",
        "add_control",
        "add_issue",
        "generate_geometry",
        "inspect_geometry",
        "fit_circles",
        "add_joint",
        "set_scale",
        "set_spec_frame",
        "set_cut_list",
        "set_spec_part",
        "set_spec_joint",
        "remove_spec_entry",
        "set_scale_length",
        "set_size_checks",
        "preview_twin",
        "submit_twin",
    ]
    assert all(t.description and t.output_schema for t in tools.values())
    assert tools["check_knowledge_base"].annotations.read_only_hint is True  # type: ignore[union-attr]
    assert tools["list_jobs"].annotations.read_only_hint is True  # type: ignore[union-attr]
    assert tools["submit_twin"].annotations.read_only_hint is False  # type: ignore[union-attr]
    assert "citations" in tools["add_fact"].input_schema["required"]


@pytest.mark.anyio
async def test_an_agent_builds_a_twin_then_a_second_request_reuses_it(setup, photo_run) -> None:
    server, generator = setup
    async with Client(server) as client:
        empty = await ok(client, "check_knowledge_base")
        assert empty["machines"] == [] and empty["data_dir"] == str(photo_run.data_dir.resolve())

        run = await prepared_run(client, photo_run)
        await ok(
            client,
            "add_control",
            run=run,
            behavior_id="index_program",
            name="Test indexing program",
            kind="program_interpreter",
            description="Steps the spindle.",
            confidence=1.0,
            citations=SHEET,
            drives_joints=["spindle_rotation"],
            spec={"step_size_deg": [0.001, 999.999]},
        )

        generated = await ok(client, "generate_geometry", run=run)
        assert not generated["reused"] and Path(generated["views"]).is_file()
        assert generated["generator"] == "fake-generator 0" and generator.calls == 1

        inspected = await ok(client, "inspect_geometry", run=run, up="+y", front="+z")
        assert inspected["axis_yz"] == pytest.approx([0.0, 0.2], abs=1e-6)
        assert inspected["axis_height_above_lowest"] == pytest.approx(1.2, abs=1e-6)
        assert Path(inspected["views"]).is_file()

        joint = await ok(
            client,
            "add_joint",
            run=run,
            up="+y",
            front="+z",
            spindle_axis_yz=[0.0, 0.2],
            spindle_radius=0.45,
            spindle_start_x=1.0,
            method="Axis from the tip slabs; the box's front face is at x = 1.",
        )
        assert joint["parts_set"] == ["joint"] and not joint["complete"]
        scaled = await ok(client, "set_scale", run=run)
        assert scaled["complete"] and scaled["spec"]["center_height_m"] == 0.1016

        preview = (await ok(client, "preview_twin", run=run))["result"]
        assert preview["scale_m_per_unit"] == pytest.approx(SCALE)
        assert all(Path(p).is_file() for p in preview["views"].values())

        submitted = await ok(client, "submit_twin", run=run)
        assert not submitted["reused_existing"]
        assert submitted["message"].startswith(
            "No twin found for moonwalkers/testindexer; built version 1 from Pipeline B. "
            f"Exported to {run}/twin.usdc."
        )
        assert submitted["twin"]["twin_id"] == "moonwalkers/testindexer@v1"
        assert Path(submitted["twin_file"]).is_file() and len(submitted["check_files"]) == 2
        assert [i for i in submitted["validation"] if i["severity"] == "error"] == []
        assert any(i.get("ref") == "spindle" for i in submitted["issues"])

        again = await ok(client, "request_twin", **MACHINE)
        assert again["reused_existing"] and again["twin"] == submitted["twin"]
        assert again["message"].startswith(
            "Found an existing twin (v1, needs review) for moonwalkers/testindexer; reused it."
        )
        stored = await ok(client, "check_knowledge_base", **MACHINE)
        assert [v["version"] for v in stored["versions"]] == [1]
        assert stored["versions"][0]["review_status"] == "needs_review"
        assert (await ok(client, "list_jobs"))["jobs"] == []  # the built job is finished
        finished = (await ok(client, "list_jobs", include_finished=True))["jobs"]
        assert [(j["run"], j["stage"]) for j in finished] == [(run, "built")]
    assert generator.calls == 1  # the mesh was generated once


@pytest.mark.anyio
async def test_list_jobs_finds_a_waiting_job_and_says_what_comes_next(setup, photo_run) -> None:
    server, _ = setup
    async with Client(server) as client:
        assert (await ok(client, "list_jobs"))["jobs"] == []
        run = (await ok(client, "start_run", **MACHINE))["run"]
        assert (await ok(client, "list_jobs"))["jobs"][0]["next_step"].startswith("add_input")
        await ok(
            client,
            "add_input",
            run=run,
            path=photo_run.photo.uri,
            source_id="src-photo",
            title="Test photo",
        )
        listed = await ok(client, "list_jobs", machine="moonwalkers/testindexer")
        job = listed["jobs"][0]
        assert (job["run"], job["stage"], job["photo"]) == (
            run,
            "waiting_for_agent",
            photo_run.photo.uri,
        )
        assert job["next_step"].startswith("the cited reading notes")
        assert listed["note"] == "1 job(s) shown, 1 waiting for the agent."
        assert (await ok(client, "list_jobs", machine="haas-ha5c"))["jobs"] == []
        assert "not a machine folder" in await fails(client, "list_jobs", machine="Haas HA5C")


@pytest.mark.anyio
async def test_a_twin_rejected_in_review_is_not_reused(
    photo_run, fake_generator, clock, fixed_time
) -> None:
    kb = JsonKnowledgeBase(photo_run.data_dir / "kb")
    key = "moonwalkers/testindexer"
    kb.save_twin(
        TwinRecord(
            twin_id=f"{key}@v1",
            machine_key=key,
            version=1,
            status="needs_review",
            created_at=fixed_time,
        )
    )
    Orchestrator(kb, {}, clock=clock).review_twin(key, 1, "rejected", "Daniel", "Wrong split.")
    server = create_server(Workspace(photo_run.data_dir, clock), fake_generator, kb=kb, clock=clock)
    async with Client(server) as client:
        assert "was rejected in review" in await fails(client, "request_twin", **MACHINE)
        report = await ok(client, "check_knowledge_base", **MACHINE)
        assert report["versions"][0]["review_status"] == "rejected"
        assert "all rejected in review" in report["note"]
        assert (await ok(client, "start_run", **MACHINE))["existing_twin"] is None


@pytest.mark.anyio
async def test_mistakes_come_back_as_readable_tool_errors(setup, photo_run) -> None:
    server, _ = setup
    async with Client(server) as client:
        assert "No twin for moonwalkers/testindexer yet" in await fails(
            client, "request_twin", **MACHINE
        )
        assert "is not a run" in await fails(client, "generate_geometry", run="runs/x")
        run = (await ok(client, "start_run", **MACHINE))["run"]
        assert "add a reference source first" in await fails(
            client, "add_fact", run=run, key="k", value=1, confidence=1.0, citations=SHEET
        )
        assert "no photo for the generator" in await fails(client, "generate_geometry", run=run)
        assert "not inside the data folder" in await fails(
            client,
            "add_input",
            run=run,
            path=str(Path(photo_run.data_dir).parent / "elsewhere.png"),
            source_id="src-x",
            title="x",
        )
        await ok(
            client,
            "add_reference_source",
            run=run,
            source_id="src-sheet",
            kind="user_input",
            uri="user",
            title="Sheet",
        )
        stray = [{"source_id": "src-unknown"}]
        photo = [{"source_id": "src-photo"}]  # an input from add_input, not a reference source
        assert "add_reference_source too" in await fails(
            client, "add_fact", run=run, key="k", value=1, confidence=1.0, citations=photo
        )
        assert "unknown sources" in await fails(
            client, "add_fact", run=run, key="k", value=1, confidence=1.0, citations=stray
        )
        assert "record the cited fact 'center_height'" in await fails(client, "set_scale", run=run)
        assert "not complete" in await fails(client, "submit_twin", run=run)
        assert "not complete" in await fails(client, "preview_twin", run=run)


@pytest.mark.anyio
async def test_a_built_run_cannot_be_changed(setup, photo_run) -> None:
    server, _ = setup
    async with Client(server) as client:
        run = await prepared_run(client, photo_run)
        await ok(client, "generate_geometry", run=run)
        joint = {
            "up": "+y",
            "front": "+z",
            "spindle_axis_yz": [0.0, 0.2],
            "spindle_radius": 0.45,
            "spindle_start_x": 1.0,
            "method": "synthetic",
        }
        await ok(client, "add_joint", run=run, **joint)
        await ok(client, "set_scale", run=run)
        await ok(client, "submit_twin", run=run)
        assert "already built its twin" in await fails(
            client, "add_joint", run=run, **(joint | {"spindle_radius": 0.5})
        )
        assert "already built its twin" in await fails(
            client, "add_issue", run=run, severity="info", message="late note"
        )
        rebuild = (await ok(client, "start_run", **MACHINE, new_version=True))["run"]
        assert rebuild.endswith("_run-002")


@pytest.mark.anyio
async def test_when_feet_reach_past_the_spindle_circle_x_gives_the_axis(
    photo_run, rotary_table, generator_for, clock
) -> None:
    """The TH240 case on the synthetic rotary table: the tip slabs measure the feet, the warnings
    say so, the scan shows the platter, and circle_x through it gives the axis the twin uses."""
    generator = generator_for(rotary_table)
    server = create_server(Workspace(photo_run.data_dir, clock), lambda: generator, clock=clock)
    async with Client(server) as client:
        run = await prepared_run(client, photo_run)
        await ok(client, "generate_geometry", run=run)
        first = await ok(client, "inspect_geometry", run=run, up="+y", front="+z")
        assert first["axis_source"] == "tip_slabs"
        assert any("not round" in w for w in first["warnings"])
        platter_x = [f["x"] for f in first["circle_scan"] if f["round"]]
        assert platter_x and all(1.0 < x < 1.3 for x in platter_x)

        second = await ok(
            client, "inspect_geometry", run=run, up="+y", front="+z", circle_x=platter_x
        )
        assert second["axis_source"] == "circle_fits"
        assert second["axis_yz"] == pytest.approx([0.0, 0.2], abs=0.005)
        assert second["axis_height_above_lowest"] == pytest.approx(1.2, abs=0.005)

        await ok(
            client,
            "add_joint",
            run=run,
            up="+y",
            front="+z",
            spindle_axis_yz=second["axis_yz"],
            spindle_radius=0.65,
            spindle_start_x=1.01,
            method="Axis from circle fits through the platter; the feet reach past it.",
        )
        await ok(client, "set_scale", run=run)
        preview = (await ok(client, "preview_twin", run=run))["result"]
    low, high = preview["spindle_bounds_m"]
    platter = 1.2 * 0.1016 / second["axis_height_above_lowest"]  # 1.2 units across, scaled
    assert high[1] - low[1] == pytest.approx(platter, rel=0.01)  # the platter alone: no feet
    assert high[2] - low[2] == pytest.approx(platter, rel=0.01)


@pytest.mark.anyio
async def test_a_recorded_program_is_checked_and_built_into_the_run(setup, photo_run) -> None:
    """Level 3 through the tools: the agent records the manual's Example #3 as the control
    behaviour's program, and the build writes the program folder for Isaac Sim."""
    server, _ = setup
    example_3 = [[1, 90.0, 270.0, 4, 91], [2, 72.0, 270.0, 5, 91], [3, 0.0, 270.0, 1, 99]]
    control = {
        "behavior_id": "index_program",
        "name": "Manual Example #3",
        "kind": "program_interpreter",
        "description": "A four-hole pattern, then a five-hole pattern.",
        "confidence": 0.9,
        "citations": SHEET,
        "drives_joints": ["spindle_rotation"],
    }
    async with Client(server) as client:
        run = await prepared_run(client, photo_run)
        too_fast = {"program": {"rows": [[1, 90.0, 300.0, 1, 91], [2, 0.0, 270.0, 1, 99]]}}
        assert "feed rate 300.0 is outside" in await fails(
            client, "add_control", run=run, **control, spec=too_fast
        )
        await ok(client, "add_control", run=run, **control, spec={"program": {"rows": example_3}})
        await ok(client, "generate_geometry", run=run)
        joint = {
            "up": "+y",
            "front": "+z",
            "spindle_axis_yz": [0.0, 0.2],
            "spindle_radius": 0.45,
            "spindle_start_x": 1.0,
            "method": "synthetic",
        }
        await ok(client, "add_joint", run=run, **joint)
        await ok(client, "set_scale", run=run)
        await ok(client, "submit_twin", run=run)
    folder = photo_run.data_dir / run / "programs" / "index-program"
    assert (folder / "program.usdc").is_file() and (folder / "run_program.py").is_file()
    trajectory = json.loads((folder / "trajectory.json").read_text(encoding="utf-8"))
    assert trajectory["final_deg"] == pytest.approx(720.0)
    notes = (photo_run.data_dir / run / "RUN.md").read_text(encoding="utf-8")
    assert "`programs/index-program/`: Manual Example #3" in notes


@pytest.mark.anyio
async def test_without_a_generator_root_only_earlier_meshes_can_be_used(photo_run, clock) -> None:
    server = create_server(Workspace(photo_run.data_dir, clock), UnconfiguredGenerator)
    async with Client(server) as client:
        run = await prepared_run(client, photo_run)
        message = await fails(client, "generate_geometry", run=run)
    assert "not configured: set MOONWALKERS_GEN_ROOT" in message


class OwnersPipelineD(Pipeline):
    """Stands in for Sarkis's Pipeline D once it is in; add_input only checks that it is."""

    pipeline_id = PipelineId.D

    def run(self, job_id: str, sources: list[Source]) -> PipelineResult:
        raise NotImplementedError


def write_manual(photo_run) -> str:
    manual = photo_run.data_dir / "machines" / "moonwalkers-testindexer" / "inputs" / "manual.pdf"
    manual.write_bytes(b"%PDF- not really a manual")
    return manual.relative_to(photo_run.data_dir).as_posix()


@pytest.mark.anyio
async def test_a_document_is_refused_while_its_pipeline_is_not_in(setup, photo_run) -> None:
    """Pipeline D's stub would answer with the HA5C's facts, so the document is refused before
    anything is generated (decision 0021)."""
    server, _ = setup
    async with Client(server) as client:
        run = (await ok(client, "start_run", **MACHINE))["run"]
        message = await fails(
            client,
            "add_input",
            run=run,
            path=write_manual(photo_run),
            source_id="src-manual",
            title="Manual",
            input_type="pdf_catalog",
        )
    assert "Pipeline D (Sarkis Nazaryan's)" in message and "not in yet" in message
    assert "add_reference_source" in message


@pytest.mark.anyio
async def test_a_document_is_added_once_its_pipeline_is_in(
    photo_run, fake_generator, clock
) -> None:
    server = create_server(
        Workspace(photo_run.data_dir, clock),
        fake_generator,
        clock=clock,
        pipelines={PipelineId.D: OwnersPipelineD()},
    )
    async with Client(server) as client:
        run = (await ok(client, "start_run", **MACHINE))["run"]
        added = await ok(
            client,
            "add_input",
            run=run,
            path=write_manual(photo_run),
            source_id="src-manual",
            title="Manual",
            input_type="pdf_catalog",
        )
    assert added["inputs"] == ["src-manual"]
    assert added["source"]["input_type"] == "pdf_catalog"


def test_the_data_folder_comes_from_the_environment(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("MOONWALKERS_DATA_DIR", raising=False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert default_data_dir() == (tmp_path / "data").resolve()
    monkeypatch.setenv("MOONWALKERS_DATA_DIR", str(tmp_path / "elsewhere"))
    assert default_data_dir() == (tmp_path / "elsewhere").resolve()
    monkeypatch.delenv("MOONWALKERS_DATA_DIR")
    monkeypatch.delenv("CLAUDE_PROJECT_DIR")
    assert default_data_dir().name == "data" and (default_data_dir() / "README.md").is_file()


@pytest.mark.anyio
async def test_several_photos_with_their_views_through_the_tools(setup, photo_run) -> None:
    """Decision 0022: views in the operator's words, checked as each photo is added."""
    server, _ = setup
    second = Path(photo_run.photo.uri).with_name("corner.png").as_posix()
    (photo_run.data_dir / second).write_bytes(b"another corner")
    photo = {"title": "Test photo", "retrieved_at": "2026-10-16T12:00:00Z"}
    async with Client(server) as client:
        run = (await ok(client, "start_run", **MACHINE))["run"]
        added = await ok(
            client,
            "add_input",
            run=run,
            path=photo_run.photo.uri,
            source_id="src-ol",
            view="front_operator_left",
            **photo,
        )
        assert added["generator_input"] == (
            "single-image model: single = src-ol; evidence: 0 photo(s)"
        )
        assert "have no view" in await fails(
            client, "add_input", run=run, path=second, source_id="src-or", **photo
        )
        assert "machine photos only" in await fails(
            client,
            "add_input",
            run=run,
            path=second,
            source_id="src-doc",
            input_type="pdf_catalog",
            view="front",
            **photo,
        )
        added = await ok(
            client,
            "add_input",
            run=run,
            path=second,
            source_id="src-or",
            view="front_operator_right",
            **photo,
        )
        assert added["generator_input"].startswith(
            "multi-view model, corners: front = src-ol, left = src-or"
        )

        generated = await ok(client, "generate_geometry", run=run)
        assert generated["grid"] == "corners"
        assert generated["photos"] == [
            "front = src-ol (front_operator_left)",
            "left = src-or (front_operator_right)",
        ]
        assert generated["expected_turn_deg"] == 45.0
        assert generated["sides_guessed"] == ["back"]

        inspected = await ok(client, "inspect_geometry", run=run, up="+y", front="+z", yaw_deg=0.0)
        assert inspected["yaw_deg"] == 0.0
        assert abs(abs(inspected["footprint_deg"]) - 90.0) < 1.0  # the indexer is square
        jobs = await ok(client, "list_jobs")
        assert jobs["jobs"][0]["photos"] == 2
        await ok(
            client,
            "add_joint",
            run=run,
            up="+y",
            front="+z",
            spindle_axis_yz=[0.0, 0.2],
            spindle_radius=0.45,
            spindle_start_x=1.0,
            yaw_deg=45.0,
            method="Synthetic geometry; turned as corner photos would leave it.",
        )
        parts = json.loads(
            (photo_run.data_dir / run / "geometry_spec.parts.json").read_text(encoding="utf-8")
        )
        assert parts["joint"]["yaw_deg"] == 45.0


@pytest.fixture
def drill_press_server(photo_run, generator_for, clock):
    """The Phase 1 drill press as the generated mesh (decision 0028's tests)."""
    from moonwalkers.pipelines.b.synthetic_parts import drill_press

    generator = generator_for(lambda: drill_press("separate").mesh)
    return create_server(Workspace(photo_run.data_dir, clock), lambda: generator, clock=clock)


async def several_parts_run(client: Client, photo_run) -> tuple[str, dict[str, Any]]:
    """A drill press run with its photo, notes and mesh, and the spec of
    test_pipeline_b_parts_spec set through the several-part spec tools."""
    from test_pipeline_b_parts_spec import drill_press_spec

    from moonwalkers.usd import primitive_drill_press as dp

    machine = {"manufacturer": dp.MANUFACTURER, "model": dp.MODEL}
    cite = [{"source_id": dp.SYNTHETIC, "locator": "test"}]
    spec = drill_press_spec()
    run = (await ok(client, "start_run", **machine))["run"]
    await ok(
        client,
        "add_input",
        run=run,
        path=photo_run.photo.uri,
        source_id="src-photo",
        title="Test photo (synthetic)",
        retrieved_at="2026-10-16T12:00:00Z",
    )
    for source_id in (dp.SYNTHETIC, dp.MANUAL):
        await ok(
            client,
            "add_reference_source",
            run=run,
            source_id=source_id,
            kind="user_input",
            uri="user",
            title=f"Synthetic source {source_id}",
        )
    await ok(client, "identify_machine", run=run, **machine, confidence=1.0, citations=cite)
    for key, value, unit in (
        ("overall_height", dp.OVERALL_HEIGHT, "m"),
        ("column_diameter", 2 * dp.COLUMN_RADIUS, "m"),
        ("max_spindle_speed", 300.0, "rad/s"),
    ):
        await ok(
            client,
            "add_fact",
            run=run,
            key=key,
            value=value,
            unit=unit,
            original=f"{value} {unit}",
            confidence=1.0,
            citations=cite,
        )
    await ok(client, "generate_geometry", run=run)
    await ok(
        client,
        "set_spec_frame",
        run=run,
        up="+y",
        front="+z",
        origin_xy=[0.0, 0.0],
        fixed_part="frame",
        method="the Phase 1 drill press, cut by the spike's synthetic cut list",
    )
    await ok(client, "set_cut_list", run=run, cuts=spec["cuts"])
    for part in spec["parts"]:
        await ok(client, "set_spec_part", run=run, part=part)
    for joint in spec["joints"]:
        await ok(client, "set_spec_joint", run=run, joint=joint)
    await ok(client, "set_scale_length", run=run, fact="overall_height", how="the height")
    await ok(client, "set_size_checks", run=run, checks=spec["size_checks"])
    return run, spec


@pytest.mark.anyio
async def test_a_spec_of_several_parts_is_set_piece_by_piece(drill_press_server, photo_run) -> None:
    from moonwalkers.usd import primitive_drill_press as dp

    async with Client(drill_press_server) as client:
        run, spec = await several_parts_run(client, photo_run)
        status = await ok(client, "remove_spec_entry", run=run, piece="parts", entry_id="table")
        assert not status["complete"] and "table" in status["problem"]
        assert "not complete" in await fails(client, "preview_twin", run=run)
        assert "not complete" in await fails(client, "submit_twin", run=run)
        status = await ok(client, "set_spec_part", run=run, part=spec["parts"][-2])
        assert status["complete"] and status["kind"] == "parts"
        assert status["parts"]["table"] == "stand_in" and len(status["joints"]) == 8
        assert "give measured_model_units" in await fails(
            client, "set_scale_length", run=run, fact="column_diameter", how="by eye"
        )
        assert "add_fact" in await fails(
            client, "set_scale_length", run=run, fact="nothing", how="?", measured_model_units=1
        )
        assert "single spindle" in await fails(
            client,
            "add_joint",
            run=run,
            up="+y",
            front="+z",
            spindle_axis_yz=[0.0, 0.2],
            spindle_radius=0.1,
            spindle_start_x=0.0,
            method="wrong kind",
        )
        # A round part along z: the column, as decision 0024 measured the T33901's.
        circles = await ok(
            client, "fit_circles", run=run, up="+y", front="+z", along="z", at=[0.1, 0.15]
        )
    column = [f for f in circles["fits"] if f["round"]]
    assert column and all(
        f["centre"][0] == pytest.approx(dp.COLUMN_X, abs=0.003)
        and f["radius"] == pytest.approx(dp.COLUMN_RADIUS, abs=0.003)
        for f in column
    )


@pytest.mark.slow
@pytest.mark.anyio
async def test_an_agent_builds_a_twin_of_several_parts_through_the_tools(
    drill_press_server, photo_run
) -> None:
    """Previewed, patched where the preview finds holes, and built (about 90 s)."""
    async with Client(drill_press_server) as client:
        run, spec = await several_parts_run(client, photo_run)
        preview = (await ok(client, "preview_twin", run=run))["result"]
        kinds = {p["part_id"]: p["kind"] for p in preview["parts"]}
        assert kinds["table"] == "stand_in" and kinds["frame"] == "cut"
        assert preview["removed_faces"]["generated_table"] > 0
        assert {"cuts", "parts", "part_table"} <= set(preview["views"])
        # The synthetic cut list's table box takes faces of the boxes under it: holes across
        # the removed table, which patches on those parts close.
        holes = preview["holes"]
        assert holes and all(h["across"] == ["generated_table"] for h in holes)
        for part in spec["parts"]:
            mine = [h for h in holes if h["part"] == part["part_id"]]
            if mine:
                patches = [{"near": h["centre"], "note": "under the table"} for h in mine]
                await ok(client, "set_spec_part", run=run, part=dict(part, patches=patches))
        preview = (await ok(client, "preview_twin", run=run))["result"]
        assert preview["holes"] == []
        assert any(i["message"].startswith("Patched") for i in preview["issues"])
        submitted = await ok(client, "submit_twin", run=run)
    assert submitted["twin"]["version"] == 1
    assert not [i for i in submitted["validation"] if i["severity"] == "error"]
    assert any(i["message"].startswith("Stand-in: a test stand-in") for i in submitted["issues"])
