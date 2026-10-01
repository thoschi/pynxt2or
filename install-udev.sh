#!/usr/bin/env bash
set -euo pipefail
RULE=/etc/udev/rules.d/70-pynxt2ors.rules
if [[ ${1:-} == --uninstall ]]; then
  rm -f "$RULE"; udevadm control --reload-rules; udevadm trigger; echo "pynxt2ors udev-Regel entfernt."; exit 0
fi
[[ $EUID -eq 0 ]] || { echo "Bitte als root ausführen." >&2; exit 1; }
cat >"$RULE" <<'RULES'
SUBSYSTEM=="usb", ATTR{idVendor}=="0694", MODE="0660", TAG+="uaccess"
RULES
udevadm control --reload-rules; udevadm trigger
echo "pynxt2ors udev-Regel installiert. NXT/EV3 ggf. neu anstecken."
