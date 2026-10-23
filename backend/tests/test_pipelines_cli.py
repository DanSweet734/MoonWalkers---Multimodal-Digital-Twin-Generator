"""``python -m moonwalkers.pipelines``: run Pipeline A, C or D on inputs, storing nothing
(decision 0021). The pipeline here is a fake standing in for an owner's real one."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from moonwalkers.contracts.pipeline_result import (
    Citation,
    Fact,
    PipelineId,
    PipelineResult,
    Source,
)
from moonwalkers.pipelines import Pipeline, result_id_for
from moonwalkers.pipelines.cli import main


class OwnersPipelineD(Pipeline):
    """Reads one fact from each input, citing it; records the sources it was given."""

    pipeline_id = PipelineId.D

    def __init__(self, break_contract: bool = False) -> None:
        self.break_contract = break_contract
        self.given: list[Source] = []

    def run(self, job_id: str, sources: list[Source]) -> PipelineResult:
        self.given = sources
        cited = "nowhere" if self.break_contract else sources[0].source_id
        fact = {"key": "spindle_travel", "value": 0.08255, "unit": "m", "confidence": 0.9}
        citations = [Citation(source_id=cited, locator="PDF p. 8")]
        fields = {
            "result_id": result_id_for(job_id, self.pipeline_id),
            "job_id": job_id,
            "pipeline": self.pipeline_id,
            "input_types": [s.input_type for s in sources],
            "produced_at": datetime(2026, 10, 23, 12, tzinfo=UTC),
            "produced_by": "owners-pipeline-d (fake)",
            "sources": sources,
        }
        if self.break_contract:  # built without validation, citing a source it was not given
            facts = [Fact.model_construct(**fact, citations=citations)]
            return PipelineResult.model_construct(**fields, facts=facts)
        return PipelineResult(**fields, facts=[Fact(**fact, citations=citations)])


@pytest.fixture
def manual(tmp_path: Path) -> Path:
    path = tmp_path / "data" / "machines" / "grizzly-t33901" / "inputs" / "documents" / "m.pdf"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"%PDF- a stand-in for the manual")
    return path


def run(manual: Path, *extra: str, pipeline: Pipeline | None = None) -> int:
    pipelines = {} if pipeline is None else {PipelineId.D: pipeline}
    data = manual.parents[4]
    argv = ["run", "D", "--input-type", "pdf_catalog", str(manual), "--data", str(data), *extra]
    return main(argv, pipelines=pipelines)


def test_list_shows_owners_and_which_pipelines_are_in(capsys) -> None:
    assert main(["list"], pipelines={PipelineId.D: OwnersPipelineD()}) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("A  Ava Harken") and lines[0].endswith("returns the stub")
    assert "python -m moonwalkers.pipelines.b" in lines[1]
    assert lines[3].startswith("D  Sarkis Nazaryan") and "pdf_catalog" in lines[3]
    assert lines[3].endswith(" in")


def test_run_writes_the_checked_result_and_stores_nothing(manual: Path, tmp_path, capsys) -> None:
    pipeline = OwnersPipelineD()
    out = tmp_path / "tries" / "d.json"
    assert run(manual, "--out", str(out), "--job", "try-manual", pipeline=pipeline) == 0
    result = PipelineResult.model_validate_json(out.read_text(encoding="utf-8"))
    assert (result.pipeline, result.job_id, result.schema_version) == (
        PipelineId.D,
        "try-manual",
        "0.2.0",
    )
    source = pipeline.given[0]
    assert source.kind == "file" and source.input_type.value == "pdf_catalog"
    assert source.uri == "machines/grizzly-t33901/inputs/documents/m.pdf"
    assert source.sha256 is not None and source.source_id == "src-m"
    assert "1 fact(s)" in capsys.readouterr().err
    assert not (tmp_path / "data" / "kb").exists()


def test_run_prints_the_result_without_out(manual: Path, capsys) -> None:
    assert run(manual, pipeline=OwnersPipelineD()) == 0
    assert json.loads(capsys.readouterr().out)["job_id"] == "try-d"


def test_a_url_becomes_a_url_source(manual: Path) -> None:
    pipeline = OwnersPipelineD()
    url = "https://cdn0.grizzly.com/manuals/t33901_m.pdf"
    data = manual.parents[4]
    argv = ["run", "D", "--input-type", "online_resource", url, "--data", str(data)]
    assert main(argv, pipelines={PipelineId.D: pipeline}) == 0
    assert (pipeline.given[0].kind, pipeline.given[0].uri) == ("url", url)


def test_a_pipeline_not_in_yet_is_refused_with_its_owner(manual: Path, capsys) -> None:
    assert run(manual) == 2
    error = capsys.readouterr().err
    assert "Pipeline D (Sarkis Nazaryan's) is not in yet" in error and "decision 0021" in error


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["run", "B", "--input-type", "machine_photo", "x"], "python -m moonwalkers.pipelines.b"),
        (["run", "D", "--input-type", "schematic", "x"], "go to Pipeline C, not D"),
    ],
    ids=["pipeline-b", "input-type-of-another-pipeline"],
)
def test_wrong_pipelines_and_input_types_are_refused(argv, message, capsys) -> None:
    assert main(argv, pipelines={PipelineId.D: OwnersPipelineD()}) == 2
    assert message in capsys.readouterr().err


def test_a_file_outside_the_data_folder_is_refused(manual: Path, tmp_path, capsys) -> None:
    outside = tmp_path / "elsewhere.pdf"
    outside.write_bytes(b"%PDF-")
    argv = [
        "run",
        "D",
        "--input-type",
        "pdf_catalog",
        str(outside),
        "--data",
        str(tmp_path / "data"),
    ]
    assert main(argv, pipelines={PipelineId.D: OwnersPipelineD()}) == 2
    assert "outside the data folder" in capsys.readouterr().err


def test_an_existing_out_file_is_never_replaced(manual: Path, tmp_path, capsys) -> None:
    out = tmp_path / "d.json"
    out.write_text("kept", encoding="utf-8")
    assert run(manual, "--out", str(out), pipeline=OwnersPipelineD()) == 2
    assert out.read_text(encoding="utf-8") == "kept"
    assert "never replaced" in capsys.readouterr().err


def test_a_result_that_breaks_the_contract_is_reported(manual: Path, tmp_path, capsys) -> None:
    out = tmp_path / "d.json"
    assert run(manual, "--out", str(out), pipeline=OwnersPipelineD(break_contract=True)) == 1
    assert "breaks the contract" in capsys.readouterr().err
    assert not out.exists()
