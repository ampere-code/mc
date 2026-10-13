"""Diálogos chicos: crear dir, renombrar, seleccionar grupo, atributos, propiedades."""

from __future__ import annotations

import os
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QVBoxLayout,
)

from . import platform
from .i18n import t
from .ops import human


class TextPromptDialog(QDialog):
    """Pedir una línea de texto, con el texto inicial preseleccionado."""

    def __init__(self, title: str, label: str, text: str = "", select_stem: bool = False,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(label))
        self.edit = QLineEdit(text)
        lay.addWidget(self.edit)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

        # Al renombrar conviene seleccionar sólo el nombre, no la extensión.
        if select_stem and "." in text[1:]:
            self.edit.setSelection(0, text.rindex("."))
        else:
            self.edit.selectAll()
        self.edit.setFocus()

    def value(self) -> str:
        return self.edit.text().strip()

    @staticmethod
    def ask(parent, title: str, label: str, text: str = "",
            select_stem: bool = False) -> str | None:
        dlg = TextPromptDialog(title, label, text, select_stem, parent)
        return dlg.value() if dlg.exec() == QDialog.Accepted else None


class SelectGroupDialog(QDialog):
    """Marcar o desmarcar por patrón (Num + / Num -)."""

    def __init__(self, marking: bool, initial: str = "*.*", history: list[str] | None = None,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("Seleccionar grupo") if marking else t("Deseleccionar grupo"))
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(
            t("Patrón (se admiten varios separados por ';' — por ejemplo  *.txt;*.md)")
        ))
        self.combo = QComboBox()
        self.combo.setEditable(True)
        if history:
            self.combo.addItems(history)
        self.combo.setCurrentText(initial)
        lay.addWidget(self.combo)
        self.files_only = QCheckBox(t("Sólo archivos (no carpetas)"))
        lay.addWidget(self.files_only)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.combo.lineEdit().selectAll()
        self.combo.setFocus()

    def patterns(self) -> list[str]:
        raw = self.combo.currentText().replace(" ", ";")
        return [p for p in raw.split(";") if p]


class AttributesDialog(QDialog):
    """Cambiar atributos (cm_SetAttrib 502).

    Windows y Unix no tienen el mismo modelo: allá son banderas r/a/h/s, acá son
    permisos rwx por dueño, grupo y otros. El diálogo se arma según el sistema
    en vez de inventar una abstracción que no le sirve a ninguno de los dos.
    """

    # Banderas de atributo de Windows.
    FA = {"r": 0x01, "h": 0x02, "s": 0x04, "a": 0x20}

    def __init__(self, paths: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("Cambiar atributos") if platform.IS_WINDOWS
                            else t("Cambiar permisos"))
        self.paths = paths
        self.boxes: dict[str, QCheckBox] = {}

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(t("{n} elemento(s) seleccionado(s)", n=len(paths))))

        if platform.IS_WINDOWS:
            for key, label in (("r", "Sólo lectura"), ("a", "Archivo"),
                               ("h", "Oculto"), ("s", "Sistema")):
                lay.addWidget(self._box(key, t(label)))
        else:
            grid = QGridLayout()
            grid.addWidget(QLabel("<b>" + t("Leer") + "</b>"), 0, 1)
            grid.addWidget(QLabel("<b>" + t("Escribir") + "</b>"), 0, 2)
            grid.addWidget(QLabel("<b>" + t("Ejecutar") + "</b>"), 0, 3)
            for row, (who, title) in enumerate(
                    (("u", "Dueño"), ("g", "Grupo"), ("o", "Otros")), start=1):
                grid.addWidget(QLabel(t(title)), row, 0)
                for col, what in enumerate(("r", "w", "x"), start=1):
                    grid.addWidget(self._box(who + what, ""), row, col)
            lay.addLayout(grid)

        lay.addWidget(QLabel(
            "<i>" + t("Los casilleros en estado intermedio dejan el valor como está.") + "</i>"
        ))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _box(self, key: str, label: str) -> QCheckBox:
        cb = QCheckBox(label)
        cb.setTristate(True)
        cb.setCheckState(Qt.PartiallyChecked)
        self.boxes[key] = cb
        return cb

    def apply(self) -> list[str]:
        if platform.IS_WINDOWS:
            return self._apply_windows()
        return self._apply_unix()

    def _apply_windows(self) -> list[str]:
        on = off = 0
        for key, cb in self.boxes.items():
            state = cb.checkState()
            if state == Qt.Checked:
                on |= self.FA[key]
            elif state == Qt.Unchecked:
                off |= self.FA[key]
        errors = []
        for p in self.paths:
            err = platform.set_windows_attributes(p, on, off)
            if err:
                errors.append(f"{p}: {err}")
        return errors

    def _apply_unix(self) -> list[str]:
        bits = {"ur": 0o400, "uw": 0o200, "ux": 0o100,
                "gr": 0o040, "gw": 0o020, "gx": 0o010,
                "or": 0o004, "ow": 0o002, "ox": 0o001}
        on = off = 0
        for key, cb in self.boxes.items():
            state = cb.checkState()
            if state == Qt.Checked:
                on |= bits[key]
            elif state == Qt.Unchecked:
                off |= bits[key]
        errors = []
        for p in self.paths:
            try:
                mode = os.stat(p).st_mode & 0o7777
            except OSError as exc:
                errors.append(f"{p}: {exc.strerror or exc}")
                continue
            new = (mode | on) & ~off
            if new != mode:
                err = platform.set_unix_mode(p, new)
                if err:
                    errors.append(f"{p}: {err}")
        return errors


