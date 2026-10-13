"""Integración con el shell de Windows: menú contextual real y accesos directos.

Este módulo **sólo existe en Windows**; importarlo en otro sistema lanza
`ImportError` a propósito, para que quien lo use tenga que decidir qué hacer sin
él. El patrón de uso es:

    try:
        from . import winshell
    except ImportError:
        winshell = None

Habla COM a mano con `ctypes`, sin `pywin32`. La razón no es purismo: el
proyecto tiene una sola dependencia y el ejecutable de Windows pesa 65 MB
después de haberlo peleado bastante. Agregar `pywin32` para esto sumaba una
dependencia de 12 MB y un camino nuevo en PyInstaller, cuando lo que hace falta
son seis interfaces y unas pocas llamadas a cada una.

Una interfaz COM es un puntero a un puntero a una tabla de funciones. `_vcall`
indexa esa tabla; los números de índice que aparecen más abajo son el orden de
declaración de cada método, contando los tres de `IUnknown` que toda interfaz
hereda primero.
"""

from __future__ import annotations

import ctypes
import os
import sys

if sys.platform != "win32":                                   # pragma: no cover
    raise ImportError("mc.winshell sólo tiene sentido en Windows")

from ctypes import wintypes

ole32 = ctypes.WinDLL("ole32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

S_OK = 0
RPC_E_CHANGED_MODE = -2147417850                               # 0x80010106

# Se declaran los HRESULT como c_long a propósito: con `ctypes.HRESULT` ctypes
# convierte un código de error en una excepción antes de que lo podamos mirar,
# y acá varios "errores" son respuestas normales que hay que poder leer.
ole32.CoInitializeEx.restype = ctypes.c_long
ole32.CoCreateInstance.restype = ctypes.c_long
ole32.IIDFromString.restype = ctypes.c_long
ole32.CoTaskMemFree.restype = None
ole32.CoTaskMemFree.argtypes = (ctypes.c_void_p,)
shell32.SHParseDisplayName.restype = ctypes.c_long
shell32.SHBindToParent.restype = ctypes.c_long
user32.CreatePopupMenu.restype = wintypes.HMENU
user32.TrackPopupMenuEx.restype = ctypes.c_int


# --- plomería COM ------------------------------------------------------

class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _guid(text: str) -> GUID:
    g = GUID()
    if ole32.IIDFromString(ctypes.c_wchar_p(text), ctypes.byref(g)) != S_OK:
        raise ValueError(f"GUID inválido: {text}")
    return g


IID_IShellFolder = _guid("{000214E6-0000-0000-C000-000000000046}")
IID_IContextMenu = _guid("{000214E4-0000-0000-C000-000000000046}")
IID_IContextMenu2 = _guid("{000214F4-0000-0000-C000-000000000046}")
IID_IContextMenu3 = _guid("{BCFCE0A0-EC17-11D0-8D10-00A0C90F2719}")
IID_IShellLinkW = _guid("{000214F9-0000-0000-C000-000000000046}")
IID_IPersistFile = _guid("{0000010B-0000-0000-C000-000000000046}")
CLSID_ShellLink = _guid("{00021401-0000-0000-C000-000000000046}")


def _vcall(this, index: int, restype, argtypes, *args):
    """Llama al método número `index` de la vtable de la interfaz `this`."""
    vtable = ctypes.cast(this, ctypes.POINTER(ctypes.c_void_p))[0]
    slot = ctypes.cast(vtable, ctypes.POINTER(ctypes.c_void_p))[index]
    proto = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    return proto(slot)(this, *args)


def _query_interface(this, iid: GUID):
    """QueryInterface (índice 0). Devuelve el puntero o None si no la soporta."""
    out = ctypes.c_void_p()
    hr = _vcall(this, 0, ctypes.c_long,
                (ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)),
                ctypes.byref(iid), ctypes.byref(out))
    return out if hr == S_OK and out else None


