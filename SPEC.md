# Marce Commander — especificación derivada de Total Commander

## Origen de la evidencia

Analizado: `C:\Users\mpereira\app\totalcmd\TOTALCMD64.EXE`
SHA-256: `4305e7d27ca55489ee0abf98056a17dc3a7318ada5d71015d0de0ed9458524e2`

| Dato | Valor | Fuente |
|---|---|---|
| Versión | 9.51 (Ghisler Software GmbH, © 1993-2020 Christian Ghisler) | VERSIONINFO del PE |
| Formato | PE32+ x86-64, 8 secciones | `binary_overview` (Ghidra 12.1.4) |
| Procedimientos | 11.247 | idem |
| Strings | 12.897 | idem |
| `.text` | 7.053.824 bytes | idem |
| `.rsrc` | 516.096 bytes | idem |
| Toolkit | Free Pascal / Lazarus (LCL) — la sección `.gnu_debuglink` y los símbolos `TForm` descartan el linker de Borland | secciones + strings |
| Recursos | 188 iconos, 93 bitmaps, 83 string tables, 56 grupos de iconos, 20 cursores, 7 diálogos RT_DIALOG, 1 manifest | `inspect_pe_resources`, 474 entradas, cobertura completa |

Los 7 diálogos RT_DIALOG frente a 554 comandos confirman que los formularios no están en la
tabla de recursos: Lazarus los serializa como RCDATA, igual que Delphi con los .DFM.

**La superficie funcional no se dedujo del código decompilado**, sino de los archivos de
especificación que el propio producto distribuye junto al ejecutable: `TOTALCMD.INC`
(554 comandos `cm_*` con su ID numérico y descripción) y `KEYBOARD.TXT` (mapa de atajos).
Son documentación pública del formato de extensión de TC.

## Qué se reimplementa y qué no

Marce Commander es una implementación **original** del género "commander" de doble panel
(Norton Commander, 1986). Se toma de TC el modelo de interacción — distribución, atajos,
nombres de comando — que es la convención del género y lo que hace que la herramienta se
sienta familiar. **No** se copia código, recursos, iconos ni textos del binario analizado.

## Distribución de la ventana

```
┌─ menú: Archivos  Marcar  Comandos  Config ───────────────┐
│ barra de botones                                          │
│ [c:][d:][e:]        unidad + espacio libre                │
├───────────────────────────┬───────────────────────────────┤
│ pestañas panel izq        │ pestañas panel der            │
│ ruta actual               │ ruta actual                   │
│ Nombre │ Ext │ Tam │ Fecha│ Nombre │ Ext │ Tam │ Fecha    │
│ ..                        │ ..                            │
│ [carpeta]                 │ archivo.txt                   │
│ ...                       │ ...                           │
│ barra de estado/selección │ barra de estado/selección     │
├───────────────────────────┴───────────────────────────────┤
│ C:\ruta\actual>  línea de comandos                        │
│ F3 Ver  F4 Editar  F5 Copiar  F6 Mover  F7 Dir  F8 Borrar │
└───────────────────────────────────────────────────────────┘
```

El panel con foco es el **origen**; el otro es el **destino**. Toda operación de archivo va
de origen a destino. Este es el invariante central del género.

## Comandos (554 en TC, agrupados por categoría)

| Categoría | TC | En MC v1 |
|---|---|---|
| Tabs | 55 | sí (núcleo) |
| View / View modes | 44 + 41 | parcial |
| Sorting / Custom columns | 44 + 49 | parcial |
| Mark | 43 | sí |
| Navigation | 36 | sí |
| FileOperations | 34 | sí |
| Configuration | 33 | parcial |
| Misc | 30 | parcial |
| Left / Right / Source | 24 + 24 + 23 | sí |
| Tools | 15 | parcial |
| Clipboard | 11 | sí |
| User, FTP, Network, Help, Window, Security, CommandLine, Print, ParallelPort | 48 | no |

### Operaciones de archivo

| Comando | ID | Acción |
|---|---|---|
| `cm_List` | 903 | Ver archivo (visor interno) |
| `cm_Edit` | 904 | Editar archivo |
| `cm_Copy` | 905 | Copiar al panel destino |
| `cm_RenMov` | 906 | Mover / renombrar |
| `cm_MkDir` | 907 | Crear directorio |
| `cm_Delete` | 908 | Borrar (a papelera o definitivo) |
| `cm_RenameOnly` | 1002 | Renombrar en el mismo directorio |
| `cm_Properties` | 1003 | Diálogo de propiedades |
| `cm_Return` | 1001 | Abrir / ejecutar |
| `cm_PackFiles` | 508 | Comprimir a ZIP |
| `cm_UnpackFiles` | 509 | Descomprimir |
| `cm_SetAttrib` | 502 | Cambiar atributos |
| `cm_CRCcreate` / `cm_CRCcheck` | 564 / 565 | Checksums |

### Selección

TC distingue en cada operación entre *archivos*, *carpetas* o *ambos* — de ahí que haya 43
comandos de marcado para 6 acciones lógicas. MC implementa las 6 acciones con la variante
"archivos + carpetas" por defecto.

