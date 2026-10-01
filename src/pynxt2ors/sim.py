"""Simulation helpers for pynxt2ors."""
from __future__ import annotations

import logging
import time
from pathlib import Path

log = logging.getLogger(__name__)


class SimRobot:
    supports_update = False

    def __init__(self, kind="NXT", system="nxt", firmware="NXT", extension="rxe",
                 output_dir=None, run_seconds=2.0):
        self.robot_kind = kind
        self.openroberta_system = system
        self.firmware = firmware
        self.extension = extension
        self.closed = False
        self.uploads = []
        self.running_until = 0.0
        self.running_name = None
        self.run_seconds = run_seconds
        self.output_dir = Path(output_dir or (Path.home() / "pynxt2ors-fake-downloads"))

    def open(self):
        self.closed = False
        return self

    def close(self):
        self.closed = True

    def register_info_for_server(self):
        return self.device_info_for_server()

    def device_info_for_server(self):
        robot = "nxt" if self.robot_kind == "NXT" else self.openroberta_system
        return {
            "firmwarename": self.firmware,
            "robot": robot,
            "firmwareversion": "SIM",
            "macaddr": "00:00:00:00:00:01",
            "brickname": f"PYNXT2ORS-{self.robot_kind}-SIM",
            "battery": "7.5",
        }

    def get_current_program_name(self):
        if self.running_name and time.monotonic() < self.running_until:
            return self.running_name
        self.running_name = None
        return None

    def upload_and_start(self, binary, filename):
        self.uploads.append((binary, filename))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(filename).name or f"program.{self.extension}"
        target = self.output_dir / safe_name
        target.write_bytes(binary)
        self.running_name = safe_name
        self.running_until = time.monotonic() + self.run_seconds
        log.info("Fake-%s: %d Bytes als %s gespeichert", self.robot_kind, len(binary), target)
        return safe_name

    def melody(self, kind):
        log.info("Fake-%s: melody(%s)", self.robot_kind, kind)


class SimNXT(SimRobot):
    def __init__(self, *args, **kwargs):
        super().__init__("NXT", "nxt", "NXT", "rxe", *args, **kwargs)


class SimEV3(SimRobot):
    def __init__(self, firmware="lejos", *args, **kwargs):
        system = "ev3dev" if firmware == "ev3dev" else "ev3lejosv1"
        super().__init__("EV3", system, system, "jar", *args, **kwargs)


class SimSpike(SimRobot):
    def __init__(self, firmware="lego", *args, **kwargs):
        system = "spikePybricks" if firmware == "pybricks" else "spike"
        super().__init__("SPIKE", system, system, "py", *args, **kwargs)


class SimServer:
    def __init__(self):
        self.push_count = 0
        self.downloaded = False

    def push(self, payload):
        self.push_count += 1
        if payload["cmd"] == "register":
            return {"cmd": "repeat"}
        if not self.downloaded:
            self.downloaded = True
            return {"cmd": "download"}
        return {"cmd": "repeat"}

    def download(self, payload):
        return b"SIMULATED-PROGRAM", "test.rxe"

    def abort(self): pass
    def close(self): pass