def _release(this) -> None:
    """Release (índice 2). Tolera None para poder llamarlo en un finally."""
    if this:
        _vcall(this, 2, ctypes.c_ulong, ())


class _Com:
    """CoInitializeEx en modo apartamento, con su CoUninitialize.

    `RPC_E_CHANGED_MODE` cuenta como éxito pero **no** hay que desinicializar:
    significa que alguien —el proveedor de iconos de Qt -- ya dejó el hilo en
    otro modo, y es su inicialización, no la nuestra.
    """

    def __enter__(self):
        hr = ole32.CoInitializeEx(None, 0x2)          # COINIT_APARTMENTTHREADED
        self._uninit = hr in (S_OK, 1)                # S_OK o S_FALSE
        if hr not in (S_OK, 1, RPC_E_CHANGED_MODE):
            raise OSError(f"CoInitializeEx falló: 0x{hr & 0xFFFFFFFF:08X}")
        return self

    def __exit__(self, *exc):
        if self._uninit:
            ole32.CoUninitialize()
        return False


# --- accesos directos (.lnk) -------------------------------------------

SLGP_RAWPATH = 0x4
_MAX_PATH = 260


def resolve_shortcut(path: str) -> str | None:
    """Destino de un `.lnk`, o None si no se pudo resolver.

    Usa `IShellLink` en vez de leer el formato a mano porque el shell resuelve
    además las rutas relativas y las variables de entorno que el archivo puede
    guardar en lugar de una ruta absoluta.
    """
    if not path.lower().endswith(".lnk"):
        return None

    link = ctypes.c_void_p()
    persist = None
    try:
        with _Com():
            hr = ole32.CoCreateInstance(
                ctypes.byref(CLSID_ShellLink), None, 1,       # CLSCTX_INPROC_SERVER
                ctypes.byref(IID_IShellLinkW), ctypes.byref(link))
            if hr != S_OK or not link:
                return None

            persist = _query_interface(link, IID_IPersistFile)
            if not persist:
                return None

            # IPersistFile::Load es el índice 5: 3 de IUnknown, GetClassID de
            # IPersist, IsDirty, y recién ahí Load.
            hr = _vcall(persist, 5, ctypes.c_long,
                        (ctypes.c_wchar_p, ctypes.c_uint32),
                        ctypes.c_wchar_p(path), 0)            # STGM_READ
            if hr != S_OK:
                return None

            buf = ctypes.create_unicode_buffer(_MAX_PATH)
            hr = _vcall(link, 3, ctypes.c_long,              # IShellLinkW::GetPath
                        (ctypes.c_wchar_p, ctypes.c_int,
                         ctypes.c_void_p, ctypes.c_uint32),
                        buf, _MAX_PATH, None, SLGP_RAWPATH)
            if hr != S_OK:
                return None
            destino = os.path.expandvars(buf.value)
            return destino or None
    except OSError:
        return None
    finally:
        _release(persist)
        _release(link)


def shortcut_target_dir(path: str) -> str | None:
    """El destino sólo si es un directorio: es el caso que cambia la navegación."""
    destino = resolve_shortcut(path)
    if destino and os.path.isdir(destino):
        return destino
    return None


# --- menú contextual ---------------------------------------------------

CMF_NORMAL = 0x0
CMF_EXPLORE = 0x4
CMF_EXTENDEDVERBS = 0x100

TPM_LEFTALIGN = 0x0
TPM_RETURNCMD = 0x100
TPM_RIGHTBUTTON = 0x2

CMIC_MASK_UNICODE = 0x4000
SW_SHOWNORMAL = 1

ID_PRIMERO = 1
ID_ULTIMO = 0x7FFF

WM_INITMENUPOPUP = 0x0117
WM_DRAWITEM = 0x002B
WM_MEASUREITEM = 0x002C
WM_MENUCHAR = 0x0120
WM_MENUSELECT = 0x011F

