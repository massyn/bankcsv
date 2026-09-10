"""Match transactions to categories using a YAML mapping file.

The mapping file (default: ``examples/mapping.yml``, override with ``--mapping``)
maps a category name to a list of rule blocks. A category matches a transaction
if any of its rule blocks match. A rule block matches when:

* the narration matches its wildcard pattern (mandatory), and
* the amount falls in its range, if an amount constraint is given, and
* the date falls in its range, if a date constraint is given.

When several categories match, the one whose matching rule group carries the
most optional constraints (amount, date) wins -- the closest, most specific
match. Ties are broken by order of appearance in the mapping file.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

import yaml

UNKNOWN = "unknown"


@dataclass(frozen=True)
class RuleBlock:
    """One way a category can be recognised."""

    narration: str
    amount: tuple[float, float] | None
    date: tuple[dt.date, dt.date] | None

    @property
    def specificity(self) -> int:
        return (self.amount is not None) + (self.date is not None)

    def matches(
        self,
        narration: str,
        amount: float | None,
        date: dt.date | None,
    ) -> bool:
        narration = (narration or "").upper()
        if not fnmatchcase(narration, self.narration):
            return False
        if self.amount is not None and (
            amount is None or not self.amount[0] <= amount <= self.amount[1]
        ):
            return False
        return self.date is None or (
            date is not None and self.date[0] <= date <= self.date[1]
        )


def _as_range(value: object) -> tuple[float, float]:
    if isinstance(value, (list, tuple)):
        low, high = float(value[0]), float(value[1])
        return (min(low, high), max(low, high))
    number = float(value)  # type: ignore[arg-type]
    return (number, number)


def _as_date(value: object) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value))


def _as_date_range(value: object) -> tuple[dt.date, dt.date]:
    if isinstance(value, (list, tuple)):
        low, high = _as_date(value[0]), _as_date(value[1])
        return (min(low, high), max(low, high))
    single = _as_date(value)
    return (single, single)


def load_mapping(path: Path) -> dict[str, list[RuleBlock]]:
    """Parse the YAML mapping file into rule blocks per category."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise TypeError(f"Mapping file must be a mapping of categories: {path}")

    mapping: dict[str, list[RuleBlock]] = {}
    for category, blocks in raw.items():
        if not isinstance(blocks, list):
            raise TypeError(f"Category {category!r} must hold a list of rule blocks")
        rules: list[RuleBlock] = []
        for block in blocks:
            if "narration" not in block:
                raise ValueError(f"Category {category!r} has a block with no narration")
            rules.append(
                RuleBlock(
                    narration=str(block["narration"]).upper(),
                    amount=_as_range(block["amount"]) if "amount" in block else None,
                    date=_as_date_range(block["date"]) if "date" in block else None,
                )
            )
        mapping[category] = rules
    return mapping


def categorise(
    mapping: dict[str, list[RuleBlock]],
    narration: str,
    amount: float | None = None,
    date: dt.date | None = None,
) -> str:
    """Return the best-matching category name, or ``UNKNOWN``."""
    best_category = UNKNOWN
    best_specificity = -1
    for category, rules in mapping.items():
        for rule in rules:
            if (
                rule.matches(narration, amount, date)
                and rule.specificity > best_specificity
            ):
                best_category = category
                best_specificity = rule.specificity
    return best_category
