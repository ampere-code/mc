#!/usr/bin/env bash
# Lanzador de Marce Commander para Linux y macOS.
# Equivalente de mc.cmd en Windows. Acepta hasta dos rutas: izquierda y derecha.
#
#   ./mc.sh
#   ./mc.sh ~/proyectos /mnt/backup
#
# Si existe un entorno virtual en .venv lo usa; si no, cae al Python del
# sistema. install.sh crea ese .venv.
set -euo pipefail

# Resolver el directorio real del script aunque se lo invoque por un symlink
# (install.sh deja uno en ~/.local/bin/mc que apunta acá).
origen="${BASH_SOURCE[0]}"
while [ -L "$origen" ]; do
    destino="$(readlink "$origen")"
    case "$destino" in
        /*) origen="$destino" ;;
        *)  origen="$(cd -P "$(dirname "$origen")" && pwd)/$destino" ;;
    esac
done
RAIZ="$(cd -P "$(dirname "$origen")" && pwd)"

if [ -x "$RAIZ/.venv/bin/python" ]; then
    PYTHON="$RAIZ/.venv/bin/python"
elif command -v python3 > /dev/null 2>&1; then
    PYTHON="$(command -v python3)"
else
    echo "mc: no encuentro Python 3. Instalalo o corré ./install.sh" >&2
    exit 1
fi

if ! "$PYTHON" -c "import PySide6" > /dev/null 2>&1; then
    echo "mc: falta PySide6 para $PYTHON." >&2
    echo "    Corré ./install.sh, o bien: $PYTHON -m pip install PySide6" >&2
    exit 1
fi

cd "$RAIZ"
exec "$PYTHON" -m mc "$@"
