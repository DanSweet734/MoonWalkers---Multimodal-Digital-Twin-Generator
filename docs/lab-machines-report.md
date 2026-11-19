# MoonWalkers lab machines plan: report (the ReBeL arm with its hand, the Haas TM-1 and VF-3)

**Status: read by Daniel, 2026-11-18 ("The report looks fine"),** at the end of the plan's
Phase 8 ([docs/lab-machines-plan.md](lab-machines-plan.md)). The advisors' page for the meeting of
2026-11-19 tells the same story for them: https://claude.ai/artifact/3kcdDKCn5AZExqbsF8oJ6B. Written by Claude Code with Daniel Sweet. As in
the [drill-press report](drill-press-report.md), each claim names its evidence: a decision record, a
worklog, a run's `RUN.md` or `score/SCORE.md`, or a program's `PROGRAM.md` (run folders are under
`data/`, which is not in the repository). Reasoning that no source states is labelled [INFERENCE].

**The answer, in short.** Yes, from photos alone: every machine of Dr. Li's lab that Daniel
photographed on 2026-11-05 has a twin at all three success levels in Isaac Sim 6.2, and a fresh
agent session built a fourth version of the TM-1 that reached levels 2 and 3, with a worse mesh.
- **The ReBeL arm** (`igus/rebel6dof02@v5`): seven parts on six joints, cut from one generated
  mesh, posed as photographed. Its joint axes point within 0.01° of the maker's ROS model's and
  sit within 8.6 mm of them; of its five cited lengths, two are within 6%, two within 8.4%, and the
  wrist is 17.9% short. Its joints reach both ends of their
  ranges within 0.01°, and a labelled test program in igus Robot Control's own format runs within
  0.29° of its plan (the lab's own program has not come yet).
- **The hand on it** (the same twin): 21 joints, 16 driven and 5 following, on LinkerBot's L20
  model's frames, as labelled stand-ins, since the generated hand contradicts the photos. Its ends
  are reached within 0.15°, and an open, fist, open grasp from the maker's SDK commands runs within
  0.86° of its plan.
- **The Haas TM-1** (`haas/tm1@v3`): the generated frame and head, with stand-ins for the saddle,
  the table, the spindle nose and the 10-pocket carousel. Each axis reaches both ends of its cited
  travel within 0.01 mm; two of Haas's own programs run with the tool tip within 0.017 mm of the
  path. Its height is 24% under the cited 109 in, as the photos show it.
- **The Haas VF-3** (`haas/vf3@v1`): the generated enclosure, with stand-ins inside for the axes
  and the TR160 trunnion. Every axis reaches its limits within 0.01 mm or 0.01°, and a program
  that tilts and turns the part runs with the tip within 0.021 mm of the path and A and B within
  0.004°.
- **The agent's build** (`haas/tm1@v4`, Phase 8): a fresh Claude Code session, from Daniel's
  dashboard job, through the MCP tools, in 38.5 minutes. Its facts agree with v3's; both
  validators are clean; 51 of 73 quotes are on their pages and none is missing (22 cannot be
  checked by the tool). Its joints and program met levels 2 and 3 in Daniel's check. Its mesh is
  worse than v3's, because the agent cut the machine out of the photos with SAM's points where v3
  had drawn masks: a 10 in pedestal under the base, shards of the generated table left in the
  frame, a bumpy right guard and holes.
- **The main limits** (section 7): the meshes are bumpy and the advisors want them better; most
  moving parts of the mills and the whole hand are stand-ins; the directions and homes of several
  axes, the trunnion's model and the hand's model are not confirmed until the lab visit; masses are
  placeholders.

## 1. The question
The advisors asked for real-world comparisons on the lab's machines (meeting of 2026-11-05;
[drill-press report](drill-press-report.md), section 7.1). Daniel photographed three, with their
nameplates: a "ReBeL® 6-DoF Cobot with SCHUNK EGP Gripper and CobotPump" with a "Realhand L20
Dexterous Robotic Hand" attached, a Haas VF-3 and a Haas TM-1. Daniel's calls (2026-11-09): all
three machines, in the order the arm, the TM-1, the VF-3, then the hand, which is part of the
arm's twin.

