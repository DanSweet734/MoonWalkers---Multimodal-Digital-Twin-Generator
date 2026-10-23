# 0021 - How Pipelines A, C and D run outside their tests

- **Status:** proposed (by Claude Code in the drill-press plan's Phase 2; Daniel left Phase 2's
  choices to Claude Code on 2026-10-23). It is agreed with Ava, Kiran and Sarkis before it is
  merged (plan, Phase 2; CLAUDE.md, "Who owns what").
- **Date:** 2026-10-23
- **Decided by:** team (Daniel, with the pipeline owners)
- **Amends:** decision 0002 (A, C and D are stubs) and decision 0009 (merging is left open)

## Context
Pipelines A, C and D belong to Ava, Kiran and Sarkis. Each replaces its stub in
`pipelines/<a|c|d>/` by making `create_pipeline()` return the real pipeline (each folder's
docstring). How their pipelines then run, outside the tests, was never decided. The plan's Phase 2
lists four questions. What the code does today (read on 2026-10-23):
- **The stubs run outside the tests.** `default_pipelines()` returns the three stubs, and the MCP
  server, the API, the control command and Pipeline B's build all use it. Each stub returns the
  HA5C's fixture for any input (`pipelines/fixture_stub.py`).
- **So a document can get HA5C facts today.** The agent's `add_input` tool takes any input type,
  not only a machine photo. If the agent added the T33901 manual as a `pdf_catalog` input,
  `submit_twin` would route it to Pipeline D's stub. The drill press's twin would then carry the
  HA5C's facts. Nothing has done this yet: every stored result is Pipeline B's.
- **Where inputs go.** The Input Router sends each input to the pipeline for its type
  (`orchestrator/router.py`). The orchestrator runs every routed pipeline and builds one twin
  version from all their results (`orchestrator/orchestrator.py`). It refuses an input whose
  pipeline is missing (`PipelineUnavailableError`).
- **Several results.**
  - The contract keeps each joint's parts in its own result, so a joint cannot join one result's
    part to another's.
  - The exporter refuses a part id found in two results, and needs every part in one tree from
    one root (decision 0017).
  - Nothing compares two results' facts. Decision 0009 leaves merging open.
- **Who has started.** No pipeline code yet (Daniel, 2026-10-23: the one teammate branch was an
  access test).

## Options considered
1. **Where they start.**
   - (a) **A command line** that runs one pipeline on files or URLs and writes its result, storing
     nothing. The owners can try their pipeline on the T33901 manual the day it runs.
   - (b) **The agent's tools.** `add_input` already puts a document in a run's request, and
     `submit_twin` already routes it. Nothing new is needed once a pipeline is in, except refusing
     a document whose pipeline is not.
   - (c) **A new MCP tool** to run one pipeline alone. While no real pipeline exists, it could only
     refuse.
   - (d) **The dashboard's upload.** It takes one machine photo, and Phase 3 reworks it for several
     photos (decision 0022).
2. **The stubs.**
   - (a) **Tests only:** `default_pipelines()` leaves out every stub, and the tests build them
     explicitly. An input for a pipeline that is not in yet is refused, naming its owner.
   - (b) Keep them, and let each result's "Stub output" issue warn the reviewer. The HA5C's facts
     would still reach another machine's twin.
   - (c) Change each `create_pipeline()` to refuse. That edits the owners' folders, which is theirs
     to do.
3. **Which results may carry parts and joints.**
   - (a) **One result per twin.** A second result with parts is refused before anything is stored,
     with a message that says why.
   - (b) Prefer one pipeline's geometry, such as B's, and drop the other's. It silently loses
     cited work.
   - (c) Merge parts by id. The contract cannot join one result's part to another's, so the trees
     would not connect.
4. **When two results give one fact different values.**
   - (a) **List them for the reviewer.** The twin's notes name each pipeline's value, and the build
     goes on. Nothing is picked, and both stay in each result's provenance. The methodology asks to
     "name both, pick one, and say which and why", and a person picks in review.
   - (b) Pick by confidence, as the machine's identity is picked. A confidence is a pipeline's
     guess, not a source's authority.
   - (c) Refuse the build. Two catalogues that round differently would stop it.
