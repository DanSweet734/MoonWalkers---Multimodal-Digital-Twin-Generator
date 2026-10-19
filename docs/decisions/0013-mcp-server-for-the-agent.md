# 0013 - The MCP server the agent drives: one tool per platform action, state in the run folder

- **Status:** accepted (proposed by Claude Code in Phase 4; Daniel approved the SDK install and the
  end-to-end plan, then reviewed and merged the Phase 4 PR, #8, on 2026-10-18). Updated for Phase 5
  (section at the end).
- **Date:** 2026-10-18
- **Decided by:** team (Daniel)

## Context
Decision 0003 makes Claude Code the PoC's agent, driving the platform through our own MCP tools.
CLAUDE.md names the actions: add source, identify machine, check knowledge base, generate
geometry, set scale, add joint, export, submit. Phase 4 of `docs/poc-plan.md` asks for:
- the server;
- a project `.mcp.json`;
- a written procedure;
- an end-to-end run.

The facts below are quoted, with access dates, in
`docs/research/2026-10-18-mcp-server-for-claude-code.md`.
- **The SDK.** The MCP Python SDK is at 2.3.0 (2026-10-02, MIT). In 2.x, `FastMCP` became
  `MCPServer`, and the 1.x line gets only critical fixes.
- **Errors.** An unexpected exception in a tool reaches the client only as "Error executing tool
  ...", with the details hidden. A `ToolError` keeps its message. A Pydantic return type gives the
  tool an output schema and structured content; a plain `dict` does not (both observed).
- **Claude Code** starts stdio servers from `.mcp.json` and asks for approval before using a
  project server. A tool call may run up to about 28 hours by default, and moves to the background
  after two minutes. It warns when a tool result passes 10,000 tokens, and caps results at 25,000
  by default.

## Options considered
1. **SDK.**
   - (a) The official `mcp` 2.x;
   - (b) its 1.x maintenance line;
   - (c) the separate `fastmcp` package (4.1.1, Apache-2.0).

   (a) is current. (c) requires `fastmcp-slim[client,server]`, whose `server` and `client`
   extras require `mcp>=2.0.0,<3.0.0`: a layer on top of (a), with more dependencies.
2. **Transport.**
   - (a) stdio: Claude Code starts the server, with no port and no authentication;
   - (b) Streamable HTTP: a long-running service, which would need authentication once shared
     [INFERENCE].

   (b) may suit Phase 5's API, but the PoC needs neither.
3. **Granularity.**
   - (a) One tool per platform action: about 15 calls per build, each checked and cited on its
     own;
   - (b) a few coarse tools, such as `build_twin(photo)`.

   (b) hides the decisions that most need an agent's judgement (axes, spindle extent, scale
   source) and a person's review.
4. **State.**
   - (a) Files in the run folder: they survive server restarts, a person can read them, and the
     CLI uses the same files and rules;
   - (b) memory in the server process;
   - (c) drafts in the knowledge base, which only the orchestrator may write (CLAUDE.md, rule 6).
5. **Images.**
   - (a) Return file paths, which the agent opens with its own file tool;
   - (b) return MCP image content.

   (b) counts against the 25,000-token result cap.
6. **Errors.**
   - (a) Convert the platform's expected exceptions to `ToolError`;
   - (b) let them surface, which hides the message the agent needs.

## Decision
- **Package and transport.** `backend/src/moonwalkers/mcp/` (1a, 2a), run with `uv run --no-sync
  ... python -m moonwalkers.mcp` from the project's `.mcp.json`. `--no-sync` means starting the
  server never installs anything.
  - The data folder comes from `MOONWALKERS_DATA_DIR`, else Claude Code's `CLAUDE_PROJECT_DIR`, else
    the repository.
  - The generator comes from `MOONWALKERS_GEN_ROOT`. Without it, earlier meshes are still reused,
    and new generation fails with a clear message.
  - Each tool call may take up to 10 minutes (`timeout` 600000).
