"""Offline Pipeline D integration checks; also runnable with stdlib unittest."""

from __future__ import annotations

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
from moonwalkers.pipelines.d.browser_worker import collect
from moonwalkers.pipelines.d.octopart import candidates, extract, input_url
from moonwalkers.pipelines.d.pipeline import BrowserReader, CatalogPipeline

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
            "http://octopart.com/a-123", "https://octopart.com.evil.test/a-123",
            "https://user:pass@octopart.com/a-123", "https://octopart.com:8443/a-123",
            "https://octopart.com/search", "https://octopart.com/search?q=A&q=B",
            "file:///tmp/x", "https://127.0.0.1/a-123",
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
        for page in ("<h1>ABC-1</h1>", html({"@type": "Product", "mpn": "ABC1"}),
                     '<script type="application/ld+json">{broken</script>'):
            self.assertEqual(extract(page, "ABC-1", URL)["status"], "needs_review")

    def test_distinct_manufacturers_require_review(self) -> None:
        other = dict(PRODUCT, manufacturer={"name": "Other Maker"})
        self.assertEqual(extract(html([PRODUCT, other]), None, URL)["status"], "needs_review")
        self.assertEqual(extract(html([PRODUCT, PRODUCT]), None, URL)["status"], "extracted")


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reader = Mock()
        self.reader.read.return_value = extract(html(), "ABC-1", URL)
        self.pipeline = CatalogPipeline(self.reader, clock=lambda: NOW)

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
        self.reader.read.side_effect = [extract(html(), "ABC-1", URL),
                                      {"status": "error", "message": "blocked"}]
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


if __name__ == "__main__":
    unittest.main()
