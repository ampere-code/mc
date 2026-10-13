# Marce Commander — plan de construcción

Qué falta y en qué orden conviene hacerlo. La v1 cubre el núcleo del género
commander; lo que queda es casi todo periferia, pero no toda la periferia vale
lo mismo. Este documento ordena por **cuánto cambia el uso diario dividido por
lo que cuesta**, no por categoría de Total Commander.

Estado actual: 90 comandos `cm_*`, 16 módulos, ~6.100 líneas. Verificado en
Windows y Linux; macOS sin probar.

## Cómo leer las etapas

Cada etapa dice qué hace, qué archivos toca y qué decisiones hay que tomar
antes de escribir código. El tamaño es relativo entre etapas, no una promesa de
horas:

| Tamaño | Qué significa |
|---|---|
| **S** | Una sesión. Un diálogo nuevo o un módulo chico, sin tocar lo existente. |
| **M** | Varias sesiones. Módulo nuevo más cambios en los que ya están. |
| **L** | Cambia una decisión de diseño de la v1. Mirar bien antes de empezar. |

---

## Etapa 1 — Diálogo de configuración · S

El hueco más barato de tapar. La plomería ya existe: `config.py` tiene el ini
con `DEFAULTS`, `get/set/save`, y el cambio de tema e idioma en caliente ya
funciona desde el menú. Lo que no hay es una ventana.

Hoy estas siete claves sólo se cambian editando el ini a mano:

```
font_family, font_size            fuente de las listas
ui_font_family, ui_font_size      fuente de la interfaz
confirm_overwrite                 pedir confirmación al sobreescribir
sort_dirs_first                   carpetas antes que archivos
terminal                          qué consola abre Ctrl+Shift+Enter
```

**Qué construir.** Un `QDialog` con pestañas en un módulo nuevo `mc/settings.py`,
y un comando `cm_Config` en el menú Configuración:

- **General** — papelera, confirmar sobreescritura, carpetas primero, mostrar
  ocultos, terminal.
- **Apariencia** — tema, las dos fuentes con su `QFontComboBox` y el cuerpo.
- **Editor** — interno o ruta externa (absorbe el `cm_ChooseEditor` que ya está).
- **Idioma** — auto / es / en.

**Cómo encaja.** El diálogo lee y escribe contra `config`, y al aceptar emite
los mismos efectos que ya disparan `cmd_set_theme` y `cmd_set_language`. Las
fuentes necesitan un camino de aplicación en caliente que hoy no existe: hay
que releer `font_family` en `Panel` y `ui_font_family` en la aplicación sin
reiniciar. Es el único trabajo real de la etapa.

**Decisión pendiente.** Aceptar/Cancelar contra aplicar al instante. El resto de
la aplicación cambia en caliente (tema, idioma), así que lo coherente es
aplicar al instante y que el botón sea sólo Cerrar.

Los menús existentes se quedan: cambiar el tema no debería costar abrir un
diálogo.

---

## Etapa 2 — Más formatos de comprimidos · M

`Alt+F5` sobre un `.rar` hoy no hace nada útil. Es la ausencia más visible de
todas, porque rompe una expectativa que el resto de la aplicación crea.

Hoy `archive.py` usa `zipfile` directo en siete lugares: `list_zip`,
`extract_one`, `PackWorker`, `UnpackWorker`, `TestWorker`. Y `ARCHIVE_EXT`
incluye los ZIP disfrazados (`jar`, `whl`, `docx`, `epub`…), que seguirían
funcionando igual.

**Qué construir.** Primero una interfaz de backend — `listar`, `extraer`,
`crear`, `verificar` — y mover el ZIP actual detrás de ella sin cambiar
comportamiento. Recién después sumar formatos:

| Formato | Cómo | Nota |
|---|---|---|
| TAR, GZ, BZ2, XZ | `tarfile`, biblioteca estándar | Lectura y escritura. Gratis. |
| 7z | `py7zr` | Lectura y escritura. Dependencia pura Python. |
| RAR | `rarfile` | **Sólo lectura.** El formato es propietario; comprimir a RAR no se puede sin el `rar` de WinRAR. |

