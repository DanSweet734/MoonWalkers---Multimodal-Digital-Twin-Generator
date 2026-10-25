"""Which side each machine photo shows, and what it is used for (decision 0022).

A request's ``photos`` map names, for each machine photo among its sources, where the camera
stood and whether the image-to-3D generator gets the photo. Sides are named as the operator sees
the machine, facing its front, because that is what people and manuals say ("Figure 3. Right
headstock components." is the T33901's handle side). Every name with a left or right says
"operator", so it cannot be read the other way round. Only Pipeline B translates these names to
the generator's (``moonwalkers.pipelines.b.photos``).
"""

from __future__ import annotations

from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, model_validator

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


class InputPhoto(BaseModel):
    """One machine photo's view and use. ``use`` defaults to ``generator`` for a whole-machine
    view and ``evidence`` for a ``detail``, which the generator never gets."""

    model_config = ConfigDict(extra="forbid")

    view: PhotoView
    use: PhotoUse

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
