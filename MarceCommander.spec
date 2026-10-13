# -*- mode: python ; coding: utf-8 -*-
"""Empaquetado de Marce Commander.

El hook de PySide6 copia el Qt entero, sin mirar qué importa la aplicación. MC
usa sólo QtCore, QtGui y QtWidgets, así que acá se filtran a mano los binarios
y datos que sobran. Es la diferencia entre ~112 MB y la mitad.
"""

import os

# DLLs de Qt que MC no toca. opengl32sw es el renderer OpenGL por software que
# Qt usa de respaldo; una aplicación de widgets puros no lo necesita.
EXCLUDED_DLLS = {
    "opengl32sw.dll",
    "qt6quick.dll", "qt6qml.dll", "qt6qmlmodels.dll", "qt6qmlmeta.dll",
    "qt6qmlworkerscript.dll", "qt6quickwidgets.dll", "qt6quickcontrols2.dll",
    "qt6quicktemplates2.dll", "qt6quickdialogs2.dll",
    "qt6pdf.dll", "qt6pdfwidgets.dll",
    "qt6network.dll", "qt6sql.dll", "qt6test.dll", "qt6designer.dll",
    "qt6multimedia.dll", "qt6charts.dll", "qt63dcore.dll",
    "qt6websockets.dll", "qt6webchannel.dll",
    "qt6virtualkeyboard.dll", "qt6spatialaudio.dll",
}

# Plugins de Qt que no se cargan nunca en esta aplicación.
EXCLUDED_PLUGIN_DIRS = (
    "plugins\\qmltooling", "plugins\\sqldrivers", "plugins\\multimedia",
    "plugins\\networkinformation", "plugins\\tls", "plugins\\position",
    "plugins\\sensors", "plugins\\virtualkeyboard", "plugins\\renderers",
    "plugins\\canbus", "plugins\\designer", "plugins\\assetimporters",
)


def keep_binary(entry):
    dest = entry[0]
    name = os.path.basename(dest).lower()
    if name in EXCLUDED_DLLS:
        return False
    low = dest.lower().replace("/", "\\")
    if any(d in low for d in EXCLUDED_PLUGIN_DIRS):
        return False
    return True


def keep_data(entry):
    low = entry[0].lower().replace("/", "\\")
    # Las traducciones de Qt son ~7 MB y MC tiene sus textos en el código.
    if "translations" in low:
        return False
    if any(d in low for d in EXCLUDED_PLUGIN_DIRS):
        return False
    return True


a = Analysis(
    ["run_mc.py"],
    pathex=[],
    binaries=[],
    datas=[("mc/resources", "mc/resources")],
    hiddenimports=[],
    excludes=[
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets",
        "PySide6.QtNetwork", "PySide6.QtSql", "PySide6.QtTest",
        "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtMultimedia",
        "PySide6.QtCharts", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
        "PySide6.QtDesigner", "PySide6.Qt3DCore",
        "tkinter", "unittest", "pydoc", "doctest", "pdb",
        "xml", "xmlrpc", "http", "email", "ftplib", "sqlite3",
    ],
    noarchive=False,
)

a.binaries = [b for b in a.binaries if keep_binary(b)]
a.datas = [d for d in a.datas if keep_data(d)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="MarceCommander",
    debug=False,
    strip=False,
    upx=False,
    console=False,          # sin consola: es una aplicación de ventanas
    icon="mc/resources/icon.ico",
)

coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False,
    upx=False,
    name="MarceCommander",
)
