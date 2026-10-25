"""Which of a run's machine photos feed the image-to-3D generator, in which slot (decision 0022).

The request's ``photos`` map (``moonwalkers.orchestrator.photos``) names each photo's view in the
operator's words. This module is the one place that translates them to the generator's slots,
``front``, ``left``, ``back`` and ``right``, where ``left`` is the machine's own left: the
operator's right (``docs/setup/generators.md``). The rules:

- one fed photo runs the single-image model (slot ``single``), as in the PoC;
- two to four fed photos run the multi-view model. They are all sides, or all corners, which the
  generator takes as a grid turned 45°, with the front corner on the operator's left as its front;
- a request with one machine photo and no ``photos`` entry is the PoC's: that photo is fed;
- with several machine photos, each needs a view.

``PhotoPlan`` also says which sides of the machine the fed photos show, so a result can say which
ones the generator had to guess.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from moonwalkers.contracts.pipeline_result import InputType, Issue, Source
from moonwalkers.generators.base import SINGLE_VIEW
from moonwalkers.orchestrator.photos import CORNER_VIEWS, SIDE_VIEWS, InputPhoto, PhotoView

Grid = Literal["single", "sides", "corners"]
Side = Literal["front", "operator_right", "back", "operator_left"]

SIDE_SLOTS: dict[PhotoView, str] = {
    "front": "front",
    "operator_right": "left",  # the machine's own left
    "back": "back",
    "operator_left": "right",
}
CORNER_SLOTS: dict[PhotoView, str] = {
    "front_operator_left": "front",
    "front_operator_right": "left",
    "back_operator_right": "back",
    "back_operator_left": "right",
}
# Where the machine's front is expected after orienting (+Z up, the generator's front as +X),
# measured from +X towards +Y (the generator's left). Measured on the T33901's corners: +48.5°.
EXPECTED_TURN_DEG: dict[Grid, float | None] = {"single": None, "sides": 0.0, "corners": 45.0}
# The sides of the machine each view shows: a side view one, square on; a corner two, at an angle.
SIDES_SHOWN: dict[PhotoView, tuple[Side, ...]] = {
    "front": ("front",),
    "operator_right": ("operator_right",),
    "back": ("back",),
    "operator_left": ("operator_left",),
    "front_operator_left": ("front", "operator_left"),
    "front_operator_right": ("front", "operator_right"),
    "back_operator_right": ("back", "operator_right"),
    "back_operator_left": ("back", "operator_left"),
}
SIDE_NAMES: dict[Side, str] = {
    "front": "the front",
    "operator_right": "the operator's right",
    "back": "the back",
    "operator_left": "the operator's left",
}
ALL_SIDES: tuple[Side, ...] = ("front", "operator_right", "back", "operator_left")
POC_GUESS = (
    "Made from one photo: the generator guessed every surface the photo does not show (the back, "
    "the underside and the far side)."
)


class PhotoPlanError(ValueError):
    """The run's photos cannot be fed to the generator as they are."""


@dataclass(frozen=True)
class FedPhoto:
    slot: str  # the generator's name: single, front, left, back or right
    source: Source
    view: PhotoView | None  # None: a PoC request's one photo, given no view


@dataclass(frozen=True)
class PhotoPlan:
    grid: Grid
    fed: tuple[FedPhoto, ...]
    evidence: tuple[tuple[Source, PhotoView], ...]  # machine photos the generator does not get

    @property
    def expected_turn_deg(self) -> float | None:
        return EXPECTED_TURN_DEG[self.grid]

    def images(self, paths: Mapping[str, Path]) -> dict[str, Path]:
        """The generator's images by slot, from each photo's file by source id."""
        return {f.slot: paths[f.source.source_id] for f in self.fed}

    def sides(self) -> tuple[list[Side], list[Side], list[Side]] | None:
        """The machine's sides seen square on, seen only at an angle, and not seen (guessed);
        None when the one photo has no view."""
        if any(f.view is None for f in self.fed):
            return None
        square = {s for f in self.fed if f.view in SIDE_VIEWS for s in SIDES_SHOWN[f.view]}
        angled = {s for f in self.fed if f.view in CORNER_VIEWS for s in SIDES_SHOWN[f.view]}
        return (
            [s for s in ALL_SIDES if s in square],
            [s for s in ALL_SIDES if s in angled - square],
            [s for s in ALL_SIDES if s not in square | angled],
        )

    def record(self) -> dict[str, object]:
        """What the generator record keeps about the photos, besides their SHA-256 key."""
        return {
            "grid": self.grid,
            "expected_turn_deg": self.expected_turn_deg,
            "fed": [
                {"slot": f.slot, "source_id": f.source.source_id, "view": f.view} for f in self.fed
            ],
            "evidence": [{"source_id": s.source_id, "view": v} for s, v in self.evidence],
        }


