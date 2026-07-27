"""
Earthdata Cloud downloading backend for TATSSI.

The former LP DAAC data pool served over plain HTTP directory listings
(https://e4ftl01.cr.usgs.gov/ ...) has been retired. NASA now distributes
MODIS/VIIRS products through the Earthdata Cloud, discoverable via CMR and
downloadable from https://data.lpdaac.earthdatacloud.nasa.gov/

Authentication keeps using ``TATSSI/download/config.json`` with the
``username`` / ``password`` of an Earthdata Login account
(https://urs.earthdata.nasa.gov/).

Docs: https://earthaccess.readthedocs.io/en/stable/
"""

import os
import json
import pickle
import datetime
from pathlib import Path

import logging
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)

# New Earthdata Cloud base (informational; earthaccess resolves the real URLs)
BASE_URL = "https://data.lpdaac.earthdatacloud.nasa.gov/"

# Cache the earthaccess Auth object so we only log in once per process
_AUTH = None


class WebError(RuntimeError):
    """An exception for web issues (kept for backwards compatibility)."""
    def __init__(self, arg):
        self.args = arg


def read_config():
    """
    Read the downloaders config file (TATSSI/download/config.json).

    Returns the tuple ``(url, username, password)``. ``url`` is kept for
    backwards compatibility but is no longer used for authentication.
    """
    downloaders_dir = os.path.dirname(__file__)
    fname = os.path.join(downloaders_dir, 'config.json')
    with open(fname) as f:
        credentials = json.load(f)

    url = credentials.get('url', BASE_URL)
    username = credentials['username']
    password = credentials['password']

    return url, username, password


def earthaccess_login(username=None, password=None):
    """
    Log in to NASA Earthdata using ``earthaccess``.

    Credentials are taken (in order) from the explicit ``username`` /
    ``password`` arguments, then from ``config.json``. They are exported as
    ``EARTHDATA_USERNAME`` / ``EARTHDATA_PASSWORD`` so ``earthaccess`` can use
    its ``environment`` strategy. If no usable credentials are found it falls
    back to the default ``all`` strategy (``~/.netrc`` or interactive prompt).

    The resulting Auth object is cached module-wide.
    """
    global _AUTH

    import earthaccess

    if _AUTH is not None and getattr(_AUTH, 'authenticated', False):
        return _AUTH

    # Resolve credentials from config.json when not provided
    if username is None or password is None:
        try:
            _, cfg_user, cfg_pass = read_config()
        except Exception:
            cfg_user, cfg_pass = None, None
        username = username or cfg_user
        password = password or cfg_pass

    placeholders = {None, '', 'USERNAME', 'PASSWORD'}
    has_creds = username not in placeholders and password not in placeholders

    if has_creds:
        os.environ['EARTHDATA_USERNAME'] = username
        os.environ['EARTHDATA_PASSWORD'] = password
        auth = earthaccess.login(strategy='environment', persist=False)
        LOG.info(f"Logged in to Earthdata as user {username}")
    else:
        # No explicit credentials: let earthaccess try netrc / token / prompt
        LOG.warning("No Earthdata credentials in config.json; trying netrc / "
                    "environment / interactive login.")
        auth = earthaccess.login(strategy='all', persist=False)
        LOG.info("Logged in to Earthdata using strategy 'all'")

    if not getattr(auth, 'authenticated', False):
        raise WebError("Earthdata authentication failed. Check the username "
                       "and password in TATSSI/download/config.json.")

    _AUTH = auth
    return auth


def _normalize_tiles(tiles):
    """Return ``tiles`` as a clean list of strings (or an empty list)."""
    if tiles is None:
        return []
    if isinstance(tiles, str):
        tiles = [tiles]
    return [t for t in tiles if t]


def _granule_filename(granule):
    """
    Best-effort extraction of the data file name for a granule, preferring the
    ``.hdf`` / ``.h5`` data link over browse/metadata links.
    """
    try:
        links = granule.data_links()
    except Exception:
        links = []

    data_link = None
    for link in links:
        low = link.lower()
        if low.endswith('.hdf') or low.endswith('.h5') or low.endswith('.nc'):
            data_link = link
            break
    if data_link is None and links:
        data_link = links[0]

    if data_link is not None:
        return data_link.split('/')[-1]

    # Fallback to the granule UR from the UMM metadata
    try:
        return granule['umm']['GranuleUR']
    except Exception:
        return None


def save_available_dates(product, granules):
    """
    Cache the granules found for a product on a pickle file in
    ``$HOME/.TATSSI/{product}`` (mirrors the original cache location).
    """
    homedir = os.path.expanduser("~")
    config_dir = os.path.join(homedir, '.TATSSI')
    Path(config_dir).mkdir(parents=True, exist_ok=True)

    fname = os.path.join(config_dir, product)
    try:
        with open(fname, 'wb') as f:
            pickle.dump(granules, f)
    except Exception as exc:
        LOG.warning("Could not write search cache for %s: %s", product, exc)


