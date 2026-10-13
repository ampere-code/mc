"""Caché de iconos con dos políticas, según de dónde salga el icono.

La mayoría de los archivos sacan el icono de **su tipo**: todos los `.txt` se
ven igual. Para ésos alcanza con pedirle uno al sistema por extensión y
reusarlo, que es lo que hace que listar un directorio con 5.000 archivos sea
instantáneo.

Pero hay tipos que llevan el icono **adentro** —`.exe`, `.lnk`, `.ico`—, y ahí
esa misma optimización es el bug: el primer programa de la lista le prestaba su
icono a todos los demás. Para esas extensiones la clave del caché es el archivo
y no el tipo.

El costo medido de pedirle al shell el icono de un `.exe` es de ~8,5 ms. Un
directorio con mil ejecutables serían ocho segundos y medio de ventana
congelada, así que no se pueden pedir todos de una. La solución no es un hilo
—`QPixmap` no se puede tocar fuera del hilo de la interfaz—, sino pedirlos de a
poco: la vista sólo consulta las filas que está por dibujar, así que la cola
nunca tiene más que una pantalla, y un temporizador la vacía en tandas cortas
sin que se note.
"""

from __future__ import annotations

from collections import OrderedDict

from PySide6.QtCore import QFileInfo, QObject, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFileIconProvider

from . import platform

# Cuánto se permite trabajar por tanda. Con ~8,5 ms por icono esto es un puñado
# por vuelta: suficiente para que una pantalla se complete en unas décimas y
# poco como para que la interfaz no pierda fluidez.
MS_POR_TANDA = 12

# Tope del caché por archivo. Cada QIcon chico pesa poco, pero un árbol grande
# recorrido entero no debería crecer sin límite.
MAX_POR_ARCHIVO = 4000


class IconCache(QObject):
    """Resuelve iconos y avisa cuando uno que faltaba quedó listo."""

    # Se avisa una vez por tanda y no archivo por archivo: el modelo repinta la
    # columna entera y la vista sólo redibuja las filas visibles, así que
    # afinar más no ahorra nada y cuesta mantener un índice de fila por clave.
    batch_ready = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._provider = QFileIconProvider()
        self._por_tipo: dict[str, QIcon] = {}
        self._por_archivo: OrderedDict[str, QIcon] = OrderedDict()
        self._pendientes: list[tuple[str, str]] = []        # (clave, ruta)
        self._encolados: set[str] = set()
        self._per_file_ext = platform.per_file_icon_extensions()
        self._timer = QTimer(self)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._procesar_tanda)

    # --- consulta --------------------------------------------------------

    @staticmethod
    def clave(path: str, mtime: float) -> str:
        """Identifica una versión concreta de un archivo.

        Va la fecha además de la ruta para que recompilar un `.exe` o cambiarle
        el destino a un acceso directo actualice el icono en vez de servir el
        viejo para siempre.
        """
        return f"{path}|{mtime:.0f}"

    def lleva_icono_propio(self, ext: str) -> bool:
        return ext.lower() in self._per_file_ext

    def folder_icon(self) -> QIcon:
        if "<dir>" not in self._por_tipo:
            self._por_tipo["<dir>"] = self._provider.icon(QFileIconProvider.Folder)
        return self._por_tipo["<dir>"]

    def por_tipo(self, ext: str, path: str, real: bool = True) -> QIcon:
        """Icono del tipo, pedido una sola vez por extensión.

        `real=False` es para rutas que no existen en el disco, como las de
        adentro de un comprimido. Van a otra clave porque el sistema devuelve
        cualquier cosa para una ruta inexistente, y cacheada bajo la extensión
        a secas ese resultado pasaría a ser el icono de todos los archivos de
        ese tipo — el mismo tipo de bug que arreglaba el caché por archivo.
        """
        key = (ext.lower() or "<file>") + ("" if real else "|virtual")
        if key not in self._por_tipo:
            self._por_tipo[key] = self._provider.icon(QFileInfo(path))
        return self._por_tipo[key]

    def por_archivo(self, clave: str, path: str, ext: str) -> QIcon:
        """Icono propio del archivo. Si todavía no está, lo encola y devuelve
        el del tipo, que es una aproximación razonable mientras tanto."""
        icono = self._por_archivo.get(clave)
        if icono is not None:
            self._por_archivo.move_to_end(clave)
            return icono
        if clave not in self._encolados:
            self._encolados.add(clave)
            self._pendientes.append((clave, path))
            if not self._timer.isActive():
                self._timer.start()
        return self.por_tipo(ext, path)

    # --- trabajo de fondo -------------------------------------------------

    def _procesar_tanda(self) -> None:
        import time

        limite = time.perf_counter() + MS_POR_TANDA / 1000.0
        hubo = False
        while self._pendientes and time.perf_counter() < limite:
            clave, path = self._pendientes.pop()        # lo último pedido es lo
            self._encolados.discard(clave)              # que se está mirando
            try:
                icono = self._provider.icon(QFileInfo(path))
                icono.pixmap(16, 16)                    # forzar la extracción acá
            except Exception:                           # noqa: BLE001
                icono = QIcon()
            self._por_archivo[clave] = icono
            while len(self._por_archivo) > MAX_POR_ARCHIVO:
                self._por_archivo.popitem(last=False)
            hubo = True

        if not self._pendientes:
            self._timer.stop()
        if hubo:
            self.batch_ready.emit()

_cache: IconCache | None = None


def cache() -> IconCache:
    global _cache
    if _cache is None:
        _cache = IconCache()
    return _cache