**Decisión pendiente.** `rarfile` necesita `unrar` o `bsdtar` instalado en el
sistema para descomprimir de verdad. Hay que decidir si es una dependencia
opcional que se detecta al arrancar — y el formato simplemente no aparece si
falta — o un requisito del instalador. Lo primero es más sano: el usuario de
Linux no debería tener que instalar un binario no libre para poder abrir ZIP.

El orden sugerido es TAR primero: es el que no suma dependencias y sirve para
validar que la interfaz de backend está bien dibujada.

---

## Etapa 3 — Menú contextual real de Windows · M

Hoy `Shift+F10` abre un menú **propio**, armado a mano en Qt con comandos de MC
(`mainwindow.py:1046`). Total Commander abre el menú real del Explorador, con
todo lo que el usuario tenga instalado: 7-Zip, "Abrir con", "Enviar a", Git
Bash, TortoiseGit, el antivirus. Es la diferencia entre un menú de catorce
entradas fijas y uno que crece con la máquina.

**Qué construir.** Un módulo `mc/shellmenu.py`, sólo Windows, que hable COM con
el shell. La secuencia es conocida:

1. `SHParseDisplayName` para conseguir el PIDL de cada archivo, y
   `SHBindToParent` para llegar al `IShellFolder` que los contiene.
2. `IShellFolder::GetUIObjectOf` con el arreglo de PIDL hijos pide un
   `IContextMenu`.
3. `CreatePopupMenu` y `IContextMenu::QueryContextMenu` lo llenan. Con la tecla
   Shift apretada se agrega `CMF_EXTENDEDVERBS`, que es lo que descubre las
   entradas ocultas igual que en el Explorador.
4. `TrackPopupMenuEx` con `TPM_RETURNCMD` lo muestra y devuelve el id elegido.
5. `IContextMenu::InvokeCommand` con `CMINVOKECOMMANDINFOEX` lo ejecuta.
6. Recargar el panel: una extensión del shell pudo haber creado, borrado o
   renombrado algo.

**El paso que siempre se olvida.** Los submenús —"Enviar a", "Abrir con",
"Nuevo"— y las entradas dibujadas por el propio plugin necesitan
`IContextMenu2`/`IContextMenu3`: hay que reenviarles `WM_INITMENUPOPUP`,
`WM_DRAWITEM`, `WM_MEASUREITEM` y `WM_MENUCHAR` a través de `HandleMenuMsg2`.
En Qt eso es un `QAbstractNativeEventFilter` instalado mientras el menú está
arriba y sacado después. Sin esto el menú aparece pero "Enviar a" sale vacío.

**Lo que hay que cuidar.**

- **Windows 11.** `IContextMenu` da el menú **clásico**, el mismo que se ve con
  "Mostrar más opciones" o con `Shift+F10` en el Explorador. El menú compacto
  nuevo usa `IExplorerCommand` y aplicaciones empaquetadas, y no se consigue
  por esta vía. TC se comporta igual. Para este caso de uso el clásico es el
  completo, así que no es una pérdida.
- **Se cargan DLL de terceros dentro del proceso.** Una extensión del shell
  rota puede colgar o tirar abajo MC. Es la misma exposición que tienen TC y el
  propio Explorador. Conviene una clave `shell_context_menu` en el ini para
  apagarlo y volver al menú actual, que queda como alternativa.
- **COM.** `CoInitializeEx` en modo apartamento sobre el hilo principal, y
  aceptar `RPC_E_CHANGED_MODE` como éxito: el proveedor de iconos de Qt ya
  inicializó COM antes. Soltar siempre las interfaces y liberar los PIDL con
  `CoTaskMemFree`; esto ya mordió una vez en este proyecto, porque `os._exit()`
  revienta con `0xC0000005` si quedan hilos COM del shell vivos.
- **Dónde no aplica.** Adentro de un ZIP y en la vista de rama (`Ctrl+B`) no
  hay PIDL utilizables —o los archivos tienen padres distintos—, así que ahí
  hay que caer al menú propio.

