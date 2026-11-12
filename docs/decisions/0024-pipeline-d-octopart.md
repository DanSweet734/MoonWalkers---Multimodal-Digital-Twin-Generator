<!-- OCTOPART-SEARCH: this whole file is about the Octopart website search (decision 0024); blocked by Octopart's security check, HTTP 403, 2026-11-10. -->
# 0024 - Pipeline D Octopart component enrichment

- **Status:** proposed (implemented for Sarkis's requested integration; team review pending)
- **Date:** 2026-11-04
- **Decided by:** implementation proposal for Sarkis Nazaryan; no team approval asserted

## Context
Sarkis requested integration of the standalone Octopart browser extraction feature into Pipeline
D. Decision [0021](0021-how-pipelines-a-c-and-d-run.md) defines the registration and subprocess
option; the [pipeline guide](../pipeline-guide.md) requires cited `PipelineResult` output and
keeps storage in the orchestrator. The existing backend has no browser dependency.

## Options considered
1. Import Playwright into the backend: simpler packaging, but adds a backend dependency and
   mixes browser lifecycle with server execution.
2. Use the [Octopart API](https://www.altium.com/documentation/altium-developer-center/quick-starts/octopart-api):
   structured access, but requires credentials and access not supplied for this task.
3. Invoke a browser worker in a separately configured Python environment, returning JSON.
   Preserves the requested browser workflow and the backend dependency set [INFERENCE].

## Decision
Implement option 3 with `MOONWALKERS_OCTOPART_PYTHON`, under `pipelines/d/`. Register a real
pipeline now and report missing setup, unsupported sources and access failures as issues.
Retain the stub for existing tests. Propose the separate Playwright install; do not install it
or modify the backend lockfile as part of this change.

Treat catalog results as component evidence, not the machine's identity. Require one exact
part candidate and one unique Product metadata object. Preserve raw offers/text with citations
and review warnings; do not infer numerical specifications or convert unknown price units.
The shared contract is unchanged.

## Consequences
The default registry now includes D. PDF catalogs and non-Octopart sources still return explicit
unsupported-input issues. The MCP test for a missing pipeline must inject an empty registry,
instead of depending on D always being absent. The backend reports issues rather than prompting
for login/CAPTCHA. One browser subprocess per source bounds each operation but adds launch
cost. Live behavior is not verified in the build environment; see the
[setup and verification guide](../setup/pipeline-d-octopart.md).

Reversal: restore D's fixture factory; keep its parser and worker dormant. No schema migration
or changes to previously stored results are necessary.