- **Fifteen tools (3a).** They map onto CLAUDE.md's list:

  | CLAUDE.md action | Tools |
  |---|---|
  | check knowledge base | `check_knowledge_base` (read-only), `request_twin` (reuse through the orchestrator) |
  | add source | `start_run`, `add_input` (the photo), `add_reference_source` (documents) |
  | identify machine | `identify_machine`, plus `add_fact`, `add_control`, `add_issue` for the other cited notes |
  | generate geometry | `generate_geometry`, `inspect_geometry` |
  | add joint | `add_joint` |
  | set scale | `set_scale`, from the cited `center_height` only |
  | export, submit | `preview_twin` (stores nothing), `submit_twin` (export before storing, decision 0012 and the orchestrator's export hook) |

- **State (4a).** Each run folder holds:
  - `request.json`, the job request;
  - `reference_facts.json`, the cited notes, validated as `ReferenceFacts`;
  - `geometry_spec.parts.json`, the two spec parts, which write `geometry_spec.json` once both are
    set.

  Decision 0012's rules hold: inputs are fixed after generation, the spec after assembly, and
  everything after the build.
- **Shared build step.** `pipelines/b/build.py` (`build_run`) is used by both the CLI and
  `submit_twin`.
- **Results (5a, 6a).** Each tool returns a small Pydantic model, with images as absolute PNG
  paths. Expected errors come back as `ToolError` messages. One lock runs the tools one at a time,
  because the SDK runs plain functions in worker threads.
- **Permissions.** No tool is pre-allowed in `.claude/settings.json`: the person approves calls
  during the run.
- **Procedure.** `docs/agent-procedure.md`. The end-to-end check runs in a fresh Claude Code
  session (Daniel's choice), and the agent reads and cites the facts itself.

## Consequences
- **Inspectable.** A build is a sequence of small cited steps that a person can follow in the run
  folder and the transcript. It costs more tool calls than a single "build" tool.
- **Context cost.** The tool definitions take about 8,800 tokens of the agent's context (35,051
  characters, measured over stdio). That is small next to the build itself.
- **Not tied to Claude Code.** Any MCP client can use the same server.
- **Groundwork for Phase 5.** The run-folder workspace and `build_run` give the API something to
  reuse.
- **No concurrency.** Tools are synchronous and run one at a time, which is fine for one agent.
  Several concurrent agents would need per-run locking.
- **Reversing it.** Moving to coarse tools or HTTP touches only `moonwalkers/mcp/`. The pipeline,
  orchestrator and knowledge base stay as they are.

## End-to-end check (2026-10-18)
- **The run.** A fresh Claude Code session in VS Code followed `docs/agent-procedure.md` with the
  suggested prompt:
  - it built `haas/ha5c@v3` (run `2026-10-18_run-001`);
  - it asked Daniel which front parts turn, showing previews of both options (he chose the nose
    only);
  - its second request reused v3.
- **Verified afterwards by the building session:**
  - all 26 quotes in v3's reading notes appear on the cited PDF pages;
  - both validators pass on all three files;
  - Daniel counts the run, despite one caveat: the agent read the worklog before the documents
    (worklog 2026-10-18).
- **No approval prompts.** Daniel saw no prompt to approve the project server, and none for tool
  calls. Claude Code's documentation says "In `claude -p` runs, Agent SDK sessions, and cloud
  sessions, the prompt can't be shown, so the server loads without asking". That the VS Code
  session counts as such a session is [INFERENCE], not confirmed. Prompts for tool calls depend on
  the session's permission mode, which was not recorded.
  - **The consequence:** in such sessions the server can start as soon as the project opens. It
    writes only inside `data/` and runs the generator only when asked. To keep it off, the
    documentation suggests listing it in `disabledMcpjsonServers`.
- **One friction point.** `identify_machine` failed when the agent cited the photo from
  `add_input`. The error now explains that reading notes cite only reference sources, and the
  procedure says so.

## Update for Phase 5 (2026-10-18)
- **The workspace moved.** `workspace.py` is now the shared package `moonwalkers.workspace`, also
  used by the API (decision 0014). `moonwalkers.mcp` still exports `Workspace`.
- **A sixteenth tool.** `list_jobs` is read-only. It lists open jobs, such as a photo uploaded in
  the dashboard, with each job's next step.
- **Reviews (decision 0015).**
  - Twin summaries carry `review_status` beside the stored `status`.
  - `check_knowledge_base`, `request_twin` and `start_run` follow the new reuse rule: the newest
    approved version, else the newest not rejected in review.
  - The agent has no review tool: only people approve or reject.
