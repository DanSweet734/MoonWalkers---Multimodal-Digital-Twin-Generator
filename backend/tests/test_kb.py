"""KnowledgeBase behaviour every implementation must have (the ``kb`` fixture runs each one)."""

from datetime import datetime

import pytest

from moonwalkers.contracts.pipeline_result import PipelineResult, TwinRecord
from moonwalkers.kb import (
    AlreadyExistsError,
    InvalidIdError,
    InvalidMachineKeyError,
    KnowledgeBase,
    KnowledgeBaseError,
)


def twin(version: int, fixed_time: datetime, key: str = "haas/ha5c", built_from=()) -> TwinRecord:
    return TwinRecord(
        twin_id=f"{key}@v{version}",
        machine_key=key,
        version=version,
        status="needs_review",
        built_from=list(built_from),
        created_at=fixed_time,
    )


def with_id(result: PipelineResult, result_id: str) -> PipelineResult:
    return result.model_copy(update={"result_id": result_id})


def test_missing_records_are_none_or_empty(kb: KnowledgeBase) -> None:
    assert kb.get_result("res-1") is None
    assert kb.get_twin("haas/ha5c") is None
    assert kb.get_twin("haas/ha5c", version=1) is None
    assert kb.list_versions("haas/ha5c") == []
    assert kb.list_machines() == []


def test_result_round_trip(kb: KnowledgeBase, example_result: PipelineResult) -> None:
    kb.save_result(example_result)
    assert kb.get_result(example_result.result_id) == example_result


def test_results_are_never_overwritten(kb: KnowledgeBase, example_result: PipelineResult) -> None:
    kb.save_result(example_result)
    changed = example_result.model_copy(update={"produced_by": "something else"})
    with pytest.raises(AlreadyExistsError):
        kb.save_result(changed)
    assert kb.get_result(example_result.result_id) == example_result


def test_all_versions_are_kept_and_latest_is_default(
    kb: KnowledgeBase, fixed_time: datetime
) -> None:
    v1, v2 = twin(1, fixed_time), twin(2, fixed_time)
    kb.save_twin(v2)  # saving out of order must not matter
    kb.save_twin(v1)
    assert kb.list_versions("haas/ha5c") == [v1, v2]
    assert kb.get_twin("haas/ha5c") == v2
    assert kb.get_twin("haas/ha5c", version=1) == v1


def test_twin_versions_are_never_overwritten(kb: KnowledgeBase, fixed_time: datetime) -> None:
    kb.save_twin(twin(1, fixed_time))
    with pytest.raises(AlreadyExistsError):
        kb.save_twin(twin(1, fixed_time).model_copy(update={"notes": "changed"}))
    assert kb.get_twin("haas/ha5c", version=1).notes is None


def test_list_machines(kb: KnowledgeBase, fixed_time: datetime) -> None:
    kb.save_twin(twin(1, fixed_time, key="haas/ha5c"))
    kb.save_twin(twin(1, fixed_time, key="grizzly-industrial/t33901"))
    assert kb.list_machines() == ["grizzly-industrial/t33901", "haas/ha5c"]


def test_sources_for_twin_lists_each_source_once(
    kb: KnowledgeBase, example_result: PipelineResult, fixed_time: datetime
) -> None:
    first, second = with_id(example_result, "res-1"), with_id(example_result, "res-2")
    kb.save_result(first)
    kb.save_result(second)
    sources = kb.sources_for_twin(twin(1, fixed_time, built_from=["res-1", "res-2"]))
    assert sources == example_result.sources


def test_sources_for_twin_reports_missing_results(kb: KnowledgeBase, fixed_time: datetime) -> None:
    with pytest.raises(KnowledgeBaseError, match="res-missing"):
        kb.sources_for_twin(twin(1, fixed_time, built_from=["res-missing"]))


def test_unsafe_ids_and_keys_are_rejected(
    kb: KnowledgeBase, example_result: PipelineResult, fixed_time: datetime
) -> None:
    with pytest.raises(InvalidIdError):
        kb.save_result(with_id(example_result, "../outside"))
    with pytest.raises(InvalidIdError):
        kb.get_result("..\\outside")
    with pytest.raises(InvalidMachineKeyError):
        kb.get_twin("../outside")
    with pytest.raises(InvalidMachineKeyError):
        kb.save_twin(twin(1, fixed_time, key="Haas/HA5C"))
