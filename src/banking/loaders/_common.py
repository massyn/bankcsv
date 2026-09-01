"""Shared plumbing for the per-bank loaders.

Nothing here knows about a specific bank; the bank modules pass their own
``try_parse`` / ``merge`` callables into :func:`load_folder`.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import date
from pathlib import Path

import pandas as pd

from banking.schema import build_frame

logger = logging.getLogger(__name__)

PathLike = str | Path


def discover_csv_files(paths: PathLike | Iterable[PathLike]) -> list[Path]:
    """Resolve ``paths`` to an ordered, de-duplicated list of ``.csv`` files.

    Each entry may be a folder (its top-level ``*.csv`` files are taken) or a
    single ``.csv`` file. Anything else is logged and skipped.
    """
    if isinstance(paths, (str, Path)):
        paths = [paths]

    found: list[Path] = []
    seen: set[Path] = set()
    for entry in paths:
        p = Path(entry).expanduser()
        if p.is_dir():
            candidates = [
                c
                for c in sorted(p.iterdir())
                if c.is_file() and c.suffix.lower() == ".csv"
            ]
        elif p.is_file() and p.suffix.lower() == ".csv":
            candidates = [p]
        else:
            logger.warning("Not a CSV file or folder: %s", p)
            continue

        for c in candidates:
            key = c.resolve()
            if key not in seen:
                seen.add(key)
                found.append(c)
    return found


def merge_span(exports: list[list[dict]]) -> list[dict]:
    """
    Merge row-lists, applied in the given (oldest-first) order, using the
    date-range replacement strategy: for each export, evict in-memory rows on
    or after its oldest transaction date, then append its rows. Sorted ascending.
    """
    memory: list[dict] = []
    for rows in exports:
        oldest = min(r["date"] for r in rows)
        memory = [r for r in memory if r["date"] < oldest]
        memory.extend(rows)
    memory.sort(key=lambda r: r["date"])
    return memory


def merge_by_account(
    exports: list[list[dict]],
    *,
    dedup_keys: tuple[str, ...] = (),
) -> list[dict]:
    """
    Merge exports for banks that carry a per-row ``account`` and a running
    ``balance``.

    Rows are grouped by ``account`` (a single ``None`` bucket is fine). Within
    each account the source files are ordered by their latest transaction date
    (row count breaks ties) and applied newest-last via :func:`merge_span`.
    Rows with an unparseable date (``date.min``) are dropped. If ``dedup_keys``
    is given, a final pass removes rows identical across those fields - safe
    only where a running balance disambiguates genuine same-day repeats.
    """
    catalogue: dict[object, list[tuple[date, int, list[dict]]]] = defaultdict(list)
    for rows in exports:
        by_account: dict[object, list[dict]] = defaultdict(list)
        for row in rows:
            by_account[row["account"]].append(row)
        for account, account_rows in by_account.items():
            dated = [r for r in account_rows if r["date"] != date.min]
            if not dated:
                logger.warning("Export for account %s has no parseable dates", account)
                continue
            catalogue[account].append(
                (max(r["date"] for r in dated), len(dated), dated)
            )

    result: list[dict] = []
    for slices in catalogue.values():
        slices.sort(key=lambda entry: (entry[0], entry[1]))
        result.extend(merge_span([rows for _, _, rows in slices]))
    result.sort(key=lambda r: r["date"])

    if not dedup_keys:
        return result

    seen: set[tuple] = set()
    deduped: list[dict] = []
    for row in result:
        key = tuple(row[k] for k in dedup_keys)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def load_folder(
    paths: PathLike | Iterable[PathLike],
    *,
    bank: str,
    try_parse: Callable[[Path], list[dict] | None],
    merge: Callable[[list[list[dict]]], list[dict]],
) -> pd.DataFrame:
    """Parse every CSV under ``paths`` with one bank's ``try_parse``, then merge.

    Files that ``try_parse`` rejects are skipped with a warning. Returns a
    DataFrame on the shared schema (empty if nothing parsed).
    """
    exports: list[list[dict]] = []
    for f in discover_csv_files(paths):
        rows = try_parse(f)
        if rows is None:
            logger.warning("%s: not a %s export, skipping", f.name, bank)
            continue
        exports.append(rows)
    return build_frame(merge(exports))
