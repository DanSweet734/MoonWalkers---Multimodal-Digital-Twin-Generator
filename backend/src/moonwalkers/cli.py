"""``python -m moonwalkers``: the platform's version, and where its commands are.

The version is the package's (``backend/pyproject.toml``), the one a release is tagged with
(``docs/releasing.md``).
"""

import argparse

from . import __version__

COMMANDS: dict[str, str] = {
    "moonwalkers.pipelines.b": "build a twin from photos (Pipeline B), dry-run, inspect, cutouts",
    "moonwalkers.pipelines": "list Pipelines A-D, run one on inputs without storing",
    "moonwalkers.control": "programs and controls: list, show, run, compare",
    "moonwalkers.usd.validate": "validate an exported twin (.usda or .usdc)",
    "moonwalkers.mcp": "the MCP server for the agent (stdio)",
    "moonwalkers.api": "the API and the built dashboard on 127.0.0.1",
}


def build_parser() -> argparse.ArgumentParser:
    width = max(len(module) for module in COMMANDS)
    listing = "\n".join(f"  python -m {m:<{width}}  {what}" for m, what in COMMANDS.items())
    return argparse.ArgumentParser(
        prog="python -m moonwalkers",
        description="MoonWalkers digital twin platform.",
        epilog=f"commands:\n{listing}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.add_argument("--version", action="version", version=f"moonwalkers {__version__}")
    parser.parse_args(argv)
    parser.print_help()
    return 0
