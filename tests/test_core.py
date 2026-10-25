import pandas as pd
import pytest

import dataseries as dsm
from dataseries import ds, ds_catalog, ds_meta, ds_search
from dataseries._core import _build_dims


class TestBuildDims:
    def test_empty(self):
        assert _build_dims({}) == ""

    def test_single(self):
        assert _build_dims({"type": "real"}) == "type=real"

    def test_multi_code_and_dim(self):
        spec = _build_dims({"item": ["100_100", "100_1"], "type": "real"})
        assert spec == "item=100_100,100_1;type=real"

    def test_non_string_codes_are_stringified(self):
        assert _build_dims({"item": 100}) == "item=100"
        assert _build_dims({"item": [100, "101"]}) == "item=100,101"


class TestDs:
    def test_long_format(self, fake_api):
        df = ds("ch_fso_cpi")
        assert list(df.columns) == ["item", "date", "value"]
        assert df["date"].is_monotonic_increasing
        assert pd.api.types.is_datetime64_any_dtype(df["date"])
        assert pd.api.types.is_float_dtype(df["value"])
        assert pd.api.types.is_string_dtype(df["item"])  # codes stay strings

    def test_kwargs_become_dims(self, fake_api):
        ds("ch_fso_cpi", item=["100_100", "100_1"], start="2020-01-01")
        assert fake_api[-1] == (
            "/series.csv?dataset=ch_fso_cpi&dims=item%3D100_100%2C100_1"
            "&from=2020-01-01"
        )

    def test_integer_code_in_query(self, fake_api):
        ds("ch_fso_cpi", item=100)
        assert "dims=item%3D100" in fake_api[-1]

    def test_dims_dict_equivalent_to_kwargs(self, fake_api):
        a = ds("ch_fso_cpi", {"item": "100_100"})
        b = ds("ch_fso_cpi", item="100_100")
        pd.testing.assert_frame_equal(a, b)

    def test_end_bound(self, fake_api):
        ds("ch_fso_cpi", end="2021-12-31")
        assert fake_api[-1].endswith("&to=2021-12-31")

    def test_wide(self, fake_api):
        w = ds("ch_fso_cpi", wide=True)
        assert set(w.columns) == {"100_100", "100_1"}
        assert w.index.name == "date"
        assert w.loc["2020-01-01", "100_100"] == 99.0
        assert pd.isna(w.loc["2020-02-01", "100_1"])

    def test_wide_no_dims(self, fake_api):
        w = ds("ch_kof_barometer", wide=True)
        assert list(w.columns) == ["value"]
        assert len(w) == 2

    def test_na_code_long(self, fake_api):
        df = ds("ch_na_code", D1="A")
        assert set(df["D0"]) == {"NA", "S", "N/A", "null", "01"}
        assert df["D0"].notna().all()
        assert df["D1"].notna().all()
        assert df["value"].isna().sum() == 1  # only the empty value is missing

    def test_na_code_wide(self, fake_api):
        w = ds("ch_na_code", wide=True)
        assert set(w.columns) == {"NA.A", "S.A", "N/A.A", "null.A", "01.A"}
        assert w.loc["2020-01-01", "NA.A"] == 1.5
        assert pd.isna(w.loc["2020-04-01", "NA.A"])

    def test_api_error_csv_raises(self, fake_api):
        with pytest.raises(ValueError, match="unknown dataset"):
            ds("nope")

    def test_bad_dataset_type(self):
        with pytest.raises(TypeError):
            ds("")

    def test_cached_result_is_a_copy(self, fake_api):
        a = ds("ch_fso_cpi")
        a["value"] = 0.0
        b = ds("ch_fso_cpi")
        assert (b["value"] != 0.0).any()
        assert len(fake_api) == 1  # second call served from cache


class TestCatalog:
    def test_columns_and_order(self, fake_api):
        cat = ds_catalog()
        assert list(cat.columns) == [
            "id", "title", "concept", "topic", "source", "license",
            "frequency", "start", "end", "n_series",
        ]
        assert list(cat["id"]) == ["ch_fso_cpi", "ch_seco_gdp"]

    def test_field_normalization(self, fake_api):
        cat = ds_catalog().set_index("id")
        assert cat.loc["ch_seco_gdp", "source"] == "SECO"
        assert cat.loc["ch_seco_gdp", "topic"] == "national-accounts"
        assert cat.loc["ch_fso_cpi", "source"] == "FSO"  # plain string passes through
        assert pd.isna(cat.loc["ch_fso_cpi", "license"])  # empty object collapses

    def test_lang(self, fake_api):
        cat = ds_catalog(lang="de").set_index("id")
        assert cat.loc["ch_seco_gdp", "title"] == "Bruttoinlandprodukt (BIP)"
        # falls back to English where no translation exists
        assert cat.loc["ch_seco_gdp", "concept"] == "National accounts / GDP"

    def test_bad_lang(self):
        with pytest.raises(ValueError, match="lang"):
            ds_catalog(lang="es")


class TestSearch:
    def test_full_table(self, fake_api):
        out = ds_search()
        assert len(out) == 2
        assert list(out.columns) == [
            "dataset", "dataset_title", "frequency", "dim", "code", "label", "path",
        ]

    def test_pattern_matches_label(self, fake_api):
        out = ds_search("unemployment")
        assert list(out["dataset"]) == ["ch_seco_ui"]

    def test_pattern_matches_dataset_title(self, fake_api):
        out = ds_search("consumer price")
        assert list(out["dataset"]) == ["ch_fso_cpi"]

    def test_lang_search(self, fake_api):
        out = ds_search("arbeitslosen", lang="de")
        assert list(out["label"]) == ["Arbeitslosenquote"]

    def test_roundtrip_into_ds(self, fake_api):
        hits = ds_search("total index")
        row = hits.iloc[0]
        df = ds(row["dataset"], {row["dim"]: row["code"]})
        assert "value" in df.columns


class TestMeta:
    def test_meta(self, fake_api):
        m = ds_meta("ch_seco_gdp")
        assert m["dim_order"] == ["type", "structure", "seas_adj"]
        assert "real" in m["dimensions"]["type"]["levels"]

    def test_unknown_dataset(self, fake_api):
        with pytest.raises(ValueError, match="unknown dataset"):
            ds_meta("nope")


class TestCache:
    def test_keys_and_clear(self, fake_api):
        ds_catalog()
        assert dsm.cache_keys() == ["json:/catalog"]
        dsm.cache_clear()
        assert dsm.cache_keys() == []
        ds_catalog()
        assert len(fake_api) == 2  # refetched after clear


class TestApiUrl:
    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("DATASERIES_API", "http://localhost:8080/")
        assert dsm.api_url() == "http://localhost:8080"
