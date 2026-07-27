"""
VIIRS downloading tool to obtain data from the
Land Processes Distributed Active Archive Center (LP DAAC).
https://lpdaac.usgs.gov/

Authentication via the EarthData login.
https://urs.earthdata.nasa.gov/

NOTE: The legacy LP DAAC data pool (https://e4ftl01.cr.usgs.gov/) has been
retired. Downloads now go through the NASA Earthdata Cloud using the
``earthaccess`` library. All the heavy lifting lives in
:mod:`TATSSI.download.earthaccess_downloader`; this module keeps the public
``get_viirs_data`` entry point unchanged for backwards compatibility.
"""

from TATSSI.download.earthaccess_downloader import (
    LOG,
    BASE_URL,
    WebError,
    read_config,
    earthaccess_login,
    search_granules,
    get_earthdata_data,
)

# VIIRS platform accepted by the legacy API (kept for validation only)
_VALID_PLATFORMS = ["VIIRS"]


def get_viirs_data(platform, product, tiles,
                   output_dir, start_date,
                   end_date=None, n_threads=5,
                   username=None, password=None,
                   progressBar=None,
                   use_cache=False):
    """
    Download VIIRS products from the NASA Earthdata Cloud.

    The product is specified by its VIIRS code (e.g. ``VNP13A1.001`` or
    ``VNP09A1.001``, i.e. ``SHORTNAME.VERSION``). ``tiles`` may be a single
    tile (``"h17v04"``) or a list of tiles. If ``end_date`` is not given, the
    current date is used.

    ``platform`` (``VIIRS``) is accepted for backwards compatibility but is no
    longer required by the Earthdata Cloud / CMR search.

    See :func:`TATSSI.download.earthaccess_downloader.get_earthdata_data`.
    """
    if platform is not None:
        assert platform.upper() in _VALID_PLATFORMS, \
            "%s is not a valid platform. Valid one is VIIRS" % platform

    return get_earthdata_data(
        platform=platform, product=product, tiles=tiles,
        output_dir=output_dir, start_date=start_date, end_date=end_date,
        n_threads=n_threads, username=username, password=password,
        progressBar=progressBar, use_cache=use_cache)
