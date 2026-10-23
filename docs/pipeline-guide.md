# Building your pipeline (A, C or D)

For Ava (Pipeline A: nameplate photos, brochures and data sheets), Kiran (Pipeline C: layout
drawings and schematics) and Sarkis (Pipeline D: PDF catalogues and online resources). How a
pipeline runs is decision 0021, still to be agreed with you. Its questions for you are at its end.

## What you build
- **One class** that implements `Pipeline.run(job_id, sources) -> PipelineResult`
  (`backend/src/moonwalkers/pipelines/base.py`). It turns the job's inputs into one cited result.
- **Your folder** is `backend/src/moonwalkers/pipelines/<a|c|d>/`. Make its `create_pipeline()`
  return your class instead of the stub. That is the only switch: from then on the platform runs
  your pipeline (decision 0021).
- **Keep `haas_ha5c.stub.json`** in your folder. The platform's tests still use it
  (`stub_pipelines()`).
- **Work on your own branch**, and open a pull request when you want it merged.
- **A pipeline never stores anything.** The orchestrator stores what it returns (CLAUDE.md, rule 6).

## The contract, in short
`backend/src/moonwalkers/contracts/pipeline_result.py` (v0.2.0, decisions 0004 and 0020). The same
rules as a JSON Schema are in `pipeline_result.schema.json` beside it.
- **Sources.** `sources` are the job's inputs that the router gave you. You may add others you
  read, such as a web page you fetched, to `result.sources`.
- **Citations.** Every fact, joint and control behaviour cites at least one source:
  `Citation(source_id, locator, quote)`.
  - The locator is where in the source, for example `"PDF p. 8"`, with the PDF's page number.
  - The quote is the words as printed, short and verbatim.
- **Units are SI:** metres, radians, seconds, kilograms. Keep what the source wrote in `original`,
  for example `"3-1/4 in."`.
- **Labels for doubt:**
  - `confidence` (0 to 1) on facts, joints, identities and behaviours;
  - an `Issue` (`info`, `warning` or `error`) for anything a reviewer should know, such as a
    guessed value;
  - `needs_human_review` stays `True`.
- **Ids:**
  - `result_id_for(job_id, pipeline_id)` gives the result's id;
  - `schema_version` defaults to "0.2.0";
  - fact keys are snake_case, such as `spindle_travel`.
- **Parts and joints, if your pipeline finds them.**
  - A joint joins two parts of the same result.
  - Only one result per twin carries parts and joints (decision 0021). If yours will, tell Daniel.
  - Contract v0.2.0 lets a joint state its `mode` (driven, spring return, locked, free), an
    `adjustable_stop` and the joint it `follows` (decision 0020).
- **When two pipelines disagree** on a fact, both values go into the twin's notes for the reviewer.
  Nothing is picked for you.
- **Changing the contract** takes a decision record and a version bump, so talk to Daniel first.

## An example
A minimal Pipeline D. It was run through the command line below on the real manual on
2026-10-23. Its two quotes are on those PDF pages.

```python
from datetime import UTC, datetime

from moonwalkers.contracts.pipeline_result import (
    Citation, Fact, MachineIdentity, PipelineId, PipelineResult, Source,
)
from moonwalkers.workspace import default_data_dir

from ..base import Pipeline, result_id_for

INCH = 0.0254


class CatalogPipeline(Pipeline):
    pipeline_id = PipelineId.D

    def run(self, job_id: str, sources: list[Source]) -> PipelineResult:
        manual = sources[0]
        path = default_data_dir() / manual.uri  # a file source's uri is relative to data/
        # ... read the file here (pypdf is already a dev dependency) ...

        def cite(page: int, quote: str) -> list[Citation]:
            return [Citation(source_id=manual.source_id, locator=f"PDF p. {page}", quote=quote)]

        return PipelineResult(
            result_id=result_id_for(job_id, self.pipeline_id),
            job_id=job_id,
            pipeline=self.pipeline_id,
            input_types=sorted({s.input_type for s in sources}, key=lambda t: t.value),
            produced_at=datetime.now(UTC),
            produced_by="pipeline-d 0.1.0",
            sources=sources,
            identity=MachineIdentity(
                manufacturer="Grizzly Industrial, Inc.", model="T33901", confidence=0.9,
                citations=cite(9, "Model T33901/T33902 (Mfd. Since 07/23)"),
            ),
            facts=[
                Fact(key="spindle_travel", value=3.25 * INCH, unit="m", original="3-1/4 in.",
                     confidence=0.9, citations=cite(8, "Spindle Travel ... 3-1/4 in.")),
            ],
        )


def create_pipeline() -> Pipeline:
    return CatalogPipeline()
```

## Try it on the T33901 manual
1. **Set up once:** `docs/setup/windows-dev-setup.md`, then `uv sync` in `backend/`.
2. **Get the manual.** `data/` is not in Git, so download it yourself from
   https://cdn0.grizzly.com/manuals/t33901_m.pdf into
   `data/machines/grizzly-t33901/inputs/documents/grizzly-t33901-t33902-manual-2023.pdf`.
   - Check that it is the same file: in PowerShell, run `Get-FileHash <file>`. It should give
     `CF117E5ECCAD47730CD3A04120863F4E25CFA5FC59CD0A9765D864E2C8817DF5` (Daniel's copy, retrieved
     2026-10-19).
   - It is copyrighted by Grizzly, so keep it for internal research only.
3. **Run your pipeline** from `backend/`, with the input type yours reads:
   ```
   uv run python -m moonwalkers.pipelines list
   uv run python -m moonwalkers.pipelines run D --input-type pdf_catalog ../data/machines/grizzly-t33901/inputs/documents/grizzly-t33901-t33902-manual-2023.pdf --out ../data/machines/grizzly-t33901/pipeline_tries/<date>_d.json
   ```
   - The command builds the source (path, SHA-256), runs your pipeline, and checks the result
     against the contract. It then writes the result and prints a summary. It stores nothing, and
     never replaces a file.
   - Until your `create_pipeline()` returns your class, it says your pipeline "is not in yet".
   - The manual suits each pipeline in its own way [INFERENCE]: A the data sheet (pp. 8-9), as
     `brochure_datasheet`; C the T33901's exploded view and parts list (pp. 48-50), as
     `layout_drawing`;
     D the whole manual, as `pdf_catalog`.
4. **Look at the JSON.** Can each fact be found on its cited page, as quoted?

## Tests
- Put them in `backend/tests/test_pipeline_<a|c|d>.py`, and run them with `uv run pytest`.
- No network calls in tests. Keep small fixtures in `backend/tests/fixtures/`, never the
  manual itself (CLAUDE.md, rule 5).
- Mark slow tests `@pytest.mark.slow`, and tests that need a GPU `@pytest.mark.gpu`.
- `tests/test_pipelines_cli.py` shows how to run a pipeline through the command line in a test, with
  a temporary data folder.
- Before a pull request: `uv run pytest`, `uv run ruff check .` and `uv run ruff format .`.

## Dependencies
- **Ask Daniel before installing anything** (CLAUDE.md, rule 3): what it is, why, its license and
  its size.
- **Light dependencies** go into the backend's own environment (`backend/pyproject.toml`).
- **Heavy or conflicting ones** run in an environment of their own, through an adapter that your
  `create_pipeline()` returns, as the image-to-3D generators do (`backend/src/moonwalkers/generators/`;
  decision 0021). Tell Daniel early, and he will build the adapter with you.

## When it is in
- The agent's `add_input` accepts your input type.
- `submit_twin` runs your pipeline with Pipeline B, and the twin is built from both results.
