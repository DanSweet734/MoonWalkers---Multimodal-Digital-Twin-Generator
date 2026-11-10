# 0030 - The tools the drill press's agent lacked: correct, measure, check and try before storing

- **Status:** accepted (by Daniel, 2026-11-09: "Yes I accept decison 0030"). Proposed by
  Claude Code in the lab's machines plan, Phase 1, with the phase's pull request (#28).
- **Date:** 2026-11-09
- **Decided by:** team (Daniel)
- **Amends:** decision 0028 (the MCP tools for a several-part spec). Decision 0029 covers tool gap
  1 (`set_photo` and the cut-outs) and is not repeated here.

## Context
The fresh agent that built `grizzly/t33901@v9` through the MCP tools (drill-press plan, Phase 7)
found seven gaps, listed in `docs/drill-press-report.md`, section 7.3. Two of them, items 2 and 6,
were added to this phase on Daniel's word (2026-11-09; `docs/lab-machines-plan.md`, Phase 1). Item
3 is not in this phase. This record covers items 2, 4, 5, 6 and 7:

- **Item 2, issues:** the agent could only add issues. It corrected one of its own by hand in
  `reference_facts.json`, and v10 and v11 carry a stale one: its note of "a thin flap ... on the
  arm's end collar's +y side", which v10's cuts had removed (worklog 2026-11-04).
- **Item 4, circle fits:** `fit_circles` fitted whole slices across x, y or z. The ReBeL arm's
  links lie at angles (Phase 2), so a slice would cross several of them.
- **Item 5, mesh warnings:** `preview_twin` did not report zero-area faces or non-manifold points.
  Only the build and NVIDIA's validator did. That cost the agent two dry runs, and v10 and v11
  one each.
- **Item 6, the upload:** the dashboard's file picker reached one folder per upload, and its
  duplicate check looked only in `inputs/photos/` itself. So the agent's job had five photos,
  where v8 had 24.
- **Item 7, trying a build:** no tool built a run in a scratch data folder. A real build stores a
  version for good (v2's lesson), so every T33901 build after v8 was first tried by hand.

## Options considered
1. **Correcting an issue (item 2).** Issues have no id in the contract (`Issue`: severity,
   message, ref).
   - (a) **Add an id to `Issue`:** stable references, but a contract change. That needs a
     decision record, a version bump and the pipeline owners' review (rule 6) for a tool that
     only touches the agent's draft notes.
   - (b) **By its place in the notes:** the summary every notes tool returns lists the issues
     with numbers from 1, and `correct_issue(run, number, ...)` changes or withdraws one. A
     withdrawal renumbers the ones after it, which the summary shows at once.
   - (c) **Replace the whole list:** one call, but the agent must resend every issue to change
     one.
2. **Measuring a part at an angle (item 4).**
   - (a) **A box only (`within`):** it keeps one link's surface. A slice across an axis still
     cuts a slanted round link in an ellipse, though: the test's rod tilted 30 degrees, of
     radius 0.050, measured 0.054 across z.
   - (b) **A box and a direction:** `along` can also be a direction, `[dx, dy, dz]`. The same rod
     measured 0.050 across its own direction. Along an axis, the fits are field-for-field the
     old ones (checked on the T33901 mesh).
3. **Finding mesh faults in the preview (item 5).**
   - (a) **Run NVIDIA's validator in the preview:** exact, but it needs a USD file per part.
     NVIDIA's validator is a development dependency only, and slow: most of a 3.5-minute dry run
     went to the 120,000-face table.
   - (b) **Our own check, with NVIDIA's definitions** (`mesh_tools.mesh_faults`, numpy;
     omniverse-asset-validator 1.18.0's source read for each one). Fast and always there; a risk
     of drift from NVIDIA's code. It gave the same counts as NVIDIA's `check_manifold_elements`
     on 29 meshes, and found v9's 40 zero-area faces again (worklog 2026-11-09).
4. **Trying a build (item 7).**
   - (a) **Copy the whole data folder:** simple, but the arm's `inputs/` alone is 139 MB, and it
     grows with every machine.
   - (b) **Copy only what the build reads:** the run folder without its previews, `kb/`, the files
     the request and the notes cite, and the cut-out masks. The copied request gets a `-dry-run`
     job id, the copy is built as `submit_twin` would build it, and both validators run on every
     USD file. The scratch folder is kept, so its files can be opened.
   - (c) **Build in memory with a throwaway knowledge base:** no copy, but the build writes run
     files, so the real run folder would change.
5. **Photos from several folders (item 6).**
   - (a) **Picks that add up:** each pick adds to the photos chosen, a repeat is named and left
     out, and each photo can be removed. It uses only the standard file input.
   - (b) **A folder picker (`webkitdirectory`):** one pick per folder, but it takes every file in
     the folder (documents, figures), and it is a non-standard attribute.
   - **In both cases** the duplicate check looks in every folder under `inputs/photos/`. A photo
     filed there is used where it is, not copied again.

## Decision
- **Item 2:** 1(b), `correct_issue`, refused once the twin is built. A built twin's issues are
  part of its record for good, so v10 and v11 stay as they are.
- **Item 4:** 2(b), `within` and `along` as an axis or a direction, in the MCP tool and the CLI
  (`--within`, `--circles-along DX,DY,DZ`).
- **Item 5:** 3(b), each faulty part as a warning in `preview_twin`, with its points in model
  units.
- **Item 7:** 4(b), `dry_run_twin` and `pipelines.b dry-run`. The procedure asks for a clean dry
  run before `submit_twin`.
- **Item 6:** 5(a), in the dashboard, with the wider duplicate check in `save_photo`.

The MCP server has 28 tools.

## Consequences
- **What it makes easier:** a fresh agent can do without the hand edits and scratch scripts of
  the T33901 build:
  - correct its own issues;
  - measure one link of an arm;
  - see the validator's mesh warnings while editing the spec;
  - try the build before storing it.

  A person can upload all of a machine's photos in one job.
- **What it costs:**
  - **The issue numbers move** when one is withdrawn, so an agent must read the returned summary
    before correcting another.
  - **`mesh_faults` copies NVIDIA's definitions.** A new version of the validator may count
    differently. Its tests name the version, and the dry run still runs NVIDIA's own validator
    before a submit.
  - **A dry run takes minutes,** most of them NVIDIA's validator on large parts, and leaves a
    scratch folder each time (gitignored, to be cleaned by hand).
  - **The picks tell files apart by name, size and time:** the browser gives no path. Two
    different files alike in all three would count as one. The server's own check, by SHA-256,
    still refuses the same photo twice.
- **To reverse it:** the tools are additions. Removing one changes no stored twin. The duplicate
  check could look in `photos/` itself again without changing any saved file.
