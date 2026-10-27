"""The quote checker (drill-press plan, Phase 5): each quote on its cited page of the PDF."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from moonwalkers.contracts.pipeline_result import Citation, Source
from moonwalkers.pipelines.b import quotes
from moonwalkers.pipelines.b.pipeline import load_reference
from moonwalkers.pipelines.b.quotes import (
    check_quotes,
    citations_in,
    cited_page,
    local_pdf,
    quote_pattern,
)

REFERENCES = Path(quotes.__file__).parent
NOW = datetime(2026, 10, 26, tzinfo=UTC)

# Two pages, written the way pypdf reads the T33901 manual: words broken over lines with a
# hyphen, a split word, and a data sheet line with a dot leader.
PAGES = [
    [
        "M. Depth Stop: Stops spindle travel at prede-",
        "termined drilling depth.",
        "Spindle speed is con -",
        "trolled by the configuration of V-belts",
    ],
    [
        "2. T ilt table until pointer aligns with desired angle on scale",
        "Spindle Travel.............................. 3-1/4 in.",
    ],
]


def write_pdf(path: Path, pages: list[list[str]]) -> Path:
    """A minimal text PDF: one Helvetica line per entry."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(len(pages)))
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>")
    font = 3 + 2 * len(pages)
    for i, lines in enumerate(pages):
        text = " 0 -14 Td ".join(f"({_escape(line)}) Tj" for line in lines)
        stream = f"BT /F1 10 Tf 40 760 Td {text} ET"
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {4 + 2 * i} 0 R "
            f"/Resources << /Font << /F1 {font} 0 R >> >> >>"
        )
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    body, offsets = b"%PDF-1.4\n", []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f"{number} 0 obj\n{obj}\nendobj\n".encode("latin-1")
    xref = len(body)
    body += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    body += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    body += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return path


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


@pytest.fixture
def manual(tmp_path: Path) -> tuple[Path, Source]:
    write_pdf(tmp_path / "machines" / "m" / "inputs" / "documents" / "manual.pdf", PAGES)
    source = Source(
        source_id="src-manual",
        kind="file",
        uri="machines/m/inputs/documents/manual.pdf",
        retrieved_at=NOW,
    )
    return tmp_path, source


def cite(locator: str | None, quote: str) -> Citation:
    return Citation(source_id="src-manual", locator=locator, quote=quote)


def test_a_pattern_joins_words_broken_at_a_line_end() -> None:
    assert quote_pattern("Stops spindle travel at predetermined drilling depth").search(
        "Stops spindle travel at prede-\ntermined drilling depth."
    )
    assert quote_pattern("is controlled by").search("is con -\ntrolled by")


def test_a_pattern_ignores_whitespace_but_not_letters() -> None:
    assert quote_pattern("Tilt table").search("2. T ilt table")
    assert not quote_pattern("Tilt table").search("Til table")


def test_an_ellipsis_stands_for_a_dot_leader_or_left_out_words() -> None:
    pattern = quote_pattern("Spindle Travel ... 3-1/4 in.")
    assert pattern.search("Spindle Travel............ 3-1/4 in.")
    assert quote_pattern("Spindle Travel … 3-1/4 in.").search("Spindle Travel... 3-1/4 in.")
    assert not pattern.search("Spindle Travel.... 3-1/2 in.")
    # what is left out starts and ends between words, so it cannot hide part of a number
    assert not quote_pattern("Spindle Travel ... 4 in.").search("Spindle Travel...... 3-1/4 in.")
    assert not quote_pattern("Spindle Trav ... 3-1/4 in.").search("Spindle Travel... 3-1/4 in.")


def test_typographic_forms_match_their_plain_ones() -> None:
    page = quotes.plain('Accepts drill bits with shanks from 1⁄8"–5⁄8"')
    assert quote_pattern('1/8"-5/8"').search(page)
    assert quote_pattern('1⁄8"–5⁄8"').search(page)


def test_the_cited_page_is_the_pdf_page() -> None:
    assert cited_page("PDF p. 7") == 7
    assert cited_page("PDF p. 4 (printed p. 3), Specifications") == 4
    assert cited_page("p. 1, Front View") == 1
    assert cited_page("specifications table") is None
    assert cited_page(None) is None


