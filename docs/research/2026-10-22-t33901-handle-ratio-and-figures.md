# The T33901's handle-to-quill ratio, and what the manual's photos show (2026-10-22)

**Question.** The drill press's downfeed handles turn as the quill slides. How far do they turn
for the quill's 3-1/4 in of travel? The twin's coupled joint needs that ratio (radians per metre).
The manual's text does not give it (`docs/drill-press-plan.md`, "What the manual gives"). Daniel
asked on 2026-10-22 whether more research could find it. A stand-in ratio is allowed if it
cannot be found.

**Answer: not found.** No source we could reach gives the ratio, the pinion's tooth count or its
pitch. What would settle it is listed at the end. Along the way, the manual's photos settled how
the table's motions chain together, and showed two photos of the whole machine.

All sources were read on 2026-10-22 (PDT).

## The manual's text
`data/machines/grizzly-t33901/inputs/documents/grizzly-t33901-t33902-manual-2023.pdf`
(https://cdn0.grizzly.com/manuals/t33901_m.pdf), read with pypdf 6.21.1.
- The data sheet (pp. 8-9) gives "Spindle Travel ... 3-1/4 in." and "Quill Diameter ... 1.85 in.",
  and no feed ratio.
- The parts list names "PINION SHAFT" (part 100, p. 50) and "QUILL" (part 63, p. 49), with no tooth
  count, module or pitch. The "GEAR 14T" (part 108, p. 50) is listed next to the "WORM SHAFT" (109)
  and the "TABLE HEIGHT CRANK" (112). [INFERENCE] It belongs to the table's crank drive, not to
  the quill.
- No page mentions handle turns or revolutions per stroke. A search of the text from p. 33 on for
  "turn" and "revolution" found only the laser switch (p. 33).

## The manual's figures
- **Exploded views (pp. 48 and 51) are vector drawings,** with 1.3 MB of drawing commands per page
  and no embedded picture. They cannot be viewed without a PDF renderer, and none is installed:
  - the Read tool needs `pdftoppm` (poppler) to render PDF pages;
  - the backend has pypdf, which does not render.

  A candidate renderer is pypdfium2. From its PyPI page (https://pypi.org/pypi/pypdfium2/5.14.0/json):
  - version 5.14.0, uploaded 2026-10-04;
  - license "BSD-3-Clause, Apache-2.0, dependency licenses";
  - `pypdfium2-5.14.0-py3-none-win_amd64.whl` is 3,947,280 bytes;
  - "pypdfium2 does not require any mandatory runtime dependencies, apart from Python and PDFium
    itself".

  The backend's own `write_png` (`pipelines/b/mesh_tools.py`) could save the pages it renders.
  Not installed at first: that needs Daniel's approval (CLAUDE.md rule 3). He gave it later the
  same day ("The exploded views, rendered", below). [INFERENCE] Even rendered, a
  pinion in an exploded view is an illustration, so a tooth count read from it would be a guess,
  not a specification.
- **Photos.** The other figures are embedded JPEG photos. Their raw streams were saved to the
  session's scratch folder (a read-only script, not committed) and viewed:
  - **The whole machine, twice (p. 5):** two studio photos from different front angles, on white
    backgrounds.
  - **The head (pp. 6-7):** the three downfeed handles on one hub on the right of the head; the
    depth stop's threaded rod; the keyed switch.
  - **The racks (p. 36, "Figure 48. Example of quill and column racks"):** the teeth of both racks.
  - **The table (p. 32):**
    - the column bracket clamps the column, with the height crank on one side and a lock handle
      on the other;
    - the table arm leaves the bracket through a horizontal pivot, which carries the tilt scale and,
      seen from below, a central hex bolt;
    - the table turns on a round boss at the arm's far end, under the table's centre, with the
      pivot lock handle beside it.

    So the tilt comes before the turn about the table's centre, and the arm is the part between
    them. [INFERENCE: from the photos, matched to the captions "Figure 38. Location of tilt lock hex
    bolt" and "Table Pivot Lock Handle" on the same page.]
  - None of the photos shows the quill at two known depths, so the handle's angle per inch cannot
    be measured from them.

## The exploded views, rendered (later on 2026-10-22)
Daniel approved a PDF renderer on 2026-10-22 and left the choice to Claude Code.
- **Choice: pypdfium2,** added to the backend's dev dependencies (`uv add --dev "pypdfium2>=5.14,<6"`,
  which installed 5.14.0).
  - Its license is permissive, and it installs with `uv` and is pinned in `uv.lock`, so every
    teammate gets the same version on any operating system.
  - PyMuPDF was not chosen. Its PyPI page (https://pypi.org/pypi/PyMuPDF/json, read 2026-10-22)
    says "Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License", which matters if the
    repository goes public.
  - poppler's `pdftoppm` was not chosen: it is a system tool outside `uv.lock`, so it would exist
    only on Daniel's machine. It would have let the Read tool open PDF pages directly.
- **How:** a scratch script renders a page or a crop of it in greyscale (`page.render(scale,
  grayscale=True, crop=...)`), and saves it with `pipelines/b/mesh_tools.write_png`. No repository
  code uses pypdfium2 yet.
- **What p. 48 ("T33901 Main") shows,** by part number from the parts list (pp. 49-50):
  - **The table's chain, confirmed:**
    - the "COLUMN" (114) stands in the "COLUMN BASE" (116) on the "BASE" (117);
    - the "RACK" (113) runs along the column, under the "COLUMN COLLAR" (103);
    - the "COLUMN BRACKET" (106) holds the "GEAR 14T" (108), the "WORM SHAFT" (109) and the
      "TABLE HEIGHT CRANK" (112);
    - the "TABLE MOUNTING ARM" (121) fits a horizontal bore in the bracket, held by a "HEX BOLT
      M16-2 X 30" (124) with a "LOCK WASHER 16MM" (123), beside the "TABLE TILT SCALE" (118). That
      bolt is the tilt lock; the tilt procedure asks for a "Wrench or Socket 24mm" (p. 32);
    - the "TABLE" (120) sits in the arm's vertical bore, locked by a "FOLDING HANDLE M10-1.5 X 28,
      70L" (122): the table pivot lock handle.
  - **One lock handle on the bracket:** "FOLDING HANDLE M12-1.75 X 50, 90L" (105). So the "table
    lock handle" for turning around the column is the table height lock handle [INFERENCE, now
    stronger: no other lock handle is drawn].
  - **The downfeed handles:** three "STUD-DE M12-1.75 X 178, 15" (102), each with a "KNOB
    M12-1.75, D35" (101), screwed into the hub on the "PINION SHAFT" (100). So a handle bar is
    178 mm long [INFERENCE: read from a stud's size; "15" is not explained].
  - **The pinion:** drawn with teeth at the end of the pinion shaft, but in perspective only its near
    side shows. Its teeth cannot be counted, and an exploded view is an illustration anyway. **The
    ratio stays not found.**
- **The belt-speed chart is on the machine, not in the manual.** p. 30 says the speeds are set "by
  the configuration of V-belts and pulleys located inside the belt cover (refer to the speed chart
  located under the belt cover)". It gives one entry: "a belt combination of B-3 creates 790 RPM.
  "B" refers to belt position between spindle and idler pulley. "3" refers to belt position between
  idler and motor pulley". A photo of that label would give the other eleven, which is another case
  for several images per machine.

## The web
- **Grizzly's own pages refuse scripts.** WebFetch got HTTP 403 Forbidden from both:
  - the product page, https://www.grizzly.com/products/T33901;
  - the parts page, https://www.grizzly.com/products/t33901/parts.

  A person can open them in a browser. Search summaries of these pages were not used as sources:
  one called the depth stop "push-button", but the manual says "Threaded Rod w/Positive Stop"
  (p. 9).
- **Searches** (WebSearch, standard):
  - "Grizzly T33901 14" benchtop drill press";
  - "Grizzly PT33901100 pinion shaft" (only unrelated John Deere parts);
  - ""T33901" drill press downfeed handle quill pinion";
  - ""T33901" Grizzly drill press review quill return spring handles";
  - a general query for drill-press pinion teeth and feed per revolution.

  None gave the ratio, a tooth count or a feed per handle turn for the T33901.
- **Other results were not used.** They covered other machines: a geared-head press with power
  feed, forum threads on Craftsman and other Grizzly presses, and a patent describing a quill rack
  driven by a feed-lever pinion. Grizzly's G7943 page reportedly says the G7943 was superseded by the
  T33901 (search summary only). It is a different machine, so its documents would not give the
  T33901's ratio.

## What would settle it
- **A measurement on a real T33901:** the handles' angle from the top of the stroke to full depth
  (3-1/4 in). That angle divided by 0.08255 m gives the ratio. Any owner, or a store with one on
  display, could do it in a minute.
- **Grizzly's technical support,** asked for the quill pinion's tooth count and pitch, or the feed
  per handle turn. Contacting them is Daniel's call.
- **Grizzly's parts and product pages,** opened by a person. The parts list may give only names,
  as the manual does.
- **Several photos or a video of a full stroke** showing the handles at the top and at a known
  depth. This fits the goal of several images per machine (Daniel, 2026-10-22).

Until then the twin uses a stand-in ratio, labelled as such and logged as an inaccuracy.
