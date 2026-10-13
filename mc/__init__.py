"""Marce Commander — gestor de archivos de doble panel."""

from __future__ import annotations

import os
import sys

__version__ = "1.1.0"
APP_NAME = "Marce Commander"


def resource_path(name: str) -> str:
    """Ruta a un archivo de mc/resources, sirva desde el código o empaquetado.

    PyInstaller extrae los datos a un directorio temporal cuya ruta deja en
    `sys._MEIPASS`; desde el código fuente hay que resolver relativo a este
    archivo. Sin esto, el icono aparece al correr con `python -m mc` y
    desaparece en el ejecutable.
    """
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "mc", "resources", name)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", name)


def app_icon():
    """QIcon de la aplicación, o un icono vacío si falta el archivo."""
    from PySide6.QtGui import QIcon

    path = resource_path("icon.ico")
    return QIcon(path) if os.path.exists(path) else QIcon()
