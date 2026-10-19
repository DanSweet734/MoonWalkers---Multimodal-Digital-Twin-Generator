"""Indexing programs as the HA5C manual's step table: reading, limits and program files."""

import json
import re

import pytest

from moonwalkers.contracts.pipeline_result import Citation, ControlBehavior
from moonwalkers.control import IndexProgram, ProgramError, ProgramFile, packaged_programs


def rows(*steps: list) -> list[list]:
    """Number the given rows 1, 2, ... (each row without its step number)."""
    return [[n, *row] for n, row in enumerate(steps, start=1)]


def test_the_manual_examples_ship_with_their_citations() -> None:
    programs = packaged_programs()
    assert sorted(programs) == [
        "ha5c-manual-example-2",
        "ha5c-manual-example-3",
        "ha5c-manual-example-3-circle-division",
        "ha5c-manual-example-4",
        "ha5c-manual-example-5",
        "ha5c-manual-example-5-subroutine",
        "ha5c-manual-example-6",
    ]
    for path in programs.values():
        program = ProgramFile.load(path)
        assert program.behavior.kind == "program_interpreter"
        assert program.behavior.drives_joints == ["spindle_rotation"]
        assert all(c.locator and c.quote for c in program.behavior.citations)
        assert [s.source_id for s in program.sources] == ["src-haas-ha5c-manual-2006"]


def test_rows_are_read_as_the_manual_prints_them() -> None:
    program = IndexProgram.from_rows(
        [
            [1, 0, 4, 3, 96],
            [2, 0, "", 1, 88],
            [3, 0, 80, 1, 95],
            [4, 90, 0, 1, 91],
            [5, 0, None, 1, 99],
        ]
    )
    call, home, end, index, last = program.steps
    assert (call.jump_to, call.feed_deg_s, call.loops) == (4, None, 3)  # Step# in the feed column
    assert home.feed_deg_s is None and index.feed_deg_s is None  # empty or 0: the maximum feed
    assert end.g == 95 and last.g == 99
    assert program.rows()[0] == [1, 0.0, 4, 3, 96]


@pytest.mark.parametrize(
    ("table", "message"),
    [
        (rows([90, 271, 1, 91], [0, None, 1, 99]), "feed rate 271.0 is outside 0.001-270.0"),
        (rows([1000, None, 1, 91], [0, None, 1, 99]), "step_deg: Input should be less than"),
        (rows([90, None, 0, 91], [0, None, 1, 99]), "loops: Input should be greater than"),
        (rows([90, None, 1, 42], [0, None, 1, 99]), "G42 is not one of the manual's G codes"),
        (rows([1, None, 1, 73], [0, None, 1, 99]), "peck cycle for linear operation only"),
        (rows([0, None, 4, 85], [0, None, 1, 99]), "G85 fractional circle division"),
        (rows([0, None, 1, 98], [0, None, 1, 99]), "circle division needs L from 2 to 999"),
        (rows([0, 9, 2, 96], [0, None, 1, 99]), "G96 jumps to missing step 9"),
        (rows([90, None, 1, 91]), "no end code (G99)"),
        ([[1, 90, None, 1, 91], [3, 0, None, 1, 99]], "without gaps"),
        ([[1, 90, None, 91]], "a step row has 5 columns, not 4"),
    ],
)
def test_programs_the_manual_does_not_allow_are_refused(table, message) -> None:
    with pytest.raises(ProgramError, match=re.escape(message)):
        IndexProgram.from_rows(table)


def test_subroutines_cannot_call_subroutines() -> None:
    table = rows(
        [0, 3, 1, 96], [0, None, 1, 95], [0, 5, 1, 96], [90, None, 1, 91], [0, None, 1, 99]
    )
    with pytest.raises(ProgramError, match="nesting of subroutine calls is not permitted"):
        IndexProgram.from_rows(table)


def behavior(spec: dict, kind: str = "program_interpreter") -> ControlBehavior:
    return ControlBehavior(
        behavior_id="index_program",
        name="Test program",
        kind=kind,  # type: ignore[arg-type]
        description="test",
        drives_joints=["spindle_rotation"],
        spec=spec,
        confidence=1.0,
        citations=[Citation(source_id="src-manual")],
    )


def test_a_program_lives_in_a_behaviours_spec() -> None:
    table = rows([90, 270, 4, 91], [0, 270, 1, 99])
    as_list = IndexProgram.from_behavior(behavior({"program": table}))
    as_dict = IndexProgram.from_behavior(behavior({"program": {"columns": [], "rows": table}}))
    assert as_list == as_dict and len(as_list.steps) == 2
    with pytest.raises(ProgramError, match="is a state_machine, not a program"):
        IndexProgram.from_behavior(behavior({"program": table}, kind="state_machine"))
    with pytest.raises(ProgramError, match="has no spec"):
        IndexProgram.from_behavior(behavior({"modes": {"G90": "absolute"}}))
    with pytest.raises(ProgramError, match="must be a list of step rows"):
        IndexProgram.from_behavior(behavior({"program": {"rows": "90 270 4 91"}}))


def test_a_program_file_cites_only_its_own_sources(tmp_path) -> None:
    data = ProgramFile.load(packaged_programs()["ha5c-manual-example-3"]).model_dump(mode="json")
    data["behavior"]["citations"][0]["source_id"] = "src-elsewhere"
    path = tmp_path / "program.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProgramError, match="cites unknown sources"):
        ProgramFile.load(path)
