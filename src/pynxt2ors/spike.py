from __future__ import annotations

import base64
import json
import secrets
import time
from pathlib import Path

from serial import Serial
from serial.tools import list_ports

from .robot import RobotError, RobotNotFound


class SpikeError(RobotError):
    pass


class SpikeNotFound(RobotNotFound, SpikeError):
    pass


class SpikeLEGO:
    """SPIKE Prime / Robot Inventor with the original LEGO firmware.

    This is a Python port of OpenRoberta/openroberta-connector's
    SpikeCommunicator. The LEGO firmware exposes a JSON protocol on its
    USB serial port at 115200 baud.
    """

    robot_kind = "SPIKE"
    firmware_kind = "lego"
    openroberta_system = "spike"
    USB_IDS = {(0x0694, 0x0009), (0x0694, 0x0010)}

    def __init__(self, port: str | None = None, timeout: float = 12.0):
        self.port = port
        self.timeout = timeout
        self.serial: Serial | None = None

    @classmethod
    def find_ports(cls):
        return [p for p in list_ports.comports() if (p.vid, p.pid) in cls.USB_IDS]

    def open(self):
        if not self.port:
            ports = self.find_ports()
            if not ports:
                raise SpikeNotFound("Kein SPIKE Prime/Robot Inventor mit LEGO-Firmware gefunden")
            self.port = ports[0].device
        # Do not keep the serial port open while idle: the LEGO firmware and
        # desktop tools behave better if the port is opened only for transfer.
        return self

    def close(self):
        if self.serial:
            try:
                self.serial.close()
            finally:
                self.serial = None

    def register_info_for_server(self):
        return self.device_info_for_server()

    def device_info_for_server(self):
        return {"firmwarename": "spike", "robot": "spike", "brickname": "Spike Prime/Robot Inventor"}

    def get_current_program_name(self):
        return None

    def melody(self, kind: str):
        pass

    @staticmethod
    def _id():
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        return "".join(secrets.choice(alphabet) for _ in range(4))

    def _payload(self, method, params=None):
        return {"m": method, "p": params or {}, "i": self._id()}

    def _read_response(self, request_id: str, method: str):
        deadline = time.monotonic() + self.timeout
        buf = bytearray()
        while time.monotonic() < deadline:
            chunk = self.serial.read(self.serial.in_waiting or 1)
            if chunk:
                buf.extend(chunk)
                # Firmware answers with JSON records separated by CR/LF. It can
                # also emit unrelated console text; inspect complete JSON lines.
                text = buf.decode("utf-8", errors="ignore")
                for line in text.replace("\r", "\n").split("\n"):
                    line = line.strip()
                    if not line.startswith("{"):
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("i") == request_id or "r" in obj or "e" in obj:
                        return obj
            time.sleep(0.01)
        raise SpikeError(f"SPIKE antwortet nicht auf {method!r}")

    def _send(self, payload):
        raw = (json.dumps(payload, separators=(",", ":")) + "\r").encode()
        self.serial.write(raw)
        self.serial.flush()
        answer = self._read_response(payload["i"], payload["m"])
        if answer.get("e"):
            try:
                msg = base64.b64decode(answer["e"]).decode("utf-8", errors="replace")
            except Exception:
                msg = str(answer["e"])
            raise SpikeError(f"SPIKE: {msg}")
        return answer

    def upload_and_start(self, binary: bytes, filename: str) -> str:
        if not self.port:
            self.open()
        self.serial = Serial(self.port, 115200, timeout=0.15, write_timeout=3)
        try:
            self.serial.reset_input_buffer()
            self._send(self._payload("program_terminate"))

            now = int(time.time())
            start = self._payload("start_write_program", {
                "slotid": 0,
                "size": len(binary),
                "meta": {
                    "created": now,
                    "modified": now,
                    "name": "NepoProg.py",
                    "type": "python",
                    "project_id": "OpenRoberta",
                },
            })
            answer = self._send(start)
            transfer_id = (answer.get("r") or {}).get("transferid")
            if not transfer_id:
                # The upstream Java connector retries this command once because
                # some firmware revisions occasionally return a broken first reply.
                answer = self._send(start)
                transfer_id = (answer.get("r") or {}).get("transferid")
            if not transfer_id:
                raise SpikeError("SPIKE lieferte keine transferid")

            for pos in range(0, len(binary), 512):
                chunk = binary[pos:pos + 512]
                self._send(self._payload("write_package", {
                    "data": base64.b64encode(chunk).decode("ascii"),
                    "transferid": transfer_id,
                }))

            self._send(self._payload("program_execute", {"slotid": 0}))
            return filename or "NepoProg.py"
        finally:
            self.close()
