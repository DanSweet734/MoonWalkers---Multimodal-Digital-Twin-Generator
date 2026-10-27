# Cutting one generated mesh into moving parts: the Phase 4 spike

**Date:** 2026-10-24 (drill-press plan, Phase 4). **For:** decision 0023.
**Question:** how should Pipeline B cut the T33901's generated mesh into its moving parts with
the least guessing? Four methods are compared on two test meshes, against the plan's five
measures:
- the share of faces put in the right part;
- open edges and seams;
- time;
- installs and licences;
- whether the result can be cited and reviewed.

Everything here can be repeated from `backend/` with:

    uv run python -m moonwalkers.pipelines.b.part_spike ../data/machines/grizzly-t33901/part_cutting/2026-10-24_spike --t33901 ../data/machines/grizzly-t33901/runs/2026-10-24_run-001

It took 4 min 35 s on Daniel's machine (the RTX 4090 is not used). The output folder holds
`report.md`, `results.json` and the coloured views named below. `data/` is not in git, so the
numbers are repeated here.

## 1. The test meshes
### The synthetic drill press (`moonwalkers.pipelines.b.synthetic_parts`)
The Phase 1 box-and-cylinder drill press (`moonwalkers.usd.primitive_drill_press`) has eight
parts: frame, quill, spindle, handle hub, column rack, table bracket, table arm and table. It
becomes one mesh in three ways, and every face knows its part:

| Build | How | Faces | Time |
|---|---|---|---|
| separate | each part's closed primitives side by side, as the exporter meshes them | 1,112 | 0.0 s |
| fused | one surface around the union of the parts, on a 4 mm grid, as a generator extracts its surface from a grid. Each face takes the part whose surface is nearest | 182,652 | 28 s |
| rounded | the same, with edges rounded and the creases where parts meet filled (6 mm) | 181,632 | 31 s |

- **Why three builds.** The plan names only the first, "the easy case [INFERENCE: a generated mesh
  fuses its parts into one surface; this one does not]". On it, "separate pieces" are the parts,
  so every method that looks at the mesh's own shape scores 1.000 (section 3). The fused build
  makes touching parts one surface, as the T33901's mesh is. Its creases are sharp, though, which
  flatters methods that cut at sharp edges, so the rounded build softens them.
  [INFERENCE: the 6 mm radius was chosen by eye. Sharpness is hard to compare across meshes with
  different face counts. The rounded mesh has 1,265 of its 272,448 edges sharper than 45° (0.5%),
  the T33901's 921 of 60,000 (1.5%). Its faces are larger, so each edge turns more.]
- **How the fused surface is made.** Naive surface nets: one vertex per grid cell the surface
  crosses, at the mean of the crossings on the cell's edges, and one quad per crossed grid edge.
  It is the simplest form of S. F. F. Gibson's SurfaceNets ("Constrained Elastic SurfaceNets:
  generating smooth surfaces from binary segmented data", MICCAI'98, pp. 888-898; MERL TR99-24,
  https://www.merl.com/publications/TR99-24, accessed 2026-10-24), without the paper's
  relaxation. The parts' signed distances are exact (boxes and round cylinders).
  - The rounding joins the pieces with the quadratic polynomial smooth minimum,
    min(a, b) - h² k / 4 with h = max(k - |a - b|, 0) / k. Source: I. Quilez's article on smooth
    minimums, https://iquilezles.org/articles/smin (found on 2026-10-24; its page did not come
    through the fetch tool, so the formula is as written in our code, not quoted).
  - At 4 mm both fused meshes are closed, with consistent winding (a slow test checks it). At
    12 mm they are not: one vertex per cell cannot close the 12 mm handles.
- **Scores.** A labelling is scored by the share of the surface area in the right part, with the
  share of faces in brackets. Methods that return unnamed segments are scored after naming each
  segment after the part holding most of its area: the best naming a reviewer could give.

### The T33901's generated mesh
Run `grizzly-t33901/runs/2026-10-24_run-001` (decision 0022; research note of 2026-10-24,
section 4), squared as the hand-off says: `--up +y --front +z --yaw 49.1`. Then +X is the
machine's front, +Y its own left (the operator's right, the handles' side), +Z up. It has
40,000 faces and is closed, in **one piece**. The manual's figures are the evidence:
`data/machines/grizzly-t33901/inputs/photos/manual/`, listed in `inputs/SOURCES.md`.

