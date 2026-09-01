"""
Macquarie CSV loader.

Reads Macquarie transaction CSV exports and merges them onto the shared bankcsv
schema (:mod:`bankcsv.schema`) using the date-range replacement strategy.

A file is recognised as Macquarie by its header row: the core columns
(``Transaction Date``, ``Details``, ``Account``, ``Debit``, ``Credit``,
``Balance``) plus at least two of Macquarie's own extras (``Category``,
``Subcategory``, ``Original Description``) which set it apart from other
Debit/Credit layouts. Macquarie has no BSB; the ``Account`` column is used as
the account identifier and the running ``Balance`` disambiguates same-day
repeats. ``Transaction Date`` is ``DD Mon YYYY`` (e.g. ``12 Sep 2025``).

The ``Category`` / ``Subcategory`` / ``Original Description`` columns are used
only for detection - they are not carried into the output.
"""

from __future__ import annotations

import csv
import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from bankcsv.loaders._common import load_folder, merge_by_account

logger = logging.getLogger(__name__)

BANK = "Macquarie"

_REQUIRED_FIELDS = {
    "Transaction Date",
    "Details",
    "Account",
    "Debit",
    "Credit",
    "Balance",
}
_SPECIFIC_FIELDS = {"Category", "Subcategory", "Original Description"}

_DEDUP_KEYS = ("account", "date", "description", "amount", "balance")

_MONTHS = {
    name: number
    for number, name in enumerate(
        (
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ),
        start=1,
    )
}


def _parse_date(raw: str) -> date:
    """Parse a 'DD Mon YYYY' string (e.g. '12 Sep 2025'); date.min if invalid."""
    parts = raw.strip().strip('"').split()
    try:
        day, month, year = parts
        return date(int(year), _MONTHS[month[:3].title()], int(day))
    except (ValueError, KeyError):
        return date.min


def _money(raw: str) -> Decimal:
    """Parse a decimal string; empty means zero."""
    text = raw.strip().strip('"').replace(",", "")
    return Decimal(text) if text else Decimal(0)


def _to_unified(raw: dict) -> dict:
    """Map one raw Macquarie CSV row onto the shared schema."""
    account = raw.get("Account", "").strip().strip('"')
    balance = raw.get("Balance", "").strip().strip('"').replace(",", "")
    return {
        "bank": BANK,
        "date": _parse_date(raw.get("Transaction Date", "")),
        "amount": _money(raw.get("Credit", "")) - _money(raw.get("Debit", "")),
        "description": raw.get("Details", "").strip().strip('"'),
        "account": account,
        "balance": Decimal(balance) if balance else None,
        "type": None,
        "payee": None,
        "note": None,
    }


def try_parse(path: Path) -> list[dict] | None:
    """Return unified rows if ``path`` is a clean Macquarie export, else None."""
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fields = set(reader.fieldnames or [])
            if not _REQUIRED_FIELDS <= fields:
                return None
            if len(_SPECIFIC_FIELDS & fields) < 2:
                return None
            return [_to_unified(raw) for raw in reader]
    except (
        OSError,
        csv.Error,
        UnicodeDecodeError,
        InvalidOperation,
        ValueError,
    ) as exc:
        logger.debug("macquarie.try_parse(%s): %s", getattr(path, "name", path), exc)
        return None


def merge(exports: list[list[dict]]) -> list[dict]:
    """Merge recognised Macquarie files: per account, date-range replace, dedup."""
    return merge_by_account(exports, dedup_keys=_DEDUP_KEYS)


def load_macquarie(folder: str) -> pd.DataFrame:
    """
    Load and merge Macquarie CSV exports from ``folder`` (or a single CSV file)
    into one DataFrame on the shared bankcsv schema.

    Files whose header is not the Macquarie layout are skipped with a warning;
    an empty DataFrame is returned when nothing parses.
    """
    return load_folder(folder, bank=BANK, try_parse=try_parse, merge=merge)
