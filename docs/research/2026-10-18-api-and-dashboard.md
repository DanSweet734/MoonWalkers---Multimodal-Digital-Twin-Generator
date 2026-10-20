# The API and the barebones dashboard (Phase 5)

**Question.** Which packages and setup give the dashboard a backend without installing more than
needed? How should a local API with no login be protected? How can the dashboard get TypeScript
types from the backend's models without copying them by hand?

**Dates.** All sources were read on 2026-10-18 (local time, PDT). Decisions 0014 and 0015 use this
note. "Observed" means checked on Daniel's machine that day, with the commands in the worklog.

## 1. FastAPI and what it adds

### The release
From PyPI (https://pypi.org/pypi/fastapi/json):
- **Version:** `fastapi` 0.146.0, uploaded 2026-10-18T15:19:29Z.
- **License and size:** MIT; the wheel is 141.3 KB.
- **Python:** `requires_python >=3.10`.
- **Dependencies, without extras:** `starlette>=0.46.0`, `pydantic>=2.9.0`,
  `typing-extensions>=4.8.0`, `typing-inspection>=0.4.2`, `annotated-doc>=0.0.2`,
  `opentelemetry-api>=1.44.0`.
- **Releases are frequent.** Five came out on 2026-10-18 alone: 0.143.4, 0.143.5, 0.144.0,
  0.145.0 and 0.146.0. 0.143.3 came out on 2026-10-16.

### Breaking changes this week
From the release notes (https://fastapi.tiangolo.com/release-notes/; the first 100,000 of 476,598
characters were read):
- **0.146.0:** "Deprecate the `root_path` parameter in `FastAPI`."
- **0.145.0:** "Remove deprecated `openapi_prefix` and unused `**extra` from `FastAPI`."
- **0.143.0:** automatic OpenTelemetry exporter setup became opt-in. Its full list of breaking
  changes was cut off in the page as read.

We use none of these parameters [INFERENCE: checked against `api/app.py`].

### Pinning
From https://fastapi.tiangolo.com/deployment/versions/:
- "Following the Semantic Versioning conventions, any version below `1.0.0` could potentially add
  breaking changes."
- "Breaking changes and new features are added in "MINOR" versions."
- The page's example pin is `fastapi[standard]>=0.112.0,<0.113.0`.
- "You shouldn't pin the version of `starlette`."

So `backend/pyproject.toml` pins `fastapi>=0.146,<0.147`, without the `standard` extra.

### What the install added
Resolved with `uv pip compile` for Windows and Python 3.12 against our other dependencies, before
anything was installed:
- **New:** only `fastapi` 0.146.0 and `annotated-doc` 0.0.5 (MIT, 5.2 KB).
- **Already installed with the MCP SDK:** `starlette` 1.9.0 (BSD-3-Clause), `uvicorn` 0.54.0
  (BSD-3-Clause) and `python-multipart` 0.0.32 (Apache-2.0). They became direct dependencies,
  because our code uses them.
- **The install** (`uv add`, approved by Daniel): "Installed 3 packages": `annotated-doc`,
  `fastapi` and the project itself.

### The documentation
- **Uploads** (https://fastapi.tiangolo.com/tutorial/request-files/):
  - "To receive uploaded files, first install `python-multipart`."
  - `UploadFile` "uses a "spooled" file: A file stored in memory up to a maximum size limit, and
    after passing this limit it will be stored on disk."
  - "you can't also declare `Body` fields that you expect to receive as JSON, as the request will
    have the body encoded using `multipart/form-data`".
- **Static files** (https://fastapi.tiangolo.com/tutorial/static-files/): "a mounted application
  is completely independent. The OpenAPI and docs from your main application won't include
  anything from the mounted application".
- **Input and output schemas** (https://fastapi.tiangolo.com/how-to/separate-openapi-schemas/):
  for a model used for both, "for **output** it will be **required**", meaning a field with a
  default.

### Observed with 0.146.0
- **Required fields.** In our schema, which has output-only models, a field with a default is
  not listed as required. For example, `Part.citations` and `JobStep.detail`. The generated
  TypeScript therefore marks such fields optional, which is safe for the dashboard.
- **The test client.** Starlette 1.9.0's test client imports `httpx2 as httpx`, falling back to
  `httpx` (in `starlette/testclient.py`). `httpx2` came with the MCP SDK, so API tests need
  nothing more.
- **Routes.** `app.routes` holds `_IncludedRouter` objects without a `.path` for included
  routers. A script that lists routes should read `app.openapi()["paths"]` instead.

## 2. TypeScript types from the backend's models
CLAUDE.md asks that the dashboard's types be generated, not copied.
- **openapi-typescript** 7.13.0 (MIT, published 2026-02-11; registry.npmjs.org) declares the peer
  dependency `typescript ^5.x`. The dashboard uses TypeScript 6.0.3.
  - Observed: `npm install --dry-run -D openapi-typescript@7.13.0`, run in a copy of the
    dashboard's `package.json` and lock file, fails with `ERESOLVE ... peer typescript@"^5.x"`.
  - npm suggests `--force` or `--legacy-peer-deps` "to accept an incorrect (and potentially
    broken) dependency resolution".
- **json-schema-to-typescript** 16.0.0 (MIT, published 2026-08-28).
  - A dry run in an empty project adds 15 packages. Their registry sizes total 15.44 MB unpacked,
    including `prettier` 3.9.10 at 9.7 MB and `lodash` at 1.4 MB.
  - Its licenses are MIT, plus `argparse` (PSF-2.0 / Python-2.0).
  - Its README does not mention `prefixItems`, the JSON Schema 2020-12 form Pydantic writes for
    tuples such as `Vec3`.
- **Our own generator.** `moonwalkers.api.typescript` reads the API's OpenAPI document. It handles
  only the keywords our schema uses, listed below, and stops on anything else.
  - The keywords: `$ref`, `anyOf`, `const`, `enum`, `type`, `items`, `prefixItems`, `properties`,
    `required` and `additionalProperties`.
  - Keywords that only describe or constrain values, such as titles and lengths, are ignored.

## 3. Tests for the dashboard without a test runner package
- The Vite template's `tsconfig.app.json` already sets `"erasableSyntaxOnly": true` and
  `"allowImportingTsExtensions": true`.
- Observed: Node v24.20.0 ran a TypeScript test file directly, with `node --test
  "src/**/*.test.ts"`, from a scratch project with no packages.
- So `npm test` runs the dashboard's pure modules (routes, formatting) with nothing installed.
  `tsconfig.test.json` type-checks those tests during `npm run build`.
- React components are not unit-tested: they are checked by `npm run build` (types), by
  `npm run lint` and by hand.

## 4. Protecting a local API that has no login
- **Custom request headers.** From OWASP's CSRF cheat sheet
  (https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html):
  - "A user-friendly defense that is particularly well suited for AJAX or API endpoints is the use
    of a custom request header."
  - "This defense relies on the CORS preflight mechanism".
  - "All modern browsers designate requests with custom headers as "to be preflighted"."
  - On fetch metadata: "`Sec-Fetch-Site` is the most useful Fetch Metadata header for blocking
    CSRF-like cross-origin requests".
- **DNS rebinding.** The MCP specification's security warning for HTTP servers
  (https://modelcontextprotocol.io/specification/2025-06-18/basic/transports):
  - "Servers **MUST** validate the `Origin` header on all incoming connections to prevent DNS
    rebinding attacks".
  - "When running locally, servers **SHOULD** bind only to localhost (127.0.0.1)".
  - "Without these protections, attackers could use DNS rebinding to interact with local MCP
    servers from remote websites."

  Our API is not an MCP server, but it is a local HTTP server that a browser can reach in the same
  way [INFERENCE].
- **Host checking.** Starlette's `TrustedHostMiddleware` (https://starlette.dev/middleware/)
  "Enforces that all incoming requests have a correctly set `Host` header, in order to guard
  against HTTP Host Header attacks", and "If an incoming request does not validate correctly then
  a 400 response will be sent." A rebound name arrives with the attacker's host name in `Host`
  [INFERENCE], so only `localhost` and `127.0.0.1` are allowed.
- **Saved web pages.** A saved page served as `text/html` from the API's origin could run its
  scripts with access to the API [INFERENCE]. The API therefore sends saved HTML as `text/plain`,
  with `X-Content-Type-Options: nosniff` and `Content-Security-Policy: sandbox`.
- **PDFs** are sent without the sandbox policy, because a browser's PDF viewer may not open in a
  sandboxed page [INFERENCE: not tested in a browser].

## 5. The development server's proxy
From https://vite.dev/config/server-options:
- `server.proxy`: "Configure custom proxy rules for the dev server." "Any requests whose request
  path starts with that key will be proxied to the specified target."
- `server.host`: "**Default:** `'localhost'`".

The dashboard forwards `/api` to `http://127.0.0.1:8000`, so in development the browser talks to
one origin and the API needs no CORS settings.

## 6. Measurements (2026-10-18)
- **Read-only, over HTTP, on the real data folder.** `python -m moonwalkers.api --port 8765`
  served the built dashboard and the API:
  - `/` returned the page with the dashboard's Content-Security-Policy, `X-Frame-Options: DENY`
    and `nosniff`;
  - `/api/jobs` listed the three HA5C jobs (`2026-10-17_run-001` has no `request.json`, so it is
    not a job);
  - the photo came back as `image/jpeg`;
  - `Host: attacker.example` got 400;
  - a write with `Origin: https://attacker.example` got 403, as did a write without the header;
  - `netstat` showed it listening on `127.0.0.1:8765` only.
- **Writes, through Vite's proxy, on a scratch copy of the data folder (48.1 MB).**
  - Uploading the HA5C photo without "new version" reused v3 at once ("Found an existing twin
    (v3, needs review) for haas/ha5c; reused it."). The photo was recognised as the file already
    in `inputs/photos/` and `SOURCES.md`, so no copy and no line were added.
  - With "new version", the job waited for the agent. `list_jobs`, called on the same copy, found
    it with the next step "the cited reading notes".
  - After a review rejected v3, a request reused v2: "... Newer versions were rejected in review:
    v3."
  - The real data folder was not touched: still four run folders, no `kb/reviews/`, and the same
    `SOURCES.md`.
- **The build.** `npm run build`: 250 KB of JavaScript (76.5 KB gzipped) and 5.1 KB of CSS. The
  built `index.html` has no inline script, so the dashboard's `default-src 'self'` policy does not
  block it.

## Open questions
- **The look in a browser.** The pages were not checked in a browser in this session, which has
  none. Daniel's hand check (`docs/setup/dashboard.md`) covers it. (Answered 2026-10-18: "minimal
  but functional", worklog 2026-10-18.)
- **PDFs in a sandboxed page:** whether browsers open them is not tested. They are served without
  the sandbox policy. (Answered 2026-10-19: the "saved copy" links open the PDF in a separate tab,
  Daniel's check.)
- **Separate processes.** The MCP server and the API are separate processes on one data folder.
  Each has its own lock, and they write different files. Two writers on the same file at the same
  moment are not guarded against (decision 0008: one writer at a time).
