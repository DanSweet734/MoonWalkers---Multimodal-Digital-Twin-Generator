"""Unit conversion at the USD boundary."""

import math

from moonwalkers.usd.units import usd_angle, usd_length


def test_angles_become_degrees() -> None:
    assert usd_angle(math.pi) == 180.0
    assert math.isclose(usd_angle(-math.pi / 2), -90.0)


def test_ha5c_max_speed_round_trips() -> None:
    # 410 deg/s is stored in the fixtures as 7.156 rad/s (rounded), so it comes back within 0.01.
    assert math.isclose(usd_angle(7.156), 410.0, abs_tol=0.01)


def test_lengths_stay_in_metres() -> None:
    assert usd_length(0.1016) == 0.1016
