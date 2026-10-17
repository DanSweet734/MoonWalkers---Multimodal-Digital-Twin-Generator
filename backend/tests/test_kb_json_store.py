"""Behaviour specific to the JSON file store."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from moonwalkers.contracts.pipeline_result import PipelineResult, TwinRecord
from moonwalkers.kb import JsonKnowledgeBase, json_store


def make_twin(fixed_time: datetime) -> TwinRecord:
    return TwinRecord(
        twin_id="haas/ha5c@v1",
        machine_key="haas/ha5c",
        version=1,
        status="needs_review",
        created_at=fixed_time,
    )


def test_data_survives_a_new_instance(
    tmp_path: Path, example_result: PipelineResult, fixed_time: datetime
) -> None:
    JsonKnowledgeBase(tmp_path).save_result(example_result)
    JsonKnowledgeBase(tmp_path).save_twin(make_twin(fixed_time))
    reopened = JsonKnowledgeBase(tmp_path)
    assert reopened.get_result(example_result.result_id) == example_result
    assert reopened.get_twin("haas/ha5c") == make_twin(fixed_time)


def test_records_are_readable_json_files(
    tmp_path: Path, example_result: PipelineResult, fixed_time: datetime
) -> None:
    kb = JsonKnowledgeBase(tmp_path)
    kb.save_result(example_result)
    kb.save_twin(make_twin(fixed_time))

    result_file = tmp_path / "results" / f"{example_result.result_id}.json"
    twin_file = tmp_path / "twins" / "haas" / "ha5c" / "v0001.json"
    for path in (result_file, twin_file):
        raw = path.read_bytes()
        assert b"\r\n" not in raw
        assert raw.startswith(b"{\n  ")  # indented, so reviewers can read it
        json.loads(raw)
    assert sorted(p.name for p in tmp_path.rglob("*") if p.is_file()) == [
        f"{example_result.result_id}.json",
        "v0001.json",
    ]  # no temporary files left behind


def test_failed_write_leaves_nothing_behind(
    tmp_path: Path, fixed_time: datetime, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*_args: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(json_store.os, "replace", fail)
    kb = JsonKnowledgeBase(tmp_path)
    with pytest.raises(OSError, match="disk full"):
        kb.save_twin(make_twin(fixed_time))
    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []
    assert kb.get_twin("haas/ha5c") is None
