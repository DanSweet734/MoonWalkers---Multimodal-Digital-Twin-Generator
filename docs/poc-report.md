# MoonWalkers proof of concept: report

**Status: final for the proof of concept, 2026-10-19.** All three success levels were met in Isaac
Sim 6.2.0. Written by Claude Code with Daniel Sweet; the evidence for each claim is linked.

**The answer, in short.** Yes: an AI agent can create a functional digital twin from machine photos.
- Claude Code, working through our platform's MCP tools, built a twin of the Haas HA5C rotary
  indexer from one photo. Every fact in it cites a Haas document, with a page or a quote.
- The twin opens at its real size in Isaac Sim, and its spindle turns on a joint.
- The manual's own indexing program (Example #5) drives that joint as the manual describes.
- A second request for the HA5C reuses the stored twin and says so. A second machine (the Haas
  TH240) went from a dashboard upload to a turning twin the same way.
- The main limits are one photo per machine, placeholder physics, one joint, and a control model
  built from the manual rather than the real controller (section 6).

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
| 6 | Indexing programs: the manual's step table, an interpreter, a runner for Isaac Sim | 0016 | #11 |

Every fact in a twin cites a source with a page or quote, and a person reviews each twin. At the
end of Phase 6 the backend has 341 tests (`uv run pytest`) and the dashboard has 8.

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

