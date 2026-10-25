"""Run one input pipeline (A, C or D) on files or URLs, outside the tests (decision 0021).

From ``backend/``::

    uv run python -m moonwalkers.pipelines list
    uv run python -m moonwalkers.pipelines run D --input-type pdf_catalog \\
        ../data/machines/grizzly-t33901/inputs/documents/grizzly-t33901-t33902-manual-2023.pdf \\
        --out ../data/machines/grizzly-t33901/pipeline_tries/2026-10-23_d.json

``run`` builds a cited ``Source`` for each input: a file inside the data folder (its path is
stored relative to it, with its SHA-256, and its modification time as when it was retrieved), or
an http(s) URL. The data folder is ``default_data_dir()``, the one a pipeline resolves a file
source's ``uri`` against (``MOONWALKERS_DATA_DIR``, else the repository's ``data/``). It runs the
pipeline, checks the result against the contract, and writes it as JSON, to ``--out`` or to the
screen. It stores nothing in the knowledge base: only the orchestrator does that (CLAUDE.md rule
6). A pipeline whose owner's ``create_pipeline()`` still returns the stub is not in, and is
refused.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from moonwalkers.clock import utc_now
from moonwalkers.contracts.pipeline_result import InputType, PipelineId, PipelineResult, Source
from moonwalkers.orchestrator.router import ROUTES
from moonwalkers.workspace import default_data_dir, sha256_of

from . import OWNERS, Pipeline, default_pipelines

RUNNABLE = (PipelineId.A, PipelineId.C, PipelineId.D)


class UsageError(Exception):
    """The command was given something it cannot use."""


def main(
    argv: Sequence[str] | None = None, pipelines: Mapping[PipelineId, Pipeline] | None = None
) -> int:
    """``pipelines`` are the ones that are in (default: ``default_pipelines()``)."""
    args = _parser().parse_args(argv)
    available = default_pipelines() if pipelines is None else dict(pipelines)
    try:
        if args.command == "list":
            print(_listing(available))
            return 0
        return _run(args, available)
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m moonwalkers.pipelines",
        description="Run Pipeline A, C or D on inputs, outside the tests (decision 0021).",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="each pipeline, its input types, owner, and whether it is in")
    run = commands.add_parser("run", help="run one pipeline and write its result as JSON")
    run.add_argument("pipeline", choices=[p.value for p in PipelineId])
    run.add_argument("inputs", nargs="+", help="files inside the data folder, or http(s) URLs")
    run.add_argument(
        "--input-type",
        required=True,
        choices=[t.value for t in InputType],
        help="what the inputs are; it must be one the pipeline reads",
    )
    run.add_argument("--job", default=None, help="job id (default: try-<pipeline>)")
    run.add_argument("--out", type=Path, default=None, help="JSON file to write (never replaced)")
    return parser


def _listing(available: Mapping[PipelineId, Pipeline]) -> str:
    lines = []
    for pid in PipelineId:
        reads = ", ".join(t.value for t, routed in ROUTES.items() if routed == pid)
        if pid == PipelineId.B:
            state = "built per run folder (python -m moonwalkers.pipelines.b)"
        elif pid in available:
            state = "in"
        else:
            state = "not in yet: create_pipeline() returns the stub"
        lines.append(f"{pid.value}  {OWNERS[pid]:<25} {reads:<38} {state}")
    return "\n".join(lines)


def _run(args: argparse.Namespace, available: Mapping[PipelineId, Pipeline]) -> int:
    pid = PipelineId(args.pipeline)
    if pid not in RUNNABLE:
        raise UsageError("Pipeline B builds in a run folder: python -m moonwalkers.pipelines.b")
    input_type = InputType(args.input_type)
    if ROUTES[input_type] != pid:
        raise UsageError(
            f"{input_type.value} inputs go to Pipeline {ROUTES[input_type].value}, not {pid.value}"
        )
    if pid not in available:
        raise UsageError(
            f"Pipeline {pid.value} ({OWNERS[pid]}'s) is not in yet: its create_pipeline() still "
            "returns the stub, which gives the HA5C's data for any input (decision 0021)"
        )
    if args.out is not None and args.out.exists():
        raise UsageError(f"{args.out} exists; pick a new file (results are never replaced)")
    data_dir = default_data_dir()
    job_id = args.job or f"try-{pid.value.lower()}"
    sources = _sources(args.inputs, input_type, data_dir)

    result = available[pid].run(job_id, sources)
    try:  # a pipeline may build its result without validation; the contract still applies
        result = PipelineResult.model_validate(result.model_dump())
    except ValidationError as exc:
        print(f"Pipeline {pid.value}'s result breaks the contract:\n{exc}", file=sys.stderr)
        return 1
    if result.pipeline != pid or result.job_id != job_id:
        print(
            f"Pipeline {pid.value} returned a result for Pipeline {result.pipeline.value}, job "
            f"{result.job_id} (expected job {job_id})",
            file=sys.stderr,
        )
        return 1

    text = result.model_dump_json(indent=2)
    if args.out is None:
        print(text)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {args.out}", file=sys.stderr)
    print(_summary(result), file=sys.stderr)
    return 0


def _sources(inputs: Sequence[str], input_type: InputType, data_dir: Path) -> list[Source]:
    sources: list[Source] = []
    for given in inputs:
        source_id = _unique_id(given, {s.source_id for s in sources})
        if re.match(r"https?://", given):
            sources.append(
                Source(
                    source_id=source_id,
                    kind="url",
                    input_type=input_type,
                    uri=given,
                    title=given,
                    retrieved_at=utc_now(),
                )
            )
            continue
        path = Path(given).resolve()
        if not path.is_file():
            raise UsageError(f"no file {given}")
        if not path.is_relative_to(data_dir):
            raise UsageError(
                f"{given} is outside the data folder {data_dir}; save inputs under "
                "data/machines/<machine>/inputs/ and list them in SOURCES.md first"
            )
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        sources.append(
            Source(
                source_id=source_id,
                kind="file",
                input_type=input_type,
                uri=path.relative_to(data_dir).as_posix(),
                title=path.name,
                sha256=sha256_of(path),
                retrieved_at=modified,
            )
        )
    return sources


def _unique_id(given: str, taken: set[str]) -> str:
    stem = Path(given.rstrip("/")).stem or "input"
    base = "src-" + (re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower() or "input")
    source_id, n = base, 2
    while source_id in taken:
        source_id, n = f"{base}-{n}", n + 1
    return source_id


def _summary(result: PipelineResult) -> str:
    identity = result.identity
    who = (
        f"{identity.manufacturer} {identity.model} ({identity.confidence:.2f})"
        if identity is not None
        else "none"
    )
    return (
        f"Pipeline {result.pipeline.value}: {len(result.facts)} fact(s), {len(result.parts)} "
        f"part(s), {len(result.joints)} joint(s), {len(result.control)} control behaviour(s), "
        f"{len(result.issues)} issue(s); identity: {who}; needs human review: "
        f"{'yes' if result.needs_human_review else 'no'}"
    )
