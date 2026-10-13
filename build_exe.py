"""Empaqueta MC en un ejecutable. --onedir por defecto, --onefile opcional."""
import shutil, subprocess, sys, os

onefile = "--onefile" in sys.argv
name = "MarceCommander"
# Qt trae mucho que MC no usa; excluirlo baja bastante el tamano.
excludes = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml",
    "PySide6.QtQuick", "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtMultimedia",
    "PySide6.QtNetwork", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner",
    "PySide6.QtOpenGL", "PySide6.QtPdf", "PySide6.QtPrintSupport",
    "tkinter", "unittest", "pydoc", "doctest", "email", "html", "xml",
]
cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
       "--windowed", "--name", name,
       "--onefile" if onefile else "--onedir"]
for e in excludes:
    cmd += ["--exclude-module", e]
cmd.append("run_mc.py")
sys.exit(subprocess.call(cmd))