## 2. The methods as tried
- **(a) An ordered cut list** (`part_cuts`). Each part has one or more shapes: a cylinder (an
  axis, a radius, and a start and end along it), an axis-aligned box, or a half-space. A face goes
  to the first part with a shape that holds its centre, and the rest stays in the fixed part. A
  part may come twice: the frame first, to keep the column's surface out of a later part's
  shape. Cuts follow the mesh's faces, as decision 0012's spindle cut does, so no face is split.
  - **Synthetic cut list:** written from the test model's own sizes with ordinary margins, so its
    score is the method's ceiling when the inspector reads the geometry right.
  - **T33901 cut list:** written from measurements on the mesh and the manual's figures (section
    4).
- **(b) The mesh's own shape** (`mesh_segments`). Its separate pieces, and regions between edges
  sharper than 20°, 30° and 45°, with regions under 0.2% of the faces merged into the neighbour
  they share most edge length with.
  - **Not tried:** thin necks. Measuring them needs ray casting, and trimesh's ray casting needs
    `rtree` or `embree` to run at this size [INFERENCE: from trimesh's ray module]. Neither is
    installed.
  - The backend has numpy and trimesh but no scipy or networkx, so pieces are found with a small
    union-find in numpy (`mesh_tools.face_groups`).
- **(c) A learned segmenter.** Researched only (section 5). Daniel chose "Research only" on
  2026-10-24, when asked whether to install one.
- **(d) Marks on photos, carried onto the mesh** (`photo_marks`).
  - **Carrying.** An orthographic camera renders the mesh's depth. A face the camera sees takes
    the mark at its centre's pixel. Where photos disagree, the one facing the face most squarely
    wins. Faces no photo sees take the part most of their neighbours have, in rounds.
  - **Synthetic marks:** perfect, rendered from the true parts. Three camera sets: the two front
    corners at 20° elevation (as the T33901 has), four corners, and four sides with the top.
  - **On the real photos,** only the first step was tried: placing each fed photo on the mesh.
    `fit_camera` searches azimuth and elevation for the camera whose silhouette of the mesh best
    overlaps the photo's mask, after lining up the two silhouettes' bounding boxes. The masks are
    the alpha channels of the generator's background-removed inputs (`generator/prepared/`).
    The backend has no image library, so they are read with a small PNG reader
    (`mesh_tools.read_png`). It undoes the five row filters of the PNG specification
    (https://www.w3.org/TR/png-3/, "Filtering", accessed 2026-10-24), and its masks equal
    Pillow 12.3.0's pixel for pixel. Pillow was run from the generator's existing environment as
    a check, and nothing was installed.

## 3. Results on the synthetic drill press
Area share in the right part (face share in brackets). For (d), also the share of the surface a
photo sees, and how much of that is carried right.

| Method | separate | fused | rounded |
|---|---|---|---|
| (a) cut list | 0.963 (0.800) | **0.995 (0.991)** | **0.996 (0.994)** |
| (b) separate pieces | 1.000 (22 pieces) | 0.859 (2 pieces) | 0.733 (1 piece) |
| (b) sharp edges 20° | 1.000 (160 regions) | 0.994 (46) | 0.976 (37) |
| (b) sharp edges 30° | 1.000 (127) | 0.989 (44) | 0.923 (13) |
| (b) sharp edges 45° | 1.000 (87) | 0.883 (10) | 0.865 (3) |
| (d) two front corners | 0.927; seen 0.461, of which 1.000 right | 0.946; seen 0.552, 0.999 | 0.947; seen 0.553, 0.999 |
| (d) four corners | 0.930; seen 0.638, 0.996 | 0.976; seen 0.725, 0.998 | 0.976; seen 0.729, 0.998 |
| (d) four sides and the top | 0.990; seen 0.526, 0.995 | 0.955; seen 0.648, 0.997 | 0.954; seen 0.656, 0.995 |

- **(a)** loses only at contacts. On the rounded mesh it finds the quill at a recall of 0.898
  (its top ring meets the head's fillet) and every other part above 0.96. On the separate mesh,
  the quill's long side faces have centres inside the head, out of the cut: 0.963 by area, 0.800
  by faces. That is a limit of the coarse primitive mesh, not of the method.
- **(b)** depends on sharp creases between parts. With the creases rounded, separate pieces find
  nothing, and at 30° the quill, the spindle and the rack are lost even with the best naming. The
  good fused scores need 44-46 regions named by hand.
- **(d)** carries marks almost perfectly where a photo sees (0.995-1.000). Its losses are what no
  photo sees:
  - from the two raised front corners, the quill hidden under the head and the arm under the
    table get recall 0: the quill takes the spindle's part and the arm the table's (view
    `synthetic_rounded_d2.png`);
  - side views at 0° see the quill, but put too much of the head's underside on it (precision
    0.26);
  - the seen share is 0.46-0.73, so a quarter to half of the surface is filled from neighbours.
- **Seams** (edges between two parts): 1,081 for (a) on the rounded mesh, 1,117 for (d) from two
  corners, and 388 for (b) at 30°, whose few large regions have short borders. Stray faces (in
  pieces under 2% of their part) are 2 for (a) on the rounded mesh and 15-413 for (d).
- **Time:** (a) and (b) take under 0.1 s on 180,000 faces; (d) 2.8-5.9 s.

## 4. Results on the T33901's mesh
### (a) The cut list (`part_spike.T33901_CUTS`)
Measured on the squared mesh, in model units (`--yaw 49.1`):
- **The column's axis:** round circle fits across z from -0.75 to +0.10 give (x, y) =
  (-0.1385, +0.005), radius 0.079. The cited "Column Diameter ... 3-1/8 in." (p. 9) then gives
  0.501 m per unit, within 1% of the 0.4965 that the cited height "39 in." (p. 8) gives for the
  squared height 1.995. [INFERENCE: two cited sizes agree; Phase 5 sets the scale, decision 0024.]
- **The spindle's axis:** the chuck guard is round about (0.277, -0.022), radius 0.112, from
  z 0.14 to 0.34. The chuck's nose below it reaches z ≈ 0.07.
- **The depth stop's rod:** a small circle at (0.334, -0.156) in slices from z 0.40 to 0.70, with a
  ring (outer radius about 0.03) at z 0.54-0.64.
- **The pinion's axis:**
  - the three handles, each fitted with a line, pass closest to (x 0.229, y 0.106, z 0.497);
  - the spring housing on -Y is round about (x 0.252, z 0.482), radius 0.035 at its face;
  - so the two ends of one shaft differ by 0.024 in x and 0.016 in z (about 1.4 cm).
- **The head's +Y wall** is at y 0.055-0.077 in front of the column. The belt tension lever (Fig.
  3) stands out from it to y ≈ 0.22, between x 0.04 and 0.12.
- **The table:** the plate is at z -0.30 to -0.23. The bracket spans z -0.50 to -0.28.

| Part | Shapes | Evidence | Faces | Pieces |
|---|---|---|---|---|
| spindle | cylinder r 0.045 about the spindle axis, z 0 to 0.137 | the chuck's nose below its guard (Fig. 4) | 161 | 1 |
| quill | cylinder r 0.17 about the spindle axis, z 0.137 to 0.39; cylinder r 0.02 about the rod, z 0.37 to 0.785 | the guard goes down with the quill (Fig. 46); the rod is "attached to the quill" (p. 31; Figs. 4, 35) | 2,364 | 2 |
| handle_hub | cylinder r 0.06 about the pinion axis, y 0.072 to 0.2; boxes beyond the head's wall and in front of the lever | Figs. 3, 46 | 1,865 | 4 |
| table | box over the plate; box under its rim beside the arm | Figs. 6, 7 | 5,690 | 1 |
| table_arm | box under the table, in front of the bracket | Fig. 36 (with the pivot lock handle) | 2,169 | 1 |
| frame (first) | cylinder r 0.083 about the column, below the bracket | keeps the column out of the bracket | - | - |
| column_rack | cylinder r 0.12 about the column, z 0.195 to 0.29 | the collar over the rack (Figs. 46, 48) | 562 | 1 |
| table_bracket | cylinder r 0.34 about the column, z -0.68 to -0.27 | the bracket, the height crank and the height lock handle (Figs. 6, 7, 36) | 2,321 | 1 |
| frame (the rest) | | base, column, head, motor | 24,868 | 6 |

- **Five passes,** each after looking at the coloured views (`part_spike.T33901_PASSES`):
  1. a shape per part from the measurements;
  2. the hub's box took a patch of the head's wall and the belt tension lever;
  3. that left the hub's disc in the head, cutting one handle off;
  4. that handle's root is fused to the wall;
  5. stray faces: the crank's knob, the outward handle's knob, the table rim's underside, and
     the guard collar's arm.
- **The pieces that remain are explained:**
  - the frame's six are the base with the lower column, the column between the bracket and the
    collar, the head with the upper column, the depth stop's ring (257 faces, left with the head
    on purpose), and 10 stray faces;
  - the quill's two are the guard with the rod's lower half, and the rod's top above the ring;
  - the hub's four are two handles with the hub, the up handle (fused to the wall, not to the
    hub), and 13 stray faces.
