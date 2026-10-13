"""Ventana principal: dos paneles, menú, barra de unidades, línea de comandos.

El registro de comandos es el centro de todo. Cada acción vive una sola vez en
`self.commands` con el mismo nombre `cm_*` que usa Total Commander, y el menú,
la barra de teclas de función y los atajos no son más que tres formas distintas
de disparar la misma entrada. Agregar un comando es agregar una fila ahí.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from PySide6.QtCore import QMimeData, QUrl, Qt, QByteArray
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMenu, QMessageBox, QPushButton, QSplitter,
    QVBoxLayout, QWidget,
)

from . import archive
from .bookmarks import BookmarksDialog, add_bookmark
from .compare import (
    CompareOptionsDialog, CompareWorker, compute_checksums, verify_checksums,
)
from .config import config
from .dialogs import (
    AttributesDialog, CopyMoveDialog, ErrorListDialog, PropertiesDialog,
    SelectGroupDialog, TextPromptDialog,
)
from .editor import Editor
from .fsmodel import SORT_DATE, SORT_EXT, SORT_NAME, SORT_NONE, SORT_SIZE, format_size
from .ops import CopyMoveWorker, DeleteWorker, ProgressDialog, human, scan
from . import i18n, platform
from .i18n import t
from .panel import Panel
from .search import SearchDialog
from . import theme
from .viewer import Viewer

APP_TITLE = "Marce Commander"

FKEYS = [
    ("F3", "Ver", "cm_List"),
    ("F4", "Editar", "cm_Edit"),
    ("F5", "Copiar", "cm_Copy"),
    ("F6", "Mover", "cm_RenMov"),
    ("F7", "Crear dir", "cm_MkDir"),
    ("F8", "Borrar", "cm_Delete"),
    ("Alt+F5", "Comprimir", "cm_PackFiles"),
    ("Alt+F7", "Buscar", "cm_SearchFor"),
]

DROPEFFECT_FORMAT = "Preferred DropEffect"
DROPEFFECT_COPY = 5
DROPEFFECT_MOVE = 2


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1180, 720)

        self.left = Panel("left", config.get("general", "left_path", os.path.expanduser("~")))
        self.right = Panel("right", config.get("general", "right_path", os.path.expanduser("~")))
        self.active = self.left
        self._open_windows: list[QWidget] = []
        self._pattern_history: list[str] = []
        self._cmd_history: list[str] = []

        self.commands = {}
        self._build_commands()
        self._build_ui()
        self._build_menu()
        self._install_shortcuts()

        for panel in (self.left, self.right):
            panel.focus_gained.connect(lambda p=panel: self._set_active(p))
            panel.path_changed.connect(self._on_path_changed)
            panel.request_open.connect(self._open_entry)
            panel.view.selection_key.connect(self._on_selection_key)

        self._restore_geometry()
        self._set_active(self.left)
        self.left.view.setFocus()

    # --- construcción ---------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # Barra de unidades: actúa sobre el panel activo.
        drives = QHBoxLayout()
        drives.setSpacing(2)
        self.drive_buttons: list[QPushButton] = []
        for label, path in self._list_drives():
            b = QPushButton(label.lower())
            b.setObjectName("drive")
            b.setToolTip(path)
            # Una letra de unidad entra en 30 px; un punto de montaje de Unix no.
            b.setFixedWidth(30 if len(label) <= 2 else min(140, 16 + 8 * len(label)))
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(lambda _=False, p=path: self._goto_drive(p))
            drives.addWidget(b)
            self.drive_buttons.append(b)
        drives.addSpacing(12)
        self.drive_info = QLabel("")
        self.drive_info.setObjectName("driveInfo")
        drives.addWidget(self.drive_info)
        drives.addStretch()
        root.addLayout(drives)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.left)
        self.splitter.addWidget(self.right)
        self.splitter.setSizes([1, 1])
        self.splitter.setChildrenCollapsible(False)
        root.addWidget(self.splitter, 1)

        # Línea de comandos.
        cmd_row = QHBoxLayout()
        self.prompt = QLabel("")
        self.prompt.setObjectName("prompt")
        self.cmdline = QComboBox()
        self.cmdline.setEditable(True)
        self.cmdline.setInsertPolicy(QComboBox.NoInsert)
        self.cmdline.lineEdit().setPlaceholderText(
            t("escribí un comando y Enter — 'cd ruta' cambia el panel activo"))
        self.cmdline.lineEdit().returnPressed.connect(self._run_command_line)
        cmd_row.addWidget(self.prompt)
        cmd_row.addWidget(self.cmdline, 1)
        root.addLayout(cmd_row)

        fkeys = QHBoxLayout()
        fkeys.setSpacing(3)
        self.fkey_buttons: list[tuple] = []
        for key, label, command in FKEYS:
            b = QPushButton(f"{key}  {t(label)}")
            b.setObjectName("fkey")
            self.fkey_buttons.append((b, key, label))
            b.clicked.connect(lambda _=False, c=command: self.run(c))
            b.setFocusPolicy(Qt.NoFocus)
            fkeys.addWidget(b)
        root.addLayout(fkeys)

        self.setCentralWidget(central)
        self.statusBar().showMessage(t("Listo."))

    def _build_menu(self) -> None:
        def add(menu, title, command, shortcut_text=""):
            a = QAction(title + (f"\t{shortcut_text}" if shortcut_text else ""), self)
            a.triggered.connect(lambda _=False, c=command: self.run(c))
            menu.addAction(a)
            return a

        m = self.menuBar().addMenu(t("&Archivos"))
        add(m, "&Ver", "cm_List", "F3")
        add(m, "&Editar", "cm_Edit", "F4")
        add(m, "&Copiar", "cm_Copy", "F5")
        add(m, "&Mover / Renombrar", "cm_RenMov", "F6")
        add(m, "Renombrar en el &sitio", "cm_RenameOnly", "Shift+F6")
        add(m, "Crear &directorio", "cm_MkDir", "F7")
        add(m, "&Borrar", "cm_Delete", "F8")
        m.addSeparator()
        add(m, "C&omprimir…", "cm_PackFiles", "Alt+F5")
        add(m, "&Descomprimir…", "cm_UnpackFiles", "Alt+F6")
        add(m, "&Verificar comprimidos", "cm_TestArchive", "Alt+Shift+F9")
        m.addSeparator()
        add(m, "Cambiar &atributos…", "cm_SetAttrib")
        add(m, "&Propiedades", "cm_Properties", "Alt+Enter")
        add(m, "Calcular espacio ocupado", "cm_GetFileSpace", "Shift+Alt+Enter")
        add(m, "Crear &checksums SHA-256", "cm_CRCcreate")
        add(m, "Verificar checksums", "cm_CRCcheck")
        m.addSeparator()
        add(m, "&Salir", "cm_Exit", "Alt+F4")

        m = self.menuBar().addMenu(t("&Marcar"))
        add(m, "&Seleccionar grupo…", "cm_SpreadSelection", "Num +")
        add(m, "&Deseleccionar grupo…", "cm_ShrinkSelection", "Num -")
        add(m, "&Invertir selección", "cm_ExchangeSelection", "Num *")
        m.addSeparator()
        add(m, "Seleccionar &todo", "cm_SelectAll", "Ctrl+A")
        add(m, "Deseleccionar todo", "cm_ClearAll", "Ctrl+Shift+A")
        add(m, "Seleccionar la misma e&xtensión", "cm_SelectCurrentExtension", "Alt+Num +")
        add(m, "Deseleccionar la misma extensión", "cm_UnselectCurrentExtension", "Alt+Num -")
        m.addSeparator()
        add(m, "&Comparar listas de archivos…", "cm_CompareDirs", "Shift+F2")

        m = self.menuBar().addMenu(t("&Comandos"))
        add(m, "&Buscar archivos…", "cm_SearchFor", "Alt+F7")
        add(m, "&Marcadores de directorios…", "cm_DirectoryHotlist", "Ctrl+D")
        add(m, "&Historial de directorios…", "cm_DirectoryHistory", "Alt+Abajo")
        m.addSeparator()
        add(m, "&Intercambiar paneles", "cm_ExchangeWithTabs", "Ctrl+U")
        add(m, "El mismo directorio en el otro panel", "cm_TargetEqualSource", "Ctrl+Shift+Enter")
        add(m, "Cambio de directorio &sincronizado", "cm_SyncChangeDir")
        m.addSeparator()
        add(m, "&Nueva pestaña", "cm_OpenNewTab", "Ctrl+T")
        add(m, "&Cerrar pestaña", "cm_CloseCurrentTab", "Ctrl+W")
        add(m, "&Bloquear pestaña", "cm_ToggleLockCurrentTab")
        m.addSeparator()
        add(m, "&Abrir una consola acá", "cm_ExecuteDOS", "Ctrl+Shift+Enter")
        add(m, "Abrir en el &Explorador", "cm_OpenInExplorer")
        add(m, "Vista &rápida", "cm_SrcQuickview", "Ctrl+Q")
        add(m, "Vista de ra&ma", "cm_SrcDirBranch", "Ctrl+B")

        m = self.menuBar().addMenu(t("&Ver"))
        add(m, "&Releer panel", "cm_RereadSrc", "F2")
        m.addSeparator()
        sort_menu = m.addMenu(t("&Ordenar por"))
        self._sort_group = QActionGroup(self)
        for title, command, shortcut, key in (
            ("&Nombre", "cm_SrcByName", "Ctrl+F3", SORT_NAME),
            ("&Extensión", "cm_SrcByExt", "Ctrl+F4", SORT_EXT),
            ("&Fecha", "cm_SrcByDateTime", "Ctrl+F5", SORT_DATE),
            ("&Tamaño", "cm_SrcBySize", "Ctrl+F6", SORT_SIZE),
            ("&Sin ordenar", "cm_SrcUnsorted", "Ctrl+F7", SORT_NONE),
        ):
            a = add(sort_menu, title, command, shortcut)
            a.setCheckable(True)
            a.setData(key)
            self._sort_group.addAction(a)
            if key == SORT_NAME:
                a.setChecked(True)
        m.addSeparator()
        self.act_hidden = QAction("Mostrar archivos &ocultos\tCtrl+F10", self, checkable=True)
        self.act_hidden.setChecked(config.get_bool("general", "show_hidden", False))
        self.act_hidden.triggered.connect(lambda: self.run("cm_ShowHidden"))
        m.addAction(self.act_hidden)
        m.addSeparator()
        add(m, "Paneles &verticales", "cm_VerticalPanels")

        m = self.menuBar().addMenu(t("Config&uración"))
        apariencia = m.addMenu(t("&Apariencia"))
        self._theme_group = QActionGroup(self)
        current_theme = config.get("general", "theme", "auto")
        for title, value in (("&Automático (según el sistema)", "auto"),
                             ("&Oscuro", "dark"),
                             ("&Claro", "light")):
            a = QAction(t(title), self, checkable=True)
            a.setData(value)
            a.setChecked(value == current_theme)
            a.triggered.connect(lambda _=False, v=value: self.cmd_set_theme(v))
            self._theme_group.addAction(a)
            apariencia.addAction(a)
        apariencia.addSeparator()
        a = QAction(t("Alternar claro / oscuro") + "\tCtrl+Shift+T", self)
        a.triggered.connect(lambda: self.run("cm_ToggleTheme"))
        apariencia.addAction(a)

        idioma = m.addMenu(t("&Idioma"))
        self._lang_group = QActionGroup(self)
        current_lang = config.get("general", "language", "auto")
        for code, label in [("auto", t("&Automático (según el sistema)"))] + \
                [(c, n) for c, n in i18n.available().items()]:
            a = QAction(label, self, checkable=True)
            a.setData(code)
            a.setChecked(code == current_lang)
            a.triggered.connect(lambda _=False, c=code: self.cmd_set_language(c))
            self._lang_group.addAction(a)
            idioma.addAction(a)
        m.addSeparator()
        self.act_recycle = QAction(t("Borrar a la &papelera de reciclaje"), self, checkable=True)
        self.act_recycle.setChecked(config.get_bool("general", "delete_to_recycle", True))
        self.act_recycle.triggered.connect(lambda: self.run("cm_ToggleRecycle"))
        m.addAction(self.act_recycle)
        add(m, "Elegir &editor externo…", "cm_ChooseEditor")
        add(m, "Guardar la configuración &ahora", "cm_SaveConfig")
        m.addSeparator()
        add(m, "&Atajos de teclado", "cm_KeyboardHelp", "F1")
        add(m, "&Acerca de", "cm_About")

    def _install_shortcuts(self) -> None:
        bindings = [
            ("F1", "cm_KeyboardHelp"), ("F2", "cm_RereadSrc"),
            ("F3", "cm_List"), ("F4", "cm_Edit"), ("F5", "cm_Copy"),
            ("F6", "cm_RenMov"), ("F7", "cm_MkDir"), ("F8", "cm_Delete"),
            ("Del", "cm_Delete"),
            ("Shift+F2", "cm_CompareDirs"), ("Shift+F4", "cm_EditNewFile"),
            ("Shift+F5", "cm_CopySamepanel"), ("Shift+F6", "cm_RenameOnly"),
            ("Shift+F7", "cm_MkDirOther"), ("Shift+F8", "cm_DeletePermanent"),
            ("Shift+Del", "cm_DeletePermanent"), ("Shift+F10", "cm_ContextMenu"),
            ("Alt+F1", "cm_LeftOpenDrives"), ("Alt+F2", "cm_RightOpenDrives"),
            ("Alt+F5", "cm_PackFiles"), ("Alt+F6", "cm_UnpackFiles"),
            ("Alt+F9", "cm_UnpackFiles"), ("Alt+F7", "cm_SearchFor"),
            ("Alt+Shift+F9", "cm_TestArchive"),
            ("Alt+Return", "cm_Properties"), ("Alt+Shift+Return", "cm_GetFileSpace"),
            ("Alt+Left", "cm_GotoPreviousDir"), ("Alt+Right", "cm_GotoNextDir"),
            ("Alt+Down", "cm_DirectoryHistory"),
            ("Ctrl+F1", "cm_SrcShort"), ("Ctrl+F2", "cm_SrcLong"),
            ("Ctrl+F3", "cm_SrcByName"), ("Ctrl+F4", "cm_SrcByExt"),
            ("Ctrl+F5", "cm_SrcByDateTime"), ("Ctrl+F6", "cm_SrcBySize"),
            ("Ctrl+F7", "cm_SrcUnsorted"), ("Ctrl+F10", "cm_ShowHidden"),
            ("Tab", "cm_SwitchPanel"), ("Backspace", "cm_GoToParent"),
            ("Ctrl+PgUp", "cm_GoToParent"), ("Ctrl+PgDown", "cm_GoToDir"),
            ("Ctrl+\\", "cm_GoToRoot"),
            ("Ctrl+Left", "cm_TransferToOtherLeft"),
            ("Ctrl+Right", "cm_TransferToOtherRight"),
            ("Ctrl+A", "cm_SelectAll"), ("Ctrl+Shift+A", "cm_ClearAll"),
            ("Ctrl+T", "cm_OpenNewTab"), ("Ctrl+W", "cm_CloseCurrentTab"),
            ("Ctrl+Tab", "cm_SwitchToNextTab"),
            ("Ctrl+Shift+Tab", "cm_SwitchToPreviousTab"),
            ("Ctrl+U", "cm_ExchangeWithTabs"), ("Ctrl+D", "cm_DirectoryHotlist"),
            ("Ctrl+B", "cm_SrcDirBranch"), ("Ctrl+Q", "cm_SrcQuickview"),
            ("Ctrl+C", "cm_CopyToClipboard"), ("Ctrl+X", "cm_CutToClipboard"),
            ("Ctrl+V", "cm_PasteFromClipboard"),
            ("Ctrl+Shift+C", "cm_CopyFullNamesToClip"),
            ("Ctrl+P", "cm_CopySrcPathToClip"),
            ("Ctrl+Return", "cm_AppendToCmdLine"),
            ("Ctrl+Shift+Return", "cm_ExecuteDOS"),
            ("Ctrl+E", "cm_FocusCmdLine"),
            ("Alt+F11", "cm_EditPath"),
            ("Shift+Esc", "cm_Minimize"),
            ("Ctrl+Shift+T", "cm_ToggleTheme"),
        ]
        for i in range(1, 10):
            bindings.append((f"Alt+{i}", f"cm_SrcActivateTab{i}"))

        for seq, command in bindings:
            a = QAction(self)
            a.setShortcut(QKeySequence(seq))
            a.setShortcutContext(Qt.WindowShortcut)
            a.triggered.connect(lambda _=False, c=command: self.run(c))
            self.addAction(a)

    # --- registro de comandos -------------------------------------------

    def _build_commands(self) -> None:
        c = self.commands
        p = lambda: self.active                       # panel origen
        o = lambda: self.other                        # panel destino

        c.update({
            # archivos
            "cm_List": self.cmd_list,
            "cm_Edit": self.cmd_edit,
            "cm_EditNewFile": self.cmd_edit_new,
            "cm_Copy": lambda: self.cmd_copy_move(move=False),
            "cm_RenMov": lambda: self.cmd_copy_move(move=True),
            "cm_CopySamepanel": self.cmd_copy_same_panel,
            "cm_RenameOnly": self.cmd_rename_inplace,
            "cm_MkDir": lambda: self.cmd_mkdir(other=False),
            "cm_MkDirOther": lambda: self.cmd_mkdir(other=True),
            "cm_Delete": lambda: self.cmd_delete(permanent=False),
            "cm_DeletePermanent": lambda: self.cmd_delete(permanent=True),
            "cm_Properties": self.cmd_properties,
            "cm_GetFileSpace": self.cmd_file_space,
            "cm_SetAttrib": self.cmd_attributes,
            "cm_Return": self.cmd_open,
            "cm_CRCcreate": self.cmd_crc_create,
            "cm_CRCcheck": self.cmd_crc_check,
            # comprimidos
            "cm_PackFiles": self.cmd_pack,
            "cm_UnpackFiles": self.cmd_unpack,
            "cm_TestArchive": self.cmd_test_archive,
            # marcado
            "cm_SpreadSelection": lambda: self.cmd_mark_group(True),
            "cm_ShrinkSelection": lambda: self.cmd_mark_group(False),
            "cm_ExchangeSelection": lambda: p().invert_marks(),
            "cm_SelectAll": lambda: p().mark_all(),
            "cm_ClearAll": lambda: p().clear_marks(),
            "cm_SelectCurrentExtension": lambda: p().mark_same_extension(True),
            "cm_UnselectCurrentExtension": lambda: p().mark_same_extension(False),
            "cm_CompareDirs": self.cmd_compare_dirs,
            # navegación
            "cm_GoToParent": lambda: p().go_parent(),
            "cm_GoToRoot": lambda: p().go_root(),
            "cm_GoToDir": self.cmd_open,
            "cm_GotoPreviousDir": lambda: p().go_back(),
            "cm_GotoNextDir": lambda: p().go_forward(),
            "cm_DirectoryHistory": self.cmd_history_menu,
            "cm_DirectoryHotlist": self.cmd_bookmarks,
            "cm_TransferToOtherLeft": lambda: self.cmd_transfer_to_other(),
            "cm_TransferToOtherRight": lambda: self.cmd_transfer_to_other(),
            "cm_TargetEqualSource": self.cmd_target_equal_source,
            "cm_SyncChangeDir": self.cmd_toggle_sync,
            "cm_SearchFor": self.cmd_search,
            "cm_EditPath": lambda: p().edit_path(),
            "cm_LeftOpenDrives": lambda: self.cmd_drive_menu(self.left),
            "cm_RightOpenDrives": lambda: self.cmd_drive_menu(self.right),
            # paneles y pestañas
            "cm_SwitchPanel": self.cmd_switch_panel,
            "cm_ExchangeWithTabs": self.cmd_swap_panels,
            "cm_OpenNewTab": lambda: p().add_tab(p().path),
            "cm_CloseCurrentTab": lambda: p().close_tab(),
            "cm_SwitchToNextTab": lambda: p().next_tab(1),
            "cm_SwitchToPreviousTab": lambda: p().next_tab(-1),
            "cm_ToggleLockCurrentTab": lambda: p().toggle_lock(),
            "cm_VerticalPanels": self.cmd_toggle_orientation,
            # vista
            "cm_RereadSrc": lambda: p().reload(restore_cursor=True),
            "cm_SrcByName": lambda: p().set_sort(SORT_NAME),
            "cm_SrcByExt": lambda: p().set_sort(SORT_EXT),
            "cm_SrcBySize": lambda: p().set_sort(SORT_SIZE),
            "cm_SrcByDateTime": lambda: p().set_sort(SORT_DATE),
            "cm_SrcUnsorted": lambda: p().set_sort(SORT_NONE),
            "cm_SrcShort": lambda: self.cmd_view_mode(brief=True),
            "cm_SrcLong": lambda: self.cmd_view_mode(brief=False),
            "cm_SrcQuickview": lambda: p().toggle_quick_view(),
            "cm_SrcDirBranch": lambda: p().toggle_branch(),
            "cm_ShowHidden": self.cmd_toggle_hidden,
            # portapapeles
            "cm_CopyToClipboard": lambda: self.cmd_clipboard_files(move=False),
            "cm_CutToClipboard": lambda: self.cmd_clipboard_files(move=True),
            "cm_PasteFromClipboard": self.cmd_paste,
            "cm_CopyNamesToClip": lambda: self.cmd_copy_names(full=False),
            "cm_CopyFullNamesToClip": lambda: self.cmd_copy_names(full=True),
            "cm_CopySrcPathToClip": lambda: self._to_clipboard_text(p().path),
            # varios
            "cm_ContextMenu": self.cmd_context_menu,
            "cm_ExecuteDOS": self.cmd_open_terminal,
            "cm_OpenInExplorer": self.cmd_open_explorer,
            "cm_FocusCmdLine": lambda: self.cmdline.setFocus(),
            "cm_AppendToCmdLine": self.cmd_append_to_cmdline,
            "cm_ToggleRecycle": self.cmd_toggle_recycle,
            "cm_ToggleTheme": self.cmd_toggle_theme,
            "cm_ChooseEditor": self.cmd_choose_editor,
            "cm_SaveConfig": lambda: (self._save_settings(),
                                      self.statusBar().showMessage(t("Configuración guardada."), 3000)),
            "cm_KeyboardHelp": self.cmd_keyboard_help,
            "cm_About": self.cmd_about,
            "cm_Minimize": self.showMinimized,
            "cm_Exit": self.close,
        })
        for i in range(1, 10):
            c[f"cm_SrcActivateTab{i}"] = lambda i=i: self.active.activate_tab(i - 1)

    def run(self, command: str) -> None:
        fn = self.commands.get(command)
        if fn is None:
            self.statusBar().showMessage(t("Comando no implementado: {name}", name=command), 4000)
            return
        try:
            fn()
        except Exception as exc:                       # un comando roto no tumba la app
            QMessageBox.critical(self, APP_TITLE, t("Error en {name}:\n{error}", name=command, error=exc))

    # --- estado de paneles -----------------------------------------------

    @property
    def other(self) -> Panel:
        return self.right if self.active is self.left else self.left

    def _set_active(self, panel: Panel) -> None:
        self.active = panel
        self.left.set_active(panel is self.left)
        self.right.set_active(panel is self.right)
        self._update_prompt()
        self._update_drive_info()

    def cmd_switch_panel(self) -> None:
        target = self.other
        self._set_active(target)
        target.view.setFocus()

    def _on_path_changed(self, _path: str) -> None:
        self._update_prompt()
        self._update_drive_info()
        if getattr(self, "_sync_dirs", False):
            self._sync_other_panel()

    def _update_prompt(self) -> None:
        self.prompt.setText(f"{self.active.path}>")
        self.setWindowTitle(f"{self.active.current_path_display()} — {APP_TITLE}")

    def _update_drive_info(self) -> None:
        import shutil

        try:
            usage = shutil.disk_usage(self.active.path)
            self.drive_info.setText(
                t("{free} libres de {total}", free=human(usage.free), total=human(usage.total)))
        except OSError:
            self.drive_info.setText("")

    @staticmethod
    def _list_drives() -> list[tuple[str, str]]:
        """[(etiqueta, ruta)]. En Unix no hay letras: son puntos de montaje."""
        return platform.list_drives()

    def _goto_drive(self, path: str) -> None:
        if not self.active.set_path(path):
            QMessageBox.warning(self, APP_TITLE, t("No se puede acceder a {path}", path=path))
        self.active.view.setFocus()

    def cmd_drive_menu(self, panel: Panel) -> None:
        menu = QMenu(self)
        for label, path in self._list_drives():
            menu.addAction(f"{label}   {path}", lambda p=path: panel.set_path(p))
        menu.exec(self.mapToGlobal(self.rect().topLeft()))

    def _on_selection_key(self, key: int, mods: int) -> None:
        alt = bool(mods & int(Qt.AltModifier.value))
        ctrl = bool(mods & int(Qt.ControlModifier.value))
        if key == Qt.Key_Plus:
            if ctrl:
                self.active.mark_all()
            elif alt:
                self.active.mark_same_extension(True)
            else:
                self.cmd_mark_group(True)
        elif key == Qt.Key_Minus:
            if ctrl:
                self.active.clear_marks()
            elif alt:
                self.active.mark_same_extension(False)
            else:
                self.cmd_mark_group(False)
        elif key == Qt.Key_Asterisk:
            self.active.invert_marks()
        elif key == Qt.Key_Slash:
            self.active.clear_marks()

    # --- comandos: archivos ----------------------------------------------

    def _selection(self) -> list:
        entries = self.active.selected_entries()
        if not entries:
            self.statusBar().showMessage(t("No hay nada seleccionado."), 3000)
        return entries

    def _materialize(self, entry) -> str | None:
        """Si estoy adentro de un zip, extrae a temporal y devuelve la ruta real."""
        if not self.active.in_archive:
            return entry.path
        try:
            tmp = tempfile.mkdtemp(prefix="mc_")
            return archive.extract_one(self.active.tab.archive_path, entry.path, tmp)
        except Exception as exc:
            QMessageBox.warning(self, APP_TITLE, t("No se pudo extraer:\n{error}", error=exc))
            return None

    def cmd_list(self) -> None:
        e = self.active.current_entry()
        if e is None or e.is_parent or e.is_dir:
            return
        path = self._materialize(e)
        if path:
            self._show_window(Viewer(path, self))

    def cmd_edit(self) -> None:
        e = self.active.current_entry()
        if e is None or e.is_parent or e.is_dir:
            return
        path = self._materialize(e)
        if path:
            self._edit_path(path)

    def _edit_path(self, path: str) -> None:
        external = config.get("general", "editor", "").strip()
        if external and external.lower() not in ("", "interno"):
            try:
                subprocess.Popen([external, path])
                return
            except OSError:
                pass            # si el editor externo falla, uso el interno
        self._show_window(Editor(path, self))

    def cmd_edit_new(self) -> None:
        name = TextPromptDialog.ask(
            self, t("Nuevo archivo de texto"), t("Nombre del archivo:"), t("nuevo.txt"), True)
        if not name:
            return
        path = os.path.join(self.active.path, name)
        if not os.path.exists(path):
            try:
                open(path, "a", encoding="utf-8").close()
            except OSError as exc:
                QMessageBox.warning(self, APP_TITLE, t("No se pudo crear:\n{error}", error=exc))
                return
        self.active.reload(select_name=name)
        self._edit_path(path)

    def _show_window(self, win: QWidget) -> None:
        self._open_windows.append(win)
        win.destroyed.connect(lambda: self._forget_window(win))
        win.show()
        theme.apply_titlebar(win)       # el marco nativo no hereda el QSS

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not getattr(self, "_titlebar_done", False):
            self._titlebar_done = True
            theme.apply_titlebar(self)

    def _forget_window(self, win) -> None:
        try:
            self._open_windows.remove(win)
        except ValueError:
            pass

    def cmd_open(self) -> None:
        self.active._activate_current()

    def _open_entry(self, entry) -> None:
        """Enter sobre un archivo: comprimido se abre, el resto va al shell."""
        if self.active.in_archive:
            path = self._materialize(entry)
            if path:
                self._show_window(Viewer(path, self))
            return
        if archive.is_archive(entry.path):
            self.active.open_archive(entry.path)
            return
        try:
            platform.open_with_default_app(entry.path)
        except OSError as exc:
            QMessageBox.warning(self, APP_TITLE, t("No se pudo abrir:\n{error}", error=exc))

    def cmd_copy_move(self, move: bool) -> None:
        entries = self._selection()
        if not entries:
            return
        if self.active.in_archive:
            if move:
                QMessageBox.information(
                    self, APP_TITLE,
                    t("Mover desde adentro de un comprimido no está soportado."))
                return
            self._unpack_members(entries)
            return

        dest = self.other.path
        if len(entries) == 1:
            dest = os.path.join(dest, entries[0].name)
        dlg = CopyMoveDialog(move, entries, dest, self)
        if dlg.exec() != QDialog.Accepted:
            return
        target = dlg.destination()
        if not target:
            return

        # Un solo elemento con destino que no es un directorio existente:
        # es copiar-y-renombrar en un paso.
        if len(entries) == 1 and not os.path.isdir(target):
            parent = os.path.dirname(target) or self.active.path
            if not os.path.isdir(parent):
                QMessageBox.warning(self, APP_TITLE, t("No existe el directorio:\n{path}", path=parent))
                return
            self._run_transfer([entries[0].path], parent, move,
                               rename_to=os.path.basename(target))
            return

        if not os.path.isdir(target):
            r = QMessageBox.question(
                self, APP_TITLE, t("El directorio no existe:\n{path}\n\n¿Crearlo?", path=target))
            if r != QMessageBox.Yes:
                return
            try:
                os.makedirs(target, exist_ok=True)
            except OSError as exc:
                QMessageBox.warning(self, APP_TITLE, t("No se pudo crear:\n{error}", error=exc))
                return
        self._run_transfer([e.path for e in entries], target, move)

    def _run_transfer(self, sources: list[str], dest_dir: str, move: bool,
                      rename_to: str | None = None) -> None:
        worker = CopyMoveWorker(sources, dest_dir, move, rename_to, self)
        title = t("Moviendo…") if move else t("Copiando…")
        count, errors = ProgressDialog(title, worker, self).run()
        self._after_file_op(count, errors, title)

    def _after_file_op(self, count: int, errors: list[str], title: str) -> None:
        self.left.reload(restore_cursor=True)
        self.right.reload(restore_cursor=True)
        if errors:
            ErrorListDialog(title, errors, self).exec()
        else:
            self.statusBar().showMessage(t("{n} elemento(s) procesado(s).", n=count), 4000)

    def cmd_copy_same_panel(self) -> None:
        e = self.active.current_entry()
        if e is None or e.is_parent:
            return
        name = TextPromptDialog.ask(
            self, t("Copiar en el mismo directorio"), t("Nombre de la copia:"), e.name, True)
        if not name or name == e.name:
            return
        self._run_transfer([e.path], self.active.path, move=False, rename_to=name)

    def cmd_rename_inplace(self) -> None:
        e = self.active.current_entry()
        if e is None or e.is_parent:
            return
        name = TextPromptDialog.ask(self, t("Renombrar"), t("Nombre nuevo:"), e.name, True)
        if not name or name == e.name:
            return
        target = os.path.join(os.path.dirname(e.path), name)
        if os.path.exists(target):
            QMessageBox.warning(self, APP_TITLE, t("Ya existe:\n{path}", path=target))
            return
        try:
            os.rename(e.path, target)
        except OSError as exc:
            QMessageBox.warning(self, APP_TITLE, t("No se pudo renombrar:\n{error}", error=exc))
            return
        self.active.reload(select_name=name)

    def cmd_mkdir(self, other: bool = False) -> None:
        panel = self.other if other else self.active
        suggestion = ""
        e = self.active.current_entry()
        if other and e and not e.is_parent:
            suggestion = e.name
        name = TextPromptDialog.ask(
            self, t("Crear directorio"),
            t("Nombre del directorio nuevo en:\n{path}", path=panel.path), suggestion)
        if not name:
            return
        path = os.path.join(panel.path, name)
        try:
            os.makedirs(path, exist_ok=False)
        except FileExistsError:
            QMessageBox.warning(self, APP_TITLE, t("Ya existe un elemento con ese nombre."))
            return
        except OSError as exc:
            QMessageBox.warning(self, APP_TITLE, t("No se pudo crear:\n{error}", error=exc))
            return
        panel.reload(select_name=name.split("\\")[0].split("/")[0])
        if not other:
            panel.view.setFocus()

    def cmd_delete(self, permanent: bool) -> None:
        entries = self._selection()
        if not entries:
            return
        if self.active.in_archive:
            QMessageBox.information(
                self, APP_TITLE, t("Borrar adentro de un comprimido no está soportado."))
            return

        to_recycle = (not permanent) and config.get_bool("general", "delete_to_recycle", True)
        what = (f'"{entries[0].name}"' if len(entries) == 1
                else t("{n} elementos", n=len(entries)))
        where = t("a la papelera de reciclaje") if to_recycle else t("DEFINITIVAMENTE")
        ndirs = sum(1 for e in entries if e.is_dir)
        extra = t("\n\n(incluye {n} carpeta(s) con todo su contenido)",
                  n=ndirs) if ndirs else ""
        r = QMessageBox.question(
            self, t("Confirmar borrado"),
            t("¿Borrar {what} {where}?{extra}", what=what, where=where, extra=extra),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r != QMessageBox.Yes:
            return

        worker = DeleteWorker([e.path for e in entries], to_recycle, self)
        count, errors = ProgressDialog(t("Borrando…"), worker, self).run()
        self._after_file_op(count, errors, "Borrar")

    def cmd_properties(self) -> None:
        entries = self._selection()
        if not entries:
            return
        PropertiesDialog(entries, parent=self).exec()

    def cmd_file_space(self) -> None:
        entries = self._selection()
        if not entries:
            return
        result = scan([e.path for e in entries])
        QMessageBox.information(
            self, t("Espacio ocupado"),
            t("{n} elemento(s) seleccionado(s)", n=len(entries)) + "\n\n" +
            t("Archivos: {files}\nCarpetas: {dirs}\nTamaño total: {size} ({bytes} bytes)",
              files=f"{result.files:,}".replace(",", "."),
              dirs=f"{result.dirs:,}".replace(",", "."),
              size=human(result.total_bytes),
              bytes=f"{result.total_bytes:,}".replace(",", ".")))

    def cmd_attributes(self) -> None:
        entries = self._selection()
        if not entries:
            return
        dlg = AttributesDialog([e.path for e in entries], self)
        if dlg.exec() == QDialog.Accepted:
            errors = dlg.apply()
            self.active.reload(restore_cursor=True)
            if errors:
                ErrorListDialog("Cambiar atributos", errors, self).exec()

    def cmd_crc_create(self) -> None:
        entries = self._selection()
        if not entries:
            return
        out = os.path.join(self.active.path, "checksums.sha256")
        text = compute_checksums([e.path for e in entries], self.active.path)
        try:
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError as exc:
            QMessageBox.warning(self, APP_TITLE, t("No se pudo escribir:\n{error}", error=exc))
            return
        self.active.reload(select_name="checksums.sha256")
        self.statusBar().showMessage(t("Checksums escritos en {path}", path=out), 5000)

    def cmd_crc_check(self) -> None:
        e = self.active.current_entry()
        if e is None or e.is_dir:
            return
        ok, bad, missing = verify_checksums(e.path)
        msg = t("Correctos: {ok}\nDistintos: {bad}\nFaltantes: {missing}",
                ok=len(ok), bad=len(bad), missing=len(missing))
        if bad or missing:
            detail = "\n".join([t("DISTINTOS:")] + bad + ["", t("FALTANTES:")] + missing)
            ErrorListDialog(t("Verificar checksums"), [msg, "", detail], self).exec()
        else:
            QMessageBox.information(self, t("Verificar checksums"), msg)

    # --- comandos: comprimidos --------------------------------------------

    def cmd_pack(self) -> None:
        entries = self._selection()
        if not entries:
            return
        base = (entries[0].stem if len(entries) == 1
                else os.path.basename(self.active.path.rstrip("\\/")) or "archivos")
        default = os.path.join(self.other.path, base + ".zip")
        dlg = archive.PackDialog(default, len(entries), self)
        if dlg.exec() != QDialog.Accepted:
            return
        worker = archive.PackWorker(
            [e.path for e in entries], dlg.zip_path, self.active.path,
            dlg.delete_originals, dlg.compress, self)
        count, errors = ProgressDialog(t("Comprimiendo…"), worker, self).run()
        self._after_file_op(count, errors, "Comprimir")

    def cmd_unpack(self) -> None:
        if self.active.in_archive:
            self._unpack_members(self.active.selected_entries())
            return
        entries = [e for e in self._selection() if archive.is_archive(e.path)]
        if not entries:
            self.statusBar().showMessage(t("No hay comprimidos seleccionados."), 3000)
            return
        dest = TextPromptDialog.ask(
            self, t("Descomprimir"), t("Descomprimir en:"), self.other.path)
        if not dest:
            return
        os.makedirs(dest, exist_ok=True)
        worker = archive.UnpackWorker([e.path for e in entries], dest, parent=self)
        count, errors = ProgressDialog(t("Descomprimiendo…"), worker, self).run()
        self._after_file_op(count, errors, "Descomprimir")

    def _unpack_members(self, entries) -> None:
        """Extraer lo seleccionado de adentro de un zip abierto (F5)."""
        if not entries:
            return
        zip_path = self.active.tab.archive_path
        members = []
        for e in entries:
            if e.is_dir:
                import zipfile
                try:
                    with zipfile.ZipFile(zip_path) as zf:
                        members += [n for n in zf.namelist() if n.startswith(e.path)]
                except (OSError, zipfile.BadZipFile):
                    pass
            else:
                members.append(e.path)
        dest = TextPromptDialog.ask(self, t("Extraer"), t("Extraer en:"), self.other.path)
        if not dest:
            return
        os.makedirs(dest, exist_ok=True)
        worker = archive.UnpackWorker([zip_path], dest, members, parent=self)
        count, errors = ProgressDialog(t("Extrayendo…"), worker, self).run()
        self._after_file_op(count, errors, "Extraer")

    def cmd_test_archive(self) -> None:
        entries = [e for e in self._selection() if archive.is_archive(e.path)]
        if not entries:
            self.statusBar().showMessage(t("No hay comprimidos seleccionados."), 3000)
            return
        worker = archive.TestWorker([e.path for e in entries], self)
        count, errors = ProgressDialog(t("Verificando…"), worker, self).run()
        if errors:
            ErrorListDialog("Verificar comprimidos", errors, self).exec()
        else:
            QMessageBox.information(
                self, APP_TITLE, t("{n} comprimido(s) verificado(s), sin errores.", n=count))

    # --- comandos: marcado y comparación -----------------------------------

    def cmd_mark_group(self, mark: bool) -> None:
        e = self.active.current_entry()
        initial = f"*.{e.ext}" if (e and e.ext) else "*.*"
        dlg = SelectGroupDialog(mark, initial, self._pattern_history, self)
        if dlg.exec() != QDialog.Accepted:
            return
        patterns = dlg.patterns()
        if not patterns:
            return
        for p in patterns:
            if p not in self._pattern_history:
                self._pattern_history.insert(0, p)
        del self._pattern_history[20:]
        n = self.active.mark_pattern(patterns, mark, dlg.files_only.isChecked())
        verb = "marcado" if mark else "desmarcado"
        self.statusBar().showMessage(t("{n} elemento(s) {verb}(s).", n=n, verb=t(verb)), 3000)

    def cmd_compare_dirs(self) -> None:
        dlg = CompareOptionsDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        worker = CompareWorker(
            list(self.left.model.entries), list(self.right.model.entries),
            dlg.by_content.isChecked(), dlg.include_dirs.isChecked(), self)
        worker.finished_compare.connect(self._apply_compare)
        self.statusBar().showMessage(t("Comparando…"))
        worker.start()
        self._compare_worker = worker       # mantener viva la referencia

    def _apply_compare(self, lmark: set, rmark: set) -> None:
        self.left.apply_marks(lmark)
        self.right.apply_marks(rmark)
        self.statusBar().showMessage(
            t("Diferencias: {l} a la izquierda, {r} a la derecha.", l=len(lmark), r=len(rmark)), 6000)

    # --- comandos: navegación ----------------------------------------------

    def cmd_history_menu(self) -> None:
        t = self.active.tab
        if not t.history:
            return
        menu = QMenu(self)
        for i, path in enumerate(reversed(t.history[-25:])):
            a = menu.addAction(path)
            a.triggered.connect(lambda _=False, p=path: self.active.set_path(p))
        menu.exec(self.active.mapToGlobal(self.active.path_edit.pos()))

    def cmd_bookmarks(self) -> None:
        dlg = BookmarksDialog(self.active.path, self)
        if dlg.exec() == QDialog.Accepted and dlg.chosen:
            if not self.active.set_path(dlg.chosen):
                QMessageBox.warning(self, APP_TITLE, t("No existe:\n{path}", path=dlg.chosen))

    def cmd_transfer_to_other(self) -> None:
        """Ctrl+← / Ctrl+→: abrir en el otro panel el dir bajo el cursor."""
        e = self.active.current_entry()
        target = e.path if (e and e.is_dir and not e.is_parent) else self.active.path
        self.other.set_path(target)

    def cmd_target_equal_source(self) -> None:
        self.other.set_path(self.active.path)

    def cmd_toggle_sync(self) -> None:
        self._sync_dirs = not getattr(self, "_sync_dirs", False)
        state = "activado" if self._sync_dirs else "desactivado"
        self.statusBar().showMessage(t("Cambio de directorio sincronizado {state}.", state=t(state)), 3000)

    def _sync_other_panel(self) -> None:
        """Reproduce en el otro panel el subdirectorio al que entró el activo."""
        src, dst = self.active, self.other
        name = os.path.basename(src.path.rstrip("\\/"))
        candidate = os.path.join(dst.path, name)
        if name and os.path.isdir(candidate):
            dst.set_path(candidate)

    def cmd_search(self) -> None:
        dlg = SearchDialog(self.active.path, self)
        if dlg.exec() != QDialog.Accepted:
            return
        if dlg.results_to_panel:
            self.active.set_entries_override(dlg.results_to_panel)
            self.statusBar().showMessage(
                t("{n} resultado(s) en el panel. F2 para volver.", n=len(dlg.results_to_panel)), 6000)
        elif dlg.goto_path:
            target = dlg.goto_path
            parent = target if os.path.isdir(target) else os.path.dirname(target)
            self.active.set_path(parent, select_name=os.path.basename(target))

    def cmd_swap_panels(self) -> None:
        lp, rp = self.left.tab.path, self.right.tab.path
        self.left.set_path(rp)
        self.right.set_path(lp)

    def cmd_toggle_orientation(self) -> None:
        new = (Qt.Vertical if self.splitter.orientation() == Qt.Horizontal
               else Qt.Horizontal)
        self.splitter.setOrientation(new)

    def cmd_view_mode(self, brief: bool) -> None:
        for panel in (self.active,):
            panel.model.show_icons = True
            for col in (1, 2, 3, 4):
                panel.view.setColumnHidden(col, brief)

    def cmd_toggle_hidden(self) -> None:
        new = not config.get_bool("general", "show_hidden", False)
        config.set("general", "show_hidden", 1 if new else 0)
        self.act_hidden.setChecked(new)
        self.left.reload(restore_cursor=True)
        self.right.reload(restore_cursor=True)

    # --- comandos: portapapeles --------------------------------------------

    def cmd_clipboard_files(self, move: bool) -> None:
        entries = self._selection()
        if not entries:
            return
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(e.path) for e in entries])
        # El Explorador distingue cortar de copiar con este formato.
        effect = DROPEFFECT_MOVE if move else DROPEFFECT_COPY
        mime.setData(DROPEFFECT_FORMAT,
                     QByteArray(effect.to_bytes(4, "little")))
        QApplication.clipboard().setMimeData(mime)
        verb = "cortado" if move else "copiado"
        self.statusBar().showMessage(t("{n} elemento(s) {verb}(s).", n=len(entries), verb=t(verb)), 3000)

    def cmd_paste(self) -> None:
        mime = QApplication.clipboard().mimeData()
        if not mime.hasUrls():
            self.statusBar().showMessage(t("El portapapeles no tiene archivos."), 3000)
            return
        sources = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
        sources = [s for s in sources if s and os.path.exists(s)]
        if not sources:
            return
        move = False
        if mime.hasFormat(DROPEFFECT_FORMAT):
            data = bytes(mime.data(DROPEFFECT_FORMAT))
            if len(data) >= 4:
                move = int.from_bytes(data[:4], "little") & DROPEFFECT_MOVE != 0
        self._run_transfer(sources, self.active.path, move)

    def cmd_copy_names(self, full: bool) -> None:
        entries = self._selection()
        if not entries:
            return
        text = "\n".join(e.path if full else e.name for e in entries)
        self._to_clipboard_text(text)

    def _to_clipboard_text(self, text: str) -> None:
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage(t("Copiado al portapapeles."), 2000)

    # --- comandos: varios --------------------------------------------------

    def cmd_context_menu(self) -> None:
        entries = self.active.selected_entries()
        menu = QMenu(self)
        if entries:
            menu.addAction("Abrir", lambda: self.run("cm_Return"))
            menu.addAction("Ver (F3)", lambda: self.run("cm_List"))
            menu.addAction("Editar (F4)", lambda: self.run("cm_Edit"))
            menu.addSeparator()
            menu.addAction("Copiar (F5)", lambda: self.run("cm_Copy"))
            menu.addAction("Mover (F6)", lambda: self.run("cm_RenMov"))
            menu.addAction("Renombrar (Shift+F6)", lambda: self.run("cm_RenameOnly"))
            menu.addAction("Borrar (F8)", lambda: self.run("cm_Delete"))
            menu.addSeparator()
            menu.addAction("Copiar al portapapeles", lambda: self.run("cm_CopyToClipboard"))
            menu.addAction("Copiar ruta completa", lambda: self.run("cm_CopyFullNamesToClip"))
            menu.addSeparator()
            menu.addAction("Propiedades", lambda: self.run("cm_Properties"))
            menu.addSeparator()
        menu.addAction("Pegar", lambda: self.run("cm_PasteFromClipboard"))
        menu.addAction("Abrir en el Explorador", lambda: self.run("cm_OpenInExplorer"))
        menu.addAction("Agregar a marcadores",
                       lambda: add_bookmark(os.path.basename(self.active.path)
                                            or self.active.path, self.active.path))
        rect = self.active.view.visualRect(self.active.view.currentIndex())
        menu.exec(self.active.view.viewport().mapToGlobal(rect.bottomLeft()))

    def cmd_open_terminal(self) -> None:
        try:
            platform.open_terminal(self.active.path,
                                   config.get("general", "terminal", ""))
        except OSError as exc:
            QMessageBox.warning(self, APP_TITLE, t("No se pudo abrir la consola:\n{error}", error=exc))

    def cmd_open_explorer(self) -> None:
        e = self.active.current_entry()
        try:
            if e and not e.is_parent and not self.active.in_archive:
                platform.reveal_in_file_manager(e.path)
            else:
                platform.reveal_in_file_manager(self.active.path)
        except OSError as exc:
            QMessageBox.warning(
                self, APP_TITLE, t("No se pudo abrir el explorador:\n{error}", error=exc))

    def cmd_append_to_cmdline(self) -> None:
        e = self.active.current_entry()
        if e is None or e.is_parent:
            return
        line = self.cmdline.currentText()
        sep = "" if (not line or line.endswith(" ")) else " "
        name = e.name if " " not in e.name else f'"{e.name}"'
        self.cmdline.setCurrentText(f"{line}{sep}{name}")
        self.cmdline.setFocus()

    def cmd_set_theme(self, name: str) -> None:
        config.set("general", "theme", name)
        applied = theme.apply(
            QApplication.instance(), name,
            config.get("general", "ui_font_family", "Segoe UI"),
            config.get_int("general", "ui_font_size", 9))
        theme.apply_titlebar(self)
        for panel in (self.left, self.right):
            panel.apply_theme()
        self._set_active(self.active)          # repinta la barra de ruta activa
        for a in self._theme_group.actions():
            a.setChecked(a.data() == name)
        self.statusBar().showMessage(
            t("Tema: {name}", name=name) + (f" → {applied.name}" if name == "auto" else ""), 3000)

    def cmd_toggle_theme(self) -> None:
        """Ctrl+Shift+T. Desde 'auto' salta a lo contrario de lo que se ve."""
        current = config.get("general", "theme", "auto")
        if current == "auto":
            new = "light" if theme.current().dark else "dark"
        else:
            new = "light" if current == "dark" else "dark"
        self.cmd_set_theme(new)

    def cmd_set_language(self, code: str) -> None:
        config.set("general", "language", code)
        applied = i18n.set_language(code)
        self._retranslate()
        self.statusBar().showMessage(
            t("Idioma: {name}", name=i18n.available().get(applied, applied)), 4000)

    def _retranslate(self) -> None:
        """Rehace el texto de la interfaz tras cambiar de idioma.

        El menú se reconstruye entero en vez de recorrer sus acciones: es más
        simple y no deja nada sin traducir. Las ventanas ya abiertas (visor,
        editor) conservan el idioma con el que nacieron.
        """
        self.menuBar().clear()
        self._build_menu()
        for button, key, label in self.fkey_buttons:
            button.setText(f"{key}  {t(label)}")
        self.cmdline.lineEdit().setPlaceholderText(
            t("escribí un comando y Enter — 'cd ruta' cambia el panel activo"))
        for panel in (self.left, self.right):
            panel.retranslate()
        self._update_drive_info()

    def cmd_toggle_recycle(self) -> None:
        new = not config.get_bool("general", "delete_to_recycle", True)
        config.set("general", "delete_to_recycle", 1 if new else 0)
        self.act_recycle.setChecked(new)

    def cmd_choose_editor(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, t("Elegir editor externo"), "", t("Programas (*.exe);;Todos (*)"))
        if path:
            config.set("general", "editor", path)
            config.save()

    def cmd_keyboard_help(self) -> None:
        from .help import keyboard_help

        box = QMessageBox(self)
        box.setWindowTitle(t("Atajos de teclado"))
        box.setTextFormat(Qt.RichText)
        box.setText(keyboard_help())
        box.exec()

    def cmd_about(self) -> None:
        from . import __version__

        QMessageBox.about(
            self, t("Acerca de {app}", app=APP_TITLE),
            f"<h3>{APP_TITLE} {__version__}</h3>"
            f"<p>{t('Gestor de archivos de doble panel.')}</p>"
            f"<p>{t('El modelo de interacción sigue la convención del género '
                    'commander (Norton Commander, 1986) y los nombres de comando '
                    'y atajos siguen la nomenclatura pública de Total Commander. '
                    'La implementación es propia.')}</p>"
            f"<p>Python {sys.version.split()[0]} · PySide6 · {sys.platform}</p>")

    # --- línea de comandos --------------------------------------------------

    def _run_command_line(self) -> None:
        line = self.cmdline.currentText().strip()
        if not line:
            return
        self._remember_command(line)
        self.cmdline.setCurrentText("")

        low = line.lower()
        if low == "cd" or low.startswith("cd "):
            target = line[3:].strip().strip('"') if len(line) > 2 else os.path.expanduser("~")
            if target in ("..", "..\\", "../"):
                self.active.go_parent()
            elif target in ("\\", "/"):
                self.active.go_root()
            else:
                if not os.path.isabs(target):
                    target = os.path.join(self.active.path, target)
                if not self.active.set_path(target):
                    self.statusBar().showMessage(t("No existe: {path}", path=target), 4000)
            self.active.view.setFocus()
            return

        if low in ("exit", "quit"):
            self.close()
            return

        try:
            platform.run_shell_command(line, self.active.path)
            self.statusBar().showMessage(t("Ejecutado: {line}", line=line), 4000)
        except OSError as exc:
            QMessageBox.warning(self, APP_TITLE, t("No se pudo ejecutar:\n{error}", error=exc))
        self.active.view.setFocus()

    def _remember_command(self, line: str) -> None:
        if line in self._cmd_history:
            self._cmd_history.remove(line)
        self._cmd_history.insert(0, line)
        del self._cmd_history[40:]
        self.cmdline.clear()
        self.cmdline.addItems(self._cmd_history)
        self.cmdline.setCurrentText("")

    # --- persistencia -------------------------------------------------------

    def _restore_geometry(self) -> None:
        w = config.get_int("geometry", "width", 0)
        h = config.get_int("geometry", "height", 0)
        if w > 300 and h > 200:
            self.resize(w, h)
        split = config.get_int("geometry", "split", 0)
        if split > 0:
            self.splitter.setSizes([split, max(split, 100)])
        for i, line in enumerate(config.section_items("history")):
            self._cmd_history.append(line[1])
        if self._cmd_history:
            self.cmdline.addItems(self._cmd_history)
            self.cmdline.setCurrentText("")

    def _save_settings(self) -> None:
        config.set("general", "left_path", self.left.path)
        config.set("general", "right_path", self.right.path)
        config.set("geometry", "width", self.width())
        config.set("geometry", "height", self.height())
        config.set("geometry", "split", self.splitter.sizes()[0])
        config.clear_section("history")
        for i, line in enumerate(self._cmd_history[:40]):
            config.set("history", f"h{i:03d}", line)
        config.save()

    def closeEvent(self, event) -> None:
        self.left.save_state()
        self.right.save_state()
        self._save_settings()
        for win in list(self._open_windows):
            win.close()
        event.accept()