The success levels, for each machine ([the plan](lab-machines-plan.md), "Success levels"):
1. A scaled model, cut into its moving parts, with cited facts, opens in Isaac Sim. It is built from
   the lab's photos, and its sizes are compared with every cited dimension.
2. Its joints move as the sources say in Isaac Sim: each about its cited axis, through its cited
   range, and holding where it is put.
3. Its control drives it: a program or commands from the machine's own control, run in Isaac Sim
   and measured against the plan the controller made.

Also: the HA5C and the T33901 still build and are reused; an agent builds one lab machine from a
dashboard job (Phase 8); and "accurately" is measured by a scorecard (section 4), which the
advisors accepted on 2026-11-12 with "always shoot for as close as possible".

## 2. What was built
| Phase | What | Decisions | PR |
|---|---|---|---|
| 0 | The plan; the scorecard | - | #27 |
| 1 | The 29 photos filed (SHA-256 checked); photos turned upright from their EXIF; cutting the machine out of each photo with SAM, a crop box or a drawn mask; six tool gaps from the drill press closed (`set_photo`, `correct_issue`, `dry_run_twin`, `fit_circles` in a box and along a direction, mesh warnings in `preview_twin`, uploads from several folders). 28 MCP tools | 0029, 0030 | #28 |
| 2 | The ReBeL arm, levels 1 and 2: a box-and-cylinder arm first, then `igus/rebel6dof02@v1` to `v3`; a per-twin hold, loose pieces removed, self-collision; the scorer | 0031, 0032 | #29 |
| 3 | The arm's level 3: igus Robot Control's XML programs read and planned; a labelled test program | 0033 | #30 |
| 4 | The TM-1, levels 1 and 2: `haas/tm1@v1` to `v3`, from three corners; a slide check file | 0034 | #31 |
| 5 | Haas G and M codes read by our own reader; the TM-1's level 3 with two of Haas's programs | 0035 | #32 |
| 6 | The VF-3, levels 1 to 3: the enclosure with stand-ins inside; the trunnion's A and B axes in the reader; parts hidden in check files | 0036 | #33 |
| 7 | The hand: 21 joints on the arm (`v4`, `v5`); LinkerBot's SDK commands as a program | 0037, 0038 | #34 |
| 8 | The agent builds `haas/tm1@v4`; a fix to where a mill program's tool tip sits; this report | 0035 (update) | this PR |

At the end of Phase 8 the backend's quick suite has 889 tests passing (853 at the end of Phase 6).

