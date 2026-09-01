"""Tests for bankcsv.loaders.anz."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from bankcsv.loaders.anz import load_anz
from bankcsv.schema import SCHEMA


def _write(folder: Path, name: str, rows: list[str]) -> None:
    folder.joinpath(name).write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_schema_types_and_field_mapping(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "ANZ.csv",
        [
            '01/06/2026,"-319.00",PAYMENT TO Y,Massyn Super Fun,Y Pty Ltd,,Admin fee,',
            '29/05/2026,"512.67",CREDIT INTEREST PAID,,,,,',
        ],
    )

    df = load_anz(str(tmp_path))

    assert list(df.columns) == list(SCHEMA)
    assert len(df) == 2

    payment = df.iloc[1]
    assert payment["date"] == date(2026, 6, 1)
    assert payment["amount"] == Decimal("-319.00")
    assert payment["bank"] == "ANZ"
    assert payment["account"] == "Massyn Super Fun"
    assert payment["payee"] == "Y Pty Ltd"
    assert payment["note"] == "Admin fee"
    # ANZ exports carry no balance or type.
    assert df["balance"].isna().all()
    assert df["type"].isna().all()

    interest = df.iloc[0]
    assert interest["amount"] == Decimal("512.67")
    assert interest["payee"] is None


def test_span_replacement_keeps_same_day_duplicates(tmp_path: Path) -> None:
    # A single export legitimately lists two identical $10 payments on one day.
    _write(
        tmp_path,
        "ANZ.csv",
        [
            '02/06/2026,"-10.00",PAYSTAY,,,,,',
            '02/06/2026,"-10.00",PAYSTAY,,,,,',
            '01/06/2026,"1875.00",SALARY,,,,,',
        ],
    )

    df = load_anz(str(tmp_path))

    paystay = df[df["description"] == "PAYSTAY"]
    assert len(paystay) == 2


def test_newer_file_replaces_overlap(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "ANZ.csv",
        ['05/06/2026,"-5.00",PENDING THING,,,,,', '01/06/2026,"100.00",SALARY,,,,,'],
    )
    _write(
        tmp_path,
        "ANZ (1).csv",
        [
            '07/06/2026,"-8.00",NEW ROW,,,,,',
            '05/06/2026,"-5.10",SETTLED THING,,,,,',
            '01/06/2026,"100.00",SALARY,,,,,',
        ],
    )

    df = load_anz(str(tmp_path))

    assert list(df["description"]) == ["SALARY", "SETTLED THING", "NEW ROW"]


def test_missing_folder_returns_empty_schema_frame(tmp_path: Path) -> None:
    df = load_anz(str(tmp_path / "nope"))

    assert list(df.columns) == list(SCHEMA)
    assert df.empty
