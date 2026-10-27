# 0024 - The drill press's facts and scale

- **Status:** proposed (by Claude Code, drill-press plan Phase 5, 2026-10-27), for Daniel's review
- **Date:** 2026-10-27
- **Decided by:** team (Daniel)
- **Amends:** decision 0012 (the scale may come from any cited length, not only a centre height)

## Context
Decision 0012 scaled the HA5C from one cited dimension, its centre height. The T33901's data sheet
cites many sizes (manual pp. 8-9; `docs/drill-press-plan.md`, "What the manual gives"), so the plan
asks which one sets the scale, whether cited dimensions can check each other, and whether the
cited "108 lbs." is split between the parts or the placeholder density stays (decision 0010).

**The facts.** `backend/src/moonwalkers/pipelines/b/grizzly_t33901.reference.json`: 36 facts from
the manual, each quoting its page. The quote checker (`python -m moonwalkers.pipelines.b.quotes`,
written this phase) found all 42 quotes on their cited PDF pages on 2026-10-27. The data sheet gave
three sizes the plan had not listed, used by the stand-ins (decision 0027): "T-Slot Size ... 9/16
in.", "Number of T-Slots ... 4" and "Quill Flange/Collar Diameter ... 2-1/8 in." (p. 9).

**The mesh.** Run `grizzly-t33901/runs/2026-10-24_run-001`, squared with up `+y`, front `+z`, yaw
49.1 (decision 0022). Measured on 2026-10-26/27 with the inspection's circle fits along z
(`inspect --circles-along z`) and read-only scratch scripts:

| Length | Measured (model units) | Cited | Scale it implies (m per unit) |
|---|---|---|---|
| Overall height: lowest point to the head's top | 1.9950 | "39 in." (p. 8) | 0.4965 |
| Overall width | 0.7660 | "15 in." (p. 8) | 0.4974 |
| Column diameter: twice the median radius of round fits, z -0.75 to -0.55 and -0.20 to +0.10 (0.0789-0.0797, rms 0.0013) | 0.1586 | "3-1/8 in." (p. 9) | 0.5005 |
| Overall depth | 1.2431 | "25-1/2 in." (p. 8) | 0.5210 |
| Spindle to column: the axes 0.4164 apart, less the column's radius | 0.3371 | "7 in." (p. 8) | 0.5274 |
| Base length: x extent within 0.02 of the lowest point | 0.9738 | "18 in." (p. 9) | 0.4694 |
| Base width: y extent within 0.02 of the lowest point | 0.5565 | "10-1/2 in." (p. 9) | 0.4792 |

- **Not measurable on this mesh:** "Distance From Spindle to Base ... 23-3/8 in." and "Max.
  Distance From Spindle to Table ... 15-7/8 in.". The spindle's nose is inside the chuck guard,
  which is clear on the machine but solid in the mesh (decision 0023).
- **One cross-check that is:** the base's work surface. An upward-facing area of 0.088 square units
  sits at z -0.892, 2.11 in above the lowest point at the height's scale. Phase 1 inferred 2-1/8
  in from three cited sizes (23-3/8 in, 15-7/8 in and the 9-5/8 in lowest floor-to-table height;
  `usd/primitive_drill_press.py`, `BASE_TOP`). [INFERENCE: that surface is the base's top.]

## Options considered
1. **The overall height,** 39 in.
   - The largest cited size, so a measuring error of 0.005 units is 0.25%.
   - Its two ends show in both fed photos: the base's underside on the bench and the top of the
     belt cover.
   - The data sheet names what it spans: "Width (side-to-side) x Depth (front-to-back) x Height".
2. **The column's diameter,** 3-1/8 in. The best-measured size (round fits along most of the
   column), but small: a 1% error in a generated column's thickness is a 1% error everywhere.
3. **Spindle to column,** 7 in. What it spans is inferred: to the column's surface, since the swing
   is 14 in [INFERENCE]. It is also where the generator is furthest off (5-6%; research note of
   2026-10-24, section 4).
4. **Spindle to base,** 23-3/8 in. The spindle's end is hidden (above).
5. **A fit over several sizes.** The mean of the implied scales above is about 0.499. It blends the
   generator's errors into the whole model, and the scale would trace to several spans, some of
   them interpreted, instead of one quote. It changes the scale by about 0.5%.

**Mass:**
- (a) keep decision 0010's placeholder: Isaac Sim infers each part's mass from its convex hull at
  1000 kg/m^3;
- (b) split the cited 48.99 kg between the parts by hull volume;
- (c) give each part a material's density.

## Decision
- **The scale is the overall height** (option 1): 0.9906 m over 1.9950 model units, **0.496536 m
  per model unit**. The column's diameter, an independent cited size, agrees within 0.8%, and the
  width within 0.2% (1.6% with the stand-in table, which is centred under the spindle).
- **The geometry spec names any cited length as its scale** (decision 0027): `scale.fact` is a fact
  in metres in the reference facts, and `scale.measured_model_units` is the same length measured
  on the mesh. For the overall depth, width and height the pipeline measures the oriented mesh
  itself. Decision 0012's centre height stays for the HA5C's specs.
- **Every cited length the mesh shows is a size check** in the twin: the three overall sizes
  (measured on the assembled twin), and the spec's own checks with the inspector's measurement and
  how it was taken. A difference above 10% is a warning, as in decision 0012.
- **Mass stays the placeholder** (option a), for now.
  - Nothing in levels 1 and 2 depends on mass: drives act on acceleration, locks are equal
    limits, the frame is fixed to the world, and a loosened table falls at g.
  - Options (b) and (c) need a share per part that no source gives. Convex hulls include air, so
    a split by hull volume would be a guess dressed as a fact.
  - The cited weight is kept as the fact `weight` (48.988 kg), and the twin says its masses are
    placeholders (an info issue). Phase 6's control logic revisits this if it needs forces.

### The size checks of `grizzly/t33901@v1` (run-001, built 2026-10-27)
| Check | Model | Cited | Difference |
|---|---|---|---|
| Overall height | 0.9906 m | 39 in | 0 (sets the scale) |
| Overall width | 0.3871 m | 15 in | +1.6% |
| Overall depth | 0.6173 m | 25-1/2 in | -4.7% |
| Column diameter | 0.0788 m | 3-1/8 in | -0.8% |
| Spindle to column | 0.1674 m (6.59 in) | 7 in | -5.9% |
| Base length | 0.4835 m | 18 in | +5.8% |
| Base width | 0.2763 m | 10-1/2 in | +3.6% |

All are under 10%, so each is an info issue in the twin.

## Consequences
- **The scale traces to one quote,** as decision 0012 requires, and every other cited size checks
  it. The generator's proportions are within 6% everywhere they can be measured.
- **The joints' travels are cited lengths,** not scaled ones: the quill's 3-1/4 in and the table's
  9-5/8 to 24 in come from the manual whatever the scale (decision 0027).
- **Masses are wrong,** and the twin says so. A pushed part's response in Isaac Sim depends on
  them; the behaviours checked at levels 1 and 2 do not.
- **Reversing it:** another `scale.fact` in a new run folder's spec, built as a new version.
