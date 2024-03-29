# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Eodms
                                 A QGIS plugin
 A plugin used to access the EODMS
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2022-05-19
        copyright            : (C) 2023 by Kevin Ballantyne/Natural Resources
                                Canada
        email                : eodms-sgdot@nrcan-rncan.gc.ca
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""

import pip
import requests
import json
import importlib.util
from packaging import version
import sys
import subprocess
import platform

from qgis.core import Qgis, QgsMessageLog

# noinspection PyPep8Naming
def classFactory(iface):    # pylint: disable=invalid-name
    """Load Eodms class from file Eodms.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """

    check_eodms_rapi()

    #
    from .eodms import Eodms
    return Eodms(iface)


# TODO Rename this here and in `classFactory`
def check_eodms_rapi():

    newest_version = '0'
    pkg_url = 'https://pypi.org/pypi/py-eodms-rapi/json'
    req = requests.get(pkg_url)

    if req.status_code == requests.codes.ok:
        j = req.json()
        info = j.get('info')
        newest_version = info.get('version')

    name = 'eodms_rapi'
    install_pkg = False
    if (spec := importlib.util.find_spec(name)) is not None:
        # If you choose to perform the actual import ...
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)

        pkg_version = module.__version__

        # QgsMessageLog.logMessage(f"pkg_version: {pkg_version}", tag="Client.base", level=Qgis.Info)
        # QgsMessageLog.logMessage(f"pkg_version: {newest_version}", tag="Client.base", level=Qgis.Info)

        if pkg_version < newest_version:
            install_pkg = True
    else:
        install_pkg = True

    if install_pkg:
        # if platform.system() == 'Windows':
        QgsMessageLog.logMessage(
            "Installing py-eodms-rapi Python package...", level=Qgis.Info
        )
        cmd = 'pip install --trusted-host pypi.org --trusted-host ' \
                'pypi.python.org --trusted-host files.pythonhosted.org ' \
                'py-eodms-rapi'
        pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        # else:
        #     pipe = subprocess.Popen(['pip', 'install', 
        #                     '--trusted-host pypi.org', 
        #                     '--trusted-host pypi.python.org', 
        #                     '--trusted-host files.pythonhosted.org', 
        #                     'py-eodms-rapi'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        output, error = pipe.communicate()

        QgsMessageLog.logMessage(
            "Installion complete.", level=Qgis.Info
        )
    else:
        QgsMessageLog.logMessage(
            "py-eodms-rapi Python package already installed.", level=Qgis.Info
        )
