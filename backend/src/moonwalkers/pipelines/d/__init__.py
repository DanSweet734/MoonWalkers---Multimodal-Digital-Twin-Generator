"""Pipeline D: catalog resources (owner: Sarkis Nazaryan).

Octopart online resources return cited component metadata. PDF catalog files return their
labelled values and part-number candidates, cited to the page (decision 0034).
The HA5C fixture remains available through ``stub_pipelines()`` for platform tests only.
"""

from ..base import Pipeline
from .pipeline import CatalogPipeline


def create_pipeline() -> Pipeline:
    return CatalogPipeline()


__all__ = ["CatalogPipeline", "create_pipeline"]
