"""Command line for Pipeline B (decision 0012). Run from ``backend/``::

    uv run python -m moonwalkers.pipelines.b build RUN --reference FILE
    uv run python -m moonwalkers.pipelines.b inspect RUN [--up +y --front +z [--yaw DEG]
                                                          [--circle-x X ...]]
    uv run python -m moonwalkers.pipelines.b inspect RUN --up +y --front +z [--yaw DEG]
                                                      --circles-along z --at Z ...
    uv run python -m moonwalkers.pipelines.b inspect RUN --preview [--spec FILE]
                                                      [--reference FILE] [--no-photos]

``RUN`` is a run folder, ``data/machines/<machine>/runs/<run>``, holding ``request.json`` (a
``JobRequest`` with the photos as sources, and their views when there are several; decision
0022). ``build`` sends the request through the orchestrator:
the first time it generates the mesh and stops for the geometry spec; once
``geometry_spec.json`` exists, it stores the twin in ``data/kb``, exports ``twin.usdc`` (plus
``checks/spin.usdc`` and ``checks/quarter_turn.usdc`` for the Isaac Sim check) and writes
``RUN.md``. One run folder holds one built twin: build a new version in a new run folder.
``inspect`` renders and measures the generated mesh, and ``--preview`` tries the spec without
storing anything. A several-part spec (decisions 0023 and 0027) is previewed into
``RUN/preview_parts/``: the coloured views of the cuts and the parts, each part alone, and the
parts drawn over each fed photo, with the scale and the size checks. The generator environment
is found through ``--gen-root`` or the ``MOONWALKERS_GEN_ROOT`` environment variable
(docs/setup/generators.md). The MCP server (``moonwalkers.mcp``) offers the same steps as tools.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from moonwalkers.generators.base import GeneratorError
from moonwalkers.generators.hunyuan3d import GEN_ROOT_ENV, Hunyuan3DConfig, Hunyuan3DGenerator
from moonwalkers.kb import JsonKnowledgeBase
from moonwalkers.orchestrator import OrchestratorError
from moonwalkers.usd.exporter import ExportError

from .build import REQUEST_FILE, build_run
from .inspection import (
    format_inspection,
    format_parts_preview,
    format_preview,
    inspect_mesh,
    preview_parts,
    preview_parts_spec,
)
from .mesh_tools import fit_circles_along, load_mesh, orientation_matrix, transformed
from .parts_spec import PartsSpec
from .pipeline import (
    GENERATOR_DIR,
    SPEC_FILE,
    GeometrySpecMissing,
    RunFolderConflict,
    generated_mesh,
    load_reference,
    read_spec,
)

PARTS_PREVIEW_DIR = "preview_parts"

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
        "--yaw",
        type=float,
        default=0.0,
        metavar="DEG",
        help="where the machine's front points after --up/--front, from +x towards +y; the mesh "
        "is turned back by it (corner photos: about 45; decision 0022)",
    )
    inspect.add_argument(
        "--circle-x",
        type=float,
        nargs="+",
        metavar="X",
        help="x positions through the round moving part: fit circles there and use their centre "
        "as the axis (when the spindle is not the front-most part)",
    )
    inspect.add_argument(
        "--circles-along",
        choices=("x", "y", "z"),
        help="fit circles in slices across this axis instead (the column and the quill stand "
        "along z), at the positions given with --at",
    )
    inspect.add_argument("--at", type=float, nargs="+", metavar="POS", help="slice positions")
    inspect.add_argument(
        "--preview", action="store_true", help=f"try RUN/{SPEC_FILE} without storing anything"
    )
    inspect.add_argument(
        "--spec", type=Path, help=f"with --preview: a draft spec, not RUN/{SPEC_FILE}"
    )
    inspect.add_argument(
        "--no-photos",
        action="store_true",
        help="with --preview of several parts: skip placing the fed photos (about a minute each)",
    )
    inspect.add_argument("--reference", type=Path, help="reference facts, for size checks")
    inspect.set_defaults(command=_inspect)
    return parser


# ------------------------------------------------------------------------------------ inspect
def _inspect(args: argparse.Namespace) -> int:
    run_dir = args.run_dir
    mesh = generated_mesh(run_dir)
    if args.preview:
        spec_path = args.spec or run_dir / SPEC_FILE
        if not spec_path.is_file():
            raise FileNotFoundError(f"--preview needs {spec_path}")
        spec = read_spec(spec_path)
        reference = load_reference(args.reference) if args.reference else None
        if isinstance(spec, PartsSpec):
            prepared = None if args.no_photos else run_dir / GENERATOR_DIR / "prepared"
            preview = preview_parts_spec(
                mesh, spec, reference, run_dir / PARTS_PREVIEW_DIR, prepared
            )
            print(format_parts_preview(preview))
            return 0
        print(format_preview(preview_parts(mesh, spec, run_dir / "preview"), reference))
        return 0
    if args.circles_along:
        if args.up is None or not args.at:
            raise UsageError("--circles-along needs --up, --front and --at")
        oriented = transformed(load_mesh(mesh), orientation_matrix(args.up, args.front, args.yaw))
        for fit, centre in fit_circles_along(oriented, args.circles_along, args.at):
            where = (
                "no circle"
                if centre is None
                else (
                    f"centre ({centre[0]:+.4f}, {centre[1]:+.4f}, {centre[2]:+.4f}), radius "
                    f"{fit.radius:.4f}, rms {fit.rms or 0:.4f}, coverage {fit.coverage:.0%}"
                    f"{', round' if fit.round else ''}"
                )
            )
            print(f"{args.circles_along} = {fit.x:+.3f}: {where} ({fit.samples} samples)")
        return 0
    if (args.up is None) != (args.front is None):
        raise UsageError("give both --up and --front, or neither")
    if args.circle_x and args.up is None:
        raise UsageError("--circle-x needs --up and --front")
    if args.yaw and args.up is None:
        raise UsageError("--yaw needs --up and --front")
    out_dir = run_dir / ("inspect_oriented" if args.up else "inspect_raw")
    inspection = inspect_mesh(
        mesh, out_dir, args.up, args.front, args.window, args.circle_x, args.yaw
    )
    print(format_inspection(inspection))
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
