"""Tests for banking.ingest (bank-agnostic auto-detection)."""

from __future__ import annotations

from pathlib import Path

from banking import Banking, ingest
from banking.schema import SCHEMA

BANKWEST_HEADER = (
    "BSB Number,Account Number,Transaction Date,Narration,Cheque,"
    "Debit,Credit,Balance,Transaction Type"
)
BANKWEST_ROW = '306-821,6660836,02/01/2025,"SALARY","",,100.00,100.00,TFC'
ANZ_ROW = '03/01/2025,"-12.34",CARD PURCHASE,,,,,'
MACQUARIE_HEADER = (
    "Transaction Date,Details,Account,Debit,Credit,Balance,"
    "Category,Subcategory,Original Description"
)
MACQUARIE_ROW = "04 Jan 2025,Coffee,Everyday,5.50,,994.50,Food,Cafe,EFTPOS COFFEE"
CBA_ROW = '05/01/2025,"-49.00","EFTPOS STORE","+123.45"'


def _bankwest(folder: Path, name: str) -> None:
    folder.joinpath(name).write_text(
        BANKWEST_HEADER + "\n" + BANKWEST_ROW + "\n", encoding="utf-8"
    )


def _anz(folder: Path, name: str) -> None:
    folder.joinpath(name).write_text(ANZ_ROW + "\n", encoding="utf-8")


def _macquarie(folder: Path, name: str) -> None:
    folder.joinpath(name).write_text(
        MACQUARIE_HEADER + "\n" + MACQUARIE_ROW + "\n", encoding="utf-8"
    )


def _cba(folder: Path, name: str) -> None:
    folder.joinpath(name).write_text(CBA_ROW + "\n", encoding="utf-8")


def test_routes_each_file_by_content_not_name(tmp_path: Path) -> None:
    # Deliberately unhelpful filenames.
    _bankwest(tmp_path, "statement_1.csv")
    _anz(tmp_path, "statement_2.csv")
    _macquarie(tmp_path, "statement_3.csv")
    _cba(tmp_path, "statement_4.csv")
    tmp_path.joinpath("notes.csv").write_text("foo,bar\n1,2\n", encoding="utf-8")

    df = ingest(tmp_path)

    assert list(df.columns) == list(SCHEMA)
    assert len(df) == 4
    assert set(df["bank"]) == {"Bankwest", "ANZ", "Macquarie", "CBA"}
    # concatenated result is date-sorted
    assert list(df["date"]) == sorted(df["date"])


def test_accepts_a_single_file(tmp_path: Path) -> None:
    _anz(tmp_path, "x.csv")

    df = ingest(tmp_path / "x.csv")

    assert len(df) == 1
    assert df.iloc[0]["bank"] == "ANZ"


def test_nothing_recognised_returns_empty_schema_frame(tmp_path: Path) -> None:
    tmp_path.joinpath("junk.csv").write_text("a,b,c\n1,2,3\n", encoding="utf-8")

    df = ingest(tmp_path)

    assert list(df.columns) == list(SCHEMA)
    assert df.empty


def test_banking_ingest_method_matches_function(tmp_path: Path) -> None:
    _bankwest(tmp_path, "a.csv")
    _anz(tmp_path, "b.csv")

    assert Banking().ingest(tmp_path).equals(ingest(tmp_path))