def plan_photos(sources: Sequence[Source], photos: Mapping[str, InputPhoto]) -> PhotoPlan:
    """The generator's input for a run: raises ``PhotoPlanError`` with what to change."""
    plan = check_photos(sources, photos)
    if plan is None:
        raise PhotoPlanError(
            "no photo for the generator: add a machine photo of the whole machine with use "
            "'generator' (decision 0022)"
        )
    return plan


def check_photos(sources: Sequence[Source], photos: Mapping[str, InputPhoto]) -> PhotoPlan | None:
    """``plan_photos``, except that a run with no photo for the generator yet is allowed (None):
    for checking each photo as it is added."""
    machine = [s for s in sources if s.input_type == InputType.MACHINE_PHOTO]
    if len(machine) == 1 and machine[0].source_id not in photos:
        return PhotoPlan("single", (FedPhoto(SINGLE_VIEW, machine[0], None),), ())
    missing = [s.source_id for s in machine if s.source_id not in photos]
    if missing:
        raise PhotoPlanError(
            f"photo(s) {missing} have no view: with several machine photos, each needs one "
            "(front, back, operator_left, operator_right, a corner, or detail; decision 0022)"
        )
    fed = [(s, photos[s.source_id].view) for s in machine if photos[s.source_id].use == "generator"]
    evidence = tuple(
        (s, photos[s.source_id].view) for s in machine if photos[s.source_id].use == "evidence"
    )
    seen: dict[PhotoView, str] = {}
    for source, view in fed:
        if view in seen:
            raise PhotoPlanError(
                f"photos {seen[view]!r} and {source.source_id!r} both show {view!r}: the "
                "generator takes one image per view, so mark one of them use 'evidence'"
            )
        seen[view] = source.source_id
    kinds = {"corners" if v in CORNER_VIEWS else "sides" for _, v in fed}
    if len(kinds) > 1:
        raise PhotoPlanError(
            f"the photos for the generator mix sides and corners ({sorted(seen)}): its views are "
            "90° apart, so feed sides only or corners only, and mark the others use 'evidence'"
        )
    if not fed:
        return None
    if len(fed) == 1:
        source, view = fed[0]
        return PhotoPlan("single", (FedPhoto(SINGLE_VIEW, source, view),), evidence)
    grid: Grid = "corners" if kinds == {"corners"} else "sides"
    slots = CORNER_SLOTS if grid == "corners" else SIDE_SLOTS
    return PhotoPlan(grid, tuple(FedPhoto(slots[v], s, v) for s, v in fed), evidence)


def photo_issues(plan: PhotoPlan) -> list[Issue]:
    """What a result tells its reviewer about the photos: which sides the generator had to guess,
    and which photos it did not get."""
    sides = plan.sides()
    if sides is None:
        issues = [Issue(severity="info", message=POC_GUESS)]
    else:
        square, angled, guessed = sides
        model = "the single-image model" if plan.grid == "single" else "the multi-view model"
        fed = ", ".join(f"{f.slot} = {f.source.source_id} ({f.view})" for f in plan.fed)
        message = (
            f"Made from {len(plan.fed)} photo(s) with {model}: {fed}. "
            f"Seen square on: {_names(square)}. Seen only at an angle, from a corner: "
            f"{_names(angled)}. Guessed by the generator: {_names(guessed)}. No view is from "
            "above or below, so the top and the underside are at most seen at a glancing angle."
        )
        issues = [Issue(severity="warning" if guessed else "info", message=message)]
    if plan.evidence:
        listed = ", ".join(f"{s.source_id} ({v})" for s, v in plan.evidence)
        issues.append(
            Issue(
                severity="info",
                message=f"Evidence photos, which the generator did not get: {listed}.",
            )
        )
    return issues


def _names(sides: Sequence[Side]) -> str:
    return ", ".join(SIDE_NAMES[s] for s in sides) or "none"
