"""Input Router: each input type goes to the pipeline the README assigns it."""

from moonwalkers.contracts.pipeline_result import InputType, PipelineId
from moonwalkers.orchestrator import ROUTES, route


def test_routes_match_the_readme_table() -> None:
    # README, "The eight input types"
    assert ROUTES == {
        InputType.WALKTHROUGH_VIDEO: PipelineId.B,
        InputType.MACHINE_PHOTO: PipelineId.B,
        InputType.NAMEPLATE_PHOTO: PipelineId.A,
        InputType.BROCHURE_DATASHEET: PipelineId.A,
        InputType.LAYOUT_DRAWING: PipelineId.C,
        InputType.SCHEMATIC: PipelineId.C,
        InputType.PDF_CATALOG: PipelineId.D,
        InputType.ONLINE_RESOURCE: PipelineId.D,
    }


def test_sources_are_grouped_in_pipeline_order(make_source) -> None:
    catalog = make_source("catalog", InputType.PDF_CATALOG)
    photo1 = make_source("photo1", InputType.MACHINE_PHOTO)
    nameplate = make_source("nameplate", InputType.NAMEPLATE_PHOTO)
    photo2 = make_source("photo2", InputType.MACHINE_PHOTO)

    routed = route([catalog, photo1, nameplate, photo2])

    assert list(routed) == [PipelineId.A, PipelineId.B, PipelineId.D]
    assert routed[PipelineId.B] == [photo1, photo2]


def test_user_typed_sources_are_not_routed(make_source) -> None:
    assert route([make_source("note", None)]) == {}
