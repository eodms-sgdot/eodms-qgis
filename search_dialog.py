# -*- coding: utf-8 -*-
"""
/***************************************************************************
 SearchDialog
                                 A QGIS plugin
 A plugin used to access the EODMS
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2022-05-19
        git sha              : $Format:%H$
        copyright            : Copyright (c) His Majesty the King in Right of 
                                Canada, as represented by the Minister of 
                                Natural Resources, 2023.
        email                : eodms-sgdot@nrcan-rncan.gc.ca
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""



import os
from eodms_rapi import EODMSRAPI
import json
from datetime import datetime
# from dateutil.parser import parse

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from PyQt5.QtWidgets import QScrollArea, QWidget, QAbstractItemView
from qgis.PyQt.QtCore import QCoreApplication
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5.QtCore import QDate, QTime, QDateTime, Qt
from qgis.core import *
from qgis.PyQt.QtWidgets import *

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'search_dialog_base.ui'))

MESSAGE_CATEGORY = 'RAPI Tasks'
DEFAULT_MAX = "150"

class CollectionTask(QgsTask):
    def __init__(self, desc, dialog):
        super().__init__(desc, QgsTask.CanCancel)

        self.dialog = dialog
        self.eodms = dialog.eodms
        self.desc = desc
        self.exception = None

    def run(self):

        self.eodms.post_message(f'Started task {self.desc}',
                                tag=MESSAGE_CATEGORY)

        self.dialog.list_collections()

        return True

    def finished(self, result):
        """This method is automatically called when self.run returns.
        result is the return value from self.run.
        This function is automatically called when the task has completed (
        successfully or otherwise). You just implement finished() to do
        whatever
        follow up stuff should happen after the task is complete. finished is
        always called from the main thread, so it's safe to do GUI
        operations and raise Python exceptions here.
        """

        self.eodms.post_message(f"result: {result}")
        if result:
            self.eodms.post_message(f'Task "{self.desc}" completed',
                                    tag=MESSAGE_CATEGORY, level=Qgis.Success)
        elif self.exception is None:
            self.eodms.post_message(f'Task "{self.desc}" not successful '
                                    f'but without exception (probably the '
                                    f'task was manually canceled by the '
                                    f'user)', tag=MESSAGE_CATEGORY,
                                    level=Qgis.Warning)
        else:
            self.eodms.post_message(f'Task "{self.desc}" Exception: '
                                    f'{self.exception}',
                                    tag=MESSAGE_CATEGORY,
                                    level=Qgis.Critical)
            raise self.exception

        self.eodms.post_message("Collection task complete.")

    def cancel(self):
        self.eodms.post_message(f'Task "{self.description}" was cancelled',
                                tag=MESSAGE_CATEGORY, level=Qgis.Info)
        super().cancel()

class SearchDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None, eodms=None):
        """Constructor."""
        super(SearchDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        # self.butLogin.clicked.connect(self.login)

        self.eodms = eodms
        self.rapi = eodms.rapi

        self.butGetList.clicked.connect(self.get_list)
        self.butSelect.clicked.connect(self.select_collections)
        self.butAddRange.clicked.connect(self.add_date_range)
        self.butRemoveRange.clicked.connect(self.remove_date_range)
        self.butInterval.clicked.connect(self.add_date_interval)
        self.cboPrevSrch.activated.connect(self.select_search)
        # self.boxOkCancel.accepted.connect(self.submit_search)

        # self.collections = rapi.get_collections(as_list=True, opt='title')

        # for coll in self.collections:
        #     # item = QtGui.QListView(coll)
        #     self.lstColl.addItem(coll)

        # self.eodms.post_message(f"self: {self}")
        # self.eodms.post_message(f"self dirs: {dir(self)}")
        # self.eodms.post_message(f"parent: {parent}")
        # self.eodms.post_message(f"parent dirs: {dir(parent)}")

        self.searches = None
        if os.path.exists(self.eodms.prev_srch_fn):
            with open(self.eodms.prev_srch_fn, 'r') as f:
                self.searches = json.load(f)
        self.cboPrevSrch.addItem("")
        self._add_prev_searches()

        layer = self.eodms.iface.activeLayer()

        if layer is not None and not isinstance(layer, QgsRasterLayer):
            features = layer.selectedFeatures()

            if len(features) > 0:
                # wkts = []
                geom = None
                for feat in features:
                    geom = feat.geometry() if geom is None \
                            else geom.combine(feat.geometry())
                                # geom = feat.geometry()
                                # wkt_str = geom.asWkt()
                                # wkts.append(wkt_str)

                self.txtFeatures.setText(geom.asWkt())

        self.cboGeoOp.addItems(['CONTAINS', 'CONTAINED BY', 'CROSSES',
                                'DISJOINT WITH', 'INTERSECTS', 'OVERLAPS',
                                'TOUCHES', 'WITHIN'])
        self.cboGeoOp.setCurrentText('INTERSECTS')

        # self.tabFilters.setVisible(False)
        for _ in range(self.tabFilters.count()):
            self.tabFilters.removeTab(0)

        self.txtMax.setText(DEFAULT_MAX)

        self.coll_filters = {}

        self.date_ranges = []

        self.lstDates.clear()

        end_dt = QDateTime.currentDateTime()
        start_dt = end_dt.addDays(-1)
        self.datStart.setDateTime(start_dt)
        self.datEnd.setDateTime(end_dt)

        self.cboInterval.addItems(['hour(s)', 'day(s)', 'week(s)',
                                   'month(s)', 'year(s)'])

        # Clear date tab widget
        # for i in range(self.tabDates.count()):
        #     self.tabDates.removeTab(0)
        # self.tabDates.setTabText(0, 'Range 1')
        # self.eodms.post_message(f"self dirs: {dir(self)}")

    def _add_prev_searches(self):

        if self.searches is None:
            return None

        for k, v in self.searches.items():
            date = self._convert_date(k, "%Y%m%d_%H%M%S", 
                                        "%Y-%m-%d,%H:%M:%S")
            coll = list(v.keys())
            self.cboPrevSrch.addItem(f"{date} ({', '.join(coll)})")

        # self.cboPrevSrch

    def _convert_date(self, date, in_format, out_format):
        if date is None or date == '':
            return ''

        date_obj = datetime.strptime(date, in_format)

        return date_obj.strftime(out_format)

    def add_date_interval(self):

        date_int = self.txtInt.text()
        if not date_int.isdigit():
            msgBox = QMessageBox()
            msgBox.setIcon(QMessageBox.Warning)
            msgBox.setText("Please enter a valid integer for the date "
                           "interval.")
            msgBox.setWindowTitle("Invalid Interval")
            msgBox.setStandardButtons(QMessageBox.Ok)
            returnValue = msgBox.exec()
            return None

        interval_type = self.cboInterval.currentText()
        if date_int == 1:
            interval_type = interval_type.replace('(s)', '')
        else:
            interval_type = interval_type.replace('(s)', 's')
        interval_str = f"{date_int} {interval_type}"

        self.lstDates.addItem(interval_str)

    def add_date_range(self):

        start_dt = self.datStart.dateTime().toPyDateTime()
        end_dt = self.datEnd.dateTime().toPyDateTime()

        start = start_dt.strftime('%Y%m%d_%H%M%S')
        end = end_dt.strftime('%Y%m%d_%H%M%S')

        date_range = f"{start}-{end}"
        self.lstDates.addItem(date_range)

        # tab_count = self.tabDates.count()
        #
        # tab = QtWidgets.QWidget()
        # hbox = QtWidgets.QHBoxLayout(tab)
        #
        # dteDate1 = QtWidgets.QDateTimeEdit()
        # dteDate1.setObjectName(f"dteTab{tab_count + 1}Date1")
        # dt_font = QtGui.QFont()
        # dt_font.setPointSize(7)
        # dteDate1.setFont(dt_font)
        # hbox.addWidget(dteDate1)
        #
        # lblTo = QtWidgets.QLabel()
        # lblTo.setText("to")
        # lblTo.setAlignment(QtCore.Qt.AlignCenter)
        # font = QtGui.QFont()
        # font.setPointSize(12)
        # lblTo.setFont(font)
        # hbox.addWidget(lblTo)
        #
        # dteDate2 = QtWidgets.QDateTimeEdit()
        # dteDate2.setObjectName(f"dteTab{tab_count + 1}Date2")
        # dt_font = QtGui.QFont()
        # dt_font.setPointSize(7)
        # dteDate2.setFont(dt_font)
        # hbox.addWidget(dteDate2)
        #
        # # if tab_count == 1:
        # #     self.tabDates.setCurrentIndex(tab_count - 1)
        # #     tab = self.tabDates.tabBar()
        # #     tab.addWidget(hbox)
        # # else:
        # self.tabDates.addTab(tab, f"Range {tab_count + 1}")
        #
        # # for i in range(self.tabDates.count()):
        # self.date_ranges.append([dteDate1, dteDate2])

    def fill_tab(self, tab, collection):
        coll_id = self.rapi.get_collection_id(collection)
        fields = self.rapi.get_available_fields(coll_id) #, ui_fields=True)

        tab.setWidgetResizable(True)

        # tab.layout = QtWidgets.QVBoxLayout(tab.widget())
        tab_layout = QtWidgets.QVBoxLayout(tab.widget())

        # self.eodms.post_message("")
        # self.eodms.post_message(f"coll_id: {coll_id}")
        # self.eodms.post_message(f"fields['search']: {fields['search']}")

        for field in fields['search']:
            
            if not fields[field].get('displayed'): continue

            # self.eodms.post_message(f"coll_id: {coll_id}")
            lblField = QtWidgets.QLabel()
            # self.eodms.post_message(f"field: {field}")
            lblField.setText(field)
            tab.layout.addWidget(lblField)
            tab.setLayout(tab.layout)

        return tab

    def get_list(self):

        self.butGetList.setEnabled(False)
        self.butSelect.setEnabled(False)

        coll_task = CollectionTask('RAPI collection', self)
        QgsApplication.taskManager().addTask(coll_task)

        while coll_task.status() not in [QgsTask.Complete, QgsTask.Terminated]:
            QCoreApplication.processEvents()
        while QgsApplication.taskManager().countActiveTasks() > 0:
            QCoreApplication.processEvents()

        self.butGetList.setEnabled(True)
        self.butSelect.setEnabled(True)

        # self.eodms.post_message(f"Number of taskManager tasks: "
        #                         f"{QgsApplication.taskManager().countActiveTasks()}")

        # while tsk.status() not in [QgsTask.Complete, QgsTask.Terminated]:
        #     self.eodms.post_message(f"tsk.status(): {tsk.status()}")
        #     self.eodms.post_message(f"QgsTask.Complete: {QgsTask.Complete}")
        #     self.eodms.post_message(f"QgsTask.Terminated: {QgsTask.Terminated}")
        #     QCoreApplication.processEvents()

        # while QgsApplication.taskManager().countActiveTasks() > 0:
        #     QCoreApplication.processEvents()

    # def list_done(self):

    def list_collections(self):

        self.eodms.post_message("Getting collections...")

        self.lstColl.clear()
        self.lstColl.addItem("Getting collections...")

        self.collections = self.rapi.get_collections(as_list=True, opt='title')

        # self.eodms.post_message(f"collections: {self.collections}")

        self.lstColl.clear()
        if self.collections is None:
            self.lstColl.addItem("Cannot get a list of collections.")
        else:
            for coll in sorted(self.collections):
                # item = QtGui.QListView(coll)
                self.lstColl.addItem(coll)

    def clear_filters(self):
        for _ in range(0, self.tabFilters.count()):
            self.tabFilters.removeTab(0)

    def create_filters(self, collections=None):

        if collections is None:
            collections = self.selected_colls

        # self.eodms.post_message(', '.join([c.text()
        #                       for c in self.selected_colls]))

        self.coll_filters = {}

        self.clear_filters()

        for coll in collections:
            # tab = self.create_tab(coll.text())
            # self.eodms.post_message(tab)
            # self.eodms.post_message(dir(tab))

            # tab = QtWidgets.QWidget()

            # tab = QScrollArea()
            # tab.setWidget(QWidget())

            # self.tabFilters.addTab(tab, coll.text())

            # self.fill_tab(tab, coll.text())

            scroll = QtWidgets.QScrollArea()

            tab = QtWidgets.QWidget()
            scroll.setWidget(tab)
            scroll.setWidgetResizable(True)
            scroll.setObjectName(f"scr{coll.replace(' ', '')}")

            v_lay = QtWidgets.QVBoxLayout(tab)

            coll_id = self.rapi.get_collection_id(coll)
            fields = self.rapi.get_available_fields(coll_id) #, ui_fields=True)

            if self.rapi.err_occurred:
                self.eodms.post_message(self.rapi.err_msg)

            # self.eodms.post_message("")
            # self.eodms.post_message(f"coll_id: {coll_id}")
            # self.eodms.post_message(f"fields['search']: {fields['search']}")

            cur_fields = self.coll_filters.get(coll)

            if cur_fields is None:
                cur_fields = []

            for field, params in fields['search'].items():

                if not params.get('displayed'): continue

                # self.eodms.post_message(f"coll_id: {coll_id}")
                # self.eodms.post_message(f"field: {field}")
                h_lay = QtWidgets.QHBoxLayout()

                obj_name = field.replace(' ', '')

                # Add label
                lblField = QtWidgets.QLabel()
                lblField.setObjectName(f"lbl{obj_name}")
                lblField.setText(f"{field}:")
                lblField.setFixedWidth(150)
                h_lay.addWidget(lblField)

                # Add operator
                cboOp = QtWidgets.QComboBox()
                cboOp.setObjectName(f"cbo{obj_name}")
                cboOp.setFixedWidth(120)
                cboOp.addItems(self.eodms.operators)
                # combo_str = '\nCombo list:\n'
                # for idx in range(0, cboOp.count()):
                #     combo_str += f"  {cboOp.itemText(idx)}\n"
                # self.eodms.post_message(combo_str)
                h_lay.addWidget(cboOp)

                # Add edit line

                choices = params.get('choices')
                allow_multiple = params.get('allowMultiple')
                data_type = params.get('datatype')

                if choices is None:
                    objValue = QtWidgets.QLineEdit()
                elif allow_multiple:
                    objValue = QtWidgets.QListWidget()
                    objValue.setSelectionMode(
                        QAbstractItemView.ExtendedSelection)
                    for choice in choices:
                        # choice_val = choice['value']
                        choice_val = choice['label']
                        # if lbl_choice == 'Any':
                        #     continue
                        if choice_val == '':
                            choice_val = choice['value']
                        if choice_val.lower() == 'any':
                            choice_val = ''
                        listWidgetItem = QtWidgets.QListWidgetItem(choice_val)
                        objValue.addItem(listWidgetItem)
                else:
                    objValue = QtWidgets.QComboBox()
                    # choices = [choice['value'] for choice in choices]
                    # choices = [choice['label'] for choice in choices]
                    # choices = [choice['value'] if choice['label'] == ''
                    #            else choice['label'] for choice in choices]
                    cbo_choices = []
                    for choice in choices:
                        value = choice['value'] if choice['label'] == '' \
                                else choice['label']
                        if value == 'Any':
                            value = ''
                        cbo_choices.append(value)

                    if '' not in cbo_choices:
                        cbo_choices.insert(0, '')

                    objValue.addItems(cbo_choices)

                objValue.setObjectName(f"obj{obj_name}")
                h_lay.addWidget(objValue)

                cur_fields.append([field, cboOp, objValue])

                # h_lay.addStretch(1)

                v_lay.addLayout(h_lay)

            self.coll_filters[coll] = cur_fields

            v_lay.addStretch()

            # scroll.setFixedHeight(400)

            self.tabFilters.addTab(scroll, coll)

        self.tabFilters.setVisible(True)

    def select_collections(self):

        self.selected_colls = [coll.text() 
                               for coll in self.lstColl.selectedItems()]

        self.create_filters()

    def select_search(self):
        search_sel = self.cboPrevSrch.currentText()

        date_str = search_sel.split(' ')[0]
        date = self._convert_date(date_str, "%Y-%m-%d,%H:%M:%S", 
                                  "%Y%m%d_%H%M%S")
        
        self.lstDates.clear()
        self.clear_filters()
        self.txtMax.setText(DEFAULT_MAX)
        self.lstColl
        
        if date == '':
            return None
        
        cur_search = self.searches[date]

        # self.eodms.post_message(f"cur_search: {cur_search}")

        # Create filters
        colls = cur_search.keys()
        # self.eodms.post_message(f"colls: {colls}")
        self.create_filters(colls)

        # self.eodms.post_message(f"self.coll_filters: {self.coll_filters}")

        # Set date ranges
        first_item = cur_search.get(next(iter(cur_search)))
        dates = first_item.get('dates')
        max_res = first_item.get('max_res')

        self.txtMax.setText(max_res)

        self.list_collections()

        for date in dates:
            if isinstance(date, str):
                date_range = date
            else:
                date_range = f"{date.get('start')}-{date.get('end')}"
            self.lstDates.addItem(date_range)

        for coll, v in cur_search.items():

            filters = v.get('filters')

            # self.lstDates = None

            for x in range(self.lstColl.count()):
                item = self.lstColl.item(x)
                if self.eodms.rapi.get_collection_id(item.text()) == coll:
                    self.lstColl.item(x).setSelected(True)

            filt_objs = self.coll_filters.get(coll)

            self.eodms.post_message(f"filt_objs: {filt_objs}")

            for filter_name, v in filters.items():
                op_val = v[0]
                f_val = v[1]
                self.eodms.post_message(f"filter_name: {filter_name}")
                self.eodms.post_message(f"op_val: {op_val}")
                self.eodms.post_message(f"f_val: {f_val}")
                for obj in filt_objs:
                    if filter_name == obj[0]:
                        op_obj = obj[1]
                        val_obj = obj[2]

                        op_obj.setCurrentText(op_val)
                        if isinstance(val_obj, QListWidget):
                            for x in range(val_obj.count()):
                                item = val_obj.item(x)
                                if item.text() in f_val:
                                    val_obj.item(x).setSelected(True)
                        elif isinstance(val_obj, QComboBox):
                            for v in f_val:
                                val_obj.setCurrentText(str(v))
                        elif isinstance(val_obj, QLineEdit):
                            val_obj.setText(str(f_val[0]))

                        self.eodms.post_message(f"op_obj: {op_obj}")
                        self.eodms.post_message(f"val_obj: {val_obj}")
                
            # msgBox = QMessageBox()
            # msgBox.setText(f"filters: {filters}\nfilt_objs: {filt_objs}")
            # msgBox.setStandardButtons(QMessageBox.Ok)
            # returnValue = msgBox.exec()

            # self.eodms.post_message(f"filters: {filters}")

    def get_widgets(self, parent, widgets=None):

        if widgets is None:
            widgets = []

        for widget in parent.children():
            widgets.append(widget)
            if len(widget.children()) > 0:
                self.get_widgets(widget, widgets)

        return widgets

    def list_widgets(self, parent, indent=0):

        for widget in parent.children():
            # self.eodms.post_message(indent*'-' + f"widget: {widget}")
            # self.eodms.post_message(indent*'-' + f"widget name: "
            #                                      f"{widget.objectName()}")
            if len(widget.children()) > 0:
                self.list_widgets(widget, indent + 1)

    def remove_date_range(self):

        sel_dates = self.lstDates.selectedItems()
        if not sel_dates: return
        for dt in sel_dates:
            # row = dt.row()
            self.lstDates.takeItem(self.lstDates.row(dt))