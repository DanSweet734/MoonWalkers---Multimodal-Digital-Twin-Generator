# 0020 - Contract v0.2.0: linked joints and joint modes

- **Status:** proposed (by Claude Code in the drill-press plan's Phase 2). Daniel reviewed it on
  2026-10-23 and kept it, with two points researched and one name changed ("Review", below). It is
  discussed with Ava, Kiran and Sarkis before it is merged (CLAUDE.md, "Who owns what").
- **Date:** 2026-10-23
- **Decided by:** team (Daniel, with the pipeline owners)
- **Amends:** decision 0004 (the contract, v0.1.0). Part of what decisions 0017-0019 put in the
  exporter's `JointSettings` moves into the contract.

## Context
Phase 1 showed in Isaac Sim 6.2.0 what the drill press's joints need (decisions 0017-0019): a
spring that returns the quill, a depth stop, locks by equal limits, free table motions, and handles
that follow the quill through a mimic joint. All of these are exporter settings (`JointSettings`),
chosen in code for each check file. A pipeline cannot state any of them, because contract v0.1.0
has no field for them.

**What v0.1.0 already describes** (worklog 2026-10-22), and keeps unchanged:
- prismatic joints, with limits in metres;
- a parent and a child part on every joint, so joints make a tree, and a chain is a tree;
- a cited top speed (`max_velocity`);
- control behaviours of kind `state_machine` and `lookup_table`, with a free-form `spec`;
- cited physical values as `Fact`s, for example a spring's force or a pinion's tooth count, when a
  source gives them.

**What it cannot describe.** The T33901 manual
(`data/machines/grizzly-t33901/inputs/documents/grizzly-t33901-t33902-manual-2023.pdf`; every quote
below was checked against its PDF page with pypdf on 2026-10-23):
- **A joint that follows another.** "Moves spindle down when pulled down" (p. 7), through the
  quill's rack and pinion: "Lubricate column rack and quill rack and pinion" (p. 35). No source we
  reached gives the ratio, so it is a labelled stand-in
  (`docs/research/2026-10-22-t33901-handle-ratio-and-figures.md`; Daniel, 2026-10-22).
- **How a joint is held or moved when nobody commands it:**
  - a spring return: "Spindle Return Spring: Automatically returns quill into headstock" (p. 7);
  - locks: "Table Height Lock Handle: Loosens to allow adjustment of table position on column;
    tightens to lock table position" (p. 7), and the "Table Pivot Lock Handle" (p. 32);
  - free motion once a lock is loosened: "Rotate table to desired position" (p. 32);
  - a drive: "Spindle speed is controlled by the configuration of V-belts and pulleys" (p. 30).
- **An adjustable stop inside a joint's limits:** the depth stop, "a threaded rod attached to the
  quill with a depth stop nut that can be lowered or raised against a stop bracket" (p. 31).

**Stored results.** `schema_version` is `Literal["0.1.0"]`, so the contract accepts no other
value today. Eight stored files say "0.1.0":
- four in `data/kb/results/`: the HA5C's three results (runs `2026-10-17_run-002`,
  `2026-10-17_run-003` and `2026-10-18_run-001`) and the TH240's one (`2026-10-18_run-001`);
- the same four in their run folders, as `pipeline_result_b.json`.

The repository also holds four: the fixture `backend/tests/fixtures/ha5c_pipeline_b.example.json`
and the three stubs' `haas_ha5c.stub.json`. Stored records are never overwritten (decision 0008),
and neither are run folders (decision 0012).

**The teammates.** No pipeline code uses the contract yet. The one teammate branch, `Sarkis`, was
only a test of access to the repository, and is ignored (Daniel, 2026-10-23).

## Options considered
1. **Where the contract stops.**
   - (a) **The machine's behaviour only:** what moves or holds each joint, where, and what it
     follows, each with a citation. The simulation's numbers stay in the exporter: stiffness,
     damping, the spring's preload, the drive type, mimic or rack and pinion, and starting
     positions for a check.
   - (b) **Everything `JointSettings` holds,** so a result fixes the whole simulation. Pipelines
     would then pick tuning values that no source gives, and every pipeline would carry PhysX's
     choices.
2. **Linked joints.**
   - (a) **A field on the follower:** `follows`, with its leader, ratio and offset. The handles have
     one leader, and `PhysxMimicJointAPI` has a single `referenceJoint` relationship for each
     axis it moves, `rotX`, `rotY` or `rotZ`
     (`docs/research/2026-10-22-sliding-joints-locks-and-coupling.md`, section 4).
   - (b) **A list of links beside `joints`.** Each link is an edge of its own, as in a graph. But
     a follower's rule, no mode of its own, then spans two lists.
   - (c) **A `ControlBehavior` of kind "other".** Its `spec` is free-form, so nothing could check
     it. And a rack and pinion is mechanism, not control.
