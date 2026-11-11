"""One JSON request on stdin, one JSON response on stdout; run in Pipeline D's own environment.

Request: ``{"path": "<absolute path of a PDF>"}``. Response: ``{"status": "extracted",
"summary": ..., "pages": [{"page", "text", "part_number_candidates", "image_count",
"warnings"}]}``, or ``{"status": "error", "message": ...}``.

This file runs directly, without importing the backend or Pydantic. It parses into a temporary
folder that is removed afterwards, so nothing is stored: images are counted, not kept.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

MAX_REQUEST = 8192


def read(path: Path) -> dict[str, Any]:
    """Parse one PDF and return its page text, candidates and counts."""
    if __package__:
        from .catalog_parser import parse_catalog
    else:
        from catalog_parser import parse_catalog

    with tempfile.TemporaryDirectory() as folder:
        parsed = parse_catalog(path, Path(folder) / "out")
    return {
        "status": "extracted",
        "summary": parsed["summary"],
        "pages": [
            {
                "page": page["page"],
                "text": page["text"],
                "part_number_candidates": page["part_number_candidates"],
                "image_count": len(page["images"]),
                "warnings": page["warnings"],
            }
            for page in parsed["pages"]
        ],
    }


def main() -> int:
    try:
        request = json.loads(sys.stdin.read(MAX_REQUEST))
        result = read(Path(request["path"]))
    except ImportError:
        result = {"status": "error", "message": "Pipeline D's environment needs pdfminer.six."}
    except FileNotFoundError:
        result = {"status": "error", "message": "The PDF file was not found."}
    except Exception as error:  # noqa: BLE001 - any parser failure becomes one issue, not a crash
        # The exception's type only: its text may hold local paths.
        result = {"status": "error", "message": f"Could not read the PDF ({type(error).__name__})."}
    # ASCII only, so the console's encoding on Windows cannot break the response.
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
