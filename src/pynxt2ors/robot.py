from __future__ import annotations

class RobotError(Exception):
    pass

class RobotNotFound(RobotError):
    pass

class MultipleRobotsError(RobotError):
    pass
