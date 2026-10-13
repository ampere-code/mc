"""Editor de texto interno (F4).

Deliberadamente simple: abrir, editar, guardar, buscar y reemplazar. Si preferís
un editor externo, se configura en `editor` dentro de mc.ini y MC lo lanza en
lugar de este.
"""

from __future__ import annotations

import os

from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit,
)

from .i18n import t
from .viewer import detect_encoding


class Editor(QMainWindow):
    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.path = path
        self.encoding = "utf-8"
        self._dirty = False

        self.edit = QPlainTextEdit()
        self.edit.setFont(QFont("Consolas", 10))
        self.edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.edit.setTabStopDistance(32)
        self.edit.modificationChanged.connect(self._on_modified)
        self.setCentralWidget(self.edit)
        self.resize(900, 680)
        self.statusBar()

        self._build_menu()
        self._load()
        self.edit.cursorPositionChanged.connect(self._update_status)
        self._update_status()

    def _build_menu(self) -> None:
        def act(menu, text, shortcut, slot):
            a = QAction(text, self)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            a.triggered.connect(slot)
            menu.addAction(a)
            self.addAction(a)
            return a

        m = self.menuBar().addMenu(t("&Archivos"))
        act(m, t("&Guardar"), "Ctrl+S", self.save)
        act(m, t("Guardar &como…"), "Ctrl+Shift+S", self.save_as)
        m.addSeparator()
        act(m, t("&Cerrar"), "Esc", self.close)

        e = self.menuBar().addMenu(t("&Editar"))
        act(e, t("&Deshacer"), "Ctrl+Z", self.edit.undo)
        act(e, t("&Rehacer"), "Ctrl+Y", self.edit.redo)
        e.addSeparator()
        act(e, t("&Buscar…"), "Ctrl+F", self._find)
        act(e, t("Buscar &siguiente"), "F3", self._find_next)
        act(e, t("&Reemplazar…"), "Ctrl+H", self._replace)
        self._needle = ""

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "rb") as fh:
                    data = fh.read()
                self.encoding = detect_encoding(data)
                self.edit.setPlainText(data.decode(self.encoding, errors="replace"))
            except OSError as exc:
                QMessageBox.warning(
                    self, t("Editor"),
                    t("No se pudo abrir:\n{error}", error=exc))
        self.edit.document().setModified(False)
        self._dirty = False
        self._update_title()

    def _on_modified(self, modified: bool) -> None:
        self._dirty = modified
        self._update_title()

    def _update_title(self) -> None:
        mark = "• " if self._dirty else ""
        self.setWindowTitle(mark + t("Editar — {name}", name=os.path.basename(self.path)))

    def _update_status(self) -> None:
        c = self.edit.textCursor()
        self.statusBar().showMessage(
            t("Línea {line}, columna {col}  —  {enc}", line=c.blockNumber() + 1,
              col=c.columnNumber() + 1, enc=self.encoding))

    def save(self) -> bool:
        enc = "utf-8-sig" if self.encoding == "utf-8-sig" else self.encoding
        try:
            with open(self.path, "w", encoding=enc, newline="") as fh:
                fh.write(self.edit.toPlainText())
        except (OSError, UnicodeEncodeError) as exc:
            QMessageBox.warning(
                self, t("Editor"),
                t("No se pudo guardar:\n{error}", error=exc))
            return False
        self.edit.document().setModified(False)
        self.statusBar().showMessage(t("Guardado"), 2000)
        return True

    def save_as(self) -> bool:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(self, t("Guardar como"), self.path)
        if not path:
            return False
        self.path = path
        return self.save()

    def _find(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle(t("Buscar"))
        dlg.setMinimumWidth(380)
        form = QFormLayout(dlg)
        edit = QLineEdit(self._needle)
        form.addRow(t("Buscar:"), edit)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        edit.selectAll()
        if dlg.exec() == QDialog.Accepted and edit.text():
            self._needle = edit.text()
            self._find_next()

    def _find_next(self) -> None:
        if not self._needle:
            self._find()
            return
        if not self.edit.find(self._needle):
            c = self.edit.textCursor()
            c.movePosition(c.MoveOperation.Start)
            self.edit.setTextCursor(c)
            if not self.edit.find(self._needle):
                self.statusBar().showMessage(t("No se encontró «{text}»", text=self._needle), 3000)

    def _replace(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle(t("Reemplazar"))
        dlg.setMinimumWidth(420)
        form = QFormLayout(dlg)
        f_edit, r_edit = QLineEdit(self._needle), QLineEdit()
        form.addRow(t("Buscar:"), f_edit)
        form.addRow(t("Reemplazar por:"), r_edit)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(t("Reemplazar todo"))
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        if dlg.exec() == QDialog.Accepted and f_edit.text():
            text = self.edit.toPlainText()
            n = text.count(f_edit.text())
            if n:
                self.edit.setPlainText(text.replace(f_edit.text(), r_edit.text()))
            self.statusBar().showMessage(t("{n} reemplazo(s)", n=n), 3000)

    def closeEvent(self, event) -> None:
        if self._dirty:
            r = QMessageBox.question(
                self, t("Editor"),
                t("«{name}» tiene cambios sin guardar.\n¿Guardar?",
                  name=os.path.basename(self.path)),
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if r == QMessageBox.Cancel:
                event.ignore()
                return
            if r == QMessageBox.Save and not self.save():
                event.ignore()
                return
        event.accept()
