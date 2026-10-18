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
- [x] Stubs for Pipelines A, C, D returning fixture `PipelineResult`s
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
