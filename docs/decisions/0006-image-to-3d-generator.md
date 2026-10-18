# 0006 - Image-to-3D generator for Pipeline B: Hunyuan3D-2mv first, Stable Fast 3D fallback

- **Status:** accepted for the PoC; fallback changed by 0011 (2026-10-17)
- **Date:** 2026-10-16
- **Decided by:** team

## Context
Development machine: Windows 11, one RTX 4090 (24 GB). Input: a few photos of one machine. Findings
(each from the project's own README or license, read Oct 16, 2026):
- Hunyuan3D-2 family (https://github.com/Tencent-Hunyuan/Hunyuan3D-2): "6 GB VRAM for shape generation
  and 16 GB for shape and texture generation in total"; supports macOS, Windows, Linux; the 2mv model
  takes multiple views (front/left/back). License: Tencent Hunyuan 3D 2.0 Community License (excludes the
  EU, UK and South Korea; separate license above 1 million monthly active users).
- Stable Fast 3D (https://github.com/Stability-AI/stable-fast-3d): about 6 GB VRAM, single image, Windows
  "experimental"; Stability AI Community License; weights gated on Hugging Face.
- TRELLIS.2 (https://github.com/microsoft/TRELLIS.2): needs at least 24 GB, tested only on Linux.
- SAM 3D Objects (https://github.com/facebookresearch/sam-3d-objects): needs at least 32 GB, Linux.
- None of these documents joints or articulation; joints are added by our own pipeline.

## Decision
Hunyuan3D-2mv primary, Stable Fast 3D fallback, each in its own environment, called through an adapter.

## Consequences
Generator dependencies never mix with the backend's. Swapping generators (for example TRELLIS.2 on a Linux
machine later) only needs a new adapter. Licenses are fine for a US student PoC but must be revisited
before any release.

## Update (2026-10-17)
Decision 0011 replaces the Stable Fast 3D fallback with Hunyuan3D-2's single-image model. That model
runs in the same environment with no compiling and no gated weights. Stable Fast 3D's README lists
Windows support as "experimental" and needs Visual Studio 2022 and gated weights. The first HA5C runs
use the single-image model because only one clean photo is available; Hunyuan3D-2mv stays the
primary choice for multi-view photo sets.
