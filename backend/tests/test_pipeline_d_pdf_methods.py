"""Stress tests of CatalogPipeline's two PDF methods, ``_pdf_facts`` and ``_pdf``.

Test cases are numbered: TC_F* test ``_pdf_facts``, TC_P* test ``_pdf``. Each name says what
it checks, each input of a test is its own line in the report (pytest ids), and each docstring
names its strategy:
- every message: choose inputs that make the method produce each of its messages;
- overflow: inputs larger than the method's buffers and limits;
- repetition: the same input, or series of inputs, many times;
- invalid output: inputs that push the method towards an invalid result;
- too large / too small: computed counts at their extremes.

Runs offline with no PDF library: the reader is a ``unittest.mock.Mock``, and ``_pdf_facts``
takes a worker record (the dictionary ``catalog_worker.py`` returns). Run from ``backend/``:

    uv run pytest -v -p no:cacheprovider tests/test_pipeline_d_pdf_methods.py
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from moonwalkers.contracts.pipeline_result import Fact, InputType, Issue, Source
from moonwalkers.pipelines.d import pipeline as pipeline_module
from moonwalkers.pipelines.d.pipeline import CatalogPipeline

NOW = datetime(2026, 11, 12, tzinfo=UTC)
DOTS = "." * 30
SOURCE_ID = "src-sheet"
SUFFIX = hashlib.sha256(SOURCE_ID.encode()).hexdigest()[:12]
URI = "machines/test-drill/inputs/documents/sheet.pdf"
NOT_IN_DATA = "The PDF file is not in the data folder."
KEY = re.compile(r"^catalog_[0-9a-f]{12}_[a-z0-9_]+$")

Result = tuple[list[Fact], list[Issue]]


def note(message: str, severity: str = "error") -> Issue:
    """The ``note`` that ``_pdf`` passes to ``_pdf_facts``."""
    return Issue(severity=severity, ref=SOURCE_ID, message=message)


def page(number: Any, text: str, candidates: list[str] | None = None) -> dict[str, Any]:
    return {
        "page": number,
        "text": text,
        "part_number_candidates": candidates or [],
        "image_count": 0,
        "warnings": [],
    }


def record(*pages: dict[str, Any], images: int = 0) -> dict[str, Any]:
    """What catalog_worker.py returns: status, summary and pages."""
    words = sum(len(str(p["text"]).split()) for p in pages)
    summary = {
        "page_count": len(pages),
        "word_count": words,
        "image_count": images,
        "exported_image_count": images,
    }
    return {"status": "extracted", "summary": summary, "pages": list(pages)}


def facts_of(rec: dict[str, Any]) -> Result:
    return CatalogPipeline._pdf_facts(rec, SOURCE_ID, note)


def short_keys(facts: list[Fact]) -> list[str]:
    """Keys without the ``catalog_<hash>_`` prefix."""
    return [fact.key.removeprefix(f"catalog_{SUFFIX}_") for fact in facts]


def messages(issues: list[Issue]) -> list[tuple[str, str]]:
    return [(issue.severity, issue.message) for issue in issues]


SHEET = "\n".join(
    [
        "MODEL T100 BENCH DRILL",
        "Operation Information",
        f"Spindle Travel {DOTS} 3-1/4 in.",
        f"Swing {DOTS} 14 in.",
    ]
)
CONTENTS = "\n".join(["Table of Contents", f"INTRODUCTION {DOTS} 2"])
TWO_ON_ONE_LINE = f"Oil {DOTS} A  Grease {DOTS} B"
EVIDENCE = (
    "PDF catalog evidence; not machine identity. Values are text as printed, not converted to "
    "SI. A PDF may cover several models: check each fact's page. Tables, drawings and text "
    "inside images are not read."
)


# =============================================================================================
# _pdf_facts: turns a parsed PDF (the worker's record) into facts and issues
# =============================================================================================
def test_TC_F1_all_six_messages_from_one_record(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strategy: every message. One record holds a contents page, a line with two values, a
    blank page and more values than the (lowered) limit, so all six issues appear in order."""
    crowded = "\n".join(
        ["Lubrication", TWO_ON_ONE_LINE] + [f"Item {n} {DOTS} value {n}" for n in range(5)]
    )
    rec = record(page(1, CONTENTS), page(2, crowded, ["T100"]), page(3, ""), images=2)
    monkeypatch.setattr(pipeline_module, "MAX_FACTS_PER_PDF", 3)
    facts, issues = facts_of(rec)
    assert len(facts) == 3  # the candidate and two values; three values dropped
    assert messages(issues) == [
        (
            "info",
            (
                "Read 3 page(s), 38 word(s): 2 labelled value(s) and 1 part-number "
                "candidate(s). 2 embedded image(s) were found and not imported."
            ),
        ),
        ("warning", EVIDENCE),
        ("warning", "No text on page(s) 3: a scan or a blank page. There is no OCR."),
        (
            "info",
            (
                "Page(s) 1 look like contents or quantity lists (bare whole numbers) and gave "
                "no facts."
            ),
        ),
        ("warning", "1 line(s) hold two labelled values and were left out."),
        ("warning", "Stopped at 3 facts; 3 more labelled value(s) were left out."),
    ]
    assert all(issue.ref == SOURCE_ID for issue in issues)


