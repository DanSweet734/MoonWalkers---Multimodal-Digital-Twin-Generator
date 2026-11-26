# Video input: the options, and what Daniel's phone can capture

**Question:** if the advisors approve video input (meeting of 2026-11-19), which routes could take
a video of a machine to a functional twin, and how should Daniel film at the lab so the footage
serves them? Also: does his Galaxy S22 Ultra have LiDAR or another depth setting to try?

**Dates and method.** Searched on 2026-11-18 by Claude Code (the lab plan's Phase 8 chat), on
Daniel's question before his lab visit of 2026-11-19. Web searches and two pages fetched; nothing
installed or downloaded. Several sources are secondary (reviews, mirrors, vendor blogs), so each
row says how firm it is. This note feeds the video plan's draft (`docs/video-plan.md`); it decides
nothing.

## The phone: Galaxy S22 Ultra
| Fact | Source | How firm |
|---|---|---|
| **No LiDAR and no time-of-flight depth camera.** Samsung used 3D ToF sensors on the S10 5G, Note 10+, S20+ and S20 Ultra, then replaced them with laser autofocus from the Note20 Ultra on; the S22 series has none | [Gizchina, 2021-04-19](https://www.gizchina.com/2021/04/19/galaxy-s22-will-not-bring-back-the-3d-tof-sensor/), [Tom's Guide](https://www.tomsguide.com/news/samsung-galaxy-s22-leak-just-revealed-a-missing-camera-feature) (pre-launch reports); [HotHardware's review](https://amp.hothardware.com/reviews/samsung-galaxy-s22-ultra-and-s22-review) describes "a matching circular laser autofocus module" | Pre-launch reports plus a review; no Samsung page read |
| **The laser autofocus is not a depth camera:** it is "more like a single 'Pixel'" that helps focusing | [Gizchina](https://www.gizchina.com/2021/04/19/galaxy-s22-will-not-bring-back-the-3d-tof-sensor/) | Secondary |
| **It supports ARCore's Depth API** (depth computed from the camera's motion, not sensed): "Galaxy S22 Ultra 5G — Supports Depth API" | [Google, ARCore supported devices](https://developers.google.com/ar/devices), fetched 2026-11-18 | Primary |
| **Video:** 4K up to 60 fps on all rear cameras; 8K only on the main camera, at 24 fps | [GSMArena review](https://www.gsmarena.com/samsung_galaxy_s22_ultra-review-2382p7.php), [DXOMARK](https://www.dxomark.com/samsung-galaxy-s22-ultra-exynos-camera-test/) (through search snippets) | Two reviews agree |
| **Rear cameras:** 108 MP wide (F1.8, 85°), 12 MP ultra-wide (120°), 10 MP 3x telephoto, and a 10x periscope | [Samsung Newsroom launch release](https://news.samsung.com/global/samsung-galaxy-s22-ultra-offers-the-ultimate-and-most-premium-s-series-experience-yet/1000) (through a search snippet) | Primary, not opened |

So there is no depth setting to switch on. Depth on this phone comes only from software that
watches the camera move (ARCore, or a reconstruction afterwards) [INFERENCE from the rows above].

## How to film for reconstruction
Guides for photogrammetry and Gaussian splatting from video agree on these (secondary, vendor and
community guides): lock exposure, focus and white balance for the whole clip; turn off electronic
stabilisation, which "crops and warps the frame" and confuses the camera model; move at about half
walking pace; 4K at 30 fps as a baseline. Sources: [PlayCanvas, taking photos for splats](https://developer.playcanvas.com/user-manual/gaussian-splatting/creating/taking-photos/),
[Polyvia, splatting from video](https://polyvia3d.pages.dev/guides/gaussian-splatting-from-video),
[Pix-Pro, video frames vs photos](https://www.pix-pro.com/blog/video-photogrammetry).

Our own record adds:
- the generator wants the whole machine in each view, cut out cleanly; the agent's SAM-only
  cut-outs gave `haas/tm1@v4` a worse mesh (`docs/lab-machines-report.md`, section 3);
- the multi-view generator takes up to four views (front, left, back, right; decision 0022,
  `docs/setup/generators.md`). Its README's example feeds `front`, `left` and `back`
  ([Hugging Face, tencent/Hunyuan3D-2mv](https://huggingface.co/tencent/Hunyuan3D-2mv/blob/main/README.md),
  through a search snippet); no source read states the camera height it expects (not confirmed).

What Daniel was given for 2026-11-19 (his checklist page, video section): one circle per machine at
chest height without zoom, the sides said aloud, a second higher circle if time allows,
close-ups and motion as separate clips, a tape measure in frame, photos as well; 4K 60 fps on the
1x lens, Super steady off, focus and exposure locked (or Pro video). 60 rather than 30 fps is
[INFERENCE]: less blur per frame when frames are pulled out.

## Routes from video to a twin
| Route | What it gives | Licence and cost | Fit for a functional twin |
|---|---|---|---|
| **A. Frames as photos** through the existing path (views, cut-outs, Hunyuan3D-2mv, the cut list) | The same twin as today, with views chosen from many frames | A frame reader (ffmpeg or OpenCV) is an install: ask first (CLAUDE.md rule 3) | The smallest step; joints and control unchanged [INFERENCE] |
| **B. SAM 2 tracking the machine through the clip** | One click on one frame, a mask on every frame: "click an object once on one frame and it tracks that object across the rest of the video" (project context, topic 5) | Apache 2.0 for code and checkpoints ([sam2 model card](https://huggingface.co/facebook/sam2-hiera-tiny/raw/a8e4b467be69abf1c58fb327abc2935aaa890d1e/README.md); [repo](https://github.com/facebookresearch/segment-anything-2)) | Aims at the cut-out gap that broke v4 (report 8.3, gap 1) [INFERENCE]; an install and weights |
| **C. Many-view reconstruction:** COLMAP/GLOMAP or VGGT for camera poses and points, then a measured mesh | Geometry measured from the footage, not generated; real scale with a tape measure in frame | COLMAP: "new BSD" ([github.com/colmap/colmap](https://github.com/colmap/colmap)); GLOMAP is merged into COLMAP 4.0 as its global mapper (secondary). VGGT: code licence changed 2025-07-29 to allow commercial use except military; the original VGGT-1B weights are CC-BY-NC-4.0, and a gated `facebook/VGGT-1B-Commercial` checkpoint exists ([Hugging Face](https://huggingface.co/facebook/VGGT-1B-Commercial); mirrors) | A different way to make the mesh, which the advisors deferred to later (2026-11-12); still needs our cut list for joints [INFERENCE] |
| **D. Gaussian splats into Isaac Sim** (3DGRUT, ParticleField USD) | A photoreal backdrop of the lab | Isaac Sim loads "USD stages that use OpenUSD ParticleField geometry" ([Isaac Sim 6.0.1, neural volume rendering](https://docs.isaacsim.omniverse.nvidia.com/6.0.1/assets/usd_assets_nurec.html), fetched); a 3DGRUT export "contains only the Gaussian splat representation", so colliders are separate ([NVIDIA forum](https://forums.developer.nvidia.com/t/loading-usdz-files-from-nurec-pipeline-into-isaac-sim-does-not-load-mesh-file/352914)) | Visual only: no parts, joints or collisions; a scene around the twins, not a twin [INFERENCE] |
| **E. Joints from motion clips** | Joint type, axis and position from a video of the part moving | Research code: Peng et al. ([arXiv 2506.08334](https://arxiv.org/abs/2506.08334v1)) needs an RGBD video, which this phone cannot record; sim2art works from a monocular video, trained on synthetic data ([arXiv 2512.07698](https://arxiv.org/abs/2512.07698v2)); Articulation in Motion, ICLR 2026 ([OpenReview](https://openreview.net/pdf/2db6760fadf898baa13788114edba6983082a4d6.pdf)). Licences not checked | Research-grade. The near use is simpler: time and direction of a jog from the lab's motion clips, against the twin's plan (level 3 against the real machine) [INFERENCE] |
| **F. A phone scan app as an outside baseline** | A photogrammetry mesh made on the phone or in the vendor's cloud | Epic's RealityScan Mobile: free on Android 7+ with ARCore, version 1.8 (2025-11) adds AR guidance and background removal; its EULA lets Epic train on scan data unless the user opts out ([CG Channel, 2025-11](https://www.cgchannel.com/2025/11/epic-games-releases-realityscan-mobile-1-8/); [RealityScan news](https://www.realityscan.com/news/realityscan-mobile-is-now-available-for-android-devices)). KIRI Engine is on Android with a free tier and splats (vendor sources) | A comparison for the scorecard's photo match, not a pipeline; the lab's permission first, since images leave our machines |

## Reading [INFERENCE]
- A and B together are the likely first phases: video becomes a better source of views, and SAM 2's
  tracking gives every frame a cut-out, which is also the advisors' ask 1 (a cut-out tool).
- C is the strongest answer to "bumpy meshes", and the footage filmed on 2026-11-19 (a steady
  circle, a second height, a tape measure) serves it, but it is the mesh study the advisors put
  later.
- D and E's research methods do not give functional parts; E's simple form (timing jogs) gives a
  real-machine check for level 3.
- Every route above that runs on Daniel's machine needs an install, asked first with what, why,
  licence and size.

## Update, 2026-11-25: the footage of 2026-11-19, and what is already on the machine
Checked by Claude Code on 2026-11-25 for the video plan's draft. Nothing installed or downloaded.
- **Approved:** the advisors approved video input and the cut-out tool at the meeting of
  2026-11-19 (worklog 2026-11-25).
- **The footage** (filed by machine on 2026-11-25; `SOURCES.md` of each): eight MP4s, 2.1 GB with
  the photos. H.264, 3840x2160, about 60 fps (variable; ffprobe's average 59.9), about 72 Mbit/s,
  AAC sound; the portrait clips carry a display rotation of -90.
  | Machine | Clips | What |
  |---|---|---|
  | TM-1 | `133809` (27.7 s), `133841` (30.1 s) | Two full circles, chest height then higher (Daniel); the back now unobstructed but for the caution panel at the pendant's side |
  | VF-3 | `133039` (34.9 s), `133120` (35.9 s), `133413` (30.2 s) | Two circles round the enclosure, hemmed in by a desk and a tool cart; close-ups inside |
  | The lab's other ReBeL, the 01 | `132340` (38.8 s), `132718` (25.3 s), `132427` (1.5 s) | Two circles, landscape, the arm stretched out with a hand; a clip of a label |
  No clip shows a machine moving (no one could operate one), so route E has nothing to measure
  yet. No tape measure was seen in the frames looked at (contact sheets of 12 frames a clip).
- **Sharpness** (variance of the Laplacian on a 960-pixel-wide grey copy of every 15th frame,
  OpenCV 4.11.0; a scratch script, figures for this footage only, not comparable across scenes):
  the share of sampled frames below half the clip's median, a rough count of blurred frames
  [INFERENCE]: TM-1 10.8% and 1.7%; VF-3 24.1% and 18.9%; the 01 arm 4.5% and 1.0%. The VF-3's
  circles, walked in a tight space, have the most blurred frames.
- **A frame reader is already on Daniel's machine:**
  - **ffmpeg and ffprobe 9.0.2** (Gyan's "full_build", winget package `Gyan.FFmpeg`, on the PATH).
    That build is configured `--enable-gpl --enable-version3`, so it is GPL v3 [the build's
    configuration line]; calling it as a separate program, as the generator is called, is not
    linking it [INFERENCE, not legal advice]. It turns the portrait clips upright by default.
  - **OpenCV 4.11.0** in the generator's environment (`C:\mw-gen`; `docs/setup/generators.md`)
    reads the clips, but reports the portrait ones as 3840x2160, so a reader through OpenCV must
    apply the rotation itself [seen in the sharpness script; INFERENCE: OpenCV's orientation
    handling].
  Neither is in the backend's dependencies or on the teammates' machines, so the backend would
  call ffmpeg found on the PATH, or a package would be an install (asked first).
- **SAM in the platform is SAM 1** (`sam_vit_b_01ec64`, quantised, in rembg 2.0.68; decision
  0029). Route B's tracking needs SAM 2, which is not installed: an install, asked first.

## Open
- Which of A to F come first (the video plan).
- Whether Hunyuan3D-2mv expects level views (not confirmed).
- RealityScan's and KIRI's processing location and terms, read from their own pages before use.
