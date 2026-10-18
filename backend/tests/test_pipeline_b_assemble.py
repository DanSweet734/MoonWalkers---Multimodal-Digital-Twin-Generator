"""Pipeline B assembly: orient, split and scale a generated mesh using a geometry spec."""

import math
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from moonwalkers.pipelines.b.assemble import GeometrySpec, assemble
from moonwalkers.pipelines.b.mesh_tools import load_mesh, orientation_matrix, transformed


@pytest.fixture
def generated(tmp_path: Path, indexer) -> Path:
    """The synthetic indexer stored like a glTF generator output (+Y up, front facing +Z)."""
    path = tmp_path / "mesh.glb"
    transformed(indexer(), np.linalg.inv(orientation_matrix(up="+y", front="+z"))).export(path)
    return path


def spec(**changes) -> GeometrySpec:
    values = {
        "up": "+y",
        "front": "+z",
        "spindle_axis_yz": (0.0, 0.2),  # indexer(): spindle axis at y=0, z=0.2, base at z=-1
        "spindle_radius": 0.45,
        "spindle_start_x": 1.0,
        "center_height_m": 0.1016,
        "decided_by": "test",
        "method": "synthetic",
    }
    return GeometrySpec(**(values | changes))


def test_assemble_scales_from_the_centre_height(generated: Path, tmp_path: Path) -> None:
    parts = assemble(generated, spec(), tmp_path / "parts")
    assert math.isclose(parts.center_height_model, 1.2)  # z = 0.2 above base z = -1
    assert math.isclose(parts.scale_factor, 0.1016 / 1.2)
    assert parts.joint_origin_m == (0.0, 0.0, 0.1016)
    body, spindle = load_mesh(parts.body_path), load_mesh(parts.spindle_path)
    s = parts.scale_factor
    assert np.allclose(body.bounds, [[-2 * s, -1.5 * s, 0], [0, 1.5 * s, 2 * s]], atol=1e-6)
    # the spindle starts at the joint (x = 0) and is centred on the axis line y = 0, z = 0.1016
    assert np.allclose(spindle.bounds[0], [0, -0.4 * s, 0.1016 - 0.4 * s], atol=1e-6)
    assert math.isclose(spindle.bounds[1][0], 0.6 * s, abs_tol=1e-6)
    assert np.allclose(parts.overall_extents_m, [2.6 * s, 3 * s, 2 * s], atol=1e-6)


def test_assemble_uses_an_explicit_base_plane(generated: Path, tmp_path: Path) -> None:
    parts = assemble(generated, spec(base_z=-0.8), tmp_path / "parts")
    assert math.isclose(parts.center_height_model, 1.0)


def test_axis_below_the_base_is_refused(generated: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="above the base"):
        assemble(generated, spec(base_z=0.5), tmp_path / "parts")


def test_spec_rejects_unknown_fields_and_axes() -> None:
    with pytest.raises(ValidationError):
        spec(up="up")
    with pytest.raises(ValidationError):
        GeometrySpec.model_validate(spec().model_dump() | {"colour": "red"})


def test_same_geometry_gives_the_same_part_files(indexer, tmp_path: Path) -> None:
    # The generator names its mesh after a temporary file, so two runs differ only in that name.
    to_gltf = np.linalg.inv(orientation_matrix(up="+y", front="+z"))
    files = []
    for run in ("run-a", "run-b"):
        mesh = transformed(indexer(), to_gltf)
        mesh.metadata["name"] = f"tmp-{run}.ply"
        source = tmp_path / run / "mesh.glb"
        source.parent.mkdir()
        mesh.export(source)
        parts = assemble(source, spec(), tmp_path / run / "parts")
        files.append((parts.body_path.read_bytes(), parts.spindle_path.read_bytes()))
    assert files[0] == files[1]
    assert b"tmp-run" not in files[0][0] and b'"name":"body"' in files[0][0]
