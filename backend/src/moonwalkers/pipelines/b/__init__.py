"""Pipeline B: walkthrough video + machine/component photos (owner: Daniel Sweet).

PoC (decision 0012): one machine photo becomes a scaled body and spindle on a revolute joint.
``PipelineB`` needs an image-to-3D generator (``moonwalkers.generators``) and a run folder; the
command line is ``python -m moonwalkers.pipelines.b`` (``build`` and ``inspect``, see ``cli``).
``haas_ha5c.reference.json`` holds what the agent read about the HA5C in Haas documents, with
citations; in Phase 4 the agent gathers these through MCP tools instead.
"""

from pathlib import Path

from .pipeline import (
    GeometrySpecMissing,
    PipelineB,
    ReferenceFacts,
    RunFolderConflict,
    load_reference,
)

HA5C_REFERENCE = Path(__file__).with_name("haas_ha5c.reference.json")

__all__ = [
    "HA5C_REFERENCE",
    "GeometrySpecMissing",
    "PipelineB",
    "ReferenceFacts",
    "RunFolderConflict",
    "load_reference",
]
