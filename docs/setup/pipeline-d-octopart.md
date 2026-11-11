# Pipeline D: Octopart catalog extraction

Pipeline D lives at `backend/src/moonwalkers/pipelines/d/`. Its `create_pipeline()` now returns
`CatalogPipeline`, so the existing default registry, input router and orchestrator can run it.
The historical HA5C stub remains available to tests only. No shared contract or backend
requirements changed. Design: [decision 0024](../decisions/0024-pipeline-d-octopart.md).

## What it accepts

Use `online_resource` sources whose `kind` is `url`, with either:

- an HTTPS Octopart product-page URL copied from your browser; or
- `https://octopart.com/search?q=LM358DR`, where `q` is an exact part number.

Search examines only the first result page. Case and surrounding whitespace are ignored;
punctuation is significant. No match or multiple exact links produces a review issue. Use a
specific product URL to resolve manufacturer ambiguity. PDF catalogs, local files, other sites,
and HTTP URLs produce explicit issues; they are not silently handled as Octopart inputs.

## Browser environment

The backend calls an isolated Python process using JSON on stdin/stdout. It does not need
Playwright in `backend/.venv`, and importing the pipeline does not start a browser. Existing
server processes can call the synchronous adapter without running Playwright inside their
async event loop. Backend dependencies and `uv.lock` remain unchanged.

Use an existing browser environment if you have one. Otherwise, the following is the proposed
setup, subject to the repository's dependency approval policy (CLAUDE.md rule 3). Nothing was
installed as part of this integration. Playwright is an Apache-2.0 browser automation package;
Chromium is a separate browser download with its own notices. Exact download and installed
sizes depend on OS/version and have not been measured here; browser binaries can be substantial.
Primary references (reviewed 2026-11-04): https://playwright.dev/python/docs/library and
https://github.com/microsoft/playwright-python/blob/main/LICENSE

After approval, from `backend/` on Windows PowerShell:

```powershell
py -3.12 -m venv C:\mw-octopart
C:\mw-octopart\Scripts\python.exe -m pip install -r src/moonwalkers/pipelines/d/octopart_agent/requirements.txt
C:\mw-octopart\Scripts\python.exe -m playwright install chromium
$env:MOONWALKERS_OCTOPART_PYTHON = "C:\mw-octopart\Scripts\python.exe"
```

If `py -3.12` finds no runtime (Python 3.12 managed by uv only), create the environment with
`uv venv --python 3.12 --seed C:\mw-octopart` instead. Measured on 2026-11-10 (Windows 11,
playwright 1.65.0): the venv is 127 MB, Chromium 450 MB and its headless shell 286 MB.

On macOS/Linux, use a Python 3.12 virtual environment outside the repo and its `bin/python`:

```sh
python3.12 -m venv "$HOME/mw-octopart"
"$HOME/mw-octopart/bin/python" -m pip install -r src/moonwalkers/pipelines/d/octopart_agent/requirements.txt
"$HOME/mw-octopart/bin/python" -m playwright install chromium
export MOONWALKERS_OCTOPART_PYTHON="$HOME/mw-octopart/bin/python"
```

Set the environment variable in the process that starts your CLI, API or MCP server. The file
`example.env` documents the name; it is not automatically loaded by this adapter. Never point
the variable to a command with flags: it must name the Python executable. No API key is needed.

## Run through the existing pipeline command

From your normal, already configured backend environment:

```sh
uv run python -m moonwalkers.pipelines list
uv run python -m moonwalkers.pipelines run D --input-type online_resource "https://octopart.com/search?q=LM358DR" --out ../data/octopart-try-001.json
```

The CLI refuses to replace an existing output file; choose another name for subsequent runs.
It emits the shared `PipelineResult` JSON, rather than the earlier standalone tool's CSV.
Check `issues`, `facts`, and `needs_human_review` even when the CLI exits 0: a valid result may
contain extraction errors and no facts. Missing browser setup is one such error.

An API/MCP caller uses the existing `online_resource` source and submit flow. To build a twin,
provide the **machine's** identity separately or through another pipeline: this pipeline does
not identify a machine from the components in its catalog. Only the orchestrator stores results.

## Result contents and limits

- Original input sources are retained. A successful extraction adds the actual product URL
  with a fresh retrieval time. Every extracted fact cites that product source.
- Exact MPN, manufacturer/brand and description come from a unique JSON-LD `Product` object.
- Datasheet/PDF links are candidates only; the pipeline does not fetch or read the PDFs.
- Offers are preserved as a JSON string, and rendered page text as text evidence (at most
  20,000 characters, with a truncation issue). They are **not normalized prices, inventory or SI
  specifications**. Currency and quantity context remain in the evidence if the page supplies it.
- Keys use `octopart_<input-source-hash>_<field>` so several component sources do not collide.
- Component data never sets `MachineIdentity` or creates geometry, joints, or control behavior.
- Each request uses a fresh headless browser. No login profile or credentials are retained.
  CAPTCHA, login redirects, HTTP errors and timeouts yield issues; jobs never prompt or wait
  for a person. If verification is required, review access manually and retry later; this version
  does not import your logged-in browser session.
- Hidden/paginated offers are not expanded. JSON-LD or layout changes may require parser updates.
- `needs_human_review` always remains true. Extraction confidence is an implementation estimate,
  not a measured probability: 0.8 for declared metadata, 0.4 for raw evidence [INFERENCE].

The official API is a separate future option, not implemented here:
https://www.altium.com/documentation/altium-developer-center/quick-starts/octopart-api

## Files and functions

| File | Purpose |
|---|---|
| `d/__init__.py` | Registers the real pipeline through `create_pipeline()` |
| `d/pipeline.py` | `CatalogPipeline.run()` maps sources to cited contract facts/issues; `BrowserReader.read()` invokes the bounded subprocess |
| `d/octopart.py` | `input_url()` validates inputs; `candidates()` finds exact links; `extract()` reads unique Product metadata |
| `d/browser_worker.py` | `collect()` drives navigation/extraction; `main()` handles the isolated worker protocol |
| `tests/test_pipeline_d.py` | Offline parser, worker, adapter, contract, registration and orchestrator checks |

## Verification

From `backend/`, with the existing backend environment:

```sh
uv run pytest tests/test_pipeline_d.py tests/test_pipeline_stubs.py tests/test_pipelines_cli.py tests/test_mcp_server.py
uv run ruff check .
uv run ruff format --check .
```

The focused tests also run without pytest, from the repository root:

```sh
PYTHONPATH=backend/src python -m unittest discover -s backend/tests -p test_pipeline_d.py -v
```

The integration's 19 offline tests passed with Python 3.12 and the available Pydantic runtime.
Full pytest/ruff checks could not run here because those tools were unavailable. The existing
CLI import required unavailable `trimesh`; live browser execution needs unavailable Playwright
and Chromium. The earlier direct Octopart access attempt returned HTTP 403. Live end-to-end
extraction remains unverified.

**Live check, 2026-11-10: blocked.** With the environment installed (`C:\mw-octopart`), the
search for `LM358DR` returned 0 facts and one error issue. Octopart answered the headless
browser with HTTP 403 and a "Please complete the security check" page. The pipeline stopped
with an issue, as designed. Worklog: `docs/worklog/2026-11-10.md`. Before relying on results, run one real product locally and
compare its cited metadata and evidence with the page.
