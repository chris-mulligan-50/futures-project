"""Databento client from the environment (Task 1, issue #7).

The API key is read from ``DATABENTO_API_KEY`` only, so it never appears in
code, notebooks or the repository.
"""
from __future__ import annotations

import os

import databento as db

ENV_VAR = "DATABENTO_API_KEY"


def get_client() -> db.Historical:
    """Historical client using the key in ``DATABENTO_API_KEY``."""
    key = os.environ.get(ENV_VAR, "").strip()
    if not key:
        raise RuntimeError(
            f"{ENV_VAR} is not set. Set it in your shell first, e.g. "
            f'export {ENV_VAR}="your-key" (PowerShell: $env:{ENV_VAR}="your-key"). '
            "Never commit the key."
        )
    return db.Historical(key=key)
