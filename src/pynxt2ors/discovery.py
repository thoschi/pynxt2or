from __future__ import annotations

from .ev3 import EV3
from .lcp import NXTUSB
from .robot import MultipleRobotsError, RobotNotFound
from .spike import SpikeLEGO


class AutoRobot:
    """Detect exactly one connector-driven robot.

    All supported transports are probed so that accidentally connecting two
    classroom robots cannot silently select the first one.
    """

    def __init__(self, ev3_address="http://10.0.1.1"):
        self.ev3_address = ev3_address

    def open(self):
        found = []
        errors = []
        factories = (
            ("NXT", NXTUSB),
            ("EV3/leJOS", lambda: EV3(self.ev3_address)),
            ("SPIKE/LEGO", SpikeLEGO),
        )
        for label, factory in factories:
            robot = factory()
            try:
                found.append((label, robot.open()))
            except RobotNotFound as exc:
                errors.append(str(exc))
                try:
                    robot.close()
                except Exception:
                    pass

        if len(found) == 1:
            return found[0][1]

        for _, robot in found:
            try:
                robot.close()
            except Exception:
                pass

        if len(found) > 1:
            names = ", ".join(label for label, _ in found)
            raise MultipleRobotsError(
                f"Mehrere Roboter gefunden ({names}). Bitte nur einen Roboter anschließen."
            )

        raise RobotNotFound("; ".join(errors) or "Kein unterstützter Roboter gefunden")
