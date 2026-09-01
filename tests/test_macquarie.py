"""Tests for bankcsv.loaders.macquarie."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from bankcsv.loaders.macquarie import load_macquarie, try_parse
from bankcsv.schema import SCHEMA

HEADER = (
    "Transaction Date,Details,Account,Debit,Credit,Balance,"
    "Category,Subcategory,Original Description"
)


def _write(folder: Path, name: str, rows: list[str]) -> None:
    folder.joinpath(name).write_text(
        "\n".join([HEADER, *rows]) + "\n", encoding="utf-8"
    )


def test_schema_types_and_signed_amount(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "mq.csv",
        [
            "13 Sep 2025,Salary,Everyday,,2000.00,2994.50,Income,Salary,ACME PAYROLL",
            "12 Sep 2025,Coffee Shop,Everyday,5.50,,994.50,Food,Cafe,EFTPOS COFFEE",
        ],
    )

    df = load_macquarie(str(tmp_path))

    assert list(df.columns) == list(SCHEMA)
    assert len(df) == 2

    coffee = df.iloc[0]
    salary = df.iloc[1]
    assert coffee["date"] == date(2025, 9, 12)
    assert coffee["amount"] == Decimal("-5.50")
    assert salary["amount"] == Decimal("2000.00")
    assert coffee["bank"] == "Macquarie"
    assert coffee["account"] == "Everyday"
    assert isinstance(coffee["balance"], Decimal)
    assert coffee["type"] is None and coffee["payee"] is None and coffee["note"] is None


def test_detection_needs_macquarie_specific_headers(tmp_path: Path) -> None:
    # Core columns only, missing Category/Subcategory/Original Description.
    plain = tmp_path / "plain.csv"
    plain.write_text(
        "Transaction Date,Details,Account,Debit,Credit,Balance\n"
        "12 Sep 2025,Coffee,Everyday,5.50,,994.50\n",
        encoding="utf-8",
    )
    assert try_parse(plain) is None


def test_newer_export_replaces_overlapping_span(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "old.csv",
        [
            "05 Jan 2025,Pending Coffee,Everyday,5.00,,95.00,Food,Cafe,PENDING",
            "02 Jan 2025,Opening,Everyday,,100.00,100.00,Income,Other,OPENING",
        ],
    )
    _write(
        tmp_path,
        "new.csv",
        [
            "06 Jan 2025,Groceries,Everyday,10.00,,84.90,Food,Super,GROCER",
            "05 Jan 2025,Coffee Shop,Everyday,5.10,,94.90,Food,Cafe,COFFEE",
            "02 Jan 2025,Opening,Everyday,,100.00,100.00,Income,Other,OPENING",
        ],
    )

    df = load_macquarie(str(tmp_path))

    assert list(df["description"]) == ["Opening", "Coffee Shop", "Groceries"]


def test_missing_folder_returns_empty_schema_frame(tmp_path: Path) -> None:
    df = load_macquarie(str(tmp_path / "nope"))

    assert list(df.columns) == list(SCHEMA)
    assert df.empty
