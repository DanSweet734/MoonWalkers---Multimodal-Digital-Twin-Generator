# 0034 - Pipeline D reads PDF catalogs

- **Status:** proposed (implemented on the `Sarkis` branch; team review pending)
- **Date:** 2026-11-11
- **Decided by:** implementation proposal for Sarkis Nazaryan; no team approval asserted

The number is the next free one on `main`, which holds decisions up to 0033 (checked on
2026-11-11). This branch's `0024-pipeline-d-octopart.md` shares its number with `main`'s
`0024-drill-press-facts-and-scale.md` and needs a new number when the branch is merged.

## Context
Sarkis asked for PDF catalog extraction in Pipeline D. Until now `CatalogPipeline` answered a
`pdf_catalog` source with an error issue ([decision 0024](0024-pipeline-d-octopart.md)), and
`pipelines/d/catalog_parser.py` was a standalone script: it writes a PDF's text, text boxes and
embedded images to a folder and returns no `PipelineResult`.

Three questions had to be answered:
- where the parser runs, since its library, pdfminer.six, is not a backend dependency;
- what in a PDF becomes a fact, since a fact needs a citation and nothing may be invented;
- whether a catalog names the machine.

What the parser gives was measured on Grizzly's three T33901 PDFs
(`docs/worklog/2026-11-10.md`): clean text for every page with text, no rebuilt tables, and the
data sheet's values printed as "label ..... value" lines.

## Options considered
**Where the parser runs**
1. Add pdfminer.six to the backend's dependencies. One process and simpler tests, but it changes
   the shared platform's `pyproject.toml` and `uv.lock`, which Daniel owns.
2. Use pypdf, already a backend dev dependency. Nothing to install, but it is a dev dependency
   only (`docs/drill-press-plan.md`: it "moves to the main dependencies" if the agent's tools
   run it), and it would replace Sarkis's parser rather than integrate it.
3. Run the parser in Pipeline D's own environment as a subprocess, JSON in and JSON out, as the
   Octopart browser worker already does (decisions 0021 and 0024).

**What becomes a fact**
1. The whole page text as one fact per page. Nothing is lost, but a 56-page manual puts 16,565
   words into the twin's record, and no fact says anything on its own.
2. Values converted to SI under shared keys such as `spindle_travel`. Most useful to the twin,
   but it needs a unit parser for forms such as "15 x 25-1/2 x 39 in." and a mapping from each
   maker's labels to our keys. A wrong conversion would be an invented number.
3. Each "label ..... value" line as one text fact, as printed, cited to its page with the line
   as its quote; and each labelled part or model number as a candidate.

## Decision
**Where:** option 3. `catalog_worker.py` runs `catalog_parser.py` in the environment named by
`MOONWALKERS_OCTOPART_PYTHON` and returns each page's text, candidates and image count. It
parses into a temporary folder that is removed, so the pipeline stores nothing (CLAUDE.md,
rule 6). The variable keeps its name: one environment serves both workers.

**What:** option 3, read by `catalog_facts.py` in the backend, which imports no PDF library.
- A labelled value's key is `catalog_<source hash>_p<page>_<heading>_<label>`. The heading is the
  nearest short line above without leader dots. The value is the text as printed, with no unit.
- A candidate's key is `catalog_<source hash>_candidate_<value>`, cited to the first three
  pages that print it. A candidate must hold a digit, so "this model is quiet" names nothing.
- A page headed as a contents page, or whose leader lines are at least 80% bare whole numbers
  (five lines or more), gives no facts and is named in an info issue. [INFERENCE] These two
  rules are mine, tuned on the T33901 manual, where they drop the contents page (p. 3) and the
  inventory list (p. 18).
- At most 500 facts per PDF, candidates first; the rest are counted in a warning.
- Confidence is an implementation estimate, not a measured probability [INFERENCE]: 0.7 for a
  labelled value (exact text layer, pairing by the leader dots), 0.5 for a candidate.

**Identity:** a catalog never sets `MachineIdentity`, as in decision 0024. The T33901 manual
covers the T33901 and the T33902, with a data sheet for each (PDF pp. 8-9 and 10-11), so the
pipeline cannot tell which model a job is about.

**Inputs:** a `pdf_catalog` source must be a file in the data folder. A PDF given as a URL is
not downloaded: it gets an error issue. A file whose SHA-256 no longer matches its source is
refused. The shared contract is unchanged.

## Consequences
- `python -m moonwalkers.pipelines run D --input-type pdf_catalog <file>` and the agent's
  `add_input` with `pdf_catalog` now give facts. On 2026-11-11 the T33901 data sheet gave 75
  facts, the manual 220 and the parts list 3 (`docs/worklog/2026-11-11.md`).
- The facts are evidence for a reviewer or the agent, not values the exporter uses. Keys carry a
  source hash and a page, so they never match another pipeline's key and never raise a
  disagreement between pipelines.
- A manual's tool and quantity lists also come through as facts ("Hex Wrench 3mm ... 1"), and
  a heading may be a fragment of a sentence. Both are printed text, cited, and noise.
- Not read: tables without leader dots (the parts list's 159 part numbers), drawings, text
  inside images, scanned pages. Embedded images are counted and not imported.
- The process that runs the pipeline needs `MOONWALKERS_OCTOPART_PYTHON`; without it every PDF
  gets one error issue. Each PDF costs one subprocess (16 s for the 56-page manual).
- `catalog_parser.py` gained `part_candidates()` (the digit rule) and lint fixes.

Reversal: make `CatalogPipeline.run` answer `pdf_catalog` with an issue again. No schema
migration is needed; stored results stay valid.

## Open questions for Sarkis
- Should values be converted to SI under shared keys (option 2), for a list of labels we agree on?
- Should the embedded images be kept, for example as photos for Pipeline B?
- Is `MOONWALKERS_OCTOPART_PYTHON` still the right name now that it serves PDFs too?
