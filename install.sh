#!/usr/bin/env bash
set -Eeuo pipefail

INSTALL_DIR=/opt/pynxt2ors
APP_DIR="$INSTALL_DIR/app"
VENV="$INSTALL_DIR/venv"
LAUNCHER=/usr/local/bin/pynxt2ors
DESKTOP=/usr/share/applications/pynxt2ors.desktop
RULE=/etc/udev/rules.d/70-pynxt2ors.rules
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

info() { echo; echo "==> $*"; }
die() { echo "FEHLER: $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Bitte als root ausführen."

if [[ ${1:-} == "--uninstall" ]]; then
    info "Entferne pynxt2ors"
    rm -rf "$INSTALL_DIR"
    rm -f "$LAUNCHER" "$DESKTOP" "$RULE"
    udevadm control --reload-rules 2>/dev/null || true
    udevadm trigger 2>/dev/null || true
    command -v update-desktop-database >/dev/null && update-desktop-database /usr/share/applications || true
    echo "pynxt2ors wurde vollständig entfernt."
    exit 0
fi

[[ $# -eq 0 || ${1:-} == "--update" ]] || die "Verwendung: $0 [--update|--uninstall]"
[[ -f "$SOURCE_DIR/pyproject.toml" && -d "$SOURCE_DIR/src/pynxt2ors" ]] || die "Kein vollständiges pynxt2ors-Projekt gefunden."
command -v python3 >/dev/null || die "python3 fehlt."
command -v rsync >/dev/null || die "rsync fehlt."
command -v udevadm >/dev/null || die "udevadm fehlt."
python3 -m venv --help >/dev/null 2>&1 || die "Python venv fehlt (python3-venv installieren)."

info "Entferne ggf. alte pynxt2or-Installation"
rm -rf /opt/pynxt2or
rm -f /usr/local/bin/pynxt2or /usr/share/applications/pynxt2or.desktop /etc/udev/rules.d/70-pynxt2or.rules

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

info "Installiere USB-Berechtigung"
cat > "$RULE" <<'EOF'
# LEGO Mindstorms devices used by pynxt2ors.
# uaccess grants the active desktop user access without a permanent local group.
SUBSYSTEM=="usb", ATTR{idVendor}=="0694", MODE="0660", TAG+="uaccess"
EOF
chmod 0644 "$RULE"
udevadm control --reload-rules
udevadm trigger

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
Comment=LEGO Mindstorms NXT/EV3 mit Open Roberta verbinden
Exec=$LAUNCHER
Icon=$APP_DIR/assets/OR.png
Terminal=false
Categories=Education;Development;
Keywords=Open Roberta;LEGO;Mindstorms;NXT;EV3;
StartupNotify=true
EOF
chmod 0644 "$DESKTOP"
command -v update-desktop-database >/dev/null && update-desktop-database /usr/share/applications || true

info "Prüfe Installation"
"$VENV/bin/python" -c 'import pynxt2ors, PySide6, usb, requests; print("Python-Module: OK")'
"$VENV/bin/pynxt2ors" --doctor || true

echo
echo "============================================================"
echo " pynxt2ors wurde erfolgreich installiert"
echo "============================================================"
echo
echo "Startmenü: pynxt2ors – Open Roberta Connector"
echo "Kommando:  pynxt2ors"
echo "Pfad:      $INSTALL_DIR"
echo
echo "NXT/EV3 ggf. einmal abziehen und wieder anstecken."
echo "Update:    sudo $APP_DIR/install.sh --update"
echo "Entfernen: sudo $APP_DIR/install.sh --uninstall"
