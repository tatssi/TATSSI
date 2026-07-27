# GDAL 3.x warns on every run that exceptions will become the default in
# GDAL 4.0. The code base assumes the legacy behaviour (failed opens return
# None instead of raising), so state it explicitly - this also silences the
# per-module FutureWarning at startup.
from osgeo import gdal, ogr, osr
gdal.DontUseExceptions()
ogr.DontUseExceptions()
osr.DontUseExceptions()

from .download import *
from .input_output import *
from .qa import *
from .download import *
from .time_series import *
from .UI import *
