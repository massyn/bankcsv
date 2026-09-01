"""
CBA (Commonwealth Bank) CSV loader.

Reads CBA transaction CSV exports and merges them onto the shared bankcsv
schema (:mod:`bankcsv.schema`) using the date-range replacement strategy.

CBA exports are headerless with four fields per line:

    DD/MM/YYYY,"<signed amount>","<description>","<signed balance>"

A file is recognised by matching that shape on its first few lines. CBA carries
no account identifier in the data (all rows share a single ``None`` account),
but it does carry a running ``Balance``, which disambiguates genuine same-day
repeats, so an exact-duplicate safety net is applied.
"""

from __future__ import annotations

import csv
import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from bankcsv.loaders._common import load_folder, merge_by_account

logger = logging.getLogger(__name__)

BANK = "CBA"

# DD/MM/YYYY,"<signed 2dp>","<description>","<signed 2dp>"
_LINE_RE = re.compile(
    r'^\d{2}/\d{2}/\d{4},"[+-]?\d+\.\d{2}","[^"]*","[+-]?\d+\.\d{2}"$'
)
_DETECT_LINES = 5
_DETECT_RATIO = 0.8

_DEDUP_KEYS = ("account", "date", "description", "amount", "balance")


def _to_unified(line: str) -> dict | None:
    """Map one raw CBA line onto the shared schema, or None if unusable."""
    try:
        row = next(csv.reader([line]))
    except csv.Error:
        return None
    if len(row) != 4:
        return None
    try:
        day, month, year = row[0].strip().split("/")
        txn_date = date(int(year), int(month), int(day))
    except (ValueError, TypeError):
        return None
    try:
        amount = Decimal(row[1].strip())
        balance = Decimal(row[3].strip())
    except InvalidOperation:
        return None
    return {
        "bank": BANK,
        "date": txn_date,
        "amount": amount,
        "description": row[2].strip(),
        "account": None,
        "balance": balance,
        "type": None,
        "payee": None,
        "note": None,
    }


def try_parse(path: Path) -> list[dict] | None:
    """Return unified rows if ``path`` matches the CBA line shape, else None."""
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        logger.debug("cba.try_parse(%s): %s", getattr(path, "name", path), exc)
        return None

    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        return None

    sample = lines[:_DETECT_LINES]
    matched = sum(1 for ln in sample if _LINE_RE.match(ln))
    if not matched or matched / len(sample) < _DETECT_RATIO:
        return None

    rows: list[dict] = []
    for ln in lines:
        parsed = _to_unified(ln)
        if parsed is None:
            return None
        rows.append(parsed)
    return rows


def merge(exports: list[list[dict]]) -> list[dict]:
    """Merge recognised CBA files: date-range replace, then exact-duplicate dedup."""
    return merge_by_account(exports, dedup_keys=_DEDUP_KEYS)


def load_cba(folder: str) -> pd.DataFrame:
    """
    Load and merge CBA CSV exports from ``folder`` (or a single CSV file) into
    one DataFrame on the shared bankcsv schema.

    Files that do not match the CBA layout are skipped with a warning; an empty
    DataFrame is returned when nothing parses.
    """
    return load_folder(folder, bank=BANK, try_parse=try_parse, merge=merge)
