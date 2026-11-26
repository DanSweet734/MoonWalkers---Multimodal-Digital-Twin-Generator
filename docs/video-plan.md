# The video plan

**Status (2026-11-25):** drafted below the hand-off; Daniel took every recommendation the same
day ("Decided on review"). Phase 1 starts after the pull request is merged on his word. The advisors approved both asks on 2026-11-19, so the plan covers
the cut-out tool and a second agent run first, then video ("The plan", below).

## Hand-off (2026-11-18, from the lab's machines plan's Phase 8 chat)
- **Start** on branch `docs/video-plan`, from `main` after PR #35 (merge commit `a17a90e`). The
  branch already holds one commit from the Phase 8 chat (2026-11-18): the research note on video
  input below, and this line. Then the advisors' answers; the plan follows.
  **Since PR #35:** Daniel rejected `haas/tm1@v4` in the dashboard (2026-11-19T02:09Z: "Mesh was
  broken in multiple spots, out of place, and holes were present where they shouldn't have
  been."); the merged docs still call it unreviewed, so correct them in this branch. Stop for
  Daniel's review with a pull request; merge only on his word.
  - Branches kept, since Daniel did not ask to delete them: every `feat/lab-phase-*` branch,
    `docs/lab-machines-plan` and the earlier plans' branches. `origin/Sarkis` is Sarkis's: read
    it, never touch it.
