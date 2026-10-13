#!/usr/bin/env bash
# Instalador de Marce Commander para Linux.
#
#   ./install.sh                 instalación completa
#   ./install.sh --no-deps       saltear los paquetes del sistema
#   ./install.sh --uninstall     deshacer
#   ./install.sh --help
#
# Hace cuatro cosas: instala las bibliotecas que el plugin gráfico de Qt
# necesita, arma un entorno virtual con PySide6, deja el comando `mc` en
# ~/.local/bin y registra la aplicación en el menú del escritorio.
#
# No corre como root: sólo usa sudo para instalar paquetes, y avisa antes.
set -euo pipefail

RAIZ="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
APPS_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
DESKTOP="$APPS_DIR/marcecommander.desktop"
ENLACE="$BIN_DIR/mc"

rojo()  { printf '\033[31m%s\033[0m\n' "$*"; }
verde() { printf '\033[32m%s\033[0m\n' "$*"; }
info()  { printf '\033[1m==>\033[0m %s\n' "$*"; }

# --- bibliotecas del sistema ------------------------------------------------
#
# Qt trae sus propias librerías, pero su plugin de plataforma xcb se enlaza
# contra éstas. Sin ellas MC arranca y muere con "could not load the Qt
# platform plugin xcb". La lista de Debian está verificada mirando con ldd qué
# le falta a libqxcb.so; las otras distribuciones son el equivalente conocido,
# pero no están probadas.

DEB_PKGS=(
    python3-venv
    libgl1 libegl1 libdbus-1-3 libglib2.0-0 libfontconfig1 libfreetype6
    libxkbcommon0 libxkbcommon-x11-0 libx11-6 libx11-xcb1 libxcb1
    libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1
    libxcb-randr0 libxcb-render0 libxcb-render-util0 libxcb-shape0
    libxcb-shm0 libxcb-sync1 libxcb-util1 libxcb-xfixes0 libxcb-xkb1
)
RPM_PKGS=(
    python3-pip mesa-libGL mesa-libEGL dbus-libs glib2 fontconfig freetype
    libxkbcommon libxkbcommon-x11 libX11 libX11-xcb libxcb
    xcb-util-cursor xcb-util-wm xcb-util-image xcb-util-keysyms
    xcb-util-renderutil
)
ARCH_PKGS=(
    python libglvnd dbus glib2 fontconfig freetype2
    libxkbcommon libxkbcommon-x11 libx11 libxcb
    xcb-util-cursor xcb-util-wm xcb-util-image xcb-util-keysyms
    xcb-util-renderutil
)

instalar_dependencias() {
    local gestor=""
    for g in apt-get dnf zypper pacman; do
        if command -v "$g" > /dev/null 2>&1; then gestor="$g"; break; fi
    done

    if [ -z "$gestor" ]; then
        rojo "No reconozco el gestor de paquetes de esta distribución."
        echo "Instalá a mano las bibliotecas de Qt y volvé a correr con --no-deps."
        echo "Para saber cuáles faltan:"
        echo "  ldda=\$(python3 -c 'import PySide6,os;print(os.path.dirname(PySide6.__file__))')"
        echo "  ldd \"\$ldda\"/Qt/plugins/platforms/libqxcb.so | grep 'not found'"
        return 1
    fi

    local -a paquetes
    local -a comando
    case "$gestor" in
        apt-get) paquetes=("${DEB_PKGS[@]}");  comando=(sudo apt-get install -y) ;;
        dnf)     paquetes=("${RPM_PKGS[@]}");  comando=(sudo dnf install -y) ;;
        zypper)  paquetes=("${RPM_PKGS[@]}");  comando=(sudo zypper install -y) ;;
        pacman)  paquetes=("${ARCH_PKGS[@]}"); comando=(sudo pacman -S --needed --noconfirm) ;;
    esac

    if [ "$gestor" != "apt-get" ]; then
        echo "Aviso: la lista de paquetes para $gestor no está probada."
        echo "Si MC no abre, usá el diagnóstico con ldd que está en el README."
    fi

    info "Instalando bibliotecas del sistema con $gestor (pide sudo)"
    if [ "$gestor" = "apt-get" ]; then
        sudo apt-get update -qq
    fi
    "${comando[@]}" "${paquetes[@]}"
}

