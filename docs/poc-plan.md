# Proof-of-concept plan

**Goal:** show that an AI agent can create a digital twin from one input type (machine photos).
**Machine:** Haas HA5C rotary indexer. **Decided:** Oct 16, 2026 (see `docs/decisions/`).
Stop at the end of each phase, open a pull request, and wait for review before starting the next.

## Success levels
1. A scaled 3D model of the HA5C, with cited facts, that opens in Isaac Sim.
2. The spindle is a separate part on a revolute joint that rotates in Isaac Sim.
3. An indexing program (absolute/incremental steps, per the 2006 operator's manual) drives the joint.
Plus: a second request for the same machine reuses the stored twin and the result says so.

## Phase 0 - Scaffold
- [ ] Python package under `backend/` with `uv`, ruff, pytest (ask before installing)
- [ ] Move the contract into `backend/src/moonwalkers/contracts/`; the contract test passes
- [ ] Vite + React + TypeScript app under `dashboard/` (ask before installing)
- [ ] Worklog entry, PR

## Phase 1 - Knowledge base and orchestrator core
- [ ] `KnowledgeBase` interface + JSON (or SQLite) implementation: save/load `TwinRecord`, look up by
      `machine_key`, versioning on user request
- [ ] Orchestrator turns `PipelineResult`(s) into a `TwinRecord`; `JobResult.reused_existing` works
- [ ] Stubs for Pipelines A, C, D returning fixture `PipelineResult`s
- [ ] Tests for reuse and re-versioning; worklog; decision record for the store choice; PR

## Phase 2 - USD export
- [ ] Exporter writes a `.usda` with correct units (`metersPerUnit`), parts as meshes, and a
      `PhysicsRevoluteJoint` with `ArticulationRootAPI` and an angular `DriveAPI`
- [ ] Validation: open with `pxr`, check joints reference real prims; optional `omni_asset_validate`
- [ ] Manual check in Isaac Sim 6.2.0 with a primitive test model (box + cylinder) before real meshes
- [ ] Worklog with screenshots described; PR

## Phase 3 - Pipeline B (machine photos -> geometry)
- [ ] Collect HA5C photos from public sources into `data/machines/haas-ha5c/inputs/`, logging each URL
- [ ] Generator adapter interface; Hunyuan3D-2mv adapter (multi-view), Stable Fast 3D fallback; each runs
      in its own environment as a subprocess (ask before installing either)
- [ ] Scale calibration from a known dimension (center height 4.000 in from the HA5C layout drawing)
- [ ] Mesh split into body and spindle (manual or semi-automatic for the PoC; document the method)
- [ ] Facts with citations from the Haas UK product page and the 2006 operator's manual
- [ ] Worklog with run details (versions, time, VRAM if available); PR

## Phase 4 - Agent via MCP
- [ ] MCP server in `backend/src/moonwalkers/mcp/` exposing the platform's actions as tools
- [ ] Project `.mcp.json` so Claude Code can connect; a written agent procedure in `docs/`
- [ ] End-to-end run where Claude Code drives the tools to build the HA5C twin; transcript summary in worklog
- [ ] PR

## Phase 5 - API and barebones dashboard
- [ ] FastAPI endpoints for jobs, twins, sources
- [ ] Dashboard: upload photos, see job status, see twin with sources and review status
- [ ] PR

## Phase 6 - Control logic (level 3)
- [ ] Represent the indexing program as a `ControlBehavior`; a small interpreter that turns G90/G91
      steps into joint drive targets
- [ ] Demonstrate in Isaac Sim; document limits honestly
- [ ] PR and a short PoC report in `docs/`
