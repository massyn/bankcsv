"""Bank-agnostic ingestion.

:func:`ingest` walks every CSV under the given path(s) and offers each file to
the registered bank loaders in turn. The first loader that parses the file
cleanly (its whole contents, not just some rows) claims it; if none do, the
file is logged and skipped. Claimed files are merged per bank and concatenated
into one DataFrame on the shared schema.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

import pandas as pd

from banking.loaders import anz, bankwest, cba, macquarie
from banking.loaders._common import PathLike, discover_csv_files
from banking.schema import build_frame

logger = logging.getLogger(__name__)

# Ordered most-specific detector first: the header-matched banks (Bankwest by an
# exact header set, Macquarie by header superset), then the content-shape banks
# (CBA by a 4-field line regex, ANZ by the loosest date+decimal check).
REGISTRY = (bankwest, macquarie, cba, anz)


def ingest(paths: PathLike | Iterable[PathLike]) -> pd.DataFrame:
    """Discover, auto-detect and merge bank CSV exports under ``paths``.

    ``paths`` may be a folder, a single ``.csv`` file, or an iterable of either.
    Returns one DataFrame on :data:`banking.schema.SCHEMA`, sorted by date;
    empty if nothing was recognised.
    """
    claims: dict = {module: [] for module in REGISTRY}

    for f in discover_csv_files(paths):
        for module in REGISTRY:
            rows = module.try_parse(f)
            if rows is not None:
                claims[module].append(rows)
                logger.info("%s -> %s (%d row(s))", f.name, module.BANK, len(rows))
                break
        else:
            logger.warning("No loader recognised %s", f.name)

    frames = [
        build_frame(module.merge(exports))
        for module, exports in claims.items()
        if exports
    ]
    if not frames:
        return build_frame([])

    combined = pd.concat(frames, ignore_index=True)
    return combined.sort_values("date", kind="stable", ignore_index=True)
