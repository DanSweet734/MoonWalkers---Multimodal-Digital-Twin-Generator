# 0029 - Cutting the machine out of each photo

- **Status:** accepted (by Daniel, 2026-11-09: "I accept Decision 0029 as proposed"). The
  method is Daniel's choice (2026-11-09: "I think having a automatic way
  with SAM is the best, however it would also be nice to afford the option to draw by hand or by
  crop boxes ... Regardless prioritize B for now"). How it is stored and checked is proposed by
  Claude Code in the lab's machines plan, Phase 1.
- **Date:** 2026-11-09
- **Decided by:** team (Daniel)
- **Amends:** decision 0022 (a photo's entry in `request.json` gains an optional `cutout`) and
  decision 0011 (the generator job no longer always removes backgrounds automatically)

## Context
Before it generates, the generator job cuts the machine out of each photo with rembg's u2net,
which keeps the photo's most salient object. The drill press's photos were catalogue and manual
pictures on plain backgrounds, so this never mattered. The lab's photos are different
(`docs/research/2026-11-09-background-removal-spike.md`):
- u2net failed on all seven TM-1 photos: it kept a sign in front of the machine, one guard, or
  almost nothing;
- it was partial on the VF-3 and the arm: it kept a monitor, an e-stop, a foam box, or lost the
  hand.

Box-prompted SAM, already in the installed rembg 2.0.68, kept the machine on the photos where
u2net kept the wrong object. Its quantised weights (about 118 MB, Apache-2.0) were downloaded on
Daniel's choice. Nothing new was installed. Daniel also asked for crop boxes and masks drawn by
hand as options.

## Options considered
1. **Where a photo's cut-out is kept.**
   - (a) **In `request.json`, on the photo's entry** beside its view and use (decision 0022).
     A run stays repeatable from its request, and the agent's tools and the dashboard already
     write there.
   - (b) Cut-out PNGs made by a separate step and fed to the generator as the photos. The
     generator's record would then hold a derived file, not the photo the job cites, and two
     files would have to agree.
2. **The methods.**
   - (a) **`sam`, `crop` and `mask` together, with no cut-out meaning automatic.**
     - `sam`: a box and points to keep or leave out a region;
     - `crop`: u2net inside a box;
     - `mask`: a PNG a person drew.
     All three end as one mask on the photo, so specks are dropped the same way, and one preview
     shows them all.
   - (b) SAM alone now, the others later. They are a few lines each in the same place, and the
     crop gives a baseline to compare SAM against.
3. **Coordinates.**
   - (a) **Fractions (0 to 1) of the photo turned upright** by its EXIF orientation, from the top
     left. They hold at any resolution, and the upright photo is what people see.
   - (b) Pixels. They depend on the file's stored orientation, which is sideways for 19 of the
     29 lab photos.
4. **Checking a cut-out before generating.**
   - (a) **A preview that runs only the job's first step** (`cutout_only`): each photo cut out,
     and a sheet with its box and points drawn, in seconds and without loading the 3D model. It
     runs in the same job script as generation, so what it shows is what the generator gets.
   - (b) Generating and looking at the result: a minute of GPU time per try, and the mesh hides
     what went wrong in the photo.

## Decision
1(a), 2(a), 3(a) and 4(a):
- **The setting.** An optional `cutout` on a photo's entry (`orchestrator.photos.Cutout`):
  `method` (`sam`, `crop` or `mask`), `box`, `points` (`x`, `y`, `keep`), `mask` (a PNG path in
  the data folder), and `min_piece`. Separate pieces smaller than `min_piece` times the largest
  are dropped; the default is 0.02, and 0 keeps every piece.
- **Saving.** A photo without a cut-out is saved exactly as before.
- **The job.** The generator job (`hunyuan3d_shape_job.py`) applies the cut-out to the photo
  turned upright. Without one, the job behaves as before: u2net, unless the photo has its own
  transparency.
- **SAM's input.** SAM gets the photo shrunk to its input size (1024 x 684) by Pillow's LANCZOS
  first, and its mask is scaled back up. rembg shrinks with `cv2.warpAffine` and `INTER_LINEAR`,
  which does not antialias. On full-size phone photos that kept the wall behind the TM-1 (the
  research note's second update).
- **Reuse.** A cut-out joins the generator's reuse key only when a fed photo has one, so earlier
  run folders still match:
  - with each mask's SHA-256 in place of its path;
  - with SAM's weights named (`sam_vit_b_01ec64 (quantised, rembg 2.0.68)`).
  Another box, point or mask is another mesh: the run folder refuses it, as for other photos.
- **The record.** The generator record lists each fed photo's cut-out.
- **The preview.**
  - `python -m moonwalkers.pipelines.b cutouts <run>` and the MCP tool `preview_cutouts` write
    `<run>/cutouts/` (the prepared PNGs and `sheet.png`). They show the fed photos, and the
    evidence photos given a cut-out.
  - The preview is overwritten on each run, like `inspect`. A run's outputs stay untouched.
- **Correcting a photo (tool gap 1 of the lab's plan).** `Workspace.set_photo` and the MCP tool
  `set_photo` correct a photo's view, use or cut-out before generation, checking the run's
  photos as a whole, as `add_input` does.

## Consequences
- **Easier:**
  - the lab's machines can be fed with what stands in front of them left out;
  - a person or the agent can try a box in seconds;
  - the whole cut-out is in the run's record.
- **Harder:**
  - someone has to pick a box and points per fed photo, by eye, until the dashboard lets a
    person click them (planned later);
  - SAM leaves holes in shiny sheet metal (the TM-1's guards in the trial), which only a drawn
    mask fills;
  - nothing can fill in what an object in front hides (the VF-3's monitor).
- **Not changed:**
  - the pipeline contract;
  - the generator's settings and fingerprint;
  - the API, the dashboard and their types (`JobPhoto` shows view and use only).
- **To reverse it:** drop the `cutout` field. Runs without one never used it.
