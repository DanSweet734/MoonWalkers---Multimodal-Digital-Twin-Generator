"""Pipeline C: layout drawings + schematics (owner: Shankar Kiran Ragavender).

PoC stub (decision 0002): returns the fixture in ``haas_ha5c.stub.json``. To build the real
pipeline, make ``create_pipeline`` return it; nothing else in the platform has to change.
"""

from pathlib import Path

from moonwalkers.contracts.pipeline_result import PipelineId

from ..base import Pipeline
from ..fixture_stub import FixturePipeline


def create_pipeline() -> Pipeline:
    return FixturePipeline(PipelineId.C, Path(__file__).with_name("haas_ha5c.stub.json"))
