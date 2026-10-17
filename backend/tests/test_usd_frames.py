"""Quaternion helpers used to orient joint frames and primitives."""

import math

import pytest

from moonwalkers.usd.frames import IDENTITY, normalize, quat_between, rotate


def close(a, b, tol: float = 1e-9) -> bool:
    return all(math.isclose(x, y, abs_tol=tol) for x, y in zip(a, b, strict=True))


@pytest.mark.parametrize(
    "target",
    [(1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1), (-1, 0, 0), (1, 1, 0), (0.2, -0.5, 3.0)],
)
@pytest.mark.parametrize("start", [(1, 0, 0), (0, 0, 1), (0, -2, 0)])
def test_quat_between_turns_start_onto_target(start, target) -> None:
    q = quat_between(start, target)
    assert math.isclose(sum(c * c for c in q), 1.0)  # unit quaternion
    assert close(rotate(q, normalize(start)), normalize(target))


def test_same_direction_is_identity() -> None:
    assert quat_between((2, 0, 0), (1, 0, 0)) == IDENTITY


def test_rotate_by_identity_changes_nothing() -> None:
    assert rotate(IDENTITY, (0.1, -0.2, 0.3)) == (0.1, -0.2, 0.3)


def test_quarter_turn_about_z() -> None:
    q = quat_between((1, 0, 0), (0, 1, 0))  # 90 degrees about +z
    assert close(q, (math.cos(math.pi / 4), 0.0, 0.0, math.sin(math.pi / 4)))
    assert close(rotate(q, (0, 1, 0)), (-1, 0, 0))


def test_zero_vector_is_rejected() -> None:
    with pytest.raises(ValueError, match="zero-length"):
        quat_between((0, 0, 0), (1, 0, 0))
