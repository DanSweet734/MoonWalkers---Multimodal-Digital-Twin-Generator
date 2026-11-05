"""Pipeline D: catalog resources (owner: Sarkis Nazaryan).

Octopart online resources return cited component metadata. PDF catalogs are not implemented.
The HA5C fixture remains available through ``stub_pipelines()`` for platform tests only.
"""

from ..base import Pipeline
from .pipeline import CatalogPipeline


def create_pipeline() -> Pipeline:
    return CatalogPipeline()


__all__ = ["CatalogPipeline", "create_pipeline"]
