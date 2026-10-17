"""Input Router: sends each input to the pipeline for its type (README, "The eight input types")."""

from __future__ import annotations

from collections.abc import Sequence

from moonwalkers.contracts.pipeline_result import InputType, PipelineId, Source

ROUTES: dict[InputType, PipelineId] = {
    InputType.WALKTHROUGH_VIDEO: PipelineId.B,
    InputType.MACHINE_PHOTO: PipelineId.B,
    InputType.NAMEPLATE_PHOTO: PipelineId.A,
    InputType.BROCHURE_DATASHEET: PipelineId.A,
    InputType.LAYOUT_DRAWING: PipelineId.C,
    InputType.SCHEMATIC: PipelineId.C,
    InputType.PDF_CATALOG: PipelineId.D,
    InputType.ONLINE_RESOURCE: PipelineId.D,
}


def route(sources: Sequence[Source]) -> dict[PipelineId, list[Source]]:
    """Group sources by the pipeline that handles their input type, in pipeline order (A-D).

    Sources without an input type (things the user typed) are not routed.
    """
    grouped: dict[PipelineId, list[Source]] = {}
    for source in sources:
        if source.input_type is not None:
            grouped.setdefault(ROUTES[source.input_type], []).append(source)
    return {pid: grouped[pid] for pid in PipelineId if pid in grouped}
