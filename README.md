# dataseries: Switzerland's Data Series in One Place

[![PyPI](https://img.shields.io/pypi/v/dataseries.svg)](https://pypi.org/project/dataseries/)
[![CI](https://github.com/cynkra/dataseries-py/actions/workflows/ci.yaml/badge.svg)](https://github.com/cynkra/dataseries-py/actions/workflows/ci.yaml)

Download and import open Swiss economic time series from
[dataseries.org](https://dataseries.org), a comprehensive and up-to-date
collection of public data from Switzerland. The package talks to the public
dataseries.org API and imports series as pandas DataFrames.

An [R package](https://CRAN.R-project.org/package=dataseries) with the same
interface is available on CRAN.

## Installation

```sh
pip install dataseries
```

Requires Python ≥ 3.9 and pandas.

## Data model

Data on dataseries.org is organized into **datasets**. A dataset is a family of
related series and, in most cases, a multi-dimensional *cube* — a single time
series is one cell of that cube, addressed by the dataset plus one code per
dimension. For example the GDP dataset (`ch_seco_gdp`) splits along three
dimensions: `type` (nominal/real/…), `structure` (GDP, value added, …) and
`seas_adj` (seasonally adjusted or not).

- `ds_catalog()` lists every dataset.
- `ds_search(pattern)` is a flat, searchable list of the individual series.
- `ds_meta(id)` describes a dataset's dimensions and the codes within them.
- `ds(id, ...)` downloads series.

## Usage

```python
import dataseries

# Browse what's available
dataseries.ds_catalog()

# Find a specific series across all datasets
dataseries.ds_search("unemployment")

# A dataset's dimensions and codes
dataseries.ds_meta("ch_seco_gdp")

# Whole dataset (long DataFrame)
dataseries.ds("ch_fso_cpi")

# One series: pass dimension codes as keyword arguments
dataseries.ds("ch_fso_cpi", item="100_100")

# Several series, restricted to a date range
dataseries.ds("ch_fso_cpi", item=["100_100", "100_1"], start="2020-01-01")

# One cell of a multi-dimensional cube, as a wide DataFrame indexed by date
dataseries.ds("ch_seco_gdp", type="real", structure="gdp", seas_adj="csa",
              wide=True)
```

The long format (the default) has the dimension column(s), then `date`
(datetime) and `value` (float) — ready for `groupby`, seaborn or plotly.
`wide=True` pivots to one column per series with a `DatetimeIndex`, the shape
you want for `.plot()` or `statsmodels`. All series are regular (annual,
quarterly or monthly); convert with e.g. `.to_period("Q")` if you prefer a
`PeriodIndex`.

Dimension arguments are optional: omit them and you get the whole dataset.
Filtering happens on the server, so selecting one series does not download the
whole cube. Downloads are cached in memory for the session;
`dataseries.cache_clear()` forces a fresh download.

## Labels in German, French or Italian

The catalog and search index are translated. Pass `lang` to get titles and
labels in any Swiss national language (falls back to English where a
translation is missing):

```python
dataseries.ds_catalog(lang="de")
dataseries.ds_search("arbeitslosigkeit", lang="de")
```

## From search hit to data

`ds_search()` returns exactly the columns you feed back to `ds()`:

```python
hits = dataseries.ds_search("consumer price")
row = hits.iloc[0]
df = dataseries.ds(row["dataset"], {row["dim"]: row["code"]})
```

## Beyond Python

Every series is also available as a plain CSV from any tool that can read a
URL:

```
https://api.dataseries.org/series.csv?dataset=ch_fso_cpi&dims=item=100_100
```

Self-hosting or testing against a mirror? Point the package elsewhere with the
`DATASERIES_API` environment variable.

## License

MIT. The data itself is published by the Swiss data providers
under their respective terms; see the `license` column in `ds_catalog()` and
the source links in `ds_meta()`.
