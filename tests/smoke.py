"""Pruebas funcionales sin interfaz. Corren igual en Windows, Linux y macOS.

    python tests/smoke.py

Usa la plataforma offscreen de Qt, así que no necesita servidor gráfico.
Devuelve 0 si todo pasa.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
import zipfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])

from mc import platform  # noqa: E402
from mc import archive  # noqa: E402
from mc.compare import (  # noqa: E402
    compare_panels, compute_checksums, verify_checksums,
)
from mc.fsmodel import SORT_NAME, SORT_SIZE, list_directory  # noqa: E402
from mc.ops import CopyMoveWorker, DeleteWorker, scan  # noqa: E402
from mc.panel import Panel  # noqa: E402
from mc.search import SearchWorker  # noqa: E402

fails: list[str] = []


def check(name: str, cond: bool, extra="") -> None:
    print(("  ok    " if cond else "  FALLA ") + f"{name} {extra}")
    if not cond:
        fails.append(name)


def write(path: str, data: bytes) -> None:
    with open(path, "wb") as fh:
        fh.write(data)


root = tempfile.mkdtemp(prefix="mctest_")
src = os.path.join(root, "origen")
dst = os.path.join(root, "destino")
os.makedirs(os.path.join(src, "sub", "hondo"))
os.makedirs(dst)
write(os.path.join(src, "a.txt"), b"a" * 100)
write(os.path.join(src, "b.log"), b"b" * 5000)
write(os.path.join(src, "c.txt"), b"c" * 20)
write(os.path.join(src, "sub", "d.txt"), b"d" * 10)
write(os.path.join(src, "sub", "hondo", "e.bin"), bytes(range(256)) * 10)

print(f"\nSistema: {sys.platform}   Python {sys.version.split()[0]}")

print("\n[0] capa de plataforma")
check("detecta un solo sistema",
      sum((platform.IS_WINDOWS, platform.IS_LINUX, platform.IS_MACOS)) == 1,
      f"win={platform.IS_WINDOWS} linux={platform.IS_LINUX} mac={platform.IS_MACOS}")
cfg = platform.config_dir()
check("directorio de configuración existe", cfg.is_dir(), str(cfg))
drives = platform.list_drives()
check("lista unidades o puntos de montaje", len(drives) > 0 and
      all(len(d) == 2 for d in drives), drives[:3])
check("las rutas de unidad existen", all(os.path.isdir(p) for _, p in drives),
      [p for _, p in drives if not os.path.isdir(p)])
check("fuentes por defecto no vacías",
      bool(platform.default_ui_font()) and bool(platform.default_mono_font()),
      f"{platform.default_ui_font()} / {platform.default_mono_font()}")
st = os.stat(os.path.join(src, "a.txt"))
attrs = platform.attribute_string(st, "a.txt")
check("cadena de atributos del sistema", isinstance(attrs, str), repr(attrs))
check("detecta ocultos por punto", platform.is_hidden(st, ".oculto"))

print("\n[1] panel: listado, navegación, orden")
p = Panel("left", src)
names = [e.name for e in p.model.entries]
check("lista el contenido",
      set(names) >= {"..", "a.txt", "b.log", "c.txt", "sub"}, names)
check("'..' va primero", p.model.entries[0].is_parent)
check("carpetas antes que archivos", p.model.entries[1].name == "sub")

p.set_sort(SORT_SIZE, reverse=True)
files = [e.name for e in p.model.entries if not e.is_dir and not e.is_parent]
check("ordena por tamaño desc", files == ["b.log", "a.txt", "c.txt"], files)
p.set_sort(SORT_NAME, reverse=False)

p.set_path(os.path.join(src, "sub"))
check("entra al subdirectorio", os.path.basename(p.path) == "sub", p.path)
p.go_parent()
check("vuelve al padre", os.path.normcase(p.path) == os.path.normcase(src), p.path)
p.go_back()
check("atrás funciona", os.path.basename(p.path) == "sub", p.path)
p.go_forward()
check("adelante funciona", os.path.normcase(p.path) == os.path.normcase(src))

print("\n[2] marcado")
p.mark_pattern(["*.txt"], True)
marcados = sorted(e.name for e in p.model.marked_entries())
check("marca por patrón *.txt", marcados == ["a.txt", "c.txt"], marcados)
check("selección devuelve lo marcado", len(p.selected_entries()) == 2)
p.invert_marks()
check("invierte la selección",
      sorted(e.name for e in p.model.marked_entries()) == ["b.log", "sub"])
p.clear_marks()
check("limpia la selección", not p.model.marked_entries())
p.set_cursor_row(1)
check("sin marcas usa el cursor", len(p.selected_entries()) == 1)

print("\n[3] copiar")
wk = CopyMoveWorker([os.path.join(src, "a.txt"), os.path.join(src, "sub")], dst, False)
wk.policy = 1
wk.run()
check("copia el archivo", os.path.isfile(os.path.join(dst, "a.txt")))
check("copia el árbol completo",
      os.path.isfile(os.path.join(dst, "sub", "hondo", "e.bin")))
with open(os.path.join(dst, "a.txt"), "rb") as fh:
    check("conserva el contenido", fh.read() == b"a" * 100)
check("sin errores", not wk.errors, wk.errors)

print("\n[4] copiar renombrando")
wk = CopyMoveWorker([os.path.join(src, "c.txt")], dst, False, rename_to="nuevo.txt")
wk.policy = 1
wk.run()
check("copia con otro nombre", os.path.isfile(os.path.join(dst, "nuevo.txt")))

print("\n[5] mover")
mover = os.path.join(root, "mover")
os.makedirs(mover)
write(os.path.join(mover, "m.txt"), b"m" * 50)
wk = CopyMoveWorker([os.path.join(mover, "m.txt")], dst, True)
wk.policy = 1
wk.run()
check("el destino existe", os.path.isfile(os.path.join(dst, "m.txt")))
check("el origen desapareció", not os.path.exists(os.path.join(mover, "m.txt")))

print("\n[6] borrar definitivo")
wk = DeleteWorker([os.path.join(dst, "sub")], to_recycle=False)
wk.run()
check("borra el árbol recursivamente", not os.path.exists(os.path.join(dst, "sub")))
check("sin errores al borrar", not wk.errors, wk.errors)

print("\n[7] papelera del sistema")
basura = os.path.join(root, "basura.txt")
write(basura, b"a la papelera")
ok, msg = platform.send_to_trash([basura])
check("manda a la papelera", ok, msg)
check("desaparece del origen", not os.path.exists(basura))

print("\n[8] zip: comprimir, listar, extraer, verificar")
zp = os.path.join(root, "paquete.zip")
wk = archive.PackWorker([src], zp, root)
wk.run()
check("crea el zip", os.path.isfile(zp) and zipfile.is_zipfile(zp))
entradas = archive.list_zip(zp, "origen/")
nombres = sorted(e.name for e in entradas if not e.is_parent)
check("lista un nivel adentro",
      nombres == ["a.txt", "b.log", "c.txt", "sub"], nombres)
outdir = os.path.join(root, "salida")
os.makedirs(outdir)
wk = archive.UnpackWorker([zp], outdir)
wk.run()
check("extrae todo",
      os.path.isfile(os.path.join(outdir, "origen", "sub", "hondo", "e.bin")))
wk = archive.TestWorker([zp])
wk.run()
check("verifica integridad", not wk.errors, wk.errors)

print("\n[9] zip-slip")
malicioso = os.path.join(root, "malo.zip")
with zipfile.ZipFile(malicioso, "w") as zf:
    zf.writestr("../../escapado.txt", "no debería salir")
safe_out = os.path.join(root, "safe")
os.makedirs(safe_out)
wk = archive.UnpackWorker([malicioso], safe_out)
wk.run()
escapado = os.path.abspath(os.path.join(root, "..", "escapado.txt"))
check("rechaza rutas que escapan",
      not os.path.exists(escapado) and len(wk.errors) == 1, wk.errors)

print("\n[10] comparar paneles")
izq, der = os.path.join(root, "izq"), os.path.join(root, "der")
os.makedirs(izq)
os.makedirs(der)
write(os.path.join(izq, "igual.txt"), b"x" * 10)
write(os.path.join(der, "igual.txt"), b"x" * 10)
t = time.time() - 10000
os.utime(os.path.join(izq, "igual.txt"), (t, t))
os.utime(os.path.join(der, "igual.txt"), (t, t))
write(os.path.join(izq, "solo_izq.txt"), b"y")
write(os.path.join(der, "solo_der.txt"), b"z")
write(os.path.join(izq, "nuevo.txt"), b"nuevo")
write(os.path.join(der, "nuevo.txt"), b"viejo")
os.utime(os.path.join(der, "nuevo.txt"), (t, t))
lm, rm = compare_panels(list_directory(izq), list_directory(der))
lnames = sorted(os.path.basename(x) for x in lm)
rnames = sorted(os.path.basename(x) for x in rm)
check("marca lo que falta y lo más nuevo",
      lnames == ["nuevo.txt", "solo_izq.txt"], lnames)
check("marca lo que falta del otro lado", rnames == ["solo_der.txt"], rnames)
check("lo idéntico queda sin marcar", "igual.txt" not in lnames + rnames)

print("\n[11] checksums")
texto = compute_checksums([os.path.join(izq, "igual.txt")], izq)
sums = os.path.join(izq, "c.sha256")
with open(sums, "w", encoding="utf-8") as fh:
    fh.write(texto)
ok_, bad, missing = verify_checksums(sums)
check("verifica correctos", len(ok_) == 1 and not bad and not missing)
write(os.path.join(izq, "igual.txt"), b"CAMBIADO")
ok_, bad, missing = verify_checksums(sums)
check("detecta el cambio", len(bad) == 1, (ok_, bad, missing))

print("\n[12] buscar")
res: list[str] = []
sw = SearchWorker(src, ["*.txt"], "", True, False, False)
sw.found.connect(lambda p_, d, s, m: res.append(p_))
sw.run()
check("encuentra recursivamente", len(res) == 3,
      sorted(os.path.basename(x) for x in res))
res.clear()
sw = SearchWorker(src, ["*"], "ccc", True, False, False)
sw.found.connect(lambda p_, d, s, m: res.append(p_))
sw.run()
check("busca por contenido",
      [os.path.basename(x) for x in res] == ["c.txt"],
      [os.path.basename(x) for x in res])

print("\n[13] zip abierto en el panel")
p2 = Panel("right", root)
check("abre el zip como carpeta", p2.set_path(zp))
check("está adentro del comprimido", p2.in_archive)
p2.go_parent()
check("sale del comprimido", not p2.in_archive)

print("\n[14] ventana principal y temas")
from mc import theme  # noqa: E402
from mc.mainwindow import MainWindow  # noqa: E402

for name in ("dark", "light", "auto"):
    theme.apply(app, name)
    check(f"tema '{name}' aplica", bool(app.styleSheet()), theme.current().name)
w = MainWindow()
w.show()
check("ventana construida", w.isVisible())
check("comandos registrados", len(w.commands) >= 85, len(w.commands))
w.cmd_set_theme("light")
check("cambia de tema en caliente", theme.current().name == "light")
w.close()

print("\n[15] idiomas")
import ast  # noqa: E402

from mc import i18n  # noqa: E402
from mc.help import FOOTER, SECTIONS, keyboard_help  # noqa: E402

mc_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mc")


def literal_keys() -> set[str]:
    """Toda clave pasada a t() como literal, sacada del AST de cada módulo."""
    found: set[str] = set()
    for fn in sorted(os.listdir(mc_dir)):
        if not fn.endswith(".py") or fn == "i18n.py":
            continue
        with open(os.path.join(mc_dir, fn), encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=fn)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name) and node.func.id == "t"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                found.add(node.args[0].value)
    return found


keys = literal_keys()
keys |= {s for s, _ in SECTIONS}
keys |= {a for _, rows in SECTIONS for _, a in rows}
keys.add(FOOTER)
missing = sorted(k for k in keys if k not in i18n.EN)
check(f"las {len(keys)} claves usadas están en el catálogo inglés",
      not missing, missing[:6])

# Los marcadores con nombre tienen que coincidir entre español e inglés, o el
# .format() de la traducción fallaría en tiempo de ejecución.
import string as _string  # noqa: E402


def fields(text: str) -> set[str]:
    return {f for _, f, _, _ in _string.Formatter().parse(text) if f}


mismatched = [k for k, v in i18n.EN.items() if fields(k) != fields(v)]
check("los marcadores {…} coinciden en ambos idiomas", not mismatched, mismatched[:5])

i18n.set_language("en")
check("t() traduce al inglés", i18n.t("Copiar") == "Copy", i18n.t("Copiar"))
check("t() formatea con marcadores",
      i18n.t("{n} elemento(s) procesado(s).", n=7) == "7 item(s) processed.",
      i18n.t("{n} elemento(s) procesado(s).", n=7))
check("una clave ausente cae al español",
      i18n.t("Texto que no está en el catálogo") == "Texto que no está en el catálogo")
check("la ayuda se arma en inglés", "Function keys" in keyboard_help())
i18n.set_language("es")
check("t() vuelve al español", i18n.t("Copiar") == "Copiar")
check("la ayuda se arma en español", "Teclas de función" in keyboard_help())
check("auto resuelve a un idioma soportado", i18n.resolve("auto") in i18n.LANGUAGES,
      i18n.resolve("auto"))

shutil.rmtree(root, ignore_errors=True)

# Desarme explícito de los widgets antes de salir. Si se deja que el intérprete
# los destruya en su propio orden al terminar, PySide6 puede liberar el
# QApplication con widgets todavía vivos y el proceso muere con SIGSEGV: en
# Python 3.12 el orden sale favorable y no se nota, pero en 3.10 el script
# imprimía "FALLAS: 0" y devolvía 139.
for _widget in (p, p2, w):
    _widget.close()
    _widget.deleteLater()
app.processEvents()

print("\n" + "=" * 54)
print(f"FALLAS: {len(fails)}" + ("  ->  " + ", ".join(fails) if fails else "  (todo bien)"))

# Salida normal, no os._exit: terminar el proceso de golpe mientras el proveedor
# de iconos del shell de Windows todavía tiene hilos COM vivos produce un
# access violation, y el script devolvería código de crash habiendo pasado todo.
sys.exit(1 if fails else 0)
