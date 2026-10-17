# 0005 - Knowledge base: Neo4j long term, simple store behind an interface for the PoC

- **Status:** accepted
- **Date:** 2026-10-16
- **Decided by:** team

## Context
The knowledge base stores source material and twins so a machine is not rebuilt. Neo4j was suggested on
Oct 1-2 (GraphRAG research, Topic 9) and confirmed Oct 16 unless the team later finds a reason to change.

## Decision
Define a `KnowledgeBase` interface (save/load twin records, look up by machine key, list versions,
store sources). The PoC implements it with a JSON or SQLite file store under `data/kb/`. A Neo4j
implementation follows in the integration phase.

## Consequences
No database server to run during the PoC. The interface must stay narrow enough that Neo4j can implement
it without changing callers.
