"""Run a job script with another environment's Python: JSON job in, JSON result out."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .base import GeneratorError


def run_job(
    python: Path,
    script: Path,
    job: Mapping[str, Any],
    work_dir: Path,
    timeout_s: float,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Run ``python script job.json result.json`` in ``work_dir`` and return the result.

    The script's output goes to ``work_dir/generator.log``. A non-zero exit, a missing result, a
    timeout, or a result whose ``status`` is not ``"ok"`` raises ``GeneratorError``. The script's
    temporary files go to ``work_dir/tmp``, removed afterwards: hy3dgen's mesh clean-up leaves its
    temporary ``.ply`` files behind (``delete=False`` in hy3dgen/shapegen/postprocessors.py).
    """
    # Absolute paths: the child runs with cwd=work_dir, so relative ones would point elsewhere.
    python, script, work_dir = (
        Path(python).resolve(),
        Path(script).resolve(),
        Path(work_dir).resolve(),
    )
    if not python.is_file():
        raise GeneratorError(f"generator Python not found: {python}")
    work_dir.mkdir(parents=True, exist_ok=True)
    job_path, result_path = work_dir / "job.json", work_dir / "result.json"
    log_path = work_dir / "generator.log"
    job_path.write_text(json.dumps(dict(job), indent=2), encoding="utf-8", newline="\n")
    result_path.unlink(missing_ok=True)

    tmp_dir = work_dir / "tmp"
    tmp_dir.mkdir(exist_ok=True)
    temp_env = {name: str(tmp_dir) for name in ("TMPDIR", "TEMP", "TMP")}  # Python's tempfile
    child_env = {**os.environ, **(env or {}), "PYTHONIOENCODING": "utf-8", **temp_env}
    with log_path.open("w", encoding="utf-8") as log:
        try:
            proc = subprocess.run(
                [str(python), "-u", str(script), str(job_path), str(result_path)],
                cwd=work_dir,
                env=child_env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise GeneratorError(
                f"generator timed out after {timeout_s:g} s; see {log_path}"
            ) from exc
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    if not result_path.is_file():
        raise GeneratorError(f"generator wrote no result (exit {proc.returncode}); see {log_path}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if proc.returncode != 0 or result.get("status") != "ok":
        message = result.get("error", "no error message")
        raise GeneratorError(
            f"generator failed (exit {proc.returncode}): {message}; see {log_path}"
        )
    result["log_path"] = str(log_path)
    return result
