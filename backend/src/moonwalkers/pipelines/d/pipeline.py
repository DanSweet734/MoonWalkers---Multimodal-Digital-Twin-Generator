"""Pipeline D: Octopart pages and PDF catalogs; only the orchestrator persists its result."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, Protocol

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
from .catalog_facts import labelled_values, line_with, slug
from .octopart import input_url

PYTHON_VARIABLE = "MOONWALKERS_OCTOPART_PYTHON"
MAX_FACTS_PER_PDF = 500
CANDIDATE_CITATIONS = 3


def run_worker(
    python: str | None,
    script: str,
    request: dict[str, Any],
    timeout: float,
    name: str,
    limit: int,
) -> dict[str, Any]:
    """Run one of Pipeline D's worker scripts in its own Python: JSON in, JSON out."""
    python = python or os.environ.get(PYTHON_VARIABLE)
    if not python:
        return {
            "status": "error",
            "message": f"Set {PYTHON_VARIABLE} to Pipeline D's environment's Python. "
            "See docs/setup/pipeline-d-octopart.md.",
        }
    worker = Path(__file__).with_name(script)
    try:
        completed = subprocess.run(
            [python, str(worker)],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": f"{name} worker timed out."}
    except OSError:
        return {"status": "error", "message": f"Could not start the {name} Python."}
    if completed.returncode != 0 or len(completed.stdout) > limit:
        return {"status": "error", "message": f"{name} worker failed."}
    try:
        result = json.loads(completed.stdout)
    except ValueError:
        result = None
    if not isinstance(result, dict):
        return {"status": "error", "message": f"{name} returned invalid JSON."}
    return result


class Reader(Protocol):
    def read(self, url: str) -> dict[str, Any]: ...


class BrowserReader:
    """Invoke an isolated Python so browser packages do not change backend dependencies."""

    def __init__(self, python: str | None = None, timeout: float = 100) -> None:
        self.python = python
        self.timeout = timeout

    def read(self, url: str) -> dict[str, Any]:
        return run_worker(
            self.python,
            "browser_worker.py",
            {"url": url},
            self.timeout,
            "Octopart browser",
            2_000_000,
        )


class PdfReader(Protocol):
    def read(self, path: Path) -> dict[str, Any]: ...


class CatalogReader:
    """Run ``catalog_parser.py`` in Pipeline D's Python, keeping pdfminer.six out of the backend."""

    def __init__(self, python: str | None = None, timeout: float = 300) -> None:
        self.python = python
        self.timeout = timeout

    def read(self, path: Path) -> dict[str, Any]:
        return run_worker(
            self.python,
            "catalog_worker.py",
            {"path": str(path)},
            self.timeout,
            "PDF catalog",
            50_000_000,
        )


class CatalogPipeline(Pipeline):
    """Cited facts from Octopart pages and PDF catalogs; never the machine's identity."""

    pipeline_id = PipelineId.D

    def __init__(
        self,
        reader: Reader | None = None,
        clock: Clock = utc_now,
        pdf_reader: PdfReader | None = None,
        data_dir: Path | None = None,
    ) -> None:
        self.reader = reader if reader is not None else BrowserReader()
        self.pdf_reader = pdf_reader if pdf_reader is not None else CatalogReader()
        self.clock = clock
        self.data_dir = data_dir  # None: default_data_dir(), read when a job runs

    def run(self, job_id: str, sources: list[Source]) -> PipelineResult:
        if not sources or any(s.input_type is None for s in sources):
            raise ValueError("Pipeline D needs at least one typed source.")
        if len({s.source_id for s in sources}) != len(sources):
            raise ValueError("Pipeline D source ids must be unique.")
        result_sources = list(sources)
        facts: list[Fact] = []
        issues: list[Issue] = []
        for source in sources:
            if source.input_type == InputType.PDF_CATALOG:
                pdf_facts, pdf_issues = self._pdf(source)
                facts.extend(pdf_facts)
                issues.extend(pdf_issues)
                continue
            if source.kind != "url" or source.input_type != InputType.ONLINE_RESOURCE:
                issues.append(
                    Issue(
                        severity="error",
                        ref=source.source_id,
                        message="Pipeline D reads pdf_catalog files and Octopart online_resource "
                        "URLs only.",
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
            produced_by="pipeline-d catalog 0.2.0",
            sources=result_sources,
            facts=facts,
            issues=issues,
            needs_human_review=True,
        )

    def _pdf(self, source: Source) -> tuple[list[Fact], list[Issue]]:
        """One PDF file's labelled values and part-number candidates, each cited to its page."""

        def note(message: str, severity: Literal["info", "warning", "error"] = "error") -> Issue:
            return Issue(severity=severity, ref=source.source_id, message=message)

        if source.kind != "file":
            return [], [
                note(
                    "Pipeline D reads a PDF catalog from a file. Save it under the data folder "
                    "(data/machines/<machine>/inputs/documents/) and give that file."
                )
            ]
        # Imported here: the workspace package itself imports the pipelines package.
        from moonwalkers.workspace import default_data_dir, sha256_of

        data_dir = (self.data_dir or default_data_dir()).resolve()
        path = (data_dir / source.uri).resolve()
        if not path.is_relative_to(data_dir) or not path.is_file():
            return [], [note("The PDF file is not in the data folder.")]
        if source.sha256 is not None and sha256_of(path) != source.sha256:
            return [], [note("The PDF file changed since it was added (its SHA-256 differs).")]
        record = self.pdf_reader.read(path)
        try:
            if record.get("status") != "extracted":
                return [], [note(str(record.get("message", "PDF extraction failed.")))]
            return self._pdf_facts(record, source.source_id, note)
        except (ValueError, KeyError, TypeError, AttributeError):
            return [], [note("Invalid PDF extraction response; no facts were imported.")]

    @staticmethod
    def _pdf_facts(
        record: dict[str, Any], source_id: str, note: Callable[..., Issue]
    ) -> tuple[list[Fact], list[Issue]]:
        pages = record["pages"]
        summary = record["summary"]
        suffix = hashlib.sha256(source_id.encode()).hexdigest()[:12]
        facts: list[Fact] = []
        keys: set[str] = set()

        def add(key: str, value: str, confidence: float, citations: list[Citation]) -> None:
            base, n = key, 2
            while key in keys:
                key, n = f"{base}_{n}", n + 1
            keys.add(key)
            facts.append(
                Fact(
                    key=key,
                    value=value,
                    original=value,
                    confidence=confidence,
                    citations=citations,
                )
            )

        def cite(page: int, quote: str | None) -> Citation:
            return Citation(
                source_id=source_id,
                locator=f"PDF p. {page}",
                quote=quote[:200] if quote else None,
            )

        # Candidates first, so a long catalog's limit never drops them.
        printed: dict[str, list[Citation]] = {}
        for page in pages:
            for candidate in page["part_number_candidates"]:
                quote = line_with(str(page["text"]), str(candidate))
                printed.setdefault(str(candidate), []).append(cite(int(page["page"]), quote))
        for candidate, citations in printed.items():
            add(
                f"catalog_{suffix}_candidate_{slug(candidate) or 'unnamed'}",
                candidate,
                0.5,
                citations[:CANDIDATE_CITATIONS],
            )
        candidates = len(facts)

        reading = labelled_values(pages)
        dropped = 0
        for item in reading.values:
            if len(facts) >= MAX_FACTS_PER_PDF:
                dropped += 1
                continue
            names = [slug(item.heading), slug(item.label) or "value"]
            add(
                f"catalog_{suffix}_p{item.page:03d}_" + "_".join(n for n in names if n),
                item.value,
                0.7,
                [cite(item.page, item.quote)],
            )

        issues = [
            note(
                f"Read {int(summary['page_count'])} page(s), {int(summary['word_count'])} "
                f"word(s): {len(facts) - candidates} labelled value(s) and {candidates} "
                f"part-number candidate(s). {int(summary['image_count'])} embedded image(s) were "
                "found and not imported.",
                "info",
            ),
            note(
                "PDF catalog evidence; not machine identity. Values are text as printed, not "
                "converted to SI. A PDF may cover several models: check each fact's page. "
                "Tables, drawings and text inside images are not read.",
                "warning",
            ),
        ]
        empty = [str(page["page"]) for page in pages if not str(page["text"]).strip()]
        if empty:
            issues.append(
                note(
                    f"No text on page(s) {', '.join(empty)}: a scan or a blank page. There is "
                    "no OCR.",
                    "warning",
                )
            )
        if reading.number_list_pages:
            listed = ", ".join(str(n) for n in reading.number_list_pages)
            issues.append(
                note(
                    f"Page(s) {listed} look like contents or quantity lists (bare whole numbers) "
                    "and gave no facts.",
                    "info",
                )
            )
        if reading.unclear_lines:
            issues.append(
                note(
                    f"{reading.unclear_lines} line(s) hold two labelled values and were left out.",
                    "warning",
                )
            )
        if dropped:
            issues.append(
                note(
                    f"Stopped at {MAX_FACTS_PER_PDF} facts; {dropped} more labelled value(s) "
                    "were left out.",
                    "warning",
                )
            )
        return facts, issues

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
