import os
import sys

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QFileDialog

import json

from pathlib import Path
current_dir = os.path.dirname(__file__)
TATSSI_HOMEDIR = str(Path(current_dir).parents[2])

def open_file_dialog(dialog_type = 'open',
                   data_format = 'GeoTiff',
                   extension = 'tif'):
    """
    Creates a Open File dialog window
    :param dialog_type: Dialog type, can be open or save. Default is
                        open
    :param data_format: Data format to Open/Save. Default is GeoTiff
    :parm extension: Data format extension. Default is tif
    :return: Full path of selected file
    """
    if dialog_type == 'open':
        fname = QFileDialog.getOpenFileName(parent=None,
                caption="Select a file...",
                directory=TATSSI_HOMEDIR,
                filter="All files (*)")

    elif dialog_type == 'open_specific':
        fname = QFileDialog.getOpenFileName(parent=None,
                caption="Select a file...",
                directory=TATSSI_HOMEDIR,
                filter="%s Files (*.%s)" % \
                        (data_format, extension))

    elif dialog_type == 'save':
        # Get format and extension
        fname = QFileDialog.getSaveFileName(parent=None,
                caption="Save file as...",
                directory=TATSSI_HOMEDIR,
                filter="%s Files (*.%s)" % \
                        (data_format, extension))

    elif dialog_type == 'directory':
        dirname = QFileDialog.getExistingDirectory(parent=None,
                caption="Select a directory...",
                directory=TATSSI_HOMEDIR,
                options=QFileDialog.ShowDirsOnly)

        return dirname

    return str(fname[0])

# decorate for log
import time
from datetime import datetime
def log(fichero_log):
        def decorador_log(func):
                def decorador_funcion(*args, **kwargs):
                        with open(fichero_log, 'a') as opened_file:
                                inicio = time.time()
                                date_inicio = datetime.now()
                                func_name=func.__name__
                                if func_name == "on_pbSmooth_click" or \
                                        func_name == "on_btn_QA_Analytics_activated" or \
                                        func_name == "on_pbCPD_click" or \
                                        func_name == "on_pbClimatology_click" or \
                                        func_name == "on_pbDecomposition_click" or \
                                        func_name == "on_pbAnomalies_click" or \
                                        func_name == "on_pbMKTest_click" or \
                                        func_name == "__frequency_analysis":
                                      output = func(args[0])
                                else:
                                        output = func(*args, **kwargs)
                                fin = time.time()
                                date_fin = datetime.now()
                                duracion=(fin - inicio)/60.0
                                func_name=func.__name__
                                opened_file.write(f"{func_name,output,date_inicio.isoformat(),date_fin.isoformat(),duracion }\n")
                        return output
                return decorador_funcion
        return decorador_log
