# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DownloadDialog
                                 A QGIS plugin
 A plugin used to access the EODMS
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2022-05-19
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Kevin Ballantyne/Natural Resources Canada
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
from dateutil import parser
from dateutil import tz

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import *

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'download_dialog_base.ui'))

MESSAGE_CATEGORY = 'RAPI Tasks'

class GetOrderTask(QgsTask):

    def __init__(self, desc, dialog):
        super().__init__(desc, QgsTask.CanCancel)

        self.dialog = dialog
        self.eodms = dialog.eodms
        self.rapi = self.eodms.rapi
        self.desc = desc
        self.exception = None
        self.orders = []

    def run(self):

        self.eodms.post_message(f'Started task {self.desc}',
                                tag=MESSAGE_CATEGORY)

        self.orders = self.rapi.get_orders()

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

        if result:
            self.eodms.post_message(
                f'Task "{self.desc}" completed', tag=MESSAGE_CATEGORY,
                level=Qgis.Success)
        elif self.exception is None:
            self.eodms.post_message(f'Task "{self.desc}" not successful '
                                    f'but without exception (probably the '
                                    f'task was manually canceled by the '
                                    f'user)', tag=MESSAGE_CATEGORY,
                                    level=Qgis.Warning)
        else:
            self.eodms.post_message(
                f'Task "{self.desc}" Exception: {self.exception}',
                tag=MESSAGE_CATEGORY, level=Qgis.Critical)
            raise self.exception

        self.eodms.post_message("Collection task complete.")

    def cancel(self):
        self.eodms.post_message(f'Task "{self.description}" was '
                                 f'cancelled', tag=MESSAGE_CATEGORY,
                                level=Qgis.Info)
        super().cancel()

class DownloadDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None, eodms=None):
        """Constructor."""
        super(DownloadDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        self.eodms = eodms
        self.rapi = eodms.rapi
        self.orders = []

        self.butBrowse.clicked.connect(self.show_browser_dialog)
        self.butOk.clicked.connect(self.click_ok)
        self.butCancel.clicked.connect(self.click_cancel)
        self.butRefresh.clicked.connect(self.refresh_orders)

        self.txtPath.setText(self.eodms.download_folder)

        self.fill_orders()

    def click_cancel(self):
        self.close()

    def click_ok(self):
        path_txt = self.txtPath.text()

        if len(path_txt) == 0:
            msgBox = QMessageBox()
            msgBox.setIcon(QMessageBox.Warning)
            msgBox.setText("Please enter a download folder.")
            msgBox.setWindowTitle("No Download Folder")
            msgBox.setStandardButtons(QMessageBox.Ok)
            returnValue = msgBox.exec()
            return None

        self.accept()

    def convert_date(self, date_str):

        in_date = parser.parse(date_str)

        from_zone = tz.tzutc()
        to_zone = tz.tzlocal()

        in_date = in_date.replace(tzinfo=from_zone)

        return in_date.astimezone(to_zone)

    def refresh_orders(self):

        self.eodms.post_message("Refreshing order list...",
                                tag=MESSAGE_CATEGORY)

        self.enable_disable_objs(False)
        self.fill_orders()

        self.enable_disable_objs(True)

    # TODO Rename this here and in `refresh_orders`
    def enable_disable_objs(self, state):
        self.tblImages.setEnabled(state)
        self.butRefresh.setEnabled(state)
        self.butOk.setEnabled(state)

    def fill_orders(self):

        ord_task = GetOrderTask('RAPI Get Orders', self)
        QgsApplication.taskManager().addTask(ord_task)

        while ord_task.status() not in [QgsTask.Complete, QgsTask.Terminated]:
            QCoreApplication.processEvents()
        while QgsApplication.taskManager().countActiveTasks() > 0:
            QCoreApplication.processEvents()

        self.orders = ord_task.orders
        # self.eodms.post_message(f"Orders: {self.orders}", tag=MESSAGE_CATEGORY)

        if len(self.orders) > 0:
            col_names = ['Order Id', 'Order Item Id', 'Record Id',
                         'Collection', 'Date Submitted', 'Status Message']
            self.tblImages.setColumnCount(len(col_names))
            self.tblImages.setHorizontalHeaderLabels(col_names)
            self.tblImages.setRowCount(len(self.orders))

            for idx, order in enumerate(self.orders):

                order_id = order['orderId']
                order_item_id = order['itemId']
                record_id = order['recordId']
                coll_id = order['collectionId']
                date_submitted = self.convert_date(order['dateSubmitted'])
                status_msg = order['statusMessage']

                # self.eodms.post_message(f"Order ID: {order_id}",
                #                         tag=MESSAGE_CATEGORY)
                # self.eodms.post_message(f"Order Item ID: {order_item_id}",
                #                         tag=MESSAGE_CATEGORY)
                # self.eodms.post_message(f"Record ID: {record_id}",
                #                         tag=MESSAGE_CATEGORY)
                # self.eodms.post_message(f"Collection: {coll_id}",
                #                         tag=MESSAGE_CATEGORY)
                # self.eodms.post_message(f"Date Submitted: {date_submitted}",
                #                         tag=MESSAGE_CATEGORY)
                # self.eodms.post_message(f"Status Message: {status_msg}",
                #                         tag=MESSAGE_CATEGORY)

                self.tblImages.setItem(idx, 0,
                                       QtWidgets.QTableWidgetItem(
                                           str(order_id)))
                self.tblImages.setItem(idx, 1,
                                       QtWidgets.QTableWidgetItem(
                                           str(order_item_id)))
                self.tblImages.setItem(idx, 2,
                                       QtWidgets.QTableWidgetItem(record_id))
                self.tblImages.setItem(idx, 3,
                                       QtWidgets.QTableWidgetItem(coll_id))
                self.tblImages.setItem(idx, 4,
                                       QtWidgets.QTableWidgetItem(
                                           date_submitted.strftime(
                                               "%Y-%m-%d, %H:%M:%S")))
                self.tblImages.setItem(idx, 5,
                                       QtWidgets.QTableWidgetItem(status_msg))

                lyr_sel = self.eodms.get_selection()

                # self.eodms.post_message(f"record IDs: "
                #                         f"{[o['recordId'] for o in self.orders]}",
                #                         tag=MESSAGE_CATEGORY)

                for sel in lyr_sel:
                    if idx := [
                        i
                        for i, o in enumerate(self.orders)
                        if o['recordId'] == sel['RECORD_ID']
                    ]:
                        self.tblImages.selectRow(idx[0])

    def show_browser_dialog(self):

        if folder := QFileDialog.getExistingDirectory(
            self,
            self.eodms.tr("Open Directory"),
            self.eodms.download_folder,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        ):
            self.txtPath.setText(folder)