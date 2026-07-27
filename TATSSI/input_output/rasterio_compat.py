"""
Compatibility layer for the removed ``xarray.open_rasterio``.

``xarray.open_rasterio`` was deprecated in xarray 0.20 and removed from
modern xarray releases. TATSSI relies not only on the function itself but on
the *legacy attributes* it attached to the returned DataArray, which are
consumed throughout the code base (``nodatavals``, ``crs`` as a PROJ4 string,
``transform`` as a 6-tuple, ``res``, ``scales``, ``offsets``):

    e.g. input_output/utils.py -> ImportFromProj4(data.crs),
         attrs['transform']; time_series/{analysis,generator,smoothing}.py ->
         data_array.nodatavals[0]; qa/EOS/quality.py -> xr_d.nodatavals[0]

This module provides :func:`open_rasterio`, a drop-in replacement built on
``rioxarray.open_rasterio`` that restores those attributes with exactly the
same names, types and band-tuple semantics the old function used, and keeps
the same ``(band, y, x)`` dims/coords layout.
"""

import numpy as np


def open_rasterio(filename, parse_coordinates=None, chunks=None,
                  cache=None, lock=None, **kwargs):
    """
    Open a rasterio/GDAL-readable file as a DataArray, mimicking the removed
    ``xarray.open_rasterio`` (dims ``(band, y, x)`` plus legacy attrs).

    Parameters mirror the old function; extra keyword arguments are passed
    straight to ``rioxarray.open_rasterio``.
    """
    import rioxarray
    import rasterio

    rio_kwargs = dict(kwargs)
    if parse_coordinates is not None:
        rio_kwargs['parse_coordinates'] = parse_coordinates
    if chunks is not None:
        # The old xarray.open_rasterio accepted chunks as a tuple in
        # dimension order (band, y, x); rioxarray deprecates tuples, so
        # normalize to the dict form it expects.
        if isinstance(chunks, (tuple, list)):
            chunks = dict(zip(('band', 'y', 'x'), chunks))
        rio_kwargs['chunks'] = chunks
    if cache is not None:
        rio_kwargs['cache'] = cache
    if lock is not None:
        rio_kwargs['lock'] = lock

    da = rioxarray.open_rasterio(filename, **rio_kwargs)

    # Restore the legacy attributes the old xarray.open_rasterio provided.
    # (rioxarray already merges the GDAL dataset tags into .attrs; here we
    # add/overwrite the structured ones TATSSI consumes.)
    with rasterio.open(filename) as riods:
        attrs = {
            # Affine transform coefficients as a plain 6-tuple (a,b,c,d,e,f)
            'transform': tuple(riods.transform)[:6],
            # (x resolution, y resolution)
            'res': riods.res,
            'is_tiled': np.uint8(riods.is_tiled),
            # Per-band nodata values; np.nan when the band defines none
            'nodatavals': tuple(np.nan if nodataval is None else nodataval
                                for nodataval in riods.nodatavals),
            'scales': riods.scales,
            'offsets': riods.offsets,
        }
        if riods.crs is not None:
            # Legacy attr was a PROJ4 string (consumed via ImportFromProj4)
            attrs['crs'] = riods.crs.to_proj4()
        if any(riods.descriptions):
            attrs['descriptions'] = riods.descriptions
        if any(riods.units):
            attrs['units'] = riods.units

    da.attrs.update(attrs)

    # The old function exposed only the band/y/x coords; drop the extra
    # 'spatial_ref' coordinate rioxarray adds so downstream code (renames,
    # to_dataframe, saved datasets) sees the exact legacy layout.
    da = da.drop_vars('spatial_ref', errors='ignore')

    return da
