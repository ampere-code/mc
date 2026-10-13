"""Configuración persistente en un ini.

Mismo espíritu que el WINCMD.INI de Total Commander: un ini plano, legible y
editable a mano. No es compatible con el formato de TC. La ubicación la decide
`platform.config_dir()`, que sigue la convención de cada sistema.
"""

from __future__ import annotations

import configparser
from pathlib import Path

from .platform import (
    config_dir, default_mono_font, default_terminal, default_ui_font,
)

CONFIG_PATH = config_dir() / "mc.ini"

DEFAULTS = {
    "general": {
        "left_path": str(Path.home()),
        "right_path": str(Path.home()),
        "delete_to_recycle": "1",
        "show_hidden": "0",
        "confirm_overwrite": "1",
        # "interno" usa el editor que trae MC; poné una ruta a un .exe para
        # delegar en uno externo (notepad.exe, code.cmd, lo que uses).
        "editor": "interno",
        "terminal": default_terminal(),
        "font_family": default_mono_font(),
        "font_size": "10",
        "sort_dirs_first": "1",
        # auto | dark | light. 'auto' sigue la preferencia del escritorio.
        "theme": "auto",
        # auto | es | en. 'auto' usa el idioma del sistema.
        "language": "auto",
        "ui_font_family": default_ui_font(),
        "ui_font_size": "9",
        # una | dos | no. 'dos' da una barra de unidades por panel, cada una
        # atada a su lado; 'una' es la barra única arriba de la ventana.
        "drive_bar": "dos",
        # Sólo Windows: usar el menú contextual real del Explorador en vez del
        # menú propio. Se puede apagar porque carga DLL de terceros en el
        # proceso, y una extensión rota puede tumbar la aplicación.
        "shell_context_menu": "1",
    },
    "geometry": {},
    "bookmarks": {},
    "history": {},
}


class Config:
    def __init__(self, path: Path = CONFIG_PATH):
        self.path = path
        self._cp = configparser.ConfigParser(interpolation=None)
        self._cp.read_dict(DEFAULTS)
        if path.exists():
            try:
                self._cp.read(path, encoding="utf-8")
            except configparser.Error:
                pass  # un ini corrupto no debe impedir arrancar

    def get(self, section: str, key: str, fallback: str = "") -> str:
        return self._cp.get(section, key, fallback=fallback)

    def get_int(self, section: str, key: str, fallback: int = 0) -> int:
        try:
            return int(self.get(section, key, str(fallback)))
        except ValueError:
            return fallback

    def get_bool(self, section: str, key: str, fallback: bool = False) -> bool:
        return self.get_int(section, key, 1 if fallback else 0) != 0

    def set(self, section: str, key: str, value) -> None:
        if not self._cp.has_section(section):
            self._cp.add_section(section)
        self._cp.set(section, key, str(value))

    def section_items(self, section: str) -> list[tuple[str, str]]:
        if not self._cp.has_section(section):
            return []
        return list(self._cp.items(section))

    def clear_section(self, section: str) -> None:
        if self._cp.has_section(section):
            self._cp.remove_section(section)
        self._cp.add_section(section)

    def save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                self._cp.write(fh)
        except OSError:
            pass


config = Config()
