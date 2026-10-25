# Several photos per run: the T33901's views, corner photos on both generators, and the belt chart

**Date:** 2026-10-24 (drill-press plan, Phase 3). **For:** decision 0022.
**Question:** which T33901 photos can feed the image-to-3D generator, how their sides must be
named, and what each Hunyuan3D-2 model does with corner views, which no example uses. And, for
Phase 6: is a readable copy of the T33901's own belt-speed chart reachable?

## 1. Which side each photo shows, checked against the manual
The manual is `data/machines/grizzly-t33901/inputs/documents/grizzly-t33901-t33902-manual-2023.pdf`
(https://cdn0.grizzly.com/manuals/t33901_m.pdf, "REVISED DECEMBER, 2023"). Its embedded photos were
saved unchanged with pypdfium2 (`PdfImage.extract`, the JPEG streams as stored) and its pages
rendered, both into the session's scratch folder (read-only scripts, not committed).
- **p. 5 ("Identification", "T33901 Shown"):** two studio photos, greyscale. They show the same two
  views as Daniel's `front_left.jpeg` and `front_right.png`: same angles, same framing.
  [INFERENCE] The listing photos and the manual's come from one photo shoot.
- **The side labels hold.** In the view of `front_left.jpeg`, p. 5's labels put the "Depth Stop"
  and the "Spindle Return Spring" on the side facing the camera. p. 7 calls that side "Figure 4.
  Left headstock components.", and p. 6 calls the side with the handle hub "Figure 3. Right
  headstock components.". So the camera of `front_left.jpeg` stands at the operator's front-left,
  and that of `front_right.png` at the operator's front-right, as Daniel's labels say.
- **The switch is on the head's front face** ("Figure 1. Power controls.", p. 6), above the chuck.
  The hand-off placed it on the right side; corrected in the plan.
- **No photo shows the back or a side square on.** Every whole-machine view reachable today is a
  front corner: Daniel's two and the manual's two (the same views again).

## 2. Corner photos on both models (scratch runs, not twins)
Four generations with our adapter (`moonwalkers.generators.hunyuan3d`) and the repository's
settings (decision 0011: 50 steps, octree 380, seed 12345, 40,000 faces), on Daniel's two colour
photos. Versions as in `docs/setup/generators.md` (hy3dgen 2.0.2, torch 2.8.0+cu126). The
multi-view model is `hunyuan3d-dit-v2-mv`.

- **How the turn was measured.** Each mesh was turned upright (generator +Y up, +Z as the twin's
  +X, as for the HA5C). The base plate is the lowest 6% of the mesh's height. Its long axis
  (principal direction), signed to point from the column (12-22% of the height) towards the
  base's far end, is the machine's front. The angle is measured from +X towards +Y, which is the
  generator's `left` side [INFERENCE: the base reaches forward of the column, as in every photo].
- **What the photos imply.** With the generator's `front` image at +X, a camera at the operator's
  front-left corner sees the machine's front turned 45° towards +Y. A camera at the operator's
  front-right sees it turned 45° towards -Y.

| Run | Model | Images (Daniel's labels, the operator's view) | Generation | Front, measured | Front, from the photos |
|---|---|---|---|---|---|
| E1 | single image | `single` = `front_left.jpeg` | 51.1 s | +88.8° | +45° |
| E2 | single image | `single` = `front_right.png` | 48.3 s | +2.2° | -45° |
| E3 | multi-view | `front` = `front_left.jpeg`, `left` = `front_right.png` | 55.9 s | +48.5° | +45° |
| E4 | multi-view | `front` = `front_right.png`, `right` = `front_left.jpeg` | 53.4 s | -37.3° | -45° |

- **All four** are watertight, 40,000 faces, peak VRAM 6.08-6.09 GB; loading the model took
  12.1-15.9 s of each run. By eye, each is a whole drill press: head, motor, column, table with its
  bracket and crank, handles and base.
- **Not mirrored.** Squared to its measured front, every mesh has its handles reaching out on the
  operator's right (+Y). The upper band (62-85% of the height) reaches further on +Y in all four:
  0.343 against 0.248 (E1), 0.26 against 0.175 (E2), 0.471 against 0.285 (E3) and 0.338 against
  0.181 (E4) model units. In E3's and E4's front views, the table crank is on the operator's right
  too, as on the real machine ("Figure 6. Right table components.", p. 7).
- **The multi-view model keeps the photos' geometry.** Fed two corners 90° apart as a grid turned
  45°, it put the machine's front within 3.5° (E3) and 7.7° (E4) of where the photos imply. Both
  of the head's sides carry their own features (the hub on one, the depth stop on the other),
  since each was seen.
- **The single-image model does not.** From a corner photo it turned the machine about 45° further
  than the photo implies, and so square to an axis: front along +Y in E1, along +X in E2. Which
  axis is not predictable from two runs [INFERENCE]. The PoC's HA5C photo (a three-quarter view)
  also came out square, with its spindle facing +Z (decision 0012).
- **Which corner as the grid's front.** E3 came closer to its expected angle than E4. Two runs are
  too few to call either better [INFERENCE].

## 3. The T33901's belt-speed chart: not found
The manual says the speeds are set "by the configuration of V-belts and pulleys located inside the
belt cover (refer to the speed chart located under the belt cover)", and gives one entry: "a belt
combination of B-3 creates 790 RPM" (p. 30). Searched on 2026-10-24:
- **The manual's own photo of the open lid** ("Figure 33. V-belt components.", p. 30) is the same
  shot as Daniel's `top_with_cover_removed.png`, smaller: the embedded image is 503 by 375 pixels,
  and the chart in it about 50 pixels wide. Unreadable. Daniel's copy is 600 by 562, the chart
  about 80 pixels wide. Unreadable too.
- **Grizzly's documents** (cdn0.grizzly.com, which answers scripts):
  - the T33901 specification sheet, https://cdn0.grizzly.com/specsheets/t33901_ds.pdf: only the
    twelve speeds ("12 Speed Settings: 340, 500, 530, 660, 740, 790, 1380, 1420, 1680, 1860, 2200,
    2860 RPM");
  - the parts list, https://cdn0.grizzly.com/partslists/t33901_pl.pdf (SHA-256 da3ea8e8...5b78):
    "V-BELT A-565" (parts 1 and 12), "MOTOR PULLEY" (2), "IDLER PULLEY" (5), "SPINDLE PULLEY"
    (11), "BELT COVER" (7). No diameters, and no chart;
  - https://cdn0.grizzly.com/manuals/t33902_m.pdf: different bytes from our copy, but every one of
    its 56 pages has the same text. No newer revision;
  - the G7943/G7944 manual, https://cdn0.grizzly.com/manuals/g7944_m.pdf, prints its belt chart
    (p. 30, "BELT:A-1,4-4" and so on), but for other speeds ("Range of Spindle Speeds ... 140 -
    3050 RPM", p. 8) and another notation ("a belt combination of A-1, 2-2 creates 540 RPM"). Not
    the T33901's.
- **The floor model T33902** has the same twelve speeds (manual, p. 11 against p. 9), so its chart
  is very likely the same [INFERENCE]. No photo of it was found either.
- **Refused scripts (HTTP 403):** grizzly.com's product and parts pages (2026-10-22), J&B Tools'
  T33901 page, mowersatjacks.com, precisiontoolhouse.com, Home Depot's T33901 listing and
  toolguyd.com. Web searches for the chart, its speeds and its belt positions found no copy.
- **A second round, after Daniel's review** (he had not found one either, and asked for an
  independent search):
  - searches for Amazon, eBay and Reddit posts, and for the chart's own values ("2860", "790",
    "B-3"), found none;
  - Leaseville's copy of the Home Depot listing
    (https://www.leaseville.com/grizzly-industrial-14-in-12-speed-benchtop-drill-press-with-5-8-in-chuck-and-led-light-and-laser-guide.html)
    carries only the main photo (`imageHD327863898.jpg`), not the cover-open one;
  - Home Depot's listing blocks scripts. Getting past a site's bot check is not something we do,
    so the larger copy of its cover-open photo stays a task for a person in a browser.
- **What is left, by hand in a browser** (Daniel's call):
  - Home Depot's image viewer on the cover-open photo, which may serve it larger than 600 pixels;
  - the galleries of the T33901 and T33902 listings at Home Depot, Lowe's and Grizzly;
  - the T33901 section of the YouTube video Daniel used (https://www.youtube.com/watch?v=fYnqLPQ21T8),
    if it opens the belt cover;
  - Grizzly's technical support, or the label as a replacement part.

  Until then, only B-3 = 790 RPM is cited, and pulley diameters are not confirmed.