**Level 3, an indexing program drives the joint: met** (2026-10-19, decision 0016, "Isaac Sim
check").
- **The program.** The manual's Example #5, in its subroutine form, on HA5C v3. It indexes 90° at
  80 °/s and slow-feeds 15° at 25 °/s, three times, then returns home: 16.1 s with a 1 s pause
  after each move.
- **With the runner** (a script pasted into Isaac Sim's Script Editor), the spindle followed the
  planned timeline. Daniel: "It did exactly as you said." The runner reported the program finished
  at 16.112 s with its target back at 0°, and the spindle stopped where it started. Stop, then
  Play, ran it again from the start.
- **With no script.** The second file, `program_native.usdc`, stores the same motion as time
  samples on the drive's target. Opened in a new session, it made the same moves and stopped where
  it started. That answers an open question of decision 0016: Isaac Sim 6.2.0 follows a drive's
  time-sampled target by itself. By eye, the two files play identically (Daniel); their timing
  was not measured.
- **The logs** of all three sessions show no errors: the runner session and two no-script
  sessions. The one warning Daniel asked about, from
  `omni.anim.graph.core`, is printed while Isaac Sim's own extensions start, before any file is
  opened; it is not about the twin.
- **Behind it:**
  - The interpreter reproduces the manual's own stated equivalences exactly: Example #3 equals its
    circle-division form, and Example #5 equals its subroutine form.
  - The program files pass both validators.
  - One small fix came from the check: on the second Play the runner moved the spindle but
    printed nothing. It now prints its lines on every run.

**Reuse: met.**
- After the fresh agent built HA5C v3, its `request_twin` answered "Found an existing twin (v3,
  needs review) for haas/ha5c; reused it."
- In the dashboard, an upload for the HA5C stopped at once and reused v3 (worklog 2026-10-18).
- Since Daniel approved v3 on 2026-10-19, a request reuses it as the newest approved version
  (decision 0015).

**The agent.**
- A fresh Claude Code session built HA5C v3 through the MCP tools: it read the manual and the
  drawing itself, and all 26 of its quotes check out. It asked Daniel one question, which parts
  turn.
- Another session built the TH240 from a dashboard job. It asked Daniel to save a web page that
  blocks scripts, and the spindle question again.

## 4. Per-run record
The methodology asks for these per run (`docs/methodology.md`, "Evaluation"). The generator was
Hunyuan3D-2 2.0.2 for all four, with seed 12345, on an RTX 4090 (each run's `RUN.md`). Isaac Sim
was 6.2.0 for every check (Kit 110.4.0, build 386251, from the 2026-10-19 logs).

| Twin | Run folder | Built by | Input | Generation | Success level | Review |
|---|---|---|---|---|---|---|
| haas/ha5c@v1 | `haas-ha5c/runs/2026-10-17_run-002` | Claude Code (CLI) | Haas UK photo | 49.4 s | not checked (the text USD failed NVIDIA's performance check, so v2 was made) | needs review |
| haas/ha5c@v2 | `haas-ha5c/runs/2026-10-17_run-003` | Claude Code (CLI) | the same photo | 49.0 s | 2 (Daniel, 2026-10-18) | needs review |
| haas/ha5c@v3 | `haas-ha5c/runs/2026-10-18_run-001` | a fresh Claude Code session through MCP | the same photo | 46.8 s | 3 (Daniel, 2026-10-19, through the Example #5 program file built from this twin). Its size was not measured on its own: its mesh measures the same as v2's | **approved** (Daniel, 2026-10-19): "Shows mostly accurate surfaces and animations look good too" |
| haas/th240@v1 | `haas-th240/runs/2026-10-18_run-001` | Claude Code through MCP, from a dashboard job | Haas TH240 page image | 57.1 s | 2 (Daniel, 2026-10-18) | **approved** (Daniel, 2026-10-19): "Accurate geometry on at least half, spindle looks clear and model looks ready for further refinement and testing" |

Programs, written from the command line for the stored twin (folders under
`data/machines/haas-ha5c/programs/`):

| Program folder | Program | Duration, end | Checked |
|---|---|---|---|
| `2026-10-18_ha5c-manual-example-5-subroutine_v3` | Example #5, subroutine form | 16.112 s, back at 0° | level 3 (Daniel, 2026-10-19), with the runner and with no script |
| `2026-10-18_ha5c-manual-example-3_v3` | Example #3: four 90° and five 72° indexes | 11.667 s, at 720° (two turns) | not checked |
| `2026-10-19_ha5c-manual-example-5-subroutine_v3`, `2026-10-19_ha5c-manual-example-3_v3` | the same two, written with the runner that prints on every run | as above | not checked yet |

The metrics from Dr. Li's agentic-pipeline deck were not measured formally for these single-photo
runs: component coverage, count accuracy, spatial plausibility and visual match. That is a step
for the integration phase.

## 5. The decisions behind it, and why
Each choice below has a record in [docs/decisions/](decisions/), with the options, sources and
costs in full. This section puts them in one place: what we chose, what we did not, why, and what
it costs us.
- **Who decided.** Each item says who made the choice: the team, Daniel, or Claude Code
  proposing and Daniel reviewing and approving it.
- **Our reasoning.** Where no source states the reason and it is our own, it is labelled
  [INFERENCE].

### 5.1 Scope and approach
- **0001, the technology stack** (the team; the advisors left the stack to us).
  - **Chose:** Python with FastAPI for the backend, and React with TypeScript for the dashboard.
    Celery, Docker and the graph database come in the integration phase.
  - **Why:** similar projects, including two from Dr. Li's lab, are written in Python. NVIDIA's
    Omniverse web viewer sample is React, TypeScript and Vite, so a live 3D view stays possible.
  - **Cost:** React is new to the team. In the PoC, jobs run in-process.
- **0002, the scope** (the team).
  - **Chose:** the HA5C (backup: a Grizzly T33901 drill press), from photos only (Pipeline B).
    Pipelines A, C and D are stubs that return fixture data in the shared format.
  - **Why the HA5C:** one servo-driven spindle is one revolute joint, and its manual documents a
    real control language (absolute and incremental steps, loops, subroutines). Haas is one of
    Dr. Li's six product-data sources.
  - **Why one pipeline end to end,** rather than four partial ones: it proves the parts every
    pipeline depends on (orchestrator, knowledge base, reuse, export). Teammates can later replace
    their stub without touching the rest.
  - **Cost:** no public CAD was found for the HA5C to compare against, and the other input types
    are not yet shown.
  - **Sources that disagree.** The HA5C's top speed is 410 °/s on the Haas UK page but 330 or
    320 °/s in the 2006 manual. We use the Haas UK figure and record the disagreement. The agent's v3 used
    the manual's 330 °/s, since the page was not among its inputs; Daniel confirmed 410 °/s for
    later builds.
- **0003, Claude Code as the agent** (the team).
  - **Chose:** Claude Code, on Daniel's existing plan, drives the platform through our own MCP
    tools.
  - **Not chosen:** an agent loop in our backend calling a model API (paid per call), or a local
    open model (setup and quality unknown).
  - **Why:** no API cost. Because the platform's actions are tools, a different agent can drive
    the same tools later.
  - **Cost:** runs are interactive and count against the plan's usage limits. The final product's
    model and agent runtime are still to be researched.
- **0007, tooling** (the team): uv, Python 3.12 only, ruff, pytest, Oxlint, and TypeScript in strict
  mode. Every tool installs from a lock file, and nothing else depends on these choices.

### 5.2 What a twin holds, and where it is kept
- **0004, one shared output contract** (the team).
  - **Chose:** every pipeline returns a `PipelineResult` (version 0.1.0, SI units). It holds:
    - sources, the machine's identity and cited facts;
    - parts, scale, joints and control behaviours;
    - issues, and `needs_human_review` (true by default).
  - **Why:**
    - four people build four pipelines in parallel, so they need one agreed format;
    - validation refuses any fact, joint or behaviour that does not cite a known source, so "every
      fact cites a source" is enforced by the code, not by habit;
    - its shape mirrors the draft knowledge-graph schema, so moving to Neo4j is a mapping, not a
      redesign.
  - **Cost:** any change needs a decision record and a version bump. None was needed in the PoC.
- **0005 and 0008, the knowledge base** (the team; Daniel approved 0008).
  - **Chose:** a narrow `KnowledgeBase` interface. For the PoC it stores one JSON file per record
    under `data/kb/`, never overwritten.
  - **Not chosen:** SQLite, or Neo4j now.
  - **Why:** there is no database server to run, and a reviewer can open any record in an editor.
    The same tests run against every store, so a Neo4j store must pass them before it replaces
    this one.
  - **Cost:** one writer at a time and no queries. This changes when Celery workers arrive.
- **0009, reuse and versions** (Claude Code's proposal; Daniel approved).
  - **Chose:** each machine has a key, "manufacturer/model" (`haas/ha5c`). A request naming a
    machine with a stored twin reuses it without running any pipeline, and the reply says so. A
    new version is built only when asked for, and older versions are kept.
  - **Why:** this is the PoC's reuse criterion, and the team's Oct 16 decision that twins are
    "re-versioned on user request".
  - **Cost:** reuse relies on every source naming the machine the same way. Aliases must be added
    on purpose.
- **0015, human review** (Daniel chose the rules).
  - **Chose:**
    - a person approves or rejects a twin version in the dashboard, with their name and a reason;
    - each review is its own record, added and never edited;
    - a request reuses the newest approved version, else the newest one not rejected, and never a
      rejected one;
    - approving never locks a twin: it can still be rebuilt, and the rebuild takes over once it
      is approved too;
    - the agent can read a review but cannot write one.
  - **Why:**
    - the methodology keeps a person in the loop;
    - keeping reviews outside the contract avoided a version bump for all four pipelines;
    - "approved first" means an unreviewed rebuild never replaces a twin a person approved.
  - **Cost:** readers must use the review status, not the status the twin was built with.
    Reviewers are not authenticated (the API is local only).

### 5.3 From a photo to a 3D model
- **0006 and 0011, the image-to-3D generator** (the team; Daniel chose each setup option).
  - **Chose:** Hunyuan3D-2 (Tencent), in its own Python environment, called as a separate process.
    - Its multi-view model (2mv) stays the first choice for when the lab's multi-view photos
      exist.
    - The PoC used its single-image model, because only one clean photo was available.
    - Stable Fast 3D, the first fallback, was dropped: its Windows support is "experimental", and
      it needs a compiler and gated weights.
  - **Why:**
    - it runs on Windows with no compiling, in about 50 s per photo and 6.1 GB of GPU memory on
      the RTX 4090;
    - the same photo and seed gave identical geometry every time;
    - a separate environment keeps its dependencies, including the GPL-licensed pymeshlab, out of
      our backend.
  - **Cost:**
    - it guesses every side the photo does not show;
    - its license excludes the EU, the UK and South Korea, so a release abroad needs a new review;
    - about 12 GB on disk.
- **0012, from a photo to a scaled body and spindle** (Claude Code's proposal; Daniel chose the
  spindle split after seeing both previews).
  - **Chose:** an inspection step instead of full automation. The agent (or a person) looks at
    rendered views and measurements. It then writes a short, cited `geometry_spec.json`, which:
    - orients the mesh;
    - cuts out the spindle as a cylinder around its axis;
    - sets the scale.
  - **The scale** comes from one dimension that three Haas documents state: the 4.000 in centre
    height, from the spindle axis to the base. Other cited sizes are only checked: a difference
    over 10% is a warning [INFERENCE: our threshold].
  - **What turns.** The sources do not settle whether the six-screw disc behind the nose turns
    with it. Daniel chose the nose only, and every result labels that [INFERENCE].
  - **Why:**
    - none of the articulation tools we reviewed names industrial machinery as a test domain;
    - a spec is short, cited and reviewable, and the twin cites it like any other source;
    - run folders are never overwritten, so any build can be repeated.
  - **Cost:**
    - the method assumes one spindle along the machine's front axis;
    - sizes other than the centre height are off by up to several percent (HA5C v2: width and
      height -3%, depth +7.9%);
    - the cut leaves open edges, which are cosmetic because colliders are convex hulls.
  - **The fix before Phase 6 (PR #10).** The spindle axis was found from the mesh's front-most
    points, which on the TH240 were the base's feet. Two changes followed:
    - the tool now warns when that measurement looks wrong;
    - it fits circles to slices of the mesh (RANSAC, then a least-squares refinement), so the
      agent can take the axis from the round part.

    On the HA5C the result is unchanged. On the TH240 the fitted axis is about 0.9 mm from the one
    the twin was built with. The thresholds are ours [INFERENCE], set from two real meshes and
    synthetic tests.

### 5.4 Writing a twin that Isaac Sim can simulate
- **0010, the USD export** (Claude Code's proposal; Daniel approved).
  - **Chose:** standard UsdPhysics only:
    - rigid bodies, with the base fixed to the world;
    - a revolute joint (parent = body0, child = body1) with an angular drive;
    - an articulation root on the twin's top prim;
    - metres, kilograms and +Z up.

    Every citation is stored inside the USD file itself, on the root, each part and each joint.
    Twins with generated meshes are binary `.usdc` (0012): NVIDIA's validator fails text files
    with large arrays, saying they "should be stored in crate files for improved performance". Two validators run: our own and NVIDIA's `omni_asset_validate`, because each
    catches problems the other misses.
  - **The drive** is of the "acceleration" type, so its response does not depend on the
    placeholder masses. Stiffness is 100 and damping 20 [INFERENCE: our tuning, critically damped
    at 10 rad/s].
  - **Why:** open standards, so other tools can read the twin, and provenance that travels with
    the file.
  - **Cost:** masses come from the default density, 1000 kg/m³, until a source gives them. The
    drive gains are simulation choices, not machine facts.

### 5.5 How the agent and people use the platform
- **0013, the MCP server: one tool per action** (Claude Code's proposal; Daniel approved the SDK
  install).
  - **Chose:**
    - the official MCP Python SDK, over stdio: Claude Code starts the server, so there is no port
      to open;
    - 16 small tools, from checking the knowledge base, through adding a source, generating and
      inspecting geometry, and adding the joint and scale, to submitting the twin;
    - all of a build's state kept as files in its run folder.
  - **Not chosen:** a few coarse tools such as `build_twin(photo)`.
  - **Why:** the decisions that need judgement (the axes, what turns, where the scale comes from)
    stay visible and are cited one by one. A person can follow a build from its run folder, and
    any MCP client can use the same server.
  - **Cost:** about 15 tool calls per build. The tool descriptions take about 8,800 tokens of the
    agent's context (measured with 15 tools). One tool runs at a time.
- **0014, the API and the barebones dashboard** (Daniel chose the job flow, the install and the
  look).
  - **Chose:** a local FastAPI API (127.0.0.1 only) serving a plain monochrome React dashboard.
    - People can upload a photo, follow the job, see a twin with every fact's source and quote,
      and approve or reject it.
    - An upload for a machine with a reusable twin is answered at once. Otherwise the job waits
      for Claude Code, which finds it with `list_jobs`.
    - The API never runs the generator.
  - **Not chosen:**
    - the API starting Claude Code by itself, because the agent's question to the person could
      not yet reach the dashboard, and every job would use Daniel's plan;
    - the API running the generator, which would share the GPU between two processes.
  - **Protection without a login:**
    - only local host names are accepted;
    - a write needs a custom header, and is refused from other web sites.
  - **Types.** The dashboard's TypeScript types are generated from the API's schema by a
    175-line script of ours, because the usual tool (`openapi-typescript`) would not install next
    to TypeScript 6.
  - **Cost:** a person starts Claude Code on a dashboard job. There is no login, so the API is not
    ready for a network.

### 5.6 Control logic (Phase 6, decision 0016)
Claude Code proposed these. Daniel reviewed PR #11 and checked level 3.
- **How a program is written.** The manual's own step table, row by row: step number, step size
  S, feed F (or the target step for a subroutine call), loop count L and G code.
  - It is checked against the manual's limits: 99 steps, S up to 999.999, F from 0.001 to 270,
    and L up to 999.
  - The manual's Examples #2 to #6 ship as program files that cite their pages; their 28 quotes
    were checked against the PDF.
  - **Not chosen:** our own move list, which would be easier to run.
  - **Why:**
    - it is the machine's own language, so an agent copies it from the manual and a person checks
      it line for line;
    - the manual's stated equivalences become tests.
- **How it runs.** An interpreter turns the program into the joint's target angle over time. It
  runs the program as the control's auto-continue mode does (Parameter 10 = 2), every step after
  the last. The alternative, one step per Cycle Start from a mill, needs a mill the simulation
  does not have.
- **What the manual leaves open.** Each of these is a setting, recorded in every program folder,
  and each is our choice [INFERENCE]:

  | Question | Our choice | The alternative | Why | Confirmed? |
  |---|---|---|---|---|
  | What happens between steps? | A 1 s pause after each move (Parameter 16, "Auto Continue Dwell", 0 to 9.9 s) | No pause (`--dwell 0`) | It stands in for the machining after each index, and makes each index visible | No: the HA5C's value is not given |
  | Which way does an absolute or home move turn? | Directly to the programmed angle, so from 315° home is 315° back | The shortest way, 45° forward (`--absolute shortest`, like Parameter 27's option +24) | It is the plain reading of "absolute position command", and it does not depend on Parameter 27, whose HA5C setting is not given | No |
  | How does a move speed up and slow down? | It does not: each move runs at its feed rate from start to end | Model Parameters 18 and 44 | The manual names the parameters but gives no HA5C values | No: real moves take a little longer |
  | Which way is positive? | Right-handed about the twin's spindle axis (+X, out of the nose): counter-clockwise as seen from in front | Clockwise | Parameter 11 can reverse the real motor, and the manuals point both ways (section 7) | No |
  | How fast can it go? | The feed rate given, or the manual's 270 °/s without one, and never above the joint's cited top speed | None | Both limits are cited. The joint's cap (330 °/s on v3) slowed no example, since the manual's feeds stop at 270 °/s | Yes (cited) |
  | What about the signals to and from the mill (G86, G87, G89, G92, G93)? | No motion and no wait; G94 adds the manual's 250 ms | Simulate a mill | There is no mill in the simulation | The 250 ms is the manual's |
  | What about G73 and G85? | Refused, with the reason | None | G73 is a "peck cycle (linear operation only)", and the manual lists G85 without describing it | Yes (cited) |

- **How the program reaches Isaac Sim.**

  | Way | What it does | Result on 2026-10-19 |
  |---|---|---|
  | **The runner (default)** | A script pasted into the Script Editor sets the drive's target position and target velocity on every physics step. This is NVIDIA's advice for fixed time stepping. | Worked, and replayed after Stop, then Play |
  | **The native file** | Time samples on the drive's target position, with no script | Worked in 6.2.0 with no script |
  | **An OmniGraph** in the file | A graph node on each physics step | Not built: it cannot be built or tested outside Isaac Sim with our tools |

  The runner stays the default. Because it also sets the target velocity, the spindle does not
  trail the plan. With a position target alone, our drive trails a moving target by about 0.2 s
  of motion: 16° during an 80 °/s index [INFERENCE: the drive's damping divided by its stiffness;
  not measured]. Whether to make the no-script file the default comes after measuring both.
- **Where program files go.** In a new build, the program folder is written into the run folder,
  with the twin. For a twin already built, the command line writes it to a separate `programs/`
  folder, because run folders never change.

## 6. Limits, stated plainly
- **One photo.**
  - The generator guesses every side the photo does not show: the TH240's back is visibly
    invented.
  - Sizes come from one cited dimension, so other dimensions are off by up to several percent.
  - The multi-view generator was not run, because no multi-view photo set exists yet.
- **Placeholder physics.** Masses come from a placeholder density (1000 kg/m³), and the drive's
  stiffness and damping are simulation choices, not machine facts. The Haas UK page does give the
  HA5C head's weight, "48 lb 21.8 kg", which a later twin can use.
- **One joint about the front axis.** Pipeline B builds one spindle on one revolute joint. The
  backup drill press needs other axes, several joints and a sliding joint (`docs/poc-plan.md`,
  "Before more machines").
- **Control is a model of the manual, not of the controller.**
  - Acceleration is not modelled: the manual names the parameters but gives no HA5C values.
  - The pause after each step stands in for machining.
  - How absolute and home moves turn, and the spindle's positive direction, are not confirmed.
  - The runner is a script a person pastes into Isaac Sim. The no-script file works in 6.2.0 and
    looks the same by eye, but neither file's tracking of the plan was measured.
  - Only Example #5 was checked in Isaac Sim. The other examples are checked by tests only.
  - Only rotary indexing is modelled. The HA5C's linear mode (Parameter 12) and its CNC relay
    and remote inputs are out of scope.
- **A person stays in the loop.** The agent asks a person when the sources do not settle a
  judgement, such as which parts turn, and needs a person to fetch pages that block scripts.
  Every twin waits for a person's review. Daniel approved HA5C v3 and TH240 v1 on 2026-10-19,
  with his reasons. HA5C v1 and v2 are not reviewed: v3 replaces them, and a request reuses it.
- **Local and single-user.** The API has no login and listens on 127.0.0.1 only. The knowledge
  base is JSON files with one writer at a time. Pipelines A, C and D are stubs.
- **Licenses.** Hunyuan3D-2's license excludes the EU, the UK and South Korea. The team is in the
  US, so this matters only for a release or a deployment abroad (decision 0011).

## 7. Open questions, by priority
Daniel answered what he could on 2026-10-19. We then researched the machine questions ourselves
in trusted sources, the manuals and the makers' pages
(`docs/research/2026-10-19-open-questions-research.md`). A platform agent should do that
research one day too. What is left is below, most important first.

### 7.1 For the advisors
1. **Access.** The repository is private. Would you like to be invited as collaborators, or may we
   make it public? If it goes public, the team must first choose a license.
2. **How far control logic should go.** For a proof of concept, we consider a program that drives
   the joint as the manual describes "functional" enough. Should a later version also model the
   real controller's acceleration, and the signals between the indexer and a mill (the remote
   Cycle Start and the CNC relay)?
3. **The lab's photos.** When will they arrive, and of which machines? Multi-view photos would let
   us run the multi-view generator and test the size errors (item 10).
4. **A real HA5C.** Does the lab, or anyone at CSUN, have an HA5C or a similar Haas indexer? One
   look would settle items 7 to 9.
5. **The next machine.** Should the next twin be the backup drill press (section 8), or a machine
   from the lab?
6. **Evaluation.** Which of the metrics from Dr. Li's agentic-pipeline deck matter first? Our
   methodology lists asset retrieval correctness, component coverage, count accuracy,
   spatial-relation plausibility, placement quality, render-vs-input visual match and trace
   quality, plus a functional check of our own. On which test set should they be measured?

### 7.2 About the HA5C: researched, still open
7. **Does the six-screw disc turn?** No source found says. The 2006 parts list names a "SPINDLE
   COVER S5C" and a "BEARING END CAP", and lists six cap screws and six copper washers, without
   saying which part they hold. [INFERENCE] Six screws with sealing washers suggest a fixed
   cover, which agrees with the twin (the nose turns alone).
8. **Which way does a positive step turn?** The manuals point both ways.
   - The 2006 manual says "All Haas indexers home in the clockwise direction as viewed from the
     spindle", and the 2012 manual says the same, "as viewed from the platter/spindle".
   - Parameter 27's "+256: search for home in positive direction" implies that this clockwise
     search is the negative direction.
   - The 2012 manual says "The direction of G33 motion is clockwise when the step size is set to
     1.000", without saying from where.

   The twin turns counter-clockwise, as seen from the front, for a positive step.
9. **The controller's settings:**
   - the direction of a program's return home (Parameter 27);
   - acceleration (Parameters 18 and 44; for 18 the two manuals even give different scale
     factors, "(Par 18)*100" and "(Par 18)*10");
   - the pause between steps (Parameter 16).

   Neither manual gives the HA5C's values. The 2012 manual keeps the 2006 programming model.
   Whether a 2026 HA5C controller does is not confirmed.
10. **Sizes.**
    - The HA5C model is about 3% small in both width and height (v2: -3.0% and -3.0%). Is that
      the generator or our method? More photos from other angles would tell. A platform agent could find them online
      without needing a person.
    - Daniel read 7.93 in on the drawing as the depth from the spindle nose to the back. What 7.80
      in spans is not known.

### 7.3 Measurements still to make
11. **How closely the spindle follows the plan** in Isaac Sim: with the runner, with the no-script
    file, and the drive's settle time. This decides whether the no-script file can become the
    default.
12. **Two quick checks:**
    - the runner that prints on every run (written on 2026-10-19), and Example #3, both in the
      `2026-10-19_...` program folders;
    - writing the cited weight (21.8 kg) and top speed into the twin itself. Neither is in the
      file yet: masses use the placeholder density, and only the interpreter enforces the top
      speed.

### 7.4 Before more agents, users or a release
13. **Codex.** We want the platform to work with Claude Code and, later, Codex. Codex supports
    local MCP servers like ours, configured in `.codex/config.toml`, but its default tool timeout
    is 60 s, while generating a mesh takes 47-57 s. A Codex setup needs a longer timeout and a
    procedure worded for Codex. Not yet tried.
14. **Unattended runs.** Whether unattended `claude -p` runs stay on the subscription is not
    confirmed. That matters if the dashboard ever starts the agent itself (decision 0003).
15. **Several writers.** The API and the agent's MCP server are two programs that write into the
    same data folder. Today they write different files. With several users or agents, two could
    write the same file at once, and one write could be lost. The database planned for the
    integration phase (SQLite or Neo4j) handles that (decision 0008).
16. **The multi-view input order.** Which side of the machine each of the generator's four images
    must show, to be checked with its example images before the first multi-view run.
17. **One license not confirmed:** that of the background-removal model `u2net.onnx`, which the
    generator's rembg package downloads. The package itself is MIT. To check before any release.

## 8. Next
### What the next machine needs: the backup drill press
The Grizzly T33901 manual describes these motions:
- **the spindle** turns, at twelve belt-selected speeds, 340-2860 RPM;
- **the quill** slides 3-1/4 in, moved down by three downfeed handles and returned by a spring,
  with an adjustable depth stop;
- **the table** "moves vertically, rotates 360° around its center, rotates 360° around the column,
  and tilts 45° left or right", and each motion has a lock;
- **the controls** are a keyed ON/OFF switch, the LED and the laser.

The manual also gives a cited weight of 108 lb, and sizes. Today, Pipeline B builds one revolute
joint about the twin's +X, and the exporter refuses sliding (prismatic) joints, though the contract
allows them. [INFERENCE] A drill-press twin needs these decisions, each with its own record:
1. **Several moving parts from one mesh.** How to cut out the quill with the spindle and chuck,
   the handles, the table and its arm. One cylinder cut is not enough. The options include
   several cuts in the geometry spec, learned part segmentation, or more photos.
2. **Joint types and axes.** Vertical and tilted axes, and sliding joints for the quill and the
   table height. The exporter needs prismatic joints with linear drives.
3. **A chain of joints.**
   - The base and column are fixed.
   - The table arm slides up the column and turns around it.
   - The table tilts and turns on the arm.
   - The quill slides in the head, and the spindle turns in the quill.

   The exporter today handles one parent and one child.
4. **Coupled motion.** The downfeed handles turn while the quill slides. Leads to try: PhysX's
   rack-and-pinion joint, or NVIDIA's mimic joints. Neither is in usd-core's UsdPhysics, and
   neither has been checked in Isaac Sim 6.2.
5. **Springs, stops and locks.** The quill's return spring (a drive towards the top), the depth
   stop (an adjustable limit), and adjustments that are locked rather than driven.
6. **Control logic for a manual machine.** It has no program. Its "control" is a keyed switch, a
   belt speed chosen from twelve, and the operator's feed down to the depth stop. We need to decide
   how a `ControlBehavior` describes that.
7. **Facts and scale.** Which cited dimension sets the scale (for example the 7 in from spindle to
   column), and how the cited 108 lb is split between the parts.

### For the integration phase
- multi-view input, and an agent that finds more photos and documents online;
- more joint types and machines (above);
- measured tracking of programs in Isaac Sim, then a choice between the runner and the no-script
  file;
- the Neo4j knowledge base and Celery jobs;
- Pipelines A, C and D from their owners;
- a Codex setup beside Claude Code;
- formal metrics on the standardized test set.
