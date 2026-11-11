"""Offline Pipeline D integration checks; also runnable with stdlib unittest."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from moonwalkers.contracts.pipeline_result import InputType, PipelineId, PipelineResult, Source
from moonwalkers.kb import JsonKnowledgeBase
from moonwalkers.orchestrator import JobRequest, MachineHint, Orchestrator
from moonwalkers.pipelines import default_pipelines, stub_pipelines
from moonwalkers.pipelines.d import pipeline as pipeline_module
from moonwalkers.pipelines.d.browser_worker import collect
from moonwalkers.pipelines.d.catalog_facts import labelled_values, line_with, slug
from moonwalkers.pipelines.d.octopart import candidates, extract, input_url
from moonwalkers.pipelines.d.pipeline import BrowserReader, CatalogPipeline, CatalogReader

NOW = datetime(2026, 11, 4, tzinfo=UTC)
URL = "https://octopart.com/abc-1-maker-123"
SEARCH = "https://octopart.com/search?q=ABC-1"
PRODUCT = {
    "@type": "Product",
    "mpn": "ABC-1",
    "manufacturer": {"name": "Test Maker"},
    "description": "Synthetic part for offline tests",
    "offers": {"price": "1.23", "priceCurrency": "USD"},
}


def html(product: object = PRODUCT) -> str:
    return '<script type="application/ld+json">' + json.dumps(product) + "</script>"


def source(name: str = "input", uri: str = SEARCH) -> Source:
    return Source(
        source_id=name,
        kind="url",
        input_type=InputType.ONLINE_RESOURCE,
        uri=uri,
        retrieved_at=NOW,
    )


class ParsingTests(unittest.TestCase):
    def test_exact_links_preserve_punctuation_and_deduplicate(self) -> None:
        links = f'<a href="{URL}"><span>ABC-1</span></a>' * 2
        links += '<a href="/abc1-maker-456">ABC1</a>'
        links += '<a href="https://evil.test/abc-1-789">ABC-1</a>'
        self.assertEqual(candidates(links, "abc-1", SEARCH), [URL])

    def test_url_validation(self) -> None:
        for uri in (
            "http://octopart.com/a-123",
            "https://octopart.com.evil.test/a-123",
            "https://user:pass@octopart.com/a-123",
            "https://octopart.com:8443/a-123",
            "https://octopart.com/search",
            "https://octopart.com/search?q=A&q=B",
            "file:///tmp/x",
            "https://127.0.0.1/a-123",
        ):
            with self.subTest(uri=uri), self.assertRaises(ValueError):
                input_url(uri)
        self.assertEqual(input_url(SEARCH), (SEARCH, "ABC-1"))

    def test_product_and_datasheets(self) -> None:
        page = html({"@graph": [PRODUCT]}) + '<a href="/sheet.pdf">Datasheet</a>'
        result = extract(page, "ABC-1", URL)
        self.assertEqual(result["status"], "extracted")
        self.assertEqual(result["manufacturer"], "Test Maker")
        self.assertEqual(result["datasheets"], ["https://octopart.com/sheet.pdf"])
        self.assertEqual(result["offers"]["priceCurrency"], "USD")

    def test_malformed_missing_and_wrong_product_are_not_success(self) -> None:
        for page in (
            "<h1>ABC-1</h1>",
            html({"@type": "Product", "mpn": "ABC1"}),
            '<script type="application/ld+json">{broken</script>',
        ):
            self.assertEqual(extract(page, "ABC-1", URL)["status"], "needs_review")

    def test_distinct_manufacturers_require_review(self) -> None:
        other = dict(PRODUCT, manufacturer={"name": "Other Maker"})
        self.assertEqual(extract(html([PRODUCT, other]), None, URL)["status"], "needs_review")
        self.assertEqual(extract(html([PRODUCT, PRODUCT]), None, URL)["status"], "extracted")


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reader = Mock()
        self.reader.read.return_value = extract(html(), "ABC-1", URL)
        self.pdf_reader = Mock()
        self.pipeline = CatalogPipeline(self.reader, clock=lambda: NOW, pdf_reader=self.pdf_reader)

    def test_registration_keeps_test_stubs(self) -> None:
        self.assertIsInstance(default_pipelines()[PipelineId.D], CatalogPipeline)
        self.assertTrue(stub_pipelines()[PipelineId.D].stub)

    def test_cited_contract_with_no_machine_identity_or_storage(self) -> None:
        given = source()
        result = self.pipeline.run("job-d", [given])
        PipelineResult.model_validate_json(result.model_dump_json())
        self.assertEqual(result.result_id, "res-job-d-d")
        self.assertIsNone(result.identity)
        self.assertEqual(result.parts, [])
        self.assertTrue(result.needs_human_review)
        self.assertEqual(result.sources[0], given)
        self.assertEqual(result.sources[1].uri, URL)
        for fact in result.facts:
            self.assertEqual(fact.citations[0].source_id, result.sources[1].source_id)
        offers = next(f for f in result.facts if f.key.endswith("offers_json"))
        self.assertIsInstance(offers.value, str)
        self.assertIsNone(offers.unit)

    def test_multiple_inputs_get_separate_fact_keys(self) -> None:
        result = self.pipeline.run("job", [source("one"), source("two")])
        keys = [fact.key for fact in result.facts]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(result.sources), 4)

    def test_unsupported_inputs_do_not_start_browser(self) -> None:
        inputs = [source(uri="https://example.com/a-123")]
        inputs.append(source("pdf").model_copy(update={"input_type": InputType.PDF_CATALOG}))
        result = self.pipeline.run("job", inputs)
        self.reader.read.assert_not_called()
        self.pdf_reader.read.assert_not_called()  # a PDF given as a URL is not downloaded
        self.assertEqual(result.facts, [])
        self.assertEqual([i.severity for i in result.issues], ["error", "error"])

    def test_ambiguity_and_errors_never_become_facts(self) -> None:
        for status in ("ambiguous", "error", "needs_review"):
            self.reader.read.return_value = {"status": status, "message": "Check page"}
            result = self.pipeline.run("job", [source()])
            self.assertFalse(result.facts)
            self.assertTrue(result.issues)

    def test_mismatched_or_untrusted_response_never_becomes_facts(self) -> None:
        for extra in ({"mpn": "ABC1"}, {"url": "https://evil.test/a-123"}, {"mpn": None}):
            self.reader.read.return_value = extract(html(), "ABC-1", URL) | extra
            result = self.pipeline.run("job", [source()])
            self.assertFalse(result.facts)
            self.assertEqual(len(result.sources), 1)
            self.assertEqual(result.issues[0].severity, "error")

    def test_partial_failure_preserves_successful_input(self) -> None:
        self.reader.read.side_effect = [
            extract(html(), "ABC-1", URL),
            {"status": "error", "message": "blocked"},
        ]
        result = self.pipeline.run("job", [source("one"), source("two")])
        self.assertTrue(result.facts)
        self.assertTrue(any(i.ref == "two" and i.severity == "error" for i in result.issues))

    def test_orchestrator_routes_and_stores_the_cited_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            kb = JsonKnowledgeBase(Path(directory) / "kb")
            orchestrator = Orchestrator(kb, {PipelineId.D: self.pipeline}, clock=lambda: NOW)
            job = orchestrator.run_job(
                JobRequest(
                    job_id="octopart-test",
                    sources=[source()],
                    machine=MachineHint(manufacturer="Test", model="Machine"),
                )
            )
            stored = kb.get_result("res-octopart-test-d")
            self.assertIsNotNone(stored)
            self.assertTrue(stored.facts)
            self.assertEqual(job.twin.machine_key, "test/machine")
            self.assertEqual(job.twin.status, "needs_review")

    def test_empty_input_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.pipeline.run("job", [])


class AdapterTests(unittest.TestCase):
    def test_missing_configuration_does_not_launch(self) -> None:
        with patch.dict("os.environ", {}, clear=True), patch("subprocess.run") as run:
            self.assertEqual(BrowserReader().read(URL)["status"], "error")
            run.assert_not_called()

    def test_worker_protocol_timeout_and_bad_json(self) -> None:
        reader = BrowserReader(python="C:/browser env/python.exe", timeout=10)
        with patch("subprocess.run") as run:
            run.return_value = SimpleNamespace(returncode=0, stdout='{"status":"needs_review"}')
            self.assertEqual(reader.read(URL)["status"], "needs_review")
            args, kwargs = run.call_args
            self.assertEqual(args[0][0], "C:/browser env/python.exe")
            self.assertEqual(json.loads(kwargs["input"]), {"url": URL})
            self.assertEqual(kwargs["timeout"], 10)
            self.assertNotIn("shell", kwargs)
            run.return_value = SimpleNamespace(returncode=0, stdout="bad")
            self.assertEqual(reader.read(URL)["status"], "error")
            run.side_effect = subprocess.TimeoutExpired("worker", 10)
            self.assertIn("timed out", reader.read(URL)["message"])


class BrowserTests(unittest.TestCase):
    def page(self, contents: list[str]) -> Mock:
        page = Mock()
        page.goto.return_value = SimpleNamespace(status=200)
        page.title.return_value = "Octopart"
        page.locator.return_value.inner_text.return_value = "Synthetic part page"
        page.content.side_effect = contents
        page.url = URL
        return page

    def test_search_follows_one_exact_link(self) -> None:
        page = self.page([f'<a href="{URL}">ABC-1</a>', html()])
        result = collect(page, SEARCH)
        self.assertEqual(result["status"], "extracted")
        self.assertEqual(page.goto.call_count, 2)
        self.assertEqual(page.goto.call_args.args[0], URL)
        self.assertIn("retrieved_at", result)

    def test_search_does_not_choose_between_manufacturers(self) -> None:
        page = self.page([f'<a href="{URL}">ABC-1</a><a href="/abc-1-other-456">ABC-1</a>'])
        self.assertEqual(collect(page, SEARCH)["status"], "ambiguous")
        self.assertEqual(page.goto.call_count, 1)

    def test_access_challenge_and_http_error_stop(self) -> None:
        page = self.page([html()])
        page.title.return_value = "Verify you are human"
        with self.assertRaises(ValueError):
            collect(page, URL)
        page.content.assert_not_called()
        page.goto.return_value = SimpleNamespace(status=403)
        with self.assertRaises(ValueError):
            collect(page, URL)


DOTS = "." * 30
SHEET = "\n".join(
    [
        "MACHINE DATA SHEET",
        "MODEL T100 BENCH DRILL",
        "Product Dimensions:",
        f"Weight{DOTS} 108 lbs.",
        "Shipping Dimensions:",
        f"Weight{DOTS} 116 lbs.",
        "Operation Information",
        f"Spindle Travel {DOTS} 3-1/4 in.",
        f"Number of Spindle Speeds{DOTS}12",
        f"Number of Spindle Speeds{DOTS}12",
    ]
)
CONTENTS = "\n".join(["Table of Contents", f"INTRODUCTION {DOTS} 2", f"Weight {DOTS} 9 lbs."])
PARTS = "\n".join(f"Hex Wrench {size}mm {DOTS} 1" for size in range(3, 9))


def record(*texts: str, candidates: tuple[str, ...] = ("T100",)) -> dict:
    """What catalog_worker.py returns for a PDF with these pages."""
    pages = [
        {
            "page": number,
            "text": text,
            "part_number_candidates": [c for c in candidates if c in text],
            "image_count": 1,
            "warnings": [],
        }
        for number, text in enumerate(texts, start=1)
    ]
    summary = {
        "page_count": len(pages),
        "word_count": sum(len(text.split()) for text in texts),
        "image_count": len(pages),
        "exported_image_count": len(pages),
    }
    return {"status": "extracted", "summary": summary, "pages": pages}


class CatalogFactsTests(unittest.TestCase):
    def test_leader_lines_carry_the_heading_above_them(self) -> None:
        reading = labelled_values(record(SHEET)["pages"])
        found = [(v.page, v.heading, v.label, v.value) for v in reading.values]
        self.assertEqual(
            found[:3],
            [
                (1, "Product Dimensions", "Weight", "108 lbs."),
                (1, "Shipping Dimensions", "Weight", "116 lbs."),
                (1, "Operation Information", "Spindle Travel", "3-1/4 in."),
            ],
        )
        self.assertEqual(reading.values[2].quote, "Spindle Travel ... 3-1/4 in.")
        self.assertEqual((reading.number_list_pages, reading.unclear_lines), ([], 0))

    def test_contents_pages_and_number_lists_give_no_values(self) -> None:
        reading = labelled_values(record(CONTENTS, PARTS, SHEET)["pages"])
        self.assertEqual(reading.number_list_pages, [1, 2])
        self.assertEqual({v.page for v in reading.values}, {3})

    def test_a_long_line_is_not_a_heading_and_two_values_on_a_line_are_left_out(self) -> None:
        lines = [
            "Lubrication",
            "x" * 61,
            f"Oil Type {DOTS} ISO 68",
            f"Oil {DOTS} A  Grease {DOTS} B",
        ]
        reading = labelled_values(record("\n".join(lines))["pages"])
        found = [(v.heading, v.label) for v in reading.values]
        self.assertEqual(found, [("Lubrication", "Oil Type")])
        self.assertEqual(reading.unclear_lines, 1)

    def test_slug_and_line_with(self) -> None:
        self.assertEqual(slug("Max. Table Tilt (Left/Right) #2"), "max_table_tilt_left_right_2")
        self.assertEqual(slug("..."), "")
        self.assertLessEqual(len(slug("a b " * 40)), 40)
        self.assertEqual(line_with(SHEET, "T100"), "MODEL T100 BENCH DRILL")
        self.assertEqual(line_with(SHEET, "116"), "Weight ... 116 lbs.")
        self.assertIsNone(line_with(SHEET, "absent"))


class PdfCatalogTests(unittest.TestCase):
    URI = "machines/test-drill/inputs/documents/sheet.pdf"

    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.data = Path(folder.name) / "data"
        self.file = self.data / self.URI
        self.file.parent.mkdir(parents=True)
        self.file.write_bytes(b"%PDF-1.4 stand-in bytes; the reader is faked")
        self.browser = Mock()
        self.reader = Mock()
        self.reader.read.return_value = record(SHEET)
        self.pipeline = CatalogPipeline(
            self.browser, clock=lambda: NOW, pdf_reader=self.reader, data_dir=self.data
        )

    def pdf(self, name: str = "sheet", **changes: object) -> Source:
        given = Source(
            source_id=name,
            kind="file",
            input_type=InputType.PDF_CATALOG,
            uri=self.URI,
            sha256=hashlib.sha256(self.file.read_bytes()).hexdigest(),
            retrieved_at=NOW,
        )
        return given.model_copy(update=changes)

    def test_labelled_values_become_facts_cited_to_their_page(self) -> None:
        given = self.pdf()
        result = self.pipeline.run("job-pdf", [given])
        PipelineResult.model_validate_json(result.model_dump_json())
        self.reader.read.assert_called_once_with(self.file.resolve())
        self.browser.read.assert_not_called()
        self.assertEqual(result.sources, [given])
        self.assertEqual(result.input_types, [InputType.PDF_CATALOG])
        self.assertIsNone(result.identity)
        self.assertEqual((result.parts, result.joints, result.control), ([], [], []))
        self.assertTrue(result.needs_human_review)
        by_key = {fact.key.split("_", 2)[2]: fact for fact in result.facts}
        travel = by_key["p001_operation_information_spindle_travel"]
        self.assertEqual(
            (travel.value, travel.original, travel.unit), ("3-1/4 in.", "3-1/4 in.", None)
        )
        self.assertEqual(travel.confidence, 0.7)
        (citation,) = travel.citations
        self.assertEqual(
            (citation.source_id, citation.locator, citation.quote),
            ("sheet", "PDF p. 1", "Spindle Travel ... 3-1/4 in."),
        )
        self.assertEqual([i.severity for i in result.issues], ["info", "warning"])
        self.assertIn("5 labelled value(s) and 1 part-number candidate", result.issues[0].message)
        self.assertIn("not converted to SI", result.issues[1].message)

    def test_the_same_label_never_shares_a_key(self) -> None:
        result = self.pipeline.run("job", [self.pdf()])
        keys = [fact.key.split("_", 2)[2] for fact in result.facts]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertIn("p001_product_dimensions_weight", keys)
        self.assertIn("p001_shipping_dimensions_weight", keys)
        self.assertIn("p001_operation_information_number_of_spindle_speeds_2", keys)
        for fact in result.facts:
            self.assertRegex(fact.key, r"^catalog_[0-9a-f]{12}_[a-z0-9_]+$")

    def test_candidates_cite_the_pages_that_print_them(self) -> None:
        self.reader.read.return_value = record(SHEET, "Model T100 parts", "T100", "T100", "T100")
        result = self.pipeline.run("job", [self.pdf()])
        candidate = result.facts[0]
        self.assertTrue(candidate.key.endswith("_candidate_t100"))
        self.assertEqual((candidate.value, candidate.confidence), ("T100", 0.5))
        self.assertEqual(
            [(c.locator, c.quote) for c in candidate.citations],
            [
                ("PDF p. 1", "MODEL T100 BENCH DRILL"),
                ("PDF p. 2", "Model T100 parts"),
                ("PDF p. 3", "T100"),
            ],
        )

    def test_number_lists_and_empty_pages_are_reported_not_imported(self) -> None:
        self.reader.read.return_value = record(CONTENTS, SHEET, "")
        result = self.pipeline.run("job", [self.pdf()])
        self.assertTrue(all(c.locator == "PDF p. 2" for f in result.facts for c in f.citations))
        notes = [(i.severity, i.message) for i in result.issues]
        self.assertTrue(any(s == "warning" and "No text on page(s) 3" in m for s, m in notes))
        self.assertTrue(any(s == "info" and "Page(s) 1 look like contents" in m for s, m in notes))

    def test_a_long_catalog_stops_at_the_limit_and_says_so(self) -> None:
        with patch.object(pipeline_module, "MAX_FACTS_PER_PDF", 3):
            result = self.pipeline.run("job", [self.pdf()])
        self.assertEqual(len(result.facts), 3)
        self.assertTrue(result.facts[0].key.endswith("_candidate_t100"))
        self.assertTrue(any("3 more labelled value(s)" in i.message for i in result.issues))

    def test_files_the_pipeline_may_not_read_never_reach_the_reader(self) -> None:
        outside = self.data.parent / "outside.pdf"
        outside.write_bytes(b"%PDF")
        cases = {
            "url": self.pdf(kind="url", uri="https://example.com/catalog.pdf", sha256=None),
            "outside": self.pdf(uri="../outside.pdf", sha256=None),
            "missing": self.pdf(uri="machines/absent.pdf", sha256=None),
            "changed": self.pdf(sha256="0" * 64),
        }
        for name, given in cases.items():
            with self.subTest(name):
                result = self.pipeline.run("job", [given])
                self.assertEqual(result.facts, [])
                self.assertEqual([(i.severity, i.ref) for i in result.issues], [("error", "sheet")])
        self.reader.read.assert_not_called()

    def test_reader_errors_and_bad_responses_never_become_facts(self) -> None:
        bad = [
            {"status": "error", "message": "Could not read the PDF (PDFSyntaxError)."},
            {"status": "extracted"},
            {"status": "extracted", "summary": {}, "pages": [{"page": "x"}]},
            {"status": "extracted", "summary": record(SHEET)["summary"], "pages": "none"},
        ]
        for response in bad:
            with self.subTest(response=response):
                self.reader.read.return_value = response
                result = self.pipeline.run("job", [self.pdf()])
                self.assertEqual(result.facts, [])
                self.assertEqual([i.severity for i in result.issues], ["error"])
        self.reader.read.return_value = bad[0]
        self.assertIn("PDFSyntaxError", self.pipeline.run("job", [self.pdf()]).issues[0].message)

    def test_a_pdf_and_an_octopart_page_share_one_result(self) -> None:
        self.browser.read.return_value = extract(html(), "ABC-1", URL)
        result = self.pipeline.run("job", [self.pdf(), self.pdf("second"), source("web")])
        keys = [fact.key for fact in result.facts]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(any(key.startswith("octopart_") for key in keys))
        self.assertEqual(sum(key.endswith("_candidate_t100") for key in keys), 2)
        self.assertEqual(result.input_types, [InputType.ONLINE_RESOURCE, InputType.PDF_CATALOG])
        PipelineResult.model_validate_json(result.model_dump_json())

    def test_orchestrator_routes_a_pdf_catalog_and_stores_the_result(self) -> None:
        kb = JsonKnowledgeBase(self.data.parent / "kb")
        orchestrator = Orchestrator(kb, {PipelineId.D: self.pipeline}, clock=lambda: NOW)
        orchestrator.run_job(
            JobRequest(
                job_id="pdf-test",
                sources=[self.pdf()],
                machine=MachineHint(manufacturer="Test", model="Drill"),
            )
        )
        stored = kb.get_result("res-pdf-test-d")
        self.assertIsNotNone(stored)
        self.assertEqual(stored.produced_by, "pipeline-d catalog 0.2.0")
        self.assertEqual(len(stored.facts), 6)


class CatalogReaderTests(unittest.TestCase):
    def test_missing_configuration_does_not_launch(self) -> None:
        with patch.dict("os.environ", {}, clear=True), patch("subprocess.run") as run:
            answer = CatalogReader().read(Path("catalog.pdf"))
            self.assertEqual(answer["status"], "error")
            self.assertIn("MOONWALKERS_OCTOPART_PYTHON", answer["message"])
            run.assert_not_called()

    def test_worker_protocol(self) -> None:
        reader = CatalogReader(python="C:/pipeline d/python.exe", timeout=20)
        path = Path("data") / "catalog.pdf"
        with patch("subprocess.run") as run:
            run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(record(SHEET)))
            self.assertEqual(reader.read(path)["status"], "extracted")
            args, kwargs = run.call_args
            self.assertEqual(args[0][0], "C:/pipeline d/python.exe")
            self.assertEqual(Path(args[0][1]).name, "catalog_worker.py")
            self.assertTrue(Path(args[0][1]).is_file())
            self.assertEqual(json.loads(kwargs["input"]), {"path": str(path)})
            self.assertEqual(kwargs["timeout"], 20)
            self.assertNotIn("shell", kwargs)
            run.return_value = SimpleNamespace(returncode=1, stdout="")
            self.assertEqual(reader.read(path)["status"], "error")
            run.side_effect = subprocess.TimeoutExpired("worker", 20)
            self.assertIn("timed out", reader.read(path)["message"])


if __name__ == "__main__":
    unittest.main()
