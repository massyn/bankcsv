"""
Bankwest CSV loader.

Reads Bankwest transaction CSV exports and merges them onto the shared bankcsv
schema (:mod:`bankcsv.schema`) using the date-range replacement strategy: a
newer export is authoritative over every transaction date it covers, so its
rows overwrite anything an older export said about that span (this is how
pending "AUTHORISATION ONLY" rows get replaced by their settled versions).

The filename is not trusted. A file is recognised as Bankwest purely by its
header row; account identity and export recency are derived from the row data:

  * account   -> "<BSB Number>/<Account Number>" from the row columns
  * recency   -> the latest Transaction Date present in the file; on a tie
                 (a re-download with no new activity) the file with the most
                 rows wins
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

BANK = "Bankwest"

_EXPECTED_FIELDS = {
    "BSB Number",
    "Account Number",
    "Transaction Date",
    "Narration",
    "Cheque",
    "Debit",
    "Credit",
    "Balance",
    "Transaction Type",
}

# Unified fields compared to drop exact-duplicate rows left at export boundaries.
_DEDUP_KEYS = ("account", "date", "description", "amount", "balance", "type")


def _parse_date(raw: str) -> date:
    """Parse a DD/MM/YYYY string; return date.min if absent or invalid."""
    try:
        day, month, year = raw.strip().split("/")
        return date(int(year), int(month), int(day))
    except (ValueError, TypeError):
        return date.min


def _money(raw: str) -> Decimal:
    """Parse a decimal string; empty means zero."""
    raw = raw.strip()
    return Decimal(raw) if raw else Decimal(0)


def _to_unified(raw: dict) -> dict:
    """Map one raw Bankwest CSV row onto the shared schema."""
    bsb = raw.get("BSB Number", "").strip()
    account = raw.get("Account Number", "").strip()
    balance = raw.get("Balance", "").strip()
    return {
        "bank": BANK,
        "date": _parse_date(raw.get("Transaction Date", "")),
        "amount": _money(raw.get("Credit", "")) - _money(raw.get("Debit", "")),
        "description": raw.get("Narration", "").strip(),
        "account": f"{bsb}/{account}" if bsb or account else "",
        "balance": Decimal(balance) if balance else None,
        "type": raw.get("Transaction Type", "").strip() or None,
        "payee": None,
        "note": None,
    }


def try_parse(path: Path) -> list[dict] | None:
    """Return unified rows if ``path`` is a clean Bankwest export, else None."""
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or set(reader.fieldnames) != _EXPECTED_FIELDS:
                return None
            return [_to_unified(raw) for raw in reader]
    except (
        OSError,
        csv.Error,
        UnicodeDecodeError,
        InvalidOperation,
        ValueError,
    ) as exc:
        logger.debug("bankwest.try_parse(%s): %s", getattr(path, "name", path), exc)
        return None


def merge(exports: list[list[dict]]) -> list[dict]:
    """Merge recognised Bankwest files: per account, date-range replace, dedup."""
    return merge_by_account(exports, dedup_keys=_DEDUP_KEYS)


def load_bankwest(folder: str) -> pd.DataFrame:
    """
    Load and merge Bankwest CSV exports from ``folder`` (or a single CSV file)
    into one DataFrame on the shared bankcsv schema.

    Files whose header is not the Bankwest layout are skipped with a warning;
    an empty DataFrame is returned when nothing parses.
    """
    return load_folder(folder, bank=BANK, try_parse=try_parse, merge=merge)