- **Seams:** 535 edges between parts. Applying the list takes 0.02 s.
- **Views:** `t33901_a.png` (all parts), `t33901_a_<part>.png` (each alone).

### (b) The mesh's own shape
- **Separate pieces:** one, the whole mesh.
- **Sharp edges:**
  - 20°: 36 regions (`t33901_b20.png`). The handles come out alone. The column, the bracket, the
    arm and the crank are one region. The table's top is split from its own rim, which joins the
    head and the base;
  - 30°: 5 regions;
  - 45°: 1 region.

### (d) The fed photos placed on the mesh
| Photo (generator slot) | Azimuth found | Azimuth the slot implies | Elevation | Silhouette IoU | Time |
|---|---|---|---|---|---|
| operator's front-left corner (`front`) | -58.1° | -49.1° | 16° | 0.796 | 47 s |
| operator's front-right corner (`left`) | +43.9° | +40.9° | 19° | 0.796 | 47 s |

The slot's azimuth is where the slot's camera stands once the mesh is squared: 0° or 90°, minus
the yaw of 49.1°. `t33901_a_on_front_photo.png` and `t33901_a_on_left_photo.png` draw the cut
parts over each photo:
- the guard, the collar, the bracket with its crank and lock handle, and the table land on the
  same parts of the photo;
