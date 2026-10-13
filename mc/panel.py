"""Un panel de archivos: pestañas, ruta, listado, marcado, historial.

Cada pestaña guarda su propio estado completo (ruta, marcas, posición del
cursor, orden), así que cambiar de pestaña y volver deja todo como estaba.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QSplitter, QTabBar, QTableView, QVBoxLayout, QWidget,
)

from . import archive, platform
from .config import config
from .i18n import t
from .fsmodel import (
    COLUMNS, COL_ATTR, COL_DATE, COL_EXT, COL_NAME, COL_SIZE, EntryDelegate, FileEntry,
    FileListModel, SORT_NAME, format_size, list_branch, list_directory,
)
from .ops import human
from .viewer import QuickView

MAX_HISTORY = 60


@dataclass
class TabState:
    path: str
    marked: set[str] = field(default_factory=set)
    cursor_row: int = 0
    branch: bool = False
    locked: bool = False
    archive_path: str = ""
    archive_inner: str = ""
    sort_key: int = SORT_NAME
    sort_reverse: bool = False
    history: list[str] = field(default_factory=list)
    history_pos: int = -1

    @property
    def title(self) -> str:
        if self.archive_path:
            name = os.path.basename(self.archive_path)
            return f"{name}" + (f"/{self.archive_inner.rstrip('/')}" if self.archive_inner else "")
        name = os.path.basename(self.path.rstrip("\\/")) or self.path
        return ("🔒 " if self.locked else "") + name


class DriveBar(QWidget):
    """Botones de unidades y espacio libre.

    La usan los dos modos: una sola barra arriba de la ventana que actúa sobre
    el panel activo, o una por panel atada a su lado. Por eso no conoce ningún
    panel: avisa qué unidad se eligió y quien la creó decide a dónde va.
    """

    drive_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(2)
        self.info = QLabel("")
        self.info.setObjectName("driveInfo")
        self.buttons: list[QPushButton] = []
        self.refresh_drives()

    def refresh_drives(self) -> None:
        """Rearma los botones. Se llama al enchufar o sacar un disco."""
        while self._lay.count():
            item = self._lay.takeAt(0)
            w = item.widget()
            if w is not None and w is not self.info:
                w.deleteLater()
        self.buttons.clear()

        for label, path in platform.list_drives():
            b = QPushButton(label.lower())
            b.setObjectName("drive")
            b.setToolTip(path)
            # Una letra de unidad entra en 30 px; un punto de montaje de Unix no.
            b.setFixedWidth(30 if len(label) <= 2 else min(140, 16 + 8 * len(label)))
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(lambda _=False, p=path: self.drive_clicked.emit(p))
            self._lay.addWidget(b)
            self.buttons.append(b)

        self._lay.addSpacing(12)
        self._lay.addWidget(self.info)
        self._lay.addStretch()

    def set_free_space(self, path: str) -> None:
        import shutil

        try:
            uso = shutil.disk_usage(path)
            # `human` y no `format_size`: es el mismo texto que mostraba la
            # barra única, y cambiarlo sería un cambio visible sin motivo.
            self.info.setText(t("{free} libres de {total}",
                                free=human(uso.free), total=human(uso.total)))
        except OSError:
            self.info.setText("")


class FileView(QTableView):
    """La tabla. Maneja las teclas propias del panel; el resto sube a la ventana."""

    activate_entry = Signal()
    toggle_mark_move = Signal(int)       # +1 baja, 0 no mueve
    quick_search_changed = Signal(str)
    selection_key = Signal(int, int)     # tecla, modificadores
    context_menu_at = Signal(object, bool)   # posición global, verbos extendidos

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setShowGrid(False)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.verticalHeader().hide()
        self.horizontalHeader().setHighlightSections(False)
        self.horizontalHeader().setSectionsClickable(True)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerItem)
        self._quick = ""
        self._quick_timer = QTimer(self)
        self._quick_timer.setSingleShot(True)
        self._quick_timer.setInterval(1200)
        self._quick_timer.timeout.connect(self._clear_quick)

    def _clear_quick(self) -> None:
        self._quick = ""
        self.quick_search_changed.emit("")

    def contextMenuEvent(self, event) -> None:
        """Clic derecho: el cursor se va a la fila clickeada y sale el menú.

        Con Shift aparecen los verbos extendidos, el mismo trato que da el
        Explorador. Si el clic cae fuera de toda fila, el menú sale igual pero
        sobre el directorio actual.
        """
        index = self.indexAt(event.pos())
        if index.isValid():
            self.setCurrentIndex(index.sibling(index.row(), 0))
        extendido = bool(event.modifiers() & Qt.ShiftModifier)
        self.context_menu_at.emit(event.globalPos(), extendido)
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key, mods = event.key(), event.modifiers()

        if key in (Qt.Key_Return, Qt.Key_Enter) and mods == Qt.NoModifier:
            self.activate_entry.emit()
            event.accept()
            return

        if key == Qt.Key_Insert and mods == Qt.NoModifier:
            self.toggle_mark_move.emit(1)
            event.accept()
            return

        if key == Qt.Key_Space and mods == Qt.NoModifier:
            if self._quick:          # si estoy en búsqueda rápida, el espacio es un carácter
                self._append_quick(" ")
            else:
                self.toggle_mark_move.emit(0)
            event.accept()
            return

        if key == Qt.Key_Backspace and self._quick:
            self._quick = self._quick[:-1]
            self.quick_search_changed.emit(self._quick)
            self._quick_timer.start()
            event.accept()
            return

        if key == Qt.Key_Escape and self._quick:
            self._clear_quick()
            event.accept()
            return

        # Las teclas de selección se resuelven acá en vez de con un QKeySequence:
        # en el teclado numérico vienen con KeypadModifier y el emparejamiento de
        # atajos para esas teclas no es confiable entre distribuciones de teclado.
        if key in (Qt.Key_Plus, Qt.Key_Minus, Qt.Key_Asterisk, Qt.Key_Slash):
            self.selection_key.emit(key, int(mods.value))
            event.accept()
            return

        # Búsqueda rápida: escribir letras salta al archivo que empiece así.
        text = event.text()
        if text and text.isprintable() and mods in (Qt.NoModifier, Qt.ShiftModifier):
            self._append_quick(text)
            event.accept()
            return

        super().keyPressEvent(event)

    def _append_quick(self, text: str) -> None:
        self._quick += text
        self.quick_search_changed.emit(self._quick)
        self._quick_timer.start()

    @property
    def quick_text(self) -> str:
        return self._quick


class Panel(QWidget):
    path_changed = Signal(str)
    focus_gained = Signal()
    status_changed = Signal()
    request_open = Signal(object)        # FileEntry que no es directorio

    def __init__(self, side: str, initial_path: str, parent=None):
        super().__init__(parent)
        self.side = side
        self.tabs: list[TabState] = []
        self.current_tab = 0
        self._loading = False
        self._stats: tuple[int, int, int] | None = None

        self.model = FileListModel(self)
        self.model.dirs_first = config.get_bool("general", "sort_dirs_first", True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(2)

        # Barra de unidades propia del panel. Sólo se ve en el modo "dos";
        # la ventana decide y llama a show_drive_bar().
        self.drive_bar = DriveBar()
        self.drive_bar.drive_clicked.connect(self._on_drive_clicked)
        self.drive_bar.hide()
        lay.addWidget(self.drive_bar)

        self.tabbar = QTabBar()
        self.tabbar.setExpanding(False)
        self.tabbar.setTabsClosable(True)
        self.tabbar.setMovable(True)
        self.tabbar.setDrawBase(False)
        self.tabbar.currentChanged.connect(self._on_tab_changed)
        self.tabbar.tabCloseRequested.connect(self.close_tab)
        lay.addWidget(self.tabbar)

        self.path_edit = QLineEdit()
        self.path_edit.setObjectName("pathBar")
        self.path_edit.setReadOnly(True)
        self.path_edit.setProperty("active", False)
        self.path_edit.returnPressed.connect(self._on_path_entered)
        self.path_edit.installEventFilter(self)
        lay.addWidget(self.path_edit)

        self.view = FileView()
        self.view.setModel(self.model)
        self.view.setItemDelegate(EntryDelegate(self.view))
        self.view.activate_entry.connect(self._activate_current)
        self.view.toggle_mark_move.connect(self._toggle_mark)
        self.view.quick_search_changed.connect(self._on_quick_search)
        self.view.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        self.view.installEventFilter(self)
        # Las flechas las maneja QTableView por dentro, así que sin esto la
        # barra de estado sólo se enteraba al recargar el directorio.
        self.view.selectionModel().currentRowChanged.connect(self._on_cursor_moved)

        self.quick_view = QuickView()
        self.quick_view.hide()
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.addWidget(self.view)
        self.splitter.addWidget(self.quick_view)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        lay.addWidget(self.splitter, 1)

        self.status = QLabel("")
        self.status.setObjectName("panelStatus")
        self.status.setTextFormat(Qt.PlainText)
        lay.addWidget(self.status)

        self._apply_font()
        self.add_tab(initial_path, activate=True)

    # --- apariencia -----------------------------------------------------

    def _apply_font(self) -> None:
        f = QFont(config.get("general", "font_family", "Consolas"),
                  config.get_int("general", "font_size", 10))
        self.view.setFont(f)
        self.view.verticalHeader().setDefaultSectionSize(
            self.view.fontMetrics().height() + 6)
        h = self.view.horizontalHeader()
        h.setSectionResizeMode(COL_NAME, QHeaderView.Stretch)
        for col, width in ((COL_EXT, 56), (COL_SIZE, 92), (COL_DATE, 118), (COL_ATTR, 46)):
            h.setSectionResizeMode(col, QHeaderView.Interactive)
            self.view.setColumnWidth(col, width)

    def show_drive_bar(self, visible: bool) -> None:
        self.drive_bar.setVisible(visible)
        if visible:
            self.drive_bar.set_free_space(self.path)

    def _on_drive_clicked(self, path: str) -> None:
        """Esta barra es de este panel: no hay que preguntar cuál está activo."""
        if not self.set_path(path):
            self.status.setText(t("No se puede acceder a {path}", path=path))
        self.view.setFocus()

    def set_active(self, active: bool) -> None:
        """Resalta el panel con foco: en un commander hay que ver cuál es el origen.

        El color lo pone el QSS a través de la propiedad dinámica `active`; hay
        que forzar un repolish porque Qt no reevalúa el selector por sí solo.
        """
        self.path_edit.setProperty("active", "true" if active else "false")
        self.path_edit.style().unpolish(self.path_edit)
        self.path_edit.style().polish(self.path_edit)

    def apply_theme(self) -> None:
        """Repintar tras un cambio de tema."""
        self._apply_font()
        self.model.refresh_colors()
        for widget in (self.path_edit, self.status, self.quick_view.title):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.FocusIn and obj is self.view:
            self.focus_gained.emit()
        if obj is self.path_edit and event.type() == QEvent.MouseButtonDblClick:
            self.edit_path()
        return super().eventFilter(obj, event)

    # --- pestañas -------------------------------------------------------

    @property
    def tab(self) -> TabState:
        return self.tabs[self.current_tab]

    def add_tab(self, path: str, activate: bool = True) -> None:
        state = TabState(path=os.path.abspath(path))
        self.tabs.append(state)
        self.tabbar.blockSignals(True)
        index = self.tabbar.addTab(state.title)
        self.tabbar.blockSignals(False)
        if activate:
            self.tabbar.setCurrentIndex(index)
            if self.current_tab != index:
                self._on_tab_changed(index)
            else:
                self.reload()
        self._update_close_buttons()

    def close_tab(self, index: int | None = None) -> None:
        if index is None:
            index = self.current_tab
        if len(self.tabs) <= 1:
            return
        if self.tabs[index].locked:
            return
        del self.tabs[index]
        self.tabbar.removeTab(index)
        self.current_tab = min(self.tabbar.currentIndex(), len(self.tabs) - 1)
        self._update_close_buttons()
        self.reload()

    def close_other_tabs(self) -> None:
        keep = self.tab
        self.tabs = [keep]
        self.tabbar.blockSignals(True)
        while self.tabbar.count():
            self.tabbar.removeTab(0)
        self.tabbar.addTab(keep.title)
        self.tabbar.blockSignals(False)
        self.current_tab = 0
        self._update_close_buttons()
        self.reload()

    def next_tab(self, delta: int = 1) -> None:
        if len(self.tabs) < 2:
            return
        self.tabbar.setCurrentIndex((self.current_tab + delta) % len(self.tabs))

    def activate_tab(self, index: int) -> None:
        if 0 <= index < len(self.tabs):
            self.tabbar.setCurrentIndex(index)

    def toggle_lock(self) -> None:
        self.tab.locked = not self.tab.locked
        self._refresh_tab_title()
        self._update_close_buttons()

    def _update_close_buttons(self) -> None:
        # Una sola pestaña no se puede cerrar; una bloqueada tampoco.
        for i in range(self.tabbar.count()):
            closable = len(self.tabs) > 1 and not self.tabs[i].locked
            for side in (QTabBar.RightSide, QTabBar.LeftSide):
                btn = self.tabbar.tabButton(i, side)
                if btn:
                    btn.setVisible(closable)

    def _on_tab_changed(self, index: int) -> None:
        if index < 0 or index >= len(self.tabs) or self._loading:
            return
        self._save_cursor()
        self.current_tab = index
        self.model.set_sort(self.tab.sort_key, self.tab.sort_reverse)
        self.reload(restore_cursor=True)

    def _refresh_tab_title(self) -> None:
        self.tabbar.setTabText(self.current_tab, self.tab.title)
        self.tabbar.setTabToolTip(self.current_tab, self.current_path_display())

    # --- navegación -----------------------------------------------------

    def current_path_display(self) -> str:
        t = self.tab
        if t.archive_path:
            return f"{t.archive_path}\\{t.archive_inner.replace('/', chr(92))}"
        return t.path

    @property
    def path(self) -> str:
        """Ruta real en disco (el zip contenedor si estoy adentro de un comprimido)."""
        t = self.tab
        return os.path.dirname(t.archive_path) if t.archive_path else t.path

    @property
    def in_archive(self) -> bool:
        return bool(self.tab.archive_path)

    def set_path(self, path: str, push_history: bool = True,
                 select_name: str | None = None) -> bool:
        path = os.path.abspath(os.path.expandvars(path.strip().strip('"')))
        if archive.is_archive(path):
            return self.open_archive(path)
        if not os.path.isdir(path):
            return False
        t = self.tab
        if t.locked:
            self.add_tab(path)
            return True
        t.archive_path = t.archive_inner = ""
        t.path = path
        t.marked.clear()
        if push_history:
            self._push_history(path)
        self.reload(select_name=select_name)
        return True

    def open_archive(self, zip_path: str, inner: str = "") -> bool:
        if not archive.is_archive(zip_path):
            return False
        t = self.tab
        t.archive_path = zip_path
        t.archive_inner = inner
        t.marked.clear()
        self.reload()
        return True

    def _push_history(self, path: str) -> None:
        t = self.tab
        if t.history_pos >= 0 and t.history[t.history_pos].lower() == path.lower():
            return
        del t.history[t.history_pos + 1:]
        t.history.append(path)
        if len(t.history) > MAX_HISTORY:
            t.history.pop(0)
        t.history_pos = len(t.history) - 1

    def go_back(self) -> bool:
        t = self.tab
        if t.history_pos <= 0:
            return False
        t.history_pos -= 1
        return self.set_path(t.history[t.history_pos], push_history=False)

    def go_forward(self) -> bool:
        t = self.tab
        if t.history_pos >= len(t.history) - 1:
            return False
        t.history_pos += 1
        return self.set_path(t.history[t.history_pos], push_history=False)

    def go_parent(self) -> None:
        t = self.tab
        if t.archive_path:
            if t.archive_inner:
                inner = t.archive_inner.rstrip("/")
                parent = inner.rpartition("/")[0]
                t.archive_inner = f"{parent}/" if parent else ""
                self.reload()
            else:
                zip_dir = os.path.dirname(t.archive_path)
                name = os.path.basename(t.archive_path)
                t.archive_path = t.archive_inner = ""
                self.set_path(zip_dir, select_name=name)
            return
        if t.branch:
            t.branch = False
            self.reload()
            return
        parent = os.path.dirname(t.path.rstrip("\\/"))
        if parent and parent != t.path:
            self.set_path(parent, select_name=os.path.basename(t.path.rstrip("\\/")))

    def go_root(self) -> None:
        drive = os.path.splitdrive(self.path)[0]
        if drive:
            self.set_path(drive + os.sep)

    def toggle_branch(self, selected_only: bool = False) -> None:
        t = self.tab
        t.branch = not t.branch
        self.reload()

    def toggle_quick_view(self) -> None:
        if self.quick_view.isVisible():
            self.quick_view.hide()
        else:
            self.quick_view.show()
            e = self.current_entry()
            self.quick_view.show_file(e.path if e and not e.is_dir else None)

    def edit_path(self) -> None:
        self.path_edit.setReadOnly(False)
        self.path_edit.setFocus()
        self.path_edit.selectAll()

    def _on_path_entered(self) -> None:
        text = self.path_edit.text()
        self.path_edit.setReadOnly(True)
        if not self.set_path(text):
            self.path_edit.setText(self.current_path_display())
        self.view.setFocus()

    # --- listado --------------------------------------------------------

    def reload(self, restore_cursor: bool = False, select_name: str | None = None) -> None:
        self._loading = True
        self._stats = None
        t = self.tab
        show_hidden = config.get_bool("general", "show_hidden", False)

        if t.archive_path:
            entries = archive.list_zip(t.archive_path, t.archive_inner)
        elif t.branch:
            entries = list_branch(t.path, show_hidden)
        else:
            entries = list_directory(t.path, show_hidden)

        self.model.set_entries(entries)
        self.model.set_marks(t.marked)

        row = 0
        if select_name:
            for i, e in enumerate(self.model.entries):
                if e.name.lower() == select_name.lower():
                    row = i
                    break
        elif restore_cursor:
            row = min(t.cursor_row, max(len(self.model.entries) - 1, 0))
        elif len(self.model.entries) > 1:
            row = 1 if self.model.entries[0].is_parent else 0

        self.set_cursor_row(row)
        self.path_edit.setText(self.current_path_display())
        self._refresh_tab_title()
        self._update_status()
        # El espacio libre se consulta sólo al recargar, no en cada movimiento
        # del cursor: es una llamada al sistema de archivos.
        if self.drive_bar.isVisible():
            self.drive_bar.set_free_space(self.path)
        self._loading = False
        self.path_changed.emit(self.current_path_display())

    def set_entries_override(self, entries: list[FileEntry]) -> None:
        """Volcar resultados de búsqueda en el panel (feed to listbox)."""
        self._stats = None
        self.model.set_entries(entries)
        self.tab.marked.clear()
        self.set_cursor_row(0)
        self._update_status()

    # --- cursor y marcado -----------------------------------------------

    def set_cursor_row(self, row: int) -> None:
        if not self.model.entries:
            return
        row = max(0, min(row, len(self.model.entries) - 1))
        index = self.model.index(row, COL_NAME)
        self.view.setCurrentIndex(index)
        self.view.scrollTo(index, QAbstractItemView.EnsureVisible)

    def cursor_row(self) -> int:
        idx = self.view.currentIndex()
        return idx.row() if idx.isValid() else 0

    def _save_cursor(self) -> None:
        if 0 <= self.current_tab < len(self.tabs):
            self.tabs[self.current_tab].cursor_row = self.cursor_row()
            self.tabs[self.current_tab].marked = set(self.model.marked)

    def current_entry(self) -> FileEntry | None:
        return self.model.entry(self.cursor_row())

    def selected_entries(self, fallback_to_cursor: bool = True) -> list[FileEntry]:
        """Lo marcado; si no hay nada marcado, lo que está bajo el cursor."""
        marked = self.model.marked_entries()
        if marked:
            return marked
        if fallback_to_cursor:
            e = self.current_entry()
            if e and not e.is_parent:
                return [e]
        return []

    def _toggle_mark(self, move: int) -> None:
        row = self.cursor_row()
        e = self.model.entry(row)
        self.model.toggle_mark(row)
        self.tab.marked = set(self.model.marked)
        # El Espacio sobre una carpeta calcula su tamaño, como en TC.
        if move == 0 and e and e.is_dir and not e.is_parent and e.path in self.model.marked:
            self._calc_dir_size(row, e)
        if move:
            self.set_cursor_row(row + move)
        self._update_status()

    def _calc_dir_size(self, row: int, entry: FileEntry) -> None:
        from .ops import scan

        entry.size = scan([entry.path]).total_bytes
        self.model.dataChanged.emit(
            self.model.index(row, COL_SIZE), self.model.index(row, COL_SIZE))
        self._update_status()

    def mark_all(self, files_only: bool = False) -> None:
        self.model.mark_all(files_only)
        self.tab.marked = set(self.model.marked)
        self._update_status()

    def clear_marks(self) -> None:
        self.model.clear_marks()
        self.tab.marked.clear()
        self._update_status()

    def invert_marks(self, files_only: bool = False) -> None:
        self.model.invert_marks(files_only)
        self.tab.marked = set(self.model.marked)
        self._update_status()

    def mark_pattern(self, patterns: list[str], mark: bool, files_only: bool = False) -> int:
        n = self.model.mark_by_pattern(patterns, mark, files_only)
        self.tab.marked = set(self.model.marked)
        self._update_status()
        return n

    def mark_same_extension(self, mark: bool = True) -> None:
        e = self.current_entry()
        if not e or e.is_parent:
            return
        pattern = f"*.{e.ext}" if e.ext else "*."
        self.mark_pattern([pattern], mark)

    def apply_marks(self, paths: set[str]) -> None:
        self.model.set_marks(paths)
        self.tab.marked = set(paths)
        self._update_status()

    # --- orden ----------------------------------------------------------

    def set_sort(self, key: int, reverse: bool | None = None) -> None:
        self.model.set_sort(key, reverse)
        self.tab.sort_key = self.model.sort_key
        self.tab.sort_reverse = self.model.sort_reverse
        self.set_cursor_row(self.cursor_row())

    def _on_header_clicked(self, section: int) -> None:
        mapping = {COL_NAME: 0, COL_EXT: 1, COL_SIZE: 2, COL_DATE: 3}
        if section in mapping:
            self.set_sort(mapping[section])

    # --- interacción ----------------------------------------------------

    def _activate_current(self) -> None:
        e = self.current_entry()
        if e is None:
            return
        if e.is_parent:
            self.go_parent()
            return
        if self.in_archive:
            if e.is_dir:
                self.tab.archive_inner = e.path
                self.reload()
            else:
                self.request_open.emit(e)
            return
        if e.is_dir:
            self.set_path(e.path)
        else:
            self.request_open.emit(e)

    def _on_quick_search(self, text: str) -> None:
        if not text:
            self._update_status()
            return
        low = text.lower()
        start = self.cursor_row()
        n = len(self.model.entries)
        # Buscar desde el cursor hacia adelante y dar la vuelta.
        for offset in range(n + 1):
            i = (start + offset) % n if n else 0
            e = self.model.entries[i]
            if e.name.lower().startswith(low):
                self.set_cursor_row(i)
                self.status.setText(t("Buscar: {text}", text=text))
                return
        self.status.setText(t("Buscar: {text}   (sin coincidencias)", text=text))

    def _on_cursor_moved(self, *_args) -> None:
        if not self._loading:
            self._update_status()

    def _link_target_bajo_cursor(self) -> str | None:
        """Destino del acceso directo bajo el cursor, si es uno.

        Adentro de un comprimido las rutas no son del disco, así que no hay
        nada que resolver.
        """
        if self.in_archive:
            return None
        e = self.current_entry()
        if e is None or e.is_parent or e.is_dir:
            return None
        return platform.link_target(e.path)

    def _listing_stats(self) -> tuple[int, int, int]:
        """(archivos, carpetas, bytes) del listado, calculado una sola vez.

        Se cachea porque la barra de estado ahora se refresca en cada
        movimiento del cursor y no sólo al recargar: recorrer diez mil entradas
        por cada flecha abajo se notaría. Marcar y ordenar no cambian estos
        totales, así que sólo hay que invalidarlo al releer el directorio.
        """
        if self._stats is None:
            archivos = carpetas = 0
            total = 0
            for e in self.model.entries:
                if e.is_parent:
                    continue
                if e.is_dir:
                    carpetas += 1
                else:
                    archivos += 1
                    total += e.size
            self._stats = (archivos, carpetas, total)
        return self._stats

    def _update_status(self) -> None:
        archivos, carpetas, total = self._listing_stats()
        hay_marcas = bool(self.model.marked)

        if not hay_marcas:
            destino = self._link_target_bajo_cursor()
            if destino:
                # Parado sobre un acceso directo, lo que interesa es adónde va.
                self.status.setText(t("→ {target}", target=destino))
                if self.quick_view.isVisible():
                    self.quick_view.show_file(
                        destino if os.path.isfile(destino) else None)
                self.status_changed.emit()
                return

        if hay_marcas:
            marked = self.model.marked_entries()
            self.status.setText(t(
                "{m} de {n} archivo(s) marcados, {msize} de {size}",
                m=len(marked), n=archivos,
                msize=format_size(sum(e.size for e in marked)),
                size=format_size(total)))
        else:
            self.status.setText(t(
                "{n} archivo(s), {d} carpeta(s), {size}",
                n=archivos, d=carpetas, size=format_size(total)))
        if self.quick_view.isVisible():
            e = self.current_entry()
            self.quick_view.show_file(e.path if e and not e.is_dir else None)
        self.status_changed.emit()

    def retranslate(self) -> None:
        """Refresca los textos propios del panel tras cambiar de idioma."""
        self.model.headerDataChanged.emit(Qt.Horizontal, 0, len(COLUMNS) - 1)
        self._update_status()
        self.quick_view.retranslate()

    def save_state(self) -> None:
        self._save_cursor()
