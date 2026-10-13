"""Buscar archivos (Alt+F7).

La búsqueda corre en un hilo y va publicando resultados a medida que los
encuentra, así una búsqueda en C:\\ muestra algo desde el primer segundo. El
botón "Enviar al panel" reproduce el «feed to listbox» de TC: vuelca los
resultados en el panel como una vista de rama.
"""

from __future__ import annotations

import fnmatch
import os
import re

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QProgressBar, QPushButton, QVBoxLayout,
)

from .fsmodel import FileEntry
from .i18n import t


class SearchWorker(QThread):
    found = Signal(str, bool, int, float)   # ruta, es_dir, tamaño, mtime
    scanning = Signal(str)
    done = Signal(int, bool)                # encontrados, cancelado

    def __init__(self, root: str, patterns: list[str], contains: str,
                 subdirs: bool, case_sensitive: bool, regex: bool,
                 max_results: int = 20000, parent=None):
        super().__init__(parent)
        self.root = root
        self.patterns = patterns or ["*"]
        self.contains = contains
        self.subdirs = subdirs
        self.case_sensitive = case_sensitive
        self.use_regex = regex
        self.max_results = max_results
        self._cancel = False
        self._needle_re: re.Pattern | None = None

    def cancel(self) -> None:
        self._cancel = True

    def _matches_name(self, name: str) -> bool:
        target = name if self.case_sensitive else name.lower()
        for p in self.patterns:
            pat = p if self.case_sensitive else p.lower()
            if fnmatch.fnmatch(target, pat):
                return True
        return False

    def _matches_content(self, path: str) -> bool:
        if not self.contains:
            return True
        try:
            with open(path, "rb") as fh:
                data = fh.read(8 * 1024 * 1024)
        except OSError:
            return False
        if self._needle_re is not None:
            try:
                text = data.decode("utf-8", errors="ignore")
            except Exception:
                return False
            return self._needle_re.search(text) is not None
        needle = self.contains.encode("utf-8", errors="ignore")
        if self.case_sensitive:
            return needle in data
        return needle.lower() in data.lower()

    def run(self) -> None:
        if self.use_regex and self.contains:
            try:
                flags = 0 if self.case_sensitive else re.IGNORECASE
                self._needle_re = re.compile(self.contains, flags)
            except re.error:
                self.done.emit(0, False)
                return

        count = 0
        walker = os.walk(self.root, onerror=lambda e: None)
        for dirpath, dirnames, filenames in walker:
            if self._cancel:
                break
            self.scanning.emit(dirpath)
            if not self.subdirs:
                dirnames[:] = []
            for name in list(dirnames) + filenames:
                if self._cancel:
                    break
                full = os.path.join(dirpath, name)
                is_dir = name in dirnames
                if not self._matches_name(name):
                    continue
                if self.contains and (is_dir or not self._matches_content(full)):
                    continue
                try:
                    st = os.stat(full)
                    size, mtime = (0 if is_dir else st.st_size), st.st_mtime
                except OSError:
                    size, mtime = 0, 0.0
                self.found.emit(full, is_dir, size, mtime)
                count += 1
                if count >= self.max_results:
                    self.done.emit(count, True)
                    return
        self.done.emit(count, self._cancel)


