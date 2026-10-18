"""Local cache for Databento requests (Task 20, issue #26).

Each request is saved once, as the DBN file Databento sent, under the
git-ignored ``data/`` folder. Re-running the same request reads that file
instead of downloading and paying for it again.

Files are keyed by the whole request (dataset, schema, symbols, symbol type,
start and end). Symbol order does not matter, and start and end are compared
as UTC instants, so ``10:00`` Chicago and ``15:00`` UTC share a file.

The cache assumes history does not change once downloaded. To refresh a
request, delete its file. Databento's degraded-data warnings appear only on
the first download, not when reading from the cache.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Callable, Optional, Union

import databento as db
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / "data" / "databento"

PathLike = Union[str, Path]

_UNSAFE = re.compile(r"[^A-Za-z0-9.\-]+")
_MAX_LABEL = 60  # keeps paths well under the Windows limit


def _utc(value: str) -> pd.Timestamp:
    return pd.Timestamp(value).tz_convert("UTC")


def cache_key(params: dict) -> str:
    """Short hash identifying a request; equal for equivalent requests."""
    canonical = dict(
        params,
        symbols=sorted(set(params["symbols"])),
        start=_utc(params["start"]).isoformat(),
        end=_utc(params["end"]).isoformat(),
    )
    text = json.dumps(canonical, sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def cache_path(params: dict, cache_dir: Optional[PathLike] = None) -> Path:
    """File for a request, e.g. ``.../GLBX.MDP3/ohlcv-1d/6EU6_6EZ6_20260810_20260915_<key>.dbn``.

    The readable part is for browsing only; the key makes the name unique.
    """
    root = Path(cache_dir) if cache_dir is not None else CACHE_DIR
    symbols = _UNSAFE.sub("_", "_".join(sorted(set(params["symbols"]))))
    start, end = _utc(params["start"]), _utc(params["end"])
    name = (
        f"{symbols[:_MAX_LABEL]}_{start:%Y%m%d}_{end:%Y%m%d}_{cache_key(params)}.dbn"
    )
    return root / params["dataset"] / params["schema"] / name


def load_or_download(
    params: dict,
    download: Callable[[], db.DBNStore],
    cache_dir: Optional[PathLike] = None,
) -> db.DBNStore:
    """Cached data for ``params``, calling ``download`` only on a miss.

    The file is written under a temporary name and renamed when complete,
    so an interrupted download never leaves a file that looks valid.
    """
    path = cache_path(params, cache_dir)
    if path.exists():
        return db.DBNStore.from_file(path)

    store = download()
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    try:
        store.to_file(partial)
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)
    return store
