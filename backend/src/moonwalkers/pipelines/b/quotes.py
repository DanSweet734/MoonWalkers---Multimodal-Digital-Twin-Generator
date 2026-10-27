"""Check that every quote in a reference file is on its cited page (drill-press plan, Phase 5).

Rule 1 says every fact needs a source; this checks the quotes cheaply. A citation is checked when
its source is a PDF kept under the data folder: a ``file`` source by its path, or any source with a
SHA-256 by finding the file with that hash under ``machines/*/inputs/``. The page is the
locator's "PDF p. N", else its first "p. N".

pypdf's text is not the page as printed, so a quote is matched loosely (worklog 2026-10-23):

- whitespace is ignored: pypdf splits some words ("T ilt", p. 32) and joins others;
- a word broken over two lines with a hyphen is joined ("prede-" / "termined", p. 7;
  "con -" / "trolled", p. 30);
- "..." (or "…") in a quote stands for text left out, such as a data sheet's dot leaders
  ("Spindle Travel ... 3-1/4 in.");
- typographic forms count as their plain ones: the fraction slash as "/", dashes as "-", curly
  quotes as straight ones.

Run from ``backend/``::

    uv run python -m moonwalkers.pipelines.b.quotes <reference.json> [<more.json> ...]
        [--data ../data]

Every file's sources are pooled, so a geometry spec whose citations name the reference file's
sources can be checked with it. pypdf is a dev dependency; it is imported only here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Literal

from moonwalkers.contracts.pipeline_result import Citation, Source

Status = Literal["found", "elsewhere", "not_found", "not_checked"]
_PLAIN = str.maketrans(
    {
        "⁄": "/",  # fraction slash, as in 1⁄8"
        "–": "-",
        "—": "-",
        "−": "-",
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        " ": " ",
        "­": None,  # soft hyphen
    }
)
# Between two characters of a quote: any whitespace, or a hyphen that breaks a word at a line end.
_GAP = r"(?:\s*-[ \t]*\n\s*|\s*)"
_ELLIPSIS = re.compile(r"\.\.\.|…")
# What "..." may stand for: a dot leader, or a few words. It starts and ends between words, so
# "Spindle Travel ... 4 in." does not match "Spindle Travel ..... 3-1/4 in.".
_LEFT_OUT = r"(?![0-9A-Za-z])[\s\S]{0,400}?(?<![0-9A-Za-z/-])"
_PDF_PAGE = re.compile(r"\bPDF p\. ?(\d+)")
_PAGE = re.compile(r"\bp\. ?(\d+)")


@dataclass(frozen=True)
class QuoteCheck:
    where: str  # which item the citation belongs to, e.g. "facts[spindle_travel]"
    citation: Citation
    status: Status
    detail: str = ""  # the page found on, or why it was not checked


def plain(text: str) -> str:
    return text.translate(_PLAIN)


def quote_pattern(quote: str) -> re.Pattern[str]:
    """A pattern for ``quote`` in pypdf's text of a page (module docstring)."""
    segments = []
    for segment in _ELLIPSIS.split(plain(quote)):
        chars = [c for c in segment if not c.isspace()]
        if chars:
            segments.append(_GAP.join(re.escape(c) for c in chars))
    if not segments:
        raise ValueError(f"nothing to look for in the quote {quote!r}")
    return re.compile(_LEFT_OUT.join(segments))


def cited_page(locator: str | None) -> int | None:
    """The PDF page a locator names ("PDF p. 7", else the first "p. N"), or None."""
    if not locator:
        return None
    match = _PDF_PAGE.search(locator) or _PAGE.search(locator)
    return int(match.group(1)) if match else None


def check_quotes(
    sources: Sequence[Source],
    citations: Sequence[tuple[str, Citation]],
    data_dir: Path,
) -> list[QuoteCheck]:
    """Check each ``(where, citation)`` that has a quote against its source's PDF."""
    by_id = {s.source_id: s for s in sources}
    checks = []
    for where, citation in citations:
        if not citation.quote:
            continue
        source = by_id.get(citation.source_id)
        if source is None:
            checks.append(QuoteCheck(where, citation, "not_checked", "unknown source"))
            continue
        pdf = local_pdf(source, data_dir)
        if pdf is None:
            reason = "no local PDF of this source" if source.kind != "user_input" else "user input"
            checks.append(QuoteCheck(where, citation, "not_checked", reason))
            continue
        page = cited_page(citation.locator)
        pattern = quote_pattern(citation.quote)
        pages = page_texts(pdf)
        if page is not None and 1 <= page <= len(pages) and pattern.search(pages[page - 1]):
            checks.append(QuoteCheck(where, citation, "found", f"p. {page}"))
            continue
        hits = [i + 1 for i, text in enumerate(pages) if pattern.search(text)]
        if hits:
            cited = "no page cited" if page is None else f"not on the cited p. {page}"
            found = ", ".join(f"p. {n}" for n in hits)
            checks.append(QuoteCheck(where, citation, "elsewhere", f"{cited}; found on {found}"))
        else:
            checks.append(QuoteCheck(where, citation, "not_found", pdf.name))
    return checks