class SearchDialog(QDialog):
    """Alt+F7. `results_to_panel` queda con las entradas si el usuario las envía."""

    def __init__(self, start_dir: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("Buscar archivos"))
        self.setMinimumSize(720, 520)
        self.worker: SearchWorker | None = None
        self.results: list[tuple[str, bool, int, float]] = []
        self.results_to_panel: list[FileEntry] | None = None
        self.goto_path: str | None = None

        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.pattern = QLineEdit("*.*")
        self.contains = QLineEdit()
        self.path = QLineEdit(start_dir)
        form.addRow(t("Buscar archivos:"), self.pattern)
        form.addRow(t("Que contengan el texto:"), self.contains)
        form.addRow(t("Buscar en:"), self.path)
        lay.addLayout(form)

        opts = QHBoxLayout()
        self.subdirs = QCheckBox(t("Incluir subdirectorios"))
        self.subdirs.setChecked(True)
        self.case = QCheckBox(t("Distinguir mayúsculas"))
        self.regex = QCheckBox(t("El texto es una expresión regular"))
        opts.addWidget(self.subdirs)
        opts.addWidget(self.case)
        opts.addWidget(self.regex)
        opts.addStretch()
        lay.addLayout(opts)

        self.list = QListWidget()
        self.list.itemActivated.connect(self._goto_selected)
        lay.addWidget(self.list, 1)

        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.hide()
        self.status = QLabel(t("Listo."))
        self.status.setTextFormat(Qt.PlainText)
        lay.addWidget(self.bar)
        lay.addWidget(self.status)

        buttons = QHBoxLayout()
        self.btn_start = QPushButton(t("&Buscar"))
        self.btn_start.setDefault(True)
        self.btn_start.clicked.connect(self._start)
        self.btn_stop = QPushButton(t("&Detener"))
        self.btn_stop.clicked.connect(self._stop)
        self.btn_stop.setEnabled(False)
        self.btn_feed = QPushButton(t("&Enviar al panel"))
        self.btn_feed.clicked.connect(self._feed)
        self.btn_feed.setEnabled(False)
        self.btn_goto = QPushButton(t("&Ir al archivo"))
        self.btn_goto.clicked.connect(self._goto_selected)
        buttons.addWidget(self.btn_start)
        buttons.addWidget(self.btn_stop)
        buttons.addStretch()
        buttons.addWidget(self.btn_goto)
        buttons.addWidget(self.btn_feed)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.button(QDialogButtonBox.Close).setText(t("Cerrar"))
        bb.rejected.connect(self.reject)
        buttons.addWidget(bb)
        lay.addLayout(buttons)

        self.pattern.setFocus()
        self.pattern.selectAll()

    def _start(self) -> None:
        root = self.path.text().strip().strip('"')
        if not os.path.isdir(root):
            self.status.setText(t("No existe el directorio: {path}", path=root))
            return
        self.list.clear()
        self.results.clear()
        patterns = [p for p in self.pattern.text().replace(" ", ";").split(";") if p]
        self.worker = SearchWorker(
            root, patterns, self.contains.text(), self.subdirs.isChecked(),
            self.case.isChecked(), self.regex.isChecked(), parent=self)
        self.worker.found.connect(self._on_found)
        self.worker.scanning.connect(self._on_scanning)
        self.worker.done.connect(self._on_done)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.bar.show()
        self.worker.start()

    def _stop(self) -> None:
        if self.worker:
            self.worker.cancel()

    def _on_found(self, path: str, is_dir: bool, size: int, mtime: float) -> None:
        self.results.append((path, is_dir, size, mtime))
        item = QListWidgetItem(("[DIR]  " if is_dir else "       ") + path)
        item.setData(Qt.UserRole, path)
        self.list.addItem(item)

    def _on_scanning(self, path: str) -> None:
        self.status.setText(t("Buscando en: {path}", path=path))

    def _on_done(self, count: int, cancelled: bool) -> None:
        self.bar.hide()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_feed.setEnabled(count > 0)
        suffix = t(" (detenida)") if cancelled else ""
        self.status.setText(t("{n} resultado(s){suffix}.", n=count, suffix=suffix))

    def _feed(self) -> None:
        entries = []
        for path, is_dir, size, mtime in self.results:
            entries.append(FileEntry(
                name=os.path.basename(path), path=path, is_dir=is_dir,
                size=size, mtime=mtime, display=path))
        self.results_to_panel = entries
        self.accept()

    def _goto_selected(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        self.goto_path = item.data(Qt.UserRole)
        self.accept()

    def closeEvent(self, event) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(2000)
        event.accept()
