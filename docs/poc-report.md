# MoonWalkers proof of concept: report

**Status: draft.** Level 3 waits on its Isaac Sim check (section 3). Written 2026-10-18 by Claude
Code with Daniel Sweet; the evidence for each claim is linked.

## 1. The question
Can an AI agent create a functional digital twin from one input type? The input is machine photos
(Pipeline B), and the machine is the Haas HA5C rotary indexer. "Functional" means moving parts
and control logic, as confirmed by our advisors. The pass criteria are in
[docs/poc-plan.md](poc-plan.md) and decision 0002:

1. A scaled 3D model with cited facts opens in Isaac Sim.
2. The spindle rotates on a joint.
3. An indexing program, from the 2006 operator's manual, drives the joint.

Also, a second request for the same machine must reuse the stored twin and say so.

## 2. What was built
| Phase | What | Decisions | PR |
|---|---|---|---|
| 0 | Python backend (uv, ruff, pytest), React dashboard scaffold, the shared `PipelineResult` contract | 0001-0007 | #1 |
| 1 | Knowledge base (JSON files) and orchestrator: reuse a stored twin, re-version on request | 0008, 0009 | #2 |
| 2 | OpenUSD exporter: rigid bodies, a driven revolute joint, cited provenance; two validators | 0010 | #3 |
| 3 | Pipeline B: one photo to a mesh (Hunyuan3D-2), then a cited geometry spec orients, splits and scales it | 0011, 0012 | #6, follow-up #7 |
| 4 | An MCP server (15 tools, now 16) so Claude Code drives the platform; a written agent procedure | 0013 | #8 |
| 5 | A local FastAPI API and a barebones dashboard: upload, follow a job, review twins with their sources | 0014, 0015 | #9 |
| fix | Find the spindle axis when the spindle is not the front-most part (found on the TH240) | 0012 | #10 |
| 6 | Indexing programs: the manual's step table, an interpreter, a runner for Isaac Sim | 0016 | this PR |

Every fact in a twin cites a source with a page or quote, and a person reviews each twin. At the
end of Phase 6 the backend has 340 tests (`uv run pytest`) and the dashboard has 8.

## 3. Results
**Level 1, a scaled model with cited facts, opens in Isaac Sim: met.**
- **HA5C v2** opened in Isaac Sim 6.2.0 on 2026-10-18. Daniel measured its sizes close to the
  expected ones (worklog 2026-10-18). The scale comes from the drawing's 4.000 in centre height,
  and the width and height are within 3% of the drawing (decision 0012).
- **Haas TH240 v1** (a second machine, from a dashboard upload) opened on 2026-10-18. Its height
  is within 0.1% of the drawing, its width +2.7% and its depth +6.6% (its `RUN.md`).

**Level 2, the spindle rotates on a joint: met.**
- **HA5C v2:** the spindle turned at the set speed, reversed when the target was set to -90, and
  held a quarter turn, with no collisions. Small seam gaps show after turning; they are cosmetic
  (decision 0012).
- **TH240 v1:** the platter turned cleanly about its own centre, with no wobble and no collisions.

**Level 3, an indexing program drives the joint: built, Isaac Sim check pending.**
- The manual's step table runs through an interpreter into joint targets over time. Its own stated
  equivalences hold exactly: Example #3 equals its circle-division form, and Example #5 equals its
  subroutine form.
- A runner sets the drive's target position and velocity every physics step (decision 0016).
- Program folders for HA5C v3 (Examples #5 and #3) pass both validators. Daniel's check follows
  [docs/setup/isaac-sim-check.md](setup/isaac-sim-check.md), section 7.

**Reuse: met.**
- After the fresh agent built HA5C v3, its `request_twin` answered "Found an existing twin (v3,
  needs review) for haas/ha5c; reused it."
- In the dashboard, an upload for the HA5C stopped at once and reused v3 (worklog 2026-10-18).

**The agent.**
- A fresh Claude Code session built HA5C v3 through the MCP tools: it read the manual and the
  drawing itself, and all 26 of its quotes check out. It asked Daniel one question, which parts
  turn.
- Another session built the TH240 from a dashboard job. It asked Daniel to save a web page that
  blocks scripts, and the spindle question again.

## 4. Per-run record
The methodology asks for these per run (`docs/methodology.md`, "Evaluation"). The generator was
Hunyuan3D-2 2.0.2 for all four, with seed 12345, on an RTX 4090 (each run's `RUN.md`).

| Twin | Run folder | Built by | Input | Generation | Success level | Review |
|---|---|---|---|---|---|---|
| haas/ha5c@v1 | `haas-ha5c/runs/2026-10-17_run-002` | Claude Code (CLI) | Haas UK photo | 49.4 s | not checked (the text USD failed NVIDIA's performance check, so v2 was made) | needs review |
| haas/ha5c@v2 | `haas-ha5c/runs/2026-10-17_run-003` | Claude Code (CLI) | the same photo | 49.0 s | 2 (Daniel, 2026-10-18) | needs review |
| haas/ha5c@v3 | `haas-ha5c/runs/2026-10-18_run-001` | a fresh Claude Code session through MCP | the same photo | 46.8 s | not checked on its own: its mesh measures the same as v2's, and its spindle cut is about 0.4 mm away; the program check (level 3) is pending | needs review |
| haas/th240@v1 | `haas-th240/runs/2026-10-18_run-001` | Claude Code through MCP, from a dashboard job | Haas TH240 page image | 57.1 s | 2 (Daniel, 2026-10-18) | needs review |

The metrics from Dr. Li's agentic-pipeline deck were not measured formally for these single-photo
runs: component coverage, count accuracy, spatial plausibility and visual match. That is a step
for the integration phase.

## 5. Limits, stated plainly
- **One photo.**
  - The generator guesses every side the photo does not show: the TH240's back is visibly
    invented.
  - Sizes come from one cited dimension, so other dimensions are off by up to several percent.
  - The multi-view generator was not run, because no multi-view photo set exists yet.
- **Placeholder physics.** Masses come from a placeholder density (1000 kg/m³), and the drive's
  stiffness and damping are simulation choices, not machine facts.
- **One joint about the front axis.** Pipeline B builds one spindle on one revolute joint. The
  backup drill press needs other axes, several joints and a sliding joint (`docs/poc-plan.md`,
  "Before more machines").
- **Control is a model of the manual, not of the controller.**
  - Acceleration is not modelled: the manual names the parameters but gives no HA5C values.
  - The pause after each step stands in for machining.
  - How absolute and home moves turn, and the spindle's positive direction, are not confirmed.
  - Running a program needs a pasted script in Isaac Sim.
- **A person stays in the loop.** The agent asks a person when the sources do not settle a
  judgement, such as which parts turn, and needs a person to fetch pages that block scripts.
  Every twin waits for a person's review.
- **Local and single-user.** The API has no login and listens on 127.0.0.1 only. The knowledge
  base is JSON files with one writer at a time. Pipelines A, C and D are stubs.

## 6. Next
- **The level 3 check in Isaac Sim,** then this report's final version.
- **For the integration phase:**
  - multi-view input;
  - more joint types and machines;
  - the Neo4j knowledge base and Celery jobs;
  - Pipelines A, C and D from their owners;
  - formal metrics on the standardized test set.
