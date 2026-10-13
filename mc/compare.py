"""Comparar los dos paneles (Shift+F2, cm_CompareDirs 533).

Regla, la misma que usa Total Commander: queda marcado lo que falta en el otro
panel y lo que está presente en ambos pero es más nuevo de este lado. Lo que es
idéntico queda sin marcar, así la selección resultante es exactamente "lo que
habría que copiar al otro lado".
"""

from __future__ import annotations

import hashlib
import os

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout,
)

from .fsmodel import FileEntry
from .i18n import t

# Tolerancia en segundos: FAT guarda la hora con resolución de 2 s, así que una
# diferencia menor no significa que el archivo haya cambiado.
MTIME_TOLERANCE = 2.0


def file_digest(path: str, chunk: int = 1 << 20) -> str | None:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            while True:
                buf = fh.read(chunk)
                if not buf:
                    break
                h.update(buf)
    except OSError:
        return None
    return h.hexdigest()


def compare_panels(left: list[FileEntry], right: list[FileEntry],
                   by_content: bool = False,
                   include_dirs: bool = False) -> tuple[set[str], set[str]]:
    """Devuelve (rutas a marcar a la izquierda, rutas a marcar a la derecha)."""
    def index(entries):
        out = {}
        for e in entries:
            if e.is_parent:
                continue
            if e.is_dir and not include_dirs:
                continue
            out[e.name.lower()] = e
        return out

    li, ri = index(left), index(right)
    lmark, rmark = set(), set()

    for name, le in li.items():
        re_ = ri.get(name)
        if re_ is None:
            lmark.add(le.path)
            continue
        if le.is_dir or re_.is_dir:
            continue
        if by_content:
            if le.size != re_.size or file_digest(le.path) != file_digest(re_.path):
                lmark.add(le.path)
                rmark.add(re_.path)
            continue
        delta = le.mtime - re_.mtime
        if delta > MTIME_TOLERANCE:
            lmark.add(le.path)
        elif delta < -MTIME_TOLERANCE:
            rmark.add(re_.path)
        elif le.size != re_.size:
            # Misma fecha pero distinto tamaño: algo cambió, marcar los dos.
            lmark.add(le.path)
            rmark.add(re_.path)

    for name, re_ in ri.items():
        if name not in li:
            rmark.add(re_.path)

    return lmark, rmark


class CompareWorker(QThread):
    """La comparación por contenido puede tardar, así que va en un hilo."""

    finished_compare = Signal(set, set)

    def __init__(self, left, right, by_content: bool, include_dirs: bool, parent=None):
        super().__init__(parent)
        self.left, self.right = left, right
        self.by_content, self.include_dirs = by_content, include_dirs

    def run(self) -> None:
        lmark, rmark = compare_panels(
            self.left, self.right, self.by_content, self.include_dirs)
        self.finished_compare.emit(lmark, rmark)


class CompareOptionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("Comparar listas de archivos"))
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(
            t("Quedan marcados los archivos que faltan del otro lado y los que son\n"
              "más nuevos. Los idénticos quedan sin marcar.")
        ))
        self.by_content = QCheckBox(t("Comparar por contenido (SHA-256, más lento)"))
        self.include_dirs = QCheckBox(t("Marcar también las carpetas que falten"))
        lay.addWidget(self.by_content)
        lay.addWidget(self.include_dirs)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(t("Comparar"))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)


def compute_checksums(paths: list[str], base_dir: str) -> str:
    """cm_CRCcreate 564: texto en formato sha256sum."""
    lines = []
    for p in paths:
        if os.path.isdir(p):
            continue
        d = file_digest(p)
        if d:
            lines.append(f"{d} *{os.path.relpath(p, base_dir)}")
    return "\n".join(lines) + ("\n" if lines else "")


def verify_checksums(sums_path: str) -> tuple[list[str], list[str], list[str]]:
    """cm_CRCcheck 565. Devuelve (ok, distintos, faltantes)."""
    base = os.path.dirname(sums_path)
    ok, bad, missing = [], [], []
    try:
        with open(sums_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(None, 1)
                if len(parts) != 2:
                    continue
                digest, name = parts[0], parts[1].lstrip("*")
                full = os.path.join(base, name)
                if not os.path.isfile(full):
                    missing.append(name)
                elif file_digest(full) == digest:
                    ok.append(name)
                else:
                    bad.append(name)
    except OSError:
        pass
    return ok, bad, missing
