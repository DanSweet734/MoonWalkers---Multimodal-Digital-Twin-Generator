"""``python -m moonwalkers.api``: serve the API (and the built dashboard) on 127.0.0.1."""

import argparse
from collections.abc import Sequence
from pathlib import Path

import uvicorn

from moonwalkers.workspace import Workspace, default_data_dir

from .app import create_app


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="MoonWalkers API and dashboard, for this computer only (127.0.0.1)."
    )
    parser.add_argument("--data", type=Path, help="the data folder (default: as the MCP server)")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    workspace = Workspace((args.data or default_data_dir()).resolve())
    print(f"Data folder: {workspace.data_dir}")
    print(f"Dashboard and API: http://127.0.0.1:{args.port}/ (API docs: /api/docs)")
    uvicorn.run(create_app(workspace), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
