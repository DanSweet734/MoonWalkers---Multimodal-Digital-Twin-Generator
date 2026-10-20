"""Control logic: indexing programs that drive a twin's joint (Phase 6, decision 0016).

- ``program``: the HA5C manual's step table as an ``IndexProgram``, carried in a
  ``ControlBehavior`` (``spec["program"]``), and program files with their sources;
- ``interpreter``: runs a program into the joint's target angle over time;
- ``export``: writes a program folder for Isaac Sim, with ``isaac_runner.py`` as its runner;
- ``python -m moonwalkers.control``: list, show and run programs.
"""

from .export import ProgramOutput, write_program_folder
from .interpreter import RunSettings, Trajectory, run_program
from .program import (
    IndexProgram,
    IndexStep,
    ProgramError,
    ProgramFile,
    packaged_programs,
    runnable_behaviors,
)

__all__ = [
    "IndexProgram",
    "IndexStep",
    "ProgramError",
    "ProgramFile",
    "ProgramOutput",
    "RunSettings",
    "Trajectory",
    "packaged_programs",
    "run_program",
    "runnable_behaviors",
    "write_program_folder",
]