def get_available_dates_from_cache(product):
    """Load cached granules for a product from ``$HOME/.TATSSI/{product}``."""
    homedir = os.path.expanduser("~")
    config_dir = os.path.join(homedir, '.TATSSI')
    fname = os.path.join(config_dir, product)

    if os.path.exists(fname):
        try:
            with open(fname, 'rb') as f:
                return pickle.load(f)
        except Exception as exc:
            LOG.warning("Could not read search cache for %s: %s", product, exc)
    return []


def search_granules(product, tiles, start_date, end_date=None,
                    use_cache=False):
    """
    Search the CMR for granules of ``product`` (``SHORTNAME.VERSION``) that
    intersect the requested ``tiles`` and fall within ``start_date`` /
    ``end_date``. Returns a list of ``earthaccess`` DataGranule objects.

    Tile filtering is done server-side via the granule name pattern
    (e.g. ``*h17v04*``). For non-tiled/global (CMG) products, where the tile is
    not part of the file name, the search falls back to every granule in the
    temporal range.
    """
    import earthaccess

    if end_date is None:
        end_date = datetime.datetime.now()

    # Split "MOD13Q1.006" -> short_name="MOD13Q1", version="006"
    if '.' in product:
        short_name, version = product.rsplit('.', 1)
    else:
        short_name, version = product, None

    common = dict(short_name=short_name, temporal=(start_date, end_date),
                  count=-1)
    if version:
        common['version'] = version

    tiles = _normalize_tiles(tiles)

    granules = []
    seen = set()

    if tiles:
        for tile in tiles:
            try:
                results = earthaccess.search_data(
                    granule_name=f"*{tile}*", **common)
            except Exception as exc:
                LOG.warning("CMR search failed for %s tile %s: %s",
                            short_name, tile, exc)
                results = []
            for g in results:
                fn = _granule_filename(g)
                if fn and fn not in seen:
                    seen.add(fn)
                    granules.append(g)

    # Global / CMG product (no tile in the file name) -> search everything
    if not granules:
        try:
            results = earthaccess.search_data(**common)
        except Exception as exc:
            raise WebError(f"CMR search failed for {product}: {exc}")
        for g in results:
            fn = _granule_filename(g)
            if fn and fn not in seen:
                seen.add(fn)
                granules.append(g)

    if use_cache and granules:
        save_available_dates(product, granules)

    return granules


def required_granules(granules, output_dir):
    """
    Drop granules whose data file already exists in ``output_dir`` so we only
    download what is missing (mirrors the original ``required_files``).
    """
    if not os.path.isdir(output_dir):
        return granules

    present = set(os.listdir(output_dir))
    missing = []
    for g in granules:
        fn = _granule_filename(g)
        if fn is None or fn not in present:
            missing.append(g)
    return missing


def get_earthdata_data(platform, product, tiles,
                       output_dir, start_date,
                       end_date=None, n_threads=5,
                       username=None, password=None,
                       progressBar=None,
                       use_cache=False):
    """
    Engine that downloads MODIS/VIIRS products from the Earthdata Cloud using
    ``earthaccess``. The signature matches the original ``get_modis_data`` /
    ``get_viirs_data`` so callers do not change.

    ``platform`` (MOLT/MOLA/MOTA/VIIRS) is accepted for compatibility but is no
    longer needed: the CMR short name uniquely identifies the collection.
    """
    # Authenticate (uses config.json when username/password are not given)
    earthaccess_login(username=username, password=password)

    # Ensure the output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # Try the cache first, exactly like the original downloaders
    granules = []
    if use_cache:
        granules = get_available_dates_from_cache(product)

    if not granules:
        granules = search_granules(product, tiles, start_date,
                                   end_date=end_date, use_cache=use_cache)

    # Skip granules already present on disk
    granules = required_granules(granules, output_dir)

    msg = f"Will download {len(granules)} files..."
    if progressBar is not None:
        progressBar.setFormat(msg)
    LOG.info(msg)

    if not granules:
        return []

    import earthaccess

    dload_files = []
    total = len(granules)
    for i, granule in enumerate(granules, start=1):
        try:
            paths = earthaccess.download(
                [granule], local_path=output_dir,
                threads=max(1, int(n_threads)))
            if paths:
                dload_files.extend(paths)
                LOG.info("Done with %s", paths[0])
        except Exception as exc:
            fn = _granule_filename(granule)
            LOG.warning("Could not download %s: %s. Try again later.",
                        fn, exc)
        finally:
            if progressBar is not None:
                progressBar.setValue(int((i / total) * 100.0))

    return dload_files
