# 0023 - Several moving parts from one mesh

- **Status:** accepted (by Daniel, 2026-10-26, review of PR #20: "For decision 0023 I agree with
  the methodology and I am willing to accept as proposed."). Proposed by Claude Code in the
  drill-press plan's Phase 4. His answers to the open questions are at the end.
- **Date:** 2026-10-24
- **Decided by:** team (Daniel)
- **Amends:** decision 0012 (the geometry spec's one spindle cylinder becomes a cut list of any
  number of parts)

## Context
The T33901's twin needs seven moving parts cut from its one generated mesh, where decision 0012
cut one spindle with one cylinder (PoC report, section 8, item 1). The mesh is run
`grizzly-t33901/runs/2026-10-24_run-001`: 40,000 faces, one closed piece, made from the two front
corner photos, with the back guessed (decision 0022). The plan's Phase 4 is a time-boxed spike
comparing four methods on two test meshes, with five measures. Daniel's directions: the least
guessing; no moving part cut from the back, which the generator guessed; stand-ins only where
visible or needed.

The spike, its numbers and its sources: `docs/research/2026-10-24-part-cutting-spike.md`. Code:
`moonwalkers.pipelines.b.part_spike` (the runner), `part_cuts` (a), `mesh_segments` (b),
`photo_marks` (d) and `synthetic_parts` (the test mesh).

## Options considered
1. **(a) An ordered cut list.** Each part has one or more shapes (cylinder, box, half-space) in the
   squared mesh's frame, and the first part whose shape holds a face's centre takes it; the rest
   is the fixed part.
   - On the synthetic drill press, fused into one surface as a generator does: **0.995 of the
     area in the right part; 0.996 with rounded edges.** That is a ceiling: the cuts were written
     from the test model's own sizes.
   - On the T33901: **8 parts, each moving part one piece** except where the mesh itself joins
     them wrongly. It took **five passes**, each after looking at coloured views of the result.
   - No install. Milliseconds to apply. Every shape carries a note saying what it is drawn
     around and from which figure or measurement, so it can be cited and reviewed.
   - Costs: a person or the agent must measure and write the shapes, and look at the result;
     and cuts follow the generator's faces, so seams are jagged and open.
2. **(b) The mesh's own shape:** separate pieces, or regions between sharp edges.
   - **The T33901's mesh is one piece,** as a generated mesh is expected to be. Separate pieces
     find nothing.
   - **Sharp edges do not follow its parts.** At 20° it gives 36 regions: the column, the
     bracket, the arm and the crank are one, and the table's top is split from its own rim. At
     30° there are 5 regions, at 45° one.
   - On the rounded synthetic mesh, even naming each region after its main part (the best a
     reviewer could do) gives 0.923 at 30°, with the quill, spindle and rack lost.
   - No install. The segments are unnamed, so someone must still name them.
3. **(c) A learned part segmenter.** Researched only: Daniel chose not to install one in this
   phase (2026-10-24). The best candidates found:
   - **P3-SAM** (Tencent's Hunyuan3D-Part): made for "any input mesh". Its licence does not apply
     in the EU, UK or South Korea, and its outputs may not be used to improve other models.
     Weights 451 MB; Python 3.10 and CUDA 12.1, plus a compiled extension.
   - **PartField** (NVIDIA): "for non-commercial research and educational purposes only".
   - Both return unnamed segments. Neither names industrial machines among its test domains.
4. **(d) Parts marked on the photos, carried onto the mesh** through a camera fitted to each
   photo.
   - **With perfect marks** (rendered from the true parts), from the two front corners the
     T33901 has: **0.947** of the rounded synthetic mesh's area right. A raised corner camera
     cannot see the quill under the head or the arm under the table, so they get their
     neighbours' parts. Four corners give 0.976.
   - **On the real photos:** a camera fitted by silhouette overlaps each of the two fed photos
     with an IoU of about 0.80, a few percent of the image off. That is too coarse to carry
     marks onto 12 mm handles, but enough to draw the cut parts over each photo for a reviewer.
   - Real marks need a person drawing them (a dashboard tool) or a segmenter on the photos (an
     install).

## Decision
**(a) cuts the parts; (d)'s camera fit draws them over the photos for review.**
- **The geometry spec gains a cut list** (Phase 5): an ordered list of parts, each with shapes
  and a note naming its evidence, and the fixed part's name. The shapes are `part_cuts`'
  cylinder, box and half-space, in the spec's model units after `up`, `front` and `yaw_deg`.
  Decision 0012's spindle fields stay valid for old specs; a spec has one or the other.
- **The inspection shows what a cut did,** so the agent or a person can judge it before a build:
  - the coloured views of every part (`part_spike.render_parts`);
  - per part: faces, pieces and stray faces (`part_cuts.seams`);
  - each fed photo with the cut parts drawn over it (`photo_marks.fit_camera`,
    `part_spike.photo_overlay`);
  - circle fits along any axis, not only +X (the column and the quill are vertical).
- **A cut is ready when** every moving part is one piece, or its note explains why not (the
  T33901's up handle is fused to the head's wall), and the overlays have been looked at.
- **(b) is not used to cut.** It may later offer the handles, which it does separate, as a hint.
- **(c) waits.** If (a) proves too slow on later machines, P3-SAM is the first to try, in its
  own environment, on Daniel's approval (CLAUDE.md rule 3).
- **(d)'s marks wait** for a way to draw them (a person in the dashboard, or a model on the
  photos), and a better camera (perspective).

## Consequences
- **Every cut is cited and reviewable,** as decision 0012's spindle was. Nothing is installed.
- **Cutting a machine takes a person's or the agent's judgement over several passes.** On the
  T33901: five passes, each with a look at the views. The spike's measurements (circle fits
  across z, slices, the handles' lines) become inspection tools in Phase 5.
- **The generator's mistakes carry into the parts,** and no cut can fix them. On the T33901:
  - the chuck guard is clear plastic, but solid in the mesh, so the chuck inside is hidden and
    only its nose can turn;
  - the column rack is a bump of at most 2.5 mm, so it stays with the column, and only its
    collar turns around the column;
  - the depth stop's nut and its bracket are one ring, which stays with the head;
  - one handle's root is fused to the head's wall, so turning the handles will open a hole
    there;
  - the table crank's handle points back, into the guessed side; the photos show it pointing
    forward.

  Each is logged as an inaccuracy. Under Daniel's rule (a labelled stand-in where the detail is
  visible or needed), the chuck and the rack are candidates for stand-ins in Phase 5. After his
  review, so are the table and the crank (below).