# ---------------------------------------------------------------------------------------------
# TC_F2 (_pdf_facts): each message has its own trigger
# Strategy:    every message.
# Description: TC_F1 makes all six messages from one record; this case checks that each
#              message comes from its own cause, with the smallest input that causes it.
# Scenario:    _pdf_facts reads the record and adds an issue for each condition it finds:
#              a summary, the evidence notice, a page without text, a contents page, a line
#              with two values, and the fact limit being reached.
# Input:       six records, one per run:
#              [summary], [evidence_notice]  a two-value data sheet (SHEET)
#              [no_text]                     one empty page
#              [contents_page]               "Table of Contents" / "INTRODUCTION .... 2"
#              [two_values_one_line]         "Oil .... A  Grease .... B"
#              [fact_limit]                  SHEET plus candidate T100, limit lowered to 1
# Expected:    the issue list holds a message of the given severity that starts with:
#              info "Read 1 page(s)" / warning "PDF catalog evidence; ..." /
#              warning "No text on page(s) 1" / info "Page(s) 1 look like" /
#              warning "1 line(s) hold two labelled values" /
#              warning "Stopped at 1 facts; 2 more labelled value(s)"
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("rec", "limit", "expected"),
    [
        pytest.param(record(page(1, SHEET)), None, ("info", "Read 1 page(s)"), id="summary"),
        pytest.param(record(page(1, SHEET)), None, ("warning", EVIDENCE), id="evidence_notice"),
        pytest.param(record(page(1, "")), None, ("warning", "No text on page(s) 1"), id="no_text"),
        pytest.param(
            record(page(1, CONTENTS)), None, ("info", "Page(s) 1 look like"), id="contents_page"
        ),
        pytest.param(
            record(page(1, TWO_ON_ONE_LINE)),
            None,
            ("warning", "1 line(s) hold two labelled values"),
            id="two_values_one_line",
        ),
        pytest.param(
            record(page(1, SHEET, ["T100"])),
            1,
            ("warning", "Stopped at 1 facts; 2 more labelled value(s)"),
            id="fact_limit",
        ),
    ],
)
def test_TC_F2_each_message_has_its_own_trigger(
    monkeypatch: pytest.MonkeyPatch,
    rec: dict[str, Any],
    limit: int | None,
    expected: tuple[str, str],
) -> None:
    """Strategy: every message. Each message, from the smallest input that causes it."""
    if limit is not None:
        monkeypatch.setattr(pipeline_module, "MAX_FACTS_PER_PDF", limit)
    _, issues = facts_of(rec)
    severity, start = expected
    assert any(i.severity == severity and i.message.startswith(start) for i in issues)


# Result of TC_F2 (2026-11-12): 6 of 6 inputs PASSED. Each message appears for its own cause,
# with the expected severity, so none of the six depends on another one being present.
# ---------------------------------------------------------------------------------------------


