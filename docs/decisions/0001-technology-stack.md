# 0001 - Technology stack: Option A

- **Status:** accepted
- **Date:** 2026-10-16
- **Decided by:** team (advisors left the stack to us)

## Context
The team needed a stack before implementation. Research on Oct 6, 2026 (Project Design doc, New Research
Topics, Topic 14) found that similar projects are Python-based (two repos from Dr. Li's lab, AHa-3D, NVlabs
SAGE), and that NVIDIA's Omniverse Web Viewer sample is React + TypeScript + Vite
(https://github.com/NVIDIA-Omniverse/web-viewer-sample). The team is comfortable with Python and Docker.

## Options considered
1. **A:** Python (FastAPI) + task queue (Celery) + React/TypeScript dashboard + Docker + graph database via its Python driver.
2. **B:** all Python with a Gradio interface (lowest effort, limited dashboard).
3. **C:** Node/TypeScript backend with Python workers.

## Decision
Option A. For the proof of concept, Celery and Docker are deferred until the integration phase; jobs run
in-process and the dashboard is barebones.

## Consequences
React is the one new technology for the team. A React front end keeps a future live 3D view possible.