- the misfit is a few percent of the image, largest at the table and the handles, which are
  nearest the camera.

[INFERENCE] The misfit comes from the photos' perspective (the camera model is orthographic) and
from the generator's own errors.
- **Enough for:** a reviewer's check of each cut against the photos.
- **Too coarse for:** carrying marks onto 12 mm handles.

### What no method can cut right on this mesh
These are the generator's errors, logged as inaccuracies for Phase 5:
- **The chuck guard** is clear plastic on the machine (Figs. 4, 46) but solid in the mesh, so the
  chuck inside is hidden. Only its nose, 161 faces, can turn.
- **The column rack** is a bump of at most 0.005 units (about 2.5 mm) on the column's +Y side.
  The column's radius is 0.0811-0.0814 there, against 0.0761-0.0805 elsewhere (medians by 20°
  sector, z -0.2 to +0.05). So the rack stays with the column, and only its collar turns around
  the column.
- **The depth stop's nut and its stop bracket** are one ring. It stays with the head, so the nut
  will not ride on the rod.
- **The up handle's root is fused to the head's wall,** at about (0.35, 0.08, 0.57). Turning the
  handles will leave a hole there.
- **The table crank's handle points back** (its knob at x -0.39, behind the column), into the
  guessed side. In the photos it points forward and down.
- **Spindle to column:** the axes are 0.416 apart. Less the column's radius, that is 0.337 units:
  6.65 in at the column's scale, 6.59 in at the height's. The manual cites "Max. Distance From
  Spindle to Column ... 7 in." (p. 8), so the mesh is 5-6% short.
- **The spindle is off the column's plane** by 0.027 units (about 1.4 cm) in y.
- **The pinion's ends** (hub and spring housing) differ by about 1.4 cm (above).
- **The back is guessed** (decision 0022). The bracket wraps the column, so its back half is cut
  from guessed surface, against Daniel's direction that no moving part be cut from the back.
  [INFERENCE] It cannot be avoided for a part that goes round the column; its note says so.

