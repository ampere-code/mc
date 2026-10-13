# Marce Commander

Gestor de archivos de doble panel en Python + PySide6 (Qt).
Corre en Windows, Linux y macOS. Interfaz en español e inglés.

El modelo de interacción sigue la convención del género *commander* (Norton
Commander, 1986) y la nomenclatura de comandos y atajos de Total Commander. La
implementación es propia: no contiene código ni recursos de TC. En
[SPEC.md](SPEC.md) está la especificación funcional que se extrajo analizando
`TOTALCMD64.EXE` y de dónde salió cada dato.

## Correr

```cmd
mc.cmd                              :: Windows
mc.cmd C:\proyectos D:\backup       :: rutas inicial izquierda y derecha
```

```sh
python -m mc                        # cualquier sistema
python -m mc ~/proyectos /mnt/backup
```

Requiere Python 3.10+ y `pip install -r requirements.txt`.

### Linux

Qt trae sus propias bibliotecas, pero su plugin gráfico `xcb` se enlaza contra
librerías del sistema que muchas instalaciones mínimas no tienen. Sin ellas MC
arranca y falla con *"could not load the Qt platform plugin xcb"*.

En Debian y Ubuntu:

```sh
sudo apt install python3-venv \
  libgl1 libegl1 libdbus-1-3 libglib2.0-0 libfontconfig1 libfreetype6 \
  libxkbcommon0 libxkbcommon-x11-0 libx11-6 libx11-xcb1 libxcb1 \
  libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
  libxcb-randr0 libxcb-render0 libxcb-render-util0 libxcb-shape0 \
  libxcb-shm0 libxcb-sync1 libxcb-util1 libxcb-xfixes0 libxcb-xkb1

git clone git@github.com:ampere-code/mc.git && cd mc
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m mc
```

Esa lista no está copiada de ningún lado: sale de mirar con `ldd` qué le falta
a `libqxcb.so`, y está verificada en un contenedor Debian. En Fedora o Arch los
paquetes equivalentes existen con otros nombres (`libxcb`, `xcb-util-*`,
`libxkbcommon-x11`), pero ahí no lo probé.

Para encontrar qué falta en cualquier distro:

```sh
ldd "$(python -c 'import PySide6,os;print(os.path.dirname(PySide6.__file__))')"/Qt/plugins/platforms/libqxcb.so | grep 'not found'
QT_DEBUG_PLUGINS=1 python -m mc        # por qué Qt rechaza un plugin
```

En Wayland, Qt usa igual `xcb` sobre XWayland por defecto, que es lo más
probado. Para el plugin nativo: `QT_QPA_PLATFORM=wayland python -m mc`.

### Ejecutable sin instalar nada

```cmd
python build_exe.py
```

Deja en `dist/MarceCommander/` una carpeta que se copia y corre sin Python.
El `.spec` filtra de Qt lo que MC no usa (QML, PDF, el renderer OpenGL por
software, traducciones): sin eso el paquete pesa el doble.

### Pruebas

```sh
python tests/smoke.py
```

Y en Linux, dentro de un contenedor. Hay dos imágenes porque prueban cosas
distintas: la primera corre la lógica con la plataforma `offscreen` de Qt, la
segunda levanta un servidor X virtual para que Qt cargue su plugin `xcb` real,
abra una ventana de verdad y guarde una captura.

```sh
docker build -f tools/Dockerfile.linux-test -t mc-linux-test .
docker run --rm -v "$PWD:/app" mc-linux-test          # 65 comprobaciones

docker build -f tools/Dockerfile.linux-gui -t mc-linux-gui .
docker run --rm -v "$PWD:/app" mc-linux-gui           # ventana real + captura
```

### Icono

```sh
python tools/make_icon.py
```

Lo dibuja vectorialmente a cada tamaño y escribe `mc/resources/icon.ico`.

## Cómo está armado

| Archivo | Qué hace |
|---|---|
| `mc/mainwindow.py` | Ventana, menú, registro de comandos, atajos, línea de comandos |
| `mc/panel.py` | Un panel: pestañas, ruta, historial, marcado, navegación |
| `mc/fsmodel.py` | Listado de directorios y modelo de tabla |
| `mc/ops.py` | Copiar, mover y borrar en hilos, con progreso y papelera |
| `mc/archive.py` | ZIP: comprimir, descomprimir, navegar adentro, verificar |
| `mc/search.py` | Buscar archivos por nombre y contenido |
| `mc/compare.py` | Comparar paneles y checksums SHA-256 |
| `mc/viewer.py` | Visor F3 (texto / hex / imagen) y vista rápida |
| `mc/editor.py` | Editor F4 |
| `mc/dialogs.py` | Diálogos chicos |
| `mc/bookmarks.py` | Marcadores de directorios |
| `mc/theme.py` | Temas claro y oscuro: paleta, hoja QSS y barra de título |
| `mc/platform.py` | Todo lo que cambia entre Windows, Linux y macOS |
| `mc/i18n.py` | Catálogo de traducción y selección de idioma |
| `mc/help.py` | Tabla de atajos para F1 |
| `mc/config.py` | Lectura y escritura del `mc.ini` |

