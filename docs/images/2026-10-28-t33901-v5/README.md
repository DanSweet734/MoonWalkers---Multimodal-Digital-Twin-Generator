# `grizzly/t33901@v5`: review images (drill-press plan, Phase 5)

Committed by Daniel's exception to CLAUDE.md rule 5, for review images only ("Yes let's upload a
few small PNGs under docs in the private repo", 2026-10-27). The twin, its meshes and the photo
overlays stay in `data/` (gitignored); the overlays hold copyrighted photos.

- From v5's own views (`data/machines/grizzly-t33901/runs/2026-10-28_run-002/views/`, built on
  2026-10-28 from `part_cutting/2026-10-27_spec/geometry_spec_v5.json` on run-001's mesh),
  downscaled to 900 by 600 and 128 colours. They replace v4's images, which were re-rendered
  because v4's own views repeat three colours.
- Each sheet: front, the machine's own left (the operator's right, the handles' side), back;
  the machine's right, top, a view from the front-left above. Twin axes: x front, y left, z up.
- `parts.png`: the twin's 17 parts, stand-ins included; `parts_legend.txt` gives each colour.
- `cuts.png`: the generated mesh coloured by the cut list, the faces cut out of the twin marked
  "(removed)" in `cuts_legend.txt`.
- `part_handle_hub.png`: the stand-in downfeed hub and its three handles alone (decision 0027,
  "Update: v2 and v3").