## 5. Method (c): learned part segmenters, researched only
All read on 2026-10-24. The quotes are as the pages returned them through the fetch tool.
- **P3-SAM, in Tencent's Hunyuan3D-Part** (https://github.com/Tencent-Hunyuan/Hunyuan3D-Part;
  paper "P3-SAM: Native 3D Part Segmentation", https://arxiv.org/abs/2509.06784, submitted
  2025-09-08, v4 2025-09-25).
  - **What it is:** a "native 3D point-promptable part segmentation model", "trained on a newly
    built dataset containing nearly 3.7 million models". "P3-SAM can handle any input mesh."
  - **What it gives:** "semantic features, part segmentations and part bounding boxes". It runs
    automatically (`auto_mask.py`, which selects and merges masks) or from point prompts
    (`app.py`).
  - **Licence:** "Tencent Hunyuan 3D-Part Community License Agreement". The territory is "the
    worldwide territory, excluding the territory of the European Union, United Kingdom and South
    Korea". Section 5(b) forbids using its outputs "to improve any other AI model (other than
    Tencent Hunyuan 3D-Part or Model Derivatives thereof)". Above "1 million monthly active
    users", a licence must be requested.
  - **Size and setup:**
    - weights `p3sam/p3sam.safetensors`, 451 MB (https://huggingface.co/tencent/Hunyuan3D-Part,
      9.5 GB in all with X-Part);
    - tested with "Python 3.10, PyTorch 2.4.0+cu121 and CUDA 12.1";
    - Sonata's packages, and a chamfer3D extension built with `python setup.py install`;
    - no Windows notes. Our generator environment is Python 3.12 with torch 2.8 and CUDA 12.6, so
      it would need its own environment [INFERENCE].
  - **Fit for us:** made for generated meshes like ours. Its parts come unnamed.
