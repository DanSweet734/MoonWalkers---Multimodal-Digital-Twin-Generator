# 0022 - Several photos per run

- **Status:** proposed (by Claude Code in the drill-press plan's Phase 3, for Daniel's review)
- **Date:** 2026-10-24
- **Decided by:** team (Daniel)
- **Amends:** decision 0011 (the multi-view model now runs whenever a run feeds it two or more
  photos) and decision 0012 (Pipeline B takes several photos; the geometry spec gains a turn about
  the up axis)

## Context
Daniel's direction for the drill press is "multiple image input and ... the least amount of
guessing" (2026-10-22). Today a run takes one photo:
- Pipeline B refuses anything but "exactly one machine photo" (`pipelines/b/pipeline.py`);
- its generator record keys the mesh to that photo's SHA-256, and only the single-image model runs;
- every result says the generator "guessed every surface the photo does not show";
- `request.json` can list several sources, but nothing says which side each photo shows;
- the dashboard uploads one photo, and a job's status names one.

The multi-view model is installed (2026-10-22). It takes up to four images named `front`, `left`,
`back` and `right`, where `left` is the machine's own left (`docs/setup/generators.md`).
Research for this record: `docs/research/2026-10-24-several-photos-and-corner-views.md`.
- **People and manuals name sides the other way round.** Daniel's photo labels are the operator's
  view, facing the front, and so is the manual ("Figure 3. Right headstock components." is the
  handles' side, p. 6). The generator calls that side `left`. Checked against the manual's own
  photos: Daniel's labels are right.
- **The T33901's whole-machine photos are all front corners:** Daniel's two, and the manual's two
  (the same views, in greyscale). The rest are close-ups: the table, the motor plate, the belts,
  under the head, and the manual's figures.
- **Corner photos, tried on 2026-10-24** (four scratch runs, research note section 2):
  - the multi-view model, given the two front corners as a grid turned 45°, put the machine's
    front within 3.5° and 7.7° of where the photos imply. Both sides of the head came out with
    their own features;
  - the single-image model, given one corner, turned the machine square to an axis, about 45° away
    from the photo, and not the same way twice;
  - no mesh was mirrored: the handles and the table crank came out on the operator's right.

## Options considered
1. **How a photo's side is named.**
   - (a) **The camera's position in the operator's words,** with "operator" in every name that has
     a left or right: `front`, `back`, `operator_left`, `operator_right`, the four corners
     (`front_operator_left` ...), and `detail` for a close-up. The adapter translates to the
     generator's names, in one place, as units convert only at the USD boundary.
   - (b) The generator's words (`left` = the machine's own left). They are the reverse of what
     people and manuals say, which is the trap the hand-off had to explain.
   - (c) An angle around the machine. Precise, and corners come free, but its sign is the same
     trap again.
   - (d) File names, as now. Not checked by anything.
2. **Where the views are kept.**
   - (a) **In `request.json`,** next to the sources: a `photos` map from each machine photo's
     source id to its view and use. `JobRequest` is the orchestrator's request, not the pipeline
     contract, so the contract does not change and old requests stay valid.
   - (b) A separate run file, like `geometry_spec.json`. One more file that must agree with the
     request.
   - (c) A `view` field on the contract's `Source`: a contract change (v0.3.0) that the teammates'
     pipelines would carry for Pipeline B's sake. A view is how one job uses a photo, not a
     property of the source.
3. **Which photos feed the generator, and which are evidence.**
   - (a) **Each photo's `use`:** `generator` or `evidence`. A whole-machine view feeds the
     generator unless marked evidence; a `detail` never does. Evidence photos stay in the job, for
     the cuts, joints and size checks of Phases 4-5 and for the reviewer.
   - (b) Feed every photo: the model takes one image per view, and close-ups are not views.
   - (c) Choose in the `generate_geometry` call: the choice would live in a call, not in the run
     folder, so the run could not be repeated from its files.
4. **Which model.**
   - (a) **One fed photo: the single-image model, as in the PoC; two to four: the multi-view
     model.** The HA5C's runs keep their meshes and keys.
   - (b) Always the multi-view model, even for one photo: untried, and it would change every
     one-photo run.
5. **Corner photos.**
   - (a) **Feed corners as a grid turned 45°,** record the expected turn, and let the geometry
     spec turn the mesh back. Measured to work (above).
   - (b) Refuse corners, or take one corner on the single-image model: it loses the second side,
     and the single-image model's turn is not predictable.
   - (c) Mix corners and sides in one generation: they are 45° apart, and the model's four slots
     are 90° apart.
6. **What no photo shows.**
   - (a) **Pipeline B works it out from the fed views** and says so in the result (an issue), in
     `RUN.md` and in the generator record: which sides were seen square on, which only at an
     angle from a corner, and which the generator guessed.
   - (b) A fixed sentence, as now: wrong as soon as there is more than one photo.

