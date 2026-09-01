"""Tests for banking.loaders.cba."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from banking.loaders.cba import load_cba, try_parse
from banking.schema import SCHEMA


def _write(folder: Path, name: str, rows: list[str]) -> None:
    folder.joinpath(name).write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_schema_types_and_signed_amount(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "cba.csv",
        [
            '03/01/2025,"-12.34","EFTPOS BAKERY","+987.66"',
            '02/01/2025,"+1000.00","SALARY","+1000.00"',
        ],
    )

    df = load_cba(str(tmp_path))

    assert list(df.columns) == list(SCHEMA)
    assert len(df) == 2

    bakery = df.iloc[1]
    salary = df.iloc[0]
    assert bakery["date"] == date(2025, 1, 3)
    assert bakery["amount"] == Decimal("-12.34")
    assert bakery["balance"] == Decimal("987.66")
    assert salary["amount"] == Decimal("1000.00")
    assert bakery["bank"] == "CBA"
    assert bakery["account"] is None
    assert bakery["type"] is None and bakery["payee"] is None


def test_rejects_non_cba_shape(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("03/01/2025,not,a,cba,row\n", encoding="utf-8")
    assert try_parse(bad) is None


def test_newer_export_replaces_and_dedupes(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "old.csv",
        [
            '05/01/2025,"-5.00","PENDING","+95.00"',
            '02/01/2025,"+100.00","OPENING","+100.00"',
        ],
    )
    _write(
        tmp_path,
        "new.csv",
        [
            '06/01/2025,"-8.00","SHOP","+81.90"',
            '05/01/2025,"-5.10","COFFEE","+89.90"',
            '02/01/2025,"+100.00","OPENING","+100.00"',
        ],
    )

    df = load_cba(str(tmp_path))

    assert list(df["description"]) == ["OPENING", "COFFEE", "SHOP"]
    assert len(df) == 3


def test_missing_folder_returns_empty_schema_frame(tmp_path: Path) -> None:
    df = load_cba(str(tmp_path / "nope"))

    assert list(df.columns) == list(SCHEMA)
    assert df.empty
