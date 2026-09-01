"""
ANZ CSV loader.

Reads ANZ transaction CSV exports and merges them onto the shared banking
schema (:mod:`banking.schema`) using the same date-range replacement strategy
as the Bankwest loader: a newer export is authoritative over every transaction
date it covers, so its rows replace whatever an older export said about that
span.

ANZ exports are headerless with 8 positional fields; columns 5 and 7 are always
empty. A file is recognised as ANZ purely by its content (every row: >= 7
fields, a DD/MM/YYYY date in col[0] and a signed decimal in col[1]). There is
no account number or running balance in the data, so all rows are treated as
one account and duplicates are never key-matched away - overlap is resolved
purely by span replacement, which keeps legitimate same-day repeats intact.
"""

from __future__ import annotations

import csv
import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from banking.loaders._common import load_folder, merge_span

logger = logging.getLogger(__name__)

BANK = "ANZ"

# Minimum field count for a usable ANZ record (col[6] is the last one we read).
_RAW_MIN_FIELDS = 7


def _to_unified(raw: list[str]) -> dict | None:
    """Map one raw ANZ record onto the shared schema, or None if unusable."""
    if len(raw) < _RAW_MIN_FIELDS:
        return None
    try:
        day, month, year = raw[0].strip().split("/")
        txn_date = date(int(year), int(month), int(day))
    except (ValueError, TypeError):
        return None
    try:
        amount = Decimal(raw[1].strip().strip('"'))
    except (InvalidOperation, AttributeError):
        return None
    return {
        "bank": BANK,
        "date": txn_date,
        "amount": amount,
        "description": raw[2].strip(),
        "account": raw[3].strip() or None,
        "balance": None,
        "type": None,
        "payee": raw[4].strip() or None,
        "note": raw[6].strip() or None,
    }


def try_parse(path: Path) -> list[dict] | None:
    """Return unified rows if every line of ``path`` is a clean ANZ record."""
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            raw_rows = [r for r in csv.reader(f) if r and any(c.strip() for c in r)]
    except (OSError, csv.Error, UnicodeDecodeError) as exc:
        logger.debug("anz.try_parse(%s): %s", getattr(path, "name", path), exc)
        return None

    if not raw_rows:
        return None

    rows: list[dict] = []
    for raw in raw_rows:
        parsed = _to_unified(raw)
        if parsed is None:
            return None
        rows.append(parsed)
    return rows


def merge(exports: list[list[dict]]) -> list[dict]:
    """Merge recognised ANZ files by latest date (row count breaks ties)."""
    catalogue: list[tuple[date, int, list[dict]]] = []
    for rows in exports:
        if not rows:
            continue
        catalogue.append((max(r["date"] for r in rows), len(rows), rows))
    catalogue.sort(key=lambda entry: (entry[0], entry[1]))
    return merge_span([rows for _, _, rows in catalogue])


def load_anz(folder: str) -> pd.DataFrame:
    """
    Load and merge ANZ CSV exports from ``folder`` (or a single CSV file) into
    one DataFrame on the shared banking schema.

    Files that do not match the ANZ layout are skipped with a warning; an empty
    DataFrame is returned when nothing parses.
    """
    return load_folder(folder, bank=BANK, try_parse=try_parse, merge=merge)