| Acción | Comando TC | Tecla |
|---|---|---|
| Seleccionar grupo (patrón) | `cm_SpreadSelection` 521 | `Num +` |
| Deseleccionar grupo | `cm_ShrinkSelection` 522 | `Num -` |
| Invertir selección | `cm_ExchangeSelection` 525 | `Num *` |
| Seleccionar todo | `cm_SelectAll` 523 | `Ctrl+Num +` |
| Deseleccionar todo | `cm_ClearAll` 524 | `Ctrl+Num -` |
| Misma extensión | `cm_SelectCurrentExtension` | `Alt+Num +` |

### Navegación

`cm_GotoPreviousDir` 570 / `cm_GotoNextDir` 571 (historial atrás/adelante),
`cm_DirectoryHistory` 572, `cm_DirectoryHotlist` 526 (marcadores),
`cm_GoToRoot` 2001, `cm_GoToParent` 2002, `cm_GoToDir` 2003,
`cm_TransferLeft` 2024 / `cm_TransferRight` 2025 (pasar el dir del cursor al otro panel),
`cm_SyncChangeDir` 2600 (cambio sincronizado de directorio en ambos paneles).

### Portapapeles

`cm_CutToClipboard` 2007, `cm_CopyToClipboard` 2008, `cm_PasteFromClipboard` 2009 — usan el
formato `CF_HDROP` de Windows, así que interoperan con el Explorador.
`cm_CopyNamesToClip` 2017 y `cm_CopyFullNamesToClip` 2018 copian los nombres como texto.

### Foco

`cm_FocusLeft` 4001, `cm_FocusRight` 4002, `cm_FocusSrc` 4005, `cm_FocusTrg` 4006,
`cm_FocusCmdLine` 4003.

## Mapa de teclado

### Teclas de función

| Tecla | Acción | Tecla | Acción |
|---|---|---|---|
| `F1` | Ayuda | `F2` | Releer panel |
| `F3` | Ver | `F4` | Editar |
| `F5` | Copiar | `F6` | Mover / renombrar |
| `F7` | Crear directorio | `F8` / `Del` | Borrar |
| `F9` | Menú | `F10` | Salir del menú |
| `Shift+F2` | Comparar listas | `Shift+F4` | Nuevo archivo de texto |
| `Shift+F5` | Copiar en el mismo dir | `Shift+F6` | Renombrar en el sitio |
| `Shift+F7` | Crear dir en el otro panel | `Shift+F8` | Borrar definitivo |
| `Shift+F10` | Menú contextual | `Shift+Esc` | Minimizar |

### Alt + F

| Tecla | Acción | Tecla | Acción |
|---|---|---|---|
| `Alt+F1` | Cambiar unidad izquierda | `Alt+F2` | Cambiar unidad derecha |
| `Alt+F5` | Comprimir | `Alt+F6` / `Alt+F9` | Descomprimir |
| `Alt+F7` | Buscar archivos | `Alt+Shift+F9` | Verificar comprimidos |
| `Alt+F8` | Historial de la línea de comandos | `Alt+F10` | Árbol de directorios |
| `Alt+←` / `Alt+→` | Atrás / adelante | `Alt+↓` | Historial de directorios |

### Ctrl + F — vista y orden

| Tecla | Acción | Tecla | Acción |
|---|---|---|---|
| `Ctrl+F1` | Vista breve (sólo nombres) | `Ctrl+F2` | Vista detallada |
| `Ctrl+Shift+F1` | Miniaturas | `Ctrl+F3` | Ordenar por nombre |
| `Ctrl+F4` | Por extensión | `Ctrl+F5` | Por fecha |
| `Ctrl+F6` | Por tamaño | `Ctrl+F7` | Sin ordenar |
| `Ctrl+F8` | Árbol | `Ctrl+F10` | Mostrar todos los archivos |

### Navegación y pestañas

| Tecla | Acción |
|---|---|
| `Tab` | Cambiar de panel |
| `Backspace` / `Ctrl+AvPág` | Directorio padre |
| `Ctrl+RePág` | Entrar al directorio / archivo comprimido |
| `Ctrl+\` | Ir a la raíz |
| `Ctrl+←` / `Ctrl+→` | Abrir el directorio del cursor en el **otro** panel |
| `Ctrl+T` | Nueva pestaña |
| `Ctrl+W` | Cerrar pestaña |
| `Ctrl+Tab` / `Ctrl+Shift+Tab` | Pestaña siguiente / anterior |
| `Ctrl+U` | Intercambiar paneles |
| `Ctrl+D` | Marcadores de directorios |
| `Ctrl+B` | Vista de rama (todos los archivos del subárbol) |
| `Ctrl+Q` | Vista rápida del archivo bajo el cursor |
| `Insert` / `Espacio` | Marcar / desmarcar |

## Decisiones propias de MC (no provienen de TC)

- Las operaciones de archivo corren en un hilo aparte con diálogo de progreso cancelable.
- El borrado va a la papelera por defecto vía `SHFileOperation` de Windows.
- La configuración se guarda en `%APPDATA%\MarceCommander\mc.ini` — mismo espíritu que el
  `WINCMD.INI` de TC, pero sin compatibilidad de formato.
- Los iconos salen de `QFileIconProvider`, que consulta al shell de Windows. No se extrae
  ningún icono del binario analizado.
