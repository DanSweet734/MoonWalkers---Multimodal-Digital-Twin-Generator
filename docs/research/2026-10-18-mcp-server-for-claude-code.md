# An MCP server that Claude Code can drive (Phase 4)

**Question.** Which SDK and setup let Claude Code, the PoC's agent (decision 0003), drive the
platform through our own MCP tools? What limits do Claude Code and the SDK put on those tools?

**Dates.** All sources were read on 2026-10-18 (local time, PDT). Decision 0013 uses this note.

## 1. The MCP Python SDK

### Releases and license
From PyPI (https://pypi.org/pypi/mcp/json):
- `mcp` 2.3.0, uploaded 2026-10-02T22:06:52Z, license MIT, `requires_python >=3.10`.
- 2.0.0 came out on 2026-07-28. The 1.x line continues: 1.30.0 came out on 2026-09-07.
- The project links its documentation at https://py.sdk.modelcontextprotocol.io/ and its code at
  https://github.com/modelcontextprotocol/python-sdk.

### Dependencies
Resolved for Windows and Python 3.12 with `uv pip compile` (nothing installed). Sizes are the
PyPI wheels for this platform, and licenses are PyPI's metadata. The backend already had pydantic,
pydantic-core, annotated-types, typing-extensions and typing-inspection.

| Package | Version | Size | License |
|---|---|---|---|
| mcp | 2.3.0 | 0.37 MB | MIT |
| mcp-types | 2.3.0 | 0.07 MB | MIT |
| pywin32 (Windows only) | 312 | 6.91 MB | PSF |
| cryptography | 50.0.2 | 3.82 MB | Apache-2.0 OR BSD-3-Clause |
| rpds-py | 2026.9.1 | 0.22 MB | MIT |
| cffi | 2.1.1 | 0.19 MB | MIT-0 |
| anyio, attrs, h11, jsonschema, jsonschema-specifications, pyjwt, referencing, truststore | - | 0.02-0.13 MB each | MIT |
| click, httpcore2, httpx2, idna, pycparser, sse-starlette, starlette, uvicorn | - | 0.02-0.13 MB each | BSD-3-Clause |
| opentelemetry-api, python-multipart | - | 0.06, 0.03 MB | Apache-2.0 |

That makes 24 new packages and 12.7 MB to download. Daniel approved the install on 2026-10-18.

### The documentation
- **Docs home** (https://py.sdk.modelcontextprotocol.io/): the example server is
  `from mcp.server import MCPServer`, then `mcp = MCPServer("Demo")`. Tools are declared with
  `@mcp.tool()` on type-hinted functions.
- **Tools page** (https://py.sdk.modelcontextprotocol.io/servers/tools/):
  - "Type hints aren't documentation here. They are **the contract**."
  - "A plain `def` tool works too: the SDK runs it in a thread so it never blocks the server."
  - Tool annotations "are hints, not security. Never rely on a client honouring them."
- **Migration guide** (https://py.sdk.modelcontextprotocol.io/migration/):
  - "The `FastMCP` class has been renamed to `MCPServer` to better reflect its role as the main
    server class in the SDK."
  - For failures the model should see: "raise `ToolError` or return `CallToolResult(is_error=True,
    ...)` directly."
  - "The v1.x maintenance line keeps receiving critical bug fixes and security patches".
- **Testing page** (https://py.sdk.modelcontextprotocol.io/get-started/testing/): "The SDK's
  `Client` class, the same one that connects to a URL or launches a subprocess, also connects **in
  memory**", as in `async with Client(mcp, raise_exceptions=True) as c:`.

### Observed with the installed 2.3.0
- **API.**
  - `MCPServer.run(transport="stdio")` defaults to stdio.
  - `MCPServer.tool(...)` takes `name`, `title`, `description`, `annotations`, `icons`, `meta` and
    `structured_output`.
  - `Client` is exported from `mcp`; `ToolAnnotations` is in `mcp.types`.
- **Behavior,** from a probe server with four tools:
  - A tool returning a Pydantic model gets an output schema, and its result carries structured
    content as well as JSON text.
  - A tool returning a plain `dict` has no output schema and no structured content, only JSON text.
  - `raise ToolError("no geometry spec yet for 3")` reaches the client as `is_error` with the text
    "Error executing tool fails: no geometry spec yet for 3".
  - `raise ValueError("unexpected")` reaches the client only as "Error executing tool crashes". The
    message and traceback go to the server's stderr.

### Alternatives
`fastmcp` 4.1.1 (Apache-2.0, uploaded 2026-10-18) requires `fastmcp-slim[client,server]==4.1.1`.
Those extras require `mcp<3.0.0,>=2.0.0` (PyPI JSON for both).

## 2. Claude Code and MCP servers
From https://code.claude.com/docs/en/mcp. The page is long; 100,000 of its 123,186 characters were
read.
- **Variable expansion:** "`${VAR}`: expands to the value of environment variable `VAR`", and
  "`${VAR:-default}`: expands to `VAR` if set, otherwise uses `default`". It applies to `command`,
  `args`, `env`, `url` and `headers`.
- **The project directory:** CLAUDE_PROJECT_DIR "is set in the server's environment, not in Claude
  Code's own environment, so referencing it via `${VAR}` expansion in the `command` or `args` of a
  project-scoped `.mcp.json` entry ... requires a default such as `${CLAUDE_PROJECT_DIR:-.}`."
- **Approval:** "Claude Code prompts for approval in interactive sessions before using
  project-scoped servers from `.mcp.json` files. To reset those approval choices, run `claude mcp
  reset-project-choices`." Until approved, `claude mcp list` shows "⏸ Pending approval (run `claude`
  to approve)".
- **Timeouts:**
  - per server: "adding a `timeout` field in milliseconds to that server's `.mcp.json` entry, for
    example `"timeout": 600000` for ten minutes", which overrides `MCP_TOOL_TIMEOUT`;
  - without one, the default is "about 28 hours";
  - the idle window "defaults to ... 30 minutes for stdio servers";
  - "An MCP tool call in the main conversation that is still running after two minutes moves to a
    background task".
- **Output limits:** "Claude Code displays a warning when any MCP tool output exceeds 10,000
  tokens", and "the default maximum is 25,000 tokens" (`MAX_MCP_OUTPUT_TOKENS`). Text results
  longer than 50,000 characters are saved to a file.
- **Windows:** "Claude Code closes the server's stdin, then ends the server's process tree if the
  process is still running 300 milliseconds later."
- **Tool names:** tools are named `mcp__<server>__<tool>` in permission rules and hook matchers.
- **Not on the page:** whether a session must be restarted to pick up a hand-edited `.mcp.json`
  (not confirmed), and `MCP_TIMEOUT`'s default.

### Observed with Claude Code 2.1.302
`claude mcp get moonwalkers` read our `.mcp.json` as:
- `Scope: Project config (shared via .mcp.json)`;
- `Status: ⏸ Pending approval`;
- `Type: stdio`, with our command, arguments and environment;
- `Timeout: 600000ms`.

## 3. Measurements on our server (2026-10-18)
- **Over real stdio.** Started with the `.mcp.json` command (`uv run --no-sync --directory
  <project>/backend python -m moonwalkers.mcp`) and driven by the SDK's stdio client:
  - connected in 0.9 s, listing 15 tools;
  - with `CLAUDE_PROJECT_DIR` set, `check_knowledge_base` found the repository's `data/` folder and
    the HA5C's two twin versions;
  - `MOONWALKERS_GEN_ROOT` was not set in that environment, so `generator_root` was null.
- **Size.** The tool list, with input and output schemas, is 35,051 characters, about 8,800 tokens
  at 4 characters per token [INFERENCE: a rough rule, not a count].
- **Tests.** 18 new tests: 6 drive the server through an in-memory `Client`, and 12 cover the
  workspace. They include a full build with the fake generator, from `start_run` to `submit_twin`,
  followed by a reuse through `request_twin`.

## 4. The end-to-end session (2026-10-18)
A fresh Claude Code session in VS Code, from Daniel's report and that session's worklog entry:
- **No prompts.** The `moonwalkers` server loaded without an approval prompt, and Daniel was not
  asked to approve any tool call. The documentation explains the first only for "`claude -p` runs,
  Agent SDK sessions, and cloud sessions" (section 2). That the VS Code session counts as one is
  [INFERENCE]. The session's permission mode was not recorded.
- **Calls and timing.** The agent made 34 tool calls, counted from its worklog table:

  | Calls | Tools |
  |---|---|
  | 9 | `add_fact` |
  | 3 each | `check_knowledge_base`, `add_issue`, `add_joint`, `preview_twin` |
  | 2 each | `add_reference_source`, `identify_machine` (one failed), `add_control` |
  | 1 each | `start_run`, `add_input`, `generate_geometry`, `inspect_geometry`, `set_scale`, `submit_twin`, `request_twin` | They ran from about 19:59 to 20:10 UTC, including the wait for Daniel's answer.
  The generation job reported 46.8 s.
- **One tool error.** `identify_machine` failed when it cited the photo from `add_input` ("citations
  of unknown sources"). The error now explains the rule (decision 0013).
- **Asking the person.** The agent asked one question, which front parts turn, with preview images
  of both options, as the procedure asks.
- **Quotes verified afterwards.** All 26 quotes in its reading notes are on the cited PDF pages
  (pypdf, page by page). The checks ignored whitespace and the glyphs pypdf cannot decode, and
  allowed the agent's "..." elisions and "/" row separators.

## Open questions
- Does Claude Code in VS Code pick up a new `.mcp.json`, or a new user environment variable,
  without restarting VS Code? Restarting is the safe assumption.
- Does the VS Code extension set `CLAUDE_PROJECT_DIR` in the server's environment? The data folder
  that `check_knowledge_base` reports in the end-to-end run will show. The server falls back to the
  repository's `data/` folder either way.
- Permission rules that allow all `moonwalkers` tools at once: the permissions page was not read.
  The end-to-end run uses per-call approval.
