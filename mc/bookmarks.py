"""Marcadores de directorios (Ctrl+D, cm_DirectoryHotlist 526)."""

from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout,
)
from PySide6.QtCore import Qt

from .config import config
from .dialogs import TextPromptDialog
from .i18n import t


def load_bookmarks() -> list[tuple[str, str]]:
    """[(nombre, ruta)] en el orden guardado."""
    items = config.section_items("bookmarks")
    out = []
    for key, value in items:
        name, _, path = value.partition("|")
        if path:
            out.append((name, path))
    return out


def save_bookmarks(items: list[tuple[str, str]]) -> None:
    config.clear_section("bookmarks")
    for i, (name, path) in enumerate(items):
        config.set("bookmarks", f"b{i:03d}", f"{name}|{path}")
    config.save()


def add_bookmark(name: str, path: str) -> None:
    items = load_bookmarks()
    items = [it for it in items if it[1].lower() != path.lower()]
    items.append((name, path))
    save_bookmarks(items)


class BookmarksDialog(QDialog):
    """Gestionar y saltar a marcadores. `chosen` queda con la ruta elegida."""

    def __init__(self, current_dir: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("Marcadores de directorios"))
        self.setMinimumSize(560, 400)
        self.current_dir = current_dir
        self.chosen: str | None = None

        lay = QVBoxLayout(self)
        self.list = QListWidget()
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.itemActivated.connect(self._accept_current)
        lay.addWidget(self.list, 1)

        row = QHBoxLayout()
        for text, slot in (
            (t("&Agregar el directorio actual"), self._add_current),
            (t("&Renombrar"), self._rename),
            (t("&Quitar"), self._remove),
        ):
            b = QPushButton(text)
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(t("Ir"))
        bb.accepted.connect(self._accept_current)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

        self._reload()

    def _reload(self) -> None:
        self.list.clear()
        for name, path in load_bookmarks():
            item = QListWidgetItem(f"{name}   —   {path}")
            item.setData(Qt.UserRole, (name, path))
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _current(self) -> tuple[str, str] | None:
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _collect(self) -> list[tuple[str, str]]:
        return [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())]

    def _add_current(self) -> None:
        name = TextPromptDialog.ask(
            self, t("Agregar marcador"), t("Nombre del marcador:"),
            os.path.basename(self.current_dir) or self.current_dir)
        if name:
            add_bookmark(name, self.current_dir)
            self._reload()

    def _rename(self) -> None:
        cur = self._current()
        if not cur:
            return
        name = TextPromptDialog.ask(self, t("Renombrar marcador"), t("Nombre:"), cur[0])
        if name:
            items = self._collect()
            items[self.list.currentRow()] = (name, cur[1])
            save_bookmarks(items)
            self._reload()

    def _remove(self) -> None:
        row = self.list.currentRow()
        if row < 0:
            return
        items = self._collect()
        del items[row]
        save_bookmarks(items)
        self._reload()

    def _accept_current(self) -> None:
        cur = self._current()
        if cur:
            self.chosen = cur[1]
            save_bookmarks(self._collect())  # conservar el reordenado por arrastre
            self.accept()
