"""Protection for a local API with no login (decision 0014).

The API listens on 127.0.0.1 only, but a web page open in the same browser can still send it
requests. Three checks keep other sites out:

- **Host.** Only ``localhost`` and ``127.0.0.1`` are accepted (Starlette's
  ``TrustedHostMiddleware``), so a site whose name resolves to this computer (DNS rebinding) is
  refused.
- **A custom header on writes.** Every request that changes something must carry
  ``X-MoonWalkers-Client``. Browsers send a cross-site request with a custom header only after a
  CORS preflight, which this API never approves (OWASP's custom request header defense).
- **Fetch metadata and Origin on writes.** A write marked ``Sec-Fetch-Site: cross-site``, or
  from an ``Origin`` that is not on this computer, is refused.

Sources and quotes: docs/research/2026-10-18-api-and-dashboard.md.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from urllib.parse import urlsplit

from fastapi import Request, Response
from fastapi.responses import JSONResponse

CLIENT_HEADER = "X-MoonWalkers-Client"
LOCAL_HOSTS = ("localhost", "127.0.0.1")
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# For the built dashboard's pages: its own scripts and styles only; photo previews use blob: URLs.
DASHBOARD_CSP = (
    "default-src 'self'; img-src 'self' blob: data:; object-src 'none'; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'none'"
)


def write_refusal(method: str, headers: Mapping[str, str]) -> str | None:
    """Why a request may not change anything, or None if it may."""
    if method.upper() in SAFE_METHODS:
        return None
    if not headers.get(CLIENT_HEADER.lower()):
        return f"requests that change something need the {CLIENT_HEADER} header"
    if headers.get("sec-fetch-site") == "cross-site":
        return "cross-site requests may not change anything"
    origin = headers.get("origin")
    if origin and urlsplit(origin).hostname not in LOCAL_HOSTS:
        return f"requests from {origin} may not change anything"
    return None


async def guard_writes(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    refusal = write_refusal(request.method, request.headers)
    if refusal is not None:
        return JSONResponse({"detail": refusal}, status_code=403)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    if not request.url.path.startswith("/api/"):  # the dashboard's own pages
        response.headers.setdefault("Content-Security-Policy", DASHBOARD_CSP)
    return response
