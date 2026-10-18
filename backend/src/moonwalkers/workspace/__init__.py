"""The data folder as the platform's shared workspace (decisions 0013, 0014).

The agent's MCP tools and the API read and write the same files, laid out as data/README.md says:

- ``runs``: run folders, their job requests, reading notes and geometry spec (``Workspace``);
- ``status``: how far each run folder's job has got;
- ``files``: the images and output files in a run folder;
- ``inputs``: photos uploaded through the dashboard, saved with a ``SOURCES.md`` line.
"""

from .files import RunFile, run_images, run_outputs
from .inputs import SavedPhoto, UnsupportedPhotoError, photo_suffix, save_photo
from .runs import (
    REFERENCE_FILE,
    SPEC_PARTS_FILE,
    SpecState,
    Workspace,
    WorkspaceError,
    sha256_of,
)
from .status import OPEN_STAGES, JobStep, RequestRecord, RunStatus, list_runs, run_status

__all__ = [
    "OPEN_STAGES",
    "REFERENCE_FILE",
    "SPEC_PARTS_FILE",
    "JobStep",
    "RequestRecord",
    "RunFile",
    "RunStatus",
    "SavedPhoto",
    "SpecState",
    "UnsupportedPhotoError",
    "Workspace",
    "WorkspaceError",
    "list_runs",
    "photo_suffix",
    "run_images",
    "run_outputs",
    "run_status",
    "save_photo",
    "sha256_of",
]
