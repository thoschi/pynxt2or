from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class RobotProfile:
    key: str
    label: str
    system: str
    connector: bool
    note: str

PROFILES = {
    "auto": RobotProfile("auto", "Automatisch erkennen", "", True, "NXT, EV3 leJOS oder SPIKE mit LEGO-Firmware"),
    "nxt": RobotProfile("nxt", "LEGO NXT", "nxt", True, "USB/LCP über pynxt2ors"),
    "ev3lejos": RobotProfile("ev3lejos", "EV3 – leJOS", "ev3lejosv1", True, "USB-Netzwerk über pynxt2ors"),
    "ev3dev": RobotProfile("ev3dev", "EV3 – ev3dev", "ev3dev", False, "EV3dev verbindet sich selbst mit Open Roberta"),
    "spike": RobotProfile("spike", "SPIKE Prime – LEGO-Firmware", "spike", True, "USB-Serial über pynxt2ors"),
    "spikepybricks": RobotProfile("spikepybricks", "SPIKE Prime – Pybricks", "spikePybricks", False, "Open Roberta verbindet per Web Bluetooth direkt mit Pybricks"),
}
