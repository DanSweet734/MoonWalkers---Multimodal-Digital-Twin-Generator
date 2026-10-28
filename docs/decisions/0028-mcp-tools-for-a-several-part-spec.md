# 0028 - MCP tools for a several-part spec: set piece by piece, built only while valid

- **Status:** proposed (by Claude Code in the drill-press plan's Phase 5, 2026-10-28), for
  Daniel's review with the phase.
- **Date:** 2026-10-28
- **Decided by:** team (Daniel)
- **Amends:** decision 0013 (the MCP server: one tool per platform action, state in the run folder)

## Context
Decision 0027 gave Pipeline B a geometry spec of several parts and joints (`PartsSpec`). The
T33901's was written by a scratch script (`compose_spec.py`), not by the agent. The plan's Phase 5
asks that `add_joint` and `inspect_geometry` stop assuming one spindle about +x, that new tools be
added where needed, that old runs keep working, and that `docs/agent-procedure.md` say how
(Phase 7 has a fresh agent build the T33901 through the tools).

What the tools did before:
- `add_joint` and `set_scale` wrote decision 0012's two spec parts into
  `geometry_spec.parts.json`; `geometry_spec.json` was written once both were there.
- `preview_twin` previewed only that kind; `inspect_geometry` fits circles across x only.
- Building v1 to v4 took measurements the tools could not make: circle fits along z and y, and
  the open edges a removed part leaves (`part_loops.py` and others in the session's scratch
  folder).

## Options considered
1. **How the agent writes a several-part spec.**
   - (a) **Piece by piece:** the frame, the cut list, each part, each joint, the scale length,
     the size checks, each set or replaced on its own. Each piece is checked by its own model
     when set; the whole spec once the required pieces are there. Small calls, and a change to
     one part is one call.
   - (b) One tool taking the whole `PartsSpec`. One model and one check, but the T33901's is
     about 30 KB of JSON, sent again for every change, and one mistake refuses all of it.
   - (c) Change `add_joint` to take either kind. One name, but two unrelated sets of arguments.
2. **When the spec is incomplete or broken by a change** (a part removed that a joint names).
   - (a) **`geometry_spec.json` exists only while the pieces make a valid spec;** the pieces stay,
     and the status says what is missing or wrong. A stale spec can never be built.
   - (b) Refuse any change that leaves the spec invalid. The pieces then have to be set in an
     order that is valid at every step (parts before joints, removed parts before the stand-ins
     that replace them), which the agent would have to know.
3. **What the agent needs to measure.**
   - (a) **`fit_circles` along x, y or z** (the CLI's `inspect --circles-along`), and **holes in
     the preview:** each cut part's open edge loops across a removed part, with its centre (a
     patch's `near`), size and what is on the other side.
   - (b) A general measuring tool (faces in a box, percentiles). More than the T33901 needed, and
     its answers are harder to read.
4. **One preview tool or two.** (a) **`preview_twin` for both kinds,** returning one report or
   the other; (b) a second tool. One tool is less for the agent to know; the cost is that its
   structured result is wrapped as `{"result": ...}` (the MCP SDK's way with a union).

## Decision
1a, 2a, 3a and 4a: Claude Code's proposals.
- **The draft:** `geometry_spec.parts.json` holds one kind. A spindle's `joint` and `scale`; or a
  several-part spec's `frame`, `scale_length`, `cuts`, `parts` and `joints` (by id) and
  `size_checks` (`workspace.runs`, `set_parts_piece`, `remove_parts_entry`). Required: frame,
  scale length, cut list and at least one part. Mixing kinds is refused: a new run switches.
- **The tools** (`moonwalkers.mcp.server`):

  | Tool | Sets |
  |---|---|
  | `set_spec_frame` | up, front, yaw_deg, origin_xy, base_z, fixed_part, decided_by, method |
  | `set_cut_list` | the ordered cut list (decision 0023), replaced whole |
  | `set_spec_part` | one part, added or replaced by id: cut (with `patches`), removed, or stand-in |
  | `set_spec_joint` | one joint, added or replaced by id |
  | `remove_spec_entry` | takes a part or a joint out, by id |
  | `set_scale_length` | the cited length (a recorded fact in m) and its measurement; the overall sizes are measured by the pipeline |
  | `set_size_checks` | the other cited lengths, each a recorded fact in m |
  | `fit_circles` | read-only: circle fits in slices across x, y or z |

  `preview_twin` previews either kind; for several parts it returns the parts, the joints, the
  size checks, the issues, the views and the holes, and with `photos=true` the overlays.
  `submit_twin` builds either. `add_joint` and `set_scale` are unchanged, and the HA5C's runs
  still build.
- **The job status** (dashboard and `list_jobs`): the spec step reads "Parts and joints set" for
  this kind, with the counts or what is missing; the preview step also counts
  `preview_parts/parts.png`.
- **The holes** come from `parts_spec.open_loops`, the same loops the patches close, so a hole's
  centre is a `near` the patch accepts (the scratch lister walked loops differently and once
  gave a centre the patch refused).

## Consequences
- **An agent can now build the T33901 through the tools** (Phase 7), with the procedure's new
  section 5b. The tests build the Phase 1 drill press that way: the quick test sets the spec
  piece by piece; the slow one (about 90 s) previews it, patches the holes the preview finds,
  previews again and submits.
- **The tool list grows from 16 to 24.** Each new tool takes one piece, so its arguments stay
  small; `set_spec_part`'s schema is the largest, since a stand-in's shape is in it.
- **`preview_twin`'s structured result moved under `result`** for both kinds. The text the agent
  reads is the same JSON with one more level.
- **What the tools still cannot do:** a dry run of the build in a scratch data folder, which
  caught v2's warning after the fact (worklog 2026-10-27). The procedure asks the agent to run
  NVIDIA's validator after submitting; a twin with a warning is followed by a new version.
- **Reversing it:** the seven tools, `fit_circles`, and the several-part branches of the draft,
  the status and `preview_twin`; decision 0012's tools never used them.