# Los mensajes que las extensiones del shell necesitan para dibujar sus propios
# submenús. Sin reenviarlos, "Enviar a" y "Abrir con" aparecen pero vacíos.
MENSAJES_DE_MENU = (WM_INITMENUPOPUP, WM_DRAWITEM, WM_MEASUREITEM, WM_MENUCHAR)


class CMINVOKECOMMANDINFOEX(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint32),
        ("fMask", ctypes.c_uint32),
        ("hwnd", wintypes.HWND),
        ("lpVerb", ctypes.c_char_p),
        ("lpParameters", ctypes.c_char_p),
        ("lpDirectory", ctypes.c_char_p),
        ("nShow", ctypes.c_int),
        ("dwHotKey", ctypes.c_uint32),
        ("hIcon", wintypes.HANDLE),
        ("lpTitle", ctypes.c_char_p),
        ("lpVerbW", ctypes.c_wchar_p),
        ("lpParametersW", ctypes.c_wchar_p),
        ("lpDirectoryW", ctypes.c_wchar_p),
        ("lpTitleW", ctypes.c_wchar_p),
        ("ptInvoke", wintypes.POINT),
    ]


def _pidl_de(path: str):
    """PIDL absoluto de una ruta. Hay que liberarlo con CoTaskMemFree."""
    pidl = ctypes.c_void_p()
    hr = shell32.SHParseDisplayName(
        ctypes.c_wchar_p(os.path.normpath(path)), None,
        ctypes.byref(pidl), 0, None)
    return pidl if hr == S_OK and pidl else None


class _Reenviador:
    """Pasa los mensajes del menú a IContextMenu2/3 mientras el menú está vivo.

    `TrackPopupMenuEx` corre su propio bucle de mensajes, pero los despacha a la
    ventana dueña — que acá es la de Qt —, así que su wndproc los ve y llama a
    los filtros nativos instalados. Por eso alcanza con un
    `QAbstractNativeEventFilter` puesto mientras dura el menú y sacado después.
    """

    def __init__(self, cm2, cm3):
        self.cm2, self.cm3 = cm2, cm3

    def manejar(self, msg: int, wparam: int, lparam: int) -> bool:
        if msg not in MENSAJES_DE_MENU:
            return False
        if self.cm3:
            resultado = wintypes.LPARAM(0)
            hr = _vcall(self.cm3, 7, ctypes.c_long,           # HandleMenuMsg2
                        (ctypes.c_uint32, wintypes.WPARAM, wintypes.LPARAM,
                         ctypes.POINTER(wintypes.LPARAM)),
                        msg, wparam, lparam, ctypes.byref(resultado))
            return hr == S_OK
        if self.cm2:
            hr = _vcall(self.cm2, 6, ctypes.c_long,           # HandleMenuMsg
                        (ctypes.c_uint32, wintypes.WPARAM, wintypes.LPARAM),
                        msg, wparam, lparam)
            return hr == S_OK
        return False


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", ctypes.c_uint32),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", ctypes.c_uint32),
        ("pt", wintypes.POINT),
    ]


class _FiltroNativoQt:
    """Pone un filtro de eventos nativos de Qt mientras el menú está arriba.

    Qt llama a los filtros desde su propia wndproc, y `TrackPopupMenuEx`
    despacha sus mensajes a la ventana dueña —que es de Qt—, así que pasan por
    acá. Se instala justo antes de mostrar el menú y se saca apenas termina:
    dejarlo puesto metería una llamada de Python en cada mensaje de Windows.
    """

    def __init__(self, handler):
        from PySide6.QtCore import QAbstractNativeEventFilter
        from PySide6.QtWidgets import QApplication

        filtro = self

        class _Filtro(QAbstractNativeEventFilter):
            def nativeEventFilter(self, tipo, mensaje):
                if tipo != b"windows_generic_MSG":
                    return False, 0
                msg = ctypes.cast(int(mensaje), ctypes.POINTER(MSG)).contents
                if filtro.handler(msg.message, msg.wParam, msg.lParam):
                    return True, 0
                return False, 0

        self.handler = handler
        self._app = QApplication.instance()
        self._qt = _Filtro()
        self._app.installNativeEventFilter(self._qt)

    def quitar(self) -> None:
        if self._qt is not None:
            self._app.removeNativeEventFilter(self._qt)
            self._qt = None


