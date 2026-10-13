"""Traducción de la interfaz. Por ahora español e inglés.

Las claves del catálogo son las cadenas en español, porque el idioma fuente del
proyecto es el español: el código y los comentarios están escritos así. Es la
misma regla de gettext —la clave es el idioma del código fuente—, sólo que acá
ese idioma no es el inglés.

Una clave que falte devuelve el texto tal cual, así que una traducción
incompleta degrada a español en lugar de romper o mostrar una clave cruda.

Uso:

    from .i18n import t

    t("Copiar")
    t("{n} archivo(s)", n=3)

Las cadenas con partes variables usan marcadores con nombre, no posicionales,
para que cada idioma pueda ordenarlos como le convenga.
"""

from __future__ import annotations

LANGUAGES = {"es": "Español", "en": "English"}
DEFAULT = "es"

_current = DEFAULT

# Catálogo inglés: {texto en español: texto en inglés}
EN: dict[str, str] = {
    # --- menú principal ---
    "&Archivos": "&Files",
    "&Marcar": "&Mark",
    "&Comandos": "&Commands",
    "&Ver": "&View",
    "Config&uración": "&Configuration",

    # --- archivos ---
    "&Editar": "&Edit",
    "&Copiar": "&Copy",
    "&Mover / Renombrar": "&Move / Rename",
    "Renombrar en el &sitio": "Rename in &place",
    "Crear &directorio": "Create &directory",
    "&Borrar": "&Delete",
    "C&omprimir…": "C&ompress…",
    "&Descomprimir…": "&Extract…",
    "&Verificar comprimidos": "&Test archives",
    "Cambiar &atributos…": "Change &attributes…",
    "Cambiar permisos": "Change permissions",
    "&Propiedades": "&Properties",
    "Calcular espacio ocupado": "Calculate occupied space",
    "Crear &checksums SHA-256": "Create SHA-256 &checksums",
    "Verificar checksums": "Verify checksums",
    "&Salir": "E&xit",

    # --- marcar ---
    "&Seleccionar grupo…": "&Select group…",
    "&Deseleccionar grupo…": "&Unselect group…",
    "&Invertir selección": "&Invert selection",
    "Seleccionar &todo": "Select &all",
    "Deseleccionar todo": "Unselect all",
    "Seleccionar la misma e&xtensión": "Select same e&xtension",
    "Deseleccionar la misma extensión": "Unselect same extension",
    "&Comparar listas de archivos…": "&Compare file lists…",

    # --- comandos ---
    "&Buscar archivos…": "&Search files…",
    "&Marcadores de directorios…": "Directory &hotlist…",
    "&Historial de directorios…": "Directory &history…",
    "&Intercambiar paneles": "S&wap panels",
    "El mismo directorio en el otro panel": "Target = source directory",
    "Cambio de directorio &sincronizado": "&Synchronous directory change",
    "&Nueva pestaña": "&New tab",
    "&Cerrar pestaña": "&Close tab",
    "&Bloquear pestaña": "&Lock tab",
    "&Abrir una consola acá": "Open a &terminal here",
    "Abrir en el &Explorador": "Open in &file manager",
    "Vista &rápida": "&Quick view",
    "Vista de ra&ma": "&Branch view",

    # --- ver ---
    "&Releer panel": "&Reread panel",
    "&Ordenar por": "S&ort by",
    "&Nombre": "&Name",
    "&Extensión": "&Extension",
    "&Fecha": "&Date",
    "&Tamaño": "&Size",
    "&Sin ordenar": "&Unsorted",
    "Mostrar archivos &ocultos": "Show &hidden files",
    "Paneles &verticales": "&Vertical panels",

    # --- configuración ---
    "&Apariencia": "&Appearance",
    "&Automático (según el sistema)": "&Automatic (follow system)",
    "&Oscuro": "&Dark",
    "&Claro": "&Light",
    "Alternar claro / oscuro": "Toggle light / dark",
    "&Barra de unidades": "&Drive bar",
    "Una en cada &panel": "One per &panel",
    "Una &sola arriba": "A &single one on top",
    "&Ocultarla": "&Hide it",
    "&Idioma": "&Language",
    "Borrar a la &papelera de reciclaje": "Delete to &recycle bin",
    "Usar el menú contextual de &Windows": "Use the &Windows context menu",
    "Muestra el menú del Explorador con todas las extensiones instaladas":
        "Shows the Explorer menu with every installed shell extension",
    "Elegir &editor externo…": "Choose external &editor…",
    "Guardar la configuración &ahora": "&Save configuration now",
    "&Atajos de teclado": "&Keyboard shortcuts",
    "&Acerca de": "&About",

    # --- barra de teclas de función ---
    "Ver": "View",
    "Editar": "Edit",
    "Copiar": "Copy",
    "Mover": "Move",
    "Crear dir": "New dir",
    "Borrar": "Delete",
    "Comprimir": "Pack",
    "Buscar": "Search",

    # --- columnas ---
    "Nombre": "Name",
    "Ext": "Ext",
    "Tamaño": "Size",
    "Fecha": "Date",
    "Atr": "Attr",

    # --- estado de los paneles ---
    "{n} archivo(s), {d} carpeta(s), {size}":
        "{n} file(s), {d} folder(s), {size}",
    "{m} de {n} archivo(s) marcados, {msize} de {size}":
        "{m} of {n} file(s) selected, {msize} of {size}",
    "Buscar: {text}": "Search: {text}",
    "Buscar: {text}   (sin coincidencias)": "Search: {text}   (no match)",
    "Vista rápida": "Quick view",
    "No se pudo leer: {error}": "Could not read: {error}",
    "→ {target}": "→ {target}",

    # --- menú contextual propio (el de respaldo) ---
    "Ver (F3)": "View (F3)",
    "Editar (F4)": "Edit (F4)",
    "Copiar (F5)": "Copy (F5)",
    "Mover (F6)": "Move (F6)",
    "Renombrar (Shift+F6)": "Rename (Shift+F6)",
    "Borrar (F8)": "Delete (F8)",
    "Abrir en el Explorador": "Open in Explorer",

    # --- diálogos generales ---
    "Confirmar borrado": "Confirm delete",
    "Crear directorio": "Create directory",
    "Nombre del directorio nuevo en:\n{path}": "Name of the new directory in:\n{path}",
    "Renombrar": "Rename",
    "Nombre nuevo:": "New name:",
    "Copiar en el mismo directorio": "Copy in the same directory",
    "Nombre de la copia:": "Name of the copy:",
    "Nuevo archivo de texto": "New text file",
    "Nombre del archivo:": "File name:",
    "nuevo.txt": "new.txt",
    "Descomprimir": "Extract",
    "Descomprimir en:": "Extract to:",
    "Extraer": "Extract",
    "Extraer en:": "Extract to:",
    "Propiedades": "Properties",
    "Espacio ocupado": "Occupied space",
    "Aceptar": "OK",
    "Cancelar": "Cancel",

    # --- copiar / mover ---
    "Mover/Renombrar": "Move/Rename",
    "{verb} {what} a:": "{verb} {what} to:",
    "Podés escribir una ruta nueva, o una ruta con nombre de archivo "
    "para renombrar al vuelo.":
        "You can type a new path, or a path with a file name to rename "
        "on the fly.",
    "Copiando…": "Copying…",
    "Moviendo…": "Moving…",
    "Borrando…": "Deleting…",
    "Comprimiendo…": "Compressing…",
    "Descomprimiendo…": "Extracting…",
    "Extrayendo…": "Extracting…",
    "Verificando…": "Testing…",
    "Preparando…": "Preparing…",
    "Cancelando…": "Cancelling…",
    "{done} de {total}": "{done} of {total}",
    "{n} elemento(s) procesado(s).": "{n} item(s) processed.",
    "{n} elemento(s) seleccionado(s)": "{n} item(s) selected",
    "No hay nada seleccionado.": "Nothing is selected.",

    # --- conflictos ---
    "El archivo ya existe": "File already exists",
    "El destino ya existe:": "The destination already exists:",
    "&Sobreescribir": "&Overwrite",
    "&Omitir": "&Skip",
    "Sobreescribir &todos": "Overwrite &all",
    "Omitir t&odos": "Skip a&ll",
    "Sólo los más &nuevos": "Only &newer",
    "Origen:  {a}\nDestino: {b}": "Source: {a}\nTarget: {b}",

    # --- borrado ---
    "¿Borrar {what} {where}?{extra}": "Delete {what} {where}?{extra}",
    "a la papelera de reciclaje": "to the recycle bin",
    "DEFINITIVAMENTE": "PERMANENTLY",
    "\n\n(incluye {n} carpeta(s) con todo su contenido)":
        "\n\n(includes {n} folder(s) with all their contents)",
    "{n} elementos": "{n} items",

    # --- selección por patrón ---
    "Seleccionar grupo": "Select group",
    "Deseleccionar grupo": "Unselect group",
    "Patrón (se admiten varios separados por ';' — por ejemplo  *.txt;*.md)":
        "Pattern (several allowed, separated by ';' — e.g.  *.txt;*.md)",
    "Sólo archivos (no carpetas)": "Files only (no folders)",
    "{n} elemento(s) {verb}(s).": "{n} item(s) {verb}.",
    "marcado": "selected",
    "desmarcado": "unselected",

    # --- atributos ---
    "Cambiar atributos": "Change attributes",
    "Sólo lectura": "Read only",
    "Archivo": "Archive",
    "Oculto": "Hidden",
    "Sistema": "System",
    "Leer": "Read",
    "Escribir": "Write",
    "Ejecutar": "Execute",
    "Dueño": "Owner",
    "Grupo": "Group",
    "Otros": "Others",
    "Los casilleros en estado intermedio dejan el valor como está.":
        "Checkboxes in the intermediate state leave the value unchanged.",

    # --- comprimidos ---
    "Comprimir archivos": "Pack files",
    "Comprimir {n} elemento(s) en:": "Pack {n} item(s) into:",
    "Comprimido (deflate)": "Compressed (deflate)",
    "Sólo almacenar (sin comprimir)": "Store only (no compression)",
    "Borrar los originales al terminar": "Delete originals when done",
    "No hay comprimidos seleccionados.": "No archives selected.",
    "{n} comprimido(s) verificado(s), sin errores.":
        "{n} archive(s) tested, no errors.",
    "Verificar comprimidos": "Test archives",
    "Mover desde adentro de un comprimido no está soportado.":
        "Moving from inside an archive is not supported.",
    "Borrar adentro de un comprimido no está soportado.":
        "Deleting inside an archive is not supported.",

    # --- comparar ---
    "Comparar listas de archivos": "Compare file lists",
    "Quedan marcados los archivos que faltan del otro lado y los que son\n"
    "más nuevos. Los idénticos quedan sin marcar.":
        "Files missing on the other side and newer ones get selected.\n"
        "Identical files are left unselected.",
    "Comparar por contenido (SHA-256, más lento)":
        "Compare by content (SHA-256, slower)",
    "Marcar también las carpetas que falten": "Also select missing folders",
    "Comparar": "Compare",
    "Comparando…": "Comparing…",
    "Diferencias: {l} a la izquierda, {r} a la derecha.":
        "Differences: {l} on the left, {r} on the right.",

    # --- buscar ---
    "Buscar archivos": "Search files",
    "Buscar archivos:": "Search for:",
    "Que contengan el texto:": "Containing text:",
    "Buscar en:": "Search in:",
    "Incluir subdirectorios": "Include subdirectories",
    "Distinguir mayúsculas": "Case sensitive",
    "El texto es una expresión regular": "Text is a regular expression",
    "&Buscar": "&Search",
    "&Detener": "&Stop",
    "&Enviar al panel": "&Feed to panel",
    "&Ir al archivo": "&Go to file",
    "Cerrar": "Close",
    "Listo.": "Ready.",
    "Buscando en: {path}": "Searching in: {path}",
    "{n} resultado(s){suffix}.": "{n} result(s){suffix}.",
    " (detenida)": " (stopped)",
    "No existe el directorio: {path}": "Directory does not exist: {path}",
    "{n} resultado(s) en el panel. F2 para volver.":
        "{n} result(s) in the panel. F2 to go back.",

    # --- marcadores ---
    "Marcadores de directorios": "Directory hotlist",
    "&Agregar el directorio actual": "&Add current directory",
    "&Renombrar": "&Rename",
    "&Quitar": "&Remove",
    "Ir": "Go",
    "Agregar marcador": "Add bookmark",
    "Nombre del marcador:": "Bookmark name:",
    "Renombrar marcador": "Rename bookmark",
    "Agregar a marcadores": "Add to hotlist",

    # --- visor y editor ---
    "Ver — {name}": "View — {name}",
    "Editar — {name}": "Edit — {name}",
    "&Texto": "&Text",
    "&Hexadecimal": "&Hex",
    "&Imagen": "&Image",
    "&Ajustar líneas": "&Wrap lines",
    "&Buscar…": "&Find…",
    "Buscar &siguiente": "Find &next",
    "&Reemplazar…": "&Replace…",
    "&Cerrar": "&Close",
    "&Guardar": "&Save",
    "Guardar &como…": "Save &as…",
    "&Deshacer": "&Undo",
    "&Rehacer": "&Redo",
    "Texto a buscar:": "Text to find:",
    "Buscar:": "Find:",
    "Reemplazar por:": "Replace with:",
    "Reemplazar todo": "Replace all",
    "Reemplazar": "Replace",
    "{n} reemplazo(s)": "{n} replacement(s)",
    "No se encontró «{text}»": "«{text}» not found",
    "Volví al principio del archivo": "Wrapped to the start of the file",
    "Guardado": "Saved",
    "Línea {line}, columna {col}  —  {enc}": "Line {line}, column {col}  —  {enc}",
    "Texto {enc}  —  {lines} líneas, {bytes} bytes{extra}":
        "Text {enc}  —  {lines} lines, {bytes} bytes{extra}",
    "Hexadecimal  —  {bytes} bytes{extra}": "Hex  —  {bytes} bytes{extra}",
    "Imagen  {w}×{h}  —  {bytes} bytes": "Image  {w}×{h}  —  {bytes} bytes",
    "  (truncado)": "  (truncated)",
    "No es una imagen que se pueda mostrar": "Not a displayable image",
    "«{name}» tiene cambios sin guardar.\n¿Guardar?":
        "«{name}» has unsaved changes.\nSave?",
    "No se pudo abrir el archivo:\n{error}": "Could not open the file:\n{error}",
    "No se pudo guardar:\n{error}": "Could not save:\n{error}",
    "No se pudo abrir:\n{error}": "Could not open:\n{error}",
    "No se pudo crear:\n{error}": "Could not create:\n{error}",
    "No se pudo renombrar:\n{error}": "Could not rename:\n{error}",
    "No se pudo escribir:\n{error}": "Could not write:\n{error}",
    "No se pudo ejecutar:\n{error}": "Could not run:\n{error}",
    "No se pudo abrir la consola:\n{error}": "Could not open the terminal:\n{error}",
    "No se pudo abrir el explorador:\n{error}":
        "Could not open the file manager:\n{error}",
    "No se pudo extraer:\n{error}": "Could not extract:\n{error}",
    "Visor": "Viewer",
    "Editor": "Editor",

    # --- varios ---
    "Abrir": "Open",
    "Pegar": "Paste",
    "Copiar al portapapeles": "Copy to clipboard",
    "Copiar ruta completa": "Copy full path",
    "Copiado al portapapeles.": "Copied to clipboard.",
    "El portapapeles no tiene archivos.": "The clipboard has no files.",
    "cortado": "cut",
    "copiado": "copied",
    "Ya existe:\n{path}": "Already exists:\n{path}",
    "Ya existe un elemento con ese nombre.": "An item with that name already exists.",
    "El directorio no existe:\n{path}\n\n¿Crearlo?":
        "The directory does not exist:\n{path}\n\nCreate it?",
    "No existe el directorio:\n{path}": "The directory does not exist:\n{path}",
    "No existe:\n{path}": "Does not exist:\n{path}",
    "No se puede acceder a {path}": "Cannot access {path}",
    "No existe: {path}": "Does not exist: {path}",
    "Ejecutado: {line}": "Ran: {line}",
    "escribí un comando y Enter — 'cd ruta' cambia el panel activo":
        "type a command and press Enter — 'cd path' changes the active panel",
    "{free} libres de {total}": "{free} free of {total}",
    "Comando no implementado: {name}": "Command not implemented: {name}",
    "Error en {name}:\n{error}": "Error in {name}:\n{error}",
    "Configuración guardada.": "Configuration saved.",
    "Tema: {name}": "Theme: {name}",
    "Idioma: {name}": "Language: {name}",
    "Cambio de directorio sincronizado {state}.":
        "Synchronous directory change {state}.",
    "activado": "on",
    "desactivado": "off",
    "Elegir editor externo": "Choose external editor",
    "Programas (*.exe);;Todos (*)": "Programs (*.exe);;All files (*)",
    "Guardar como": "Save as",
    "La operación terminó con {n} error(es):":
        "The operation finished with {n} error(s):",
    "Archivos: {files}\nCarpetas: {dirs}\nTamaño total: {size} ({bytes} bytes)":
        "Files: {files}\nFolders: {dirs}\nTotal size: {size} ({bytes} bytes)",
    "Checksums escritos en {path}": "Checksums written to {path}",
    "Correctos: {ok}\nDistintos: {bad}\nFaltantes: {missing}":
        "Correct: {ok}\nDifferent: {bad}\nMissing: {missing}",
    "DISTINTOS:": "DIFFERENT:",
    "FALTANTES:": "MISSING:",
    "Atajos de teclado": "Keyboard shortcuts",
    "Acerca de {app}": "About {app}",
    "Carpeta": "Folder",
    "Archivo {ext}": "{ext} file",
    "Ubicación:": "Location:",
    "Tipo:": "Type:",
    "Modificado:": "Modified:",
    "Creado:": "Created:",
    "Accedido:": "Accessed:",
    "Atributos:": "Attributes:",
    "Selección:": "Selection:",
    "Tamaño total:": "Total size:",
    "Tamaño:": "Size:",
    "Nombre:": "Name:",
    "{files} archivo(s), {dirs} carpeta(s)": "{files} file(s), {dirs} folder(s)",
    "El idioma se aplica a los menús al instante; las ventanas ya abiertas "
    "conservan el idioma anterior.":
        "The language applies to menus immediately; windows that are already "
        "open keep the previous language.",
    "Gestor de archivos de doble panel.": "Dual-pane file manager.",
    "El modelo de interacción sigue la convención del género commander "
    "(Norton Commander, 1986) y los nombres de comando y atajos siguen la "
    "nomenclatura pública de Total Commander. La implementación es propia.":
        "The interaction model follows the commander genre convention "
        "(Norton Commander, 1986), and the command names and shortcuts follow "
        "Total Commander's public naming. The implementation is original.",

    # --- ayuda de teclado (help.py) ---
    "Teclas de función": "Function keys",
    "Alt": "Alt",
    "Vista y orden": "View and sorting",
    "Navegación": "Navigation",
    "Selección": "Selection",
    "Portapapeles y consola": "Clipboard and terminal",
    "Esta ayuda": "This help",
    "Releer el panel": "Reread the panel",
    "Mover / renombrar": "Move / rename",
    "Comparar listas": "Compare lists",
    "Copiar en el mismo dir": "Copy in the same dir",
    "Renombrar en el sitio": "Rename in place",
    "Crear dir en el otro panel": "Create dir in the other panel",
    "Borrar definitivo": "Delete permanently",
    "Menú contextual": "Context menu",
    "Minimizar": "Minimize",
    "Unidad izq. / der.": "Left / right drive",
    "Atrás / adelante": "Back / forward",
    "Historial de directorios": "Directory history",
    "Ir a la pestaña N": "Go to tab N",
    "Editar la ruta": "Edit the path",
    "Vista breve": "Brief view",
    "Vista detallada": "Full view",
    "Ordenar por nombre": "Sort by name",
    "Por extensión": "By extension",
    "Por fecha": "By date",
    "Por tamaño": "By size",
    "Sin ordenar": "Unsorted",
    "Mostrar ocultos": "Show hidden",
    "Cambiar de panel": "Switch panel",
    "Directorio padre": "Parent directory",
    "Entrar / abrir zip": "Enter / open zip",
    "Ir a la raíz": "Go to root",
    "Abrir en el otro panel": "Open in the other panel",
    "Intercambiar paneles": "Swap panels",
    "Marcadores": "Hotlist",
    "Vista de rama": "Branch view",
    "Nueva pestaña": "New tab",
    "Cerrar pestaña": "Close tab",
    "Pestaña siguiente": "Next tab",
    "Pestaña anterior": "Previous tab",
    "Marcar y bajar": "Select and move down",
    "Marcar (calcula el tamaño de la carpeta)":
        "Select (computes the folder size)",
    "Marcar por patrón": "Select by pattern",
    "Desmarcar por patrón": "Unselect by pattern",
    "Invertir selección": "Invert selection",
    "Limpiar selección": "Clear selection",
    "Marcar todo": "Select all",
    "Desmarcar todo": "Unselect all",
    "Misma extensión": "Same extension",
    "Copiar / cortar / pegar": "Copy / cut / paste",
    "Copiar rutas completas": "Copy full paths",
    "Copiar la ruta del panel": "Copy the panel path",
    "Foco en la línea de comandos": "Focus the command line",
    "Agregar el nombre a la línea": "Append the name to the line",
    "Abrir consola acá": "Open a terminal here",
    "Escribir letras sobre la lista salta al archivo que empiece así.":
        "Typing letters over the list jumps to the file starting with them.",
}

CATALOGS = {"en": EN}


def available() -> dict[str, str]:
    return dict(LANGUAGES)


def current() -> str:
    return _current


def set_language(code: str) -> str:
    """Fija el idioma. 'auto' lo toma del sistema. Devuelve el código aplicado."""
    global _current
    _current = resolve(code)
    return _current


def resolve(code: str) -> str:
    if code in LANGUAGES:
        return code
    if code == "auto":
        return detect()
    return DEFAULT


def detect() -> str:
    """Idioma del sistema, si lo tenemos; si no, español."""
    try:
        from PySide6.QtCore import QLocale

        name = QLocale.system().name()          # p. ej. 'es_AR', 'en_US'
    except Exception:
        return DEFAULT
    code = name.split("_")[0].lower()
    return code if code in LANGUAGES else DEFAULT


def t(text: str, **kwargs) -> str:
    """Traduce y formatea. Una clave ausente devuelve el texto original."""
    catalog = CATALOGS.get(_current)
    out = catalog.get(text, text) if catalog else text
    if kwargs:
        try:
            return out.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            # Una traducción con marcadores mal escritos no debe tumbar la app.
            return text.format(**kwargs)
    return out
