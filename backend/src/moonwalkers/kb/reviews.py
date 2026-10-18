"""Reviews of twin versions: a person approves or rejects one, with a reason (decision 0015).

A review is a record of its own, never an edit of the twin. The stored ``TwinRecord`` keeps the
status it was built with (``needs_review``), and each review is added beside it, so every decision
stays on record (docs/methodology.md, "Human review"). A version's review status is its latest
review's decision: a later review can reverse an earlier one.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from moonwalkers.contracts.pipeline_result import TwinRecord

from .keys import validate_machine_key

ReviewDecision = Literal["approved", "rejected"]
ReviewStatus = Literal["draft", "needs_review", "approved", "rejected"]
Reviewer = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class TwinReview(BaseModel):
    """One person's decision on one twin version."""

    model_config = ConfigDict(extra="forbid")

    machine_key: str
    version: int = Field(ge=1)
    number: int = Field(ge=1, description="1 for a version's first review, then 2, 3, ...")
    decision: ReviewDecision
    reviewer: Reviewer = Field(description="who reviewed it, by name")
    reason: Reason = Field(description="why: what was checked and what was seen")
    reviewed_at: datetime

    @field_validator("machine_key")
    @classmethod
    def _key(cls, key: str) -> str:
        return validate_machine_key(key)

    @property
    def twin_id(self) -> str:
        return f"{self.machine_key}@v{self.version}"


def review_status(twin: TwinRecord, reviews: Sequence[TwinReview]) -> ReviewStatus:
    """The latest review's decision, or the status the twin was stored with."""
    return reviews[-1].decision if reviews else twin.status
