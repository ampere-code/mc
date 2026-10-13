"""Temas claro y oscuro.

Un tema son dos cosas: una QPalette, que es lo que usan los widgets que dibuja
el estilo nativo (y el delegado de la tabla), y una hoja QSS para el resto. Las
dos salen del mismo juego de tokens de color, así que no se pueden desalinear.

El estilo base es Fusion a propósito: el estilo nativo de Windows ignora buena
parte de la paleta y haría que el modo oscuro quedara a medias.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette

from . import platform


@dataclass(frozen=True)
class Theme:
    name: str
    dark: bool
    window: str          # fondo de la ventana
    surface: str         # fondo de listas y campos
    surface_alt: str     # filas alternas
    elevated: str        # barras, encabezados, pestañas
    border: str
    text: str
    text_dim: str        # texto secundario y archivos ocultos
    accent: str
    accent_hover: str
    accent_text: str     # texto sobre el acento
    selection: str       # fila bajo el cursor
    marked: str          # archivos marcados
    folder: str          # nombres de carpeta
    danger: str

    # --- paleta -------------------------------------------------------

    def palette(self) -> QPalette:
        p = QPalette()
        c = QColor
        p.setColor(QPalette.Window, c(self.window))
        p.setColor(QPalette.WindowText, c(self.text))
        p.setColor(QPalette.Base, c(self.surface))
        p.setColor(QPalette.AlternateBase, c(self.surface_alt))
        p.setColor(QPalette.Text, c(self.text))
        p.setColor(QPalette.Button, c(self.elevated))
        p.setColor(QPalette.ButtonText, c(self.text))
        p.setColor(QPalette.Highlight, c(self.selection))
        p.setColor(QPalette.HighlightedText, c(self.text))
        p.setColor(QPalette.ToolTipBase, c(self.elevated))
        p.setColor(QPalette.ToolTipText, c(self.text))
        p.setColor(QPalette.PlaceholderText, c(self.text_dim))
        p.setColor(QPalette.Link, c(self.accent))
        p.setColor(QPalette.Mid, c(self.border))
        p.setColor(QPalette.Midlight, c(self.elevated))
        p.setColor(QPalette.Dark, c(self.border))
        p.setColor(QPalette.Shadow, c(self.border))
        for group in (QPalette.Disabled,):
            p.setColor(group, QPalette.Text, c(self.text_dim))
            p.setColor(group, QPalette.WindowText, c(self.text_dim))
            p.setColor(group, QPalette.ButtonText, c(self.text_dim))
        return p

    # --- hoja de estilo -------------------------------------------------

    def qss(self, ui_font: str = "sans-serif", ui_size: int = 9) -> str:
        t = self
        return f"""
* {{
    font-family: "{ui_font}";
    font-size: {ui_size}pt;
}}
QWidget {{
    background: {t.window};
    color: {t.text};
}}
QMainWindow, QDialog {{ background: {t.window}; }}

/* --- menú --- */
QMenuBar {{
    background: {t.window};
    border-bottom: 1px solid {t.border};
    padding: 2px 4px;
}}
QMenuBar::item {{
    padding: 5px 10px;
    border-radius: 5px;
    background: transparent;
}}
QMenuBar::item:selected {{ background: {t.elevated}; }}
QMenuBar::item:pressed  {{ background: {t.accent}; color: {t.accent_text}; }}

QMenu {{
    background: {t.elevated};
    border: 1px solid {t.border};
    border-radius: 8px;
    padding: 5px;
}}
QMenu::item {{
    padding: 6px 26px 6px 14px;
    border-radius: 5px;
}}
QMenu::item:selected {{ background: {t.accent}; color: {t.accent_text}; }}
QMenu::separator {{
    height: 1px;
    background: {t.border};
    margin: 5px 8px;
}}

/* --- listas de archivos --- */
QTableView {{
    background: {t.surface};
    alternate-background-color: {t.surface_alt};
    border: 1px solid {t.border};
    border-radius: 8px;
    gridline-color: transparent;
    outline: none;
    selection-background-color: {t.selection};
}}
QTableView::item {{ padding: 2px 4px; border: none; }}
QTableView::item:selected {{ background: {t.selection}; }}

QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: {t.elevated};
    color: {t.text_dim};
    padding: 6px 8px;
    border: none;
    border-right: 1px solid {t.border};
    border-bottom: 1px solid {t.border};
    font-weight: 600;
}}
QHeaderView::section:first {{ border-top-left-radius: 7px; }}
QHeaderView::section:last  {{ border-top-right-radius: 7px; border-right: none; }}
QHeaderView::section:hover {{ background: {t.border}; color: {t.text}; }}

/* --- barra de ruta: marca cuál es el panel origen --- */
QLineEdit#pathBar {{
    background: {t.surface};
    border: 1px solid {t.border};
    border-radius: 6px;
    padding: 5px 9px;
    color: {t.text_dim};
}}
QLineEdit#pathBar[active="true"] {{
    background: {t.accent};
    border: 1px solid {t.accent};
    color: {t.accent_text};
    font-weight: 600;
}}

/* --- pestañas --- */
QTabBar {{ background: transparent; qproperty-drawBase: 0; }}
QTabBar::tab {{
    background: transparent;
    color: {t.text_dim};
    padding: 5px 12px;
    margin-right: 3px;
    border: 1px solid transparent;
    border-radius: 6px;
    min-width: 40px;
}}
QTabBar::tab:hover {{ background: {t.elevated}; color: {t.text}; }}
QTabBar::tab:selected {{
    background: {t.elevated};
    color: {t.text};
    border: 1px solid {t.border};
    font-weight: 600;
}}
QTabBar::close-button {{ subcontrol-position: right; }}

/* --- campos de texto --- */
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox {{
    background: {t.surface};
    border: 1px solid {t.border};
    border-radius: 6px;
    padding: 5px 9px;
    selection-background-color: {t.accent};
    selection-color: {t.accent_text};
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border: 1px solid {t.accent};
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {t.text_dim};
    margin-right: 7px;
}}
QComboBox QAbstractItemView {{
    background: {t.elevated};
    border: 1px solid {t.border};
    border-radius: 6px;
    selection-background-color: {t.accent};
    selection-color: {t.accent_text};
    padding: 3px;
}}

/* --- botones --- */
QPushButton {{
    background: {t.elevated};
    border: 1px solid {t.border};
    border-radius: 6px;
    padding: 6px 14px;
    color: {t.text};
}}
QPushButton:hover  {{ background: {t.border}; }}
QPushButton:pressed {{ background: {t.accent}; color: {t.accent_text}; }}
QPushButton:default {{ border: 1px solid {t.accent}; }}
QPushButton:disabled {{ color: {t.text_dim}; background: {t.window}; }}

/* botonera de teclas de función */
QPushButton#fkey {{
    background: {t.elevated};
    border: 1px solid {t.border};
    border-radius: 6px;
    padding: 7px 6px;
    font-size: {ui_size}pt;
}}
QPushButton#fkey:hover {{ background: {t.accent}; color: {t.accent_text}; border-color: {t.accent}; }}

/* barra de unidades */
QPushButton#drive {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 3px 0;
    font-weight: 600;
    color: {t.text_dim};
}}
QPushButton#drive:hover {{ background: {t.elevated}; color: {t.text}; border-color: {t.border}; }}

