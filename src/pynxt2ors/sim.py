"""Simulation helpers for pynxt2ors.

SimNXT replaces only the physical NXT. It can therefore be combined with the
real OpenRobertaServer to test registration, pairing, long polling and program
downloads without hardware.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

log = logging.getLogger(__name__)


class SimNXT:
    robot_kind = "NXT"
    supports_update = False
    """Small NXT stand-in implementing the interface used by Connector."""

    def __init__(self, output_dir: str | Path | None = None, run_seconds: float = 2.0):
        self.closed = False
        self.uploads: list[tuple[bytes, str]] = []
        self.running_until = 0.0
        self.running_name: str | None = None
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
        # Deliberately plausible values matching the fields sent by the legacy
        # NXT connector. No real hardware identity is claimed.
        return {
            "firmwarename": "NXT",
            "robot": "nxt",
            "firmwareversion": "1.31",
            "macaddr": "00:00:00:00:00:01",
            "brickname": "PYNXT2OR-SIM",
            "battery": "7.5",
        }

    def get_current_program_name(self):
        if self.running_name and time.monotonic() < self.running_until:
            return self.running_name
        self.running_name = None
        return None

    def upload_and_start(self, binary: bytes, filename: str):
        self.uploads.append((binary, filename))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(filename).name or "program.rxe"
        target = self.output_dir / safe_name
        target.write_bytes(binary)
        self.running_name = safe_name
        self.running_until = time.monotonic() + self.run_seconds
        log.info("Fake-NXT: %d Bytes als %s gespeichert", len(binary), target)
        return safe_name

    def melody(self, kind):
        log.info("Fake-NXT: melody(%s)", kind)


class SimServer:
    """Fully offline server stand-in used by --simulate."""

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
        return b"SIMULATED-RXE", "test.rxe"

    def abort(self):
        pass

    def close(self):
        pass
