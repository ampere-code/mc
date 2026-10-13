"""Ayuda de atajos (F1).

Se arma desde datos en vez de tener un bloque HTML por idioma: así hay una sola
tabla que mantener y las traducciones salen del catálogo como el resto.
"""

from __future__ import annotations

from .i18n import t

# (título de sección, [(tecla, acción), ...])
SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    ("Teclas de función", [
        ("F1", "Esta ayuda"),
        ("F2", "Releer el panel"),
        ("F3", "Ver"),
        ("F4", "Editar"),
        ("F5", "Copiar"),
        ("F6", "Mover / renombrar"),
        ("F7", "Crear directorio"),
        ("F8 / Del", "Borrar"),
        ("Shift+F2", "Comparar listas"),
        ("Shift+F4", "Nuevo archivo de texto"),
        ("Shift+F5", "Copiar en el mismo dir"),
        ("Shift+F6", "Renombrar en el sitio"),
        ("Shift+F7", "Crear dir en el otro panel"),
        ("Shift+F8", "Borrar definitivo"),
        ("Shift+F10", "Menú contextual"),
        ("Shift+Esc", "Minimizar"),
    ]),
    ("Alt", [
        ("Alt+F1 / F2", "Unidad izq. / der."),
        ("Alt+F5", "Comprimir"),
        ("Alt+F6", "Descomprimir"),
        ("Alt+F7", "Buscar archivos"),
        ("Alt+Enter", "Propiedades"),
        ("Alt+Shift+F9", "Verificar comprimidos"),
        ("Alt+← / →", "Atrás / adelante"),
        ("Alt+↓", "Historial de directorios"),
        ("Alt+1…9", "Ir a la pestaña N"),
        ("Alt+F11", "Editar la ruta"),
    ]),
    ("Vista y orden", [
        ("Ctrl+F1", "Vista breve"),
        ("Ctrl+F2", "Vista detallada"),
        ("Ctrl+F3", "Ordenar por nombre"),
        ("Ctrl+F4", "Por extensión"),
        ("Ctrl+F5", "Por fecha"),
        ("Ctrl+F6", "Por tamaño"),
        ("Ctrl+F7", "Sin ordenar"),
        ("Ctrl+F10", "Mostrar ocultos"),
        ("Ctrl+Shift+T", "Alternar claro / oscuro"),
    ]),
    ("Navegación", [
        ("Tab", "Cambiar de panel"),
        ("Backspace", "Directorio padre"),
        ("Ctrl+AvPág", "Directorio padre"),
        ("Ctrl+RePág", "Entrar / abrir zip"),
        ("Ctrl+\\", "Ir a la raíz"),
        ("Ctrl+← / →", "Abrir en el otro panel"),
        ("Ctrl+U", "Intercambiar paneles"),
        ("Ctrl+D", "Marcadores"),
        ("Ctrl+B", "Vista de rama"),
        ("Ctrl+Q", "Vista rápida"),
        ("Ctrl+T", "Nueva pestaña"),
        ("Ctrl+W", "Cerrar pestaña"),
        ("Ctrl+Tab", "Pestaña siguiente"),
        ("Ctrl+Shift+Tab", "Pestaña anterior"),
    ]),
    ("Selección", [
        ("Insert", "Marcar y bajar"),
        ("Espacio", "Marcar (calcula el tamaño de la carpeta)"),
        ("Num +", "Marcar por patrón"),
        ("Num -", "Desmarcar por patrón"),
        ("Num *", "Invertir selección"),
        ("Num /", "Limpiar selección"),
        ("Ctrl+Num +", "Marcar todo"),
        ("Ctrl+Num -", "Desmarcar todo"),
        ("Alt+Num +", "Misma extensión"),
        ("Ctrl+A", "Marcar todo"),
    ]),
    ("Portapapeles y consola", [
        ("Ctrl+C / X / V", "Copiar / cortar / pegar"),
        ("Ctrl+Shift+C", "Copiar rutas completas"),
        ("Ctrl+P", "Copiar la ruta del panel"),
        ("Ctrl+E", "Foco en la línea de comandos"),
        ("Ctrl+Enter", "Agregar el nombre a la línea"),
        ("Ctrl+Shift+Enter", "Abrir consola acá"),
    ]),
]

FOOTER = "Escribir letras sobre la lista salta al archivo que empiece así."


def keyboard_help() -> str:
    """HTML de la ayuda, en el idioma activo."""
    parts = ["<style>td { padding: 1px 12px 1px 0; }</style>",
             f"<h3>{t('Atajos de teclado')}</h3>", "<table>"]
    for title, rows in SECTIONS:
        parts.append(f'<tr><td colspan="4"><br><b>{t(title)}</b></td></tr>')
        # Dos columnas de pares tecla/acción por fila, para que entre a lo ancho.
        for i in range(0, len(rows), 2):
            cells = []
            for key, action in rows[i:i + 2]:
                cells.append(f"<td><b>{key}</b></td><td>{t(action)}</td>")
            if len(cells) == 1:
                cells.append("<td></td><td></td>")
            parts.append("<tr>" + "".join(cells) + "</tr>")
    parts.append("</table>")
    parts.append(f"<p><i>{t(FOOTER)}</i></p>")
    return "\n".join(parts)