# ---------------------------------------------------------------------------------------------
# TC_F3 (_pdf_facts): 600 values overflow the 500-fact limit
# Strategy:    overflow.
# Description: a catalog prints more labelled values than one PDF may give
#              (MAX_FACTS_PER_PDF = 500, decision 0034).
# Scenario:    _pdf_facts adds the part-number candidates first, then labelled values until
#              it holds 500 facts, counts the rest as dropped and warns about them.
# Input:       one page: "Model T100 sheet", then 600 lines "Value n .... n mm"
#              (n = 0..599), with the candidate T100.
# Expected:    exactly 500 facts; the first is candidate_t100 (never dropped); the last issue
#              is "Stopped at 500 facts; 101 more labelled value(s) were left out."
#              (1 candidate + 499 values kept, 600 - 499 = 101 dropped).
# ---------------------------------------------------------------------------------------------


def test_TC_F3_600_values_overflow_the_500_fact_limit() -> None:
    """Strategy: overflow. 600 labelled values and a candidate against the real limit of 500."""
    lines = [f"Value {n} {DOTS} {n} mm" for n in range(600)]
    rec = record(page(1, "\n".join(["Model T100 sheet", *lines]), ["T100"]))
    facts, issues = facts_of(rec)
    assert pipeline_module.MAX_FACTS_PER_PDF == 500
    assert len(facts) == 500
    assert short_keys(facts)[0] == "candidate_t100"  # the candidate is never dropped
    assert issues[-1].message == "Stopped at 500 facts; 101 more labelled value(s) were left out."


# Result of TC_F3 (2026-11-12): PASSED. The limit held at 500, the candidate came first, and
# the dropped count was reported exactly; the overflow did not crash or lose the candidate.
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("length", [1, 190, 191, 192, 1_000, 100_000])
def test_TC_F4_long_values_are_kept_whole_and_quotes_cut_to_200(length: int) -> None:
    """Strategy: overflow. A value of 1 to 100,000 characters against the 200-character quote
    ("Long ... " is 9 characters, so 191 is the first value that is cut)."""
    value = "x" * length
    (fact,) = facts_of(record(page(1, f"Long {DOTS} {value}")))[0]
    assert fact.value == value  # the value is kept whole
    assert len(fact.citations[0].quote or "") == min(200, 9 + length)


@pytest.mark.parametrize("times", [2, 50, 400])
def test_TC_F5_the_same_label_repeated_gives_unique_keys(times: int) -> None:
    """Strategy: repetition. "Weight .... 108 lbs." printed 2, 50 and 400 times on one page."""
    rec = record(page(1, "\n".join(["Specs", *[f"Weight {DOTS} 108 lbs."] * times])))
    keys = short_keys(facts_of(rec)[0])
    assert len(keys) == len(set(keys)) == times
    assert keys[:2] == ["p001_specs_weight", "p001_specs_weight_2"]
    assert keys[-1] == f"p001_specs_weight_{times}"


def test_TC_F6_a_candidate_on_20_pages_cites_its_first_3() -> None:
    """Strategy: repetition. The same part number printed on 20 pages."""
    rec = record(*[page(n, "Model T100", ["T100"]) for n in range(1, 21)])
    (candidate,) = facts_of(rec)[0]
    assert [c.locator for c in candidate.citations] == ["PDF p. 1", "PDF p. 2", "PDF p. 3"]


def test_TC_F7_the_same_record_1000_times_gives_the_same_result() -> None:
    """Strategy: repetition. One record read 1,000 times: no state is carried between calls."""
    rec = record(page(1, SHEET, ["T100"]), page(2, CONTENTS))
    first = facts_of(rec)
    assert all(facts_of(rec) == first for _ in range(999))


