import io
import json
import urllib.error
import urllib.request

import pytest

from dataseries import _api

CATALOG = [
    {
        "id": "ch_seco_gdp",
        "title": {"en": "Gross domestic product (GDP)", "de": "Bruttoinlandprodukt (BIP)"},
        "concept": {"en": "National accounts / GDP"},
        "topic": {"key": "national-accounts", "name": {"en": "National accounts"}},
        "source": {"key": "seco", "name": {"en": "SECO", "de": "SECO (DE)"}},
        "license": "seco",
        "frequency": "quarterly",
        "start": "1980-01-01",
        "end": "2026-01-01",
        "n_series": 660,
    },
    {
        "id": "ch_fso_cpi",
        "title": {"en": "Consumer price index (CPI)", "de": "Landesindex der Konsumentenpreise"},
        "concept": {"en": "Prices / Consumer prices"},
        "topic": {"key": "prices", "name": {"en": "Prices"}},
        "source": "FSO",
        "license": {},
        "frequency": "monthly",
        "start": "1982-12-01",
        "end": "2026-07-01",
        "n_series": 400,
    },
]

SEARCH_INDEX = [
    {
        "datasetId": "ch_fso_cpi",
        "datasetTitle": {"en": "Consumer price index (CPI)", "de": "Landesindex"},
        "freq": "monthly",
        "dim": "item",
        "code": "100_100",
        "label": {"en": "Total index", "de": "Totalindex"},
        "path": [{"en": "All items", "de": "Alle Waren"}],
    },
    {
        "datasetId": "ch_seco_ui",
        "datasetTitle": {"en": "Unemployment insurance"},
        "freq": "monthly",
        "dim": "measure",
        "code": "rate",
        "label": {"en": "Unemployment rate", "de": "Arbeitslosenquote"},
        "path": [],
    },
]

META = {
    "schema_version": "1.1",
    "id": "ch_seco_gdp",
    "dim_order": ["type", "structure", "seas_adj"],
    "dimensions": {
        "type": {"label": {"en": "Type"}, "levels": {"real": {"label": {"en": "Real"}}}},
        "structure": {"label": {"en": "Structure"}, "levels": {"gdp": {"label": {"en": "GDP"}}}},
        "seas_adj": {"label": {"en": "Adjustment"}, "levels": {"csa": {"label": {"en": "Adjusted"}}}},
    },
}

SERIES_CSV = """item,date,value
100_100,2020-02-01,99.1
100_100,2020-01-01,99.0
100_1,2020-01-01,101.5
"""

SERIES_CSV_NODIM = """date,value
2020-01-01,1.5
2020-04-01,1.7
"""

# Dimension codes that look like missing values must survive verbatim.
SERIES_CSV_NA = """D0,D1,date,value
NA,A,2020-01-01,1.5
NA,A,2020-04-01,
S,A,2020-01-01,2.5
N/A,A,2020-01-01,3.5
null,A,2020-01-01,4.5
01,A,2020-01-01,5.5
"""

# Real API error responses: (status, body).
UNKNOWN_DATASET = (404, "error\nmissing or unknown dataset\n")
UNKNOWN_DIM = (
    400,
    'error\n"unknown dimension ""nope"" for dataset ch_fso_cpi. '
    'Valid dimensions: item"\n',
)
UNKNOWN_CODE = (
    400,
    'error\n"unknown code ""nope"" for dimension ""item"". '
    'Valid codes: ' + ", ".join(f"100_{i}" for i in range(100)) + '"\n',
)
UNKNOWN_DATASET_META = (200, '{"error":"unknown dataset"}')


class _Resp:
    def __init__(self, body):
        self._body = body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


@pytest.fixture
def fake_api(monkeypatch):
    """Serve canned API responses (errors included) and record requested paths."""
    requested = []

    def respond(path):
        if path == "/catalog":
            return 200, json.dumps(CATALOG)
        if path == "/search-index.json":
            return 200, json.dumps(SEARCH_INDEX)
        if path == "/dataset/ch_seco_gdp/meta":
            return 200, json.dumps(META)
        if path.startswith("/dataset/"):
            return UNKNOWN_DATASET_META
        if path.startswith("/series.csv"):
            if "dataset=nope" in path:
                return UNKNOWN_DATASET
            if "dims=nope" in path:
                return UNKNOWN_DIM
            if "item%3Dnope" in path:
                return UNKNOWN_CODE
            if "dataset=ch_down" in path:
                return 503, "Service Unavailable"
            if "dataset=ch_na_code" in path:
                return 200, SERIES_CSV_NA
            if "dataset=ch_kof_barometer" in path:
                return 200, SERIES_CSV_NODIM
            if "from=2099" in path:
                return 200, "item,date,value\n"
            return 200, SERIES_CSV
        raise AssertionError(f"unexpected path {path}")

    def urlopen(req, timeout=None):
        path = req.full_url[len(_api.api_url()):]
        requested.append(path)
        status, body = respond(path)
        if status >= 400:
            raise urllib.error.HTTPError(
                req.full_url, status, "error", {}, io.BytesIO(body.encode("utf-8"))
            )
        return _Resp(body)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    _api.cache_clear()
    yield requested
    _api.cache_clear()
