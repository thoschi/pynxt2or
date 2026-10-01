# pynxt2ors

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
pynxt2ors --doctor       # works without NXT
pynxt2ors --simulate     # hardware/server-free state-machine test
pynxt2ors --probe        # tomorrow: real USB/LCP test
pynxt2ors --debug --probe
pynxt2ors                # GUI
```

## Implemented legacy behavior

USB discovery; device info; firmware and battery; running-program detection; 8-character token; HTTPS registration and long-polling; program download; `.rxe` replacement/upload/start; execution-completion detection; connect/download/disconnect tones; token timeout; configurable server address.

Not implemented: Bluetooth. The legacy NXT firmware `update()` path was empty and therefore needs no replacement.

## Echter Open-Roberta-Test ohne NXT-Hardware

Mit `--fake-nxt` wird nur der physische NXT simuliert. Die GUI verbindet sich
mit dem angegebenen echten Open-Roberta-Server, registriert einen NXT, zeigt den
Pairing-Token und führt das normale Push-/Download-Protokoll aus.

```bash
pynxt2ors --fake-nxt
```

Für Protokollausgaben:

```bash
pynxt2ors --fake-nxt --debug
```

Der simulierte NXT meldet sich als `PYNXT2OR-SIM` mit Firmware `1.31`.
Heruntergeladene Programme werden statt per USB auf einen Brick nach
`~/pynxt2ors-fake-downloads/` geschrieben und anschließend für zwei Sekunden als
"laufend" simuliert.

Ein anderer Server kann wie gewohnt angegeben werden:

```bash
pynxt2ors --fake-nxt --server https://mein-open-roberta.example:443
```

## 0.4: NXT + EV3

`pynxt2ors` erkennt nun automatisch einen NXT über PyUSB oder einen Open-Roberta/leJOS-EV3 über das USB-Netzwerk unter `http://10.0.1.1`. Die Open-Roberta-Serverlogik und GUI werden gemeinsam verwendet. Der EV3-Pfad implementiert `/brickinfo`, `/program` und `/firmware` sowie das serverseitige `update`-Kommando. Er setzt die Open-Roberta/leJOS-Firmware auf dem EV3 voraus; die originale LEGO-Firmware stellt diese HTTP-Endpunkte nicht bereit.

Die GUI besitzt zusätzlich `Beenden`; während einer aktiven Verbindung bzw. Programmausführung ist der Knopf gesperrt. Der Token wird beim Warten auf Open Roberta in die Zwischenablage kopiert. Der Server-Timeout beträgt 70 Sekunden, damit das Long-Polling nicht nach 20 Sekunden abbricht.

## 0.5: eigener/öffentlicher Open-Roberta-Server

Die GUI bietet zwei Servermodi. **Eigener Server** ist vorausgewählt; als Vorgabe wird `https://cora.corvi.schule` verwendet und die Adresse kann in der GUI geändert werden (sie wird gespeichert). Beim Verbinden öffnet pynxt2ors den angepassten eigenen Server automatisch mit `loadSystem` und `connectorToken`.

**Online Open Roberta** verwendet `https://lab.open-roberta.org`. Der Knopf **Open Roberta öffnen** öffnet dort direkt das erkannte Robotersystem (`nxt` bzw. `ev3lejosv1`). Der Pairing-Token wird weiterhin angezeigt und in die Zwischenablage kopiert.

Systemweite Client-Installation inklusive Startmenü und udev-Regel:

```bash
sudo ./install.sh
sudo ./install.sh --update
sudo ./install.sh --uninstall
```