@pytest.mark.parametrize(
    ("label", "candidate"),
    [
        pytest.param("!!!", "---", id="exclamation_marks"),
        pytest.param("###", "###", id="hashes"),
        pytest.param("@@@", "***", id="at_signs"),
        pytest.param("§§§", "///", id="section_signs"),
    ],
)
def test_TC_F8_labels_without_letters_still_give_valid_keys(label: str, candidate: str) -> None:
    """Strategy: invalid output. Labels and candidates with no letter or digit would give an
    empty key part; they become "value" and "unnamed" instead."""
    facts, _ = facts_of(record(page(7, f"{label} {DOTS} 5\n{label} {DOTS} 6", [candidate])))
    assert short_keys(facts) == ["candidate_unnamed", "p007_value", "p007_value_2"]
    assert all(KEY.match(fact.key) and fact.citations for fact in facts)


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param({"status": "extracted", "summary": record()["summary"]}, id="no_pages"),
        pytest.param({"status": "extracted", "pages": []}, id="no_summary"),
        pytest.param(record(page("x", "Model T1", ["T1"])), id="page_number_not_a_number"),
        pytest.param({"status": "extracted", "summary": {}, "pages": 7}, id="pages_not_a_list"),
    ],
)
def test_TC_F9_malformed_records_raise_instead_of_half_a_result(bad: dict[str, Any]) -> None:
    """Strategy: invalid output. A malformed record must raise (``_pdf`` turns that into one
    error issue), never return a partial list of facts."""
    with pytest.raises((KeyError, ValueError, TypeError)):
        facts_of(bad)


@pytest.mark.parametrize(
    ("rec", "pages", "expected_issues"),
    [
        pytest.param(record(), 0, 2, id="zero_pages"),
        pytest.param(record(page(1, "")), 1, 3, id="one_empty_page"),
        pytest.param(record(page(1, "   \n\t ")), 1, 3, id="one_whitespace_page"),
    ],
)
def test_TC_F10_too_small_a_pdf_gives_no_facts(
    rec: dict[str, Any], pages: int, expected_issues: int
) -> None:
    """Strategy: too small. A PDF with no pages, and one whose only page has no text."""
    facts, issues = facts_of(rec)
    assert facts == []
    assert issues[0].message == (
        f"Read {pages} page(s), 0 word(s): 0 labelled value(s) and 0 part-number "
        "candidate(s). 0 embedded image(s) were found and not imported."
    )
    assert len(issues) == expected_issues


@pytest.mark.parametrize("count", [0, 1, 10**6, 10**12, 2**63])
def test_TC_F11_extreme_summary_counts_are_reported_exactly(count: int) -> None:
    """Strategy: too large / too small. Word and image counts from 0 to 2**63 are printed as
    given, with no rounding or overflow."""
    rec = record(page(1, SHEET))
    rec["summary"] |= {"word_count": count, "image_count": count}
    info = facts_of(rec)[1][0].message
    assert f"{count} word(s)" in info
    assert f"{count} embedded image(s)" in info


# =============================================================================================
# _pdf: checks the file, runs the reader and turns every failure into one error issue
# =============================================================================================
@dataclass
class Env:
    data: Path
    file: Path
    reader: Mock
    pipeline: CatalogPipeline

    def source(self, **changes: Any) -> Source:
        given = Source(
            source_id=SOURCE_ID,
            kind="file",
            input_type=InputType.PDF_CATALOG,
            uri=URI,
            sha256=hashlib.sha256(self.file.read_bytes()).hexdigest(),
            retrieved_at=NOW,
        )
        return given.model_copy(update=changes)


@pytest.fixture
def env(tmp_path: Path) -> Env:
    """A data folder with one PDF and a faked reader that answers with a two-value sheet."""
    data = tmp_path / "data"
    file = data / URI
    file.parent.mkdir(parents=True)
    file.write_bytes(b"%PDF-1.4 stand-in; the reader is faked")
    (tmp_path / "outside.pdf").write_bytes(b"%PDF")
    reader = Mock()
    reader.read.return_value = record(page(1, SHEET, ["T100"]))
    pipeline = CatalogPipeline(Mock(), clock=lambda: NOW, pdf_reader=reader, data_dir=data)
    return Env(data, file, reader, pipeline)


