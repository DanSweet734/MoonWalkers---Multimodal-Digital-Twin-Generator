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
- [ ] Pull request; stop for review

**Measured by:** the drawn masks against v3's (IoU), the time Daniel takes, and the tests.

## Phase 2 - The second agent run
The advisors' ask 1, its second half. A fresh Claude Code session builds the TM-1 again from a
dashboard job, as in the lab plan's Phase 8 (with its run-sheet and starter prompt, updated). This
time it has the cut-out tool and the Phase 1 warnings.
- **Proposed inputs:** the same eight photos of 2026-11-05 as v4's job (question 4). Then the tool
  is the only change, and v3, v4 and the new version compare on one scorecard. The new photos come
  in Phase 3.
- [ ] The run-sheet and starter prompt; Daniel starts the session; the chat checks the transcript
- [ ] **Check (Daniel):** levels 1 to 3 in Isaac Sim, as for v4; the review in the dashboard is his
- [ ] The scorecard against v3 and v4; the tool gaps it finds; pull request; stop

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
