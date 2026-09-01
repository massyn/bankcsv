"""Shared transaction schema for all bank loaders.

Every loader returns a :class:`pandas.DataFrame` with these nine columns, in
this order. The columns are always present (mandatory). ``bank``, ``date``,
``amount`` and ``description`` are additionally guaranteed non-null on every
row; the rest are ``None`` where the source does not supply them.

Money is normalised to a single signed ``decimal.Decimal`` (credit positive,
debit negative); ``date`` is a ``datetime.date``. The frame is object dtype
throughout and gaps are Python ``None`` (never ``NaN``), so ``Decimal`` columns
stay exact and ``x is None`` works. An optional column that is ``None`` on
every row means that bank does not expose it.
"""

from __future__ import annotations

import pandas as pd

SCHEMA: tuple[str, ...] = (
    "bank",
    "date",
    "amount",
    "description",
    "account",
    "balance",
    "type",
    "payee",
    "note",
)


def build_frame(rows: list[dict]) -> pd.DataFrame:
    """Assemble ``rows`` into a schema DataFrame with ``None`` (not ``NaN``) gaps."""
    df = pd.DataFrame(rows, columns=SCHEMA).astype("object")
    return df.where(df.notna(), None)
