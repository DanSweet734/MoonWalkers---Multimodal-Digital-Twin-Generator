"""Command line for Pipeline B (decision 0012). Run from ``backend/``::

    uv run python -m moonwalkers.pipelines.b build RUN --reference FILE
    uv run python -m moonwalkers.pipelines.b inspect RUN [--up +y --front +z] [--preview]

``RUN`` is a run folder, ``data/machines/<machine>/runs/<run>``, holding ``request.json`` (a
``JobRequest`` with the photo as a source). ``build`` sends the request through the orchestrator:
the first time it generates the mesh and stops for the geometry spec; once
``geometry_spec.json`` exists, it stores the twin in ``data/kb``, exports ``twin.usdc`` (plus
``checks/spin.usdc`` and ``checks/quarter_turn.usdc`` for the Isaac Sim check) and writes
``RUN.md``. One run folder holds one built twin: build a new version in a new run folder.
``inspect`` renders and measures the generated mesh, and ``--preview`` tries the spec without
storing anything. The generator environment is found through ``--gen-root`` or the
``MOONWALKERS_GEN_ROOT`` environment variable (docs/setup/generators.md). The MCP server
(``moonwalkers.mcp``) offers the same steps as tools.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from moonwalkers.generators.base import GeneratorError
from moonwalkers.generators.hunyuan3d import Hunyuan3DConfig, Hunyuan3DGenerator
from moonwalkers.kb import JsonKnowledgeBase
from moonwalkers.orchestrator import OrchestratorError
from moonwalkers.usd.exporter import ExportError

from .assemble import GeometrySpec
from .build import REQUEST_FILE, build_run
from .inspection import format_inspection, format_preview, inspect_mesh, preview_parts
from .pipeline import (
    SPEC_FILE,
    GeometrySpecMissing,
    RunFolderConflict,
    generated_mesh,
    load_reference,
)

GEN_ROOT_ENV = "MOONWALKERS_GEN_ROOT"
AXES = ("+x", "-x", "+y", "-y", "+z", "-z")


class UsageError(Exception):
    """The command was given arguments it cannot use."""


EXPECTED_ERRORS = (
    UsageError,
    GeometrySpecMissing,
    RunFolderConflict,
    OrchestratorError,
    GeneratorError,
    ExportError,
    FileNotFoundError,
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.command(args)
    except GeometrySpecMissing as exc:
        print(f"stopped: {exc}")
        return 2
    except EXPECTED_ERRORS as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m moonwalkers.pipelines.b", description=__doc__)
    commands = parser.add_subparsers(required=True)

    build = commands.add_parser("build", help="build (or reuse) the twin for a run's request")
    build.add_argument("run_dir", type=Path, help="data/machines/<machine>/runs/<run>")
    build.add_argument("--reference", type=Path, required=True, help="reference facts JSON")
    build.add_argument(
        "--request", type=Path, help=f"JobRequest JSON (default: RUN/{REQUEST_FILE})"
    )
    build.add_argument("--gen-root", type=Path, help=f"generator folder (default: ${GEN_ROOT_ENV})")
    build.add_argument("--data", type=Path, help="data folder (default: from the run folder)")
    build.add_argument("--kb", type=Path, help="knowledge base folder (default: DATA/kb)")
    build.set_defaults(command=_build)

    inspect = commands.add_parser("inspect", help="render and measure the generated mesh")
    inspect.add_argument("run_dir", type=Path)
    inspect.add_argument("--up", choices=AXES, help="the generator axis that points up")
    inspect.add_argument("--front", choices=AXES, help="the generator axis the spindle faces")
    inspect.add_argument("--window", type=float, help="profile radius limit (model units)")
    inspect.add_argument(
        "--preview", action="store_true", help=f"try RUN/{SPEC_FILE} without storing anything"
    )
    inspect.add_argument("--reference", type=Path, help="reference facts, for size checks")
    inspect.set_defaults(command=_inspect)
    return parser


# ------------------------------------------------------------------------------------ inspect
def _inspect(args: argparse.Namespace) -> int:
    run_dir = args.run_dir
    mesh = generated_mesh(run_dir)
    if args.preview:
        spec_path = run_dir / SPEC_FILE
        if not spec_path.is_file():
            raise FileNotFoundError(f"--preview needs {spec_path}")
        spec = GeometrySpec.model_validate_json(spec_path.read_text(encoding="utf-8"))
        reference = load_reference(args.reference) if args.reference else None
        print(format_preview(preview_parts(mesh, spec, run_dir / "preview"), reference))
        return 0
    if (args.up is None) != (args.front is None):
        raise UsageError("give both --up and --front, or neither")
    out_dir = run_dir / ("inspect_oriented" if args.up else "inspect_raw")
    print(format_inspection(inspect_mesh(mesh, out_dir, args.up, args.front, args.window)))
    return 0


# -------------------------------------------------------------------------------------- build
def _build(args: argparse.Namespace) -> int:
    run_dir = args.run_dir.resolve()
    data_dir = (args.data or _data_dir_of(run_dir)).resolve()
    gen_root = args.gen_root or os.environ.get(GEN_ROOT_ENV)
    if gen_root is None:
        raise UsageError(f"the generator folder is needed: pass --gen-root or set {GEN_ROOT_ENV}")
    request_path = args.request or run_dir / REQUEST_FILE
    outcome = build_run(
        run_dir,
        data_dir,
        request_path,
        load_reference(args.reference),
        args.reference,
        Hunyuan3DGenerator(Hunyuan3DConfig.under(Path(gen_root))),
        JsonKnowledgeBase(args.kb or data_dir / "kb"),
    )
    print(outcome.job.message)
    for issue in outcome.validation:
        print(f"  validation {issue.severity}: {issue.message} ({issue.ref or '-'})")
    return 0


def _data_dir_of(run_dir: Path) -> Path:
    """``data/`` for a run folder ``data/machines/<machine>/runs/<run>`` (data/README.md)."""
    parts = run_dir.parts
    if len(parts) < 5 or parts[-2] != "runs" or parts[-4] != "machines":
        raise UsageError(f"{run_dir} is not data/machines/<machine>/runs/<run>; pass --data")
    return run_dir.parents[3]


if __name__ == "__main__":
    sys.exit(main())