def assert_one_error(result: Result, message: str) -> None:
    facts, issues = result
    assert facts == []
    assert [(i.severity, i.ref, i.message) for i in issues] == [("error", SOURCE_ID, message)]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        pytest.param(
            {"kind": "url", "uri": "https://example.com/c.pdf", "sha256": None},
            "Pipeline D reads a PDF catalog from a file. Save it under the data folder "
            "(data/machines/<machine>/inputs/documents/) and give that file.",
            id="url_not_a_file",
        ),
        pytest.param(
            {"uri": "../outside.pdf", "sha256": None}, NOT_IN_DATA, id="outside_the_data_folder"
        ),
        pytest.param({"uri": "machines/absent.pdf", "sha256": None}, NOT_IN_DATA, id="missing"),
        pytest.param({"uri": "machines", "sha256": None}, NOT_IN_DATA, id="a_folder_not_a_file"),
        pytest.param(
            {"sha256": "0" * 64},
            "The PDF file changed since it was added (its SHA-256 differs).",
            id="changed_since_added",
        ),
    ],
)
def test_TC_P1_bad_sources_are_refused_before_the_reader_runs(
    env: Env, changes: dict[str, Any], message: str
) -> None:
    """Strategy: every message. The five checks before reading, each from its own input."""
    assert_one_error(env.pipeline._pdf(env.source(**changes)), message)
    env.reader.read.assert_not_called()


@pytest.mark.parametrize(
    ("response", "message"),
    [
        pytest.param(
            {"status": "error", "message": "Could not read the PDF (PDFSyntaxError)."},
            "Could not read the PDF (PDFSyntaxError).",
            id="reader_error_with_message",
        ),
        pytest.param({"status": "error"}, "PDF extraction failed.", id="reader_error_no_message"),
        pytest.param(
            {"status": "extracted", "summary": {}, "pages": [{"page": 1}]},
            "Invalid PDF extraction response; no facts were imported.",
            id="extracted_but_malformed",
        ),
    ],
)
def test_TC_P2_reader_failures_give_their_messages(
    env: Env, response: dict[str, Any], message: str
) -> None:
    """Strategy: every message. The three messages that come after the reader runs."""
    env.reader.read.return_value = response
    assert_one_error(env.pipeline._pdf(env.source()), message)


def test_TC_P3_a_10000_page_response_is_capped_at_500_facts(env: Env) -> None:
    """Strategy: overflow. The reader answers with 10,000 pages, one value each."""
    env.reader.read.return_value = record(*[page(n, f"Item {DOTS} {n}") for n in range(1, 10_001)])
    facts, issues = env.pipeline._pdf(env.source())
    assert len(facts) == 500
    assert issues[-1].message == "Stopped at 500 facts; 9500 more labelled value(s) were left out."


# ---------------------------------------------------------------------------------------------
# TC_P4 (_pdf): a very long reader message is passed whole
# Strategy:    overflow.
# Description: the PDF reader fails and answers with an error message far longer than any
#              real one, to check that _pdf neither crashes nor cuts it.
# Scenario:    _pdf checks the file, calls the reader, sees status "error" and returns no
#              facts and one error issue carrying the reader's message.
# Input:       a valid source (file in the data folder, correct SHA-256); the faked reader
#              returns {"status": "error", "message": "E" * length}, with
#              length = [2000] and [100000].
# Expected:    no facts; exactly one issue: ("error", "src-sheet", "E" * length), with the
#              message the same length as the reader's.
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("length", [2_000, 100_000])
def test_TC_P4_a_very_long_reader_message_is_passed_whole(env: Env, length: int) -> None:
    """Strategy: overflow. A 2,000- and a 100,000-character error message from the reader."""
    env.reader.read.return_value = {"status": "error", "message": "E" * length}
    assert_one_error(env.pipeline._pdf(env.source()), "E" * length)


# Result of TC_P4 (2026-11-12): 2 of 2 inputs PASSED. Both messages came back whole as one
# error issue. Nothing limits their length: a reviewer may see a very long message.
# ---------------------------------------------------------------------------------------------


# ---------------------------------------------------------------------------------------------
# TC_P5 (_pdf): a file name too long is "not in the data folder"
# Strategy:    overflow.
# Description: a file name longer than Windows' limit of 255 characters per name.
# Scenario:    _pdf resolves the path inside the data folder and asks whether it is a file;
#              Windows cannot hold such a name, so no file is found and _pdf refuses the
#              source before calling the reader.
# Input:       uri = "a" * length + ".pdf", with length = [256], [300] and [1000];
#              no SHA-256.
# Expected:    no facts; exactly one issue:
#              ("error", "src-sheet", "The PDF file is not in the data folder.")
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("length", [256, 300, 1_000])
def test_TC_P5_a_file_name_too_long_is_not_in_the_data_folder(env: Env, length: int) -> None:
    """Strategy: overflow. A file name longer than Windows' 255-character limit."""
    source = env.source(uri="a" * length + ".pdf", sha256=None)
    assert_one_error(env.pipeline._pdf(source), NOT_IN_DATA)


