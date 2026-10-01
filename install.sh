#!/usr/bin/env bash
set -Eeuo pipefail

INSTALL_DIR=/opt/pynxt2ors
APP_DIR="$INSTALL_DIR/app"
VENV="$INSTALL_DIR/venv"
LAUNCHER=/usr/local/bin/pynxt2ors
DESKTOP=/usr/share/applications/pynxt2ors.desktop
RULE=/etc/udev/rules.d/70-pynxt2ors.rules
GROUP=openroberta
LMN_HOOK=/etc/linuxmuster-linuxclient7/onLoginAsRoot.d/20_userToOpenRoberta.sh
CONFIG=/etc/pynxt2ors-install.conf
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

info() { echo; echo "==> $*"; }
die() { echo "FEHLER: $*" >&2; exit 1; }
usage() {
    cat <<EOF
Verwendung:
  sudo $0 user
  sudo $0 linuxmuster
  sudo $0 --update user
  sudo $0 --update linuxmuster
  sudo $0 --uninstall

user         Zugriff für den Benutzer, der sudo aufgerufen hat
linuxmuster  dynamische Gruppenzuweisung für Domainbenutzer beim Login
EOF
}

[[ $EUID -eq 0 ]] || die "Bitte als root ausführen."

ACTION=install
MODE=""
case "${1:-}" in
    --uninstall) ACTION=uninstall; shift ;;
    --update) ACTION=update; shift ;;
