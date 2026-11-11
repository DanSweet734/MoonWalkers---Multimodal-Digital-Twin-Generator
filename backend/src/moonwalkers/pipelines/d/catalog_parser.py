"""Simple product catalog PDF parser (Python 3.10+).

Install: pip install 'pdfminer.six[image]'
Run: python catalog_parser.py catalog.pdf --output catalog_output

Writes catalog.txt, catalog.json, and images/. Output directory must be new.
Analysis is deliberately basic: page counts, words, image dimensions, and
explicitly labeled part/model/SKU candidates that contain a digit. Candidates
are not validated products. Text blocks retain bounding boxes in PDF points (bottom-left origin).
Images are extracted, not interpreted; no OCR, table reconstruction, vector
rendering, or automatic product-to-image matching is performed. Some uncommon
image encodings export as raw .img data rather than viewable pictures.
"""

import argparse
import json
import re
from pathlib import Path

from pdfminer.high_level import extract_pages
from pdfminer.image import ImageWriter
from pdfminer.layout import LAParams, LTContainer, LTImage, LTTextContainer

PART_LABEL = re.compile(
    r"\b(?:part\s*(?:number|no\.?|#)|model(?:\s*(?:number|no\.?|#))?|SKU)"
    r"[ \t]*[:#-]?[ \t]+([A-Za-z0-9][A-Za-z0-9._/-]*)",
    re.IGNORECASE,
)


def part_candidates(text):
    """Labeled part/model/SKU values that contain a digit, without trailing punctuation.

    The digit keeps ordinary words out: "this model is quiet" names no part.
    """
    found = (match.rstrip(".,;:/-") for match in PART_LABEL.findall(text))
    return sorted({value for value in found if any(char.isdigit() for char in value)})


def walk_layout(element):
    """Visit nested figures, stopping at text blocks to avoid duplicate text."""
    if isinstance(element, (LTTextContainer, LTImage)):
        yield element
    elif isinstance(element, LTContainer):
        for child in element:
            yield from walk_layout(child)


def parse_catalog(pdf_path, output_dir):
    """Extract a catalog and return the same dictionary written to JSON."""
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    # Require a fresh directory so earlier results cannot mix with this run.
    output_dir.mkdir(parents=True, exist_ok=False)
    writer = ImageWriter(str(output_dir / "images"))
    pages = []
    for number, layout in enumerate(
        extract_pages(str(pdf_path), laparams=LAParams(all_texts=True)), start=1
    ):
        blocks, images, warnings = [], [], []
        for element in walk_layout(layout):
            bbox = [round(value, 2) for value in element.bbox]
            if isinstance(element, LTTextContainer):
                blocks.append({"text": element.get_text(), "bbox": bbox})
            elif isinstance(element, LTImage):
                # Synthetic names avoid collisions and unsafe PDF resource names.
                element.name = f"page_{number:04d}_image_{len(images) + 1:04d}"
                info = {
                    "bbox": bbox,
                    "width_px": element.srcsize[0],
                    "height_px": element.srcsize[1],
                    "file": None,
                }
                try:
                    filename = writer.export_image(element)
                    info["file"] = f"images/{filename}"
                    if filename.endswith(".img"):
                        warnings.append(f"{filename}: raw image data; may need decoding.")
                except Exception as error:  # noqa: BLE001 - pdfminer raises many types
                    # An unsupported image should not discard the page's text.
                    info["error"] = f"{type(error).__name__}: {error}"
                    warnings.append(f"Image export failed: {element.name}")
                images.append(info)
        text = "\n".join(block["text"].rstrip() for block in blocks)
        if not text.strip():
            warnings.append(
                "No extractable text; this may be a scan or blank page. OCR is not included."
            )
        pages.append(
            {
                "page": number,
                "width_points": layout.width,
                "height_points": layout.height,
                "text": text,
                "text_blocks": blocks,
                "word_count": len(text.split()),
                "part_number_candidates": part_candidates(text),
                "images": images,
                "warnings": warnings,
            }
        )
    result = {
        "source": pdf_path.name,
        "summary": {
            "page_count": len(pages),
            "word_count": sum(page["word_count"] for page in pages),
            "image_count": sum(len(page["images"]) for page in pages),
            "exported_image_count": sum(
                image["file"] is not None for page in pages for image in page["images"]
            ),
        },
        "pages": pages,
    }
    (output_dir / "catalog.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output_dir / "catalog.txt").write_text(
        "\n\n".join(f"--- Page {page['page']} ---\n{page['text']}" for page in pages),
        encoding="utf-8",
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path, default=Path("catalog_output"))
    args = parser.parse_args()
    try:
        result = parse_catalog(args.pdf, args.output)
    except Exception as error:  # noqa: BLE001 - report any failure, then exit 1
        parser.exit(1, f"Error: {error}\nIf output was created, it may contain partial images.\n")
    print(json.dumps(result["summary"], indent=2))
    print(f"Saved to {args.output.resolve()}")


if __name__ == "__main__":
    main()
