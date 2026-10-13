"""Comprueba que la ventana de MC abre de verdad y guarda una captura.

Pensado para correr bajo Xvfb dentro del contenedor de tools/Dockerfile.linux-gui,
pero sirve igual en una máquina Linux con escritorio:

    python tools/gui_check.py [salida.png]

Se diferencia de tests/smoke.py en que éste usa el plugin de plataforma real
(xcb) en vez de offscreen, así que falla si falta alguna librería del sistema.
La captura la saca la propia ventana con grab(), sin herramientas externas.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    out = sys.argv[1] if len(sys.argv) > 1 else "linux_gui.png"

    app = QApplication(sys.argv)
    platform_name = app.platformName()
    print(f"plugin de plataforma: {platform_name}")
    if platform_name == "offscreen":
        print("ERROR: se esperaba un plugin real (xcb/wayland), no offscreen")
        return 1

    from mc import app_icon, i18n, theme
    from mc.config import config

    app.setWindowIcon(app_icon())
    i18n.set_language(config.get("general", "language", "auto"))
    theme.apply(app, config.get("general", "theme", "auto"),
                config.get("general", "ui_font_family", ""),
                config.get_int("general", "ui_font_size", 9))

    from mc.mainwindow import MainWindow

    win = MainWindow()
    win.resize(1360, 860)
    win.show()

    result = {"code": 1}

    def capture() -> None:
        try:
            print(f"ventana visible: {win.isVisible()}")
            print(f"tamaño: {win.width()}x{win.height()}")
            print(f"panel izquierdo: {win.left.path}")
            print(f"filas listadas: {win.left.model.rowCount()}")
            print(f"comandos: {len(win.commands)}")
            print(f"tema: {theme.current().name}   idioma: {i18n.current()}")
            ok = win.grab().save(out, "PNG")
            print(f"captura guardada en {out}: {ok}")
            result["code"] = 0 if (ok and win.isVisible()) else 1
        finally:
            app.quit()

    # Un respiro para que el gestor de ventanas mapee la ventana antes de grabar.
    QTimer.singleShot(1500, capture)
    app.exec()
    return result["code"]


if __name__ == "__main__":
    sys.exit(main())
