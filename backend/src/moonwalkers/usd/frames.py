"""Vector and quaternion helpers for joint frames and primitive placement (pure Python).

Quaternions are ``(w, x, y, z)``, the component order USD uses
(https://docs.isaacsim.omniverse.nvidia.com/6.2.0/reference_material/reference_conventions.html).
"""

from __future__ import annotations

import math

Vec3 = tuple[float, float, float]
Quat = tuple[float, float, float, float]

IDENTITY: Quat = (1.0, 0.0, 0.0, 0.0)

_PARALLEL = 1.0 - 1e-12


def dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def normalize(v: Vec3) -> Vec3:
    length = math.sqrt(dot(v, v))
    if length < 1e-12:
        raise ValueError(f"cannot normalise the zero-length vector {v}")
    return (v[0] / length, v[1] / length, v[2] / length)


def quat_between(a: Vec3, b: Vec3) -> Quat:
    """The shortest rotation that turns direction ``a`` into direction ``b``."""
    a, b = normalize(a), normalize(b)
    d = dot(a, b)
    if d > _PARALLEL:
        return IDENTITY
    if d < -_PARALLEL:  # opposite directions: half a turn about any axis perpendicular to a
        axis = cross(a, (1.0, 0.0, 0.0))
        if dot(axis, axis) < 1e-12:
            axis = cross(a, (0.0, 1.0, 0.0))
        x, y, z = normalize(axis)
        return (0.0, x, y, z)
    c = cross(a, b)
    w, x, y, z = 1.0 + d, c[0], c[1], c[2]
    n = math.sqrt(w * w + x * x + y * y + z * z)
    return (w / n, x / n, y / n, z / n)


def rotate(q: Quat, v: Vec3) -> Vec3:
    """Apply the unit quaternion ``q`` to the vector ``v``."""
    w, u = q[0], (q[1], q[2], q[3])
    t = cross(u, v)
    t = (2.0 * t[0], 2.0 * t[1], 2.0 * t[2])
    s = cross(u, t)
    return (v[0] + w * t[0] + s[0], v[1] + w * t[1] + s[1], v[2] + w * t[2] + s[2])