esac
MODE="${1:-}"
[[ $# -le 1 ]] || { usage; exit 1; }

if [[ "$ACTION" != uninstall ]]; then
    [[ "$MODE" == user || "$MODE" == linuxmuster ]] || { usage; exit 1; }
fi

if [[ "$ACTION" == uninstall ]]; then
    info "Entferne pynxt2ors"

    OLD_MODE=""
    OLD_USER=""
    if [[ -f "$CONFIG" ]]; then
        # shellcheck disable=SC1090
        source "$CONFIG"
        OLD_MODE="${INSTALL_MODE:-}"
        OLD_USER="${INSTALL_USER:-}"
    fi

    rm -rf "$INSTALL_DIR"
    rm -f "$LAUNCHER" "$DESKTOP" "$RULE" "$LMN_HOOK" "$CONFIG"
    rm -rf /opt/pynxt2or
    rm -f /usr/local/bin/pynxt2or /usr/share/applications/pynxt2or.desktop \
          /etc/udev/rules.d/70-pynxt2or.rules

    if [[ "$OLD_MODE" == user && -n "$OLD_USER" ]] && getent group "$GROUP" >/dev/null; then
        gpasswd -d "$OLD_USER" "$GROUP" >/dev/null 2>&1 || true
    fi

    udevadm control --reload-rules 2>/dev/null || true
    udevadm trigger 2>/dev/null || true
    command -v update-desktop-database >/dev/null && \
        update-desktop-database /usr/share/applications || true

    echo
    echo "pynxt2ors wurde entfernt."
    echo "Die Gruppe '$GROUP' bleibt vorsichtshalber bestehen."
    exit 0
fi

[[ -f "$SOURCE_DIR/pyproject.toml" && -d "$SOURCE_DIR/src/pynxt2ors" ]] || \
    die "Kein vollständiges pynxt2ors-Projekt gefunden."
command -v python3 >/dev/null || die "python3 fehlt."
command -v rsync >/dev/null || die "rsync fehlt."
command -v udevadm >/dev/null || die "udevadm fehlt."
command -v groupadd >/dev/null || die "groupadd fehlt."
command -v usermod >/dev/null || die "usermod fehlt."
python3 -m venv --help >/dev/null 2>&1 || \
    die "Python venv fehlt (python3-venv installieren)."

if [[ "$MODE" == linuxmuster ]]; then
    [[ -d /etc/linuxmuster-linuxclient7/onLoginAsRoot.d ]] || \
        die "linuxmuster-Modus gewählt, aber /etc/linuxmuster-linuxclient7/onLoginAsRoot.d fehlt."
fi

info "Entferne ggf. alte pynxt2or-Installation"
rm -rf /opt/pynxt2or
rm -f /usr/local/bin/pynxt2or /usr/share/applications/pynxt2or.desktop \
      /etc/udev/rules.d/70-pynxt2or.rules

info "Richte Hardwaregruppe '$GROUP' ein"
getent group "$GROUP" >/dev/null || groupadd --system "$GROUP"

INSTALL_USER=""
if [[ "$MODE" == user ]]; then
    INSTALL_USER="${SUDO_USER:-}"
    [[ -n "$INSTALL_USER" && "$INSTALL_USER" != root ]] || \
        die "Im Modus 'user' bitte mit sudo aus einer normalen Benutzersitzung starten (sudo ./install.sh user)."
    id "$INSTALL_USER" >/dev/null 2>&1 || die "Benutzer '$INSTALL_USER' existiert nicht."

    info "Füge '$INSTALL_USER' zur Gruppe '$GROUP' hinzu"
    usermod -aG "$GROUP" "$INSTALL_USER"
    rm -f "$LMN_HOOK"
else
    info "Installiere linuxmuster-Login-Hook"
    cat > "$LMN_HOOK" <<'EOF'
#!/usr/bin/env bash
# pynxt2ors: Domainbenutzer beim Login für LEGO-USB/Serial-Geräte freischalten.
set -u

GROUP="openroberta"
USER_NAME="${User_sAMAccountName:-}"

[[ -n "$USER_NAME" ]] || exit 0
getent group "$GROUP" >/dev/null || groupadd --system "$GROUP"
id "$USER_NAME" >/dev/null 2>&1 || exit 0

if ! id -nG "$USER_NAME" 2>/dev/null | tr ' ' '\n' | grep -Fxq "$GROUP"; then
    usermod -aG "$GROUP" "$USER_NAME"
fi

exit 0
EOF
    chmod 0755 "$LMN_HOOK"
fi

info "Installiere udev-Regeln für NXT, EV3 und SPIKE"
cat > "$RULE" <<EOF
# pynxt2ors - LEGO NXT, EV3, SPIKE / Robot Inventor
# Zugriff erfolgt einheitlich über die Gruppe '$GROUP'.

# NXT normal + Firmware/DFU
SUBSYSTEM=="usb", ATTR{idVendor}=="0694", ATTR{idProduct}=="0002", GROUP="$GROUP", MODE="0660"
SUBSYSTEM=="usb", ATTR{idVendor}=="03eb", ATTR{idProduct}=="6124", GROUP="$GROUP", MODE="0660"

# EV3 normal + Update-Modus
SUBSYSTEM=="usb", ATTR{idVendor}=="0694", ATTR{idProduct}=="0005", GROUP="$GROUP", MODE="0660"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="0694", ATTRS{idProduct}=="0005", GROUP="$GROUP", MODE="0660"
SUBSYSTEM=="usb", ATTR{idVendor}=="0694", ATTR{idProduct}=="0006", GROUP="$GROUP", MODE="0660"

# SPIKE / Robot Inventor / verwandte Hub-Varianten
SUBSYSTEM=="usb", ATTR{idVendor}=="0694", ATTR{idProduct}=="0008", GROUP="$GROUP", MODE="0660"
SUBSYSTEM=="usb", ATTR{idVendor}=="0694", ATTR{idProduct}=="0009", GROUP="$GROUP", MODE="0660"
SUBSYSTEM=="usb", ATTR{idVendor}=="0694", ATTR{idProduct}=="000c", GROUP="$GROUP", MODE="0660"
SUBSYSTEM=="usb", ATTR{idVendor}=="0694", ATTR{idProduct}=="000d", GROUP="$GROUP", MODE="0660"
SUBSYSTEM=="usb", ATTR{idVendor}=="0694", ATTR{idProduct}=="0010", GROUP="$GROUP", MODE="0660"
SUBSYSTEM=="usb", ATTR{idVendor}=="0694", ATTR{idProduct}=="0011", GROUP="$GROUP", MODE="0660"

# Serielle Geräte der LEGO-Hubs (insbesondere SPIKE mit LEGO-Firmware)
SUBSYSTEM=="tty", ATTRS{idVendor}=="0694", GROUP="$GROUP", MODE="0660"

# HID-Zugriff für LEGO-Geräte
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="0694", GROUP="$GROUP", MODE="0660"
EOF
chmod 0644 "$RULE"
udevadm control --reload-rules
udevadm trigger

cat > "$CONFIG" <<EOF
INSTALL_MODE="$MODE"
INSTALL_USER="$INSTALL_USER"
EOF
chmod 0644 "$CONFIG"

info "Installiere Programm nach $APP_DIR"
mkdir -p "$APP_DIR"
rsync -a --delete \
    --exclude='.git/' --exclude='venv/' --exclude='.venv/' \
    --exclude='*.egg-info/' --exclude='__pycache__/' --exclude='.pytest_cache/' \
    "$SOURCE_DIR/" "$APP_DIR/"

info "Erzeuge Python-Umgebung"
rm -rf "$VENV"
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV/bin/pip" install "$APP_DIR"

info "Installiere systemweiten Starter"
cat > "$LAUNCHER" <<EOF
#!/bin/sh
exec "$VENV/bin/pynxt2ors" "\$@"
EOF
chmod 0755 "$LAUNCHER"

info "Installiere Startmenü-Eintrag"
cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=pynxt2ors – Open Roberta Connector
Comment=LEGO NXT/EV3/SPIKE mit Open Roberta verbinden
Exec=$LAUNCHER
Icon=$APP_DIR/assets/OR.png
Terminal=false
Categories=Education;Development;
Keywords=Open Roberta;LEGO;Mindstorms;NXT;EV3;SPIKE;Pybricks;
StartupNotify=true
EOF
chmod 0644 "$DESKTOP"
command -v update-desktop-database >/dev/null && \
    update-desktop-database /usr/share/applications || true

info "Prüfe Installation"
"$VENV/bin/python" -c 'import pynxt2ors, PySide6, usb, requests, serial; print("Python-Module: OK")'
"$VENV/bin/pynxt2ors" --doctor || true

# Das alte separate udev-Skript wird nicht mehr benötigt.
rm -f "$APP_DIR/install-udev.sh"

echo
echo "============================================================"
echo " pynxt2ors wurde erfolgreich installiert"
echo "============================================================"
echo
echo "Modus:     $MODE"
echo "Startmenü: pynxt2ors – Open Roberta Connector"
echo "Kommando:  pynxt2ors"
echo "Pfad:      $INSTALL_DIR"
echo "USB-Gruppe:$GROUP"
if [[ "$MODE" == user ]]; then
    echo "Benutzer:   $INSTALL_USER"
    echo
    echo "WICHTIG: '$INSTALL_USER' muss sich einmal ab- und wieder anmelden,"
    echo "damit die neue Gruppenzugehörigkeit wirksam wird."
else
    echo "LMN-Hook:   $LMN_HOOK"
    echo
    echo "Domainbenutzer werden beim Login automatisch der Gruppe '$GROUP' hinzugefügt."
fi
echo
echo "LEGO-Geräte nach der Installation einmal abziehen und wieder anstecken."
echo
echo "Update:"
echo "  sudo $APP_DIR/install.sh --update $MODE"
echo
echo "Entfernen:"
echo "  sudo $APP_DIR/install.sh --uninstall"