# Result of TC_P5 (2026-11-12): 3 of 3 inputs PASSED. A long file name gives the error issue.
# A long whole path (40,205 characters) does not: it crashes, see TC_P6.
# ---------------------------------------------------------------------------------------------


@pytest.mark.xfail(
    raises=ValueError,
    strict=True,
    reason="DEFECT FOUND: bad path crashes _pdf with ValueError",
)
@pytest.mark.parametrize(
    "uri",
    [
        pytest.param("/".join(["d" * 200] * 200) + "/x.pdf", id="path_40205_chars"),
        pytest.param("x\x00.pdf", id="nul_byte_in_path"),
    ],
)
def test_TC_P6_an_overflowing_path_gives_an_issue_not_a_crash(env: Env, uri: str) -> None:
    """Strategy: overflow. ``Path.is_file()`` raises ``ValueError`` for these paths ("path too
    long for Windows", "embedded null character in path"); neither ``_pdf`` nor ``run``
    catches it, so the whole job fails. Remove the xfail once ``_pdf`` answers NOT_IN_DATA."""
    assert_one_error(env.pipeline._pdf(env.source(uri=uri, sha256=None)), NOT_IN_DATA)


def test_TC_P7_the_same_source_1000_times_gives_the_same_result(env: Env) -> None:
    """Strategy: repetition. The same source 1,000 times; the file is read afresh each time."""
    first = env.pipeline._pdf(env.source())
    assert all(env.pipeline._pdf(env.source()) == first for _ in range(999))
    assert env.reader.read.call_count == 1_000  # no cache


def test_TC_P8_a_failure_between_successes_leaves_no_trace(env: Env) -> None:
    """Strategy: repetition. Success, failure, success: the third result equals the first."""
    first = env.pipeline._pdf(env.source())
    env.reader.read.side_effect = [
        {"status": "error", "message": "blocked"},
        record(page(1, SHEET, ["T100"])),
    ]
    assert_one_error(env.pipeline._pdf(env.source()), "blocked")
    assert env.pipeline._pdf(env.source()) == first


@pytest.mark.parametrize(
    "response",
    [
        pytest.param(None, id="none"),
        pytest.param([], id="a_list"),
        pytest.param("extracted", id="a_string"),
        pytest.param({"status": "extracted"}, id="status_only"),
        pytest.param(
            record(page(1, SHEET))
            | {"summary": {"page_count": "many", "word_count": 1, "image_count": 0}},
            id="page_count_not_a_number",
        ),
    ],
)
def test_TC_P9_invalid_reader_output_never_becomes_facts(env: Env, response: Any) -> None:
    """Strategy: invalid output. The reader returns things that are not a worker record."""
    env.reader.read.return_value = response
    facts, issues = env.pipeline._pdf(env.source())
    assert facts == []
    assert [i.severity for i in issues] == ["error"]


def test_TC_P10_an_empty_pdf_file_gives_no_facts(env: Env) -> None:
    """Strategy: too small. A 0-byte file with the right hash; the reader finds 0 pages."""
    env.file.write_bytes(b"")
    env.reader.read.return_value = record()
    facts, issues = env.pipeline._pdf(env.source())
    assert facts == []
    assert [i.severity for i in issues] == ["info", "warning"]
    assert issues[0].message.startswith("Read 0 page(s), 0 word(s)")


@pytest.mark.parametrize("uri", [pytest.param("", id="empty"), pytest.param(".", id="dot")])
def test_TC_P11_an_empty_path_is_not_in_the_data_folder(env: Env, uri: str) -> None:
    """Strategy: too small. A path of no characters, and "." (the data folder itself)."""
    assert_one_error(env.pipeline._pdf(env.source(uri=uri, sha256=None)), NOT_IN_DATA)