def instalar_filtro_qt(handler):
    """Fábrica para pasarle a `show_context_menu` como `instalar_filtro`."""
    return _FiltroNativoQt(handler)


WM_DEVICECHANGE = 0x0219
DBT_DEVICEARRIVAL = 0x8000
DBT_DEVICEREMOVECOMPLETE = 0x8004


def vigilar_unidades(callback):
    """Llama a `callback()` cuando se enchufa o se saca una unidad.

    Éste sí queda instalado toda la sesión, a diferencia del filtro del menú:
    el handler descarta de entrada todo lo que no sea `WM_DEVICECHANGE`, que es
    una comparación de enteros, y nunca consume el mensaje — otros interesados
    también tienen que verlo.
    """

    def handler(msg, wparam, lparam):
        if msg == WM_DEVICECHANGE and wparam in (DBT_DEVICEARRIVAL,
                                                 DBT_DEVICEREMOVECOMPLETE):
            callback()
        return False

    return _FiltroNativoQt(handler)


def context_menu_disponible(paths: list[str]) -> bool:
    """Si el menú real se puede mostrar para este conjunto de rutas.

    Pide que existan y que compartan carpeta madre: `GetUIObjectOf` trabaja
    sobre PIDL hijos de un mismo `IShellFolder`. La vista de rama (Ctrl+B)
    mezcla carpetas, y adentro de un ZIP no hay rutas reales.
    """
    if not paths:
        return False
    try:
        madres = {os.path.dirname(os.path.normpath(p)).lower() for p in paths}
        return len(madres) == 1 and all(os.path.exists(p) for p in paths)
    except OSError:
        return False