# --- entorno virtual --------------------------------------------------------

crear_entorno() {
    info "Creando el entorno virtual en $RAIZ/.venv"
    if [ ! -d "$RAIZ/.venv" ]; then
        python3 -m venv "$RAIZ/.venv"
    fi
    "$RAIZ/.venv/bin/python" -m pip install --quiet --upgrade pip
    "$RAIZ/.venv/bin/python" -m pip install --quiet -r "$RAIZ/requirements.txt"
    local version
    version="$("$RAIZ/.venv/bin/python" -c 'import PySide6; print(PySide6.__version__)')"
    verde "PySide6 $version instalado"
}

# --- integración con el escritorio ------------------------------------------

integrar_escritorio() {
    info "Dejando el comando 'mc' en $BIN_DIR"
    mkdir -p "$BIN_DIR"
    chmod +x "$RAIZ/mc.sh"
    ln -sf "$RAIZ/mc.sh" "$ENLACE"

    info "Registrando la aplicación en el menú"
    mkdir -p "$APPS_DIR" "$ICON_DIR"
    cp "$RAIZ/mc/resources/icon.png" "$ICON_DIR/marcecommander.png"

    cat > "$DESKTOP" << DESKTOP_EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Marce Commander
GenericName=File Manager
Comment=Gestor de archivos de doble panel
Comment[en]=Dual-pane file manager
Exec=$RAIZ/mc.sh %F
Icon=marcecommander
Terminal=false
Categories=Utility;System;FileTools;FileManager;
Keywords=file;manager;commander;archivos;
StartupNotify=true
DESKTOP_EOF

    # Refrescar los índices del escritorio si las herramientas están.
    command -v update-desktop-database > /dev/null 2>&1 \
        && update-desktop-database "$APPS_DIR" 2> /dev/null || true
    command -v gtk-update-icon-cache > /dev/null 2>&1 \
        && gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2> /dev/null || true
}

avisar_path() {
    case ":$PATH:" in
        *":$BIN_DIR:"*) ;;
        *)
            echo
            rojo "$BIN_DIR no está en tu PATH."
            echo "Agregá esta línea a ~/.bashrc o ~/.zshrc:"
            echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
            echo "Mientras tanto podés usar: $RAIZ/mc.sh"
            ;;
    esac
}

desinstalar() {
    info "Quitando la integración"
    rm -f "$ENLACE" "$DESKTOP" "$ICON_DIR/marcecommander.png"
    command -v update-desktop-database > /dev/null 2>&1 \
        && update-desktop-database "$APPS_DIR" 2> /dev/null || true
    verde "Listo. El entorno virtual sigue en $RAIZ/.venv"
    echo "Para borrarlo también: rm -rf \"$RAIZ/.venv\""
}

uso() {
    sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

# --- principal --------------------------------------------------------------

main() {
    local con_deps=1
    for arg in "$@"; do
        case "$arg" in
            --no-deps)   con_deps=0 ;;
            --uninstall) desinstalar; exit 0 ;;
            -h|--help)   uso; exit 0 ;;
            *) rojo "Opción desconocida: $arg"; uso; exit 1 ;;
        esac
    done

    if [ "$(id -u)" -eq 0 ]; then
        rojo "No lo corras como root: instalaría para el usuario root."
        exit 1
    fi

    echo "Marce Commander — instalación"
    echo "Origen: $RAIZ"
    echo

    [ "$con_deps" -eq 1 ] && instalar_dependencias
    crear_entorno
    integrar_escritorio

    echo
    verde "Instalado."
    echo "  mc                        desde cualquier lado"
    echo "  mc ~/proyectos /mnt/bak   con rutas iniciales"
    echo "  ./install.sh --uninstall  para deshacerlo"
    echo
    echo "También figura en el menú de aplicaciones."
    echo "Sin depender del PATH: $RAIZ/mc.sh"
    avisar_path
}

main "$@"
