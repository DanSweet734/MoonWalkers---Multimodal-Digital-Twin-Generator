"""Which side each machine photo shows, and what it is used for (decision 0022).

A request's ``photos`` map names, for each machine photo among its sources, where the camera
stood and whether the image-to-3D generator gets the photo. Sides are named as the operator sees
the machine, facing its front, because that is what people and manuals say ("Figure 3. Right
headstock components." is the T33901's handle side). Every name with a left or right says
"operator", so it cannot be read the other way round. Only Pipeline B translates these names to
the generator's (``moonwalkers.pipelines.b.photos``).

A photo the generator gets may also say how to cut the machine out of it (``Cutout``, decision
0029): by default the generator's background removal keeps the most salient object, which in a
lab is often a sign or a box in front of the machine.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)

PhotoView = Literal[
    "front",
    "operator_right",
    "back",
    "operator_left",
    "front_operator_left",
    "front_operator_right",
    "back_operator_right",
    "back_operator_left",
    "detail",
]
PhotoUse = Literal["generator", "evidence"]

SIDE_VIEWS: tuple[PhotoView, ...] = ("front", "operator_right", "back", "operator_left")
CORNER_VIEWS: tuple[PhotoView, ...] = (
    "front_operator_left",
    "front_operator_right",
    "back_operator_right",
    "back_operator_left",
)
DETAIL: PhotoView = "detail"
VIEWS: tuple[PhotoView, ...] = get_args(PhotoView)


CutoutMethod = Literal["sam", "crop", "mask"]
Fraction = Annotated[float, Field(ge=0.0, le=1.0)]
# The SAM weights the generator job runs: rembg's quantised ViT-B (docs/setup/generators.md).
SAM_MODEL = "sam_vit_b_01ec64 (quantised, rembg 2.0.68)"


class CutoutPoint(BaseModel):
    """A point on the upright photo, as fractions of its width and height from the top left:
    ``keep`` on the machine, or not, on something to leave out (a sign in front of it)."""

    model_config = ConfigDict(extra="forbid")

    x: Fraction
    y: Fraction
    keep: bool


class Cutout(BaseModel):
    """How to cut the machine out of one photo, instead of the automatic background removal
    (decision 0029). Coordinates are fractions of the photo turned upright by its EXIF
    orientation, from the top left, so they hold at any resolution.

    - ``sam``: Segment Anything, prompted with ``box`` around the machine and optional ``points``
      to keep or leave out a region;
    - ``crop``: the automatic removal inside ``box``, everything outside it cut away;
    - ``mask``: a mask drawn by hand, ``mask`` being a PNG in the data folder (usually in the run
      folder), the photo's shape: white, or opaque, is the machine.

    Separate pieces of the cut-out smaller than ``min_piece`` times the largest piece are dropped
    (specks of the wall behind the machine); 0 keeps every piece.
    """

    model_config = ConfigDict(extra="forbid")

    method: CutoutMethod
    box: tuple[Fraction, Fraction, Fraction, Fraction] | None = None  # x0, y0, x1, y1
    points: list[CutoutPoint] = Field(default_factory=list)
    mask: str | None = None
    min_piece: Fraction = 0.02

    @model_validator(mode="after")
    def _check(self) -> Cutout:
        if self.method == "mask":
            if self.mask is None or self.box is not None or self.points:
                raise ValueError("a 'mask' cut-out gives the mask's file, and no box or points")
            if not self.mask.lower().endswith(".png"):
                raise ValueError(f"the mask {self.mask!r} must be a PNG")
            return self
        if self.mask is not None:
            raise ValueError(f"a {self.method!r} cut-out takes no mask file")
        if self.box is None:
            raise ValueError(f"a {self.method!r} cut-out needs a box around the machine")
        x0, y0, x1, y1 = self.box
        if not (x0 < x1 and y0 < y1):
            raise ValueError(f"the box {self.box} must run from its top left to its bottom right")
        if self.method == "crop" and self.points:
            raise ValueError("a 'crop' cut-out takes no points: use 'sam' to keep or drop regions")
        return self


class InputPhoto(BaseModel):
    """One machine photo's view and use. ``use`` defaults to ``generator`` for a whole-machine
    view and ``evidence`` for a ``detail``, which the generator never gets. ``cutout`` applies
    when the generator gets the photo; without it, the background is removed automatically."""

    model_config = ConfigDict(extra="forbid")

    view: PhotoView
    use: PhotoUse
    cutout: Cutout | None = None  # how the generator cuts the machine out (decision 0029)

    @model_serializer(mode="wrap")
    def _without_unset_cutout(self, handler: SerializerFunctionWrapHandler) -> Any:
        # A photo with no cut-out is written as before decision 0029.
        data = handler(self)
        if isinstance(data, dict) and data.get("cutout") is None:
            data.pop("cutout", None)
        return data

    @model_validator(mode="before")
    @classmethod
    def _default_use(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("use") is None:
            data = {**data, "use": "evidence" if data.get("view") == DETAIL else "generator"}
        return data

    @model_validator(mode="after")
    def _check(self) -> InputPhoto:
        if self.view == DETAIL and self.use == "generator":
            raise ValueError(
                "a 'detail' photo is a close-up, not a view of the whole machine: "
                "the generator cannot use it (use 'evidence')"
            )
        return self