## Decision
1a, 2a, 3a, 4a, 5a and 6a. These are Claude Code's proposals.

### Views and uses
| View | Where the camera stands (facing the machine's front is the operator's view) | Generator slot, sides grid | Generator slot, corners grid |
|---|---|---|---|
| `front` | in front | `front` | - |
| `operator_right` | at the operator's right: the machine's own left | `left` | - |
| `back` | behind | `back` | - |
| `operator_left` | at the operator's left: the machine's own right | `right` | - |
| `front_operator_left` | the front corner on the operator's left | - | `front` |
| `front_operator_right` | the front corner on the operator's right | - | `left` |
| `back_operator_right` | the back corner on the operator's right | - | `back` |
| `back_operator_left` | the back corner on the operator's left | - | `right` |
| `detail` | a close-up or part of the machine | never fed | never fed |

- **The corners grid's front is the front corner on the operator's left.** That is a fixed rule
  so a run can be repeated; E3 used it [INFERENCE: two runs do not show it is better].
- **The expected turn** of the machine's front, after orienting (+Z up, the generator's front as
  +X): 0° for sides, +45° (towards the generator's `left`) for corners. It is recorded, not
  assumed: the agent measures the turn and writes it in the spec.
- **Use:** `generator` (the default for a whole-machine view) or `evidence` (the only use for
  `detail`).
- **Daniel's file names may change to these views** (he allowed it on 2026-10-24):
  `front_left.jpeg` becomes `front_operator_left.jpeg`, and `front_right.png` becomes
  `front_operator_right.png`. Same bytes; `SOURCES.md` keeps the old name in its note. Done after
  this record is accepted.

### The rules a run's photos must meet
Checked by `add_input` as each photo is added, and again by Pipeline B, with a message that
says what to change:
- every key of `photos` is a machine photo among the request's sources;
- the fed photos (use `generator`) have whole-machine views, at most one photo per view, all
  sides or all corners;
- one fed photo runs the single-image model, two to four the multi-view model;
- **a request with one machine photo and no `photos` entry is the PoC's,** and builds as before:
  the photo feeds the single-image model, with the same generator key. Two or more machine photos
  each need a view.

### Pipeline B and the run folder
- **The generator record** (`generator/run.json`) keys the mesh to every fed photo's SHA-256 by
  generator slot, plus the generator's settings. A one-photo run keeps the PoC's key
  (`photo_sha256`), so the HA5C's and TH240's run folders still reuse their meshes. The record
  also holds each slot's source id and view, the grid, and the expected turn.
- **The adapter** carries both models' settings and runs the one the fed photos need. Its
  fingerprint is that model's, as before.
- **The geometry spec** gains `yaw_deg` (default 0): a turn about the up axis after `up` and
  `front`, so a corners grid, or a single-image mesh that came out turned, can be squared. The
  inspection tools take the same turn, and report how far the base's footprint is turned from the
  axes, to measure it. Old specs are unchanged.
- **The result** (contract unchanged):
  - its sources hold every machine photo of the request, fed or evidence;
  - each part cites every fed photo, and the generator's `params` record which photo filled which
    slot;
  - an issue lists the sides seen square on, those seen only at an angle from a corner, and those
    guessed. No view is from above or below, so the top and the underside are at most seen at a
    glancing angle;
  - another lists the evidence photos, which the generator did not see.
- **`RUN.md`** gets a photos table: source, file, view, use and slot.

### The agent and the dashboard
- **`add_input`** takes `view` and `use` for a machine photo. Documents stay refused while their
  pipeline is not in (decision 0021). The procedure (`docs/agent-procedure.md`) says how to read a
  view from a photo, and that a nameplate or a motor plate is a reference source, not a job input.
- **The dashboard's upload** (last in this phase) takes several photos. For each it asks where the
  person stood, in the operator's words with a small sketch, its use, and its origin. One photo
  with no view still works.
- **A job's status** lists its photos, with their views.

## Consequences
- **Several photos reach the generator,** and the twin says which ones, how each was used, and
  which sides are still guesses. That is the evidence the "least guessing" direction asks for.
- **Nobody translates left and right by hand.** People write the operator's view, which is what
  they and the manuals say; the adapter alone speaks the generator's words.
- **The HA5C and TH240 runs are unaffected:** same requests, same keys, same meshes, same specs.
- **The contract does not change,** so the teammates' pipelines are untouched. The views live in
  the request, which only the orchestrator, Pipeline B and the workspace read.
- **Corner grids need a measured turn** before a twin can be built. Until a back or side photo
  exists, the T33901's back is a guess, and its twin says so.
- **The multi-view model's corner behaviour rests on two runs** on one machine. Another machine,
  or photos that are not 90° apart, may come out differently; the measured turn will show it.
- **Reversing it:** drop the `photos` map and the view rules; one-photo runs never used them.