def show_context_menu(hwnd: int, paths: list[str], x: int, y: int,
                      extended: bool = False,
                      instalar_filtro=None) -> bool:
    """Muestra el menú del Explorador para `paths` y ejecuta lo que se elija.

    `instalar_filtro` recibe un callable `(msg, wparam, lparam) -> bool` y debe
    devolver un objeto con `.quitar()`; es el enganche para que la ventana de Qt
    reenvíe los mensajes del menú. Si es None, el menú se muestra igual pero los
    submenús de las extensiones pueden salir vacíos.

    Devuelve True si se mostró el menú (se haya elegido algo o no), False si no
    se pudo y hay que caer al menú propio.
    """
    if not context_menu_disponible(paths):
        return False

    # Los PIDL absolutos son nuestros y hay que liberarlos. Los "hijos" que
    # devuelve SHBindToParent apuntan adentro del absoluto correspondiente:
    # liberarlos aparte sería un doble free.
    absolutos = []
    pidls_hijos = []
    carpeta = ctypes.c_void_p()
    menu_com = None
    cm2 = cm3 = None
    hmenu = None
    filtro = None

    try:
        with _Com():
            # 1. PIDL de cada archivo, y el IShellFolder que los contiene.
            for p in paths:
                pidl = _pidl_de(p)
                if not pidl:
                    return False
                absolutos.append(pidl)

            hijo = ctypes.c_void_p()
            hr = shell32.SHBindToParent(
                absolutos[0], ctypes.byref(IID_IShellFolder),
                ctypes.byref(carpeta), ctypes.byref(hijo))
            if hr != S_OK or not carpeta:
                return False
            pidls_hijos.append(hijo)

            for pidl in absolutos[1:]:
                otro_padre = ctypes.c_void_p()
                h = ctypes.c_void_p()
                if shell32.SHBindToParent(pidl, ctypes.byref(IID_IShellFolder),
                                          ctypes.byref(otro_padre),
                                          ctypes.byref(h)) != S_OK:
                    return False
                _release(otro_padre)
                pidls_hijos.append(h)

            # 2. IContextMenu para ese conjunto.
            arreglo = (ctypes.c_void_p * len(pidls_hijos))(
                *[p.value for p in pidls_hijos])
            salida = ctypes.c_void_p()
            hr = _vcall(carpeta, 10, ctypes.c_long,           # GetUIObjectOf
                        (wintypes.HWND, ctypes.c_uint32, ctypes.c_void_p,
                         ctypes.POINTER(GUID), ctypes.c_void_p,
                         ctypes.POINTER(ctypes.c_void_p)),
                        hwnd, len(pidls_hijos), arreglo,
                        ctypes.byref(IID_IContextMenu), None, ctypes.byref(salida))
            if hr != S_OK or not salida:
                return False
            menu_com = salida

            # 3. Llenar el menú. Con Shift aparecen los verbos extendidos,
            #    igual que en el Explorador.
            hmenu = user32.CreatePopupMenu()
            if not hmenu:
                return False
            flags = CMF_NORMAL | CMF_EXPLORE | (CMF_EXTENDEDVERBS if extended else 0)
            hr = _vcall(menu_com, 3, ctypes.c_long,           # QueryContextMenu
                        (wintypes.HMENU, ctypes.c_uint32, ctypes.c_uint32,
                         ctypes.c_uint32, ctypes.c_uint32),
                        hmenu, 0, ID_PRIMERO, ID_ULTIMO, flags)
            if hr < 0:
                return False

            # 4. Los submenús de las extensiones necesitan los mensajes.
            cm3 = _query_interface(menu_com, IID_IContextMenu3)
            cm2 = None if cm3 else _query_interface(menu_com, IID_IContextMenu2)
            if instalar_filtro is not None and (cm2 or cm3):
                filtro = instalar_filtro(_Reenviador(cm2, cm3).manejar)

            # 5. Mostrarlo y ejecutar lo elegido.
            user32.SetForegroundWindow(wintypes.HWND(hwnd))
            elegido = user32.TrackPopupMenuEx(
                wintypes.HMENU(hmenu),
                TPM_RETURNCMD | TPM_LEFTALIGN | TPM_RIGHTBUTTON,
                ctypes.c_int(x), ctypes.c_int(y), wintypes.HWND(hwnd), None)
            # Sin esto el menú puede quedar dibujado hasta el próximo mensaje.
            user32.PostMessageW(wintypes.HWND(hwnd), 0, 0, 0)   # WM_NULL

            if filtro is not None:
                filtro.quitar()
                filtro = None

            if elegido > 0:
                info = CMINVOKECOMMANDINFOEX()
                info.cbSize = ctypes.sizeof(CMINVOKECOMMANDINFOEX)
                info.fMask = CMIC_MASK_UNICODE
                info.hwnd = wintypes.HWND(hwnd)
                # El verbo por número es un entero disfrazado de puntero.
                info.lpVerb = ctypes.cast(
                    ctypes.c_void_p(elegido - ID_PRIMERO), ctypes.c_char_p)
                info.lpVerbW = ctypes.cast(
                    ctypes.c_void_p(elegido - ID_PRIMERO), ctypes.c_wchar_p)
                info.nShow = SW_SHOWNORMAL
                _vcall(menu_com, 4, ctypes.c_long,            # InvokeCommand
                       (ctypes.POINTER(CMINVOKECOMMANDINFOEX),),
                       ctypes.byref(info))
            return True
    except OSError:
        return False
    finally:
        if filtro is not None:
            filtro.quitar()
        if hmenu:
            user32.DestroyMenu(wintypes.HMENU(hmenu))
        _release(cm2)
        _release(cm3)
        _release(menu_com)
        _release(carpeta)
        for pidl in absolutos:
            if pidl:
                ole32.CoTaskMemFree(pidl)
