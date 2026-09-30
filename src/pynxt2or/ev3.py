from __future__ import annotations
import requests
from .robot import RobotError, RobotNotFound

class EV3Error(RobotError): pass
class EV3NotFound(RobotNotFound, EV3Error): pass

class EV3:
    """Open-Roberta/leJOS EV3 transport over the USB network (normally 10.0.1.1)."""
    robot_kind = "EV3"
    supports_update = True

    def __init__(self, address="http://10.0.1.1", timeout=3, session=None):
        self.base = address.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        self._last_info = None

    def open(self):
        try:
            # isrunning is a cheap reachability/protocol check and does not alter pairing state.
            self.is_running()
        except requests.RequestException as exc:
            raise EV3NotFound("Kein Open-Roberta/leJOS-EV3 unter 10.0.1.1 gefunden") from exc
        except (ValueError, KeyError) as exc:
            raise EV3NotFound("EV3 antwortet nicht mit dem erwarteten Open-Roberta-Protokoll") from exc
        return self

    def close(self):
        self.session.close()

    def _brick(self, command: str) -> dict:
        r = self.session.post(self.base + "/brickinfo", json={"cmd": command}, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, dict): raise EV3Error("Ungültige EV3-Antwort")
        return data

    def register_info_for_server(self) -> dict:
        self._last_info = self._brick("register")
        return dict(self._last_info)

    def device_info_for_server(self) -> dict:
        self._last_info = self._brick("repeat")
        return dict(self._last_info)

    def is_running(self) -> bool:
        return str(self._brick("isrunning").get("isrunning", "false")).lower() == "true"

    def get_current_program_name(self):
        return "EV3-program" if self.is_running() else None

    def upload_and_start(self, binary: bytes, filename: str) -> str:
        r = self.session.post(self.base + "/program", data=binary,
            headers={"Filename": filename, "Content-Type": "application/octet-stream"}, timeout=30)
        r.raise_for_status()
        return filename

    def upload_firmware(self, binary: bytes, filename: str):
        r = self.session.post(self.base + "/firmware", data=binary,
            headers={"Filename": filename, "Content-Type": "application/octet-stream"}, timeout=30)
        r.raise_for_status()
        return r.json()

    def restart(self):
        self._brick("update")

    def melody(self, kind: str):
        # The EV3 menu itself handles visual/acoustic feedback.
        pass
