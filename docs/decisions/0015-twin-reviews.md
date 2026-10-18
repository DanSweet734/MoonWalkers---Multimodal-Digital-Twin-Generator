# 0015 - Reviews of twin versions: separate append-only records; a rejected version is not reused

- **Status:** proposed (Claude Code, Phase 5). Daniel chose "approve or reject, and skip rejected
  versions" on 2026-10-18; the details await his review in the Phase 5 PR.
- **Date:** 2026-10-18
- **Decided by:** team (Daniel)

## Context
- **What the methodology asks.** `docs/methodology.md`: "A reviewer approves or rejects a twin; the
  decision and reason are recorded with the twin version." Phase 5 asks the dashboard to show each
  twin's review status.
- **What the earlier decisions left open:**
  - The contract's `TwinRecord.status` allows `draft`, `needs_review` and `approved`.
  - Decision 0009: "The contract has no "rejected" status, so a reviewer's rejection cannot be
    recorded yet; that needs a contract change (new decision record and version bump) when review
    is built."
  - Decision 0008: records are never overwritten, and "Changing a stored record (for example, a
    reviewer approving a twin) needs a new method".
- **What reuse did.** Decision 0009 reuses the latest version whatever its review status, because
  no review step existed yet.

## Options considered
1. **Where a review lives.**
   - (a) **A record of its own,** beside the twin version, written by the orchestrator. The
     `TwinRecord` and the pipeline contract are unchanged.
   - (b) **Change the contract:** add `rejected` to `TwinRecord.status` and a review field, with a
     version bump.
     - The bump would also change `PipelineResult.schema_version`, which every stored result
       carries as `"0.1.0"`, and which Pipelines A, C and D would have to follow, for a change
       none of them makes [INFERENCE].
     - Recording a decision would still mean editing a stored record, against decision 0008.
2. **What a rejection does.**
   - (a) **Skip it:** a request reuses the newest version that review did not reject, and builds
     a new one when every version is rejected.
   - (b) **Name it only:** reuse stays as decision 0009 says, and the message names the review.
3. **Who reviews.**
   - (a) **People only:** through the dashboard and the API.
   - (b) **The agent too,** through an MCP tool.

## Decision
Daniel chose 2a. The others (1a, 3a) are Claude Code's proposals.

- **Record.** `moonwalkers.kb.TwinReview` (`kb/reviews.py`):
  - `machine_key`, `version` and `number` (1, 2, ... per version);
  - `decision` (`approved` or `rejected`);
  - `reviewer` (a name, 1-100 characters) and `reason` (1-2000 characters), both trimmed;
  - `reviewed_at`.
- **Storage.** `kb/reviews/<manufacturer>/<model>/v0003/r0001.json`, never overwritten.
  - `KnowledgeBase` gains `save_review`, `list_reviews` and `review_status`. A version's review
    status is its latest review's decision, or the status it was stored with.
  - The stored `TwinRecord` keeps `needs_review`.
- **Writer.** Only the orchestrator writes reviews (CLAUDE.md, rule 6).
  `Orchestrator.review_twin(key, version, decision, reviewer, reason)` checks that the version
  exists. A later review of the same version is added after the earlier one and decides from then
  on, so a rejection can be reversed, and both stay on record.
- **Reuse (amends decision 0009).**
  - `Orchestrator.reusable_twin(key)` is the newest version whose review status is not
    `rejected`. A request reuses that version.
  - The message names its review status and any newer versions skipped: "Found an existing twin
    (v2, needs review) for haas/ha5c; reused it. Newer versions were rejected in review: v3."
  - When every version is rejected, a request with inputs builds a new version: "Every stored
    version of the haas/ha5c twin was rejected in review, so built version 4 (previous: v3) ...".
- **Reviewers.** People review through the dashboard (`POST
  /api/twins/{manufacturer}/{model}/versions/{version}/reviews`). The MCP server has no review
  tool, so the agent can read a review status but never set one (3a).

## Consequences
- **Every decision stays on record,** with who and why, and the twin and its results are never
  edited.
- **Two status fields.** `TwinRecord.status` is the status at build time, so readers must use the
  review status for the current state. The API returns both (`twin.status`, `review_status`), and
  the MCP tools report `review_status` beside `status`.
- **No contract change.** The JSON Schema and the pipelines are untouched. `TwinReview` is
  knowledge-base data, outside `contracts/` [INFERENCE: it is not pipeline output].
- **Reviewers are not authenticated.** A reviewer types their name, and the API is local only
  (decision 0014). Real accounts come with a shared deployment.
- **Reversing it.** Dropping reviews means deleting `kb/reviews/` and going back to "latest
  version". Moving them into the contract later means migrating the review files into the new
  field.