**Decisión pendiente.** `ctypes` puro o `pywin32`. Hoy el proyecto tiene una
sola dependencia y `platform.py` habla con Win32 por `ctypes` a mano, pero son
llamadas a funciones sueltas; esto son interfaces COM con vtables, que a mano
es bastante más código. `pywin32` trae `GetUIObjectOf` e `IContextMenu2` ya
envueltos. Mi inclinación es `pywin32` como dependencia **sólo de Windows** en
`requirements.txt`, y que el menú propio sea el camino de respaldo si no está.

**De paso.** Las catorce cadenas del menú actual (`mainwindow.py:1050-1068`) no
pasan por `t()`: en inglés siguen apareciendo en español. Hay que envolverlas y
agregar las claves al catálogo `EN`.

---

## Etapa 4 — Iconos por archivo y accesos directos · S

Dos síntomas, una causa. `fsmodel.py:33` cachea los iconos **por extensión**:

```python
key = entry.ext.lower() or "<file>"
```

Así, el primer `.exe` que se lista le presta su icono a todos los demás `.exe`,
y lo mismo pasa con `.lnk` y `.ico`. Para la mayoría de las extensiones está
bien y es lo que hace rápido el listado —un directorio con 5.000 `.txt` pide un
solo icono al shell—, pero justo para los tipos que llevan su icono **adentro**
el resultado es visiblemente incorrecto.

Y los accesos directos además no se ven como tales: les falta la flecha
superpuesta, y `Enter` sobre un `.lnk` no sigue al destino.

**Qué construir.**

1. **Un conjunto de extensiones que se cachean por ruta y no por extensión**:
   `exe`, `lnk`, `ico`, `cur`, `url`, `msc`, `cpl`. Para esas, la clave del
   caché es la ruta completa más la fecha de modificación. El caché se acota
   con un LRU para que un directorio de 10.000 ejecutables no se coma la
   memoria.
2. **La flecha de acceso directo.** `SHGetFileInfo` con
   `SHGFI_ICON | SHGFI_LINKOVERLAY` la devuelve ya compuesta por el shell, que
   es mejor que dibujarla a mano porque respeta el tema y el DPI.
3. **Seguir el acceso directo.** `IShellLink` + `IPersistFile::Load` resuelve el
   destino. Si apunta a una carpeta, `Enter` navega ahí; si apunta a un archivo,
   lo ejecuta. Es lo que hace TC y es la mitad de la utilidad de un `.lnk` en un
   gestor de archivos.
4. **Mostrar el destino.** En la barra de estado al pararse encima, y como
   columna opcional cuando exista la etapa 9.

**Lo que hay que cuidar.** Pedirle iconos al shell archivo por archivo es lento
si se hace en el hilo de la interfaz: un directorio de red con cien `.exe`
congela la ventana. La forma correcta es pedirlos en un hilo y que el modelo
emita `dataChanged` cuando llegan, con un icono genérico mientras tanto.
`SHGFI_USEFILEATTRIBUTES` sirve para el icono provisorio sin tocar el disco.

En Linux el equivalente son los enlaces simbólicos, que `fsmodel.py:97` ya
listaba con `follow_symlinks=False`; marcarlos con una flecha y resolverlos con
`os.readlink` es el mismo trabajo y mucho más barato.

---

## Etapa 5 — Barra de unidades en cada panel · S

Hoy hay **una sola** barra de unidades, arriba de todo, y actúa sobre el panel
activo (`mainwindow.py:99`). Eso obliga a mirar cuál panel tiene el foco antes
de hacer clic, que es exactamente la duda que la barra debería evitar. TC
permite una barra por panel, cada una atada a su lado.

**Qué construir.** Mover la construcción de la barra a `Panel`, de modo que
cada una sepa a qué panel pertenece y no consulte `self.active`. Una clave
`drive_bar` en el ini con tres valores: `una` (lo de hoy), `dos` (una por
panel) y `no` (ocultarla), con su selector en el diálogo de la etapa 1.

