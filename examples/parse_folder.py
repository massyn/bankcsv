"""Example: load bank CSV exports into a DataFrame.

Usage:
    python examples/parse_folder.py bankwest path/to/csv/folder
    python examples/parse_folder.py anz path/to/csv/folder
    python examples/parse_folder.py macquarie path/to/csv/folder
    python examples/parse_folder.py cba path/to/csv/folder
    python examples/parse_folder.py ingest path/to/csv/folder   # auto-detect
"""

from __future__ import annotations

import logging
import sys

from dotenv import load_dotenv

from banking import Banking

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)


def main() -> int:
    commands = {"bankwest", "anz", "macquarie", "cba", "ingest"}
    if len(sys.argv) != 3 or sys.argv[1] not in commands:
        print(__doc__)
        return 1

    command, folder = sys.argv[1], sys.argv[2]
    df = getattr(Banking(), command)(folder)

    print(f"\n{len(df)} rows\n")
    print(df.head(20).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
