"""Punto de entrada: python -m mc [ruta_izquierda] [ruta_derecha]"""

from __future__ import annotations

import os
import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from . import APP_NAME
    from .config import config

    # Las rutas de la línea de comandos pisan las guardadas en el ini.
    args = [a for a in sys.argv[1:] if os.path.isdir(a)]
    if len(args) >= 1:
        config.set("general", "left_path", os.path.abspath(args[0]))
    if len(args) >= 2:
        config.set("general", "right_path", os.path.abspath(args[1]))

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Marce")

    from . import app_icon

    app.setWindowIcon(app_icon())

    # Idioma y tema van antes de construir la ventana: así los widgets nacen
    # con el texto y los colores definitivos, sin parpadeo ni retraducciones.
    from . import i18n, theme

    i18n.set_language(config.get("general", "language", "auto"))
    theme.apply(app, config.get("general", "theme", "auto"),
                config.get("general", "ui_font_family", ""),
                config.get_int("general", "ui_font_size", 9))

    from .mainwindow import MainWindow

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
