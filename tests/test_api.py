"""Tests for the bankcsv.Banking entry point."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from bankcsv import Banking, load_anz, load_bankwest
from bankcsv.schema import SCHEMA

BANKWEST_HEADER = (
    "BSB Number,Account Number,Transaction Date,Narration,Cheque,"
    "Debit,Credit,Balance,Transaction Type"
)


def _make_folders(tmp_path: Path) -> tuple[Path, Path]:
    bw = tmp_path / "bankwest"
    az = tmp_path / "anz"
    bw.mkdir()
    az.mkdir()
    bw.joinpath("bw.csv").write_text(
        BANKWEST_HEADER
        + '\n306-821,6660836,02/01/2025,"SALARY","",,100.00,100.00,TFC\n',
        encoding="utf-8",
    )
    az.joinpath("ANZ.csv").write_text(
        '02/01/2025,"-12.34",CARD PURCHASE,,,,,\n', encoding="utf-8"
    )
    return bw, az


def test_methods_delegate_to_loaders(tmp_path: Path) -> None:
    bw, az = _make_folders(tmp_path)
    b = Banking()

    assert b.bankwest(str(bw)).equals(load_bankwest(str(bw)))
    assert b.anz(str(az)).equals(load_anz(str(az)))


def test_frames_share_schema_and_concatenate(tmp_path: Path) -> None:
    bw, az = _make_folders(tmp_path)
    b = Banking()

    bw_df = b.bankwest(str(bw))
    az_df = b.anz(str(az))
    assert list(bw_df.columns) == list(SCHEMA)
    assert list(az_df.columns) == list(SCHEMA)

    combined = pd.concat([bw_df, az_df], ignore_index=True)
    assert list(combined.columns) == list(SCHEMA)
    assert set(combined["bank"]) == {"Bankwest", "ANZ"}
