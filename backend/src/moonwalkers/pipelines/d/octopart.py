# OCTOPART-SEARCH: this whole file is the Octopart website search (decision 0024).
# Blocked by Octopart's security check (HTTP 403, 2026-11-10).
"""Pure Octopart parsing, shared by the backend and the isolated browser worker."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

HOSTS = {"octopart.com", "www.octopart.com"}


def input_url(uri: str) -> tuple[str, str | None]:
    """Return a canonical part/search URL and the exact search MPN, if supplied."""
    parsed = urlsplit(uri)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
    ):
        raise ValueError("Use an HTTPS Octopart product URL or /search?q=<exact part number>.")
    base = urlunsplit(("https", parsed.hostname, parsed.path, "", ""))
    if parsed.path.rstrip("/") == "/search":
        queries = parse_qs(parsed.query).get("q", [])
        if len(queries) != 1 or not queries[0].strip() or len(queries[0]) > 200:
            raise ValueError("An Octopart search must contain one exact part number in q.")
        query = queries[0].strip()
        return base + "?" + urlencode({"q": query}), query
    if not re.fullmatch(r"/[\w%+.,()-]+-\d+/?", parsed.path):
        raise ValueError("Use an Octopart product URL or /search?q=<exact part number>.")
    return base, None


def normalize(value: str) -> str:
    """Ignore case and edge whitespace, preserving orderable-part punctuation."""
    return value.strip().casefold()


class PageParser(HTMLParser):
    """Read JSON-LD and anchor labels from browser-serialized HTML."""

    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self.documents: list[Any] = []
        self.links: list[tuple[str, str]] = []
        self._json: list[str] | None = None
        self._anchor: tuple[str, list[str]] | None = None
        self.feed(html)
        self.close()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "script" and attributes.get("type") == "application/ld+json":
            self._json = []
        if tag == "a" and attributes.get("href"):
            self._anchor = (attributes["href"], [])

    def handle_data(self, data: str) -> None:
        if self._json is not None:
            self._json.append(data)
        if self._anchor is not None:
            self._anchor[1].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._json is not None:
            try:
                self.documents.append(json.loads("".join(self._json)))
            except (ValueError, RecursionError):
                pass
            self._json = None
        if tag == "a" and self._anchor is not None:
            href, text = self._anchor
            self.links.append((href, "".join(text).strip()))
            self._anchor = None


def _objects(value: Any) -> list[dict[str, Any]]:
    found = []
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            found.append(item)
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return found


def candidates(html: str, query: str, base: str) -> list[str]:
    urls: list[str] = []
    for href, label in PageParser(html).links:
        if normalize(label) != normalize(query):
            continue
        try:
            url, search = input_url(urljoin(base, href))
        except ValueError:
            continue
        if search is None and url not in urls:
            urls.append(url)
    return urls


def extract(html: str, query: str | None, url: str) -> dict[str, Any]:
    """Read one unambiguous Product, never select a fuzzy MPN or the cheapest offer."""
    parser = PageParser(html)
    products = []
    for item in _objects(parser.documents):
        types = item.get("@type", [])
        if isinstance(types, str):
            types = [types]
        mpn = item.get("mpn")
        if not isinstance(types, list) or "Product" not in types:
            continue
        if not isinstance(mpn, str) or not mpn.strip():
            continue
        if (query is None or normalize(mpn) == normalize(query)) and item not in products:
            products.append(item)
    if len(products) != 1:
        return {
            "status": "needs_review",
            "url": url,
            "message": "No unique exact-MPN Product metadata; choose a product URL or review page.",
        }
    product = products[0]
    maker = product.get("manufacturer") or product.get("brand")
    if isinstance(maker, dict):
        maker = maker.get("name")
    sheets = []
    for href, label in parser.links:
        link = urljoin(url, href)
        parsed = urlsplit(link)
        is_sheet = "datasheet" in label.casefold() or parsed.path.casefold().endswith(".pdf")
        if parsed.scheme == "https" and is_sheet and link not in sheets:
            sheets.append(link)
    return {
        "status": "extracted",
        "url": url,
        "mpn": product["mpn"],
        "manufacturer": maker if isinstance(maker, str) else "",
        "description": product.get("description")
        if isinstance(product.get("description"), str)
        else "",
        "datasheets": sheets,
        "offers": product.get("offers"),
        "message": "Catalog metadata only; offers and linked datasheets need human review.",
    }
