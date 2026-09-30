"""Small, explicit subset of the LEGO NXT LCP protocol used by Open Roberta."""
from __future__ import annotations
import logging
import time
from .robot import RobotError, RobotNotFound
from dataclasses import dataclass

log = logging.getLogger(__name__)
VENDOR_ID = 0x0694
PRODUCT_ID = 0x0002
EP_OUT = 0x01
EP_IN = 0x82
TIMEOUT_MS = 3000
DIRECT_REPLY = 0x00
SYSTEM_REPLY = 0x01
REPLY = 0x02
MAX_FILENAME = 19
WRITE_CHUNK = 58

STATUS = {
    0x00: "success", 0x20: "pending communication transaction", 0x40: "mailbox queue empty",
    0x81: "no more handles", 0x82: "no space", 0x83: "no more files", 0x84: "end of file expected",
    0x85: "end of file", 0x86: "not a linear file", 0x87: "file not found", 0x88: "handle already closed",
    0x89: "no linear space", 0x8A: "undefined error", 0x8B: "file busy", 0x8C: "no write buffers",
    0x8D: "append not possible", 0x8E: "file full", 0x8F: "file exists", 0x90: "module not found",
    0x91: "out of bounds", 0x92: "illegal file name", 0x93: "illegal handle", 0xBD: "request failed",
    0xBE: "unknown command opcode", 0xBF: "insane packet", 0xC0: "data contains out-of-range values",
    0xDD: "communication bus error", 0xDE: "no free memory", 0xDF: "specified channel invalid",
    0xE0: "channel busy", 0xEC: "no active program", 0xED: "illegal size", 0xEE: "illegal mailbox",
    0xEF: "invalid field", 0xF0: "bad input/output", 0xFB: "insufficient memory", 0xFF: "bad arguments",
}

class NXTError(RobotError): pass
class NXTNotFound(RobotNotFound, NXTError): pass
class NXTProtocolError(NXTError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message); self.status = status


def _cstr(data: bytes) -> str:
    return bytes(data).split(b"\0", 1)[0].decode("latin-1", "replace")

def _u16(data: bytes) -> int: return data[0] | (data[1] << 8)
def _u32(data: bytes) -> int: return data[0] | (data[1] << 8) | (data[2] << 16) | (data[3] << 24)
def _addr(raw: bytes) -> str: return ":".join(f"{b:02X}" for b in raw)
def _name(name: str) -> bytes: return name.encode("ascii", "strict")[:MAX_FILENAME] + b"\0"

@dataclass(frozen=True)
class DeviceInfo:
    brickname: str
    macaddr: str
    signal_strength: int
    user_flash: int

