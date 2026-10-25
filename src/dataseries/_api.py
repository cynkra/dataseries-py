"""Low-level access to the dataseries.org API plus a simple in-memory cache.

Everything fetched from the API (catalog, metadata, series) is cached by URL
for the lifetime of the Python process, so repeated calls are free. Use
:func:`dataseries.cache_clear` to force a fresh download.
"""

from __future__ import annotations

import io
import json
import os
import urllib.error
import urllib.request

from ._version import __version__

_cache: dict[str, object] = {}

_USER_AGENT = f"dataseries-py/{__version__} (https://github.com/cynkra/dataseries-py)"


def api_url() -> str:
    """Base URL of the dataseries.org API.

    Override for testing or self-hosting via the ``DATASERIES_API``
    environment variable.
    """
    return os.environ.get("DATASERIES_API", "https://api.dataseries.org").rstrip("/")


def _fetch(path: str) -> str:
    url = api_url() + path
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8")
    except (urllib.error.URLError, OSError) as err:
        raise ConnectionError(
            f"could not reach the dataseries.org API ({url}): {err}"
        ) from err


def get_json(path: str, cache: bool = True):
    """GET a path and parse the JSON body."""
    key = "json:" + path
    if cache and key in _cache:
        return _cache[key]
    out = json.loads(_fetch(path))
    if cache:
        _cache[key] = out
    return out


def get_csv(path: str, cache: bool = True):
    """GET a /series.csv path and read it as a pandas DataFrame.

    All columns are read as strings (dimension codes such as ``"100_100"``
    must not be coerced to numbers) and no default NA markers are applied,
    so codes like ``"NA"`` or ``"null"`` stay verbatim. Only an empty
    ``value`` field is missing. ``date`` and ``value`` are converted by the
    caller.
    """
    import pandas as pd

    key = "csv:" + path
    if cache and key in _cache:
        return _cache[key].copy()
    out = pd.read_csv(
        io.StringIO(_fetch(path)),
        dtype=str,
        keep_default_na=False,
        na_values={"value": [""]},
    )
    if cache:
        _cache[key] = out
    return out.copy()


def cache_keys() -> list[str]:
    """List the cached requests (keyed by request path)."""
    return sorted(_cache)


def cache_clear() -> None:
    """Empty the in-memory cache, forcing fresh downloads on the next call."""
    _cache.clear()
