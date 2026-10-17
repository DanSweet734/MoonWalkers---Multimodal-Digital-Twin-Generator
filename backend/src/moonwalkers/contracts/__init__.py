"""Shared contracts between pipelines, the orchestrator, and the knowledge base."""

from .pipeline_result import (
    SCHEMA_VERSION,
    JobResult,
    PipelineResult,
    TwinRecord,
)

__all__ = ["SCHEMA_VERSION", "JobResult", "PipelineResult", "TwinRecord"]
