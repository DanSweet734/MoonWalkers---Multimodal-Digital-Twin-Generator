"""Control logic: indexing programs that drive a twin's joint (Phase 6, decision 0016).

- ``program``: the HA5C manual's step table as an ``IndexProgram``, carried in a
  ``ControlBehavior`` (``spec["program"]``), and program files with their sources;
- ``interpreter``: runs a program into the joint's target angle over time;
- ``export``: writes a program folder for Isaac Sim, with ``isaac_runner.py`` as its runner;
- ``manual``: a manual machine's controls (decision 0025): a switch, a speed table and the
  operator's commands, planned with the controller ``isaac_controls`` runs in Isaac Sim;
- ``controls_export``: writes a controls folder; ``compare`` measures a recording against it;
- ``python -m moonwalkers.control``: list, show and run programs; controls and compare.
"""

from .controls_export import ControlsOutput, controls_files, write_controls_folder
from .export import ProgramOutput, write_program_folder
from .interpreter import RunSettings, Trajectory, run_program
from .manual import ControlPlan, ControlsFile, ManualControls, manual_controls, plan_scenario
from .program import (
    IndexProgram,
    IndexStep,
    ProgramError,
    ProgramFile,
    packaged_programs,
    runnable_behaviors,
)

__all__ = [
    "ControlPlan",
    "ControlsFile",
    "ControlsOutput",
    "IndexProgram",
    "IndexStep",
    "ManualControls",
    "ProgramError",
    "ProgramFile",
    "ProgramOutput",
    "RunSettings",
    "Trajectory",
    "controls_files",
    "manual_controls",
    "packaged_programs",
    "plan_scenario",
    "run_program",
    "runnable_behaviors",
    "write_controls_folder",
    "write_program_folder",
]
