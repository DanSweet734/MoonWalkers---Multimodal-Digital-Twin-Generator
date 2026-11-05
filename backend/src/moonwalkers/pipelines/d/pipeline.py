"""Pipeline D's Octopart source adapter; only the orchestrator persists its result."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Protocol

from moonwalkers.clock import Clock, utc_now
from moonwalkers.contracts.pipeline_result import (
    Citation,
    Fact,
    InputType,
    Issue,
    PipelineId,
    PipelineResult,
    Source,
)

from ..base import Pipeline, result_id_for
from .octopart import input_url


class Reader(Protocol):
    def read(self, url: str) -> dict[str, Any]: ...


class BrowserReader:
    """Invoke an isolated Python so browser packages do not change backend dependencies."""

    def __init__(self, python: str | None = None, timeout: float = 100) -> None:
        self.python = python
        self.timeout = timeout

    def read(self, url: str) -> dict[str, Any]:
        python = self.python or os.environ.get("MOONWALKERS_OCTOPART_PYTHON")
        if not python:
            return {
                "status": "error",
                "message": "Set MOONWALKERS_OCTOPART_PYTHON to the browser environment's Python. "
                "See docs/setup/pipeline-d-octopart.md.",
            }
        worker = Path(__file__).with_name("browser_worker.py")
        try:
            completed = subprocess.run(
                [python, str(worker)],
                input=json.dumps({"url": url}),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "Octopart browser worker timed out."}
        except OSError:
            return {"status": "error", "message": "Could not start the Octopart browser Python."}
        if completed.returncode != 0 or len(completed.stdout) > 2_000_000:
            return {"status": "error", "message": "Octopart browser worker failed."}
        try:
            result = json.loads(completed.stdout)
        except ValueError:
            result = None
        if not isinstance(result, dict):
            return {"status": "error", "message": "Octopart browser returned invalid JSON."}
        return result


class CatalogPipeline(Pipeline):
    """Enrich online Octopart sources with component facts, never machine identity."""

    pipeline_id = PipelineId.D

    def __init__(self, reader: Reader | None = None, clock: Clock = utc_now) -> None:
        self.reader = reader if reader is not None else BrowserReader()
        self.clock = clock

    def run(self, job_id: str, sources: list[Source]) -> PipelineResult:
        if not sources or any(s.input_type is None for s in sources):
            raise ValueError("Pipeline D needs at least one typed source.")
        if len({s.source_id for s in sources}) != len(sources):
            raise ValueError("Pipeline D source ids must be unique.")
        result_sources = list(sources)
        facts: list[Fact] = []
        issues: list[Issue] = []
        for source in sources:
            if source.kind != "url" or source.input_type != InputType.ONLINE_RESOURCE:
                issues.append(
                    Issue(
                        severity="error",
                        ref=source.source_id,
                        message="Pipeline D currently reads Octopart online_resource URLs only. "
                        "PDF catalog extraction is not implemented.",
                    )
                )
                continue
            try:
                url, query = input_url(source.uri)
                record = self.reader.read(url)
                status = record.get("status")
                if status != "extracted":
                    message = str(record.get("message", "Octopart extraction needs review."))
                    links = record.get("candidates")
                    if isinstance(links, list):
                        message += " Candidates: " + ", ".join(str(link) for link in links[:10])
                    issues.append(
                        Issue(
                            severity="error" if status == "error" else "warning",
                            ref=source.source_id,
                            message=message,
                        )
                    )
                    continue
                fetched, search = input_url(record["url"])
                mpn = record.get("mpn")
                if search is not None or not isinstance(mpn, str) or not mpn.strip():
                    raise ValueError("Browser did not return a product with a part number.")
                if query is not None and query.casefold() != mpn.strip().casefold():
                    raise ValueError("Returned product does not match the exact requested part.")
                # New provenance describes the actual page read, not merely the search URL.
                suffix = hashlib.sha256(source.source_id.encode()).hexdigest()[:12]
                page_id = f"src-octopart-{suffix}"
                while page_id in {s.source_id for s in result_sources}:
                    page_id += "-page"
                fetched_source = Source(
                    source_id=page_id,
                    kind="url",
                    input_type=InputType.ONLINE_RESOURCE,
                    uri=fetched,
                    title=f"Octopart: {mpn}",
                    retrieved_at=self.clock(),
                )
                extracted = self._facts(record, page_id, suffix)
                result_sources.append(fetched_source)
                facts.extend(extracted)
                issues.append(
                    Issue(
                        severity="warning",
                        ref=source.source_id,
                        message="Octopart component metadata; not machine identity. Offers, PDF "
                        "links and page text are unverified evidence, not SI specifications or "
                        "normalized price/stock quotes. Hidden and paginated offers may be absent.",
                    )
                )
                if record.get("text_truncated"):
                    issues.append(
                        Issue(
                            severity="warning",
                            ref=source.source_id,
                            message="Page evidence truncated to the first 20,000 characters.",
                        )
                    )
            except (ValueError, KeyError, TypeError):
                issues.append(
                    Issue(
                        severity="error",
                        ref=source.source_id,
                        message="Unsupported Octopart URL or invalid extraction response; "
                        "no facts were imported for this input.",
                    )
                )
        return PipelineResult(
            result_id=result_id_for(job_id, self.pipeline_id),
            job_id=job_id,
            pipeline=self.pipeline_id,
            input_types=sorted({s.input_type for s in sources}, key=lambda t: t.value),
            produced_at=self.clock(),
            produced_by="pipeline-d octopart 0.1.0",
            sources=result_sources,
            facts=facts,
            issues=issues,
            needs_human_review=True,
        )

    @staticmethod
    def _facts(record: dict[str, Any], source_id: str, suffix: str) -> list[Fact]:
        facts = []
        values = {
            "mpn": record.get("mpn"),
            "manufacturer": record.get("manufacturer"),
            "description": record.get("description"),
            "datasheet_links": record.get("datasheets"),
            "offers_json": record.get("offers"),
            "page_text": record.get("page_text"),
        }
        for field, value in values.items():
            if value is None or value == "" or value == []:
                continue
            if not isinstance(value, str):
                value = json.dumps(value, ensure_ascii=False, allow_nan=False)
            raw = field in {"offers_json", "page_text", "datasheet_links"}
            facts.append(
                Fact(
                    key=f"octopart_{suffix}_{field}",
                    value=value,
                    original=value,
                    confidence=0.4 if raw else 0.8,
                    citations=[
                        Citation(
                            source_id=source_id,
                            locator="Rendered page evidence" if raw else f"JSON-LD Product.{field}",
                            quote=value[:200] if field != "offers_json" else None,
                        )
                    ],
                )
            )
        return facts
