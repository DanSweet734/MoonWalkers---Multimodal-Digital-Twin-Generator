"""Offline tests for Pipeline D's standalone catalog PDF parser.

The parser needs pdfminer.six, which lives in Pipeline D's own environment and not in the
backend's, so these tests skip themselves where it is missing. Run them from the repository
root with the environment's Python (docs/setup/pipeline-d-octopart.md):

    C:\\mw-octopart\\Scripts\\python.exe -m unittest discover -s backend/tests
        -p test_catalog_parser.py -v

The PDFs are built here, in memory: no fixture file and no network.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

PARSER = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "moonwalkers"
    / "pipelines"
    / "d"
    / "catalog_parser.py"
)
WORKER = PARSER.with_name("catalog_worker.py")
HAS_PDFMINER = importlib.util.find_spec("pdfminer") is not None


def load_parser() -> ModuleType:
    """Load the file by path: importing the package would need the backend's dependencies."""
    spec = importlib.util.spec_from_file_location("catalog_parser_under_test", PARSER)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stream(dictionary: str, data: bytes) -> bytes:
    head = f"<< {dictionary} /Length {len(data)} >>\nstream\n".encode("ascii")
    return head + data + b"\nendstream"


def make_pdf(pages: list[bytes], image: bytes | None = None) -> bytes:
    """A minimal PDF: one content stream per page, Helvetica, and an optional 2x2 RGB image."""
    count = len(pages)
    font_id = 3
    image_id = 4
    first_page_id = 5
    kids = " ".join(f"{first_page_id + 2 * i} 0 R" for i in range(count))
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {count} >>".encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        stream(
            "/Type /XObject /Subtype /Image /Width 2 /Height 2 "
            "/ColorSpace /DeviceRGB /BitsPerComponent 8",
            image if image is not None else bytes(12),
        ),
    ]
    for index, content in enumerate(pages):
        page_id = first_page_id + 2 * index
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 {font_id} 0 R >> "
                f"/XObject << /Im1 {image_id} 0 R >> >> "
                f"/Contents {page_id + 1} 0 R >>"
            ).encode("ascii")
        )
        objects.append(stream("", content))
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode("ascii")
    out += f"startxref\n{xref}\n%%EOF\n".encode("ascii")
    return bytes(out)


TEXT_PAGE = (
    b"BT /F1 12 Tf 72 700 Td (Part No: ABC-123) Tj ET\n"
    b"BT /F1 12 Tf 72 650 Td (Bench drill, SKU 99-A) Tj ET\n"
    b"q 100 0 0 50 72 500 cm /Im1 Do Q\n"
)
BLANK_PAGE = b""