La barra por panel muestra además el espacio libre de **esa** unidad, no el de
la activa, lo que hace que `_update_drive_info` deje de ser global.

Conviene aprovechar y sumar lo que TC tiene al lado de cada barra: un combo con
la letra, la etiqueta del volumen y el espacio libre. `Alt+F1` y `Alt+F2` ya
abren ese menú de unidades para el panel izquierdo y el derecho
(`cm_LeftOpenDrives` / `cm_RightOpenDrives`); el combo es la misma información
siempre visible.

**Lo que hay que cuidar.** Las unidades se enumeran una sola vez al arrancar
(`platform.py:51`, `GetLogicalDrives`). Con dos barras se nota más que un pendrive
enchufado después no aparece. La solución es escuchar `WM_DEVICECHANGE` en
Windows —el mismo `QAbstractNativeEventFilter` de la etapa 3— y refrescar.

---

## Etapa 6 — Renombrado masivo (Multi-Rename) · M

`Ctrl+M`. De lo más usado de TC y no tiene nada que ver con el resto: un módulo
nuevo, `mc/multirename.py`, sin tocar casi nada de lo existente.

**Qué construir.** Un diálogo con una plantilla de nombre y una de extensión,
una tabla de vista previa que muestra *nombre viejo → nombre nuevo* actualizada
a cada tecla, y el renombrado en lote.

Comodines, los mismos que TC para que la memoria muscular sirva:

```
[N]        nombre sin extensión        [E]        extensión
[N1-5]     caracteres 1 a 5 del nombre [C]        contador
[C:3]      contador con ancho fijo     [d]        fecha del archivo
[Y][M][D]  año, mes, día
```

Más buscar y reemplazar, con una casilla para tratar el patrón como expresión
regular, y pasar a mayúsculas o minúsculas.

**Lo que hay que cuidar.** Tres cosas, y las tres muerden:

1. **Colisiones.** Dos archivos que terminan con el mismo nombre. Hay que
   detectarlo en la vista previa y marcarlo en rojo antes de tocar el disco.
2. **Renombrados en cadena.** `a→b` cuando `b` ya existe y también se va a
   renombrar. Se resuelve renombrando a nombres temporales y después al
   definitivo.
3. **Deshacer.** TC guarda la lista para revertir. Vale la pena: un renombrado
   masivo mal hecho sobre 400 archivos no se arregla a mano.

---

## Etapa 7 — Sincronizar directorios · M

Comparar dos árboles completos y copiar en ambos sentidos. Es el complemento
natural de `Shift+F2`, que hoy compara **sólo el directorio actual** de cada
panel y deja marcado lo que habría que copiar.

**Qué construir.** Un módulo `mc/sync.py` con el recorrido recursivo en un hilo
— `compare.py` ya tiene el patrón `QThread` con señales — y un diálogo con la
lista de diferencias, una flecha por fila (`→`, `←`, `=`, `≠`) que se puede
cambiar a mano, y filtros por dirección.

Reglas de comparación, de más barata a más cara: por tamaño, por fecha, por
contenido. El hash SHA-256 por bloques que usa `compare.py:28` ya sirve para la
tercera.

La copia reutiliza `CopyMoveWorker` de `ops.py` tal cual.

**Lo que hay que cuidar.** Un árbol de 100.000 archivos no entra cómodo en un
`QTableWidget` poblado fila por fila. Si aparece lentitud, el camino es un
modelo propio sobre `QAbstractTableModel`, igual que `fsmodel.py`.

---

## Etapa 8 — Comparar archivos por contenido · M

Un visor de diferencias lado a lado. Hoy no hay nada: el visor muestra de a un
archivo.

**Qué construir.** `mc/diff.py`, dos `QPlainTextEdit` sincronizados en el
scroll, el algoritmo de `difflib.SequenceMatcher` de la biblioteca estándar
(suficiente hasta decenas de miles de líneas), colores de agregado, borrado y
cambiado tomados de los tokens de `theme.py` para que respete claro y oscuro, y
navegación de diferencia en diferencia con `F7` y `Shift+F7`.