/* --- barras de desplazamiento --- */
QScrollBar:vertical {{
    background: transparent;
    width: 11px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {t.border};
    border-radius: 5px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: {t.text_dim}; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 11px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {t.border};
    border-radius: 5px;
    min-width: 28px;
}}
QScrollBar::handle:horizontal:hover {{ background: {t.text_dim}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* --- varios --- */
QSplitter::handle {{ background: transparent; }}
QSplitter::handle:horizontal {{ width: 5px; }}
QSplitter::handle:vertical {{ height: 5px; }}
QSplitter::handle:hover {{ background: {t.accent}; }}

QStatusBar {{
    background: {t.window};
    border-top: 1px solid {t.border};
    color: {t.text_dim};
}}
QStatusBar::item {{ border: none; }}

QLabel#panelStatus {{
    color: {t.text_dim};
    padding: 3px 6px;
}}
QLabel#quickViewTitle {{
    background: {t.elevated};
    border: 1px solid {t.border};
    border-radius: 6px;
    padding: 5px 9px;
    font-weight: 600;
}}
QLabel#prompt {{
    color: {t.accent};
    font-family: "Consolas";
    font-weight: 600;
}}
QLabel#driveInfo {{ color: {t.text_dim}; }}

QProgressBar {{
    background: {t.surface};
    border: 1px solid {t.border};
    border-radius: 6px;
    height: 16px;
    text-align: center;
    color: {t.text};
}}
QProgressBar::chunk {{
    background: {t.accent};
    border-radius: 5px;
}}

QToolTip {{
    background: {t.elevated};
    color: {t.text};
    border: 1px solid {t.border};
    border-radius: 5px;
    padding: 4px 7px;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 15px; height: 15px;
    border: 1px solid {t.border};
    border-radius: 4px;
    background: {t.surface};
}}
QCheckBox::indicator:checked {{
    background: {t.accent};
    border-color: {t.accent};
}}
QCheckBox::indicator:indeterminate {{
    background: {t.text_dim};
    border-color: {t.text_dim};
}}
QListWidget {{
    background: {t.surface};
    border: 1px solid {t.border};
    border-radius: 8px;
    outline: none;
    padding: 3px;
}}
QListWidget::item {{ padding: 4px 7px; border-radius: 5px; }}
QListWidget::item:selected {{ background: {t.accent}; color: {t.accent_text}; }}
"""


DARK = Theme(
    name="dark", dark=True,
    window="#1a1d23",
    surface="#21252c",
    surface_alt="#252a32",
    elevated="#2b313a",
    border="#39404b",
    text="#d8dee9",
    text_dim="#8b94a3",
    accent="#3d8bfd",
    accent_hover="#5c9eff",
    accent_text="#ffffff",
    selection="#30455f",
    marked="#ff8a80",
    folder="#7fb3ff",
    danger="#ff6b6b",
)

LIGHT = Theme(
    name="light", dark=False,
    window="#f2f3f5",
    surface="#ffffff",
    surface_alt="#f7f8fa",
    elevated="#e8eaee",
    border="#d2d7df",
    text="#1f2328",
    text_dim="#6a737d",
    accent="#1f6feb",
    accent_hover="#3b82f6",
    accent_text="#ffffff",
    selection="#cfe2ff",
    marked="#c5321f",
    folder="#0b4fa8",
    danger="#c5321f",
)

THEMES = {"dark": DARK, "light": LIGHT}

_current: Theme = DARK


def current() -> Theme:
    """El tema activo. Lo consultan el modelo y los delegados para pintar."""
    return _current


def prefers_dark() -> bool:
    """Preferencia de tema del escritorio. La implementación por sistema vive
    en `platform`; acá sólo se reexporta para los usuarios del tema."""
    return platform.prefers_dark()


def resolve(name: str) -> Theme:
    """'auto' consulta al sistema; 'dark'/'light' son explícitos."""
    if name == "auto":
        return DARK if prefers_dark() else LIGHT
    return THEMES.get(name, DARK)


def apply(app, name: str, ui_font: str = "", ui_size: int = 9) -> Theme:
    """Aplica el tema a toda la aplicación. Devuelve el tema resuelto."""
    global _current
    theme = resolve(name)
    _current = theme
    app.setStyle("Fusion")
    ui_font = ui_font or platform.default_ui_font()
    app.setPalette(theme.palette())
    app.setStyleSheet(theme.qss(ui_font, ui_size))
    return theme


def apply_titlebar(widget) -> None:
    """Ajusta el marco nativo al tema actual. Sólo hace algo en Windows."""
    platform.apply_titlebar(widget, _current.dark)
