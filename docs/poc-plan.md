# Proof-of-concept plan

**Goal:** show that an AI agent can create a digital twin from one input type (machine photos).
**Machine:** Haas HA5C rotary indexer. **Decided:** Oct 16, 2026 (see `docs/decisions/`).
Stop at the end of each phase, open a pull request, and wait for review before starting the next.

**Complete.** All phases are done, and the PoC was presented to the advisors on Oct 22, 2026, with
positive feedback (`docs/poc-report.md`). The next phase, integration, starts with the Grizzly
T33901 drill press, which the advisors approved. Its plan is `docs/drill-press-plan.md` (Oct 22,
2026).

## Success levels
1. A scaled 3D model of the HA5C, with cited facts, that opens in Isaac Sim.
2. The spindle is a separate part on a revolute joint that rotates in Isaac Sim.
3. An indexing program (absolute/incremental steps, per the 2006 operator's manual) drives the joint.
Plus: a second request for the same machine reuses the stored twin and the result says so.

## Phase 0 - Scaffold
- [x] Python package under `backend/` with `uv`, ruff, pytest (ask before installing)
- [x] Move the contract into `backend/src/moonwalkers/contracts/`; the contract test passes
- [x] Vite + React + TypeScript app under `dashboard/` (ask before installing)
- [x] Worklog entry, PR (Oct 16, 2026: branch `chore/phase-0-scaffold`; also added a schema-drift test
      and decision record 0007)

## Phase 1 - Knowledge base and orchestrator core
- [x] `KnowledgeBase` interface + JSON (or SQLite) implementation: save/load `TwinRecord`, look up by
      `machine_key`, versioning on user request (JSON files, decision 0008)
- [x] Orchestrator turns `PipelineResult`(s) into a `TwinRecord`; `JobResult.reused_existing` works
      (reuse and versioning rules: decision 0009)
- [x] Stubs for Pipelines A, C, D returning fixture `PipelineResult`s (historical PoC; D now has an [Octopart adapter and a PDF catalog reader](setup/pipeline-d-octopart.md), with its fixture retained for tests)
- [x] Tests for reuse and re-versioning; worklog; decision record for the store choice; PR
      (Oct 16, 2026: branch `feat/phase-1-kb-orchestrator`)

## Phase 2 - USD export
- [x] Exporter writes a `.usda` with correct units (`metersPerUnit`), parts as meshes, and a
      `PhysicsRevoluteJoint` with `ArticulationRootAPI` and an angular `DriveAPI` (decision 0010)
- [x] Validation: open with `pxr`, check joints reference real prims; optional `omni_asset_validate`
      (both run in the test suite)
- [x] Manual check in Isaac Sim 6.2.0 with a primitive test model (box + cylinder) before real meshes
      (Oct 17, 2026, by Daniel: both test files opened and moved as expected; 0 errors in the log)
- [x] Worklog with screenshots described; PR (Oct 17, 2026: branch `feat/phase-2-usd-export`; no
      screenshots were shared, so the worklog records Daniel's description of what he saw)

## Phase 3 - Pipeline B (machine photos -> geometry)
- [x] Collect HA5C photos from public sources into `data/machines/haas-ha5c/inputs/`, logging each URL
      (Oct 17, 2026: only one clean photo was reachable, the Haas UK studio shot; the layout drawing and
      2006 manual are saved alongside it, all listed with URLs and hashes in `SOURCES.md`)
- [x] Generator adapter interface; Hunyuan3D-2mv adapter (multi-view), Stable Fast 3D fallback; each runs
      in its own environment as a subprocess (ask before installing either). Changed by decision 0011:
      one Hunyuan3D-2 adapter takes the single-image model (used, since there is one photo) or the
      multi-view one (not yet run: no multi-view photo set), and the fallback is Hunyuan3D-2 single-image
- [x] Scale calibration from a known dimension (center height 4.000 in from the HA5C layout drawing)
      (0.189268 m per model unit; width and height within 3% of the drawing)
- [x] Mesh split into body and spindle (manual or semi-automatic for the PoC; document the method)
      (semi-automatic: a cited geometry spec, decision 0012; the nose alone turns, Daniel's choice)
- [x] Facts with citations from the Haas UK product page and the 2006 operator's manual (plus the
      layout drawing; quotes checked against the PDFs; `pipelines/b/haas_ha5c.reference.json`)
- [x] Manual check of the HA5C twin in Isaac Sim 6.2.0: success levels 1 and 2 (Daniel;
      `docs/setup/isaac-sim-check.md`, section 6) (Oct 18, 2026: level 2 reached. Sizes measured close
      to expected; the spindle turns, reverses at -90 and holds a quarter turn. Small cosmetic gaps
      show at the cut after turning; see decision 0012)
- [x] Worklog with run details (versions, time, VRAM if available); PR (Oct 17, 2026: branch
      `feat/phase-3-pipeline-b`; twin `haas/ha5c@v2`, both validators pass)

## Phase 4 - Agent via MCP
- [x] MCP server in `backend/src/moonwalkers/mcp/` exposing the platform's actions as tools
      (Oct 18, 2026: 15 tools on the MCP Python SDK 2.3, state in the run folder; decision 0013)
- [x] Project `.mcp.json` so Claude Code can connect; a written agent procedure in `docs/`
      (Oct 18: Claude Code 2.1.302 lists the server as a project server awaiting approval;
      `docs/agent-procedure.md`)
- [x] End-to-end run where Claude Code drives the tools to build the HA5C twin; transcript summary in worklog
      (Oct 18, 2026: a fresh Claude Code session built `haas/ha5c@v3` through the tools, asked Daniel
      which parts turn, and showed reuse on a second request. All 26 of its quotes check out. It read
      the worklog before the documents, which Daniel accepted. Worklog 2026-10-18)
- [x] PR (Oct 18, 2026: branch `feat/phase-4-mcp-agent`)

## Phase 5 - API and barebones dashboard
- [x] FastAPI endpoints for jobs, twins, sources
      (Oct 18, 2026: `moonwalkers.api` on FastAPI 0.146, local only; jobs are run folders shared with
      the MCP server through `moonwalkers.workspace`; an upload reuses a stored twin at once or waits
      for the agent, which finds it with the new `list_jobs` tool. Decision 0014)
- [x] Dashboard: upload photos, see job status, see twin with sources and review status
      (Oct 18: jobs with live steps, twins with every fact's citation and quote, sources, and
      approve/reject reviews, Daniel's choice. Requests reuse the newest approved version, never a
      rejected one, decision 0015. Types generated from the API; `npm test` on Node's runner.
      Daniel's hand check in a browser: minimal but functional. A reused HA5C job worked, and a
      TH240 photo became `haas/th240@v1`, built by Claude Code from the dashboard job and level 2
      in Isaac Sim)
- [x] PR (Oct 18, 2026: branch `feat/phase-5-api-dashboard`, PR #9)

## Phase 6 - Control logic (level 3)
- [x] Represent the indexing program as a `ControlBehavior`; a small interpreter that turns G90/G91
      steps into joint drive targets
      (Oct 18, 2026: `moonwalkers.control`. The manual's step table lives in `spec["program"]`,
      and the interpreter runs it as auto-continue: G90/G91, home, circle division, dwell,
      subroutines. The manual's Examples #2-#6 ship as cited program files, and its two stated
      equivalences hold exactly. Builds and the CLI write a program folder with a runner for
      Isaac Sim. Decision 0016)
- [x] Demonstrate in Isaac Sim; document limits honestly
      (Oct 19, 2026: Daniel ran the manual's Example #5 on HA5C v3 in Isaac Sim 6.2.0. The spindle
      followed the program with the runner, and again after Stop then Play. The time-sampled file
      did the same with no script. Level 3 met. Limits: decision 0016 and `docs/poc-report.md`,
      section 6)
- [x] PR and a short PoC report in `docs/`
      (PR #11; `docs/poc-report.md`, with results per level, the decisions behind them and the
      limits)

## Before more machines (noted Oct 18, 2026)
Found while building the second machine, the Haas TH240, from a dashboard job. Do these before
Pipeline B is used on other machines.
- [x] `inspect_geometry` finds the spindle axis when the spindle is not the front-most part. On the
      TH240 the base's feet reach past the platter, so the tip slabs measured the feet. The agent
      worked around it with scratch scripts (decision 0012, "Known limitation"; candidates: a front
      limit, rim circle fits as a tool, a warning). Test it on a synthetic machine whose base
      reaches past its spindle.
      (Oct 18, 2026: fixed with warnings and RANSAC circle fits, a scan plus `circle_x`. On the
      real TH240 mesh the warnings fire and `circle_x` gives the platter axis; the HA5C is
      unchanged. Tested on a synthetic rotary table. Decision 0012, "The fix"; branch
      `fix/spindle-axis-not-front-most`)
- [ ] Joints other than one spindle turning about the front axis. Pipeline B builds exactly one
      revolute joint about the twin's +X: a spindle facing the front, as on the HA5C and TH240
      (`pipelines/b/pipeline.py`, `axis=(1.0, 0.0, 0.0)`; decision 0012). The backup machine, the
      Grizzly T33901 drill press, has "about five joints" (decision 0002). [INFERENCE] Its spindle
      turns about, and its quill slides along, a vertical axis, so it needs other axes, several
      joints and prismatic joints. Noted Oct 18, 2026, while fixing the item above; it needs its
      own decision. Not started. (Oct 19, 2026: its manual was read, and the seven decisions it
      needs are listed in `docs/poc-report.md`, section 8. Oct 22, 2026: planned in
      `docs/drill-press-plan.md`.)
