"""Pure reading of a parsed catalog's page text: labelled values and where a candidate is printed.

No PDF library is imported here, so the backend and its tests can use it without Pipeline D's
own environment. The page text comes from ``catalog_worker.py`` (decision 0034).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

# "Spindle Travel........ 3-1/4 in.": a label, a run of leader dots, the value.
LEADER = re.compile(r"^\s*(?P<label>\S.*?)\s*\.{4,}\s*(?P<value>\S.*?)\s*$")
LEADER_RUN = re.compile(r"\s*\.{4,}\s*")
HEADING_LENGTH = 60  # a longer line without leader dots is prose, not a heading
NUMBER_LIST_SHARE = 0.8
NUMBER_LIST_LINES = 5


@dataclass(frozen=True)
class LabelledValue:
    """One printed "label ..... value" line, with the heading above it."""

    page: int
    heading: str
    label: str
    value: str

    @property
    def quote(self) -> str:
        """The line as printed, with its leader dots shortened to " ... "."""
        return f"{self.label} ... {self.value}"


@dataclass(frozen=True)
class PageReading:
    values: list[LabelledValue]
    number_list_pages: list[int]  # contents pages and quantity lists, left out
    unclear_lines: int  # lines with two runs of leader dots, left out


def slug(text: str, limit: int = 40) -> str:
    """snake_case for a fact key; empty when the text has no letter or digit."""
    return re.sub(r"[^a-z0-9]+", "_", text.casefold()).strip("_")[:limit].strip("_")


def labelled_values(pages: Sequence[dict[str, Any]]) -> PageReading:
    """Read each page's "label ..... value" lines.

    The heading is the nearest short line above without leader dots, and starts again on each
    page. A page headed as a contents page, or whose leader lines are nearly all bare whole
    numbers (page numbers, quantities), is left out and named in ``number_list_pages``.
    """
    values: list[LabelledValue] = []
    number_list_pages: list[int] = []
    unclear = 0
    for page in pages:
        number = int(page["page"])
        lines = [line.strip() for line in str(page.get("text", "")).splitlines()]
        lines = [line for line in lines if line]
        found: list[LabelledValue] = []
        heading = ""
        for line in lines:
            match = LEADER.match(line)
            if match is None:
                if len(line) <= HEADING_LENGTH:
                    heading = line.rstrip(":").strip()
                continue
            label, value = match["label"], match["value"]
            if LEADER_RUN.search(value):  # two columns on one line: which value is whose?
                unclear += 1
                continue
            found.append(LabelledValue(number, heading, label.strip(), value))
        if not found:
            continue
        bare = sum(1 for item in found if item.value.isdigit())
        contents = "contents" in lines[0].casefold()
        if contents or (len(found) >= NUMBER_LIST_LINES and bare / len(found) >= NUMBER_LIST_SHARE):
            number_list_pages.append(number)
            continue
        values.extend(found)
    return PageReading(values, number_list_pages, unclear)


def line_with(text: str, word: str) -> str | None:
    """The first line of ``text`` that prints ``word``, for a citation's quote."""
    for line in text.splitlines():
        if word in line:
            return LEADER_RUN.sub(" ... ", line.strip())
    return None
