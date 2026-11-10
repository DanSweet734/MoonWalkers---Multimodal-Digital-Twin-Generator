# The lab's machines plan

**Goal:** functional twins of the three machines in Dr. Li's lab, built from Daniel's photos, to
compare with the real machines. These are the advisors' "real-world comparisons" (meeting of
2026-10-29), and the start of "Evaluate on the standardized test set" on the README's roadmap.

**Status:** drafted on 2026-11-09 for Daniel's review (Phase 0, branch `docs/lab-machines-plan`,
PR #27). He answered eight of its nine questions the same day ("Decided on review"). Nothing is
built, filed or installed until he approves it. The hand-off from the chat that closed
the drill-press plan comes first; the plan follows it, from "The plan (draft of 2026-11-09)".

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

## The plan (draft of 2026-11-09)
Written by Claude Code in the plan chat of 2026-11-09, from the hand-off above, the 29 photos
(looked at with the scripts in `data/scratch/2026-11-09_lab-photos/` and more crops in the
session's scratchpad; nothing written to `data/`), and sources read the same day. Those sources
are in [the research note's second update](research/2026-11-06-lab-machines.md) with their URLs
and access dates. Photos are named by their time stamp, `20261105_HHMMSS`, shortened here to
`HHMMSS`.

Like the drill-press plan, every phase ends in a pull request and a stop for review, and runs in a
new chat with a hand-off written into this file. Every stand-in is labelled in the twin and logged
as an inaccuracy (Daniel, 2026-10-22 and 2026-10-24).

### Decided on review (2026-11-09)
Daniel's answers to the questions at the end of this plan, the same day. The phases below carry
them.

| Question | Answer |
|---|---|
| 1. The photos' licence note | The proposed wording: "Photographed by Daniel Sweet in Dr. Li's lab, CSUN, 2026-11-05; the team's own photo; internal research only; shows serial numbers, keep out of commits." |
| 2. The machine folders | `igus-rebel6dof02` (the arm and the hand, one twin), `haas-tm1`, `haas-vf3`. "The temp folder may go once the copies are checked" |
| 3. The hand in the arm's first twin | The recommendation: the generator's fused shape, one labelled part on the flange |
| 4. The fingers in Phase 7 | "If they can't be modeled from the input photos then stand ins will have to do." So the fingers are cut from the generated mesh where the photos allow, and are otherwise labelled stand-ins sized from the maker's model. The maker's meshes are not imported |
| 5. The arm's front | "where the hand finger tips are pointing to." Fixed to the base as the photos show it: in `133326` the connector panel faces the camera and the arm reaches straight away from it, so this is also the side away from the panel, the plan's proposal |
| 6. The scorecard | To the next weekly meeting, "if possible" (Thursday, 2026-11-12) |
| 7. A lab visit | Not planned now. Daniel just visited, and can go again if a need is found. The visit list stays for that case. Dr. Li wants the three machines worked on |
| 8. Tool gaps 2 and 6 | Fixed as well, in Phase 1 |
| 9. The agent's build in Phase 8 | Open. Daniel read the question as the order of machines, which starts with the arm (Phase 2, agreed on 2026-11-09). Phase 8 asks which machine the agent builds unaided at the end. Asked again |

### What the sources and photos settled since the hand-off
- **The hand is a LinkerBot hand.** Its back shell reads "LINKERBOT" (photo `133438`, from above).
  The name "Realhand L20" is from Dr. Li's website (Daniel, 2026-11-09). Whether Realhand and
  LinkerBot are one maker is still **not confirmed**: retailers sell the "Linker Hand L20" by
  "Linkerbot", and no page found names Realhand.
- **LinkerBot publishes its own L20 models.** `linkerbotai/linker_hand_sim` (Apache-2.0) holds
  `linker_hand_isaac_gym_urdf/l20/left` and `/right`. Its right hand has 21 revolute joints, 5 of
  them mimic joints, like Realhand's. The two models differ, though: different joint names, and
  different limits (LinkerBot's first joint -0.297 to 0.683 rad, Realhand's first ±0.17 rad). So
  which model matches the lab's hand is **not confirmed**. The repository's README says it moved
  to `linker-bot/linkerhand-sim`, which the GitHub API did not find on 2026-11-09.
- **A right hand** [INFERENCE]: in `133438` the shell (the back of the hand) faces the camera
  above, the fingers point away from the base, and the thumb is on the image's left. A right hand
  held palm down looks like that. To confirm on the hand's label or box.
- **igus's own technical documentation** for the ReBeL ("Technical documentation ReBeL",
  MAT0075179.25, "Stand 08/2022", 8 pages, from Unchained Robotics' download):
  - 6 DOF: reach "664" mm, payload "2" kg, mass "< 8" kg, "Max. speed 45 [°/s]", "Linear speed
    200 [mm/s]", "Footprint Ø 180 [mm]", accuracy "+-1 [mm]" (p. 2);
  - "J1: -179° bis to +179° J2: -80° bis to +140° J3: -80° bis to +140° J4: -179° bis to +179°
    J5: -95° bis to + 95° J6: -179° bis to +179°" (p. 2);
  - a drawing of the arm straight up, "Nullstellung" (zero position), with "ReBeL-6DOF-00 660 252
    237 297 126 180" for L1, X1 to X4 and D1 (p. 6). Read from the drawing: X1 runs from the
    foot to joint 2's axis, X2 to joint 3's, X3 to joint 5's, X4 to the flange; L1 from joint 2's
    axis to the flange; D1 is the foot's diameter;
  - "With and without integrated control" in the base (p. 2).
- **Version 01 of the ROS model is version 00.** `igus_rebel_6dof_01.description.xacro` only
  includes `igus_rebel_6dof_00`'s description (`CommonplaceRobotics/iRC_ROS`, 2026-11-09).
- **The URDF's limits agree with igus's** [INFERENCE, by arithmetic]: joints 2 and 3 are limited
  to ±110° about origins turned +30° (`pi/6`), which gives -80° to +140° from the straight-up
  zero; joint 5 to -87.5° to +102.5° about an origin turned -7.5° (`-pi/24`), which gives ±95°.
  The URDF's comment: "pi*2/3 are the physical limits, but to avoid any collisions we set the
  actual limits lower". Its link offsets (0.249, 0.2384, 0.289 and 0.122 m) are within 1-8 mm of
  igus's X1 to X4. ManualsLib's "±140° / ±115° / ±90°" (a search listing) is still unread.
- **Version 02 may be the one with control in the base** [INFERENCE]: the lab's base has a
  connector panel with a power button, network and USB ports (`133326`), on a base plate with its
  own label (kept in `data/`). igus's drawing shows a plain foot. Not confirmed: no public page describing
  "6DOF-02" was found, though DigiKey and Unchained Robotics list the part number.
- **The VF-3's trunnion** has a cradle carrying a round platter between two end housings
  (`133959`, `133938`). A small plate on the cradle's base, lower left, may name it; it cannot be
  read in the photos. Dealers' listings say Haas's TRT160 and TRT210 need "a Haas mill with 4th
  and 5th axis drives". So its two axes are the mill's own and are programmed in the mill's G-code
  [INFERENCE from second-hand listings], unlike the HA5C, which has its own control. **So the
  G-code reader carries over to the trunnion, and decision 0026's indexer controller likely does
  not.** This corrects the hand-off's inference; to confirm in Haas's manual.
- **The TM-1, from dealers' listings** (second-hand, years vary): X 30 in, Y 12 in, Z 16 in;
  a table of about 47.75 by 10.5 in (some say 47.5); a 4000 RPM CAT-40 spindle; a 10-pocket tool
  changer. The TM-1P is listed at 6000 RPM. The lab's unit shows "Tool Room Mill" and an umbrella
  tool changer (`134314`).
- **Machine keys** (decision 0009, `kb/keys.py`, run on 2026-11-09): igus with "REBEL-6DOF-02"
  gives `igus/rebel6dof02`, Haas with "TM-1" gives `haas/tm1`, Haas with "VF-3" gives `haas/vf3`.
  "igus GmbH" gives `igus-gmbh/...`, so the key code needs "GmbH" dropped, or an alias, before a
  pipeline names the maker that way.
- **The lab's backgrounds are busy:** benches, other robots, the ceiling, and on the TM-1's back a
  large sign and a stool in front of its right side (`134322`, `134329`; Daniel's views, 2026-11-09). The generator's background removal
  (rembg with `u2net`, `docs/setup/generators.md`) has only seen clean photos so far.
- **Kept out of the repository:** the serial numbers, the IP address, and the university's asset
  tag on the arm's base (`133326`).

### Answers to the hand-off's questions
| Question | What the sources answer | Still open |
|---|---|---|
| The ReBeL 02's geometry and limits | Joint ranges, speeds, sizes and the zero pose from igus's documentation (version 00's drawing); joint axes and frames from the ROS URDF (00 = 01). The two agree on the limits once the URDF's offsets are added. The twin cites both, with an issue: "version 02 not confirmed to match 00/01" | What changed in 02. igus's configurator, Unchained's STEP files and the ManualsLib manual are not opened. A tape measure at the lab settles the sizes (visit list) |
| The public models' role | Sources of joint facts (frames, axes, limits) and the score for the generated mesh, never the twin's geometry. Where the photos cannot give the fingers, the maker's model sizes their stand-ins (Daniel, 2026-11-09). The arm's joint frames are cited from the URDF and scored against igus's drawing, a separate source | |
| Measures for "accurately" | The scorecard below: proposed measures and starting targets, for the weekly meetings to judge (Daniel, 2026-11-09) | The targets |
| The generator and the views | The arm: its four sides. The TM-1: its four corners (`134300`, `134337`, `134329`, `134355`; the back corners confirmed by Daniel, 2026-11-09). The VF-3: its corners, or its front and a side. Top and detail photos are evidence. **The arm's front** (Daniel, 2026-11-09): where the fingertips point in the photographed pose, which is the side away from its base's connector panel, so `133326` is its back | Whether background removal copes (Phase 1). Daniel's check of each photo's view |
| The arm's zero pose | igus's zero is the arm straight up (p. 6). The twin is built in the photographed pose. Each joint's angle in that pose is measured on the cut mesh and becomes the joint's start; the limits stay about igus's zero | The real angles: the lab's control software can show them (visit list) |
| Control, level 3 | The mills: a reader of the G-code the programs use, new (Phase 5). The trunnion: two more axes of that reader (above). The arm: joint moves at the cited 45°/s, as iRC runs them; the program format is to be researched (Phase 3). The hand: the maker's SDK commands over CAN; its 5 mimic joints map onto `follows` (decision 0020) [INFERENCE] | Haas's pages (saved by Daniel); iRC's program format; which SDK fits the lab's hand |
| Sources scripts cannot reach | haascnc.com, the igus factsheet on RobotShop, and DigiKey answer 403. igus's documentation came from Unchained Robotics instead | Daniel saves Haas's pages in a browser (list below) |
| Video | Not in this plan. Pipeline B reads no video yet; a video plan follows once the photo results are acceptable (2026-11-05) | |
| Installs | None needed to start. Perhaps later, each asked first: a COLLADA reader for the ROS model's `.dae` meshes (Phase 2's score), a segmenter if background removal fails (Phase 1) | |

### Success levels (each machine)
The drill press's three levels, for each machine:
1. **A scaled model, cut into its moving parts, with cited facts, opens in Isaac Sim.** It is built
   from the lab's photos, and its sizes are compared with every cited dimension.
2. **Its joints move as the sources say** in Isaac Sim: each about its cited axis, through its
   cited range, and holding where it is put.
3. **Its control drives it:** a program or commands from the machine's own control, run in Isaac
   Sim and measured against the plan the controller made.

And the HA5C and the T33901 still build and are reused, and every phase keeps the tests passing.

### How "accurately" is measured: the scorecard
Proposed, for the weekly meetings to judge. A starting target is what the T33901 reached, or none
where nothing has been measured yet. Several of these are metrics from Dr. Li's deck (methodology,
"Evaluation").

| Measure | How | Machines | Starting target |
|---|---|---|---|
| Sizes | Every cited dimension against the twin's (the size checks) | All | Within 6% (the T33901 reached -5.9% to +5.8%); over 10% flagged |
| Match with the photos | Each fed photo against the twin's silhouette, placed by `photo_marks.fit_camera`, as IoU | All | None yet: the first builds set a baseline |
| Shape against the maker's model | Distance from the generated mesh to the maker's mesh in the same pose: mean and 95th percentile, in mm | Arm, hand | None yet |
| Parts and joints | Parts and joints in the twin against the sources' list (coverage, count accuracy) | All | Every moving part the sources name; each gap logged |
| Joint axes and places | Each axis's direction (degrees) and position (mm) against the cited frames | Arm and hand; the mills' axes by direction | None yet |
| Ranges | Each joint's range reached in Isaac Sim, from the joint recorder, against the cited range | All | Within 1° or 1 mm |
| Control | The recorded motion against the controller's plan (`control compare`), and its time against the cited speeds | All | The T33901's stroke stayed within 0.63 mm of its plan |
| Evidence | Quotes found on their cited pages (the quote checker); stand-ins and guesses logged | All | Every quote found |

Comparing with the **real** machine's motion needs the real machine moving, which is the video
trip (Daniel, 2026-11-09). Until then, level 3 is measured against the cited speeds.

## Phase 0 - Plan
- [x] Read the record: CLAUDE.md's "Current phase", the hand-off, the research note, the worklogs
      of 2026-11-06 and 2026-11-09, and the drill-press report and plan
- [x] Looked over the 29 photos, with crops of the trunnion, the hand and the arm's base
- [x] Research: igus's documentation, the ROS model's versions, LinkerBot's models, the trunnion
      and the TM-1 (the research note's second update)
- [x] This plan, a worklog entry, PR; stop for Daniel's review (PR #27)
- [x] Daniel's answers to the questions at the end, recorded ("Decided on review", 2026-11-09).
      Question 9 is asked again
- [ ] The scorecard to the weekly meeting of 2026-11-12, and the advisors' answers recorded

**Measured by:** Daniel's review.

## Phase 1 - File the photos and sources, and close the tool gaps
- [x] Machine folders `data/machines/igus-rebel6dof02/` (the arm and its hand, one twin),
      `haas-tm1/` and `haas-vf3/`, by decision 0009's key. The "GmbH" fix in `kb/keys.py`, with
      a test.
      (2026-11-09: "gmbh" is a legal-form word; decision 0009, update)
- [x] Copy each photo into `inputs/photos/` unchanged, and check its SHA-256 against the
      original.
      (2026-11-09: 29 photos, each copy's SHA-256 checked twice, by the filing script and by
      `sha256sum`. Daniel confirmed the TM-1's `134346` as its left side and `134355` as its back
      left corner: "I couldn't get a photo directly behind the machine as it was close to the
      wall". He also confirmed `134322` as its right side, the pendant's, with a sign in the way
      and "not much room to move it", and `134329` as its back right corner, the back of the
      pendant above the caution sign. So all four corners are photographed: `134300`, `134337`,
      `134329`, `134355`.) One `SOURCES.md` line each: what it shows, its view in the operator's words
      (proposed, checked by Daniel), its use (generator or evidence), the date, the SHA-256 and
      the licence note: "Photographed by Daniel Sweet in Dr. Li's lab, CSUN, 2026-11-05; the
      team's own photo; internal research only; shows serial numbers, keep out of commits."
      No serial number, IP address or asset tag in any committed file.
- [x] Remove `data/machine photos (temp)/` once every copy's SHA-256 matches its original
      (Daniel, 2026-11-09: "the temp folder may go once the copies are checked").
      (2026-11-09: removed)
- [ ] File the cited documents, each with its `SOURCES.md` line: igus's documentation; the ROS
      model at a fixed commit; LinkerBot's and Realhand's L20 models; Haas's pages as Daniel saves
      them.
      (2026-11-09: all but Haas's pages, in the arm's `documents/`, each model at a fixed commit
      with its LICENSE and a SHA-256 manifest)
- [x] **Found on the way: the generator ignored phone photos' EXIF orientation.** 19 of the 29
      photos are stored sideways ("rotate 90°"). The job now turns each upright
      (`_open_upright` in `hunyuan3d_shape_job.py`).
- [x] **A background spike:** run the generator's background removal on every photo planned for
      the generator, and look at each mask. If they fail, Daniel chooses between a crop box per
      photo in `request.json` (amending decision 0022; no install) and a segmenter (an install,
      asked first).
      (2026-11-09: they fail on the TM-1, and are partial on the VF-3 and the arm:
      `docs/research/2026-11-09-background-removal-spike.md`. Recommended: box-prompted SAM,
      already in the installed rembg, with about 118 MB of weights.
      Daniel chose it the same day ("prioritize B for now"), and wants crop boxes and hand-drawn
      masks offered as well. Weights downloaded; a trial on seven photos kept the machine where
      u2net had kept the wrong object.)
- [x] **A cut-out setting per photo** in `request.json`, beside its view and use (amends decision
      0022): `sam` (a box, with points to keep or drop), `crop` (a box, then the automatic cut),
      `mask` (a PNG a person drew, in the run), or the automatic cut as today. The generator job
      applies it; small separate specks are removed. Built for SAM first, on Daniel's word, with
      `crop` and `mask` in the same change since they share the setting. Clicking boxes and points
      in the dashboard comes later.
      (2026-11-09: decision 0029, accepted by Daniel the same day.
      - A preview runs only the job's first step, in seconds: the command
        `python -m moonwalkers.pipelines.b cutouts <run>` and the MCP tool `preview_cutouts`.
      - Tried on nine lab photos through the platform. SAM needed the photo shrunk with
        antialiasing first: rembg's own shrink kept the wall.
      - What is left is per photo: more points, and a drawn mask for the TM-1's shiny guards. It
        belongs to each machine's phase (the research note's second update).)
- [x] **The tool gaps** (drill-press report, section 7.3):
  - [x] item 1: a tool that corrects a photo's view or use in a job, before the mesh is generated
    (2026-11-09: `set_photo`, which also sets the cut-out; decision 0029);
  - [x] item 5: `preview_twin` reports zero-area faces and non-manifold points per part, as the
    build and NVIDIA's validator do (2026-11-09: `mesh_tools.mesh_faults`, NVIDIA's definitions,
    the same counts as its own code on 29 meshes; it found v9's 40 zero-area faces again);
  - [x] item 7: a tool that builds a run in a scratch copy of `data/` and runs both validators,
    storing nothing (2026-11-09: `dry_run_twin` and `pipelines.b dry-run`; v11's spec dry-ran
    clean as v12 in a copy);
  - [x] item 4: `fit_circles` within a box, since the arm's links lie at angles and a whole slice
    would cut through several links (2026-11-09: `within`, and `along` as a direction for a link
    at an angle; the old fits are unchanged);
  - [x] item 2: a tool that corrects or withdraws an issue the agent added (the cause of v10's and
    v11's stale issue) (2026-11-09: `correct_issue`, with the issues numbered in the notes'
    summary; refused once the twin is built);
  - [x] item 6: the dashboard's upload takes photos from more than one folder, and its duplicate check
    looks in every photo folder of the machine, `photos/manual/` included (2026-11-09: each pick
    adds to the photos chosen, with "Remove"; checked in headless Edge with four photos from two
    folders, which the job took from where they were filed).

  Items 2 and 6 were added on Daniel's word (2026-11-09).
- [ ] Decision record (the tools, amending 0028), worklog, PR. (2026-11-09: decision 0030
      proposed, the worklog written, the PR opened for Daniel's review.)

**Measured by:** the tests; every copied photo's SHA-256 matching its original; the masks looked
at; the new tools used in Phase 2.

## Phase 2 - The ReBeL arm: levels 1 and 2
- [ ] Reference facts for `igus/rebel6dof02`, each quoted from igus's documentation or the URDF,
      with the issue "version 02 not confirmed to match 00/01".
- [ ] A box-and-cylinder arm first, as in the drill press's Phase 1: six joints in series on the
      cited frames, the hand a box. Daniel checks in Isaac Sim that each joint turns through its
      range, and that six driven joints hold a pose under gravity.
- [ ] The views, the front (where the fingertips point in the photographed pose, fixed to the
      base; Daniel, 2026-11-09) and the zero pose, in a decision record.
- [ ] Generate the mesh from the four sides, and look at it with `inspect_geometry`.
- [ ] Cut it into seven parts and the hand by cited shapes (decision 0023), with the joint housings
      measured by `fit_circles`. The hand is the generator's fused shape, one labelled part on the
      flange, until Phase 7 (Daniel, 2026-11-09). The cables fused into the mesh are logged.
- [ ] Scale by a cited length between two fitted joint axes: X2, 237 mm [INFERENCE: the
      straightest link]. Size checks on all the others.
- [ ] Measure each joint's angle in the photographed pose; set the start pose and the limits.
- [ ] Dry run, both validators, the real build; Daniel's Isaac Sim check with the joint recorder.
- [ ] The score: a small scorer for the measures above. The shape distance needs the ROS model's
      `.dae` meshes read, which may need an install (asked first).
- [ ] Decision records, worklog, `RUN.md`, PR. The PR says which of Phase 1's new tools were
      used and how they did, for the tool guide (Phase 8).

**Measured by:** the scorecard's sizes, photo match, shape, parts and joints, axes and ranges.

## Phase 3 - The ReBeL arm: level 3
- [ ] Research note: what an igus Robot Control (iRC) program holds (joint and linear moves,
      speeds), and CRI, from igus's and Commonplace Robotics' documentation.
- [ ] A program of joint moves at no more than the cited 45°/s, as a `program_interpreter`
      behaviour. Linear moves need inverse kinematics: left out unless a source makes them simple.
- [ ] The lab's own program if it shares one (the best comparison, later, on video); otherwise a
      short labelled test program.
- [ ] Daniel's Isaac Sim check; `control compare` against the plan.
- [ ] Decision record, worklog, PR.

**Measured by:** each joint's recorded motion against the plan; the move times against 45°/s.

## Phase 4 - The Haas TM-1: levels 1 and 2
- [ ] Sources: Haas's pages saved by Daniel, and dealers' listings as second-hand, with their
      disagreements named. One is known (2026-11-09): the TM-1's Y travel, 12 in on Haas's 2018
      Toolroom sheet and the listings of 2006-07 units, 16 in on today's page (`SOURCES.md`). Which part carries which axis is cited, not assumed. The control's
      generation is read from the pendant's photos.
- [ ] No box test: the drill press proved sliding joints and chains (decisions 0017-0019).
- [ ] Generate from the four corners; the sign and stool at the back are logged where they show.
- [ ] Parts: the frame, the axes' carriages, the head, the spindle and the tool carousel. Fixed:
      the guards and the pendant. Stand-ins where the mesh gets a visible part wrong.
- [ ] Level 2: each axis slides its cited travel, the spindle turns, the carousel indexes its
      cited pockets.
- [ ] Dry run, validators, build; Daniel's Isaac Sim check; decision record, worklog, PR.

**Measured by:** the scorecard's sizes, photo match, parts and joints, and ranges.

## Phase 5 - Mill programs, and the TM-1's level 3
- [ ] Research note: Haas's G and M codes, from the mill manual's pages Daniel saves.
- [ ] Decision record: a reader of the codes the programs use (moves, arcs, units, absolute and
      incremental, spindle, tool change, end), written here with no library; a library only on
      Daniel's approval.
- [ ] `moonwalkers.control` learns it: a program becomes the axes' motion at cited rapid and feed
      rates; accelerations are stand-ins unless cited.
- [ ] A program from Haas's manual, and the lab's own if it shares one.
- [ ] Daniel's Isaac Sim check; the tool tip's recorded path against the program's.
- [ ] Worklog, PR.

**Measured by:** the tool tip's distance from the programmed path, in mm; the time against the plan.

## Phase 6 - The Haas VF-3 with its trunnion: levels 1 to 3
- [ ] Sources as for the TM-1, and the trunnion's once its plate is read (visit list). Until then
      the trunnion is a labelled stand-in, sized from the photos against the table's cited size.
- [ ] The enclosure from the generator. The moving parts inside are stand-ins matched to the four
      inside photos, since the enclosure hides them. A check file without the enclosure shows the
      axes.
- [ ] The trunnion's tilt and turn as two joints, with Haas's axis names cited.
- [ ] The tool changer does not show in the photos: left out (Daniel's rule, 2026-10-24), and a
      program's tool change is logged, not simulated.
- [ ] Phase 5's reader with the two extra axes; a program that tilts and turns the part.
- [ ] Dry run, validators, build; Daniel's Isaac Sim check; decision record, worklog, PR.

**Measured by:** as Phases 4 and 5, with the trunnion's two axes.

## Phase 7 - The hand: 21 joints and its commands
- [ ] Decision record: the fingers' geometry. They are cut from the generated mesh where the photos
      allow; otherwise they are labelled stand-ins sized from the maker's model (Daniel,
      2026-11-09: "If they can't be modeled from the input photos then stand ins will have to
      do"). The maker's meshes are not imported. The hand is scored against the photos.
- [ ] The 16 driven and 5 following joints, from the model that matches the lab's hand (visit
      list), with `follows` (decision 0020): one articulation of 27 joints with the arm.
- [ ] Research note: the SDK's commands (joint positions, preset poses) over CAN. LinkerBot's
      Python SDK has no licence on GitHub, so it is read and cited, not copied.
- [ ] A grasp: the hand closes and opens on the SDK's commands in Isaac Sim.
- [ ] Daniel's check; worklog, PR.

**Measured by:** the joint count against the cited 21 (5 following), the finger ranges reached,
the commanded poses against the plan, and the hand's match with the photos.

## Phase 8 - The agent builds one, and the report
- [ ] The agent builds one lab machine from a dashboard job through the MCP tools, as in the drill
      press's Phase 7. **Proposed: the TM-1,** which has no public model, so it is the hardest
      test of photos to twin.
- [ ] The plan's report: results per machine and level, the scorecard, the inaccuracies, the open
      questions and the tool gaps; a new advisors' page in the drill-press page's design.
- [ ] A hand-off for the video plan.
- [ ] **The tool guide brought up to date** (Daniel, 2026-11-09). Once the agent's build has used
      Phase 1's tools, `docs/tool-guide.md` replaces its note "Not yet used in an agent's build"
      with how each did, citing the runs. A tool still unused, or one that fell short, stays
      named there with the reason.

**Measured by:** the scorecard for the agent's build, beside the chat's builds.

### A planned visit to the lab
Daniel: measuring "has to be planned in advance". No visit is planned now: he has just been, and
can go again if a phase finds a need (2026-11-09). Items 1 and 2 are the likeliest needs (Phases
6 and 7), so each phase says when it reaches one. What a visit could settle, by priority:
1. A close photo of the trunnion's plate (its model).
2. The hand's label or box: maker, model, version, left or right.
3. The arm's joint angles as its control software shows them, in the photographed pose, if the
   lab will turn it on. They are the answer key for the zero pose.
4. A tape measure on the arm: X1 to X4 and the foot, to compare version 02 with igus's drawing
   of 00.
5. Each mill's control version from its screen, and the VF-3's tool changer.
6. The TM-1's sides square on, and the VF-3's back, without the sign in front.
7. Whether the lab will share a program each machine really runs.

### Sources for Daniel to save in a browser
haascnc.com refuses scripts (403):
- the TM-1's and the VF-3's specification pages, or archived sheets for 2006 and 2014;
- the mill operator's manual for each machine's control, with its G and M code chapters;
- **Filed on 2026-11-09** (`SOURCES.md` of each mill): Haas's PDFs under `/content/dam/` answer
  scripts, so on Daniel's permission Claude Code fetched the Toolroom Series sheet and three mill
  manuals: 96-8000 Rev Y (2009) and Rev AP (2012) for the Classic Haas Control, and the 2023 one
  for the Next Generation Control. Haas's HTML pages still answered 403, so Daniel saved the
  TM-1's product page and pre-install guide and the VF-3's product page in a browser the same
  evening; Claude Code checked each (the page itself, with its specs). Which control each mill
  has is still to read off its screen (lab visit, item 5).
- links found by a search on 2026-11-09 (the search's summaries are not used as sources):
  - https://www.haascnc.com/machines/vertical-mills/toolroom-mills/models/tm-1.html
  - https://haascnc.com/content/dam/haascnc/machines/vertical-mills/toolroom/assets/Vertical_ToolroomSeries.pdf
  - https://www.haascnc.com/owners/pre-install-guide/mills-pre-install/TM-1.html
  - https://www.haascnc.com/machines/vertical-mills/vf-series/models/medium/vf-3.html
  - https://www.haascnc.com/service/online-operator-s-manuals/mill-operator-s-manual.html (the
    one that answered 403 on 2026-11-06)
  - https://haascnc.com/content/dam/haascnc/en/service/manual/operator/english_mill_interactive_manual_print_version_2023.pdf
  - https://haascnc.com/content/dam/haascnc/en/service/manual/operator/english---mill-ngc---operator's-manual---2021.pdf
  - the online chapters "17 - Mill - G-Codes" and "18 - Mill - M-Codes" under the manual's page;
- the trunnion's page once its model is known, and how a Haas rotary is set up as a 4th and 5th
  axis.

For the arm: the igus manual on ManualsLib (https://www.manualslib.de/manual/949812/Igus-Rebel.html)
and igus's product page (https://www.igus.de/product/21465), both search listings, not opened.

### Decision records this plan needs
Numbered when written, from the newest `main`: 0029 is the next free number on `main` today, and
merging Sarkis's branch needs one too.

| Title | Phase |
|---|---|
| The tools for the lab's builds (amends 0028) | 1 |
| Crop boxes or masks for busy photos, if the spike needs one (amends 0022) | 1 |
| A robot arm: its front, zero pose, and the public models' role | 2 |
| An arm's joint programs | 3 |
| Mill programs: a G-code reader | 5 |
| The VF-3's trunnion axes | 6 |
| The hand's geometry and joints | 7 |
| The scorecard, once the meetings have judged it | 8 |

### Not in this plan
- Video input (its own plan, once the photo results are acceptable); Pipelines A, C and D (their
  owners'); Neo4j, Celery and Codex.
- Masses, a bonus (Dr. Lu, 2026-11-05). igus gives only the arm's total ("< 8" kg). Per-part
  masses need a contract change, discussed with the pipeline owners first (decision 0024, update).
- The other arms in the lab's photos.

### Questions for Daniel
Answered on 2026-11-09, except question 9 ("Decided on review", above).
1. **The licence note** for the photos you took in the lab. Proposed: "Photographed by Daniel
   Sweet in Dr. Li's lab, CSUN, 2026-11-05; the team's own photo; internal research only; shows
   serial numbers, keep out of commits."
2. **The machine folders:** `igus-rebel6dof02` (the arm and the hand, one twin), `haas-tm1` and
   `haas-vf3`. And may the temp folder go once the copies check out?
3. **The hand in the arm's first twin** (the hand-off's reading): the generator's fused shape as one
   labelled part on the flange (recommended: it is what the photos give), or a labelled stand-in?
   Its 21 joints come in Phase 7.
4. **The fingers in Phase 7:** labelled stand-ins sized from the maker's model, or the maker's
   meshes imported and labelled? Stand-ins keep the photos-to-twin path; the meshes are closer to
   the real hand but are not generated. Perhaps a question for the advisors too.
5. **The arm's front:** the side away from its base's connector panel?
6. **The scorecard:** take it to the next weekly meeting as proposed?
7. **The lab visit:** worth planning, and with which items?
8. **The tool gaps:** items 1, 4, 5 and 7 in Phase 1. Items 2 and 6 as well?
9. **Phase 8's agent build:** the TM-1, or another machine?
