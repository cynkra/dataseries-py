"""Download open Swiss economic time series from dataseries.org into pandas.

`dataseries.org <https://dataseries.org>`_ is a comprehensive and up-to-date
collection of public data from Switzerland. This package talks to its public
API and imports series as pandas DataFrames.

>>> import dataseries as ds
>>> ds.ds_catalog()                                            # doctest: +SKIP
>>> ds.ds("ch_fso_cpi", item="100_100")                        # doctest: +SKIP
"""

from ._api import api_url, cache_clear, cache_keys
from ._core import ds, ds_catalog, ds_meta, ds_search
from ._version import __version__

__all__ = [
    "__version__",
    "api_url",
    "cache_clear",
    "cache_keys",
    "ds",
    "ds_catalog",
    "ds_meta",
    "ds_search",
]
