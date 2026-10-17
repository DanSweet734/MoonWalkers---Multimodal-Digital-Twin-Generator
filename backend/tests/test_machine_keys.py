"""Machine keys: one key per machine, however its name is written."""

import pytest

from moonwalkers.kb import InvalidMachineKeyError, machine_key, validate_machine_key


@pytest.mark.parametrize(
    ("manufacturer", "model", "expected"),
    [
        ("Haas Automation", "HA5C", "haas/ha5c"),
        ("Haas Automation, Inc.", "HA-5C", "haas/ha5c"),
        ("HAAS", "ha5c", "haas/ha5c"),
        ("  haas automation inc  ", "HA 5C", "haas/ha5c"),
        ("Grizzly Industrial", "T33901", "grizzly-industrial/t33901"),
    ],
)
def test_same_machine_gives_same_key(manufacturer: str, model: str, expected: str) -> None:
    assert machine_key(manufacturer, model) == expected


@pytest.mark.parametrize(
    ("manufacturer", "model"), [("", "HA5C"), ("Inc.", "HA5C"), ("Haas", "--")]
)
def test_unusable_names_are_rejected(manufacturer: str, model: str) -> None:
    with pytest.raises(InvalidMachineKeyError):
        machine_key(manufacturer, model)


@pytest.mark.parametrize(
    "key",
    ["", "haas", "../etc", "haas/../x", "Haas/HA5C", "haas/ha5c/v1", "haas/ha-5c", "-haas/ha5c"],
)
def test_malformed_keys_are_rejected(key: str) -> None:
    with pytest.raises(InvalidMachineKeyError):
        validate_machine_key(key)


def test_valid_key_is_returned_unchanged() -> None:
    assert validate_machine_key("grizzly-industrial/t33901") == "grizzly-industrial/t33901"
