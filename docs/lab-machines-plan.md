# The lab's machines plan

**Goal:** functional twins of the three machines in Dr. Li's lab, built from Daniel's photos, to
compare with the real machines. These are the advisors' "real-world comparisons" (meeting of
2026-10-29), and the start of "Evaluate on the standardized test set" on the README's roadmap.

**Status:** not written yet. This file holds only the hand-off from the chat that closed the
drill-press plan. The plan itself is drafted below it, for Daniel's review, before anything is
built.

## Hand-off (2026-11-09, from the drill-press plan's Phase 7 chat)
- **Start** from `main` after PR #26 (merge commit `d27eb28`, 2026-11-09), on branch
  `docs/lab-machines-plan`. Its first commit holds this hand-off and is not on `main` yet.
  - Your first task is to **draft this plan** below this section, then stop for Daniel's review.
    Build nothing before he approves it.
  - Branches kept, since Daniel did not ask to delete them: `feat/phase-7-agent-build`,
    `docs/advisors-answers-2026-10-29`, `docs/advisors-answers-2026-11-05` and
    `docs/team-setup-guide`.
- **Read first:**
  - CLAUDE.md "Current phase", especially "Next: the lab's machines";
  - [the research note on the lab's machines](research/2026-11-06-lab-machines.md), including
    its update of 2026-11-09;
  - the worklogs of [2026-11-06](worklog/2026-11-06.md) and [2026-11-09](worklog/2026-11-09.md);
  - [the drill-press report](drill-press-report.md): section 7.1 holds the advisors' answers,
    7.3 the agent's tool gaps, and section 6 the inaccuracies;
  - [the drill-press plan](drill-press-plan.md), as the model for this plan's shape: phases with
    checkbox items, each ending in a pull request and a stop for review.

### What Daniel decided
- **All three machines** (2026-11-09): "I say we shoot for all three machines to show off the
  platform we are building."
- **Order:** the ReBeL arm, the Haas TM-1, the Haas VF-3, then the hand. He agreed with the
  recommendation of 2026-11-06 (research note, "Which comes first").
- **The hand is part of the arm's twin:** "the photos I took do have the hand attatched to the arm
  therefore I think it should be a part of the twin."
  - **One reading to confirm with him** [INFERENCE]: the arm's first twin carries the hand as one
    labelled stand-in, or as the generator's fused shape, and the hand's 21 joints come last.
- **Priorities** (2026-11-06, agreed 2026-11-09):
  1. update the record (done, PR #25);
  2. the teammates' setup guide (done, PR #26);
  3. file the photos, and write this plan;
  4. close the agent's tool gaps that would slow the next build: a wrong view in a job, mesh checks
     in `preview_twin`, and a tool for scratch dry runs (report 7.3, items 1, 5 and 7);
  5. build the machines, then start video once the photo results are acceptable;
  6. masses last, as a bonus.
- **What "acceptable" means:** "the real-world comparion should measure accurately. Our acceptable
  is based on our goals and the stakeholders feedback as it comes from our weekly meetings." So
  the plan proposes the measures, and the weekly meetings judge them.
- **Measuring at the lab** is possible, but "it has to be planned in advance so it can't be done on
  a whim. Most to all measurements can be found online according to stakeholders." So cite online
  sources first, and list any measurement worth a planned visit.
- **Video** is a later, separate trip: "I took photos, not videos yet I plan to make that a separate
  trip."
- **From the advisors (2026-11-05):**
  - masses are a bonus, not a priority (Dr. Lu);
  - an agent that cannot reach a source prompts the person, with an option to skip it (Dr. Li;
    `docs/agent-procedure.md`, step 2);
  - the lab has no HA5C, so decision 0026's stand-ins stay.

### What the photos show
29 JPEGs of 2026-11-05, 13:32-13:44, from Daniel's phone (EXIF). The full findings are in the
worklog of 2026-11-09.
- **ReBeL arm, 10 photos:** all sides and two from above, in one pose.
  - **Model:** the base label reads "REBEL-6DOF-02", "Payload: 2 kg", "Supply: 24VDC = 12A".
  - **No public model of version 02:** the Apache-2.0 ROS package (`CommonplaceRobotics/iRC_ROS`)
    describes only `igus_rebel_6dof_00`, `_01` and `_pre`. Its joint limits also disagree with
    two other sources (research note).
  - **End effector:** a Realhand L20 on the wrist flange, its back wrapped in clear plastic. No
    SCHUNK gripper or CobotPump is fitted: that name is from Dr. Li's website.
  - **Not settled:** whether it is a left or a right hand. Public URDFs exist for both, in
    `realhand-robotics/Realhand_description` (Apache-2.0), each with 21 revolute joints, 5 of them
    mimic joints.
  - **Not twinned:** other arms stand behind it.
- **Haas TM-1, 8 photos:** front, front corners, back, back corners, and the nameplate.
  - **Nameplate:** "TM-1", made "11/06".
  - **Open-framed,** with sheet-metal guards and an umbrella tool changer, so its axes show.
- **Haas VF-3, 11 photos:** front, front corners, a side, a back corner, four inside with the doors
  open, and the nameplate.
  - **Nameplate:** "VF-3", made "12/2014".
  - **Enclosed,** with a Haas two-axis trunnion rotary table inside (photo `20261105_133959`). The
    trunnion's model is not read yet.
- **Where the photos are:** `data/machine photos (temp)/<Haas TM-1|Haas VF-3|ReBel Arm>/`.
  - Daniel: "Once we get the information we need we should most likely move these photos to a
    better spot."
  - The plan's first step files them under `data/machines/<machine>/inputs/photos/`, each with a
    `SOURCES.md` line: date, SHA-256 and licence note (`data/README.md`). The folder names follow
    the machine keys (decision 0009), which the plan sets.
  - **Ask Daniel** what the licence note should say for photos he took in the lab.
- **Viewing them:** the backend has no Pillow. `data/scratch/2026-11-09_lab-photos/` holds
  `sheets.py` and `crops.py`, with their contact sheets and crops. Run them with the generator
  environment's Python, which has Pillow: `C:\mw-gen\hunyuan3d-2\.venv\Scripts\python.exe -I`.
  Nothing needs installing.
- **The repository is public:** nameplates' serial numbers, and the IP address taped on the arm,
  stay in `data/`.

### Questions the plan must answer
- **The ReBeL 02's geometry and limits.** Where do they come from, given no public model of
  version 02? Candidates:
  - igus's ReBeL configurator (https://tpdb2.truphysics.com/igus/Rebel/), which igus's page
    describes as "CAD-based configuration". Whether it gives a download is not checked;
  - a STEP file of the "ReBeL-6DOF-OS", offered by Unchained Robotics (a search listing, not
    opened; research note). Whether that model matches version 02 is not confirmed;
  - the igus manual on ManualsLib (research note);
  - asking the lab.
- **The public models' role.** As cited sources of joint facts they fit our rules. As the twin's
  geometry they would skip the photo-to-mesh step the platform exists to prove. Using one file both
  as a source and as the score is not an independent check (research note).
- **Measures for "accurately":**
  - sizes against cited dimensions, as the size checks do now;
  - the generated mesh against a published mesh where one exists;
  - joint limits against cited ones;
  - each control's timing against its source.
- **The generator and the views:**
  - the multi-view model takes up to four views (front, the operator's left and right, back; or
    the four corners as a grid turned 45 degrees). The views are in the operator's words, and
    `pipelines/b/photos.py` alone maps them (decision 0022);
  - a robot arm has no operator's front, so the plan defines one;
  - the arm stands in one pose, so its twin's zero pose must be worked out.
- **Control, level 3,** for each machine:
  - **the mills:** G-code. Nothing in `moonwalkers.control` reads it, so a reader for mill
    programs is new work;
  - **the VF-3's trunnion:** it is a Haas rotary product, like the HA5C, so decision 0026's
    controller may carry over [INFERENCE];
  - **the arm:** joint moves through Commonplace Robotics' iRC software, over CRI or CAN
    (`iRC_ROS` README);
  - **the hand:** a Python SDK over CAN, with 16 driven joints (Realhand's SDK page). Its 5 mimic
    joints map onto contract v0.2.0's `follows` (decision 0020) [INFERENCE].
- **Sources scripts cannot reach:**
  - haascnc.com answers 403, so Daniel saves Haas's pages in a browser (agent procedure, step 2);
  - the igus factsheet and the L20 manual on RobotShop's CDN answered 403 too.
- **Video:** the input router already sends `walkthrough_video` to Pipeline B
  (`orchestrator/router.py`), but nothing in Pipeline B reads a video yet.
- **Installs:** a CAD or URDF reader, or a G-code library, needs Daniel's approval first: what it
  is, why, its licence and its size (CLAUDE.md, rule 3).

### Carried over, none blocking
- **The T33901:**
  - the crank passes into the base at the table's lowest setting;
  - a stale issue in v10 and v11.

  Both go into its next version, if one is built (drill-press report, section 6).
- **Waiting on Daniel:**
  - the HA5C's Isaac Sim check of decision 0026, if he deems it necessary;
  - his stroke timing for the T33901;
  - a look at the stakeholder pages' Mermaid diagrams on GitHub (report 7.2).
- **The pipeline owners' review** of decisions 0020 and 0021 is still open.
- **Sarkis's branch** (`origin/Sarkis`) has Pipeline D work since 2026-11-05. It is his: read it,
  never change it.
  - The worklog of 2026-11-06 lists what merging it into `main` needs, including a new decision
    number: 0029 is the next free one on `main`. Check `docs/decisions/` on the newest `main`
    before numbering one.
  - His Playwright and Chromium install needs Daniel's approval.
- **The team:** everyone works on Windows except Ava, who uses macOS (Daniel, 2026-11-09). So
  her first run of `docs/setup/team-setup.md` is its first macOS test.

### How Daniel works
These are also in CLAUDE.md and the memory notes.
- **Merging and deleting:** merge or delete only on his explicit word in that message. Any change
  after a conditional approval voids it.
- **Stop at each phase's end,** with a pull request for his review. Each phase runs in a new chat,
  with a hand-off written into this plan and a starter prompt.
- **After each weekly meeting** (Thursdays, starting 2026-10-22), ask for the advisors' answers,
  and record them the same day.
- **Reports cover Daniel's work only.** Teammates' gaps are theirs to present.
- **Twin reviews are his.** The agent never reviews.
- **Before an agent's build:** restart the MCP server (`/mcp`) if the tools changed. Build in a
  scratch copy of `data/`, and run both validators before the real build, since a real build
  stores a version for good.
- **The advisors' page** for the drill-press plan is https://claude.ai/artifact/RttTc4nE7DUYJ6NP2uEziK.
  This plan's report gets a new page in the same design (memory "drill-press-report-page").
