"""Tests for banking.loaders.bankwest."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from banking.loaders.bankwest import load_bankwest
from banking.schema import SCHEMA

HEADER = (
    "BSB Number,Account Number,Transaction Date,Narration,Cheque,"
    "Debit,Credit,Balance,Transaction Type"
)


def _write(folder: Path, name: str, rows: list[str]) -> None:
    folder.joinpath(name).write_text(
        "\n".join([HEADER, *rows]) + "\n", encoding="utf-8"
    )


def test_schema_types_and_signed_amount(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "one.csv",
        [
            '306-821,6660836,03/01/2025,"CARD PURCHASE","",20.99,,979.01,WDC',
            '306-821,6660836,02/01/2025,"SALARY","",,1000.00,1000.00,TFC',
        ],
    )

    df = load_bankwest(str(tmp_path))

    assert list(df.columns) == list(SCHEMA)
    assert len(df) == 2

    debit = df.iloc[1]
    credit = df.iloc[0]
    assert debit["date"] == date(2025, 1, 3)
    assert debit["amount"] == Decimal("-20.99")
    assert credit["amount"] == Decimal("1000.00")
    assert isinstance(credit["balance"], Decimal)
    assert credit["bank"] == "Bankwest"
    assert credit["account"] == "306-821/6660836"
    assert credit["type"] == "TFC"
    # Columns Bankwest does not supply are None, never NaN.
    assert debit["payee"] is None and debit["note"] is None


def test_newer_export_replaces_overlapping_span(tmp_path: Path) -> None:
    # Older export: a pending authorisation on 05/01.
    _write(
        tmp_path,
        "old.csv",
        [
            '306-821,6660836,05/01/2025,"AUTHORISATION ONLY - COFFEE","",5.00,,95.00,DAU',
            '306-821,6660836,02/01/2025,"SALARY","",,100.00,100.00,TFC',
        ],
    )
    # Newer export (later max date): the authorisation has settled with a
    # different narration/balance, plus a fresh row.
    _write(
        tmp_path,
        "new.csv",
        [
            '306-821,6660836,06/01/2025,"CARD PURCHASE","",10.00,,84.90,WDC',
            '306-821,6660836,05/01/2025,"COFFEE SHOP","",5.10,,94.90,WDC',
            '306-821,6660836,02/01/2025,"SALARY","",,100.00,100.00,TFC',
        ],
    )

    df = load_bankwest(str(tmp_path))
    narrations = list(df["description"])

    assert "AUTHORISATION ONLY - COFFEE" not in narrations
    assert narrations == ["SALARY", "COFFEE SHOP", "CARD PURCHASE"]
    assert df.iloc[1]["amount"] == Decimal("-5.10")


def test_tie_on_max_date_prefers_more_rows(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "small.csv",
        ['306-821,6660836,10/01/2025,"LATER","",1.00,,9.00,WDC'],
    )
    _write(
        tmp_path,
        "big.csv",
        [
            '306-821,6660836,10/01/2025,"LATER","",1.00,,9.00,WDC',
            '306-821,6660836,09/01/2025,"EARLIER","",2.00,,10.00,WDC',
        ],
    )

    df = load_bankwest(str(tmp_path))

    assert list(df["description"]) == ["EARLIER", "LATER"]


def test_missing_folder_returns_empty_schema_frame(tmp_path: Path) -> None:
    df = load_bankwest(str(tmp_path / "does-not-exist"))

    assert list(df.columns) == list(SCHEMA)
    assert df.empty
