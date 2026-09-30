from __future__ import annotations
from .ev3 import EV3
from .lcp import NXTUSB
from .robot import RobotNotFound

class AutoRobot:
    """Try NXT USB first, then the leJOS EV3 USB-network endpoint."""
    def __init__(self, ev3_address="http://10.0.1.1"):
        self.ev3_address = ev3_address

    def open(self):
        errors = []
        for factory in (NXTUSB, lambda: EV3(self.ev3_address)):
            robot = factory()
            try:
                return robot.open()
            except RobotNotFound as exc:
                errors.append(str(exc))
                try: robot.close()
                except Exception: pass
        raise RobotNotFound("; ".join(errors) or "Kein unterstützter Roboter gefunden")
