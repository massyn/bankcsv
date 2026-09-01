"""bankcsv — bank CSV statement ingestion.

Point a loader at a folder of a bank's CSV exports and get back a single
:class:`pandas.DataFrame` with every statement row merged, overlapping
downloads reconciled by date-range replacement, and columns normalised to the
shared schema (:mod:`bankcsv.schema`).

    from bankcsv import Banking

    b = Banking()
    df = b.bankwest("~/iCloudDrive/Bankwest")   # this folder is Bankwest
    df = b.anz("~/Downloads")                    # this folder is ANZ
    df = b.ingest("~/Downloads")                 # auto-detect each file's bank

The ``load_bankwest`` / ``load_anz`` / ``ingest`` functions are also exported
for direct use.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from bankcsv.ingest import ingest
from bankcsv.loaders import load_anz, load_bankwest, load_cba, load_macquarie
from bankcsv.loaders._common import PathLike
from bankcsv.schema import SCHEMA, build_frame

__version__ = "0.0.1"

__all__ = [
    "SCHEMA",
    "Banking",
    "__version__",
    "build_frame",
    "ingest",
    "load_anz",
    "load_bankwest",
    "load_cba",
    "load_macquarie",
]


class Banking:
    """Entry point for loading bank statement exports into the common schema.

    Each method returns a :class:`pandas.DataFrame` on
    :data:`bankcsv.schema.SCHEMA`. Frames from different banks share the same
    columns, so they can be concatenated directly.
    """

    def bankwest(self, folder: str) -> pd.DataFrame:
        """Load a folder of Bankwest CSV exports. See :func:`bankcsv.load_bankwest`."""
        return load_bankwest(folder)

    def anz(self, folder: str) -> pd.DataFrame:
        """Load a folder of ANZ CSV exports. See :func:`bankcsv.load_anz`."""
        return load_anz(folder)

    def macquarie(self, folder: str) -> pd.DataFrame:
        """Load a folder of Macquarie CSV exports. See :func:`bankcsv.load_macquarie`."""
        return load_macquarie(folder)

    def cba(self, folder: str) -> pd.DataFrame:
        """Load a folder of CBA CSV exports. See :func:`bankcsv.load_cba`."""
        return load_cba(folder)

    def ingest(self, paths: PathLike | Iterable[PathLike]) -> pd.DataFrame:
        """Auto-detect and merge mixed bank CSV exports. See :func:`bankcsv.ingest`."""
        return ingest(paths)
