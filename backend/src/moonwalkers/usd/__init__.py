"""OpenUSD export of twins (decision 0010).

Modules:

* ``units`` - unit conversion at the USD boundary (contract SI; UsdPhysics angles in degrees)
* ``frames`` - vector and quaternion helpers for joint frames
* ``geometry`` - meshes for primitive parts (box, cylinder)

These three are pure Python. The exporter and validator, which need ``pxr`` (usd-core), are imported
from their own modules so the helpers stay usable without it.
"""
