"""Listado de directorios y modelo de tabla para un panel.

El marcado de archivos (Insert / Espacio / Num+) es independiente de la
selección del cursor de Qt: en un commander el cursor se mueve libremente sin
perder lo que ya marcaste. Por eso el modelo mantiene su propio conjunto
`marked` y la QTableView se configura sin selección propia de filas.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPalette
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from . import icons, platform, theme
from .i18n import t

COL_NAME, COL_EXT, COL_SIZE, COL_DATE, COL_ATTR = range(5)
COLUMNS = ["Nombre", "Ext", "Tamaño", "Fecha", "Atr"]

SORT_NAME, SORT_EXT, SORT_SIZE, SORT_DATE, SORT_NONE = range(5)

def icon_for(entry: "FileEntry") -> QIcon:
    """Icono del archivo.

    Por tipo para casi todo, y propio del archivo para los que llevan el icono
    adentro —`.exe`, `.lnk`— porque si no todos los programas se ven iguales.
    El detalle de las dos políticas está en `icons.py`.
    """
    cache = icons.cache()
    if entry.is_dir or entry.is_parent:
        return cache.folder_icon()
    ext = entry.ext
    if entry.virtual:
        # Adentro de un comprimido no hay archivo que mirar.
        return cache.por_tipo(ext, entry.path, real=False)
    if cache.lleva_icono_propio(ext):
        return cache.por_archivo(
            icons.IconCache.clave(entry.path, entry.mtime), entry.path, ext)
    return cache.por_tipo(ext, entry.path)


@dataclass
class FileEntry:
    name: str
    path: str
    is_dir: bool = False
    size: int = 0
    mtime: float = 0.0
    attrs: str = ""
    is_parent: bool = False
    # Para la vista de rama (Ctrl+B): ruta relativa a mostrar en vez del nombre.
    display: str | None = None
    # La ruta no existe en el disco: es una entrada adentro de un comprimido.
    virtual: bool = False

    @property
    def ext(self) -> str:
        if self.is_dir or self.is_parent:
            return ""
        _, _, e = self.name.rpartition(".")
        return e if e and e != self.name else ""

    @property
    def stem(self) -> str:
        if self.is_dir or self.is_parent or not self.ext:
            return self.name
        return self.name[: -len(self.ext) - 1]

    @property
    def label(self) -> str:
        return self.display or self.stem


def _attr_string(st: os.stat_result, name: str) -> str:
    return platform.attribute_string(st, name)


def _is_hidden(st: os.stat_result, name: str) -> bool:
    return platform.is_hidden(st, name)


def list_directory(path: str, show_hidden: bool = False) -> list[FileEntry]:
    """Lee un directorio. Las entradas inaccesibles se omiten en silencio."""
    entries: list[FileEntry] = []
    p = Path(path)
    if p.parent != p:
        entries.append(FileEntry(name="..", path=str(p.parent), is_dir=True, is_parent=True))
    try:
        with os.scandir(path) as it:
            for de in it:
                try:
                    st = de.stat(follow_symlinks=False)
                    if not show_hidden and _is_hidden(st, de.name):
                        continue
                    is_dir = de.is_dir(follow_symlinks=False)
                    entries.append(
                        FileEntry(
                            name=de.name,
                            path=de.path,
                            is_dir=is_dir,
                            size=0 if is_dir else st.st_size,
                            mtime=st.st_mtime,
                            attrs=_attr_string(st, de.name),
                        )
                    )
                except OSError:
                    continue
    except OSError:
        pass
    return entries


def list_branch(root: str, show_hidden: bool = False, limit: int = 100_000) -> list[FileEntry]:
    """Vista de rama (Ctrl+B): todos los archivos del subárbol, aplanados."""
    entries: list[FileEntry] = []
    rp = Path(root)
    if rp.parent != rp:
        entries.append(FileEntry(name="..", path=str(rp.parent), is_dir=True, is_parent=True))
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
        if not show_hidden:
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            try:
                st = os.stat(full)
                if not show_hidden and _is_hidden(st, fn):
                    continue
                rel = os.path.relpath(full, root)
                entries.append(
                    FileEntry(
                        name=fn,
                        path=full,
                        size=st.st_size,
                        mtime=st.st_mtime,
                        attrs=_attr_string(st, fn),
                        display=rel,
                    )
                )
            except OSError:
                continue
            if len(entries) >= limit:
                return entries
    return entries


def format_size(n: int) -> str:
    if n < 1024:
        return f"{n}"
    for unit in ("k", "M", "G", "T"):
        n /= 1024.0
        if n < 1024:
            return f"{n:,.1f} {unit}".replace(",", ".")
    return f"{n:,.1f} P"


class FileListModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.entries: list[FileEntry] = []
        self.marked: set[str] = set()
        self.sort_key = SORT_NAME
        self.sort_reverse = False
        self.dirs_first = True
        self.show_icons = True
        # Los iconos propios de cada archivo llegan de a tandas; cuando una
        # queda lista hay que repintar la columna de nombres.
        icons.cache().batch_ready.connect(self._repintar_iconos)

    # --- datos ---------------------------------------------------------

    def set_entries(self, entries: list[FileEntry], keep_marks: bool = False) -> None:
        self.beginResetModel()
        self.entries = entries
        if not keep_marks:
            self.marked.clear()
        else:
            present = {e.path for e in entries}
            self.marked &= present
        self._apply_sort()
        self.endResetModel()

    def _repintar_iconos(self) -> None:
        if self.entries:
            self.dataChanged.emit(self.index(0, COL_NAME),
                                  self.index(len(self.entries) - 1, COL_NAME),
                                  [Qt.DecorationRole])

    def entry(self, row: int) -> FileEntry | None:
        if 0 <= row < len(self.entries):
            return self.entries[row]
        return None

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.entries)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return t(COLUMNS[section])
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        e = self.entries[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == COL_NAME:
                if e.is_parent:
                    return ".."
                return f"[{e.label}]" if e.is_dir else e.label
            if col == COL_EXT:
                return e.ext
            if col == COL_SIZE:
                if e.is_parent:
                    return ""
                return "<DIR>" if e.is_dir else format_size(e.size)
            if col == COL_DATE:
                if e.is_parent or not e.mtime:
                    return ""
                return datetime.fromtimestamp(e.mtime).strftime("%d/%m/%y %H:%M")
            if col == COL_ATTR:
                return e.attrs

        elif role == Qt.DecorationRole and col == COL_NAME and self.show_icons:
            return icon_for(e)

        elif role == Qt.ForegroundRole:
            t = theme.current()
            if e.path in self.marked:
                return QBrush(QColor(t.marked))
            if "h" in e.attrs:
                return QBrush(QColor(t.text_dim))
            if e.is_dir and not e.is_parent:
                return QBrush(QColor(t.folder))

        elif role == Qt.FontRole:
            if e.path in self.marked:
                f = QFont()
                f.setBold(True)
                return f

        elif role == Qt.TextAlignmentRole and col in (COL_SIZE, COL_DATE):
            return int(Qt.AlignRight | Qt.AlignVCenter)

        return None

    # --- marcado -------------------------------------------------------

    def _markable(self, e: FileEntry) -> bool:
        return not e.is_parent

    def toggle_mark(self, row: int) -> None:
        e = self.entry(row)
        if e is None or not self._markable(e):
            return
        if e.path in self.marked:
            self.marked.discard(e.path)
        else:
            self.marked.add(e.path)
        self._row_changed(row)

    def set_marks(self, paths: set[str]) -> None:
        self.marked = {p for p in paths}
        self._all_changed()

    def mark_all(self, files_only: bool = False) -> None:
        for e in self.entries:
            if self._markable(e) and not (files_only and e.is_dir):
                self.marked.add(e.path)
        self._all_changed()

    def clear_marks(self) -> None:
        self.marked.clear()
        self._all_changed()

    def invert_marks(self, files_only: bool = False) -> None:
        for e in self.entries:
            if not self._markable(e) or (files_only and e.is_dir):
                continue
            if e.path in self.marked:
                self.marked.discard(e.path)
            else:
                self.marked.add(e.path)
        self._all_changed()

    def mark_by_pattern(self, patterns: list[str], mark: bool, files_only: bool = False) -> int:
        """Marca o desmarca según patrones glob separados por espacio o ';'."""
        import fnmatch

        count = 0
        for e in self.entries:
            if not self._markable(e) or (files_only and e.is_dir):
                continue
            if any(fnmatch.fnmatch(e.name.lower(), p.lower()) for p in patterns):
                if mark:
                    self.marked.add(e.path)
                else:
                    self.marked.discard(e.path)
                count += 1
        self._all_changed()
        return count

    def marked_entries(self) -> list[FileEntry]:
        return [e for e in self.entries if e.path in self.marked]

    def _row_changed(self, row: int) -> None:
        self.dataChanged.emit(
            self.index(row, 0), self.index(row, len(COLUMNS) - 1),
            [Qt.ForegroundRole, Qt.FontRole],
        )

    def _all_changed(self) -> None:
        if not self.entries:
            return
        self.dataChanged.emit(
            self.index(0, 0), self.index(len(self.entries) - 1, len(COLUMNS) - 1),
            [Qt.ForegroundRole, Qt.FontRole],
        )

    # --- ordenamiento ---------------------------------------------------

    def set_sort(self, key: int, reverse: bool | None = None) -> None:
        if reverse is None:
            reverse = not self.sort_reverse if key == self.sort_key else False
        self.beginResetModel()
        self.sort_key, self.sort_reverse = key, reverse
        self._apply_sort()
        self.endResetModel()

    def _apply_sort(self) -> None:
        if self.sort_key == SORT_NONE:
            return
        keyfns = {
            SORT_NAME: lambda e: e.name.lower(),
            SORT_EXT: lambda e: (e.ext.lower(), e.name.lower()),
            SORT_SIZE: lambda e: e.size,
            SORT_DATE: lambda e: e.mtime,
        }
        kf = keyfns[self.sort_key]
        parent = [e for e in self.entries if e.is_parent]
        rest = [e for e in self.entries if not e.is_parent]
        if self.dirs_first:
            dirs = sorted((e for e in rest if e.is_dir), key=kf, reverse=self.sort_reverse)
            files = sorted((e for e in rest if not e.is_dir), key=kf, reverse=self.sort_reverse)
            rest = dirs + files
        else:
            rest = sorted(rest, key=kf, reverse=self.sort_reverse)
        self.entries = parent + rest

    def refresh_colors(self) -> None:
        """Repintar tras un cambio de tema."""
        self._all_changed()


class EntryDelegate(QStyledItemDelegate):
    """Conserva el color de la fila aunque esté bajo el cursor.

    Por omisión Qt pinta el texto de una fila seleccionada con HighlightedText y
    descarta el ForegroundRole del modelo, con lo cual un archivo marcado deja
    de verse como marcado justo cuando el cursor está encima. En un commander
    eso importa, así que acá se reinyecta el color del modelo.
    """

    def initStyleOption(self, option, index) -> None:
        super().initStyleOption(option, index)
        brush = index.data(Qt.ForegroundRole)
        if brush is not None and (option.state & QStyle.State_Selected):
            option.palette.setBrush(QPalette.HighlightedText, brush)
