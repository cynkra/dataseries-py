"""User-facing functions: ds(), ds_catalog(), ds_search(), ds_meta()."""

from __future__ import annotations

from typing import Optional, Union
from urllib.parse import quote

from . import _api
from ._labels import check_lang, label, scalar, source_name

DimValue = Union[str, "list[str]", "tuple[str, ...]"]


def _build_dims(dims: dict) -> str:
    """Build the dims grammar string ("item=100_100,100_1;type=real")."""
    parts = []
    for name, value in dims.items():
        if isinstance(value, str):
            codes = [value]
        else:
            codes = [str(v) for v in value]
        parts.append(f"{name}={','.join(codes)}")
    return ";".join(parts)


def ds(
    dataset: str,
    dims: Optional[dict] = None,
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
    wide: bool = False,
    **dim_filters: DimValue,
):
    """Download time series from dataseries.org.

    Data on `dataseries.org <https://dataseries.org>`_ is organized into
    **datasets**. A dataset is a family of related series and is, in most
    cases, a multi-dimensional *cube*: a single time series is one cell of
    the cube, addressed by the dataset plus one code per dimension. Pass
    those codes as **keyword arguments** (the names are the dimension names,
    see :func:`ds_meta`)::

        ds("ch_seco_gdp", type="real", structure="gdp", seas_adj="csa")

    Dimension arguments are optional. Omit them and you get the whole
    dataset (all series, in long format). A few datasets are a single series
    and take no dimensions at all (e.g. ``ds("ch_kof_barometer")``).
    Filtering happens on the server, so selecting one series does not
    download the whole cube.

    Downloads are **cached in memory** for the session. Run
    :func:`cache_clear` to force a fresh download.

    Parameters
    ----------
    dataset : str
        A single dataset ``id``, as listed by :func:`ds_catalog`.
    dims : dict, optional
        Dimension filters as a dict, e.g. ``{"type": "real"}``. Convenient
        programmatically (e.g. built from a :func:`ds_search` result row).
        Merged with, and overridden by, keyword filters.
    start, end : str, optional
        ISO ``"YYYY-MM-DD"`` date bounds that restrict the returned range,
        inclusive.
    wide : bool, default False
        Return one column per series (a wide DataFrame indexed by date,
        column names are the dimension codes joined by ``"."``) instead of
        the long format.
    **dim_filters
        Dimension filters, e.g. ``type="real"`` or
        ``structure=["gdp", "gva"]``. See :func:`ds_meta` for the available
        dimensions and codes.

    Returns
    -------
    pandas.DataFrame or None
        Long format (default): one row per observation, with the dimension
        column(s), then ``date`` (datetime) and ``value`` (float). Wide
        format: one column per series, indexed by date. ``None`` if the
        selection is empty.

    Examples
    --------
    >>> ds("ch_fso_cpi")                                       # doctest: +SKIP
    >>> ds("ch_fso_cpi", item="100_100")                       # doctest: +SKIP
    >>> ds("ch_fso_cpi", item=["100_100", "100_1"],
    ...    start="2020-01-01")                                 # doctest: +SKIP
    >>> ds("ch_seco_gdp", type="real", structure="gdp",
    ...    seas_adj="csa", wide=True)                          # doctest: +SKIP

    See Also
    --------
    ds_catalog : the list of datasets
    ds_meta : a dataset's dimensions and codes
    ds_search : find individual series across all datasets
    """
    import pandas as pd

    if not isinstance(dataset, str) or not dataset:
        raise TypeError("dataset must be a non-empty string")

    filters = dict(dims or {})
    filters.update(dim_filters)

    qs = [f"dataset={quote(dataset, safe='')}"]
    spec = _build_dims(filters)
    if spec:
        qs.append(f"dims={quote(spec, safe='')}")
    if start is not None:
        qs.append(f"from={start}")
    if end is not None:
        qs.append(f"to={end}")

    df = _api.get_csv("/series.csv?" + "&".join(qs))

    # The API answers an unknown/empty dataset with a one-column "error" CSV.
    if "error" in df.columns and "value" not in df.columns:
        raise ValueError(
            f"dataseries.org API: {df['error'].iloc[0]} (dataset {dataset!r})"
        )
    if not {"date", "value"}.issubset(df.columns):
        raise ValueError(f"unexpected response for dataset {dataset!r}")
    if df.empty:
        return None

    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"])
    dimcols = [c for c in df.columns if c not in ("date", "value")]
    df = df[dimcols + ["date", "value"]].sort_values("date", kind="stable")
    df = df.reset_index(drop=True)

    if wide:
        return _to_wide(df, dimcols)
    return df


def _to_wide(df, dimcols: list):
    """Reshape long to one column per series (cell), indexed by date."""
    if dimcols:
        key = df[dimcols].agg(".".join, axis=1)
    else:
        import pandas as pd

        key = pd.Series("value", index=df.index)
    wide = df.assign(series=key).pivot(index="date", columns="series", values="value")
    wide.columns.name = None
    return wide.sort_index()