Para binarios, comparación en hexadecimal reutilizando `hex_dump` de
`viewer.py:52`.

**Alcance que conviene dejar afuera por ahora.** Editar y copiar bloques de un
lado al otro, como hace TC. Primero que muestre bien; lo otro es otra etapa.

---

## Etapa 9 — Columnas, vistas y miniaturas · L

Acá se toca una decisión de la v1: `fsmodel.py:25` tiene cinco columnas fijas
—Nombre, Ext, Tamaño, Fecha, Atr— cableadas en el modelo, y `FileListModel`
asume ese orden.

**Qué construir, en tres pasos que se pueden hacer por separado:**

1. **Columnas elegibles y reordenables.** Mostrar u ocultar, arrastrar el
   encabezado, guardar el ancho en el ini. Esto solo ya es la mitad del valor.
2. **Columnas nuevas.** Propietario, permisos en octal, cantidad de archivos de
   una carpeta, hash.
3. **Miniaturas.** Un `QListView` en modo icono como vista alternativa del
   panel, con generación de miniaturas en un hilo y caché en disco bajo
   `config_dir()`.

**Por qué es L.** Las columnas dejan de ser una constante y pasan a ser estado
por pestaña, lo que toca `TabState` en `panel.py:32`, el modelo entero y el
guardado de configuración. Y las miniaturas meten un segundo widget de vista en
`Panel`, que hoy asume un `FileView` y nada más.

---

## Etapa 10 — Que el usuario pueda cambiar las teclas y los botones · M

Hoy la tabla de atajos vive en el código (`mainwindow.py:279`) y la barra de
botones es fija.

**Qué construir.** Una sección `[keys]` en el ini que mapee atajo a nombre de
comando, con la tabla actual como valores por defecto, y un editor en el
diálogo de la etapa 1: lista de los 90 comandos, el atajo asignado, detección
de conflictos y botón para volver al valor de fábrica.

Lo mismo para la barra de botones: una sección `[buttonbar]` con la lista de
comandos, y arrastrar para reordenar.

**Lo que esto habilita.** Comandos de usuario — los `em_*` de TC: lanzar un
programa externo con parámetros sobre el archivo seleccionado. Una vez que las
teclas salen del ini, un `em_*` es una entrada más en el diccionario
`self.commands`, construida al arrancar en vez de escrita a mano.

Es la etapa que más se parece a lo que hace que TC sea TC para quien lo usa en
serio.

---

## Etapa 11 — Herramientas sueltas · S cada una

Independientes entre sí. Se pueden tomar de a una cuando haya ganas:

- **Dividir y unir archivos.** El formato `.001`, `.002` de TC, con un `.crc`
  para verificar. Trivial sobre el patrón `_Worker` de `ops.py`.
- **Más checksums.** Hoy sólo SHA-256 en formato `sha256sum`. Sumar MD5, SHA-1,
  CRC32 y leer/escribir `.sfv` y `.md5`. Es casi todo elegir el algoritmo en un
  combo, `compare.py:125` ya hace el resto.
- **Buscar dentro de comprimidos.** `search.py` recorre el árbol; falta que al
  cruzar un archivo que `is_archive()` reconoce, mire adentro. Depende de la
  etapa 2 para que valga para algo más que ZIP.
- **Buscar duplicados.** Por tamaño primero y por hash después, que es el orden
  que evita leer todo. Encaja como una casilla más en el diálogo de búsqueda.
- **Codificar y decodificar.** Base64, MIME, UUE. Casi todo está en la
  biblioteca estándar.
- **Panel de árbol** (`Ctrl+F8`). Un `QTreeView` a la izquierda del panel, con
  carga perezosa. La vista de rama (`Ctrl+B`) ya existe y es otra cosa.
- **Imprimir listados.** `QPrinter` sobre el contenido del panel o del visor.

---

## Etapa 12 — Probar macOS · S, pero necesita una Mac