class PropertiesDialog(QDialog):
    """Propiedades (cm_Properties 1003)."""

    def __init__(self, entries, total_size: int | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("Propiedades"))
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        form = QFormLayout()

        if len(entries) == 1:
            e = entries[0]
            form.addRow(t("Nombre:"), self._val(e.name))
            form.addRow(t("Ubicación:"), self._val(os.path.dirname(e.path)))
            form.addRow(t("Tipo:"), self._val(
                t("Carpeta") if e.is_dir else
                (t("Archivo {ext}", ext=e.ext.upper()) if e.ext else t("Archivo"))))
            size = total_size if total_size is not None else e.size
            form.addRow(t("Tamaño:"), self._val(f"{human(size)}  ({size:,} bytes)".replace(",", ".")))
            try:
                st = os.stat(e.path)
                fmt = "%d/%m/%Y %H:%M:%S"
                form.addRow(t("Modificado:"), self._val(
                    datetime.fromtimestamp(st.st_mtime).strftime(fmt)))
                form.addRow(t("Creado:"), self._val(
                    datetime.fromtimestamp(st.st_ctime).strftime(fmt)))
                form.addRow(t("Accedido:"), self._val(
                    datetime.fromtimestamp(st.st_atime).strftime(fmt)))
            except OSError:
                pass
            form.addRow(t("Atributos:"), self._val(e.attrs or "—"))
        else:
            ndirs = sum(1 for e in entries if e.is_dir)
            form.addRow(t("Selección:"), self._val(t(
                "{files} archivo(s), {dirs} carpeta(s)",
                files=len(entries) - ndirs, dirs=ndirs)))
            size = total_size if total_size is not None else sum(e.size for e in entries)
            form.addRow(t("Tamaño total:"), self._val(
                f"{human(size)}  ({size:,} bytes)".replace(",", ".")))

        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Ok)
        bb.accepted.connect(self.accept)
        lay.addWidget(bb)

    @staticmethod
    def _val(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return lbl


class ErrorListDialog(QDialog):
    """Mostrar los errores acumulados de una operación."""

    def __init__(self, title: str, errors: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(620, 320)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(t("La operación terminó con {n} error(es):", n=len(errors))))
        box = QPlainTextEdit("\n".join(errors))
        box.setReadOnly(True)
        lay.addWidget(box)
        bb = QDialogButtonBox(QDialogButtonBox.Ok)
        bb.accepted.connect(self.accept)
        lay.addWidget(bb)


class CopyMoveDialog(QDialog):
    """Confirmación de copiar/mover, con destino editable (F5 / F6)."""

    def __init__(self, move: bool, entries, dest: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("Mover/Renombrar") if move else t("Copiar"))
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)

        verb = t("Mover") if move else t("Copiar")
        if len(entries) == 1:
            what = f'"{entries[0].name}"'
        else:
            ndirs = sum(1 for e in entries if e.is_dir)
            what = t("{files} archivo(s), {dirs} carpeta(s)",
                     files=len(entries) - ndirs, dirs=ndirs)
        lay.addWidget(QLabel("<b>" + t("{verb} {what} a:", verb=verb, what=what) + "</b>"))

        self.edit = QLineEdit(dest)
        lay.addWidget(self.edit)
        lay.addWidget(QLabel(
            "<i>" + t("Podés escribir una ruta nueva, o una ruta con nombre de archivo "
                      "para renombrar al vuelo.") + "</i>"
        ))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(verb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.edit.setFocus()
        self.edit.selectAll()

    def destination(self) -> str:
        return self.edit.text().strip().strip('"')