def ds_catalog(lang: str = "en"):
    """Catalog of available datasets.

    Lists every dataset available on
    `dataseries.org <https://dataseries.org>`_, one row per dataset. Use the
    ``id`` column with :func:`ds` to download data and with :func:`ds_meta`
    to inspect a dataset's dimensions.

    Parameters
    ----------
    lang : {"en", "de", "fr", "it"}, default "en"
        Language for the ``title``, ``concept`` and ``source`` columns.

    Returns
    -------
    pandas.DataFrame
        One row per dataset with the columns ``id``, ``title``, ``concept``,
        ``topic``, ``source``, ``license``, ``frequency``, ``start``, ``end``
        and ``n_series``.

    Examples
    --------
    >>> cat = ds_catalog()                                     # doctest: +SKIP
    >>> cat[cat.title.str.contains("price", case=False)]       # doctest: +SKIP
    """
    import pandas as pd

    check_lang(lang)
    raw = _api.get_json("/catalog")
    rows = [
        {
            "id": scalar(d.get("id")),
            "title": label(d.get("title"), lang),
            "concept": label(d.get("concept"), lang),
            "topic": (d.get("topic") or {}).get("key")
            if isinstance(d.get("topic"), dict)
            else scalar(d.get("topic")),
            "source": source_name(d.get("source"), lang),
            "license": scalar(d.get("license")),
            "frequency": scalar(d.get("frequency")),
            "start": scalar(d.get("start")),
            "end": scalar(d.get("end")),
            "n_series": d.get("n_series"),
        }
        for d in raw
    ]
    return pd.DataFrame(rows).sort_values("id").reset_index(drop=True)


def ds_search(pattern: Optional[str] = None, lang: str = "en"):
    """Search for series across all datasets.

    Returns a flat, searchable table of the individual series available
    across every dataset on `dataseries.org <https://dataseries.org>`_ —
    one row per series. This is the finest-grained way to discover what
    exists. The ``dataset``, ``dim`` and ``code`` columns are exactly what
    you feed back to :func:`ds`.

    Parameters
    ----------
    pattern : str, optional
        Search string, treated as a case-insensitive regular expression and
        matched against the series ``label`` and ``dataset_title``. When
        ``None`` (the default) the full table is returned.
    lang : {"en", "de", "fr", "it"}, default "en"
        Language for the ``dataset_title`` and ``label`` columns. Searching
        also matches against labels in this language.

    Returns
    -------
    pandas.DataFrame
        Columns ``dataset``, ``dataset_title``, ``frequency``, ``dim``,
        ``code``, ``label`` and ``path``.

    Examples
    --------
    >>> hits = ds_search("unemployment")                       # doctest: +SKIP
    >>> ds(hits.dataset[0], {hits.dim[0]: hits.code[0]})       # doctest: +SKIP
    """
    import pandas as pd

    check_lang(lang)
    raw = _api.get_json("/search-index.json")
    rows = [
        {
            "dataset": scalar(e.get("datasetId")),
            "dataset_title": label(e.get("datasetTitle"), lang),
            "frequency": scalar(e.get("freq")),
            "dim": scalar(e.get("dim")),
            "code": scalar(e.get("code")),
            "label": label(e.get("label"), lang),
            "path": " / ".join(
                label(p, lang) or "" for p in (e.get("path") or [])
            ),
        }
        for e in raw
    ]
    out = pd.DataFrame(rows)
    if pattern is not None:
        hit = out["label"].str.contains(
            pattern, case=False, regex=True, na=False
        ) | out["dataset_title"].str.contains(pattern, case=False, regex=True, na=False)
        out = out[hit].reset_index(drop=True)
    return out


def ds_meta(dataset: str) -> dict:
    """Metadata for one dataset.

    Returns the full metadata for a single dataset: its dimensions, the
    codes (levels) available within each dimension, labels, source, license
    and date range. Use this to discover which dimension codes to pass to
    :func:`ds`.

    Parameters
    ----------
    dataset : str
        A single dataset ``id``, as listed by :func:`ds_catalog`.

    Returns
    -------
    dict
        The parsed metadata. Notable keys are ``dim_order`` (the dataset's
        dimensions) and ``dimensions`` (each dimension's ``levels``, keyed
        by code, with a ``label``).

    Examples
    --------
    >>> m = ds_meta("ch_seco_gdp")                             # doctest: +SKIP
    >>> m["dim_order"]                                         # doctest: +SKIP
    ['type', 'structure', 'seas_adj']
    >>> list(m["dimensions"]["type"]["levels"])                # doctest: +SKIP
    """
    if not isinstance(dataset, str) or not dataset:
        raise TypeError("dataset must be a non-empty string")
    m = _api.get_json(f"/dataset/{quote(dataset, safe='')}/meta")
    if isinstance(m, dict) and m.get("error"):
        raise ValueError(
            f"unknown dataset: {dataset!r}. See ds_catalog() for valid ids."
        )
    return m