## 3. Results
### The ReBeL arm (`igus/rebel6dof02`)
- **Level 1: met** (v1, 2026-11-09; decision 0031). One Hunyuan3D-2mv mesh from the arm's four
  sides, each cut out by a mask made from SAM's cut-out, cut into seven parts by cited shapes.
  Scaled by X2, 237 mm, between two joint axes fitted by `fit_circles` (igus's documentation, p. 6)
  [INFERENCE: the straightest link]. Position 0 of each joint is its photographed pose, and igus's
  limits are shifted by each joint's angle in it (decision 0031).
- **Level 2: met** (Daniel's checks, 2026-11-10):
  - a box-and-cylinder arm first (run `moonwalkers-testarm/runs/2026-11-09_run-001`): every joint
    reached its upper limit within 0.001°; the default drive sagged 1.1-1.5°, the stiff one 0.06°;
  - v1: both ends of every range reached within 0.01°; but the arm folded through itself, loose
    bits floated, extra cable strands and a duplicate thumb showed (decision 0032);
  - v2: a stiffer hold, the strands and loose bits cut out, a self-collision check file; clean;
  - v3: the remaining strands cut by measured boxes, collisions on in the twin; it holds within
    0.043°. Daniel: "in a good spot".
- **Level 3: met** (Daniel's check, 2026-11-10; decision 0033). iRC's own XML, read by
  `control/irc.py`, planned as synchronised joint moves at the cited 45°/s. The lab shared no
  program, so the labelled test `rebel-test-joint-moves` (16 moves, 24.36 s) ran: every joint within
  0.29° of the plan, at 45.00°/s, no collisions. Logged: when joint 2 turns, part of the column comes
  with it (v3's cut list [INFERENCE]).

### The hand (`igus/rebel6dof02@v5`)
- **Level 1: met** (decision 0037). The generated hand contradicts the photos (two thumbs), so the
  fingers are labelled stand-ins on LinkerBot's right L20 model's frames, its meshes read for sizes
  only, not imported. 21 joints (16 driven, 5 following their leaders), 27 moving joints in one
  articulation with the arm. The hand's parts pass through each other (the spec's `collide_apart`).
- **Level 2: met** (Daniel's check, 2026-11-17): every finger reaches its ends within 0.15°. v4
  blew up in Isaac Sim: a following joint's speed cap fought its leader. The exporter now writes
  followers without a speed cap and with limits 2° clear of their leader's reach (worklog
  2026-11-17).
- **Level 3: met** (Daniel's check, 2026-11-17; decision 0038). LinkerBot's SDK calls (`set_speed`,
  `finger_move`, `sleep`) as a program, values turned into angles by the SDK's `mapping.py`: open,
  fist, open within 0.86° of the plan. The thumb passes through the fingers at the fist; the maker's
  own meshes overlap at its fist preset too.

### The Haas TM-1 (`haas/tm1@v3`)
- **Level 1: met** (decision 0034). Generated from **three** corners: a four-corner trial put the
  pendant at the back, pulled by the back right photo, which a sign and a stool hide below 60%. Each
  fed photo has a drawn mask (SAM's cut-out plus traced polygons; worklog 2026-11-11). The head is cut
  from the mesh; the saddle, the table with its T-slots and chip guard, the spindle nose and the
  10-pocket carousel are stand-ins. Scaled by the cited 90 in width. Y travel 12 in from Haas's 2002
  addendum, where today's pages say 16 (research note 2026-11-11).
- **Level 2: met by v3** (Daniel's check, 2026-11-11): the head holds within 0.014 mm; each axis
  reaches both ends within 0.01 mm at the cited 200 ipm (84.7 mm/s); the carousel indexes 36° a
  pocket and holds. v2's head sank 100 mm under the exporter's default hold, fixed in v3.
- **Level 3: met** (Daniel's check, 2026-11-16; decision 0035). Our own reader of Haas's codes
  (`control/haas_gcode.py`, no library). Haas's O40001 and O40006 (2023 manual, pp. 102 and 172):
  the tip within 0.017 mm of the path (0.014 mm while cutting), every block within 0.01 s of its
  planned end, the axes at 84.7 mm/s, the spindle at 1000 rpm. Z lags the plan up to 1.84 mm while
  rising at the rapid (the speed cap [INFERENCE]).

### The Haas VF-3 (`haas/vf3@v1`)
- **Level 1: met** (decision 0036). The generated enclosure from two sides, scaled by its cited
  78.8 in height, with stand-ins inside for the base, the saddle, the table, the head, the nose and
  the trunnion's base, cradle and platter: a TR160 by elimination [INFERENCE] until its plate is
  read. The spec's
  `hidden_in_checks` hides the enclosure in check files and program folders, never in `twin.usdc`.
- **Level 2: met** (Daniel's check, 2026-11-17): every limit within 0.01 mm or 0.01°; the head
  holds within 0.019 mm; `a_axis` ±120°, `b_axis` unlimited, 80°/s. A `b_axis` target typed in Isaac
  Sim goes a turn at a time.
- **Level 3: met** (Daniel's check, 2026-11-17). A and B in the Haas reader: Haas's O40001 on the
  platter and the labelled test `moonwalkers-vf3-test-tilt-and-turn`: the tip within 0.021 mm of the
  path, A and B within 0.004° of the plan, every block within 0.02 s.

### The agent's build (Phase 8)
- **The job.** Daniel uploaded the TM-1's eight photos in the dashboard on 2026-11-18, with "Build a
  new version" ticked; views and uses as v3's, recorded as the user's choice (the plan's run-sheet).
  One use was set wrong in the form (the back left corner as evidence, where v3 fed it to the
  generator); the Phase 8 chat found it in `request.json` before the agent started, and Daniel's
  starter prompt asked the agent to correct it with `set_photo`, which it did first.
- **The session** (`docs/worklog/2026-11-18.md`, the agent's own entry; transcript `4f635491`): a
  fresh Claude Code session, 38.5 minutes (23:19-23:58 UTC), 191 tool calls, 88 of them to 20 of the
  28 MCP tools.
  - **The prompt** (the plan, "The agent's starter prompt") allowed the Haas documents, the
    procedure, the decisions and the packaged O40001 as a format. It held back v3's reference
    facts, spec, runs and part-cutting scripts, the TM-1 and mill-program research notes, the
    worklogs and the plan until after `submit_twin`.
  - **What the transcript shows:** no held-back path in any tool call before `submit_twin`.
    CLAUDE.md, which every session loads, describes v3 (three corners, the stand-ins, the 12 in Y
    travel): a limit of the test, as for the drill press's agent [INFERENCE].
  - **Its MCP calls:** 17 `add_fact`, 13 `add_reference_source`, 13 `set_photo` (its worklog says
    eleven), 11 `set_spec_part`, 6 `preview_cutouts`, 5 `set_spec_joint`, 4 `add_issue`, 4
    `preview_twin`, 2 each of `check_knowledge_base`, `inspect_geometry` and `set_cut_list`, and one
    each of `list_jobs`, `generate_geometry`, `identify_machine`, `set_spec_frame`,
    `set_scale_length`, `add_control`, `dry_run_twin`, `submit_twin` and `request_twin`. Unused:
    `start_run` and `add_input` (the dashboard made the job), `add_joint` and `set_scale` (one-part
    tools), `fit_circles`, `correct_issue`, `remove_spec_entry` and **`set_size_checks`**, which the
    procedure asks for (`agent-procedure.md`, step 5b).
  - **Its one question:** what to scale by. Daniel: "Width 90 in (Recommended)".
- **What it built:** `haas/tm1@v4` (run `2026-11-18_run-001`), the same six parts and five joints
  as v3, with O40001 recorded as a control behaviour, so the build wrote its program folder.
  - **The checks:** `dry_run_twin` clean on its first call; both validators clean on `twin.usdc`,
    the three check files and `program.usdc` (the agent's run, and the Phase 8 chat's re-run). The
    quote checker: 73 quotes, 51 on their page, 0 elsewhere, 0 not found, 22 not checkable (photos,
    the saved product page, Daniel's answer).
  - **The cut-outs:** SAM with boxes and points on all three corners, after six sheets; it kept 45%,
    36.5% and 55.5% of the photos, with ragged pieces, the base and chip pan lost from the front
    right corner, and floor kept in the front left one (`cutouts/sheet.png`). It did not use v3's
    drawn masks, the run-sheet's fallback, and did not ask about the cut-outs.
  - **The mesh:** 40,000 faces, generated in 92 s. Its overlays match the photos less than v3's
    (silhouette IoU 0.688, 0.612 and 0.773 against 0.751, 0.797 and 0.842).
- **Against v3** (compared by the agent after submitting; its worklog has every difference):
  - the same facts where both have them, including 12 in of Y for the same reason; v3 has 17 more
    (T-slots, the taper, the carousel's 15.6 in, the control and others). The agent: "v3 is right to
    have them";
  - the same frame, fixed part, hold, scale and five joints; v3's table, saddle (with handwheels)
    and carousel stand-ins are the better ones, by the agent's own judgement;
  - **X at position 0:** the agent took the photographed table to be at X home; v3 measured it 4.6
    in in from the end. The agent: "v3 is more likely right";
  - **the spindle turns the other way:** v4's axis is -z, so M03 turns it clockwise seen from above;
    v3's is +z. Neither manual read states the viewing side [INFERENCE]; to settle at the lab.
- **Daniel's check of v4** (2026-11-18, recorded in its `RUN.md`):
  - **Level 1:** it does not stand flat. The frame's lowest 0.25 m is one generated block about
    0.62 x 0.45 m (the agent set the base at the mesh's lowest point, where v3 cut under its floor
    line), so the machine stands about 10 in up; the height check's -13.5% includes it [INFERENCE:
    about 2.1 m without it, as v3]. Shards of the generated table block pass through the stand-in
    table; holes in the mesh; the right guard "very bumpy and unstable". The carousel stand-in "seems
    good".
  - **Level 2: met.** Every axis reaches both ends within 0.01 mm at 84.7 mm/s; the carousel held
    exactly 36, 72 and -36° and back; the head holds within 0.0135 mm. The saddle passes into the
    frame's mesh at Y's back end (collisions off).
  - **Level 3: met, after a fix.** In the agent's folder the tool looked off centre. The cause was
    ours: `mill_export.measure_geometry` took the nose's centre as the mean of the spindle's lowest
    face, and the agent's one-lug stand-in put the lug's points on that face, 5.4 mm off the axis;
    the tool, drawn there, circled the axis at 1000 rpm. The nose now sits on the spindle joint's
    axis (a test with an off-axis nose; v3's and the VF-3's program files measure 0.000 mm
    different). Re-run with `control run` on the agent's own `program.json`
    (`data/machines/haas-tm1/programs/2026-11-18_haas-o40001-basic-program_v4/`), the same joint
    plan: the tip within 0.014 mm of the path while cutting, every block within 0.01 s, the axes at
    84.7 mm/s, 1000 rpm. Daniel: "The tool is centered now".
  - **Review:** left unreviewed (Daniel, 2026-11-18), so a request still reuses v3.

### Reuse
- **The lab's twins:** Daniel approved `haas/tm1@v3`, `haas/vf3@v1` and `igus/rebel6dof02@v5` on
  2026-11-17. After the agent's submission, `request_twin` answered: "Found an existing twin (v3,
  approved) for haas/tm1; reused it. Newer versions were not reused: v4 (needs review)." An
  unreviewed version never replaces an approved one (decision 0015).
- **The HA5C and the T33901 still build** (2026-11-18, after Phase 8's fix): their approved runs
  (`haas-ha5c/runs/2026-10-18_run-001`, v3; `grizzly-t33901/runs/2026-11-04_run-004`, v11), staged
  unbuilt in `data/scratch/2026-11-18_phase-8-reuse/` (`stage.py`) and dry-run: the HA5C built as
  version 4 in the scratch knowledge base, the T33901 built too, both validators clean on every file
  (our validator's only notes on the T33901 are its five informational ones: the mimic joint and
  four locks). Both are approved, so requests reuse HA5C v3 and T33901 v11 (decision 0015).

## 4. The scorecard
The plan's measures ("How 'accurately' is measured"), accepted at the meeting of 2026-11-12 with
the targets unchanged. From each run's `score/SCORE.md` and Daniel's recordings.

| Measure (target) | Arm `v5` | TM-1 `v3` | TM-1 `v4` (agent) | VF-3 `v1` |
|---|---|---|---|---|
| Sizes (within 6%; over 10% flagged) | base to joint 2 +2.0%; joint 3 to 5 -5.8%; joint 2 to flange -6.0%; footprint -8.4%; **wrist -17.9%** | depth +0.6%; **height -24.0%**; carousel to spindle -9.6%; the generated table -16.2% (replaced) | no size checks set; the build's own: depth +8.7%, height -13.5% (with the pedestal) | operating height -9.7% |
| Photo match, silhouette IoU (no target) | 0.742, 0.675, 0.764, 0.739 | 0.751, 0.797, 0.842 | 0.688, 0.612, 0.773 | 0.890, 0.760 |
| Shape against the maker's model, mean / p95 (no target) | links 4.7-22.5 / 9.5-80.4 mm (twin to maker) | no public model | no public model | no public model |
| Parts and joints (every moving part named) | 7 of 7 links, 6 of 6 joints; the hand's 21 joints are not read by the scorer | head, saddle, table, spindle, carousel | the same | axes, head, spindle, trunnion A and B; the tool changer left out (not in the photos) |
| Joint axes and places (no target) | directions within 0.01°, places 0-8.6 mm | by direction only | by direction only | by direction only |
| Ranges (within 1° or 1 mm) | within 0.01° (v1's recordings); hand within 0.15° | within 0.01 mm | within 0.01 mm | within 0.01 mm or 0.01° |
| Control (the T33901's 0.63 mm) | 0.29° (test program); hand 0.86° | tip 0.017 mm | tip 0.014 mm cutting (fixed folder) | tip 0.021 mm; A, B 0.004° |
| Evidence (every quote found) | 223 found, 0 missing, 7 not checkable | 76 found, 0 missing, 7 not checkable | 51 found, 0 missing, 22 not checkable | 121 found, 0 missing, 1 not checkable |

The arm's ranges were last scored on v1's recordings; v3's spin recording stopped where parts met
(joint 2 at +78.9°), as Phase 3's hand-off logs. The arm's size checks are the same in every
version (the same mesh and scale).

## 5. Per-run record
Generator: Hunyuan3D-2 2.0.2 with the multi-view model `hunyuan3d-dit-v2-mv`, seed 12345, on an
RTX 4090. Isaac Sim 6.2 for every check. Reviews are Daniel's, in the dashboard (decision 0015).

| Twin | Run folder | Built by | What changed | Success level (Daniel's check) | Review |
|---|---|---|---|---|---|
| test arm | `moonwalkers-testarm/runs/2026-11-09_run-001` | Claude Code (CLI), Phase 2 | boxes and cylinders on the cited frames | joints and holds (2026-11-10) | - |
| arm `v1` | `2026-11-09_run-001` | Claude Code: the spec through the MCP tools, built from the command line | the first cut, posed as photographed | 2 for the ranges; folds, loose bits (2026-11-10) | needs review |
| arm `v2` | `2026-11-10_run-001` | Claude Code (script) | hold, loose pieces, strands cut | clean (2026-11-10) | needs review |
| arm `v3` | `2026-11-10_run-002` | Claude Code (script) | strands by boxes, collisions on | 2, and **3** with the test program (2026-11-10) | needs review |
| arm `v4` | `2026-11-17_run-001` | Claude Code (script), Phase 7 | the hand's 21 joints | blew up (followers' speed cap) | needs review |
| arm `v5` | `2026-11-17_run-002` | Claude Code (script) | followers uncapped, limits clear | **3** for the arm and the hand (2026-11-17) | **approved** (2026-11-17): "Mesh needs work, many gaps and rough faces. Even so satisfactory for current Phase." |
| TM-1 `v1` | `2026-11-11_run-001` | Claude Code (script), Phase 4 | the first cut, three corners | no slide check file | needs review |
| TM-1 `v2` | `2026-11-11_run-002` | Claude Code (script) | stand-ins, the slide check | the head sank 100 mm | needs review |
| TM-1 `v3` | `2026-11-11_run-003` | Claude Code (script) | the sliding joints' hold | 2 (2026-11-11), **3** with two programs (2026-11-16) | **approved** (2026-11-17): "TM-1 is satisfactory for this phase, further optimization and refinement planned for later phases." |
| TM-1 `v4` | `2026-11-18_run-001` | **a fresh Claude Code session through the MCP tools,** from a dashboard job | everything, written anew | 2 and **3** (2026-11-18, the fixed program folder); the mesh's faults | not reviewed (Daniel's choice) |
| VF-3 `v1` | `2026-11-16_run-001` | Claude Code (script), Phase 6 | the enclosure, stand-ins inside, the trunnion | 2, and **3** with two programs (2026-11-17) | **approved** (2026-11-17): "Satisfactory mesh generated, further optimization and refinement planned for later phases." |

"Script" means a spec written by a Python script in the machine's `part_cutting/` folder and
built from the command line, dry-run first.

## 6. The decisions behind it
Each record in [docs/decisions/](decisions/) has the options, sources and costs in full. Claude
Code proposed each one, and Daniel reviewed and accepted it.

| No. | Decision | Status |
|---|---|---|
| [0029](decisions/0029-cutting-the-machine-out-of-each-photo.md) | Cutting the machine out of each photo: SAM with a box and points, a crop box, or a drawn mask, per photo, previewed in seconds | accepted, 2026-11-09 |
| [0030](decisions/0030-tools-the-drill-press-agent-lacked.md) | The tools the drill press's agent lacked | accepted, 2026-11-09 |
| [0031](decisions/0031-the-arms-views-front-and-zero-pose.md) | An arm's views, front and zero pose: the photographed pose is position 0, the maker's limits shifted by it; the public model is a source of facts and the score, never the geometry | accepted, 2026-11-10 |
| [0032](decisions/0032-an-arms-hold-its-loose-pieces-and-self-collision.md) | A per-twin hold, loose pieces removed, self-collision | accepted, 2026-11-10 |
| [0033](decisions/0033-an-arms-joint-programs.md) | iRC's own XML read and planned as synchronised joint moves; linear moves refused | accepted, 2026-11-10, "as is until we know if we get the program from the lab" |
| [0034](decisions/0034-a-mills-axes-from-its-photos.md) | A mill's axes from its photos: three corners, stand-ins for the axes' parts, the slide check | accepted, 2026-11-11 |
| [0035](decisions/0035-a-mills-g-code-programs.md) | Our own reader of Haas's codes, program folders with a stand-in tool, stock and the drawn path; updated 2026-11-18: the nose on the spindle's axis | accepted, 2026-11-16; the update for Daniel's review |
| [0036](decisions/0036-a-trunnions-a-and-b-axes.md) | A trunnion's A and B axes in the reader; parts hidden in check files | accepted, 2026-11-17 |
| [0037](decisions/0037-the-hands-fingers-and-their-joints.md) | The hand's fingers as stand-ins on the maker's frames, 21 joints with followers | accepted, 2026-11-17 |
| [0038](decisions/0038-a-hands-sdk-commands.md) | The hand's SDK commands as a program | accepted, 2026-11-17 |

## 7. Limits, stated plainly
- **The meshes are bumpy and less detailed than hoped** (the advisors, 2026-11-12). Better meshes
  and other generators come after this plan; the scorecard's photo match is the baseline.
- **Cutting a busy lab photo needs a person.** Every machine's photos needed drawn masks or boxes
  erased by hand; SAM's points alone were not enough on the arm, the TM-1 or the VF-3. The agent,
  without masks, got a worse mesh from the same photos (section 3).
- **Most moving parts are stand-ins.** The mills' saddles, tables, noses, carousel and trunnion,
  and every finger. They match the photos and cited sizes, not the parts' real shape (decision
  0027's rule).
- **Not confirmed until the lab visit:** which way the mills' axes move and where they home; the
  trunnion's model; the hand's maker, model and side; the arm's version 02 against igus's 00; the
  TM-1's height (cited 109 in, about 80 in in the photos).
- **The control is cited, not observed.** Level 3 compares the twin with its own plan at the cited
  speeds. The real machines' motion needs video (the video plan). The arm's program is a labelled
  test until the lab's own comes.
- **Placeholder physics.** Masses are placeholders (a bonus, Dr. Lu, 2026-11-05). Accelerations are
  stand-ins where no source gives them.
- **People stay in the loop.** Daniel's checks in Isaac Sim found what the validators and previews
  did not: v1's folding arm, v2's sinking head, v4's blown-up hand, the agent's pedestal and the
  off-centre tool.

### Known inaccuracies and stand-ins, in one place
For the approved versions unless the row says otherwise. Each carries a warning in its twin; the
twins' `RUN.md` files list every one (the hand alone has 79 warnings).

| What | How far off, or what it rests on | Evidence |
|---|---|---|
| The arm's wrist (joint 5 to the flange) | -17.9% against igus's drawing of version 00 | v5's score; Phase 2 |
| The arm's version | 02 not confirmed to match igus's 00/01 models | the reference facts' issue |
| The arm's joints 1, 4 and 6 in the photographed pose | taken as 0, not confirmed | decision 0031 |
| The arm's mesh | a wire or two still attached; gaps on the backs of the joints; part of the column moves with joint 2 | v3's `RUN.md`; Phase 3 |
| The arm's acceleration and program | no acceleration cited (a stand-in); the program a labelled test | decision 0033 |
| The hand's fingers | stand-ins on LinkerBot's right L20 frames; right hand and maker [INFERENCE]; parts pass through each other; the thumb passes through the fingers at the fist | decisions 0037, 0038 |
| The TM-1's height | -24.0% against the cited 109 in; the photos agree with the mesh (about 80 in) | v3's `RUN.md` |
| The TM-1's Y travel | 12 in (Haas's 2002 addendum) against 16 in on today's pages | research note 2026-11-11 |
| The TM-1's axes | +X, +Y and X home are stand-ins; the table passes 2 in into the left guard at X's left end | decision 0034; v3's `RUN.md` |
| The TM-1's carousel | 10 pockets second-hand; 15.6 in from today's drawing | v3's `RUN.md` |
| The TM-1's back | the back right corner not fed (a sign and a stool); guessed | decision 0034 |
| The TM-1's control | Classic Haas Control [INFERENCE] | research note 2026-11-11 |
| Mill programs | a 3 in tool, 2 in stock and the work offset are stand-ins; Z lags up to 1.84 mm at the rapid; a typed target moves an axis up to 224 mm/s | decision 0035; Phase 4 |
| The VF-3's trunnion | a TR160 by elimination; +A's and +B's directions and homes are stand-ins | decision 0036 |
| The VF-3's height | -9.7% | v1's score |
| The agent's TM-1 (`v4`) | a 10 in pedestal; shards of the table block in the frame; 7 holes patched; a bumpy right guard; X at its home end [INFERENCE]; the spindle turned the other way from v3 | v4's `RUN.md`; section 3 |
| Masses | placeholders | decision 0024, update |

## 8. Open questions, by priority
### 8.1 For the advisors (meeting of 2026-11-19)
1. **The agent's build.** It reached levels 2 and 3, but its mesh is worse where it cut the photos
   without drawn masks. Should the next step be a tool to draw or correct a cut-out (in the
   dashboard, or polygons added and removed on top of SAM, as v3's masks were made), then a second
   agent run with it?
2. **Video.** Both Haas mills reached level 3, the advisors' condition (2026-11-12). Start the video
   plan now?
3. **The VF-3's trunnion** (Daniel raises it when scheduling his next visit): a square-on photo of
   the plate on the cradle's base; if unreadable, the control's Settings 78 and 30; if allowed, a
   phone video of a jog of +A, then +B.
4. **The lab's iRC program** for the arm, through Dr. Li's assistant, with the visit.

**Answered at the meeting of 2026-11-12** (worklog 2026-11-16): the scorecard accepted, targets
unchanged, "always shoot for as close as possible"; keep to photos until both Haas mills reach
level 3, in the order TM-1, VF-3, hand, agent build; the meshes are bumpy, so optimising and other
ways to generate come later; the lab's arm program comes later; the semester ends about
2026-12-17.

### 8.2 For Daniel and the team
1. **The lab visit** (the plan's visit list), postponed until after 2026-11-19.
2. **`haas/tm1@v4`'s review,** left open by Daniel's choice.
3. **The pipeline owners' review** of decisions 0020 and 0021 (Ava, Kiran, Sarkis), still open.

### 8.3 Found in the agent's build: gaps in the tools
From the agent's worklog and the Phase 8 chat's check. Only the last is fixed.
1. **No way to draw or correct a cut-out.** SAM breaks into pieces with many points and keeps the
   neighbours with few; a drawn mask must be made outside the tools (the agent's gap 2).
2. **Nothing warns that the base stands on a small slab.** `set_spec_frame` takes a `base_z`, and
   the cut list can cut under a floor line, as v3's script did (`base_z` -0.75, a cut under z
   -0.763). The agent left `base_z` unset, the mesh's lowest point, and kept a generated pedestal
   about 0.62 x 0.45 m; no preview flagged it.
3. **Nothing warns about pieces of a removed part left in a kept part,** where a moving part
   passes (the shards through v4's table).
4. **`inspect_geometry`'s point views are hard to read for edges** on a 40,000-face mesh; the agent
   wrote its own shaded renderer in its scratch folder (the agent's gap 1).
5. **No tool places a hole on the photos;** holes come in model units only (the agent's gap 3).
6. **The photo overlays' camera fit can be far off** (the front's elevation 46° for a photo taken
   at head height), and nothing lets the agent pin a camera (the agent's gap 4).
7. **`set_spec_frame` cannot set `hidden_in_checks`** (known since Phase 6; not needed for the
   TM-1).
8. **The scorer reads one maker's model per twin,** so the hand is not scored (Phase 7).
9. **`set_size_checks` was skipped** without a warning: nothing in `preview_twin` or `dry_run_twin`
   says a spec has no size checks.
10. **Fixed: a mill program's tool tip** sat off the spindle's axis when a key lay on the nose's
    face (decision 0035, update of 2026-11-18).

## 9. Next
The plan's three machines reach all three levels, and an agent built one from a dashboard job.
For the advisors to choose (8.1): a cut-out tool and a second agent run; the video plan; the lab
visit's measurements, each a new version where it changes a twin. The record for a new chat: this
report, [docs/lab-machines-plan.md](lab-machines-plan.md) and CLAUDE.md's "Current phase".
