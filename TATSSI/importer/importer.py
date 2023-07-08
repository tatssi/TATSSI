
import os
import sys
import gdal
from glob import glob
import datetime as dt
import numpy as np
from TATSSI.UI.helpers.utils import *

DataDir = '/data/Landsat7'

def add_metadata(fname, str_date, data_var):
    """
    Adds date to metadata as follows:
        RANGEBEGINNINGDATE=YYYY-MM-DD
    :param fname: Full path of files to add date to its metadata
    :param str_date: date in string format, layout: YYYY-MM-DD
    :param data_var: Variable name, e.g. surface_reflectance
    :param fill_value: Fill value
    """

    # Open the file for update
    d = gdal.Open(fname, gdal.GA_Update)
    band = d.GetRasterBand(1)

    # Open band and get existing metadata
    md = d.GetMetadata()
    mband = band.GetMetadata()
    nodata_value=band.GetNoDataValue()
    # Add date
    mband['RANGEBEGINNINGDATE'] = str_date
    md['RANGEBEGINNINGDATE'] = str_date
    # Add variable description
    mband['data_var'] = data_var
    md['data_var'] = data_var
    # Add fill value #np.nan
    mband['_FillValue'] = "{}".format(nodata_value)
    mband['NoData Value'] = "{}".format(nodata_value)
    md['NoData Value'] = "{}".format(nodata_value)
    md['_FillValue'] = "{}".format(nodata_value)

    mband['version'] = "000"
    
    # Set metadata
    d.SetMetadata(md)
    band.SetMetadata(mband)

    d = None


def get_nodata_value(fname):
        d = gdal.Open(fname, gdal.GA_Update)
        band = d.GetRasterBand(1)

        # Open band and get existing metadata
        nodata_value=band.GetNoDataValue()
        d = None
        return nodata_value

if __name__ == "__main__":

    # Get all file from data directory for Landsat band 4, for instance
    # /data/Landsat7/LE70290462004017EDC01/LE70290462004017EDC01_sr_band4.tif
    fnames = glob(os.path.join(DataDir, '*', '*_sr_band4.tif'))
    fnames.sort()

    for fname in fnames:
        # Extract date from filename
        # LE7PPPRRRYYYYDDDEDC01_sr_band4.tif
        # YYYY = year
        # DDD = julian day
        year_julian_day = os.path.basename(fname)[9:16]

        # Conver string YYYYDDD into a datetime object
        _date = dt.datetime.strptime(year_julian_day, '%Y%j')
        # Convert datetime object to string YYYY-MM-DD
        str_date = _date.strftime('%Y-%m-%d')

        # Set data variable to a descriptive 'L7_SurfaceReflectance_B4'
        data_var = 'L7_SurfaceReflectance_B4'

        # Add metadata
        add_metadata(fname=fname, str_date=str_date,
                data_var=data_var, fill_value='-9999')
