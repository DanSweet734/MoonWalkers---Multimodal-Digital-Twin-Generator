# 0009 - Machine keys, twin reuse, and re-versioning

- **Status:** accepted (proposed by Claude Code in Phase 1; Daniel reviewed and approved on 2026-10-17)
- **Date:** 2026-10-16
- **Decided by:** team (Daniel)

## Context
PoC pass criterion: "a second request for the same machine reuses the stored twin and says so"
(`docs/poc-plan.md`). The Oct 16 team decisions say the PoC is single-user, twins are "re-versioned on
user request", and results "must say when a twin was found in the knowledge base"
(`docs/research/project-context.md`, Section 10b). Existing project text about the key:
- `TwinRecord.machine_key`: "normalised 'manufacturer/model', used for reuse lookups"; the `JobResult`
  example message says "for haas/ha5c" (`backend/src/moonwalkers/contracts/pipeline_result.py`).
- `data/README.md`: machine folders are "lowercase `manufacturer-model` (this matches
  `TwinRecord.machine_key`)", e.g. `haas-ha5c`.
- The example Pipeline B result names the manufacturer "Haas Automation".

## Options considered
**Machine key**
1. Slug of the full names: "Haas Automation" + "HA5C" gives `haas-automation/ha5c`. Simple, but does not
   match the `haas/ha5c` used throughout the docs.
2. Normalise, then apply a short alias table: lowercase; keep letters and digits; drop trailing legal
   words (Inc, Corp, LLC, Ltd, ...); join manufacturer words with hyphens; strip all punctuation from the
   model ("HA-5C" gives `ha5c`); then map `haas-automation` to `haas`. Matches the docs. Costs: the alias
   table must be curated, and two different machines whose names differ only in punctuation would share a key.
3. A canonical catalog id (for example from Pipeline D). Better long term; not available in the PoC.

**Which version to reuse**
1. The latest version, whatever its review status, with the status named in the message.
2. Only an approved version. More conservative, but no review step exists yet, so the PoC would always rebuild.

## Decision
- **Key:** option 2 (`moonwalkers/kb/keys.py`). The folder name under `data/machines/` is the key with
  "/" replaced by "-" (`haas/ha5c` becomes `haas-ha5c`). Keys are validated before use as paths.
- **Flow** (`moonwalkers/orchestrator/orchestrator.py`):
  1. If the request names the machine and a twin exists, reuse it without running any pipeline.
  2. Otherwise run the routed pipelines and take the key from their results: the request's machine if
     given, else the most confident identity.
  3. If that machine's twin exists, reuse it; the message says it was found after running the pipelines
     and that their results were not stored.
  4. Otherwise store the results and twin version 1.
- **Reuse:** the latest version (option 1). The message reads, for example,
  "Found an existing twin (v1, needs review) for haas/ha5c; reused it."
- **Re-versioning:** only when the request sets `new_version`. The new version is latest + 1, earlier
  versions are kept, and `built_from` lists only that job's results.
- **Status:** every new twin is `needs_review`; the orchestrator never sets `approved` (v1 keeps a human
  in the loop, `docs/methodology.md`).
- **Disagreement:** when the request or pipelines name different machines, the chosen key and the others
  are written to `TwinRecord.notes` and repeated in the message.

## Consequences
- Reuse works only if every pipeline's identity normalises to the same key; new manufacturers may need
  alias entries (add them deliberately, with the source of the short name).
- Without a machine hint, an expensive pipeline (Pipeline B's image-to-3D) runs before the knowledge
  base is checked [INFERENCE: Phase 4's MCP tools "identify machine" and "check knowledge base" should
  run before "generate geometry", so the agent passes a hint].
- The contract has no "rejected" status, so a reviewer's rejection cannot be recorded yet; that needs a
  contract change (new decision record and version bump) when review is built.
- Merging facts from several versions or jobs into one twin is not decided; each version is built only
  from its own job's results.
