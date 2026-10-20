# 0015 - Reviews of twin versions: separate append-only records; a rejected version is not reused

- **Status:** accepted (proposed by Claude Code in Phase 5; Daniel chose "approve or reject, and
  skip rejected versions", then "approved first" after trying the dashboard, and reviewed and
  merged the Phase 5 PR, #9, all on 2026-10-18).
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
3. **What an approval does,** when a newer version has not been reviewed yet.
   - (a) **Approved first:** a request reuses the newest approved version, so an unreviewed
     rebuild never replaces a twin a person approved. Only without an approved version does it
     take the newest one not rejected.
   - (b) **Newest not rejected:** a new rebuild is reused at once, before anyone reviews it.
4. **Who reviews.**
   - (a) **People only:** through the dashboard and the API.
   - (b) **The agent too,** through an MCP tool.

## Decision
Daniel chose 2a and, after trying the dashboard, 3a. The others (1a, 4a) are Claude Code's
proposals.

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
- **Reuse (amends decision 0009).** `Orchestrator.reusable_twin(key)` picks the version a request
  reuses:
  1. the newest **approved** version;
  2. if none is approved, the newest version not rejected (`needs_review` or `draft`);
  3. if every version is rejected, none.

  - The message names the reused version's review status and every newer version it skipped,
    with theirs: "Found an existing twin (v1, approved) for haas/ha5c; reused it. Newer versions
    were not reused: v2 (needs review)."
  - When every version is rejected, a request with inputs builds a new version: "Every stored
    version of the haas/ha5c twin was rejected in review, so built version 4 (previous: v3) ...".
- **Approval never locks a twin.** A new version can always be built (`new_version`). It starts as
  `needs_review` and takes over from an approved one only once it is approved too.
- **Reviewers.** People review through the dashboard (`POST
  /api/twins/{manufacturer}/{model}/versions/{version}/reviews`). The MCP server has no review
  tool, so the agent can read a review status but never set one (4a).

## Consequences
- **Every decision stays on record,** with who and why, and the twin and its results are never
  edited.
- **A rebuild waits for its review.** After an approval, a new version is not reused until someone
  approves it. The job that built it still reports it, and its page in the dashboard shows it. But
  a later request by name keeps getting the approved version, and its message names the newer
  version it skipped.
- **Approving an older version on the real data changes reuse.** For example, approving HA5C v2
  while v3 is unreviewed makes requests reuse v2.
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
