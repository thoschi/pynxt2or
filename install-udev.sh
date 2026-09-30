#!/usr/bin/env bash
set -euo pipefail

GROUP="lego"
RULE_FILE="/etc/udev/rules.d/70-lego.rules"
USER_TO_ADD=""

usage() {
    cat <<EOF
Usage:
  sudo $0 [--user USER]
  sudo $0 --uninstall

Installiert die udev-Regeln für LEGO Mindstorms NXT und legt
bei Bedarf die Gruppe "${GROUP}" an.

Optionen:
  --user USER    Fügt USER zusätzlich der Gruppe "${GROUP}" hinzu
  --uninstall    Entfernt die udev-Regeln wieder
  -h, --help     Zeigt diese Hilfe
EOF
}

if [[ ${EUID} -ne 0 ]]; then
    echo "Fehler: Dieses Skript muss als root ausgeführt werden." >&2
    echo "Beispiel: sudo $0 --user \"\$USER\"" >&2
    exit 1
fi

MODE="install"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --user)
            if [[ $# -lt 2 ]]; then
                echo "Fehler: --user benötigt einen Benutzernamen." >&2
                exit 1
            fi
            USER_TO_ADD="$2"
            shift 2
            ;;
        --uninstall)
            MODE="uninstall"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unbekannte Option: $1" >&2
            usage
            exit 1
            ;;
    esac
done

reload_udev() {
    if command -v udevadm >/dev/null 2>&1; then
        udevadm control --reload-rules
        udevadm trigger --subsystem-match=usb
    else
        echo "Warnung: udevadm wurde nicht gefunden."
        echo "Die Regeln werden spätestens nach einem Neustart aktiv."
    fi
}

if [[ "$MODE" == "uninstall" ]]; then
    echo "Entferne pynxt2or-NXT-udev-Regeln ..."

    if [[ -f "$RULE_FILE" ]]; then
        rm -f "$RULE_FILE"
        echo "Entfernt: $RULE_FILE"
    else
        echo "Nicht vorhanden: $RULE_FILE"
    fi

    reload_udev

    echo
    echo "Die Gruppe '${GROUP}' wurde absichtlich NICHT gelöscht."
    echo "Dadurch werden bestehende Gruppenmitgliedschaften nicht verändert."
    echo
    echo "Deinstallation abgeschlossen."
    exit 0
fi

echo "Installiere NXT-USB-Unterstützung für pynxt2or ..."

if getent group "$GROUP" >/dev/null 2>&1; then
    echo "Gruppe '${GROUP}' existiert bereits."
else
    groupadd "$GROUP"
    echo "Gruppe '${GROUP}' wurde angelegt."
fi

cat > "$RULE_FILE" <<EOF
# LEGO Mindstorms NXT
# Installed for pynxt2or

# NXT normal mode
SUBSYSTEM=="usb", ATTR{idVendor}=="0694", ATTR{idProduct}=="0002", GROUP="${GROUP}", MODE="0660"

# NXT firmware update mode (Atmel SAM-BA)
SUBSYSTEM=="usb", ATTR{idVendor}=="03eb", ATTR{idProduct}=="6124", GROUP="${GROUP}", MODE="0660"
EOF

chmod 0644 "$RULE_FILE"

echo "Installiert: $RULE_FILE"

if [[ -n "$USER_TO_ADD" ]]; then
    if ! id "$USER_TO_ADD" >/dev/null 2>&1; then
        echo "Fehler: Benutzer '${USER_TO_ADD}' existiert nicht." >&2
        exit 1
    fi

    if id -nG "$USER_TO_ADD" | tr ' ' '\n' | grep -Fxq "$GROUP"; then
        echo "Benutzer '${USER_TO_ADD}' ist bereits Mitglied von '${GROUP}'."
    else
        usermod -aG "$GROUP" "$USER_TO_ADD"
        echo "Benutzer '${USER_TO_ADD}' wurde der Gruppe '${GROUP}' hinzugefügt."
        echo "Die neue Gruppenmitgliedschaft gilt nach einer neuen Anmeldung."
    fi
fi

reload_udev

echo
echo "Installation abgeschlossen."

if [[ -z "$USER_TO_ADD" ]]; then
    echo
    echo "Noch wurde kein Benutzer der Gruppe '${GROUP}' hinzugefügt."
    echo "Für einen lokalen Entwicklungsbenutzer beispielsweise:"
    echo
    echo "    sudo $0 --user USERNAME"
fi

echo
echo "Aktuelle Gruppe:"
getent group "$GROUP"

echo
echo "Aktuelle Regel:"
cat "$RULE_FILE"
