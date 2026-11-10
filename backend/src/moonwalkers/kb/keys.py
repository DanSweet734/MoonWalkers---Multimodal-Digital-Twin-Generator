"""Machine keys: the normalised ``manufacturer/model`` string used to find an existing twin.

Two identities that name the same machine must give the same key, or reuse silently fails, so
punctuation, case, spacing and legal-form words are dropped (decision 0009)::

    machine_key("Haas Automation, Inc.", "HA-5C") == "haas/ha5c"
"""

from __future__ import annotations

import re

# Trailing legal-form words dropped from manufacturer names. "gmbh" since the lab's ReBeL arm,
# whose maker signs its documentation "igus® GmbH" (Technical documentation ReBeL, 08/2022, p. 8)
# while its base label reads "igus" (docs/lab-machines-plan.md, Phase 1).
LEGAL_SUFFIXES = frozenset(
    {
        "inc",
        "incorporated",
        "corp",
        "corporation",
        "co",
        "company",
        "llc",
        "ltd",
        "limited",
        "plc",
        "gmbh",
    }
)

# Short manufacturer names the project uses in keys and folder names (for example "haas/ha5c" in
# the contract's JobResult example and "haas-ha5c" in data/README.md). Add entries deliberately,
# with the source of the short name (decision 0009):
# - "Grizzly Industrial, Inc." (T33901 manual, p. 1) is "Grizzly" on its machines: the "GRIZZLY
#   LOGO LABEL" (part 201, manual p. 54). Data folder grizzly-t33901 (Daniel, 2026-10-24).
MANUFACTURER_ALIASES: dict[str, str] = {
    "haas-automation": "haas",
    "grizzly-industrial": "grizzly",
}

MACHINE_KEY_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*/[a-z0-9]+")


class InvalidMachineKeyError(ValueError):
    """The text cannot be (or does not form) a valid machine key."""


def normalize_manufacturer(name: str) -> str:
    """Lowercase words joined by hyphens, without trailing legal-form words, aliases applied."""
    words = re.findall(r"[a-z0-9]+", name.lower())
    while words and words[-1] in LEGAL_SUFFIXES:
        words.pop()
    slug = "-".join(words)
    return MANUFACTURER_ALIASES.get(slug, slug)


def normalize_model(model: str) -> str:
    """Lowercase letters and digits only, so "HA-5C", "HA 5C" and "ha5c" match."""
    return "".join(re.findall(r"[a-z0-9]+", model.lower()))


def machine_key(manufacturer: str, model: str) -> str:
    """The machine key for a manufacturer and model name."""
    return validate_machine_key(f"{normalize_manufacturer(manufacturer)}/{normalize_model(model)}")


def validate_machine_key(key: str) -> str:
    """Return ``key`` unchanged if it is a well-formed machine key; raise otherwise.

    Stores use keys in file paths, so this also blocks path tricks such as ``../``.
    """
    if not MACHINE_KEY_PATTERN.fullmatch(key):
        raise InvalidMachineKeyError(
            f"invalid machine key {key!r}: expected 'manufacturer/model' in lowercase letters, "
            "digits and hyphens, for example 'haas/ha5c'"
        )
    return key
