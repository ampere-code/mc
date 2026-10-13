"""Visor interno (F3) — el equivalente del Lister de Total Commander.

Tres modos: texto, hexadecimal e imagen. Se elige automáticamente según el
contenido, y se puede cambiar con 1/2/3. Los archivos grandes se leen sólo
hasta un tope, para que abrir un log de 2 GB no cuelgue la ventana.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt

from .i18n import t
from PySide6.QtGui import QAction, QFont, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QDialog, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
    QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

MAX_TEXT = 16 * 1024 * 1024
MAX_HEX = 4 * 1024 * 1024

IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "bmp", "ico", "webp", "tif", "tiff", "svg"}

MODE_TEXT, MODE_HEX, MODE_IMAGE = range(3)


def detect_encoding(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if data.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if data.startswith(b"\xfe\xff"):
        return "utf-16-be"
    try:
        data.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "cp1252"


def looks_binary(data: bytes) -> bool:
    if b"\x00" in data[:8192]:
        return True
    if not data:
        return False
    printable = sum(1 for b in data[:4096] if b >= 32 or b in (9, 10, 13))
    return printable / min(len(data), 4096) < 0.85


def hex_dump(data: bytes, base: int = 0) -> str:
    out = []
    for off in range(0, len(data), 16):
        chunk = data[off:off + 16]
        hexa = " ".join(f"{b:02X}" for b in chunk).ljust(47)
        text = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        out.append(f"{base + off:08X}  {hexa}  {text}")
    return "\n".join(out)


class Viewer(QMainWindow):
    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.path = path
        self.data = b""
        self.truncated = False
        self.mode = MODE_TEXT

        self.resize(900, 680)
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.text.setFont(QFont("Consolas", 10))
        self.stack.addWidget(self.text)

        self.image_label = QLabel(alignment=Qt.AlignCenter)
        scroll = QScrollArea()
        scroll.setWidget(self.image_label)
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignCenter)
        self.stack.addWidget(scroll)

        self._build_actions()
        self.statusBar()
        self._load()

    def _build_actions(self) -> None:
        def act(text, shortcut, slot):
            a = QAction(text, self)
            a.setShortcut(QKeySequence(shortcut))
            a.triggered.connect(slot)
            self.addAction(a)
            return a

        m = self.menuBar().addMenu(t("&Ver"))
        m.addAction(act(t("&Texto") + "\t1", "1", lambda: self.set_mode(MODE_TEXT)))
        m.addAction(act(t("&Hexadecimal") + "\t2", "2", lambda: self.set_mode(MODE_HEX)))
        m.addAction(act(t("&Imagen") + "\t3", "3", lambda: self.set_mode(MODE_IMAGE)))
        m.addSeparator()
        self.wrap_action = QAction(t("&Ajustar líneas"), self, checkable=True)
        self.wrap_action.setShortcut(QKeySequence("W"))
        self.wrap_action.toggled.connect(self._toggle_wrap)
        m.addAction(self.wrap_action)
        m.addSeparator()
        m.addAction(act(t("&Buscar…"), "F7", self._find))
        m.addAction(act(t("Buscar &siguiente"), "F3", self._find_next))
        m.addSeparator()
        m.addAction(act(t("&Cerrar"), "Esc", self.close))
        self._needle = ""

    def _load(self) -> None:
        try:
            size = os.path.getsize(self.path)
            with open(self.path, "rb") as fh:
                self.data = fh.read(MAX_TEXT)
            self.truncated = size > len(self.data)
        except OSError as exc:
            QMessageBox.warning(
                self, t("Visor"),
                t("No se pudo abrir el archivo:\n{error}", error=exc))
            self.data = b""
            size = 0

        ext = os.path.splitext(self.path)[1].lstrip(".").lower()
        if ext in IMAGE_EXT:
            mode = MODE_IMAGE
        elif looks_binary(self.data):
            mode = MODE_HEX
        else:
            mode = MODE_TEXT

        self.setWindowTitle(t("Ver — {name}", name=os.path.basename(self.path)))
        self._size = size
        self.set_mode(mode)

    def set_mode(self, mode: int) -> None:
        self.mode = mode
        if mode == MODE_IMAGE:
            pix = QPixmap(self.path)
            if pix.isNull():
                self.statusBar().showMessage(t("No es una imagen que se pueda mostrar"))
                self.set_mode(MODE_HEX)
                return
            self.image_label.setPixmap(pix)
            self.stack.setCurrentIndex(1)
            self.statusBar().showMessage(
                f"Imagen  {pix.width()}×{pix.height()}  —  {self._size:,} bytes".replace(",", "."))
            return

        self.stack.setCurrentIndex(0)
        if mode == MODE_HEX:
            self.text.setPlainText(hex_dump(self.data[:MAX_HEX]))
            extra = "  (truncado)" if len(self.data) > MAX_HEX or self.truncated else ""
            self.statusBar().showMessage(
                f"Hexadecimal  —  {self._size:,} bytes{extra}".replace(",", "."))
        else:
            enc = detect_encoding(self.data)
            self.text.setPlainText(self.data.decode(enc, errors="replace"))
            extra = "  (truncado)" if self.truncated else ""
            lines = self.text.blockCount()
            self.statusBar().showMessage(
                f"Texto {enc}  —  {lines:,} líneas, {self._size:,} bytes{extra}".replace(",", "."))

    def _toggle_wrap(self, on: bool) -> None:
        self.text.setLineWrapMode(
            QPlainTextEdit.WidgetWidth if on else QPlainTextEdit.NoWrap)

    def _find(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle(t("Buscar"))
        dlg.setMinimumWidth(380)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(t("Texto a buscar:")))
        edit = QLineEdit(self._needle)
        edit.returnPressed.connect(dlg.accept)
        lay.addWidget(edit)
        edit.selectAll()
        if dlg.exec() == QDialog.Accepted and edit.text():
            self._needle = edit.text()
            self._find_next()

    def _find_next(self) -> None:
        if not self._needle:
            self._find()
            return
        if not self.text.find(self._needle):
            cursor = self.text.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            self.text.setTextCursor(cursor)
            if not self.text.find(self._needle):
                self.statusBar().showMessage(t("No se encontró «{text}»", text=self._needle))
            else:
                self.statusBar().showMessage(t("Volví al principio del archivo"))


class QuickView(QWidget):
    """Vista rápida embebida en el panel (Ctrl+Q)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel(t("Vista rápida"))
        self.title.setObjectName("quickViewTitle")
        self.body = QPlainTextEdit()
        self.body.setReadOnly(True)
        self.body.setFont(QFont("Consolas", 9))
        self.body.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.image = QLabel(alignment=Qt.AlignCenter)
        self.image.hide()
        self._path: str | None = None
        lay.addWidget(self.title)
        lay.addWidget(self.body)
        lay.addWidget(self.image)

    def retranslate(self) -> None:
        if not self._path:
            self.title.setText(t("Vista rápida"))

    def show_file(self, path: str | None) -> None:
        self._path = path if path and os.path.isfile(path) else None
        if not path or not os.path.isfile(path):
            self.title.setText(t("Vista rápida"))
            self.body.setPlainText("")
            self.body.show()
            self.image.hide()
            return
        self.title.setText(os.path.basename(path))
        ext = os.path.splitext(path)[1].lstrip(".").lower()
        if ext in IMAGE_EXT:
            pix = QPixmap(path)
            if not pix.isNull():
                self.body.hide()
                self.image.show()
                self.image.setPixmap(pix.scaled(
                    self.image.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                return
        self.image.hide()
        self.body.show()
        try:
            with open(path, "rb") as fh:
                data = fh.read(128 * 1024)
        except OSError as exc:
            self.body.setPlainText(f"No se pudo leer: {exc}")
            return
        if looks_binary(data):
            self.body.setPlainText(hex_dump(data[:16 * 1024]))
        else:
            self.body.setPlainText(data.decode(detect_encoding(data), errors="replace"))
