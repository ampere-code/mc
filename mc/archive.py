"""Soporte ZIP: comprimir (Alt+F5), descomprimir (Alt+F6) y navegar adentro.

Navegar un ZIP es de sólo lectura: se puede mirar el contenido, ver archivos con
F3 y extraer con F5. Escribir adentro de un comprimido ya abierto queda afuera
de esta versión.
"""

from __future__ import annotations

import os
import zipfile
from datetime import datetime

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QLabel, QLineEdit, QVBoxLayout,
)

from .fsmodel import FileEntry
from .i18n import t
from .ops import _Worker

ARCHIVE_EXT = {"zip", "jar", "whl", "egg", "xpi", "docx", "xlsx", "pptx", "odt", "epub"}


def is_archive(path: str) -> bool:
    ext = os.path.splitext(path)[1].lstrip(".").lower()
    return ext in ARCHIVE_EXT and zipfile.is_zipfile(path)


def list_zip(zip_path: str, inner: str = "") -> list[FileEntry]:
    """Lista un nivel de un ZIP. `inner` usa '/' y termina en '/' o es ''."""
    entries: list[FileEntry] = []
    entries.append(FileEntry(name="..", path=inner, is_dir=True, is_parent=True))
    seen_dirs: set[str] = set()
    try:
        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.infolist():
                name = info.filename.replace("\\", "/")
                if not name.startswith(inner) or name == inner:
                    continue
                rest = name[len(inner):]
                if not rest:
                    continue
                head, slash, tail = rest.partition("/")
                if slash:
                    if head not in seen_dirs:
                        seen_dirs.add(head)
                        entries.append(FileEntry(
                            name=head, path=f"{inner}{head}/", is_dir=True))
                else:
                    try:
                        mtime = datetime(*info.date_time).timestamp()
                    except (ValueError, OverflowError):
                        mtime = 0.0
                    entries.append(FileEntry(
                        name=head, path=name, size=info.file_size, mtime=mtime))
    except (OSError, zipfile.BadZipFile):
        pass
    return entries


def extract_one(zip_path: str, member: str, dest_dir: str) -> str:
    """Extrae un miembro y devuelve la ruta resultante."""
    with zipfile.ZipFile(zip_path) as zf:
        zf.extract(member, dest_dir)
    return os.path.join(dest_dir, member.replace("/", os.sep))


def _safe_join(dest_dir: str, member: str) -> str | None:
    """Evita el zip-slip: rechaza miembros que escapen del destino."""
    target = os.path.normpath(os.path.join(dest_dir, member.replace("/", os.sep)))
    base = os.path.normpath(dest_dir)
    if os.path.commonpath([base, target]) != base:
        return None
    return target


class PackWorker(_Worker):
    def __init__(self, sources: list[str], zip_path: str, base_dir: str,
                 move: bool = False, compress: bool = True, parent=None):
        super().__init__(parent)
        self.sources = sources
        self.zip_path = zip_path
        self.base_dir = base_dir
        self.move = move
        self.method = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED

    def _collect(self) -> list[tuple[str, str]]:
        """(ruta real, nombre dentro del zip)."""
        items = []
        for src in self.sources:
            if os.path.isdir(src):
                for dirpath, _dirnames, filenames in os.walk(src, onerror=lambda e: None):
                    for fn in filenames:
                        full = os.path.join(dirpath, fn)
                        items.append((full, os.path.relpath(full, self.base_dir)))
            else:
                items.append((src, os.path.relpath(src, self.base_dir)))
        return items

    def run(self) -> None:
        items = self._collect()
        self.total_bytes = max(len(items), 1)
        try:
            with zipfile.ZipFile(self.zip_path, "w", self.method, allowZip64=True) as zf:
                for full, arcname in items:
                    if self._cancel:
                        break
                    try:
                        zf.write(full, arcname)
                        self.processed += 1
                    except OSError as exc:
                        self.errors.append(f"{full}: {exc.strerror or exc}")
                    self.done_bytes += 1
                    self.progress.emit(full, self.done_bytes, self.total_bytes)
        except OSError as exc:
            self.errors.append(f"{self.zip_path}: {exc.strerror or exc}")

        if self._cancel:
            try:
                os.remove(self.zip_path)  # no dejar un zip a medio hacer
            except OSError:
                pass
        elif self.move and not self.errors:
            for src in self.sources:
                try:
                    if os.path.isdir(src):
                        import shutil
                        shutil.rmtree(src, ignore_errors=True)
                    else:
                        os.remove(src)
                except OSError as exc:
                    self.errors.append(f"{src}: {exc.strerror or exc}")
        self.completed.emit(self.processed, self.errors)


