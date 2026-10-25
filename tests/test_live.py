"""Smoke tests against the live dataseries.org API.

Excluded by default; run with `pytest -m network`.
"""

import pandas as pd
import pytest

from dataseries import ds, ds_catalog, ds_meta, ds_search

pytestmark = pytest.mark.network


def test_catalog_live():
    cat = ds_catalog()
    assert len(cat) > 50
    assert "ch_seco_gdp" in set(cat["id"])


def test_catalog_lang_live():
    de = ds_catalog(lang="de").set_index("id")
    assert "Bruttoinlandprodukt" in de.loc["ch_seco_gdp", "title"]


def test_series_live():
    df = ds("ch_fso_cpi", item="100_100", start="2020-01-01")
    assert df["date"].min() >= pd.Timestamp("2020-01-01")
    assert df["value"].notna().all()


def test_wide_live():
    w = ds("ch_seco_gdp", type="real", structure="gdp", seas_adj="csa", wide=True)
    assert w.shape[1] == 1
    assert len(w) > 100


def test_meta_live():
    m = ds_meta("ch_seco_gdp")
    assert m["dim_order"] == ["type", "structure", "seas_adj"]


def test_search_live():
    hits = ds_search("unemployment")
    assert len(hits) > 0


def test_na_code_live():
    # "NA" is a real dimension code (net acquisition of financial assets).
    df = ds("ch_snb_bopcapbalq", D0="NA", D1="A")
    assert (df["D0"] == "NA").all()
    w = ds("ch_snb_bopcapbalq", D0=["NA", "S"], wide=True)
    assert any(c.startswith("NA.") for c in w.columns)


def test_errors_live():
    with pytest.raises(ValueError, match=r"unknown dataset 'ch_nope'; see ds_catalog\(\)"):
        ds("ch_nope")
    with pytest.raises(ValueError, match=r"unknown dataset 'ch_nope'"):
        ds_meta("ch_nope")
    with pytest.raises(ValueError, match="unknown dimension"):
        ds("ch_fso_cpi", nope="1")
    with pytest.raises(ValueError, match="unknown code"):
        ds("ch_fso_cpi", item="nope")