El centro de todo es `MainWindow.commands`: un diccionario que va del nombre
`cm_*` a la función que lo ejecuta. El menú, la barra de teclas de función y los
atajos de teclado son tres formas de disparar la misma entrada, así que agregar
un comando nuevo es agregar una fila ahí y, si querés, una línea en
`_install_shortcuts`.

## Lo que hace

**Paneles.** Dos paneles con pestañas independientes (`Ctrl+T` / `Ctrl+W`), cada
una con su ruta, marcas, cursor, orden e historial propios. Pestañas bloqueables.
El panel con foco es el **origen** y se ve resaltado; el otro es el **destino**.
`Ctrl+U` los intercambia, `Alt+Enter` muestra propiedades.

**Navegación.** `Tab` cambia de panel, `Backspace` sube, `Ctrl+\` va a la raíz,
`Alt+←/→` es el historial, `Ctrl+←/→` abre el directorio del cursor en el otro
panel, `Ctrl+D` los marcadores. Escribir letras sobre la lista salta al archivo
que empiece así.

**Operaciones.** F5 copiar, F6 mover, F7 crear dir, F8 borrar. Corren en un hilo
aparte con barra de progreso cancelable y resolución de conflictos
(sobreescribir / omitir / todos / sólo los más nuevos). Un solo archivo con un
destino que no es un directorio existente copia y renombra en un paso. El
borrado va a la papelera por defecto (`Shift+F8` es definitivo).

**Selección.** `Insert` marca y baja, `Espacio` marca y calcula el tamaño de la
carpeta, `Num +/-` marca y desmarca por patrón glob, `Num *` invierte. Si no hay
nada marcado, las operaciones usan el archivo bajo el cursor.

**Comprimidos.** `Alt+F5` comprime a ZIP, `Alt+F6` descomprime, `Alt+Shift+F9`
verifica integridad. Un ZIP se abre con Enter como si fuera una carpeta: se
navega adentro, se ven archivos con F3 y se extrae con F5. La extracción rechaza
rutas que escapen del destino (*zip-slip*).

**Buscar** (`Alt+F7`) por nombre y por contenido, con regex opcional. Los
resultados se pueden volcar en el panel como vista de rama.

**Comparar** (`Shift+F2`) marca en cada panel lo que falta del otro lado y lo que
es más nuevo; lo idéntico queda sin marcar. Con la opción por contenido compara
SHA-256 en vez de fecha y tamaño.

**Portapapeles** interoperable con el Explorador: `Ctrl+C` / `Ctrl+X` / `Ctrl+V`
usan el formato `CF_HDROP` con el `Preferred DropEffect` correcto.

**Línea de comandos** abajo: ejecuta en el directorio del panel activo, y `cd`
mueve el panel. `Ctrl+Enter` agrega el nombre del archivo bajo el cursor.

`F1` muestra la lista completa de atajos.

## Apariencia

Tema **oscuro y claro**, en *Configuración → Apariencia*. Por defecto está en
`auto`: lee `AppsUseLightTheme` del registro y sigue lo que tenga Windows.
`Ctrl+Shift+T` alterna entre claro y oscuro, y el cambio se aplica en caliente,
sin reiniciar.

Un tema (`mc/theme.py`) es un juego de tokens de color del que salen dos cosas:
una `QPalette`, que usan los widgets que dibuja el estilo y el delegado de la
tabla, y una hoja QSS para todo lo demás. Al salir las dos de la misma fuente no
se pueden desalinear. El estilo base es Fusion a propósito: el estilo nativo de
Windows ignora buena parte de la paleta y dejaría el modo oscuro a medias.

Los colores semánticos de las listas —archivos marcados, carpetas, ocultos—
salen del tema activo, así que mantienen el contraste en los dos modos. Un
detalle que importa en un commander: Qt descarta el color del modelo cuando la
fila está seleccionada, con lo cual un archivo marcado dejaba de verse marcado
justo cuando el cursor estaba encima; `EntryDelegate` reinyecta ese color.

La barra de título nativa se pinta de oscuro con `DWMWA_USE_IMMERSIVE_DARK_MODE`.
Ese atributo sólo sabe *forzar* el modo oscuro: con Windows en tema oscuro
(`SystemUsesLightTheme=0`), el tema claro de MC convive con una barra de título
oscura y no hay API pública para evitarlo.

## Idiomas

Español e inglés, en *Configuración → Idioma*. Por defecto `auto`: toma el
idioma del sistema. El cambio se aplica en caliente — el menú se reconstruye
entero y los paneles se refrescan; las ventanas ya abiertas (visor, editor)
conservan el idioma con el que nacieron.

Las claves del catálogo (`mc/i18n.py`) son las cadenas **en español**, porque el
idioma fuente del proyecto es el español. Es la regla de gettext —la clave es el
idioma del código fuente—, sólo que acá ese idioma no es el inglés. Una clave
que falte devuelve el texto tal cual, así que una traducción incompleta degrada
a español en vez de romper.

Para agregar un idioma: sumá un código a `LANGUAGES`, un diccionario a
`CATALOGS` y listo. `tests/smoke.py` recorre el AST de todos los módulos
buscando las llamadas `t("…")` y falla si alguna clave no está en el catálogo,
así que las traducciones no se quedan atrás sin que nadie se entere.

## Multiplataforma

Todo lo que depende del sistema vive en `mc/platform.py`: dónde va la
configuración, las unidades o puntos de montaje, abrir archivos y consolas, los
atributos, la papelera y la preferencia de tema del escritorio. El resto del
código no importa `ctypes` ni mira `sys.platform`.

La razón de concentrarlo no es sólo prolijidad: `ctypes.wintypes` **no se puede
importar** fuera de Windows (define `VARIANT_BOOL` con `_type_ = "v"`, un código
que sólo existe en la build de Windows de `_ctypes`), así que un
`from ctypes import wintypes` a nivel de módulo rompe la aplicación entera al
arrancar en Linux o Mac. Ahí vive dentro de las funciones que lo necesitan.

Diferencias por sistema:

| | Windows | Linux | macOS |
|---|---|---|---|
| Configuración | `%APPDATA%\MarceCommander` | `$XDG_CONFIG_HOME/marcecommander` | `~/Library/Application Support` |
| Barra de unidades | letras `C:` `D:` | `/`, `~`, `/media`, `/mnt` | `/`, `~`, `/Volumes` |
| Papelera | `SHFileOperation` | spec freedesktop, con `.trashinfo` | Finder vía `osascript` |
| Columna *Atr* | `r a h s` | permisos `rwx` | permisos `rwx` |
| Abrir archivo | `os.startfile` | `xdg-open` | `open` |
| Mostrar en carpeta | `explorer /select,` | nautilus / dolphin / nemo / thunar | `open -R` |

La papelera de Linux está implementada a mano siguiendo la especificación
freedesktop.org en vez de depender de `gio trash`, que no está en todos los
escritorios; el `.trashinfo` que deja es lo que permite restaurar después.

## Lo que no hace

FTP, plugins (WCX/WFX/WLX), árbol de directorios separado, miniaturas, columnas
personalizadas, sincronización de carpetas, y comprimidos que no sean ZIP (RAR,
7z, TAR). En `SPEC.md` está el detalle de qué categorías de comandos de TC se
cubrieron y cuáles no.

**Linux** está verificado con ventana real: `tools/Dockerfile.linux-gui` levanta
un servidor X virtual, Qt carga su plugin `xcb` y MC abre, lista directorios y
renderiza bien, con los permisos `rwx` en la columna *Atr* y los puntos de
montaje en la barra de unidades. Más las 65 comprobaciones de lógica.

**macOS no se probó en absoluto** — no tengo una máquina a mano. El código
tiene sus ramas (`Library/Application Support`, `/Volumes`, `open`, `open -R`,
Finder para la papelera), pero están escritas, no verificadas.

Lo que más chance tiene de necesitar ajustes en cualquiera de los dos es el
menú contextual y la detección de puntos de montaje en escritorios concretos.

## Configuración

En texto plano, en el directorio de configuración del sistema (ver la tabla de
arriba). Lo más útil:

| Clave | Por defecto | Qué hace |
|---|---|---|
| `theme` | `auto` | `auto`, `dark` o `light` |
| `language` | `auto` | `auto`, `es` o `en` |
| `ui_font_family`, `ui_font_size` | `Segoe UI`, `9` | Fuente de menús, botones y diálogos |
| `editor` | `interno` | Editor de F4; poné una ruta a un .exe para usar otro |
| `terminal` | según el sistema | Consola que abre `Ctrl+Shift+Enter` |
| `delete_to_recycle` | `1` | F8 a la papelera en vez de borrar definitivo |
| `show_hidden` | `0` | Mostrar archivos ocultos y de sistema |
| `sort_dirs_first` | `1` | Carpetas antes que archivos |
| `font_family`, `font_size` | según el sistema | Fuente monoespaciada de las listas |

Las rutas de los paneles, el tamaño de la ventana y la posición del divisor se
guardan al salir.