5. **The environment.**
   - (a) **The backend's own,** as a Python class that `create_pipeline()` returns. A dependency is
     added to `backend/pyproject.toml` after asking Daniel (rule 3).
   - (b) **Its own environment,** called as a subprocess through an adapter, as the generators are
     (`generators/`). That is for heavy or conflicting dependencies (OCR, a vision-language model,
     a GPU).

## Decision
1a and 1b now; 1c and 1d wait. 2a, 3a, 4a, and 5a by default with 5b when needed. These are Claude
Code's proposals.

### Where they start
- **The command line** (`moonwalkers.pipelines`):
  - `uv run python -m moonwalkers.pipelines list` shows each pipeline, its input types, its owner,
    and whether it is in;
  - `uv run python -m moonwalkers.pipelines run D --input-type pdf_catalog <file or URL>...
    [--out FILE]` runs one pipeline;
  - it builds a cited `Source` for each input: a file inside the data folder, hashed, or a URL;
  - it checks the result against the contract, and writes it as JSON. It stores nothing: only the
    orchestrator does that (rule 6). It refuses to overwrite a file.
- **The agent:** `add_input` refuses an input whose pipeline is not in, before anything is
  generated. The message says to cite the document with `add_reference_source` instead, as in the
  PoC. Once an owner's pipeline is in, the same `add_input` adds the document, and `submit_twin`
  runs that pipeline with Pipeline B.
- **Later:**
  - a separate MCP tool, if the agent needs to run a pipeline alone;
  - the dashboard, with Phase 3's uploads (decision 0022).

### The stubs
- `Pipeline.stub` marks a stub, and `FixturePipeline` is one.
- `default_pipelines()` returns only the owners' pipelines that are not stubs: none today.
- `stub_pipelines()` builds the three stubs for the tests. The fixtures stay in the owners'
  folders, and the guide asks the owners to keep them.
- A refused input names the pipeline, the input type and the owner, and says how a pipeline
  comes in.

### One twin from several results
- **Geometry:** at most one result of a job carries parts and joints. Two are refused before
  anything is stored or exported.
- **Facts:** when results give one fact key different values, the twin's notes list each
  pipeline's value. Values agree when:
  - numbers have the same unit and are within 0.5% of each other [INFERENCE: wide enough for
    rounding, for example 3-1/4 in against 82.5 mm, which differ by 0.06%];
  - text matches, ignoring case and the spaces at either end;
  - anything else is equal.
- **Identity** stays as it is: the request's machine, else the most confident identity, with a
  note when they disagree.
- **Across jobs and versions,** merging stays open (decision 0009).

### The environment
- A pipeline runs in the backend's environment by default (5a).
- One that needs heavy or conflicting dependencies runs in its own, through an adapter that
  `create_pipeline()` returns (5b). The adapter is built with its owner, when one is needed.

## Consequences
- **No HA5C facts reach another machine.** Until an owner's pipeline is in, its inputs are
  refused, at `add_input` and again in the build.
- **The owners can try their pipelines now,** on the T33901 manual, without the agent or the
  knowledge base (`docs/pipeline-guide.md`).
- **Nothing changes for Pipeline B.** Its builds route only a machine photo, as before. The HA5C's
  and TH240's runs are unaffected, since none of them used a stub.
- **The tests keep the stubs,** through `stub_pipelines()`. The orchestrator's tests run on them
  and on fake pipelines.
- **A second geometry is refused,** even where a person could see how to join them. Joining
  Pipeline C's kinematics to Pipeline B's mesh needs a contract change, when a pipeline needs it.
- **Disagreements wait for a person.** The twin is built, and the reviewer reads the notes. The
  dashboard shows them on the twin's page.
- **Reversing it:** let `default_pipelines()` return the stubs again, and drop the two checks in
  the orchestrator.

## Questions for the pipeline owners (Ava, Kiran, Sarkis)
- Does your pipeline need anything the backend's environment lacks (OCR, a model, a GPU)? If so,
  which, and how large?
- Will your results carry parts or joints (Pipeline C's drawings might)? Then the one-geometry
  rule matters to you.
- Is the 0.5% agreement for numbers right for your sources?
- Is a command line enough to start with, or do you need the agent or the dashboard to run your
  pipeline sooner?
