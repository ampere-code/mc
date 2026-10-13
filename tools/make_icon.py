"""Genera el icono de Marce Commander.

El motivo es el de la aplicación: dos paneles, el de la izquierda activo. Se
dibuja vectorialmente a cada tamaño en vez de escalar un PNG grande, porque a
16 px una reducción queda barrosa; a los tamaños chicos se omiten los renglones
y quedan sólo los dos bloques, que es lo único que se llega a leer.

    python tools/make_icon.py

Escribe mc/resources/icon.ico (con todos los tamaños) y icon.png (256).
"""

from __future__ import annotations

import os
import struct
import sys

from PySide6.QtCore import QBuffer, QByteArray, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QApplication

SIZES = [16, 24, 32, 48, 64, 128, 256]

BG_TOP = "#2a3140"
BG_BOTTOM = "#161920"
ACCENT = "#3d8bfd"
ACCENT_DIM = "#1e5fc4"
PANEL_IDLE = "#8b94a3"
ROW_ON = "#eaf2ff"
ROW_OFF = "#5b6473"


def draw(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)

    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)

    s = float(size)
    radius = s * 0.22

    # Fondo: cuadrado redondeado con degradado vertical.
    grad = QLinearGradient(0, 0, 0, s)
    grad.setColorAt(0.0, QColor(BG_TOP))
    grad.setColorAt(1.0, QColor(BG_BOTTOM))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(grad))
    p.drawRoundedRect(QRectF(0, 0, s, s), radius, radius)

    # Borde sutil, sólo cuando hay píxeles para que se note.
    if size >= 32:
        p.setBrush(Qt.NoBrush)
        pen = QPen(QColor(255, 255, 255, 28))
        pen.setWidthF(max(1.0, s * 0.012))
        p.setPen(pen)
        inset = pen.widthF() / 2
        p.drawRoundedRect(
            QRectF(inset, inset, s - 2 * inset, s - 2 * inset), radius, radius)

    # Dos paneles.
    margin = s * 0.16
    gap = s * 0.06
    top = s * 0.22
    height = s - top - margin
    width = (s - 2 * margin - gap) / 2
    panel_radius = max(1.0, s * 0.05)

    left = QRectF(margin, top, width, height)
    right = QRectF(margin + width + gap, top, width, height)

    p.setPen(Qt.NoPen)
    left_grad = QLinearGradient(left.topLeft(), left.bottomLeft())
    left_grad.setColorAt(0.0, QColor(ACCENT))
    left_grad.setColorAt(1.0, QColor(ACCENT_DIM))
    p.setBrush(QBrush(left_grad))
    p.drawRoundedRect(left, panel_radius, panel_radius)

    p.setBrush(QColor(PANEL_IDLE))
    p.setOpacity(0.38)
    p.drawRoundedRect(right, panel_radius, panel_radius)
    p.setOpacity(1.0)

    # Barra de título del panel activo: la franja de arriba.
    if size >= 24:
        bar = QRectF(margin, top - s * 0.11, width, s * 0.07)
        p.setBrush(QColor(ACCENT))
        p.drawRoundedRect(bar, panel_radius * 0.6, panel_radius * 0.6)

    # Renglones de archivos. Debajo de 48 px no entran y ensucian.
    if size >= 48:
        rows = 4
        row_h = height * 0.085
        step = height / (rows + 1.6)
        for i in range(rows):
            y = top + step * (i + 0.55)
            w_left = width * (0.72 if i % 2 == 0 else 0.52)
            w_right = width * (0.62 if i % 2 == 0 else 0.78)
            p.setBrush(QColor(ROW_ON))
            p.setOpacity(0.92 if i == 1 else 0.55)
            p.drawRoundedRect(
                QRectF(left.x() + width * 0.12, y, w_left, row_h),
                row_h / 2, row_h / 2)
            p.setBrush(QColor(ROW_OFF))
            p.setOpacity(0.85)
            p.drawRoundedRect(
                QRectF(right.x() + width * 0.12, y, w_right, row_h),
                row_h / 2, row_h / 2)
        p.setOpacity(1.0)

    p.end()
    return img


def png_bytes(img: QImage) -> bytes:
    # El QByteArray va en una variable propia: si se pasa como temporal, Python
    # lo libera y el QBuffer queda apuntando a memoria muerta (segfault).
    store = QByteArray()
    buf = QBuffer(store)
    buf.open(QBuffer.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return bytes(store)


def write_ico(path: str, images: list[QImage]) -> None:
    """Arma un .ico con las entradas comprimidas en PNG (soportado desde Vista)."""
    payloads = [png_bytes(i) for i in images]
    count = len(images)
    header = struct.pack("<HHH", 0, 1, count)
    offset = len(header) + 16 * count

    entries, blob = b"", b""
    for img, data in zip(images, payloads):
        w = 0 if img.width() >= 256 else img.width()
        h = 0 if img.height() >= 256 else img.height()
        entries += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
        blob += data

    with open(path, "wb") as fh:
        fh.write(header + entries + blob)


def main() -> int:
    # QPainter sobre QImage necesita una aplicación viva. Se la deja en una
    # global: destruirla al salir de la función hace que Qt desarme sus
    # recursos en mal orden y el proceso termine con segfault.
    global _app
    _app = QApplication(sys.argv)
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "mc", "resources")
    os.makedirs(out_dir, exist_ok=True)

    images = [draw(s) for s in SIZES]
    ico = os.path.join(out_dir, "icon.ico")
    write_ico(ico, images)
    images[-1].save(os.path.join(out_dir, "icon.png"), "PNG")

    print(f"icon.ico  {os.path.getsize(ico):,} bytes  tamaños: {SIZES}")
    print(f"icon.png  256x256")
    return 0


if __name__ == "__main__":
    sys.exit(main())
