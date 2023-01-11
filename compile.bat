@echo off
call "C:\Program Files\QGIS 3.22.8\bin\o4w_env.bat"
call "C:\Program Files\QGIS 3.22.8\bin\qt5.bat"
call "C:\Program Files\QGIS 3.22.8\bin\py3_env.bat"

@echo on
pyrcc5 -o resources.py resources.qrc

pause