# The video plan

**Status (2026-11-18):** not drafted. This file holds only the hand-off from the chat that closed the
lab's machines plan. The plan itself is drafted below it, after the advisors' meeting of
2026-11-19, and nothing is built, filed or installed until Daniel approves it.

## Hand-off (2026-11-18, from the lab's machines plan's Phase 8 chat)
- **Start** from `main` after the Phase 8 pull request is merged, on a new branch
  `docs/video-plan`. Its first commit holds the advisors' answers; the plan follows. Stop for
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
- **`haas/tm1@v4`** (the agent's) is unreviewed; requests reuse v3 (decision 0015). The dashboard
  review is Daniel's.
- **The tool gaps** in the report's section 8.3, gaps 1 to 9.
- **Decision 0035's update** (the nose on the spindle's axis) is in the Phase 8 pull request, for
  Daniel's review with it.
- **Time:** the semester ends about 2026-12-17 (CLAUDE.md); meetings stay weekly.
