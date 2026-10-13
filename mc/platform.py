"""Todo lo que cambia entre Windows, Linux y macOS, en un solo lugar.

El resto de la aplicación no importa `ctypes` ni mira `sys.platform`: le pide
las cosas a este módulo. La razón concreta es que `ctypes.wintypes` no se puede
ni importar fuera de Windows —define `VARIANT_BOOL` con `_type_ = "v"`, un
código que sólo existe en la build de Windows de `_ctypes`—, así que cualquier
`from ctypes import wintypes` a nivel de módulo rompe la aplicación entera al
arrancar en Linux o Mac. Acá ese import vive dentro de las funciones que lo
necesitan, que sólo se llaman en Windows.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")


# --- ubicación de la configuración -------------------------------------

def config_dir() -> Path:
    """Directorio de configuración según la convención de cada sistema."""
    if IS_WINDOWS:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        path = Path(base) / "MarceCommander"
    elif IS_MACOS:
        path = Path.home() / "Library" / "Application Support" / "MarceCommander"
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
        path = Path(base) / "marcecommander"
    path.mkdir(parents=True, exist_ok=True)
    return path


# --- unidades y puntos de montaje ---------------------------------------

def list_drives() -> list[tuple[str, str]]:
    """[(etiqueta, ruta)] para la barra de unidades.

    En Windows son las letras; en Unix no existe tal cosa, así que se ofrece la
    raíz, el home y los puntos de montaje donde el sistema engancha los discos
    extraíbles, que es el equivalente útil.
    """
    if IS_WINDOWS:
        import ctypes

        mask = ctypes.windll.kernel32.GetLogicalDrives()
        return [(f"{chr(65 + i)}:", f"{chr(65 + i)}:\\")
                for i in range(26) if mask & (1 << i)]

    drives = [("/", "/"), ("~", str(Path.home()))]
    roots = ["/Volumes"] if IS_MACOS else [
        f"/media/{os.environ.get('USER', '')}", "/media", "/mnt", "/run/media"]
    for root in roots:
        try:
            for entry in sorted(os.scandir(root), key=lambda e: e.name):
                if entry.is_dir() and not entry.name.startswith("."):
                    drives.append((entry.name, entry.path))
        except OSError:
            continue
    # Sin duplicados, conservando el orden.
    seen, out = set(), []
    for label, path in drives:
        if path not in seen:
            seen.add(path)
            out.append((label, path))
    return out


# --- abrir cosas ---------------------------------------------------------

def open_with_default_app(path: str) -> None:
    """Abre un archivo con la aplicación asociada del sistema."""
    if IS_WINDOWS:
        os.startfile(path)                                  # noqa: S606
    elif IS_MACOS:
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def reveal_in_file_manager(path: str) -> None:
    """Muestra el elemento en el explorador de archivos del sistema."""
    path = os.path.normpath(path)
    if IS_WINDOWS:
        if os.path.isdir(path):
            os.startfile(path)                              # noqa: S606
        else:
            subprocess.Popen(["explorer", "/select,", path])
        return
    if IS_MACOS:
        subprocess.Popen(["open", "-R", path] if os.path.isfile(path)
                         else ["open", path])
        return
    # En Linux no hay una forma única; se prueba lo que haya instalado.
    target = path if os.path.isdir(path) else os.path.dirname(path)
    for cmd in (["nautilus", "--select", path], ["dolphin", "--select", path],
                ["nemo", path], ["thunar", target]):
        if shutil.which(cmd[0]):
            subprocess.Popen(cmd)
            return
    subprocess.Popen(["xdg-open", target])


def default_ui_font() -> str:
    """Fuente de interfaz nativa de cada escritorio."""
    if IS_WINDOWS:
        return "Segoe UI"
    if IS_MACOS:
        return "SF Pro Text, Helvetica Neue"
    return "Cantarell, Ubuntu, DejaVu Sans"


def default_mono_font() -> str:
    """Monoespaciada para las listas de archivos y el visor."""
    if IS_WINDOWS:
        return "Consolas"
    if IS_MACOS:
        return "SF Mono, Menlo"
    return "DejaVu Sans Mono, Liberation Mono, monospace"


def default_terminal() -> str:
    if IS_WINDOWS:
        return "cmd.exe"
    if IS_MACOS:
        return "Terminal.app"
    return os.environ.get("SHELL", "/bin/bash")


def open_terminal(cwd: str, configured: str = "") -> None:
    """Abre una consola en el directorio dado."""
    term = configured.strip() or default_terminal()
    if IS_WINDOWS:
        subprocess.Popen(term, cwd=cwd, shell=True)
        return
    if IS_MACOS:
        subprocess.Popen(["open", "-a", term, cwd])
        return
    for cmd in (["x-terminal-emulator"], ["gnome-terminal"], ["konsole"],
                ["xfce4-terminal"], ["alacritty"], ["xterm"]):
        if shutil.which(cmd[0]):
            subprocess.Popen(cmd, cwd=cwd)
            return
    subprocess.Popen([term], cwd=cwd)


def run_shell_command(line: str, cwd: str) -> None:
    """Ejecuta una línea de la línea de comandos del panel."""
    if IS_WINDOWS:
        subprocess.Popen(line, cwd=cwd, shell=True)
    else:
        subprocess.Popen([os.environ.get("SHELL", "/bin/sh"), "-c", line], cwd=cwd)


# --- papelera ------------------------------------------------------------

def send_to_trash(paths: list[str]) -> tuple[bool, str]:
    """Manda a la papelera del sistema. Devuelve (ok, mensaje de error)."""
    if not paths:
        return True, ""
    if IS_WINDOWS:
        return _trash_windows(paths)
    if IS_MACOS:
        return _trash_macos(paths)
    return _trash_freedesktop(paths)


def _trash_windows(paths: list[str]) -> tuple[bool, str]:
    import ctypes
    from ctypes import wintypes

    FO_DELETE = 0x0003
    FOF_SILENT = 0x0004
    FOF_NOCONFIRMATION = 0x0010
    FOF_ALLOWUNDO = 0x0040
    FOF_NOERRORUI = 0x0400

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", ctypes.c_uint16),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    # pFrom es una lista terminada en doble NUL.
    buf = "\0".join(os.path.abspath(p) for p in paths) + "\0\0"
    op = SHFILEOPSTRUCTW()
    op.hwnd = None
    op.wFunc = FO_DELETE
    op.pFrom = buf
    op.pTo = None
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
    op.fAnyOperationsAborted = False
    op.hNameMappings = None
    op.lpszProgressTitle = None
    rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if rc != 0:
        return False, f"SHFileOperation devolvió 0x{rc:X}"
    if op.fAnyOperationsAborted:
        return False, "operación cancelada"
    return True, ""


def _trash_macos(paths: list[str]) -> tuple[bool, str]:
    # Finder es quien sabe mover a la papelera conservando el "poner de vuelta".
    items = ", ".join(f'POSIX file "{os.path.abspath(p)}"' for p in paths)
    script = f'tell application "Finder" to delete {{{items}}}'
    try:
        res = subprocess.run(["osascript", "-e", script],
                             capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    if res.returncode != 0:
        return False, (res.stderr or "osascript falló").strip()
    return True, ""


def _trash_freedesktop(paths: list[str]) -> tuple[bool, str]:
    """Papelera según la especificación freedesktop.org.

    Se implementa a mano en vez de depender de `gio trash`, que no está en todos
    los escritorios. El archivo .trashinfo es lo que permite restaurar después.
    """
    from datetime import datetime
    from urllib.parse import quote

    home_trash = Path(
        os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")) / "Trash"
    errors = []
    for src in paths:
        src = os.path.abspath(src)
        try:
            trash = _trash_dir_for(src, home_trash)
            files_dir, info_dir = trash / "files", trash / "info"
            files_dir.mkdir(parents=True, exist_ok=True)
            info_dir.mkdir(parents=True, exist_ok=True)

            # Nombre único: la papelera puede ya tener algo que se llame igual.
            name = os.path.basename(src.rstrip("/"))
            stem, suffix = os.path.splitext(name)
            target = files_dir / name
            n = 1
            while target.exists() or (info_dir / f"{target.name}.trashinfo").exists():
                target = files_dir / f"{stem}.{n}{suffix}"
                n += 1

            info = (info_dir / f"{target.name}.trashinfo")
            info.write_text(
                "[Trash Info]\n"
                f"Path={quote(src)}\n"
                f"DeletionDate={datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}\n",
                encoding="utf-8")
            try:
                os.rename(src, target)
            except OSError:
                # Distinto sistema de archivos: copiar y borrar.
                if os.path.isdir(src):
                    shutil.copytree(src, target, symlinks=True)
                    shutil.rmtree(src)
                else:
                    shutil.copy2(src, target)
                    os.remove(src)
        except OSError as exc:
            errors.append(f"{src}: {exc.strerror or exc}")
    return (not errors), "; ".join(errors)


def _trash_dir_for(path: str, home_trash: Path) -> Path:
    """La papelera del volumen donde vive el archivo, o la del home."""
    try:
        if os.stat(path).st_dev == os.stat(Path.home()).st_dev:
            return home_trash
    except OSError:
        return home_trash
    # Volumen externo: subir hasta el punto de montaje y usar .Trash-<uid>.
    p = Path(path).resolve()
    while not os.path.ismount(p) and p.parent != p:
        p = p.parent
    candidate = p / f".Trash-{os.getuid()}"
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate
    except OSError:
        return home_trash


# --- atributos de archivo ------------------------------------------------

def attribute_string(st, name: str) -> str:
    """Columna 'Atr': en Windows r/a/h/s, en Unix los permisos del dueño."""
    if IS_WINDOWS:
        import stat as st_mod

        out = []
        fa = getattr(st, "st_file_attributes", 0)
        if fa & st_mod.FILE_ATTRIBUTE_READONLY:
            out.append("r")
        if fa & st_mod.FILE_ATTRIBUTE_ARCHIVE:
            out.append("a")
        if fa & st_mod.FILE_ATTRIBUTE_HIDDEN or name.startswith("."):
            out.append("h")
        if fa & st_mod.FILE_ATTRIBUTE_SYSTEM:
            out.append("s")
        return "".join(out)

    mode = st.st_mode
    return ("r" if mode & 0o400 else "-") + \
           ("w" if mode & 0o200 else "-") + \
           ("x" if mode & 0o100 else "-")


def is_hidden(st, name: str) -> bool:
    if IS_WINDOWS:
        import stat as st_mod

        fa = getattr(st, "st_file_attributes", 0)
        if fa & (st_mod.FILE_ATTRIBUTE_HIDDEN | st_mod.FILE_ATTRIBUTE_SYSTEM):
            return True
    return name.startswith(".")


def set_windows_attributes(path: str, flags_on: int, flags_off: int) -> str:
    """Cambia atributos en Windows. Devuelve '' si salió bien, o el error."""
    import ctypes

    get = ctypes.windll.kernel32.GetFileAttributesW
    setf = ctypes.windll.kernel32.SetFileAttributesW
    cur = get(path)
    if cur == 0xFFFFFFFF:
        return "no se pudieron leer los atributos"
    new = (cur | flags_on) & ~flags_off
    if new != cur and not setf(path, new):
        return "no se pudieron cambiar los atributos"
    return ""


def set_unix_mode(path: str, mode: int) -> str:
    try:
        os.chmod(path, mode)
    except OSError as exc:
        return exc.strerror or str(exc)
    return ""


# --- integración con el escritorio ---------------------------------------

def prefers_dark() -> bool:
    """Si el escritorio está configurado en tema oscuro."""
    if IS_WINDOWS:
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            with key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0
        except OSError:
            return True
    if IS_MACOS:
        try:
            res = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"],
                                 capture_output=True, text=True, timeout=5)
            return "dark" in res.stdout.lower()
        except (OSError, subprocess.SubprocessError):
            return True
    # Linux: GNOME y derivados exponen la preferencia por gsettings.
    try:
        res = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            capture_output=True, text=True, timeout=5)
        if res.returncode == 0 and res.stdout.strip():
            return "dark" in res.stdout.lower()
    except (OSError, subprocess.SubprocessError):
        pass
    return True


def apply_titlebar(widget, dark: bool) -> None:
    """Pone la barra de título nativa en oscuro. Sólo hace algo en Windows.

    DWMWA_USE_IMMERSIVE_DARK_MODE es 20 desde la build 18985 y era 19 antes; se
    prueba el 20 y sólo se cae al 19 si devuelve error, porque en builds nuevas
    el 19 significa otra cosa. Cambiar el atributo no repinta el marco solo: hay
    que avisar con SWP_FRAMECHANGED.

    Límite conocido: el atributo sólo *fuerza* el modo oscuro. Pasar 0 no pinta
    la barra de claro, sino que devuelve el marco al default del sistema; con
    Windows en tema oscuro, el tema claro de MC convive con una barra oscura.

    En Linux y macOS el marco lo dibuja el escritorio según su propio tema y no
    hay nada que hacer desde la aplicación.
    """
    if not IS_WINDOWS:
        return
    try:
        import ctypes
        from ctypes import wintypes

        hwnd = wintypes.HWND(int(widget.winId()))
        value = ctypes.c_int(1 if dark else 0)
        ok = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, ctypes.c_uint(20), ctypes.byref(value), ctypes.sizeof(value))
        if ok != 0:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, ctypes.c_uint(19), ctypes.byref(value), ctypes.sizeof(value))

        SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_FRAMECHANGED = 1, 2, 4, 0x20
        ctypes.windll.user32.SetWindowPos(
            hwnd, None, 0, 0, 0, 0,
            SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED)
    except Exception:
        pass
