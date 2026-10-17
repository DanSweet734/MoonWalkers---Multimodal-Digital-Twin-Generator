# 0004 - Shared pipeline output contract (v0.1.0)

- **Status:** accepted (draft content, may change with a version bump)
- **Date:** 2026-10-16
- **Decided by:** team

## Context
Four people build four pipelines in parallel. They need one agreed format for what a pipeline returns.
Advisors require that users can see where every piece of information came from.

## Decision
`PipelineResult` (Pydantic, `backend/src/moonwalkers/contracts/pipeline_result.py`, JSON Schema export
alongside). It carries: sources, machine identity, cited facts, parts (geometry), scale calibration,
joints, control behaviors, issues, and `needs_human_review` (default true). `TwinRecord` and `JobResult`
cover what the orchestrator stores and returns, including `reused_existing` and twin versions.
Rules enforced by validation: every fact, joint and behavior cites a known source; joints reference real
parts; behaviors reference real joints; no unknown fields. Units are SI.

## Consequences
The structure mirrors the draft knowledge-graph schema (machine, component, joint, control signal, data
source, prior twin), so moving from the simple store to Neo4j is a mapping, not a redesign. Pydantic is
also used by Dr. Li's lab's benchmark repo. Any change requires a new decision record and a version bump.