3. **Joint modes.**
   - (a) **One `mode` per joint,** of four kinds (driven, spring return, locked, free), with one
     position: where a spring returns the joint, or where it is locked. The adjustable stop is a
     field of its own, because the quill has both a spring and a stop.
   - (b) **What the joint has, apart from how it is set:** "lockable" or "has a spring", and then
     "locked at 30°". That is closer to a machine whose locks an operator opens
     [INFERENCE], but it doubles the fields, and the exporter needs only the setting.
   - (c) **Free-form text or a dictionary,** as `Part.primitive` is. Nothing could check it.
4. **How a stand-in ratio is labelled.**
   - (a) **A `stand_in` flag on the link,** and the validator requires an issue on that joint. The
     label can be read by code (the dashboard, the exporter, the phase report's table), and the
     issue cannot be forgotten.
   - (b) **As Phase 1 labels made-up sizes:** a citation to a `user_input` source whose locator
     says so, plus an issue. Nothing checks that both are there.
5. **The stored v0.1.0 results.**
   - (a) **Add only:** every new field is optional, and `schema_version` accepts "0.1.0" and
     "0.2.0". A result that says "0.1.0" may not use the new fields, so its label stays true.
     Nothing is rewritten.
   - (b) **Migrate:** rewrite the eight files to "0.2.0". That edits stored records, against
     decisions 0008 and 0012.
   - (c) **Upgrade on reading:** "0.1.0" is read as "0.2.0". The record in memory then says
     something its file does not, and a teammate's "0.1.0" result would be relabelled without
     anyone noticing.
   - (d) **Two models, one per version,** chosen by `schema_version`. That doubles the contract for
     a change that only adds fields.

## Decision
1a, 2a, 3a, 4a and 5a. These are Claude Code's proposals.

**The rule:** the contract says what the machine does; the exporter decides how to simulate it.

### Three new fields on `Joint`
All are optional and default to `None`, which means "not stated", and a joint without them exports
as it does today.

| Field | Model | What it says |
|---|---|---|
| `mode` | `JointMode` | How the joint is moved or held when nothing commands it |
| `adjustable_stop` | `AdjustableStop` | A stop a person sets inside its limits |
| `follows` | `JointLink` | The joint it moves with, and at what ratio |

**The names** (Daniel left them to Claude Code's judgement, 2026-10-23):
- `adjustable_stop` replaces the first draft's `stop`. A joint's limits are stops too, the ends of
  its travel, so "stop" alone does not say which one is meant. "Adjustable" is what sets it apart,
  as the manual's depth stop "can be lowered or raised" (p. 31). And "stop" could be read as a verb.
- `mode` is kept. It is the plan's own word ("joint modes"), and its `kind` says the rest.
  "Holding" does not fit a driven joint, and "actuation" does not fit a locked one.
- `follows` is kept, because it reads as a sentence: `downfeed_handles` follows `quill_travel`.

**`JointMode`:**
- `kind`: "driven", "spring_return", "locked" or "free";
- `position`: a number or `None`, in rad (revolute) or m (prismatic): where a spring returns the
  joint, or where it is locked. `None` means the modelled pose, position 0. Only "spring_return"
  and "locked" take a position;
- `citations`: at least one.

| Kind | Meaning | Example | What the exporter writes (decisions 0017-0018) |
|---|---|---|---|
| driven | A motor or actuator moves it. A control behaviour may say how | The T33901's and the HA5C's spindles | Today's default drive, a hold at 0, which a program or a check replaces |
| spring_return | A spring returns it to `position` when let go | The quill, to the top of its travel | A position drive towards the rest position, aimed 0.03 m past it when it is a limit, as a preload (stiffness 600, damping 49; all stand-ins) |
| locked | Held at `position` until a person changes the setting: a lock handle or a bolt | The table's four motions: the height lock handle holds the height and the turn around the column (p. 7) | Equal limits at the position, no drive, and it starts there |
| free | Moves when pushed; nothing holds it | A table motion with its lock loosened | A drive with damping only (2, a stand-in for friction) |

**`AdjustableStop`:**
- `position`: where the stop is set, within the joint's limits;
- `side`: "lower" or "upper", the end of the travel it shortens;
- `citations`: at least one.

The exporter writes the stop as the limit on that side (decision 0018, 2a). NVIDIA: "Articulation
joints without limits cannot be configured with limits after attaching the stage"
(`docs/research/2026-10-17-usd-physics-for-isaac-sim.md`), so the stop is always written as a
limit from the start.

**`JointLink`:**
- `leader`: the id of the joint it follows;
- `ratio`: the follower's units per leader unit, for example rad per m for the handles. The
  follower's position is `ratio` × the leader's + `offset`, signed by each joint's own axis
  (right-hand rule for a turning joint);
- `offset`: in the follower's units, 0 by default;
- `stand_in`: true when the ratio is not from a source, false by default;
- `citations`: at least one.

The exporter writes the link as a `PhysxMimicJointAPI`, or as a rack and pinion when asked
(decision 0019). Which of the two is an export choice, not a contract field.

### Rules the validator adds
- **Links:**
  - the leader is another joint in the same result;
  - neither the leader nor the follower is fixed;
  - the ratio is not 0;
  - links may chain, but may not loop back to a joint already in the chain. PhysX: "there is no
    restriction on the number of mimic joints referenced by any individual joint"
    (`docs/research/2026-10-23-table-height-lock-and-mimic-chains.md`, section 2). No chain has
    been run in Isaac Sim;
  - a joint that follows has no `mode`, since its leader moves it.
- **Positions:** a `mode.position` only for "spring_return" and "locked". That position (0 when
  not given) and `adjustable_stop.position` lie within the joint's limits, where those are given.
- **Fixed joints** take no `mode`, `adjustable_stop` or `follows`.
- **Stand-ins:** a link with `stand_in` true needs an issue whose `ref` is the follower's id.
- **Citations:** every new citation names one of the result's sources, as today.
- **Versions:** a result that says "0.1.0" uses none of the three fields.

### The version
- `SCHEMA_VERSION` becomes "0.2.0", and new results write it by default.
- `schema_version` accepts "0.1.0" and "0.2.0".
- The JSON Schema (`moonwalkers.contracts.json_schema`) and the dashboard's types
  (`moonwalkers.api.typescript`) are regenerated from the models.

### What stays out of the contract
- **The simulation's numbers:** stiffness, damping, the preload, the drive type, the coupling
  method, starting positions, and each check file's scenario. They stay in `JointSettings`, which
  can still override any joint for a check.
- **Cited physical values,** such as a spring's force or a pinion's teeth: they are `Fact`s, as
  today.
- **Changing a mode while the twin runs,** such as opening a lock or moving the depth stop: that is
  control logic, decision 0025 (plan, Phase 6).
- **Merging results from several pipelines:** decision 0021.
- **Stand-in facts and parts:** they are labelled as Phase 1 labels them, with a `user_input`
  source and an issue.

### Example
The box-and-cylinder drill press's quill, handles and table pivot, in v0.2.0. Only the new fields
and the joints' ids are shown. `src-synthetic` is the test model's `user_input` source.

```json
[
  {
    "joint_id": "quill_travel",
    "mode": {
      "kind": "spring_return",
      "position": 0.0,
      "citations": [{"source_id": "src-t33901-manual", "locator": "PDF p. 7",
                     "quote": "Spindle Return Spring: Automatically returns quill into headstock"}]
    },
    "adjustable_stop": {
      "position": 0.0381,
      "side": "upper",
      "citations": [{"source_id": "src-t33901-manual", "locator": "PDF p. 31",
                     "quote": "a threaded rod attached to the quill with a depth stop nut that can be lowered or raised against a stop bracket"},
                    {"source_id": "src-synthetic", "locator": "depth set for the check: 1-1/2 in"}]
    }
  },
  {
    "joint_id": "downfeed_handles",
    "follows": {
      "leader": "quill_travel",
      "ratio": 57.085,
      "offset": 0.0,
      "stand_in": true,
      "citations": [{"source_id": "src-t33901-manual", "locator": "PDF p. 35",
                     "quote": "Lubricate column rack and quill rack and pinion"},
                    {"source_id": "src-synthetic", "locator": "stand-in: 270 degrees over the 3-1/4 in stroke"}]
    }
  },
  {
    "joint_id": "table_around_center",
    "mode": {
      "kind": "locked",
      "position": 0.7854,
      "citations": [{"source_id": "src-t33901-manual", "locator": "PDF p. 32",
                     "quote": "Table Pivot Lock Handle"},
                    {"source_id": "src-synthetic", "locator": "setting chosen for the check: 45 degrees"}]
    }
  }
]
```

The stand-in link needs the issue the drill press already carries: `{"severity": "warning", "ref":
"downfeed_handles", "message": "Stand-in ratio: the handles turn 270 degrees over the 3-1/4 in
stroke. ..."}`.

## Consequences
- **The stored results load and build as before,** and no file is rewritten. The "0.1.0" fixture
  and stubs stay as they are, so the tests keep proving it. Checked on the real data on
  2026-10-23, read only: all eight stored results load and still say "0.1.0", and the four stored
  twins (HA5C v1-v3, TH240 v1) build their stages.
- **The teammates need change nothing.** Their v0.1.0 results still validate, and they use the new
  fields by writing "0.2.0".
- **Pipeline B writes "0.2.0" without the new fields** until Phase 5, when it builds several
  joints. The HA5C's stage then changes only in its provenance.
- **Two lines of provenance change.** The twin's `contract_schema_version` becomes "0.2.0", and each
  result's own `schema_version` is added beside it, so a twin built from a "0.1.0" result says so.
  The Phase 2 test twin's fixture test is changed to check that only these lines differ, as the
  keep-awake test checks its one difference (decision 0017). It is not loosened. Built on
  2026-10-23: both fixture tests pass for both files (`spin.usda`, `quarter_turn.usda`), and each
  line they replace is checked to occur exactly once.
- **The exporter reads the new fields.** A joint without `JointSettings` gets its drive, limits and
  coupling from its mode, stop and link. `JointSettings` still overrides a joint for a check.
  - The box-and-cylinder drill press is rewritten: the result carries the modes, the stop and the
    link, and each check file adds only its scenario.
  - At a fixed time, its physics matches Phase 1's (plan, Phase 2). Only the provenance gains the
    new fields.
- **A driven prismatic joint gets today's hold,** which sags 0.098 m on a vertical slide (decision
  0017). No twin has one yet; its tuning is decided when one does.
- **A turning follower needs limits for the mimic** ("PhysicsRevoluteJoint (with a limit set)",
  research note, section 4). The contract does not require them. Today the exporter refuses a
  follower without limits. NVIDIA's own demo gives one limits of ±1e10 instead. Which of the two
  the exporter does is settled in the build [INFERENCE: ±1e10 is untried on our stages].
- **There are four kinds.** A fifth, such as a brake or a detent, needs its own version bump.
- **The knowledge graph:** a link is an edge between two joints, and a mode and a stop are a
  joint's properties. So moving to Neo4j stays a mapping (decision 0004) [INFERENCE].
- **The agent's tools learn the fields in Phase 5** (`add_joint`, `docs/agent-procedure.md`), when
  Pipeline B builds several joints (plan).
- **Reversing it:** drop the three fields and "0.2.0". Any result written as "0.2.0" would then
  need migrating.

## Questions for the pipeline owners (Ava, Kiran, Sarkis)
- Can your sources state any of this? For example, a gear ratio on a drawing (C), or "spring
  return" or a lock in a datasheet or catalog (A, D).
- Are the names clear: `mode`, `adjustable_stop`, `follows`?
- Do your machines need a kind that is not listed?
- Is it fine that new results write "0.2.0" while "0.1.0" results stay valid?

## Review (Daniel, 2026-10-23)
"Reading over all you've done it looks good." On the five points raised:
1. **The names:** "look good unless you think they need to be more descriptive", left to Claude
   Code's judgement. `stop` became `adjustable_stop` ("The names", above).
2. **The strict stand-in rule:** kept. "if our goal is accuracy tighter better overall".
3. **The table height as "locked":** researched
   (`docs/research/2026-10-23-table-height-lock-and-mimic-chains.md`, section 1).
   - The manual names the lock handle as what holds the height in use: it "tightens to lock table
     position" (p. 7), and the height is changed by loosening it, cranking, then tightening it
     "to secure" (p. 32). So "locked" now rests on the lock handle, not on the worm.
   - Whether the worm holds the table while the lock is loose is **not confirmed.** The manual
     gives no lead angle. Analyses of self-locking "deal with static conditions", and it can be
     lost under "shock and vibration" (Karvelis, *Machine Design*, 2000). A test on a real T33901
     or Grizzly's answer would settle it.
   - **Daniel's own research:** the forum thread is about a 1950s Craftsman drill press (model
     103.23140) whose similar table fell once a lock was loosened, and Grizzly's site has no
     T33901 page. His direction: assume the T33901 behaves the same "unless otherwise stated
     somewhere". So the drill press's `table_free` check lets the height fall, as a logged
     assumption (decision 0018, update).
4. **Chains of links:** researched (same note, section 2). PhysX allows a joint in any number of
   mimic joints, and nothing in Isaac Sim 6.2.0 refuses a chain. The rule now refuses loops only.
   No chain has been run in Isaac Sim.
5. **The fixture test:** built as proposed. Only the two provenance lines differ (Consequences).
