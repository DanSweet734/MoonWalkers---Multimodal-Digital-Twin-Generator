"""Image-to-3D generator adapters (decisions 0006 and 0011).

Each generator runs in its own Python environment, outside the backend, and is called as a
subprocess: the backend writes a JSON job, the generator's Python runs a job script from
``generators/scripts/``, and the script writes a mesh plus a JSON result. Generator dependencies
therefore never mix with the backend's.
"""
