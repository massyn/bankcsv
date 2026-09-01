"""Per-bank statement loaders.

Each module exposes:

* ``BANK``       - the bank's display name
* ``try_parse(path) -> list[dict] | None`` - parse the *whole* file to unified
  rows, or return None if it is not this bank's format
* ``merge(exports) -> list[dict]`` - reconcile overlapping files for this bank
* ``load_<bank>(folder) -> pandas.DataFrame`` - the single-bank convenience call
"""

from __future__ import annotations

from bankcsv.loaders.anz import load_anz
from bankcsv.loaders.bankwest import load_bankwest
from bankcsv.loaders.cba import load_cba
from bankcsv.loaders.macquarie import load_macquarie

__all__ = ["load_anz", "load_bankwest", "load_cba", "load_macquarie"]