def local_pdf(source: Source, data_dir: Path) -> Path | None:
    """The source's PDF under ``data_dir``: its own path for a ``file`` source, else the input
    file with its SHA-256."""
    data_dir = Path(data_dir).resolve()
    if source.kind == "file":
        path = (data_dir / source.uri).resolve()
        if path.suffix.lower() == ".pdf" and path.is_file():
            return path
    if source.sha256:
        path = _inputs_by_sha256(data_dir).get(source.sha256)
        if path is not None and path.suffix.lower() == ".pdf":
            return path
    return None


@cache
def _inputs_by_sha256(data_dir: Path) -> dict[str, Path]:
    found = {}
    for path in sorted(data_dir.glob("machines/*/inputs/**/*.pdf")):
        found[hashlib.sha256(path.read_bytes()).hexdigest()] = path
    return found


@cache
def page_texts(pdf: Path) -> tuple[str, ...]:
    from pypdf import PdfReader  # dev dependency (pyproject); only this checker needs it

    # pypdf logs a warning per font it cannot fully decode without fontTools; the text is fine.
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    return tuple(plain(page.extract_text() or "") for page in PdfReader(pdf).pages)


# ---------------------------------------------------------------------------------- files
def citations_in(data: Any, where: str = "") -> Iterator[tuple[str, Citation]]:
    """Every citation in a JSON document, with where it sits ("facts[spindle_travel]")."""
    if isinstance(data, Mapping):
        if "source_id" in data and set(data) <= {"source_id", "locator", "quote"}:
            yield where, Citation.model_validate(data)
            return
        name = next((str(data[k]) for k in _ID_KEYS if k in data), None)
        for key, value in data.items():
            if key == "sources":
                continue
            inner = f"{where}[{name}]" if name and not where.endswith(f"[{name}]") else where
            yield from citations_in(value, f"{inner}.{key}" if inner else key)
    elif isinstance(data, list):
        for item in data:
            yield from citations_in(item, where)


_ID_KEYS = ("key", "joint_id", "part_id", "behavior_id", "part", "id")


def sources_in(data: Any) -> list[Source]:
    return (
        [Source.model_validate(s) for s in data.get("sources", [])]
        if isinstance(data, Mapping)
        else []
    )


def format_checks(checks: Sequence[QuoteCheck]) -> str:
    counts = {s: sum(1 for c in checks if c.status == s) for s in _ORDER}
    lines = [
        (
            f"{len(checks)} quotes: {counts['found']} found on their page, {counts['elsewhere']} "
            f"on another page, {counts['not_found']} not found, {counts['not_checked']} not checked"
        ),
    ]
    for check in sorted(checks, key=lambda c: _ORDER.index(c.status)):
        if check.status == "found":
            continue
        lines.append(
            f"{check.status}: {check.where} ({check.citation.source_id}, "
            f"{check.citation.locator or 'no locator'}): {check.citation.quote!r} - {check.detail}"
        )
    return "\n".join(lines)


_ORDER: tuple[Status, ...] = ("not_found", "elsewhere", "not_checked", "found")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check that each quote is on its cited page.")
    parser.add_argument("files", type=Path, nargs="+", help="reference facts or other JSON files")
    parser.add_argument("--data", type=Path, default=Path("../data"), help="the data folder")
    args = parser.parse_args(argv)
    documents = [json.loads(p.read_text(encoding="utf-8")) for p in args.files]
    sources = [s for d in documents for s in sources_in(d)]
    citations = [
        (f"{p.name}: {where}", c)
        for p, d in zip(args.files, documents, strict=True)
        for where, c in citations_in(d)
    ]
    checks = check_quotes(sources, citations, args.data)
    print(format_checks(checks))
    return 1 if any(c.status in ("not_found", "elsewhere") for c in checks) else 0


if __name__ == "__main__":
    sys.exit(main())