def test_quotes_are_found_on_their_page(manual: tuple[Path, Source]) -> None:
    data, source = manual
    citations = [
        ("a", cite("PDF p. 1", "Stops spindle travel at predetermined drilling depth")),
        ("b", cite("PDF p. 2", "Tilt table until pointer aligns with desired angle on scale")),
        ("c", cite("PDF p. 2", "Spindle Travel ... 3-1/4 in.")),
    ]
    checks = check_quotes([source], citations, data)
    assert [c.status for c in checks] == ["found", "found", "found"]


def test_a_quote_on_another_page_or_on_none_is_reported(manual: tuple[Path, Source]) -> None:
    data, source = manual
    citations = [
        ("a", cite("PDF p. 1", "Spindle Travel ... 3-1/4 in.")),
        ("b", cite("PDF p. 1", "Spindle Travel ... 3-1/2 in.")),
        ("c", cite(None, "Spindle speed is controlled")),
    ]
    elsewhere, missing, unpaged = check_quotes([source], citations, data)
    assert (elsewhere.status, elsewhere.detail) == (
        "elsewhere",
        "not on the cited p. 1; found on p. 2",
    )
    assert missing.status == "not_found"
    assert (unpaged.status, unpaged.detail) == ("elsewhere", "no page cited; found on p. 1")


def test_quotes_that_cannot_be_checked_say_why(manual: tuple[Path, Source]) -> None:
    data, source = manual
    user = Source(source_id="src-user", kind="user_input", uri="user", retrieved_at=NOW)
    web = Source(source_id="src-web", kind="url", uri="https://example.com", retrieved_at=NOW)
    citations = [
        ("a", Citation(source_id="src-user", quote="Motor end to lever tip")),
        ("b", Citation(source_id="src-web", locator="p. 1", quote="60:1")),
        ("c", Citation(source_id="src-gone", quote="anything")),
        ("d", Citation(source_id="src-manual", locator="PDF p. 1")),  # no quote: skipped
    ]
    checks = check_quotes([source, user, web], citations, data)
    assert [(c.where, c.detail) for c in checks] == [
        ("a", "user input"),
        ("b", "no local PDF of this source"),
        ("c", "unknown source"),
    ]


def test_a_url_source_is_found_by_its_sha256(manual: tuple[Path, Source]) -> None:
    data, source = manual
    pdf = data / source.uri
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    web = Source(
        source_id="src-web", kind="url", uri="https://example.com/m.pdf", sha256=digest,
        retrieved_at=NOW,
    )  # fmt: skip
    assert local_pdf(web, data) == pdf.resolve()
    check = check_quotes([web], [("a", Citation(source_id="src-web", locator="PDF p. 2",
                                                 quote="T ilt table"))], data)  # fmt: skip
    assert check[0].status == "found"


def test_citations_are_found_anywhere_with_where_they_sit() -> None:
    document = {
        "sources": [{"source_id": "s", "quote": "not a citation"}],
        "facts": [{"key": "spindle_travel", "citations": [{"source_id": "s", "quote": "x"}]}],
        "joints": [{"joint_id": "quill_travel", "mode": {"kind": "spring_return",
                                                          "citations": [{"source_id": "s"}]}}],
    }  # fmt: skip
    assert [where for where, _ in citations_in(document)] == [
        "facts[spindle_travel].citations",
        "joints[quill_travel].mode.citations",
    ]


def test_the_command_line_fails_on_a_missing_quote(
    manual: tuple[Path, Source], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data, source = manual
    reference = {
        "sources": [source.model_dump(mode="json")],
        "facts": [
            {
                "key": "a",
                "citations": [cite("PDF p. 2", "Spindle Travel ... 3-1/4 in.").model_dump()],
            }
        ],
    }
    path = tmp_path / "reference.json"
    path.write_text(json.dumps(reference), encoding="utf-8")
    assert quotes.main([str(path), "--data", str(data)]) == 0
    reference["facts"][0]["citations"][0]["quote"] = "Spindle Travel ... 4 in."
    path.write_text(json.dumps(reference), encoding="utf-8")
    assert quotes.main([str(path), "--data", str(data)]) == 1
    assert "not_found" in capsys.readouterr().out


def test_the_t33901_reference_facts_load() -> None:
    reference = load_reference(REFERENCES / "grizzly_t33901.reference.json")
    assert reference.identity is not None and reference.identity.model == "T33901"
    travel = reference.fact("spindle_travel")
    assert travel is not None and travel.value == pytest.approx(3.25 * 0.0254)
    assert reference.fact("max_spindle_speed").value == pytest.approx(
        2860 * 2 * 3.14159265 / 60, rel=1e-5
    )