@unittest.skipUnless(HAS_PDFMINER, "pdfminer.six is not installed in this environment")
class CatalogParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = load_parser()

    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.tmp = Path(folder.name)
        self.pdf = self.tmp / "catalog.pdf"
        self.pdf.write_bytes(make_pdf([TEXT_PAGE, BLANK_PAGE]))
        self.out = self.tmp / "out"

    def test_summary_counts_pages_words_and_images(self) -> None:
        result = self.parser.parse_catalog(self.pdf, self.out)
        self.assertEqual(result["source"], "catalog.pdf")
        self.assertEqual(
            result["summary"],
            {"page_count": 2, "word_count": 7, "image_count": 1, "exported_image_count": 1},
        )

    def test_text_blocks_keep_their_place_on_the_page(self) -> None:
        page = self.parser.parse_catalog(self.pdf, self.out)["pages"][0]
        self.assertEqual((page["width_points"], page["height_points"]), (612, 792))
        self.assertIn("Part No: ABC-123", page["text"])
        block = next(b for b in page["text_blocks"] if "ABC-123" in b["text"])
        x0, y0, x1, y1 = block["bbox"]
        self.assertAlmostEqual(x0, 72, delta=1)
        self.assertTrue(y0 < 700 < y1 + 12, block["bbox"])
        self.assertGreater(x1, x0)

    def test_labelled_part_numbers_are_candidates(self) -> None:
        page = self.parser.parse_catalog(self.pdf, self.out)["pages"][0]
        self.assertEqual(page["part_number_candidates"], ["99-A", "ABC-123"])

    def test_image_is_exported_with_its_size_and_box(self) -> None:
        page = self.parser.parse_catalog(self.pdf, self.out)["pages"][0]
        (image,) = page["images"]
        self.assertEqual((image["width_px"], image["height_px"]), (2, 2))
        self.assertEqual(image["bbox"], [72.0, 500.0, 172.0, 550.0])
        self.assertTrue(image["file"].startswith("images/page_0001_image_0001"))
        self.assertGreater((self.out / image["file"]).stat().st_size, 0)

    def test_blank_page_is_warned_about_and_does_not_stop_the_run(self) -> None:
        page = self.parser.parse_catalog(self.pdf, self.out)["pages"][1]
        self.assertEqual(page["page"], 2)
        self.assertEqual(page["word_count"], 0)
        self.assertEqual(page["images"], [])
        self.assertEqual(len(page["warnings"]), 1)
        self.assertIn("No extractable text", page["warnings"][0])

    def test_written_files_match_the_returned_result(self) -> None:
        result = self.parser.parse_catalog(self.pdf, self.out)
        stored = json.loads((self.out / "catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(stored, result)
        text = (self.out / "catalog.txt").read_text(encoding="utf-8")
        self.assertIn("--- Page 1 ---", text)
        self.assertIn("--- Page 2 ---", text)
        self.assertIn("SKU 99-A", text)

    def test_existing_output_folder_is_refused_and_left_alone(self) -> None:
        self.out.mkdir()
        keep = self.out / "earlier.txt"
        keep.write_text("earlier run", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.parser.parse_catalog(self.pdf, self.out)
        self.assertEqual([p.name for p in self.out.iterdir()], ["earlier.txt"])

    def test_missing_pdf_creates_no_output_folder(self) -> None:
        with self.assertRaises(FileNotFoundError):
            self.parser.parse_catalog(self.tmp / "absent.pdf", self.out)
        self.assertFalse(self.out.exists())

    def test_part_candidates(self) -> None:
        cases = {
            "Part Number: PT33901001": ["PT33901001"],
            "part # 12-34/5": ["12-34/5"],
            "Part No. X.9": ["X.9"],
            "MODEL T33901 14 in.": ["T33901"],
            "Model No: G7943": ["G7943"],
            "Model: T33901. SKU 99-A, model T33901": ["99-A", "T33901"],  # sorted, once each
            "sku-778": [],  # a label needs a space before its value
            "PT33901001 MOTOR PULLEY": [],  # unlabelled table rows are not candidates
            "this model is quiet": [],  # a candidate holds a digit
            "each part number is listed": [],
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(self.parser.part_candidates(text), expected)

    def test_command_line_prints_the_summary(self) -> None:
        argv = ["catalog_parser.py", str(self.pdf), "--output", str(self.out)]
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            sys.argv, saved = argv, sys.argv
            try:
                self.parser.main()
            finally:
                sys.argv = saved
        self.assertIn('"page_count": 2', printed.getvalue())
        self.assertTrue((self.out / "catalog.json").is_file())

    def test_command_line_exits_1_on_a_missing_pdf(self) -> None:
        argv = ["catalog_parser.py", str(self.tmp / "absent.pdf"), "--output", str(self.out)]
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors), self.assertRaises(SystemExit) as raised:
            sys.argv, saved = argv, sys.argv
            try:
                self.parser.main()
            finally:
                sys.argv = saved
        self.assertEqual(raised.exception.code, 1)
        self.assertIn("PDF not found", errors.getvalue())


@unittest.skipUnless(HAS_PDFMINER, "pdfminer.six is not installed in this environment")
class CatalogWorkerTests(unittest.TestCase):
    """The worker as Pipeline D starts it: a script, JSON on stdin, JSON on stdout."""

    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.tmp = Path(folder.name)

    def ask(self, request: str) -> dict:
        completed = subprocess.run(
            [sys.executable, str(WORKER)],
            input=request,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout)

    def test_pages_candidates_and_counts_come_back_and_nothing_is_left_behind(self) -> None:
        pdf = self.tmp / "catalog.pdf"
        pdf.write_bytes(make_pdf([TEXT_PAGE, BLANK_PAGE]))
        answer = self.ask(json.dumps({"path": str(pdf)}))
        self.assertEqual(answer["status"], "extracted")
        self.assertEqual(answer["summary"]["page_count"], 2)
        first, second = answer["pages"]
        self.assertEqual(
            sorted(first), ["image_count", "page", "part_number_candidates", "text", "warnings"]
        )
        self.assertIn("Part No: ABC-123", first["text"])
        self.assertEqual(first["part_number_candidates"], ["99-A", "ABC-123"])
        self.assertEqual((first["image_count"], second["image_count"]), (1, 0))
        self.assertEqual(second["text"], "")
        self.assertEqual([p.name for p in self.tmp.iterdir()], ["catalog.pdf"])

    def test_failures_are_one_error_without_paths(self) -> None:
        broken = self.tmp / "broken.pdf"
        broken.write_bytes(b"not a pdf")
        requests = {
            "missing": json.dumps({"path": str(self.tmp / "absent.pdf")}),
            "broken": json.dumps({"path": str(broken)}),
            "no path": "{}",
            "not json": "catalog.pdf",
        }
        for name, request in requests.items():
            with self.subTest(name):
                answer = self.ask(request)
                self.assertEqual(answer["status"], "error")
                self.assertNotIn(str(self.tmp), answer["message"])


if __name__ == "__main__":
    unittest.main()
