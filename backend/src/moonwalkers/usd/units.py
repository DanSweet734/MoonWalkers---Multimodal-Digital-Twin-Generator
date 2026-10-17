"""Unit conversion at the USD export boundary.

The contract is SI (metres, radians, seconds, kilograms; CLAUDE.md) and is converted only here.
UsdPhysics "adopts degrees as the standard angular unit" (https://openusd.org/release/api/
usd_physics_page_front.html), so angles and angular speeds become degrees. The exported stage uses
``metersPerUnit = 1`` and ``kilogramsPerUnit = 1`` (Isaac Sim's defaults are metres and kilograms:
https://docs.isaacsim.omniverse.nvidia.com/6.2.0/reference_material/reference_conventions.html), so
lengths and masses pass through unchanged.
"""

from __future__ import annotations

import math

METERS_PER_UNIT = 1.0
KILOGRAMS_PER_UNIT = 1.0


def usd_angle(radians: float) -> float:
    """An angle (rad) or angular speed (rad/s) in UsdPhysics units (degrees, degrees/s)."""
    return math.degrees(radians)


def usd_length(meters: float) -> float:
    """A length in stage units."""
    return meters / METERS_PER_UNIT
