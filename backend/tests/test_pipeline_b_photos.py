"""Several photos per run (decision 0022): views, uses, and which photos feed the generator."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from moonwalkers.contracts.pipeline_result import InputType, Source
from moonwalkers.orchestrator import InputPhoto, JobRequest
from moonwalkers.pipelines.b.photos import (
    POC_GUESS,
    PhotoPlanError,
    check_photos,
    photo_issues,
    plan_photos,
)

WHEN = datetime(2026, 10, 24, tzinfo=UTC)


def photo(source_id: str, input_type: InputType = InputType.MACHINE_PHOTO) -> Source:
    return Source(
        source_id=source_id,
        kind="file",
        input_type=input_type,
        uri=f"machines/x/inputs/photos/{source_id}.png",
        retrieved_at=WHEN,
    )


def views(**given: str) -> dict[str, InputPhoto]:
    """``views(a="front", b="detail")``; a value "view:use" sets the use too."""
    out = {}
    for source_id, text in given.items():
        view, _, use = text.partition(":")
        out[source_id] = InputPhoto.model_validate({"view": view, "use": use or None})
    return out


# ------------------------------------------------------------------------------- InputPhoto
def test_use_defaults_to_generator_for_a_whole_view_and_evidence_for_a_detail() -> None:
    assert InputPhoto(view="front").use == "generator"  # type: ignore[call-arg]
    assert InputPhoto(view="detail").use == "evidence"  # type: ignore[call-arg]
    assert InputPhoto(view="back", use="evidence").use == "evidence"


def test_a_detail_cannot_feed_the_generator() -> None:
    with pytest.raises(ValidationError, match="close-up"):
        InputPhoto(view="detail", use="generator")


def test_views_are_the_operators_words_only() -> None:
    with pytest.raises(ValidationError):
        InputPhoto.model_validate({"view": "left"})  # whose left? refused


# -------------------------------------------------------------------------------- JobRequest
def test_a_poc_request_without_photos_is_still_valid() -> None:
    request = JobRequest.model_validate({"job_id": "j", "sources": [photo("a").model_dump()]})
    assert request.photos == {}


def test_the_photos_map_names_only_machine_photos_of_the_request() -> None:
    sources = [photo("a"), photo("doc", InputType.PDF_CATALOG)]
    with pytest.raises(ValidationError, match="not machine photos"):
        JobRequest(job_id="j", sources=sources, photos=views(doc="front"))
    with pytest.raises(ValidationError, match="not machine photos"):
        JobRequest(job_id="j", sources=sources, photos=views(missing="front"))


# ------------------------------------------------------------------------------------- plans
def test_one_photo_without_a_view_is_the_pocs_single_image_run() -> None:
    plan = plan_photos([photo("a")], {})
    assert plan.grid == "single"
    assert [(f.slot, f.source.source_id, f.view) for f in plan.fed] == [("single", "a", None)]
    assert plan.expected_turn_deg is None
    assert plan.sides() is None
    assert [i.message for i in photo_issues(plan)] == [POC_GUESS]


def test_sides_take_the_generators_slots_with_its_left_as_the_operators_right() -> None:
    plan = plan_photos(
        [photo("f"), photo("r"), photo("b")],
        views(f="front", r="operator_right", b="back"),
    )
    assert plan.grid == "sides"
    assert {f.slot: f.source.source_id for f in plan.fed} == {
        "front": "f",
        "left": "r",
        "back": "b",
    }
    assert plan.expected_turn_deg == 0.0
    assert plan.sides() == (["front", "operator_right", "back"], [], ["operator_left"])


def test_corners_are_a_grid_turned_45_degrees() -> None:
    plan = plan_photos(
        [photo("ol"), photo("or"), photo("table")],
        views(ol="front_operator_left", **{"or": "front_operator_right"}, table="detail"),
    )
    assert plan.grid == "corners"
    assert {f.slot: f.source.source_id for f in plan.fed} == {"front": "ol", "left": "or"}
    assert plan.expected_turn_deg == 45.0
    assert [(s.source_id, v) for s, v in plan.evidence] == [("table", "detail")]
    assert plan.sides() == ([], ["front", "operator_right", "operator_left"], ["back"])
    coverage, evidence = photo_issues(plan)
    assert coverage.severity == "warning"  # the back is a guess
    assert "Guessed by the generator: the back." in coverage.message
    assert "front = ol (front_operator_left), left = or (front_operator_right)" in coverage.message
    assert evidence.message == "Evidence photos, which the generator did not get: table (detail)."


def test_one_fed_photo_with_evidence_runs_the_single_image_model() -> None:
    plan = plan_photos([photo("a"), photo("b")], views(a="front_operator_left", b="detail"))
    assert plan.grid == "single"
    assert [f.slot for f in plan.fed] == ["single"]
    assert plan.sides() == ([], ["front", "operator_left"], ["operator_right", "back"])


def test_several_photos_each_need_a_view() -> None:
    with pytest.raises(PhotoPlanError, match=r"\['b'\] have no view"):
        plan_photos([photo("a"), photo("b")], views(a="front"))


def test_two_photos_of_one_view_cannot_both_feed_the_generator() -> None:
    with pytest.raises(PhotoPlanError, match="both show 'front'.*evidence"):
        plan_photos([photo("a"), photo("b")], views(a="front", b="front"))
    plan = plan_photos([photo("a"), photo("b")], views(a="front", b="front:evidence"))
    assert [f.source.source_id for f in plan.fed] == ["a"]


def test_sides_and_corners_do_not_mix() -> None:
    with pytest.raises(PhotoPlanError, match="mix sides and corners"):
        plan_photos([photo("a"), photo("b")], views(a="front", b="front_operator_right"))


def test_a_run_may_wait_for_its_generator_photo_but_cannot_generate_without_one() -> None:
    sources, given = [photo("a")], views(a="detail")
    assert check_photos(sources, given) is None
    with pytest.raises(PhotoPlanError, match="no photo for the generator"):
        plan_photos(sources, given)
    with pytest.raises(PhotoPlanError, match="no photo for the generator"):
        plan_photos([], {})


def test_the_record_names_each_slot_and_the_evidence() -> None:
    plan = plan_photos(
        [photo("ol"), photo("or"), photo("t")],
        views(ol="front_operator_left", **{"or": "front_operator_right"}, t="detail"),
    )
    assert plan.record() == {
        "grid": "corners",
        "expected_turn_deg": 45.0,
        "fed": [
            {"slot": "front", "source_id": "ol", "view": "front_operator_left"},
            {"slot": "left", "source_id": "or", "view": "front_operator_right"},
        ],
        "evidence": [{"source_id": "t", "view": "detail"}],
    }