El código tiene sus ramas escritas y nunca ejecutadas: `Library/Application
Support`, `/Volumes`, `open`, `open -R`, Finder para la papelera, todo en
`platform.py`. Lo que más chance tiene de fallar es el menú contextual y la
detección de volúmenes.

Hace falta además un `install.command` o un `.app` armado con PyInstaller, y
firmarlo para que Gatekeeper no lo bloquee.

No se puede avanzar sin hardware. Mientras tanto, el README dice la verdad:
macOS no está probado.

---

## Etapa 13 — Lo grande, si alguna vez · L

Lo que en `SPEC.md` figura como "no" y debería seguir figurando así hasta que
haya una razón concreta:

**FTP, SFTP y WebDAV.** No es sólo el protocolo: es que el panel deja de ser un
directorio local. `Panel` asume rutas del sistema de archivos en todos lados.
Hacerlo bien significa una capa de sistema de archivos virtual entre
`fsmodel.py` y el panel, y eso es un rediseño, no una etapa.

**Plugins WCX / WFX / WLX / WDX.** Cargar DLL de terceros con la ABI de TC. En
Python significa `ctypes` contra una interfaz no documentada oficialmente, y
sólo funcionaría en Windows. El retorno de inversión es malo; la capa de
sistema de archivos virtual de arriba daría el 80% del beneficio de los WFX sin
atarse a una ABI ajena.

---

## Reglas de la casa

Para que lo que venga se parezca a lo que ya está:

**Un comando nuevo es una fila en `self.commands`** (`mainwindow.py:335`), con
el nombre `cm_*` que usa TC. El menú, la barra de teclas y los atajos son tres
formas de disparar la misma entrada. Si el comando existe en TC, usá su nombre
aunque la implementación sea distinta.

**Todo texto visible pasa por `t()`.** Las claves del catálogo son **las
cadenas en español**, porque el idioma fuente del proyecto es el español. Al
sumar texto hay que agregar la traducción en el diccionario `EN` de
`i18n.py:30`. Una clave ausente devuelve el texto tal cual, así que olvidarse
degrada a español en vez de romper.

**Nada específico del sistema fuera de `platform.py`.** La razón es dura:
`ctypes.wintypes` no se puede ni importar fuera de Windows. Un
`from ctypes import wintypes` a nivel de módulo rompe la aplicación entera al
arrancar en Linux.

**Toda operación larga va en un `QThread`** con progreso cancelable. El patrón
está en `_Worker` (`ops.py:60`) y lo reusan `archive.py` y `compare.py`.

**Los colores salen de los tokens de `theme.py`**, nunca escritos a mano en un
widget. Si no, el tema claro queda roto.

**`tests/smoke.py` tiene que seguir en verde**, incluido su chequeo de AST que
verifica que las claves de traducción existan. Correrlo con
`QT_QPA_PLATFORM=offscreen`, y en Python 3.10 además de 3.12: la imagen
`tools/Dockerfile.linux-test` usa 3.10 a propósito para cazar sintaxis que sólo
anda en versiones nuevas.

## Orden sugerido

```
1 config  →  2 comprimidos
                                 ┌─ 3 menú contextual ─┐
   integración con Windows ──────┼─ 4 iconos y .lnk    ├──→  9 columnas
                                 └─ 5 barra de unidades┘          ↓
                                                         10 teclas y botones
6 multi-rename  →  7 sincronizar  →  8 diff

11 herramientas sueltas: en cualquier momento
12 macOS: cuando haya una Mac        13 lo grande: por ahora no
```

Las etapas 1 a 8 son independientes entre sí y cada una se puede soltar
terminada.

Las tres de integración con Windows —3, 4 y 5— conviene hacerlas en ese orden
aunque sean independientes: las tres tocan Win32, y el
`QAbstractNativeEventFilter` que hace falta para los submenús del menú
contextual es el mismo que después escucha `WM_DEVICECHANGE` para refrescar las
unidades. La 4 es la más barata de las tres y la que más se nota por día.

La 9 y la 10 conviene hacerlas juntas porque las dos mueven configuración al
ini. La 11 se puede intercalar en cualquier momento.
