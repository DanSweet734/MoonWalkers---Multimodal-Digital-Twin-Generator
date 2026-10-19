# 0008 - PoC knowledge base store: one JSON file per record

- **Status:** accepted (proposed by Claude Code in Phase 1; Daniel reviewed and approved on 2026-10-17)
- **Date:** 2026-10-16
- **Decided by:** team (Daniel)

## Context
Decision 0005 puts the knowledge base behind a `KnowledgeBase` interface and leaves the PoC store as
"a JSON or SQLite file store under `data/kb/`". Phase 1 of `docs/poc-plan.md` needs that store. Constraints:
the PoC is single-user (`docs/research/project-context.md`, Section 10b); v1 keeps a human in the loop,
so reviewers should be able to see exactly what was stored; and no installs are wanted for this step.

## Options considered
1. **JSON files, one per record** (Python standard library plus pydantic, already installed).
   Pros: a reviewer can open any record in an editor; diffs are readable; append-only is easy to
   enforce (refuse to write a file that exists). Cons: no transactions or queries; listing means
   scanning folders [INFERENCE: fine at PoC scale, a handful of machines]; safe for one writer only.
   Writes go to a temporary file and are moved into place with `os.replace`. The Python docs say:
   "If successful, the renaming will be an atomic operation (this is a POSIX requirement)"
   (https://docs.python.org/3.12/library/os.html#os.replace, accessed 2026-10-16). Atomicity on
   Windows is not stated there: **not confirmed**.
2. **SQLite** (`sqlite3`, standard library; https://docs.python.org/3.12/library/sqlite3.html).
   Pros: transactions and concurrent readers. Cons: a binary file that needs a tool to inspect; a table
   schema to maintain; records would most likely still be stored as JSON text [INFERENCE].
3. **Neo4j now.** A database server to install and run; deferred to the integration phase by 0005.

## Decision
Option 1, implemented in `backend/src/moonwalkers/kb/json_store.py`:

```
data/kb/
  results/<result_id>.json                 # every stored PipelineResult
  twins/<manufacturer>/<model>/v0001.json  # one TwinRecord per version (machine key haas/ha5c)
```

Records are never overwritten. Result ids and machine keys are validated before they become paths,
so a malformed id such as `../x` is refused. A twin's sources are not stored separately: they live
inside the results it was built from, and `KnowledgeBase.sources_for_twin` collects them (listing a
source once even when several results cite it).

## Consequences
- No install and no server; `data/kb/` can be read by hand during review.
- One writer at a time. When Celery workers arrive in the integration phase, move to SQLite or Neo4j.
- `tests/test_kb.py` runs against every implementation through the parametrized `kb` fixture, so a
  Neo4j store must pass the same tests before it can replace this one.
- Changing a stored record (for example, a reviewer approving a twin) needs a new method; today the
  store only adds records. (2026-10-18: decision 0015 records reviews as new files,
  `reviews/<manufacturer>/<model>/v0001/r0001.json`, so the store still only adds records.)
