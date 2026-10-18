"""Read a part's mesh file (GLB or OBJ) into ``MeshData`` for the exporter (decision 0012).

Pipeline B writes part meshes already in the twin frame and in metres, so no transform or scale is
applied here.
"""

from __future__ import annotations

from pathlib import Path

import trimesh

from .geometry import MeshData

MESH_FILE_FORMATS = frozenset({"glb", "obj"})


def mesh_data_from_file(path: Path) -> MeshData:
    """The triangles of a mesh file, with scene transforms applied."""
    mesh = trimesh.load(Path(path), force="mesh")
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ValueError(f"{path} holds no triangle mesh")
    points = tuple((float(x), float(y), float(z)) for x, y, z in mesh.vertices)
    indices = tuple(int(i) for i in mesh.faces.reshape(-1))
    return MeshData(points, (3,) * len(mesh.faces), indices)
