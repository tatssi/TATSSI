
import os
import sys

# TATSSI modules
from pathlib import Path
current_dir = os.path.dirname(os.path.realpath(__file__))
src_dir = Path(current_dir).parents[1]
sys.path.append(str(src_dir.absolute()))

from TATSSI.input_output.utils import *
from TATSSI.notebooks.helpers.utils import *
from TATSSI.importer.importer import add_metadata, get_nodata_value

from osgeo import gdal 
from datetime import datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta

from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import Qt, pyqtSlot

from TATSSI.notebooks.helpers.qa_analytics import Analytics
from TATSSI.UI.plots_qa_analytics import PlotInterpolation

from TATSSI.UI.helpers.utils import *

class QTextEditLogger(logging.Handler):
    def __init__(self, parent):
        super().__init__()
        self.widget = QtWidgets.QPlainTextEdit(parent)
        self.widget.setReadOnly(True)

    def emit(self, record):
        msg = self.format(record)
        self.widget.appendPlainText(msg)

class genericImporterUI(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(genericImporterUI, self).__init__(parent)
        uic.loadUi('genericImporter.ui', self)
        self.parent = parent
        #Iniciar UI
        self.lbl_msjsUser.setText("")
        self.groupBox_Settings.setEnabled(False)
        self.groupBox_Interpolation.setEnabled(False)
        self.progressBar.hide()
        self.progressBar.setValue(0)
        #Connect methods with events
        self.btnInputDIr.clicked.connect(
                self.on_btnInputDIr_click)
        
        self.comboBox_products.activated.connect(
                self.on_comboBox_products_activated)
        # radio buttons:
        self.radioButton_SatName.clicked.connect(
                self.on_radioButton_SatName_activated)
        
        self.radioButton_ProdName.clicked.connect(
                self.on_radioButton_ProdName_activated)
        
        self.radioButton_SpatialRes.clicked.connect(
                self.on_radioButton_SpatialRes_activated)
        
        self.ln_SatName.textChanged.connect(
            lambda: self.on_ln_SatName_activated())
        
        self.ln_ProdName.textChanged.connect(
            lambda: self.on_ln_ProdName_activated())
        
        self.ln_SpatialRes.textChanged.connect(
            lambda: self.on_ln_SpatialRes_activated())
        
        self.btn_Apply.clicked.connect(
                self.on_btn_Apply_activated)
        
        self.btn_createTS.clicked.connect(
            self.on_btn_createTS_activated)
        
        self.btn_Interpolation.clicked.connect(
            self.on_btn_Interpolation_activated)
        
        self.btn_QA_saves.clicked.connect(
            self.on_btn_QA_Analytics_activated)

        self.show()
    
    def clear_table(self):

        self.tableList.setRowCount(0)
        self.tableList.setEnabled(False)
        self.lbl_datavar.setText("")
        self.lbl_fillValue.setText("")
        self.lbl_numFiles.setText("")
        self.groupBox_Interpolation.setEnabled(False)
        self.progressBar.hide()
        self.progressBar.setValue(0)
        self.lbl_msjsUser.setText("")
        self.lbl_interpolation.setText("")

    def fill_dataSettings(self, spacecraft, 
                product, 
                resolution, 
                start_date, 
                end_date, 
                period, 
                fill_value, 
                data_var):
        self.ln_SatName.setText(spacecraft)
        self.ln_ProdName.setText(product)
        self.ln_SpatialRes.setText(resolution)
        #qdate = datetime.strptime(self.start_date.text(), '%d-%m-%Y')
        if start_date == end_date:
            qdate = datetime.strptime(start_date, '%Y-%m-%d')
            self.Qdate_start.setDate(qdate)
            self.Qdate_end.setDate(qdate)
            self.spinBox_Period.setEnabled(True)
            self.comboBox_period.setEnabled(True)

        else:
            qdate = datetime.strptime(start_date, '%Y-%m-%d')
            self.Qdate_start.setDate(qdate)
            qdate = datetime.strptime(end_date, '%Y-%m-%d')
            self.Qdate_end.setDate(qdate)
            self.spinBox_Period.setEnabled(False)
            self.comboBox_period.setEnabled(False)
        self.spinBox_Period.setSpecialValueText(period)
        self.ln_Fillvalue.setText(fill_value)
        self.ln_dataVar.setText(data_var)

    def is_valid_date(self,user_date):
            if len(user_date) == 6:
                try:
                    result = datetime.strptime(user_date, '%Y%m')
                except ValueError:
                    return False
                return result
            elif len(user_date) == 7:
                try:
                    result = datetime.strptime(user_date, '%Y%j')
                except ValueError:
                    return False
                return result
            elif len(user_date) > 7:
                try:
                    result = datetime.strptime(user_date, '%Y-%m-%d')
                except ValueError:
                    try:
                        result = datetime.strptime(user_date, '%Y%m%d')
                    except ValueError:
                            try:
                                result = datetime.strptime(user_date, '%d%m%Y')
                            except ValueError:
                                return False
                            return result
                    return result
                return result
            elif len(user_date) < 6:
                return False

    def fill_files_table(self, file2insert):
        rows = len(file2insert)
        columns = len(file2insert[0])-1
        #print(f'Rows:{rows}, Column:{columns}')
        #print(file2insert)
        #tableList
        #Row count
        self.tableList.setRowCount(rows)
        self.tableList.setColumnCount(columns)
        for row in range(0,rows):
            for col in range(0,columns):
                # Insert item on products TableView
                item = file2insert[row][col]
                self.tableList.setItem(row, col,
                        QtWidgets.QTableWidgetItem(item))

        self.tableList.resizeColumnsToContents()
        self.tableList.horizontalHeader().setStretchLastSection(True)
        self.tableList.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.Stretch)

    def get_idate(self,start_date, iteracion , period, dateRange):
        delta=iteracion * period
        user_date = datetime.strptime(start_date, '%Y-%m-%d')
        if dateRange == "days":
            idelta = timedelta(days=delta)
        elif dateRange == "months":
            idelta = relativedelta(months=delta)
        elif dateRange == "years":
            idelta = relativedelta(years=delta)
        result = user_date + idelta
        return result


    def get_files2insert(self, product):
        # export list fill, date, file:
        iFile = []
        resultFileList = []
        current_dir = self.lbl_InputDir.text()
        data = Path(current_dir)
        fill_value = self.ln_Fillvalue.text()
        qdate = self.Qdate_start.date()
        start_date = qdate.toPyDate().strftime("%Y-%m-%d")
        period = self.spinBox_Period.value()
        dateRange = self.comboBox_period.currentText()


        if product == "data4tatssi":
            fileList = sorted(list(data.glob("**/*.tif")))
        else:
            fileList = sorted(list(data.glob("**/*"+product+"*.tif")))
        if len(fileList) > 0:
            index = 0
            
            for file in fileList:
                fileName = file.stem
                iteracion = index
                if len(file.stem.split('_')) >= 4:  
                    if self.is_valid_date(file.stem.split('_')[1]):
                        result = self.is_valid_date(file.stem.split('_')[1])
                        idate = result.strftime('%Y-%m-%d')
                    else:
                        result = self.get_idate(start_date, iteracion , period, dateRange)
                        idate = result.strftime('%Y-%m-%d')
                else:
                    result = self.get_idate(start_date, iteracion , period, dateRange)
                    idate = result.strftime('%Y-%m-%d')
                        
                #newrow = [fill_value, idate, fileName]
                newrow = [fileName, idate, file]
                resultFileList.append(newrow)
                index += 1
            
        return resultFileList

    
    def get_dataset_info(self, product):
        #S2A_202101_LAI_10m
        #satname=0
        #date=1
        #prod=2
        #res=3
        
        dates = []
        dateList = []
        current_dir = self.lbl_InputDir.text()
        data = Path(current_dir)
        fileList = list(data.glob("**/*"+product+"*.tif"))
        if len(fileList) > 0:
            for file in fileList:
                nodata_value=get_nodata_value(str(file))
                if len(file.stem.split('_')) >= 4:
                    spacecraft = file.stem.split('_')[0]
                    idate = file.stem.split('_')[1]
                    if self.is_valid_date(idate):
                        result = self.is_valid_date(idate)
                        dates.append(result)
                    resolution = file.stem.split('_')[3]
            dateList = sorted(list(set(dates)))   

            if len(dateList) == 0:
                spacecraft = "SAT-TATSSI"
                resolution = "1000m"
                start_date = "1999-01-01"
                end_date = "1999-01-01"
                self.lbl_msjsUser.setText("Warning: Not DATE found. Example: \n S2A_20010101_NDVI_10m.tif ")
            else:
                dateListMin = min(dateList)
                dateListMax = max(dateList)
                start_date = dateListMin.strftime('%Y-%m-%d')
                end_date = dateListMax.strftime('%Y-%m-%d')
        else:
            spacecraft = "SAT-TATSSI"
            resolution = "1000m"
            start_date = "1999-01-01"
            end_date = "1999-01-01"
            self.lbl_msjsUser.setText("Warning: Not Files found (*.tif) ")
        return spacecraft, product, resolution, start_date, end_date, "{}".format(nodata_value)

    def get_prod_list(self):
        """
        Gets a list of available products
        """
        current_dir = self.lbl_InputDir.text()
        data = Path(current_dir)

        # Empty list of bands
        productList = []
        products = []

        self.comboBox_products.clear()
        header=["Select one option"]
 
        fileList = list(data.glob("**/*.tif"))
        if len(fileList) > 0:
            for file in fileList:
                if len(file.stem.split('_')) >= 4:
	                products.append(file.stem.split('_')[2])
            productList = sorted(list(set(products)))            
            if len(productList) == 0:
                productList=["data4tatssi"]
                self.lbl_msjsUser.setText("Warning: Not product name found. \nexample: S2A_20010101_NDVI_10m.tif ")
            self.comboBox_products.addItems(header)
            self.comboBox_products.addItems(productList)
            self.comboBox_products.setEnabled(True)
            
        else:
            
            self.comboBox_products.addItems(header)
            self.comboBox_products.setEnabled(False)

        return productList
    
    
    @pyqtSlot()
    def on_btnInputDIr_click(self):
        """
        Opens dialog to select output dir and sets the
        OutputDirectory label text
        """
        input_dir = open_file_dialog('directory')
        self.lbl_InputDir.setText(input_dir)
        

        # Si el directorio esta vacio:
        if (input_dir.isspace() or len(input_dir) ==0):
            self.lbl_msjsUser.setText("Error: NULL Input directory")
            self.groupBox_Settings.setEnabled(False)
            self.tableList.setEnabled(False)
            self.btn_createTS.setEnabled(False)
        else:
            self.lbl_msjsUser.setText("")
            productList = []
            productList = self.get_prod_list()
            self.clear_table()
        self.comboBox_products.setCurrentIndex(0)
        self.groupBox_Settings.setEnabled(False)
        self.tableList.setEnabled(False)
        self.btn_createTS.setEnabled(False)

    @pyqtSlot()
    def on_comboBox_products_activated(self):
        """
        Opens dialog to select output dir and sets the
        OutputDirectory label text
        """
        indexProd = self.comboBox_products.currentIndex()
        if indexProd == 0:
            self.clear_table()
            self.btn_createTS.setEnabled(False)
            self.groupBox_Settings.setEnabled(False)
        else:
            self.groupBox_Settings.setEnabled(True)
            product = self.comboBox_products.currentText()
            if product == "data4tatssi":
                spacecraft = "SAT-TATSSI"
                resolution = "1000m"
                start_date = "1999-01-01"
                end_date = "1999-01-01"
                period = "-"
                fill_value = "-9999"
                data_var = spacecraft+"_"+product+"_"+resolution
            else:
                spacecraft,productName,resolution,start_date,end_date,fill_value = self.get_dataset_info(product)
                period = "NA"
                #fill_value = "-9999"
                data_var = spacecraft+"_"+productName+"_"+resolution
            
            def num_files(product):
                current_dir = self.lbl_InputDir.text()
                data = Path(current_dir)
                if product == "data4tatssi":
                    fileList = list(data.glob("**/*.tif"))
                else:
                    fileList = list(data.glob("**/*"+product+"*.tif"))
                self.lbl_numFiles.setText("Selected files: "+ str(len(fileList)))


            self.fill_dataSettings(spacecraft=spacecraft, 
                        product=product, 
                        resolution=resolution, 
                        start_date=start_date, 
                        end_date=end_date, 
                        period=period, 
                        fill_value=fill_value, 
                        data_var=data_var)
            num_files(product)

    @pyqtSlot()
    def on_btn_Apply_activated(self):
        #Button to apply changes....
        # checar si el perido:
        def is_valid_period(user_period):
            if self.spinBox_Period.isEnabled():
                value = self.spinBox_Period.value()
                if value == 0:
                    return False
                elif value > 0:
                    return True
            else:
                return True
        period = self.spinBox_Period.text()
        if is_valid_period(period):
            product = self.comboBox_products.currentText()
            file2insert = self.get_files2insert(product)
            self.lbl_datavar.setText("Data var: "+self.ln_dataVar.text())
            self.lbl_fillValue.setText("Fill Value: "+self.ln_Fillvalue.text())
            self.fill_files_table(file2insert)
            self.tableList.setEnabled(True)
            self.btn_createTS.setEnabled(True)
            self.lbl_msjsUser.setText("")
            # llenar la lista
            # activar boton de importar:

        else:
            self.lbl_msjsUser.setText("Error: Invalid period")

    
    @pyqtSlot()
    def on_btn_createTS_activated(self):
        start = time.time()
        tiempo_inicial = datetime.now()
        product = self.comboBox_products.currentText()
        file2insert = self.get_files2insert(product)
        data_var = self.ln_dataVar.text()
        fill_value = self.ln_Fillvalue.text()
        input_dir = self.lbl_InputDir.text()
        output_dir = input_dir
        @log("ficheroLog.log")
        def generar_VRT_TS(output_fname,fnameList,vrt_options):
            with open("ficheroLog.log","a") as file:
                file.write("Generic Importer:\n")
            gdal.BuildVRT(output_fname, fnameList , options=vrt_options)
        if output_dir == "/temp/data/output":
            self.lbl_msjsUser.setText("Error: output directory is missing")
        else:
            output_fname = output_dir+"/"+data_var+".vrt"
            fnameList = []
            for fileName,str_date,fname in file2insert:
                add_metadata(str(fname), str_date, data_var)
                nodata_value=get_nodata_value(str(fname))
                fnameList.append(str(fname))
            # Create layerstack (vrt)
            vrt_options = gdal.BuildVRTOptions(separate=True, VRTNodata=nodata_value, callback=gdal.TermProgress_nocb)
            generar_VRT_TS(output_fname,fnameList,vrt_options)
            end = time.time()
            tiempo_final= datetime.now()
            duracion=(end - start)/60.0
            print("************** Time Series importer (VRT file) *********")
            print("Start:", tiempo_inicial," End: ", tiempo_final, " @minutes: ", duracion)

            
            if os.path.isfile(output_fname):
                self.lbl_msjsUser.setText("VRT file created in: "+output_dir+"\n"+" File name: "+data_var+".vrt")
                self.groupBox_Interpolation.setEnabled(True)

                self.btn_QA_saves.setEnabled(True)
                self.btn_Interpolation.setEnabled(False)
                self.lbl_interpolation.setText(output_fname)
                self.qa_analytics = None

                self.progressBar.show()
                self.progressBar.setEnabled(False)
                self.progressBar.setValue(0)
                self.progressBar.setFormat('')                
            else:
                self.lbl_msjsUser.setText("ERROR: In creating: "+output_fname)

    def on_btn_Interpolation_activated(self):
        self.dialogs = list()
        with open("ficheroLog.log","a") as file:
                file.write("Interpolation:\n")
        # Wait cursor
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)

        dialog = PlotInterpolation(self)
        self.dialogs.append(dialog)
        qdate = self.Qdate_start.date()
        start_date = qdate.toPyDate().strftime("%Y-%m-%d")
        qdate = self.Qdate_end.date()
        end_date = qdate.toPyDate().strftime("%Y-%m-%d")
        @log("ficheroLog.log")
        def plotInterpolacion_genericImporter(dialog,qa_analytics):
            dialog._plot(qa_analytics)
            dialog.show()

        if self.qa_analytics == None:
            self.qa_analytics = Analytics(
                    source_dir=self.lbl_InputDir.text(),
                    product=self.ln_ProdName.text(),
                    chunked=True,
                    version="000",
                    start=start_date,
                    end=end_date,
                    data_format='tif')

        plotInterpolacion_genericImporter(dialog,self.qa_analytics)
        
        # Standard cursor
        QtWidgets.QApplication.restoreOverrideCursor()
    
    @log("ficheroLog.log")
    def on_btn_QA_Analytics_activated(self):
        self.progressBar.show()
        self.progressBar.setEnabled(True)
        tiempo_inicial = datetime.now()
        start = time.time()
        if self.qa_analytics == None:
            qdate = self.Qdate_start.date()
            start_date = qdate.toPyDate().strftime("%Y-%m-%d")
            qdate = self.Qdate_end.date()
            end_date = qdate.toPyDate().strftime("%Y-%m-%d")
            self.qa_analytics = Analytics(
                    source_dir=self.lbl_InputDir.text(),
                    product=self.ln_ProdName.text(),
                    chunked=True,
                    version="000",
                    start=start_date,
                    end=end_date,
                    data_format='tif')
            self.progressBar.setValue(75)
            self.progressBar.setFormat('computing qa_analytics ...')
            self.qa_analytics._analytics(self.progressBar)
        else:
            self.progressBar.setEnabled(True)
            self.progressBar.setValue(100)
            self.progressBar.setFormat('qa_analytics created ...')
        end = time.time()
        tiempo_final= datetime.now()
        duracion=(end - start)/60.0
        print("************** QA products *********")
        print("Start:", tiempo_inicial," End: ", tiempo_final, " @minutes: ", duracion)

        """
        Save to the user's selected path:
            The current user-defined QA setting into a JSON file
            The percentage of data available as COG
            The max gap-lenth as COG
            The mask generated by the QA settings as COG
        """
        fname = open_file_dialog(dialog_type = 'save',
                data_format = 'JSON',
                extension = 'json')

        
        if (fname.isspace() or len(fname) ==0):
            self.progressBar.setFormat('Error: output name missing')
        else:
            # Wait cursor
            QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
            with open(fname, 'w') as f:
                user_qa_selection = {
                    "data": [
                        self.ln_dataVar.text(),
                    ]
                    }
                f.write(json.dumps(user_qa_selection))

            LOG.info(f"QA settings file {fname} written to disk.")

            fname = os.path.splitext(fname)[0]

            _data_var = list(self.qa_analytics.ts.data.data_vars.keys())[0]
            # Copy metadata
            self.qa_analytics.pct_data_available.attrs = \
                    self.qa_analytics.ts.data[_data_var].attrs
            self.qa_analytics.max_gap_length.attrs = \
                    self.qa_analytics.ts.data[_data_var].attrs

            # Add one dimension and save to disk percentage of data avail.
            tmp_data_array = self.qa_analytics.pct_data_available.expand_dims(
                    dim='time', axis=0)
            save_dask_array(fname=f'{fname}_pct_data_available.tif',
                    data=tmp_data_array,
                    data_var=None, method=None)

            # Add one dimension and save to disk max gap-length
            tmp_data_array = self.qa_analytics.max_gap_length.expand_dims(
                    dim='time', axis=0)
            save_dask_array(fname=f'{fname}_max_gap_length.tif',
                    data=tmp_data_array,
                    data_var=None, method=None)

            # Save mask
            #save_dask_array(fname=f'{fname}_qa_analytics_mask.tif',
            #        data=self.qa_analytics.mask,
            #        data_var=None, method=None)
            
            del(tmp_data_array)
            if os.path.isfile(fname):
                self.progressBar.setFormat('Save Done..')
                self.btn_Interpolation.setEnabled(True)
                self.btn_QA_saves.setEnabled(False)
            else:
                self.progressBar.setFormat('Error: output file')

            # Standard cursor
            QtWidgets.QApplication.restoreOverrideCursor()

    
    # Radio buttons
    
    @pyqtSlot()
    def on_radioButton_SatName_activated(self):
        if self.radioButton_SatName.isChecked():
            self.ln_SatName.setEnabled(True)
        else:
            self.ln_SatName.setEnabled(False)
    
    @pyqtSlot()
    def on_ln_SatName_activated(self):
        spacecraft = self.ln_SatName.text()
        product = self.ln_ProdName.text()
        resolution = self.ln_SpatialRes.text()

        self.ln_dataVar.setText(spacecraft+"_"+product+"_"+resolution)

    @pyqtSlot()
    def on_ln_ProdName_activated(self):
        spacecraft = self.ln_SatName.text()
        product = self.ln_ProdName.text()
        resolution = self.ln_SpatialRes.text()

        self.ln_dataVar.setText(spacecraft+"_"+product+"_"+resolution)
    
    @pyqtSlot()
    def on_ln_SpatialRes_activated(self):
        spacecraft = self.ln_SatName.text()
        product = self.ln_ProdName.text()
        resolution = self.ln_SpatialRes.text()

        self.ln_dataVar.setText(spacecraft+"_"+product+"_"+resolution)
    

    @pyqtSlot()
    def on_radioButton_ProdName_activated(self):
        if self.radioButton_ProdName.isChecked():
            self.ln_ProdName.setEnabled(True)
        else:
            self.ln_ProdName.setEnabled(False)
    @pyqtSlot()
    def on_radioButton_SpatialRes_activated(self):
        if self.radioButton_SpatialRes.isChecked():
            self.ln_SpatialRes.setEnabled(True)
        else:
            self.ln_SpatialRes.setEnabled(False)   

if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    window = genericImporterUI()
    app.exec_()