class NXTUSB:
    robot_kind = "NXT"
    supports_update = False
    def __init__(self, timeout_ms: int = TIMEOUT_MS, device=None):
        self.timeout_ms = timeout_ms
        self.dev = device
        self._usb = None
        self._detached_kernel_driver = False

    def open(self):
        if self.dev is not None:
            return self
        try:
            import usb.core
            import usb.util
        except ImportError as exc:
            raise NXTError("PyUSB fehlt. Im venv: pip install pyusb") from exc
        self._usb = (usb.core, usb.util)
        dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        if dev is None:
            raise NXTNotFound("Kein LEGO NXT (0694:0002) gefunden")
        self.dev = dev
        try:
            if hasattr(dev, "is_kernel_driver_active") and dev.is_kernel_driver_active(0):
                dev.detach_kernel_driver(0); self._detached_kernel_driver = True
        except (NotImplementedError, usb.core.USBError):
            pass
        try:
            dev.set_configuration()
        except usb.core.USBError as exc:
            # A configured device can legitimately reject SET_CONFIGURATION. Actual I/O is authoritative.
            log.debug("set_configuration: %s", exc)
        try:
            usb.util.claim_interface(dev, 0)
        except usb.core.USBError as exc:
            log.debug("claim_interface: %s", exc)
        return self

    def close(self):
        if self.dev is not None and self._usb:
            usb_core, usb_util = self._usb
            try: usb_util.release_interface(self.dev, 0)
            except Exception: pass
            if self._detached_kernel_driver:
                try: self.dev.attach_kernel_driver(0)
                except Exception: pass
            try: usb_util.dispose_resources(self.dev)
            except Exception: pass
        self.dev = None

    def __enter__(self): return self.open()
    def __exit__(self, *_): self.close()

    def command(self, command_type: int, opcode: int, payload: bytes = b"", min_reply: int = 3) -> bytes:
        if self.dev is None: raise NXTError("NXT nicht geöffnet")
        packet = bytes((command_type, opcode)) + bytes(payload)
        log.debug("USB OUT %s", packet.hex(" "))
        try:
            written = self.dev.write(EP_OUT, packet, timeout=self.timeout_ms)
            if written != len(packet): raise NXTProtocolError(f"USB schrieb nur {written}/{len(packet)} Bytes")
            raw = bytes(self.dev.read(EP_IN, 64, timeout=self.timeout_ms))
        except Exception as exc:
            raise NXTError(f"USB/LCP-Übertragung fehlgeschlagen: {exc}") from exc
        log.debug("USB IN  %s", raw.hex(" "))
        if len(raw) < 3: raise NXTProtocolError(f"Zu kurze NXT-Antwort ({len(raw)} Bytes): {raw.hex()}")
        if raw[0] != REPLY or raw[1] != opcode:
            raise NXTProtocolError(f"Unerwartete Antwort auf 0x{opcode:02X}: {raw.hex()}")
        status = raw[2]
        if status:
            raise NXTProtocolError(f"NXT-Status 0x{status:02X}: {STATUS.get(status, 'unknown status')}", status)
        if len(raw) < min_reply: raise NXTProtocolError(f"Zu kurze NXT-Antwort ({len(raw)} Bytes): {raw.hex()}")
        return raw

    def get_device_info(self) -> DeviceInfo:
        r = self.command(SYSTEM_REPLY, 0x9B, min_reply=33)
        return DeviceInfo(_cstr(r[3:18]), _addr(r[18:24]), _u32(r[25:29]), _u32(r[29:33]))

    def get_firmware_version(self) -> dict:
        r = self.command(SYSTEM_REPLY, 0x88, min_reply=7)
        return {"protocol": f"{r[4]}.{r[3]}", "firmware": f"{r[6]}.{r[5]}"}

    def get_battery_level(self) -> int:
        return _u16(self.command(DIRECT_REPLY, 0x0B, min_reply=5)[3:5])

    def get_current_program_name(self) -> str | None:
        try: return _cstr(self.command(DIRECT_REPLY, 0x11, min_reply=23)[3:23])
        except NXTProtocolError as exc:
            if exc.status == 0xEC: return None
            raise

    def start_program(self, name: str): self.command(DIRECT_REPLY, 0x00, _name(name))
    def play_tone(self, freq: int, duration: int):
        self.command(DIRECT_REPLY, 0x03, bytes((freq & 255, freq >> 8, duration & 255, duration >> 8)))

    def delete(self, name: str):
        try: self.command(SYSTEM_REPLY, 0x85, _name(name))
        except NXTProtocolError as exc:
            if exc.status != 0x87: raise

    def open_write(self, name: str, size: int) -> int:
        p = _name(name) + size.to_bytes(4, "little")
        return self.command(SYSTEM_REPLY, 0x81, p, min_reply=4)[3]

    def write_file(self, handle: int, data: bytes) -> int:
        r = self.command(SYSTEM_REPLY, 0x83, bytes((handle,)) + data, min_reply=6)
        return _u16(r[4:6])

    def close_file(self, handle: int): self.command(SYSTEM_REPLY, 0x84, bytes((handle,)))

    @staticmethod
    def rxe_name(filename: str) -> str:
        # Exact legacy behavior: part before first dot, at most MAX_FILENAMELENGTH-5 (14), then .rxe.
        base = filename.rsplit("/", 1)[-1].split(".", 1)[0]
        return base[:14] + ".rxe"

    def upload_and_start(self, binary: bytes, filename: str) -> str:
        if self.get_current_program_name() is not None:
            raise NXTError("Auf dem NXT läuft bereits ein Programm")
        name = self.rxe_name(filename)
        self.delete(name); time.sleep(0.2)
        handle = self.open_write(name, len(binary))
        close_needed = True
        try:
            for pos in range(0, len(binary), WRITE_CHUNK):
                chunk = binary[pos:pos + WRITE_CHUNK]
                if self.write_file(handle, chunk) != len(chunk):
                    raise NXTProtocolError("NXT bestätigte nicht den vollständigen Dateiblock")
            self.close_file(handle); close_needed = False
        finally:
            if close_needed:
                try: self.close_file(handle)
                except Exception: pass
        time.sleep(0.2); self.start_program(name); return name

    def register_info_for_server(self) -> dict:
        return self.device_info_for_server()

    def device_info_for_server(self) -> dict:
        d = self.get_device_info(); fw = self.get_firmware_version(); mv = self.get_battery_level()
        return {"firmwarename":"NXT", "robot":"nxt", "firmwareversion":fw["firmware"],
                "macaddr":d.macaddr, "brickname":d.brickname, "battery":format(mv / 1000.0, ".1f")}

    def melody(self, kind: str):
        seq = {"connect":[523,654,784,915], "disconnect":[915,784,654,523], "download":[450,487,525,562]}.get(kind, [])
        for freq in seq:
            try: self.play_tone(freq, 100); time.sleep(0.1)
            except NXTError: break