class UnpackWorker(_Worker):
    def __init__(self, zip_paths: list[str], dest_dir: str,
                 members: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.zip_paths = zip_paths
        self.dest_dir = dest_dir
        self.members = members

    def run(self) -> None:
        for zp in self.zip_paths:
            if self._cancel:
                break
            try:
                with zipfile.ZipFile(zp) as zf:
                    names = self.members or zf.namelist()
                    self.total_bytes = max(len(names), 1)
                    for name in names:
                        if self._cancel:
                            break
                        target = _safe_join(self.dest_dir, name)
                        if target is None:
                            self.errors.append(f"{name}: ruta insegura, se omitió")
                            continue
                        try:
                            zf.extract(name, self.dest_dir)
                            self.processed += 1
                        except (OSError, zipfile.BadZipFile) as exc:
                            self.errors.append(f"{name}: {exc}")
                        self.done_bytes += 1
                        self.progress.emit(name, self.done_bytes, self.total_bytes)
            except (OSError, zipfile.BadZipFile) as exc:
                self.errors.append(f"{zp}: {exc}")
        self.completed.emit(self.processed, self.errors)


class TestWorker(_Worker):
    """Verificar integridad (Alt+Shift+F9, cm_TestArchive 518)."""

    def __init__(self, zip_paths: list[str], parent=None):
        super().__init__(parent)
        self.zip_paths = zip_paths

    def run(self) -> None:
        self.total_bytes = max(len(self.zip_paths), 1)
        for zp in self.zip_paths:
            if self._cancel:
                break
            try:
                with zipfile.ZipFile(zp) as zf:
                    bad = zf.testzip()
                    if bad:
                        self.errors.append(f"{os.path.basename(zp)}: CRC inválido en {bad}")
                    else:
                        self.processed += 1
            except (OSError, zipfile.BadZipFile) as exc:
                self.errors.append(f"{os.path.basename(zp)}: {exc}")
            self.done_bytes += 1
            self.progress.emit(zp, self.done_bytes, self.total_bytes)
        self.completed.emit(self.processed, self.errors)


class PackDialog(QDialog):
    def __init__(self, default_path: str, count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("Comprimir archivos"))
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<b>" + t("Comprimir {n} elemento(s) en:", n=count) + "</b>"))
        self.edit = QLineEdit(default_path)
        lay.addWidget(self.edit)

        self.combo = QComboBox()
        self.combo.addItems([t("Comprimido (deflate)"),
                             t("Sólo almacenar (sin comprimir)")])
        lay.addWidget(self.combo)

        self.move_box = QCheckBox(t("Borrar los originales al terminar"))
        lay.addWidget(self.move_box)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(t("Comprimir"))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

        self.edit.setFocus()
        stem = os.path.basename(default_path)
        if stem.endswith(".zip"):
            self.edit.setSelection(len(default_path) - len(stem), len(stem) - 4)

    @property
    def zip_path(self) -> str:
        p = self.edit.text().strip().strip('"')
        return p if p.lower().endswith(".zip") else p + ".zip"

    @property
    def compress(self) -> bool:
        return self.combo.currentIndex() == 0

    @property
    def delete_originals(self) -> bool:
        return self.move_box.isChecked()
