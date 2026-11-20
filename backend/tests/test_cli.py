"""``python -m moonwalkers``: the version a release is tagged with, and the command list."""

import importlib.util
import tomllib
from pathlib import Path

import pytest

import moonwalkers
from moonwalkers.cli import COMMANDS, main

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_version_is_the_packages() -> None:
    declared = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]
    assert moonwalkers.__version__ == declared


def test_version_flag_prints_it_and_exits(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"moonwalkers {moonwalkers.__version__}"


def test_no_arguments_lists_every_command(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    out = capsys.readouterr().out
    for module in COMMANDS:
        assert f"python -m {module} " in out


@pytest.mark.parametrize("module", list(COMMANDS))
def test_every_listed_command_runs_as_a_module(module: str) -> None:
    spec = importlib.util.find_spec(module)
    assert spec is not None
    if spec.submodule_search_locations is not None:  # a package runs through its __main__
        assert importlib.util.find_spec(f"{module}.__main__") is not None