- **Seams stay open,** as with decision 0012's spindle. They show when a part moves.
- **Reversing it:** the cut list is a spec field and three modules; dropping it returns to
  decision 0012's single spindle.

## Daniel's answers (2026-10-26, review of PR #20)
- **The chuck:** "If the chuck needs a stand in then yes that sounds like a plan." It does: the
  generator made its clear guard solid, so a labelled stand-in chuck goes inside the guard in
  Phase 5.
- **The depth stop's ring:** "the depth stop ring can stay in the head for now." As cut: the
  bracket is right, the nut does not ride on the rod. Logged.
- **The crank and the table:** "The crank according to the photos looks all wrong, maybe I have
  the wrong impression but it doesn't even look like one piece. The table too, it's supposed to
  be symmetrical. We should definitely match it to the photos."
  - Checked the same day (research note, section 8). In the mesh the crank is joined to the
    bracket, but its shape is wrong: its arm curves down and back to a round knob, where Fig. 36
    shows a flat S-shaped arm with the handle pointing out, down and to the front.
  - The table's top is 0.586 by 0.614 model units, a skewed four-sided shape, centred 0.055 off
    the spindle. The manual gives a square "11-1/4 in." by "11-1/4 in." (p. 9). The photos show it
    square with rounded corners (`table_top.png`, Fig. 36).
  - So both get labelled stand-ins matched to the photos in Phase 5: Daniel's rule for unknown
    details, extended to details the generator got wrong. The table takes its cited sizes; the
    crank has none cited.
- **The back:** "I can't find anything of the back and we don't have a T33901 to take one
  ourselves unfortuntately." It stays guessed, and is logged as such.
- **The column rack** was not answered. It is visible in Figs. 36, 37 and 48, so under Daniel's
  rule it gets a labelled stand-in too, unless he says otherwise (asked on 2026-10-26).
