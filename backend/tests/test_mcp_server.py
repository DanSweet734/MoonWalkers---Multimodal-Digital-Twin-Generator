"""The MCP server, driven through an in-memory MCP client as an agent would drive it.

The synthetic indexer stands in for the HA5C (conftest): the fake generator writes it with +Y up
and its spindle nose facing +Z; the spindle axis is at y = 0, z = 0.2 above a base at z = -1, and
the box's front face is at x = 1.
"""

from pathlib import Path
from typing import Any

import pytest
from mcp import Client

from moonwalkers.mcp import Workspace, create_server, default_data_dir
from moonwalkers.mcp.server import UnconfiguredGenerator

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
        "start_run",
        "add_input",
        "add_reference_source",
        "identify_machine",
        "add_fact",
        "add_control",
        "add_issue",
        "generate_geometry",
        "inspect_geometry",
        "add_joint",
        "set_scale",
        "preview_twin",
        "submit_twin",
    ]
    assert all(t.description and t.output_schema for t in tools.values())
    assert tools["check_knowledge_base"].annotations.read_only_hint is True  # type: ignore[union-attr]
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

        preview = await ok(client, "preview_twin", run=run)
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
    assert generator.calls == 1  # the mesh was generated once


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
        assert "exactly one machine photo" in await fails(client, "generate_geometry", run=run)
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
async def test_without_a_generator_root_only_earlier_meshes_can_be_used(photo_run, clock) -> None:
    server = create_server(Workspace(photo_run.data_dir, clock), UnconfiguredGenerator)
    async with Client(server) as client:
        run = await prepared_run(client, photo_run)
        message = await fails(client, "generate_geometry", run=run)
    assert "not configured: set MOONWALKERS_GEN_ROOT" in message


def test_the_data_folder_comes_from_the_environment(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("MOONWALKERS_DATA_DIR", raising=False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert default_data_dir() == (tmp_path / "data").resolve()
    monkeypatch.setenv("MOONWALKERS_DATA_DIR", str(tmp_path / "elsewhere"))
    assert default_data_dir() == (tmp_path / "elsewhere").resolve()
    monkeypatch.delenv("MOONWALKERS_DATA_DIR")
    monkeypatch.delenv("CLAUDE_PROJECT_DIR")
    assert default_data_dir().name == "data" and (default_data_dir() / "README.md").is_file()
