# OCTOPART-SEARCH: this whole file is the Octopart website search (decision 0024).
# Blocked by Octopart's security check (HTTP 403, 2026-11-10).
"""One JSON request on stdin, one JSON response on stdout; run in a browser environment.

This file can run directly without importing the backend or Pydantic. Never prompts for input.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

if __package__:
    from .octopart import HOSTS, candidates, extract, input_url
else:
    from octopart import HOSTS, candidates, extract, input_url

MAX_HTML = 8_000_000


def collect(page: Any, uri: str) -> dict[str, Any]:
    """Navigate a supported URL and read a single product, with bounded waits."""
    url, query = input_url(uri)

    def visit(target: str) -> str:
        response = page.goto(target, wait_until="domcontentloaded", timeout=30_000)
        if response is None or response.status >= 400:
            raise ValueError("Octopart refused the request; check access in a regular browser.")
        page.wait_for_timeout(2000)
        input_url(page.url)  # Reject off-site or login redirects before reading data.
        text = page.locator("body").inner_text(timeout=10_000).casefold()
        title = page.title().casefold()
        markers = ("verify you are human", "verify you are a human", "access denied", "captcha")
        if any(marker in title or marker in text[:6000] for marker in markers):
            raise ValueError("Octopart requires verification; automatic extraction stopped.")
        if "just a moment" in title or "checking your browser" in text[:6000]:
            raise ValueError("Octopart is checking the browser; automatic extraction stopped.")
        # Client-side rendering may complete after DOMContentLoaded.
        page.wait_for_function(
            """() => document.querySelector('script[type="application/ld+json"]') ||
            Array.from(document.querySelectorAll('a[href]'))
                .some(a => /-\\d+$/.test(a.pathname))""",
            timeout=10_000,
        )
        html = page.content()
        if len(html) > MAX_HTML:
            raise ValueError("Octopart page exceeds the extraction size limit.")
        return html

    html = visit(url)
    if query is not None:
        links = candidates(html, query, page.url)
        if len(links) != 1:
            return {
                "status": "ambiguous" if links else "needs_review",
                "url": page.url,
                "message": "Search has no unique exact link on its first page. Use a product URL.",
                "candidates": links,
            }
        html = visit(links[0])
    result = extract(html, query, page.url)
    # Text evidence retains div-based offers without guessing their column meanings.
    evidence = page.locator("body").inner_text(timeout=10_000)
    result["page_text"] = evidence[:20_000]
    result["text_truncated"] = len(evidence) > 20_000
    result["retrieved_at"] = datetime.now(UTC).isoformat()
    return result


def main() -> int:
    try:
        request = json.loads(sys.stdin.read(8192))
        uri, _ = input_url(request["url"])
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(accept_downloads=False, service_workers="block")

                def restrict_navigation(route: Any) -> None:
                    req = route.request
                    parsed = urlsplit(req.url)
                    if req.is_navigation_request() and (
                        parsed.scheme != "https" or parsed.hostname not in HOSTS
                    ):
                        route.abort()
                    else:
                        route.continue_()

                context.route("**/*", restrict_navigation)
                result = collect(context.new_page(), uri)
            finally:
                browser.close()
    except ImportError:
        result = {
            "status": "error",
            "message": "Browser environment needs Playwright and Chromium.",
        }
    except Exception:  # noqa: BLE001 - any failure becomes one issue, not a trace
        # Do not expose browser traces, local profile paths or credentials in pipeline results.
        result = {"status": "error", "message": "Browser extraction failed or access was blocked."}
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