- **PartField** (NVIDIA, ICCV 2025; https://github.com/nv-tlabs/PartField; paper
  https://arxiv.org/abs/2504.11451).
  - **What it gives:** feature fields for meshes (`.obj`, `.glb`), Gaussian splats and point
    clouds, clustered into a hierarchical part tree, with up to 20 clusters in the examples.
  - **Licence:** "NVIDIA License": "The Work and any derivative works thereof only may be used or
    intended for use non-commercially", that is "for non-commercial research and educational
    purposes only". [INFERENCE] A university capstone fits that; later commercial use would not.
  - **Not released:** "the model that was also trained on PartNet". The checkpoint's size is not
    stated.
  - **Setup:** "Python 3.10 with PyTorch 2.4 and CUDA 12.4", conda, `torch-scatter`, `open3d`,
    `lightning`.
- **Articulate AnyMesh** (https://arxiv.org/abs/2502.02590, CoRL 2025, PMLR 305): vision-language
  models and visual prompting segment a mesh's parts and build its joints. No code repository
  was confirmed.
- **Topic 13's two** (`docs/research/project-context.md`): Articulate-Anything
  (https://arxiv.org/abs/2410.13882) and URDF-Anything (https://arxiv.org/abs/2511.00940).
  Neither was looked at again. None of the five names industrial machines among its test domains
  in the pages read.

## 6. The measures, side by side
| Measure | (a) cut list | (b) own shape | (c) learned | (d) photo marks |
|---|---|---|---|---|
| Right part, rounded synthetic | **0.996** (a ceiling: cuts from known sizes) | 0.733 (pieces); 0.923 at 30°, best naming | not tried | 0.947 from two corners, perfect marks; 0.976 from four |
| On the T33901 | 8 parts; each moving part in one piece, or explained | 1 piece; regions cross parts | not tried | photos placed, IoU 0.80; no marks carried |
| Seams | 1,081 edges (synthetic); 535 (T33901); open, jagged | fewer, but in the wrong places | - | 1,117 edges (synthetic) |
| Time | 0.02-0.08 s to apply; writing it took five passes on the T33901 | under 0.1 s, plus naming 13-46 regions | - | 3-6 s to carry; 47 s to place a photo |
| Installs, licences | none | none | P3-SAM: Tencent community licence (not in the EU, UK or South Korea), 451 MB, its own environment; PartField: non-commercial only | none to place photos; marks need a drawing tool or a model |
| Cited and reviewed | each shape has a note naming its evidence; coloured views; overlays on the photos | segments carry no reason | a model's output; unnamed | marks are evidence if a person draws them |

## 7. Conclusions [INFERENCE] and open questions
- **(a) is the method to build in Phase 5,** with (d)'s camera fit as the reviewer's check
  (decision 0023). It is the only method that is accurate on a fused surface, needs no install,
  and says why each face is where it is.
- **Writing a cut list is the slow part.** The tools to build into the inspection are the ones
  measured here by hand:
  - circle fits along any axis (the column and the quill are vertical);
  - zoomed slices;
  - lines fitted to handles;
  - the coloured views, each part's pieces, and the photo overlays.
- **(d) could make cuts less of a guess later.** Its marks are near-perfect where a photo sees, and
  more photos see more (0.55 to 0.73 of the surface from two to four corners). It needs marks
  drawn by a person or a model, and a perspective camera.
- **Open, for Daniel:**
  - **Stand-ins:** the chuck is visible through its clear guard and needed for the spindle's
    turn to show, and the rack is visible. Both are candidates for labelled stand-ins in Phase 5
    (the rule at the top of the plan).
  - **The depth stop's ring:** with the head, so the bracket is right and the nut wrong (as cut),
    or with the quill, so the nut is right and the bracket wrong?
  - **The table crank** points into the guessed back. Keep it as generated, or turn it to match
    the photos (a stand-in pose)?
  - **More photos:** a back or side photo would remove the guessed back, and a third or fourth
    view helps (d).

  Daniel answered on 2026-10-26 (section 8).

## 8. Daniel's review, and the table and the crank checked (2026-10-26)
Daniel accepted decision 0023 and answered section 7's questions. His words are in the decision
record. In short:
- a stand-in chuck: yes;
- the depth stop's ring stays with the head for now;
- the crank "looks all wrong" and the table "is supposed to be symmetrical", so both are to match
  the photos;
- no photo of the back exists that he can find, and there is no T33901 to photograph.

The table and the crank were then measured on the squared mesh with the cut list of section 4.
These were read-only scratch scripts; the views were looked at and not kept.
- **The table's top** (its 572 faces looking up, at z ≈ -0.231):
  - **not square:** 0.586 deep (x) by 0.614 wide (y). At the column's 0.501 m per unit that is
    about 11.6 by 12.1 in, where the manual gives "11-1/4 in." by "11-1/4 in." (p. 9);
  - **off centre:** its centre is at (0.260, +0.033), 0.055 in y from the spindle's axis
    (0.277, -0.022) [INFERENCE: the real table's centre hole sits under the spindle, as in
    `table_top.png`];
  - **uneven corners:** near the -Y edge (y -0.244) the table spans 0.357 in x, and near the +Y
    edge (y +0.310) 0.460. Its outline mirrored left to right lies a median 0.007 units from
    itself, and up to 0.056 (about 3 cm);
  - seen from above, it is a skewed four-sided shape with four slot openings. The photos show a
    square with rounded corners, a raised rim, and a plate with four slots in an X around a
    centre hole (`table_top.png`; Fig. 36, p. 32).
- **The crank** is joined to the bracket: the table bracket is one piece after the cut (section
  4). Its shape is wrong, though:
  - it is a round hub with an arm that curves down and back, to a knob at x -0.39 behind the
    column;
  - Fig. 36 and the colour photos show a flat S-shaped arm, with the handle pointing out, down
    and to the front.
- **What the stand-ins can rest on:**
  - the table: its cited sizes, "11-1/4 in." square and "1-1/16 in." thick (p. 9), and the
    photos for its rim, slots and centre hole;
  - the chuck: the data sheet gives its type and capacity, "Drill Chuck Type ... JT3 Key Chuck"
    and "Drill Chuck Size ... 1/8 - 5/8 in.", with "Spindle Taper ... MT#2" (PDF p. 8, read with
    pypdf on 2026-10-26). None of these is its outer size, so the body's size comes from the
    photos (Figs. 4, 46, 48) [INFERENCE];
  - the crank: no size is cited, so its proportions come from the photos, scaled by cited sizes
    [INFERENCE].
- **The column rack** was not answered. It is visible (Figs. 36, 37, 48), so under Daniel's rule it
  gets a stand-in too, unless he says otherwise.