- **Your first task: the meeting of 2026-11-19.** Ask Daniel for the advisors' answers and record
  them (a worklog entry, and `docs/lab-machines-report.md`, section 8.1, as the drill-press report's
  section 7.1 did). The page he presents is https://claude.ai/artifact/3kcdDKCn5AZExqbsF8oJ6B.
  Its four asks, section 10:
  1. **a tool to draw cut-outs,** then a second agent run with it (the report's section 8.3, gap 1);
  2. **video:** may we start planning it? Both Haas mills reached level 3, the advisors' condition
     (meeting of 2026-11-12);
  3. **the VF-3's trunnion:** its plate, or the control's Settings 78 and 30, and a jog of +A then
     +B (memory "meeting-2026-11-19-items");
  4. **the lab's iRC program for the arm,** through Dr. Li's assistant, at Daniel's visit.
- **Then, on the advisors' answer to asks 1 and 2,** draft the plan below this hand-off: video
  only, the cut-out tool first and video after, or the cut-out tool alone (then this file's name
  changes with Daniel's word). Ask Daniel which, if the answers leave it open.
- **The scorecard's decision record** (the lab plan's list, "The scorecard, once the meetings have
  judged it") waits until after the meeting (Daniel, 2026-11-18). Write it then as decision 0039,
  with what the advisors said.

### Read first
- CLAUDE.md "Current phase";
- [the research note on video input](research/2026-11-18-video-input-options.md): routes A to F,
  Daniel's phone (no LiDAR), and how he was asked to film on 2026-11-19;
- [the lab's machines report](lab-machines-report.md): section 3's agent build, section 7's
  inaccuracies, section 8's open questions and tool gaps;
- [the lab's machines plan](lab-machines-plan.md): its shape (phases with checkbox items, each
  ending in a pull request), its scorecard, "A planned visit to the lab" and "Not in this plan";
- [the project context](research/project-context.md), section 0 (Dr. Li's walkthrough video) and
  topics 5 and 6 (SAM 2 and 3 for video, VGGT for many views); read the sections, not the whole
  file;
- [worklog 2026-11-18](worklog/2026-11-18.md): the agent's entry, and the Phase 8 chat's.

### What exists for video, and what does not
- **The contract and the router know video:** `InputType.WALKTHROUGH_VIDEO`
  (`contracts/pipeline_result.py`) goes to Pipeline B (`orchestrator/router.py`). **Nothing in
  Pipeline B reads a video yet** (the lab plan, "Questions the plan must answer").
- **No video reader is installed** in the backend (`backend/pyproject.toml`, 2026-11-18: FastAPI,
  mcp, numpy, pydantic, python-multipart, trimesh, usd-core, uvicorn). Whether the generator's
  environment (`C:\mw-gen`) holds one is not checked. Reading frames needs an install, asked first
  (CLAUDE.md, rule 3).
- **The generator takes at most four views** (Hunyuan3D-2mv; `docs/setup/generators.md`), each cut
  out first (decision 0029). The lab's photos needed hand-drawn masks for every machine; the
  agent's SAM-only cut-outs gave a worse mesh (report, section 3).
- **Daniel's plan for video:** "a separate trip", and start video "once the photo results are
  acceptable" (the lab plan's hand-off, "What Daniel decided" and its priorities, 2026-11-09).

### Two uses of video in the record
1. **As input for the geometry** (Dr. Li's walkthrough, project context section 0): frames as
   views. The smallest step [INFERENCE]: pick up to four frames of one machine and run them through
   the photo path that exists (views, cut-outs, the multi-view generator), so a video is a source of
   photos before it is anything more. Many-view reconstruction (VGGT) and video tracking (SAM 2/3)
   are researched, not tried or installed.
2. **As evidence of motion:** "Comparing with the real machine's motion needs the real machine
   moving, which is the video trip" (the lab plan, its scorecard). The visit list already asks for
   phone videos: a tool change on the TM-1 (to time it), and +A then +B on the VF-3's trunnion.
   `control compare` measures a twin's recording against a plan; a measure of a real machine's
   motion from video does not exist [INFERENCE: a first one could time an axis's move between two
   marks].

### Carried over, none blocking
- **The lab visit** (the lab plan's visit list), now after the meeting of 2026-11-19: each
  measure that changes a twin is a new version.
- **`haas/tm1@v4`** (the agent's) was rejected by Daniel on 2026-11-18 (the mesh); requests reuse
  the approved v3 (decision 0015). Corrected in the merged docs on 2026-11-25.
- **The tool gaps** in the report's section 8.3, gaps 1 to 9.
- **Decision 0035's update** (the nose on the spindle's axis) is in the Phase 8 pull request, for
  Daniel's review with it.
- **Time:** the semester ends about 2026-12-17 (CLAUDE.md); meetings stay weekly.

## The plan (draft of 2026-11-25)
Written by Claude Code from the hand-off above and the advisors' answers of 2026-11-19 (Daniel's
account, 2026-11-25). It also draws on the photos and videos of the lab visit of 2026-11-19, filed
the same day and looked at with scratch scripts (contact sheets, crops, frame strips). Nothing was
written to `data/` but the filed copies, their `SOURCES.md` rows and dated notes in three runs'
`RUN.md`. As before:
- every phase ends in a pull request and a stop for review;
- each phase runs in a new chat, with a hand-off written into this file;
- every stand-in is labelled and logged;
- nothing is installed without asking first.

### Decided on review (2026-11-25)
Daniel, the same day: "Go with your recommendations on all eight questions." So:

| Question | Answer |
|---|---|
| 1. The order | The cut-out tool and the second agent run first (Phases 1-2), then video (Phase 3) |
| 2. The file's name | `docs/video-plan.md` stays, for both |
| 3. Gaps 2, 3 and 9 | In Phase 1, with the cut-out tool |
| 4. The agent run's photos | The same eight of 2026-11-05 as v4's job |
| 5. The frame reader | ffmpeg, already on Daniel's machine, called as a program found on the PATH; no package added |
| 6. The first machine from video | The TM-1 |
| 7. The 01 arm | A twin in Phase 4 if time allows (option a); footage only otherwise |
| 8. The temp folder | May go. All 42 copies were byte-compared with the originals, then `data/machine photos (temp)/11-19-26/` was deleted (2026-11-25); the empty `machine photos (temp)/` stays as a drop folder |

Also from Daniel (2026-11-25):
- **No meeting this week:** the weekly meeting of 2026-11-26 is cancelled for Thanksgiving.
- **No advisors' page of the plan yet:** it comes next week, for the following meeting.

### What the advisors decided (meeting of 2026-11-19)
| Ask (the lab report's page, section 10) | Answer |
|---|---|
| 1. A cut-out drawing tool, then a second agent run | **Yes** |
| 2. Video input | **Approved** |
| 3. The VF-3's trunnion: plate, Settings 78 and 30, the +A and +B jog | Still unsure: note it and ask at the next lab visit |
| 4. The lab's iRC program for the arm | To be delivered "sometime next week" (the week of 2026-11-30 [INFERENCE, from Daniel's message of 2026-11-25]) |
| The scorecard | **Accepted as is** ([decision 0039](decisions/0039-the-scorecard.md)) |

So the plan does both, and the cut-out tool comes first. A video's frames need cut-outs as much as
photos do, and the second agent run measures the tool before video adds a new source [INFERENCE].

### What the visit of 2026-11-19 gives (filed 2026-11-25)
No lab member could meet Daniel, so nothing was operated, measured or shown on a screen. He took
34 photos and 8 videos (2.1 GB) on the Galaxy S22 Ultra, the videos 4K at about 60 fps
([research note, update of 2026-11-25](research/2026-11-18-video-input-options.md)).

| Machine | Videos | Photos | Settles | Leaves open |
|---|---|---|---|---|
| **TM-1** | Two full circles, chest height then higher (`133809`, `133841`) | 8: the front square on, a front corner, the pendant's side, a side guard, the back corners and the cabinet | The back is now seen: the stool of 2026-11-05 is gone; the caution panel still stands at the pendant's side (`133709`) | Every measure (no tape seen), the axes' directions and homes, the control's screen |
| **VF-3** | Two circles round the enclosure (`133039`, `133120`), close to a desk and a tool cart; one inside (`133413`) | 16: the back, the sides, the front, the pendant, the trunnion square on, its plate, the head | **The trunnion is a TR160** (its plate, `133507`). **The control is the Classic Haas Control** by its keys (`133254`): they match the 2012 manual (PDF pp. 15, 35-36), not the 2023 NGC manual (PDF pp. 34-35) | Settings 78 and 30, the +A and +B jog, the software version |
| **The lab's other ReBeL, the 01** (`igus-rebel6dof01`, new) | Two circles, landscape (`132340`, `132718`); a 1.5 s label clip | 10: its plate "REBEL-6DOF-01", 28.12.2023; its base plate; its asset tag; its tape; the arm from three sides and above | The connector box is on the 01 too, so the box no longer hints at what 02 changes | Everything about the twin's 02 (not filmed); the maker of the 01's hand |

- **Not the twin's arm:** Daniel, 2026-11-25: "All of it is the 01". The twin `igus/rebel6dof02`
  is the unit with the tape "Rebel-6DOF-02" and the next asset tag.
- **Blur:** the VF-3's circles have the most blurred frames: 19-24% of sampled frames fall under
  half the clip's median sharpness, against 2-11% for the TM-1 and 1-5% for the 01 (the research
  note's update) [INFERENCE: a tight space walked quickly].
- **What it means for the plan [INFERENCE]:**
  - **The TM-1's circles are the best first video test.** They give two complete heights and the
    back that v3 had to guess, and the approved `haas/tm1@v3` (from three photos) can be compared
    with the result on the same scorecard.
  - **The 01's circles** are the only footage of a machine with a public maker's model of its own
    version, so the scorecard's "shape against the maker's model" could score a video-built mesh.
    But it is a fourth machine.
  - **The VF-3's footage** is the weakest for geometry; its plate is a fact for its next version.

### What exists, and what each phase adds
- **Cut-outs** (decision 0029): per photo in `request.json`, one of:
  - `sam`: SAM 1 (`sam_vit_b_01ec64` in rembg 2.0.68), with a box and points;
  - `crop`;
  - `mask`: a PNG a person drew outside the tools.

  The MCP tool `set_photo` sets them and `preview_cutouts` previews them. v3's masks were "SAM's
  cut-out plus traced fill polygons", made by scripts (worklog 2026-11-11). Gap 1 (report 8.3): no
  tool draws or corrects a cut-out.
- **Video:** `InputType.WALKTHROUGH_VIDEO` routes to Pipeline B, which reads nothing from it. A
  frame reader is on Daniel's machine (ffmpeg 9.0.2 on the PATH; OpenCV 4.11.0 in `C:\mw-gen`). It
  is neither in the backend's dependencies nor on the teammates' machines (the research note's
  update).
- **The generator** takes up to four views, cut out first (decision 0022). A fed photo is fitted to
  800 pixels first (`part_views.fit_photo`), so a 4K frame serves it as well as a photo
  [INFERENCE: a frame's blur and compression, not its size, would make the difference].

### Success levels
The three levels stay for each new twin (the lab plan's "Success levels"). Every new twin is
scored on decision 0039's scorecard beside the version it is compared with. Each phase adds its own
measure below.

## Phase 0 - Plan
- [x] Read the record: CLAUDE.md's "Current phase", this hand-off, the research note, the lab report
- [x] `main` merged into this branch (PRs #36-#38, 2026-11-25)
- [x] The advisors' answers recorded (worklog 2026-11-25; the lab report, section 8.1)
- [x] The visit's 42 files filed by machine, SHA-256 checked, `SOURCES.md` rows; plates read; what
      they settle in the research notes, the report, the visit list and the runs' `RUN.md`
- [x] `haas/tm1@v4`'s rejection corrected in the merged docs
- [x] [Decision 0039](decisions/0039-the-scorecard.md), the scorecard
- [x] This plan, a pull request (#39); Daniel's answers to "Questions for Daniel" (2026-11-25,
      "Decided on review")
- [x] Merged on Daniel's word (PR #39, `a451e42`, 2026-11-25); then Phase 1's branch from `main`,
      its hand-off first
- [ ] The advisors' page of the plan: next week (Daniel, 2026-11-25), for the first meeting after
      Thanksgiving

## Phase 1 - A tool to draw and correct a cut-out

### Hand-off (2026-11-25, from the plan's Phase 0 chat)
- **Start** on branch `feat/video-phase-1-cutout-tool`, cut from `main` at `a451e42` (PR #39
  merged on Daniel's word, 2026-11-25). Its first commit is this hand-off. `docs/video-plan`
  is kept (no word to delete it).
- **Decided** (the plan's "Decided on review"): this phase carries the cut-out tool **and** the
  warnings for gaps 2, 3 and 9. Decision 0041 is the next free number (0040 is the PR labels).
- **No meeting on 2026-11-26** (Thanksgiving). The advisors' page of the plan is due next week,
  for the first meeting after it (Daniel); it is not this phase's job unless he asks.
- **The lab's iRC program** may arrive the week of 2026-11-30 (beside the phases). If it comes
  mid-phase, ask Daniel whether to take it here or on its own branch.

#### Where the cut-out lives now (read before designing)
- **The model:** `backend/src/moonwalkers/orchestrator/photos.py`: `CutoutMethod =
  Literal["sam", "crop", "mask"]`, `CutoutPoint` (x, y, keep), `Cutout` (method, box, points,
  mask, `min_piece` 0.02). Coordinates are fractions of the photo turned upright by its EXIF.
  `Cutout._check` ties the fields to the method ("a 'mask' cut-out gives the mask's file, and no
  box or points").
- **Where a mask is made:** in the generator's job script,
  `backend/src/moonwalkers/generators/scripts/hunyuan3d_shape_job.py` (`sam_prompt`,
  `mask_from_file`, the `method` branches near line 185, `ImageOps.exif_transpose` at line 53).
  It runs in `C:\mw-gen`'s environment, the only one with Pillow: **the backend has no Pillow**
  (found 2026-11-25). So polygons are best drawn into the mask there, after SAM's or the crop's
  mask and before `min_piece` [INFERENCE], and the backend only validates and passes them.
- **The run's record:** `pipelines/b/pipeline.py` `_cutouts` (near line 279) swaps a mask's path
  for its SHA-256 in the settings, so a changed cut-out is a changed mesh; the run folder refuses
  a change after generating (decision 0029). Polygons must enter that record too.
- **The tools:** MCP `set_photo` and `preview_cutouts` (`mcp/server.py` around lines 516-535;
  `mcp/reports.py` `CutoutPreview`); CLI `... pipelines.b cutouts <run>` writes
  `<run>/cutouts/sheet.png`.
- **The dashboard and API:** pages in `dashboard/src/pages/` (`JobPage.tsx` shows a job); pure
  logic in `dashboard/src/lib/` with `*.test.ts`; the API's routes are `api/jobs.py` (list, one
  job, create), `api/files.py` (`GET /api/files/{path}` serves data files for the dashboard),
  `api/twins.py`, `api/sources.py`. Nothing writes a photo's `cutout` from the API yet. After an
  API model change, `uv run python -m moonwalkers.api.typescript` (a test fails when stale).
- **The answer key for the check:** v3's masks were made by
  `data/machines/haas-tm1/part_cutting/2026-11-11_spec/make_masks.py` from SAM's cut-out plus
  `FILL` and `ERASE` polygons, in fractions of the upright photo, per photo. These are the proposed
  `add` and `remove`. Its masks: `data/machines/haas-tm1/runs/2026-11-11_run-003/masks/photo-
  134300.png`, `photo-134337.png`, `photo-134355.png` (`min_piece` 0.1; SAM's settings in
  `tm1_request.py` beside the script). A first test of the new fields: v3's polygons through the
  tool should give masks with an IoU near 1 against these [INFERENCE: SAM's run must match].

#### Gaps 2, 3 and 9 (the lab report, section 8.3; v4's faults)
- **Gap 2, a base on a small slab:** v4 (run `haas-tm1/runs/2026-11-18_run-001`) left `base_z`
  unset, the mesh's lowest point, and stood on a generated block about 0.62 x 0.45 m, 0.25 m tall,
  about 10 in. v3's script set `base_z` -0.75 and cut under z -0.763.
- **Gap 3, pieces of a removed part left in a kept part:** shards of v4's generated table block
  pass through the stand-in table.
- **Gap 9, no size checks:** the agent skipped `set_size_checks`, and neither `preview_twin` nor
  `dry_run_twin` said so.
- Each warning should fire on v4's spec and stay quiet on v3's (a test on each, from small
  fixtures, never the run folders).

#### Pitfalls from the Phase 0 chat
- Bash heredocs with quotes or Python triple quotes break here; write scripts with the Write tool
  (memory "bash-script-pitfalls").
- Serials, asset tags and IP addresses stay in `data/`; grep the diff before committing.
- The quick suite was 898 passed at `main` (2026-11-25), in about 5 minutes.

### What Phase 1 is to do
The advisors' ask 1; the report's gap 1. **Proposed shape** (a decision record, 0041):
- **Polygons on top of any cut-out.** A photo's `cutout` gains `add` and `remove` polygons, in
  fractions of the upright photo as boxes and points are now. They apply after SAM's or the crop's
  mask. This is how v3's masks were made by script, now in the tools. `mask` (a drawn PNG) stays.
- **For a person: the dashboard.** On a job's page, a photo opens with its cut-out drawn over it.
  The person clicks points to add a region or cut one out, sees the mask, and saves. The API writes
  the photo's `cutout` in `request.json`, with the same check as `set_photo`: a run that has
  generated refuses a change (decision 0029). The pure geometry goes in `dashboard/src/lib/` with
  tests.
- **For the agent:** `set_photo` takes the same polygons, and `preview_cutouts` shows them.
  - Where SAM still keeps a neighbour or loses a part after its tries, the procedure has the agent
    ask the user to draw the cut-out in the dashboard, with the option to skip (Dr. Li's rule,
    2026-11-05; `agent-procedure.md`, step 2).
  - [INFERENCE] An agent places polygons poorly by eye on a busy photo, so the person's route is
    the main one.
- **Proposed with it, all small:** warnings in `preview_twin` and `dry_run_twin` for the faults
  behind v4's rejection (Daniel's call, question 3):
  - the base stands on a small slab (gap 2);
  - pieces of a removed part stay inside a kept part where a moving part passes (gap 3);
  - a spec has no size checks (gap 9).
- [x] Decision 0041 (proposed; Daniel's four choices of 2026-11-25); code, tests (backend and
      dashboard), the tool guide, the procedure, the dashboard guide's section 3b. v3's masks
      rewritten as edits on SAM: IoU 0.999, 0.992, 0.997; the warnings fire on v4 (five) and are
      quiet on v3, the VF-3 and the arm (worklog 2026-11-25)
- [x] **Check (Daniel, 2026-11-25):** draw the cut-outs of the TM-1's three fed photos in the
      dashboard; the tool prints each mask's IoU against v3's drawn masks (a measure for this
      phase, no target). Done in "roughly 3 or 4 minutes", 8 edits in all: IoU 0.879, 0.933,
      0.873. Decision 0041 accepted as it stands
- [x] Pull request; stop for review (PR #40, merged on Daniel's word 2026-11-25, `feb69a9`)

**Measured by:** the drawn masks against v3's (IoU), the time Daniel takes, and the tests.

## Phase 2 - The second agent run
The advisors' ask 1, its second half. A fresh Claude Code session builds the TM-1 again from a
dashboard job, as in the lab plan's Phase 8 (with its run-sheet and starter prompt, updated). This
time it has the cut-out tool and the Phase 1 warnings.
- **Proposed inputs:** the same eight photos of 2026-11-05 as v4's job (question 4). Then the tool
  is the only change, and v3, v4 and the new version compare on one scorecard. The new photos come
  in Phase 3.

### Hand-off (2026-11-25, from the Phase 1 chat)
- **Start** on branch `feat/video-phase-2-agent-run`, cut from `main` at `feb69a9` (PR #40
  merged on Daniel's word, 2026-11-25). Its first commit is this hand-off. Its second takes
  v3's own numbers out of the slab warning and the procedure (below, "Limits of the test").
  `feat/video-phase-1-cutout-tool` is kept (no word to delete it). Stop for review with a pull
  request; merge only on Daniel's word.
- **Read first:** CLAUDE.md's "Current phase"; this hand-off; the lab plan's Phase 8 hand-off
  (`docs/lab-machines-plan.md`, "Phase 8", its run-sheet, starter prompt and "Then the Phase 8
  chat"), which this phase repeats; the lab report's section on the agent's build
  (`docs/lab-machines-report.md`, "The agent's build (Phase 8)") and its section 8.3, the tool
  gaps; decision 0041 and [worklog 2026-11-25](worklog/2026-11-25.md), Phase 1's entries.

#### What Phase 1 left
- **Decision 0041, accepted** (Daniel, 2026-11-25). A cut-out takes ordered edits (polygons, and
  lines with a width, to add or remove) on any method, and an `auto` method; `set_photo` sets
  them; a job's page in the dashboard draws them ("Edit the cut-out") and previews them through
  the API when it was started with `MOONWALKERS_GEN_ROOT`.
- **The spec warnings** (`pipelines/b/spec_warnings.py`): a slab under the twin, loose pieces
  inside a replacing stand-in along its travel, no size checks. In `preview_twin`'s issues and
  `dry_run_twin`'s `spec_warnings`; they never change `clean`. On v4's spec: five; on v3's: none.
- **Daniel's check:** he drew the three corners in "roughly 3 or 4 minutes", 8 edits on `auto`,
  IoU 0.879, 0.933 and 0.873 against v3's masks (his drawing is in
  `data/scratch/2026-11-25_cutout-tool-check/`; the agent must not see it).
- **The procedure** (`agent-procedure.md`, step 2, item 5): the agent tries SAM and its own
  edits, and after two or three tries asks the person to draw in the dashboard, offering to skip
  (Daniel's extension of Dr. Li's rule, 2026-11-25). Step 5b, items 8-10: act on each warning or
  say why in an issue.
- **Logged, not this phase:** the T33901's crank becomes an issue in its next version (Daniel).
- **The quick suite:** 926 passed at `main` (about 5 minutes).

#### What is different from v4's run, and what stays
- **The same:** the job (eight photos, views and uses as v3's, "Build a new version" ticked),
  the documents, the held-back files, level 3 by Haas's O40001, Daniel's answers to the likely
  questions on scale and stand-ins, the Isaac Sim checks (check guide sections 11 and 12).
- **Different:**
  - the API is started with `MOONWALKERS_GEN_ROOT`, so Daniel can draw when the agent asks;
  - v3's drawn masks are **not** offered as a fallback (v4's run-sheet offered them): the tool is
    what is measured [INFERENCE];
  - the MCP server starts afresh in the new session, so it has Phase 1's `set_photo` (`/mcp`
    should list `moonwalkers` with 28 tools);
  - the dashboard must be built from `main` (`npm run build` in `dashboard/`) so its editor is
    there; Phase 1's build is in `dashboard/dist/`, but build again after pulling.
- **The new version** will be `haas/tm1@v5`. `request_twin` after its submission should still
  answer v3 (approved; v5 is not reviewed). That is expected.

#### Limits of the test [INFERENCE]
- **CLAUDE.md**, which every session loads, describes v3 and v4 at length (three corners, the
  stand-ins, the 12 in Y travel, v4's pedestal and shards, v3's IoUs). As for v4's run, name it
  in the report as a limit.
- **v3's floor line:** the slab warning's text and the procedure gave v3's `base_z` and cut
  height for this very machine. The branch's second commit replaces them with the method alone
  (set `base_z` at the floor line and cut a little below it), so the agent measures its own.
- **The procedure and the tool guide** name v4's faults and v3's mask IoUs: that is the tool's
  documentation, and the agent may read it.

#### Daniel's run-sheet for the agent's build (v4's, updated)
Two Claude Code sessions: **the agent** (a fresh one that builds, recorded) and **the Phase 2
chat** (this hand-off's reader, which checks and reports). Keep them apart.

1. **Before recording.** On `feat/video-phase-2-agent-run`, pulled. In `dashboard/`:
   `npm run build`. In `backend/`, PowerShell: `$env:MOONWALKERS_GEN_ROOT = "C:\mw-gen"`, then
   `uv run python -m moonwalkers.api`; open http://127.0.0.1:8000/.
2. **The job, in the dashboard** (`docs/setup/dashboard.md`, section 3, step 6): manufacturer
   `Haas Automation`, model `TM-1`, **"Build a new version" ticked**. Pick all eight photos in
   `data/machines/haas-tm1/inputs/photos/`:

   | Photo | View | Use |
   |---|---|---|
   | `20261105_134300.jpg` | Front-left corner (your left) | Used to make the 3D model |
   | `20261105_134337.jpg` | Front-right corner (your right) | Used to make the 3D model |
   | `20261105_134355.jpg` | Back-left corner (your left) | Used to make the 3D model |
   | `20261105_134314.jpg` | Front | Kept as evidence |
   | `20261105_134322.jpg` | Right side (your right) | Kept as evidence |
   | `20261105_134329.jpg` | Back-right corner (your right) | Kept as evidence |
   | `20261105_134346.jpg` | Left side (your left) | Kept as evidence |
   | `20261105_134411.jpg` | A close-up or part of the machine | Kept as evidence |

   Origin, for every photo: "Photographed by Daniel Sweet in Dr. Li's lab, CSUN, 2026-11-05; the
   team's own photo; internal research only; shows serial numbers, keep out of commits." Start
   the job. **Do not draw any cut-out yet**: the agent starts from none, as v4 did. The Phase 2
   chat checks `request.json` against this table before the agent starts (v4's job had one use
   wrong, `134355`).
3. **Record** (the Snipping Tool or the Game Bar, Win+Alt+R; in parts is fine), and note the
   start and end times.
4. **The agent.** A new Claude Code session at the repository's root; paste the prompt below.
   Allow its tool calls as they come.
5. **Its questions.** The answers are Daniel's; each goes in the report as human help. Likely
   ones, with suggested answers:
   - *It asks you to draw a cut-out:* draw it in the dashboard ("Edit the cut-out"), save and
     preview, time it, then tell it "Drawn and saved; preview again". Or "Skip it" where the
     photo is good enough. (The measure: how often it asks, and what you draw.)
   - *Which height or width scales the twin:* "Your call: cite it, and log the disagreement"
     (v4's agent asked; Daniel answered "Width 90 in").
   - *An axis's direction or home that no source gives:* "A labelled stand-in, logged."
   - *A spec warning it cannot clear:* "Your call: fix it, or say why in an issue."
6. **After its submission.** It reports the reuse check, its comparison and a worklog summary,
   and commits nothing. Stop the recording.
7. **Isaac Sim, on the agent's run** (the Phase 2 chat gives the files and targets): level 1 by
   eye on `twin.usdc` (stands flat? shards? holes? Daniel's reasons for rejecting v4); level 2 as
   in section 11; level 3 as in section 12.
8. **Review in the dashboard:** Daniel's alone, once the checks are in.

#### The agent's starter prompt
```text
Use the MoonWalkers MCP tools to build a new version of the Haas TM-1 twin, with a program it
runs, for the open dashboard job (list_jobs finds it). Follow docs/agent-procedure.md, including
section 5b (a machine of several parts), the cut-outs (step 2: preview_cutouts, set_photo with
edits, and asking me to draw in the dashboard), the spec warnings (5b, items 8-10) and step 3's
programs.

What you may read, and what not until you have submitted:
- Read the Haas documents in data/machines/haas-tm1/inputs/documents/ yourself (listed in
  data/machines/haas-tm1/inputs/SOURCES.md): the Toolroom Series sheet, the Toolroom addenda of
  2002 and 2009, the TM-1 layout drawing, the mill operator's manuals of 2009 and 2023, and the
  two saved web pages. Cite every fact with its PDF page and a short quote. Where sources
  disagree, name both, pick one and say why.
- You may read docs/agent-procedure.md, docs/tool-guide.md, the decision records in
  docs/decisions/, and backend/src/moonwalkers/control/programs/haas-o40001-basic-program.json as
  the format of a mill program. State its machine and setup for your own joints and frame, and
  cite the manual's pages for the program yourself.
- Do not open, until you have submitted: backend/src/moonwalkers/pipelines/b/haas_tm1.reference.json,
  anything under data/machines/haas-tm1/part_cutting/ or data/machines/haas-tm1/runs/ other than
  your own run, data/machines/haas-tm1/programs/, anything under data/scratch/ but your own dry
  runs, the research notes on the TM-1 and on mill programs in docs/research/, the worklogs,
  docs/lab-machines-plan.md, docs/lab-machines-report.md or docs/video-plan.md. Measure the mesh
  yourself with the tools.

While building:
- Open every view the tools return: the cut-out sheet, the mesh views, each part_<id> view and
  the photo overlays.
- Where a cut-out keeps what stands in front of the machine or loses part of it, correct it with
  set_photo (SAM's box and points, and edits); after two or three tries, ask me to draw it in the
  dashboard or to skip it.
- Act on every spec warning in preview_twin and dry_run_twin: fix it, or say why in an issue.
- For level 3, record Haas's basic program O40001 (2023 Mill Operator's Manual, p. 102) as a
  program_interpreter behaviour with add_control, so the build writes its program folder.
- Ask me when a judgement changes the twin and the sources do not settle it. Install nothing.
  Never review the twin. Write no serial number from the nameplate photo anywhere in docs/.

Before submit_twin: dry_run_twin until it is clean (a submitted version is kept for good).
Then submit_twin, and run both validators on the stored twin.usdc, every file in checks/ and
the program folder's program.usdc: uv run python -m moonwalkers.usd.validate <file> and
uv run omni_asset_validate <file>, from backend/.

Afterwards:
- Call request_twin for the TM-1 and report its message (a newer approved version may be
  reused; say which and why).
- Compare your facts with backend/src/moonwalkers/pipelines/b/haas_tm1.reference.json, and your
  spec with data/machines/haas-tm1/runs/2026-11-11_run-003/geometry_spec.json (v3, approved) and
  data/machines/haas-tm1/runs/2026-11-18_run-001/geometry_spec.json (v4, rejected for its mesh).
  Report every difference, and which you think is right and why.
- Write a summary of the session in docs/worklog/<today's date>.md: the tools you called, in
  order; your choices and why; the questions you asked me and my answers; the cut-outs I drew;
  the spec warnings and what you did with each; the results; anything that went wrong; the tool
  gaps you found. Do not commit.
```

#### Then the Phase 2 chat
- **While the agent builds:** walk Daniel through the run-sheet a step at a time; it does not
  build, and does not answer the agent's questions for him. Before the agent starts, check the
  job's `request.json` against the run-sheet's table.
- **After the submission, check the agent's run** (from `backend/`), as Phase 8 did:
  - the transcript (`~/.claude/projects/<project>/<session>.jsonl`): no held-back path in any
    tool call before `submit_twin`; count the MCP calls by tool, and the cut-outs Daniel drew;
  - the quotes: `uv run python -m moonwalkers.pipelines.b.quotes <run>/reference_facts.json
    <run>/geometry_spec.json --data ../data` (v4: 51 of 51 checkable found);
  - both validators on `twin.usdc`, every check file and `program.usdc`;
  - the spec warnings on the stored run (Phase 1's scratch script `run_warnings.py` is gone with
    its chat's scratchpad; `spec_warnings(oriented_mesh(...), spec, scale)` as in
    `dry_run.run_spec_warnings`);
  - no serial number in the agent's worklog entry.
- **The scorecard** (decision 0039): `uv run python -m moonwalkers.pipelines.b.score <run>
  [--recording <csv> ...]`, no maker's file for the TM-1; v5 beside v3 and v4. The photo match
  (IoU) against v4's 0.688, 0.612, 0.773 and v3's 0.751, 0.797, 0.842; the cut-outs' IoU against
  v3's masks, run on a copy of the run's `request.json` in a new scratch folder, never in the run
  itself, whose `cutouts/` is the agent's record (as Phase 1 did:
  `... pipelines.b cutouts <scratch run> --data ../data --compare
  ../data/machines/haas-tm1/runs/2026-11-11_run-003/masks`); v4's faults (pedestal, shards,
  holes) present or not; the session's time and calls, and Daniel's drawing time.
- **Level 3:** `uv run python -m moonwalkers.control compare <recording.csv>
  <folder>/trajectory.json`.
- **Then:** the report's update (the lab report's tool gaps, section 8.3, as closed or still
  open), the tool guide's "How the tools did", the worklog, the README and CLAUDE.md; a pull
  request; stop.
- [x] The run-sheet and starter prompt; Daniel starts the session; the chat checks the transcript
      (job `haas-tm1/runs/2026-11-25_run-001`, checked against the table before the agent
      started; the session 2026-11-25, 22:43-23:37 Pacific; below, "The second agent run")
- [x] **Check (Daniel, 2026-11-26):** levels 1 to 3 in Isaac Sim, as for v4: **all three met**;
      the review in the dashboard is his
- [x] The scorecard against v3 and v4; the tool gaps it finds; pull request (#41); stop

### The second agent run (2026-11-25 and 26)
The record: the agent's own entry in [worklog 2026-11-25](worklog/2026-11-25.md) ("The video
plan's Phase 2: the agent's second build"), the Phase 2 chat's in
[worklog 2026-11-26](worklog/2026-11-26.md), and the run's `RUN.md` (Daniel's check).
- **The session** (transcript `baa5b454`): a fresh Claude Code session, 54.4 min (06:43:32 to
  07:37:58 UTC), `submit_twin` at 45.7 min. 249 tool calls, 100 of them to 22 of the 28 MCP
  tools (v4: 88 to 20, 38.5 min): 18 `add_fact`, 15 `set_spec_part`, 12 `add_reference_source`,
  9 `preview_twin`, 8 `set_photo`, 7 `set_cut_list`, 6 each of `add_issue` and
  `set_spec_joint`, 4 `preview_cutouts`, 2 each of `inspect_geometry` and `fit_circles`, and one
  each of `list_jobs`, `check_knowledge_base`, `generate_geometry`, `identify_machine`,
  `set_spec_frame`, `set_scale_length`, **`set_size_checks`**, `add_control`, `dry_run_twin`,
  `submit_twin` and `request_twin`. No held-back path in any tool call before `submit_twin`.
- **Its three questions** (Daniel took the recommended answer each time):
  1. after three tries at the cut-outs: accept them, or draw in the dashboard? "Accept, generate";
  2. the scale: the 47.75 in table length or the 109 in height? "Table length";
  3. a 10-pocket carousel on a TM-1? "10 pockets".
- **The cut-outs:** SAM's box and points plus the agent's own edits (decision 0041), 2, 4 and 3
  edits, 55.2%, 48.1% and 69.2% kept; small remnants in front of the machine left (a floor coil,
  a hose, cords; the twin's issue). **Daniel drew none**: the drawing was offered, and declined.
- **What it built:** `haas/tm1@v5`, the same six parts and five joints as v3, scaled by the table
  length, with O40001's program folder. Spec warnings: one (frame pieces in the table's travel),
  acted on by shallower end guards, since the piece was machine; `dry_run_twin` clean on its first
  call with no warnings. Both validators clean on all five files (the chat's re-run too).
- **What it got wrong, by its own account and confirmed:** the arm's hold (10000, 200) instead of
  decision 0034's (100000, 632.5); a red handwheel on the table's end, not the saddle; the
  carousel-to-spindle distance (15.6 in) left out of its size checks.

**Daniel's Isaac Sim check (2026-11-26; the run's `RUN.md`):** levels 1, 2 and 3 met.
- **Level 1:** "It stands flat, I see no shards through the table, and I see no incorrect holes as
  far as I can tell"; a small cosmetic lump at the left guard's foot (the twin stands on its whole
  base at z 0, measured); a "large gap" under the head, where the agent cut out the generated
  spindle region for a small nose stand-in [INFERENCE].
- **Level 2:** every axis to both ends within 0.01 mm, the carousel exactly 36, 72, -36 and 0°;
  **the head rests 0.64 mm low** under the arm's hold (v3 0.014 mm). The table's tall end guards
  pass through the pendant and the carousel (parts do not collide, as in v3).
- **Level 3:** O40001 runs, the tip **within 0.645 mm** of the path while cutting, all of it the
  sag (v3 0.017 mm); the axes at 84.7 mm/s, 1000 rpm. A first try printed no "first physics
  step" and moved nothing (cause not confirmed); the repeat and a fresh session's run gave
  byte-identical recordings.

**The scorecard** (decision 0039), v5 beside v3 and v4 (each run's `score/SCORE.md`, the chat's
measures in [worklog 2026-11-26](worklog/2026-11-26.md)):

| Measure (target) | TM-1 `v3` (chat, approved) | TM-1 `v4` (agent, rejected) | TM-1 `v5` (agent, 2nd run) |
|---|---|---|---|
| Sizes (within 6%; over 10% flagged) | depth +0.6%; **height -24.0%**; carousel to spindle -9.6%; table -16.2% (replaced) | no size checks; the build's own: depth +8.7%, height -13.5% (pedestal) | cable carrier height -6.6%; the build's own: depth +2.7%, **height -11.3%**, **width +16.0%** |
| Photo match, its own cut-outs (no target) | 0.751, 0.797, 0.842 | 0.688, 0.612, 0.773 | 0.859, 0.789, 0.897 |
| Photo match, on v3's drawn cut-outs (one key) | 0.751, 0.797, 0.842 | 0.737, 0.757, 0.829 | 0.750, 0.769, 0.830 |
| Cut-outs against v3's masks (IoU) | 1 (they are v3's) | 0.855, 0.715, 0.899 | 0.841, 0.914, 0.867 |
| v4's faults: pedestal, shards, holes | none | all three | no pedestal, no shards; a gap under the head |
| Parts and joints | head, saddle, table, spindle, carousel | the same | the same |
| Ranges (within 1 mm) | within 0.01 mm | within 0.01 mm | within 0.01 mm |
| The head's hold | 0.014 mm | 0.0135 mm | **0.64 mm** |
| Control (the T33901's 0.63 mm) | tip 0.017 mm | tip 0.014 mm cutting (fixed folder) | **tip 0.645 mm cutting** (the sag) |
| Evidence (every quote found) | 76 found, 0 missing, 7 not checkable | 51 found, 0 missing, 22 not checkable | 61 found, 1 on another page, 0 missing, 12 not checkable |
| Time; calls | (built by the chat) | 38.5 min; 88 MCP calls | 54.4 min; 100 MCP calls; Daniel drew nothing |

- **The photo match needs one key [INFERENCE].** The scorer fits each twin to its own run's
  cut-outs (`generator/prepared`), so a looser cut-out scores higher. On v3's drawn cut-outs,
  v5's mesh is level with v3's on the front (0.750 against 0.751) and under it on the two others;
  every twin scores higher on v5's cut-outs. So v5's better cut-outs did not give a mesh that
  matches the photos better than v3's.
- **The cut-outs:** the agent's edits fixed v4's worst photo (134337, 0.715 to 0.914, near
  Daniel's own drawing's 0.933); the other two stayed near v4's.
- **What made the difference to v4's rejection** [INFERENCE]: the slab warning stayed quiet
  because there was no slab (the base is the chip pan), and the loose-piece warning made the
  agent look at the piece in the table's way. The one fault no warning caught is the hold.

**Tool gaps found in the second run** (the agent's seven, in its worklog, and the chat's):
1. **No check of a hold drive:** `set_spec_frame` takes any `hold_drive`, and nothing estimates
   the sag (m g / k) in `preview_twin` or `dry_run_twin`. The one fault that cost v5 its
   precision (agent's gap 1).
2. **Non-manifold points by hand:** one preview per guessed cut edge (agent's gap 2).
3. **Loose pieces are counted, not shown** (agent's gap 3).
4. **The photo overlays' cameras** were fitted 7, 32 and 33° from their slots (agent's gap 4;
   the report's 8.3, gap 6, still open).
5. **Stand-in pieces may not meet end to end,** and `repeat` steps only in a line (agent's gap 5).
6. **No measuring tools** (grid, sections, box extents); the agent wrote its own again (agent's
   gap 6; the report's 8.3, gap 4, still open).
7. **A program's numbers come late,** in the dry run's `PROGRAM.md` (agent's gap 7).
8. **The scorer's photo match has no common key** (the chat): each twin against its own cut-outs.
9. **A stand-in sweeping through the kept frame** along its travel is not warned (the chat): the
   loose-piece warning looks only at loose pieces; v5's end guards pass through the pendant.
10. **The runner sometimes does not start** (the chat): once, Play gave the recorder its steps
    but not the runner; not reproduced.

**Measured by:**
- the photo match (IoU), against v4's 0.61-0.77 and v3's 0.75-0.84;
- whether the faults Daniel rejected v4 for (pedestal, shards, holes) are present;
- the session's time and calls.

## Phase 3 - Video as a source of photos (route A)
The advisors' ask 2, its first step: a video becomes frames, and the frames go through the photo
path that exists. **Proposed shape** (a decision record, 0042):
- **A video in a job:** `add_input` and the dashboard's upload take an MP4 as
  `walkthrough_video`. It is filed under `inputs/videos/` with its `SOURCES.md` row, as on
  2026-11-25.
- **Frames as photos:** a new MCP tool shows a video's frames at chosen times as a contact sheet,
  with each frame's time and sharpness. It files the chosen frames as photos of the run:
  - each cites the video's SHA-256 and its time;
  - each has a view in the operator's words (decision 0022).

  From there, cut-outs (Phase 1), the generator and the cut list are unchanged.
- **The frame reader:** ffmpeg, already on Daniel's machine (question 5).
  - The backend calls it as a program found on the PATH, as it calls the generator. No package is
    added.
  - The tests use a tiny generated clip, or skip when ffmpeg is missing.
  - The teammates' setup guide says how to get it.
- **First machine: the TM-1, from its circles** (question 6):
  - four corners, the back right one among them;
  - built as a new version through the chat's script route, dry-run first;
  - compared with v3 on the scorecard;
  - its joints and programs carry over from v3's facts.
- [ ] Decision 0042; code, tests; docs (tool guide, procedure, pipeline guide on the input type)
- [ ] The TM-1 from video frames, dry-run, built; **Daniel's check** in Isaac Sim, levels 1-3
- [ ] Pull request; stop

**Measured by:**
- the scorecard against `haas/tm1@v3`: the photo match on the same photos of 2026-11-05, the
  sizes, and the back's shape against the new back photos;
- how many frames per view had to be skipped for blur.

### Hand-off (2026-11-26, from the Phase 2 chat)
- **Start** on branch `feat/video-phase-3-video-frames`, cut from `main` at `efdf90d` (PR #41
  merged on Daniel's word, 2026-11-26). Its first commit is this hand-off, with v6's record (below).
  `feat/video-phase-2-agent-run` is kept (no word to delete it). Stop for review with a pull
  request; merge only on Daniel's word.
- **Read first:** CLAUDE.md's "Current phase"; this hand-off and Phase 3's shape above; the
  research note [2026-11-18-video-input-options.md](research/2026-11-18-video-input-options.md)
  (route A, and its update of 2026-11-25: ffmpeg 9.0.2 on the PATH, the footage's blur);
  decisions 0022 (photo views and uses), 0029 and 0041 (cut-outs), 0039 (the scorecard);
  Phase 2's "The second agent run" (the scorecard of v5 and its ten tool gaps).

#### What Phase 2 left
- **`haas/tm1@v5`** (the agent's, run `2026-11-25_run-001`): levels 1-3 met in Daniel's check;
  **approved by Daniel in the dashboard** (2026-11-26), so a request reuses v5, not v3. Its one
  measured fault is the hold (the arm's 10000 and 200): the head rests 0.64 mm low, O40001's tip
  runs 0.645 mm off its path.
- **`haas/tm1@v6`** (run `2026-11-26_run-001`): v5 with decision 0034's hold (100000, 632.5) and
  nothing else, built by the Phase 2 chat on Daniel's "We can build v6 with decision 0034's hold
  if you think that's best" (2026-11-26), from
  `data/machines/haas-tm1/part_cutting/2026-11-26_spec/compose_v6.py`. It is **stored, as needs
  review**. Its state:
  - **Checks:** dry run clean. Both validators are clean on its five files.
  - **The same as v5:** the quotes (61 found, 1 on another page, 0 missing), the scorer's figures,
    and O40001's `program.nc` and `program.json`. `trajectory.json` differs only in the hold.
  - **At rest, headless** (Isaac Sim 6.2.0): the head holds at -0.0135 mm, where v5 sags
    -0.6445 mm in the same trial.
  - **Daniel's Isaac Sim check:** the steps are in the run's `RUN.md` ("For Daniel's check"):
    `twin.usdc` at rest, then O40001 with `control compare`. Where his check is recorded,
    `RUN.md` has it; if not, it is still to do.
  - **Reuse:** a request reuses the newest approved version, so v5 until Daniel approves v6.
  - Its expected result is the tip within about 0.02 mm of the path [INFERENCE: v3's 0.017 mm
    with the same hold; v5's 0.645 mm was its sag].
- **The hold check** (Phase 2's tool gap 1: nothing estimates a `hold_drive`'s sag in
  `preview_twin` or `dry_run_twin`): Daniel, 2026-11-26: "Let's do you recommendation on the hold
  check once we come across it in the road map." Not this phase's job unless a build here needs
  it; the plan's tool-gap work is where it goes. **Every build in this phase sets decision 0034's
  hold** in its spec.
- **The runner once did not start** (Phase 2, tool gap 10): Play gave the recorder its steps but
  the runner printed no "first physics step". If Daniel meets it again, the runner's header says
  to set `API = "omni.physx"` and run it again.

#### What Phase 3 should know before designing
- **The photo match needs one key** (Phase 2's tool gap 8). `score.photo_scores` fits a twin to
  its own run's `generator/prepared` cut-outs. A twin built from video frames has frames there, not
  the photos of 2026-11-05, so the plan's measure ("the photo match on the same photos of
  2026-11-05") needs the twin fitted to another run's prepared photos. Phase 2 did that with a
  scratch script calling `part_views.fit_fed_photos(scene, <other run>/generator/prepared,
  spec.yaw_deg)`; on v3's drawn cut-outs v3 scores 0.751, 0.797, 0.842, v5 0.750, 0.769, 0.830.
  An option on the scorer (a prepared folder to fit to) would make it a measure [INFERENCE].
- **The footage** (`data/machines/haas-tm1/inputs/videos/`, with their rows in `SOURCES.md`): two full
  circles, portrait 4K at about 60 fps: `20261119_133809.mp4` (27.7 s, chest height) and
  `20261119_133841.mp4` (30.1 s, higher, over the guards onto the table). 2-11% of sampled frames
  fall under half the clip's median sharpness (the research note's update). The stool of
  2026-11-05 is gone; the CAUTION panel still stands at the pendant's side.
- **The generator** takes up to four views (decision 0022) and fits each to 800 pixels
  (`part_views.fit_photo`), so a 4K frame costs no more than a photo there.
- **ffmpeg** is called as a program found on the PATH, as the generator is (question 5): no
  package added. It is not on the teammates' machines; tests skip without it or use a tiny clip.
- **Version numbers:** v6 is stored, so the TM-1 from video will be `haas/tm1@v7`. Build it by
  the chat's script route, dry-run first, as the plan says. Its scorecard sits beside v3, v5 and
  v6: v6 is the like-for-like photo-built reference, with the same hold.
- **The next free decision number is 0042.**
- **Beside the phase:** the lab's iRC program may come the week of 2026-11-30 (its own small pull
  request, "Beside the phases"); the advisors' page of the plan is due that week, for the meeting
  of 2026-12-03 [INFERENCE: the next Thursday] (Daniel, 2026-11-25).
- **The quick suite:** 926 passed at `main` after Phase 1; Phase 2 changed no code.

## Phase 4 (if time allows) - A second machine from video, or SAM 2 across frames
For Daniel to choose at Phase 3's review, from what it shows:
- **(a) The 01 arm from its circles:** a twin `igus/rebel6dof01`, scored against igus's own model
  of its version (the scorecard's shape row). It is the only machine where a video-built mesh can
  be scored against a maker's mesh. Its joints come from the 02's cited facts (the same
  documentation).
- **(b) SAM 2 tracking** (route B): one click on one frame, a mask on every frame. It is an install
  (the `sam2` code and a checkpoint, Apache-2.0); its size and versions are read before asking.
- **(c) The VF-3's next version** from the plate (TR160 as read, the Classic control), with the
  new photos for its back.

## Beside the phases
- **The lab's iRC program** (expected the week of 2026-11-30): run on `igus/rebel6dof02@v5`, as the
  lab plan's Phase 3 ran the labelled test. Decision 0033 ("as is until we know if we get the
  program from the lab") is revisited then. It gives a program folder, and no new twin unless the
  program needs one. Its own small pull request when it comes.
- **The next lab visit:** the lab plan's visit list, items 1-8 and 10-14, is still open.
  - First, Settings 78 and 30 and the +A and +B jog (the advisors); then the TM-1's jog and
    measures.
  - A phone video of each jog gives route E's simple measure: the time and direction of a move
    between two marks. That is a new scorecard row and an amendment of decision 0039.
  - Photograph the 02, not the 01, for the twin.
- **The report and the advisors' page:** at the end, before the semester ends (about 2026-12-17).

### Not in this plan
- Many-view reconstruction (route C), Gaussian splats (D), research methods for joints from
  motion (E's papers) and phone scan apps (F). The advisors put other ways to make the mesh later
  (2026-11-12); route C would be its own study.
- Pipelines A, C and D (their owners'); Neo4j, Celery, Codex; masses (a bonus).

### Decision records this plan needs
Numbered when written: 0039 is written and 0040 is taken (PR labels), so 0041 is the next free.

| Title | Phase |
|---|---|
| The scorecard: [0039](decisions/0039-the-scorecard.md), accepted by the advisors | 0 |
| Drawing and correcting a cut-out (amends 0029) | 1 |
| A video as a source of photos (amends 0022) | 3 |
| The lab's iRC program, if it changes decision 0033 | beside |

### Questions for Daniel
Answered on 2026-11-25: every recommendation taken ("Decided on review", above).
1. **The order:** the cut-out tool and the second agent run first, then video (recommended, above),
   or video first?
2. **The file's name:** keep `docs/video-plan.md` for both (recommended), or rename it?
3. **Gaps 2, 3 and 9** (warnings for a base on a slab, shards in a kept part, no size checks): in
   Phase 1 with the cut-out tool (recommended: they are what v4 was rejected for), or later?
4. **The second agent run's photos:** the same eight of 2026-11-05 as v4 (recommended, so the tool
   is the only change), or the new ones of 2026-11-19?
5. **The frame reader:** ffmpeg, already on your machine and called as a program (recommended: no
   install; teammates install it only to use video), or a Python package in the backend (an
   install, asked separately)?
6. **The first machine from video:** the TM-1 (recommended), the 01 arm, or the VF-3?
7. **The 01 arm:** worth a twin in Phase 4, or footage only?
8. **The temp folder** `data/machine photos (temp)/11-19-26/`: may it go now that the copies are
   checked (every SHA-256 matched)?
