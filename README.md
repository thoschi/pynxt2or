# pynxt2or

Modern 64-bit USB connector between LEGO Mindstorms NXT and Open Roberta Lab. It replaces the legacy Java 8/i386/leJOS/JNI connector with Python, PyUSB/libusb-1.0, HTTPS and PySide6.

## Install into a venv

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install .
```

No Python packages need to be installed with apt. **USB still requires the operating system's libusb-1.0 runtime**, and Linux needs a udev permission rule. GUI libraries are supplied by the PySide6 wheel.

Linux udev rule (`/etc/udev/rules.d/70-lego.rules`):

```text
SUBSYSTEM=="usb", ATTR{idVendor}=="0694", ATTR{idProduct}=="0002", GROUP="lego", MODE="0660"
```

After changing the rule: `udevadm control --reload-rules`, reconnect the NXT, and ensure the logged-in user belongs to `lego`.

## Useful commands

```bash
pynxt2or --doctor       # works without NXT
pynxt2or --simulate     # hardware/server-free state-machine test
pynxt2or --probe        # tomorrow: real USB/LCP test
pynxt2or --debug --probe
pynxt2or                # GUI
```

## Implemented legacy behavior

USB discovery; device info; firmware and battery; running-program detection; 8-character token; HTTPS registration and long-polling; program download; `.rxe` replacement/upload/start; execution-completion detection; connect/download/disconnect tones; token timeout; configurable server address.

Not implemented: Bluetooth. The legacy NXT firmware `update()` path was empty and therefore needs no replacement.

## Echter Open-Roberta-Test ohne NXT-Hardware

Mit `--fake-nxt` wird nur der physische NXT simuliert. Die GUI verbindet sich
mit dem angegebenen echten Open-Roberta-Server, registriert einen NXT, zeigt den
Pairing-Token und führt das normale Push-/Download-Protokoll aus.

```bash
pynxt2or --fake-nxt
```

Für Protokollausgaben:

```bash
pynxt2or --fake-nxt --debug
```

Der simulierte NXT meldet sich als `PYNXT2OR-SIM` mit Firmware `1.31`.
Heruntergeladene Programme werden statt per USB auf einen Brick nach
`~/pynxt2or-fake-downloads/` geschrieben und anschließend für zwei Sekunden als
"laufend" simuliert.

Ein anderer Server kann wie gewohnt angegeben werden:

```bash
pynxt2or --fake-nxt --server https://mein-open-roberta.example:443
```
