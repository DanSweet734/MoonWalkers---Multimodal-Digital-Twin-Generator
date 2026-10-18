"""What the API returns and accepts (decision 0014).

The dashboard's TypeScript types are generated from these through the OpenAPI schema
(``moonwalkers.api.typescript``), so a change here shows up in ``types.gen.ts`` once regenerated.
Contract models (``TwinRecord``, ``PipelineResult``, ``Source``) are returned as they are stored.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from moonwalkers.contracts.pipeline_result import PipelineResult, Source, TwinRecord
from moonwalkers.kb.reviews import Reason, ReviewDecision, Reviewer, ReviewStatus, TwinReview
from moonwalkers.pipelines.b.pipeline import ReferenceFacts
from moonwalkers.workspace import RunFile, RunStatus


class ApiStatus(BaseModel):
    version: str = Field(description="the moonwalkers package version")
    data_dir: str
    machines: int = Field(description="machines with at least one twin version")
    twin_versions: int
    open_jobs: int = Field(description="jobs not built or reused yet")


class JobDetail(BaseModel):
    job: RunStatus
    notes: ReferenceFacts | None = Field(description="the agent's cited reading notes so far")
    images: list[RunFile]
    outputs: list[RunFile]
    agent_prompt: str | None = Field(
        description="what to ask Claude Code to build this job, while it is open"
    )


class TwinVersion(BaseModel):
    twin: TwinRecord
    review_status: ReviewStatus = Field(description="latest review decision, or stored status")
    latest_review: TwinReview | None
    reusable: bool = Field(description="a request for this machine would reuse this version now")
    run: str | None = Field(description="the run folder that holds its files")


class MachineTwins(BaseModel):
    machine_key: str
    reusable_version: int | None = Field(description="the version a request would reuse")
    versions: list[TwinVersion] = Field(description="newest first")


class CitationUse(BaseModel):
    item: str = Field(description='what cites the source, for example "fact center_height"')
    locator: str | None
    quote: str | None


class SourceUse(BaseModel):
    source: Source
    cited_by: list[CitationUse]
    local_file: str | None = Field(description="a copy in the data folder that the API serves")


class TwinDetail(BaseModel):
    version: TwinVersion
    reviews: list[TwinReview] = Field(description="oldest first")
    results: list[PipelineResult]
    sources: list[SourceUse]
    images: list[RunFile]
    outputs: list[RunFile]


class ReviewRequest(BaseModel):
    decision: ReviewDecision
    reviewer: Reviewer
    reason: Reason


class SourceListing(BaseModel):
    source: Source = Field(description="as the newest twin citing it recorded it")
    source_ids: list[str] = Field(description="the ids the twins gave it")
    twins: list[str] = Field(description="twin ids that cite it, oldest first")
    local_file: str | None = Field(description="a copy in the data folder that the API serves")
