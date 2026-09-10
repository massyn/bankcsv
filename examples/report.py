"""CLI to ingest bank CSV exports, categorise them, and write an HTML report.

Usage:
    python examples/report.py --csv <folder or .csv> [--mapping mapping.yml] [--output report.html]

``--csv`` is a folder of bank CSV exports (or a single ``.csv`` file). Files are
auto-detected and merged via :func:`bankcsv.ingest` onto the shared schema.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from pathlib import Path

import pandas as pd
from categorise import categorise, load_mapping
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape

from bankcsv import ingest

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)

DEFAULT_MAPPING = Path(__file__).with_name("mapping.yml")
DEFAULT_OUTPUT = Path(__file__).with_name("report.html")
TEMPLATE_DIR = Path(__file__).with_name("templates")


def _coerce_date(value: object) -> dt.date | None:
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else parsed.date()


def _coerce_amount(value: object) -> float | None:
    number = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(number) else float(number)


def add_categories(df: pd.DataFrame, mapping_path: Path) -> pd.DataFrame:
    """Return ``df`` with ``category`` and ``month`` columns."""
    mapping = load_mapping(mapping_path)

    df = df.copy()
    df["category"] = [
        categorise(
            mapping,
            str(narration),
            _coerce_amount(amount),
            _coerce_date(date),
        )
        for narration, amount, date in zip(df["description"], df["amount"], df["date"])
    ]
    df.insert(
        0, "month", pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m")
    )
    return df


MONTHS_SHOWN = 12
HIDDEN_COLUMNS = ("bank", "type", "payee", "note")


def render_report(df: pd.DataFrame) -> str:
    """Render the transactions and a category-by-month sum table as an HTML page.

    The sum table is limited to the most recent ``MONTHS_SHOWN`` months present
    in the data; categories with no activity in that window are dropped.
    """
    amounts = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    pivot = (
        df.assign(amount=amounts)
        .groupby(["category", "month"])["amount"]
        .sum()
        .unstack(fill_value=0.0)
        .sort_index()
    )
    pivot = pivot.reindex(columns=sorted(pivot.columns)[-MONTHS_SHOWN:])
    pivot = pivot.loc[pivot.abs().sum(axis=1) > 0]
    rows = [
        {
            "category": str(category),
            "amounts": [float(pivot.loc[category, m]) for m in pivot.columns],
        }
        for category in pivot.index
    ]

    dates = pd.to_datetime(df["date"], errors="coerce").dropna()
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["money"] = lambda value: (
        f"{float(value):+,.0f}" if round(value) else "0"
    )
    columns = [c for c in df.columns if c not in HIDDEN_COLUMNS]
    return env.get_template("report.html.j2").render(
        months=[str(m) for m in pivot.columns],
        rows=rows,
        month_totals=[float(pivot[m].sum()) for m in pivot.columns],
        columns=columns,
        transactions=df[columns].to_dict("records"),
        transaction_count=len(df),
        date_from=dates.min().date().isoformat() if not dates.empty else "-",
        date_to=dates.max().date().isoformat() if not dates.empty else "-",
        generated_at=dt.datetime.now(dt.timezone.utc)
        .astimezone()
        .strftime("%Y-%m-%d %H:%M"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ingest bank CSV exports, categorise them, and write an HTML report."
    )
    parser.add_argument(
        "--csv",
        required=True,
        type=Path,
        help="Folder of bank CSV exports, or a single .csv file.",
    )
    parser.add_argument(
        "--mapping",
        type=Path,
        default=DEFAULT_MAPPING,
        help=f"Path to the category mapping YAML (default: {DEFAULT_MAPPING}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Path to write the HTML report to (default: {DEFAULT_OUTPUT}).",
    )
    args = parser.parse_args(argv)

    if not args.csv.exists():
        parser.error(f"Path not found: {args.csv}")
    if not args.mapping.is_file():
        parser.error(f"Mapping file not found: {args.mapping}")

    df = ingest(args.csv)
    if df.empty:
        parser.error(f"No recognised bank CSV exports under {args.csv}")

    df = add_categories(df, args.mapping)

    args.output.write_text(render_report(df), encoding="utf-8")
    print(f"Wrote report for {len(df)} transactions to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
