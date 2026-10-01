from __future__ import annotations
import logging, secrets, threading, time
from enum import Enum
from .discovery import AutoRobot
from .robot import MultipleRobotsError, RobotError, RobotNotFound
from .server import OpenRobertaServer, ServerError

log = logging.getLogger(__name__)
TOKEN_ALPHABET = "123456789ABCDEFGHIJKLMNPQRSTUVWXYZ"
def make_token(): return "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(8))

class State(Enum):
    DISCOVER="discover"; READY="ready"; WAIT_SERVER="wait_server"; CONNECTED="connected"; RUNNING="running"; MULTIPLE="multiple"; ERROR="error"; TOKEN_TIMEOUT="token_timeout"

class Connector:
    def __init__(self, on_state=lambda *_:None, address="https://lab.open-roberta.org:443", robot_factory=AutoRobot, server=None, nxt_factory=None, auto_connect=False):
        self.on_state=on_state; self.server=server or OpenRobertaServer(address)
        # nxt_factory remains accepted for compatibility with 0.3/tests.
        self.robot_factory=nxt_factory or robot_factory
        self.auto_connect=auto_connect
        self.stop_evt=threading.Event(); self.connect_evt=threading.Event(); self.disconnect_evt=threading.Event()
        self.robot=None; self.nxt=None; self.token=""; self.brick=""; self.robot_kind=""; self.robot_system=""; self.state=State.DISCOVER

    def emit(self,state,message=""):
        self.state=state; log.info("%s %s",state.value,message); self.on_state(state,message)
    def request_connect(self): self.connect_evt.set()
    def request_disconnect(self): self.disconnect_evt.set(); self.server.abort()
    def stop(self): self.stop_evt.set(); self.request_disconnect()

    def _discover(self):
        r=self.robot_factory().open(); self.robot=r; self.nxt=r
        info=r.device_info_for_server(); self.brick=info.get("brickname", info.get("name", "Roboter"))
        self.robot_kind=getattr(r,"robot_kind", info.get("robot", "robot")).upper()
        self.robot_system=getattr(r,"openroberta_system", "") or {"NXT":"nxt","EV3":"ev3lejosv1","SPIKE":"spike"}.get(self.robot_kind, info.get("robot", ""))
        return r,info

    def _update_ev3(self, info):
        if not getattr(self.robot, "supports_update", False):
            raise RuntimeError("Server fordert Firmware-Update für einen Roboter ohne Update-Unterstützung")
        prefix = "v1/" if info.get("firmwarename") == "ev3lejosv1" else ""
        for name in ("runtime", "jsonlib", "websocketlib", "ev3menu"):
            binary, filename = self.server.download_update(prefix + name)
            self.robot.upload_firmware(binary, filename)
        self.robot.restart()

    def run(self):
        while not self.stop_evt.is_set():
            try:
                self.emit(State.DISCOVER,"Suche unterstützten LEGO-Roboter …")
                try: self.robot,info=self._discover()
                except RobotNotFound: time.sleep(1); continue
                except MultipleRobotsError as exc:
                    self.emit(State.MULTIPLE, str(exc))
                    time.sleep(1)
                    continue
                if self.robot.get_current_program_name() is not None:
                    raise RobotError("Auf dem Roboter läuft bereits ein Programm")
                self.emit(State.READY,f"{self.robot_kind} erkannt: {self.brick} – Open-Roberta-System: {self.robot_system}")
                if self.auto_connect:
                    self.connect_evt.set()
                while not self.stop_evt.is_set() and not self.connect_evt.wait(.2):
                    if self.robot.get_current_program_name() is not None: raise RobotError("Auf dem Roboter läuft bereits ein Programm")
                if self.stop_evt.is_set(): break
                self.connect_evt.clear(); self.token=make_token(); self.emit(State.WAIT_SERVER,f"Token: {self.token}")
                reginfo = self.robot.register_info_for_server() if hasattr(self.robot,"register_info_for_server") else info
                payload=dict(reginfo,token=self.token,cmd="register")
                try:
                    response=self.server.push(payload)
                except ServerError as exc:
                    # A server/proxy failure must not invalidate the USB robot.
                    # Keep the robot open and return to a usable READY state.
                    self.token = ""
                    self.emit(State.READY, f"{self.robot_kind} weiterhin erkannt: {self.brick} – Server nicht erreichbar: {exc}")
                    if self.auto_connect:
                        time.sleep(2)
                        self.connect_evt.set()
                    continue
                cmd=response.get("cmd")
                if cmd == "abort":
                    self.token = ""
                    self.emit(State.READY, f"{self.robot_kind} weiterhin erkannt: {self.brick} – Token abgelaufen")
                    if self.auto_connect:
                        time.sleep(1)
                        self.connect_evt.set()
                    continue
                if cmd != "repeat": raise RuntimeError(f"Registrierung: unerwartetes Kommando {cmd!r}")
                self.robot.melody("connect"); self.emit(State.CONNECTED,f"Verbunden: {self.brick}")
                while not self.stop_evt.is_set():
                    if self.disconnect_evt.is_set(): self.disconnect_evt.clear(); self.robot.melody("disconnect"); break
                    info=self.robot.device_info_for_server(); payload=dict(info,token=self.token,cmd="push")
                    try:
                        response=self.server.push(payload)
                    except ServerError as exc:
                        # /rest/pushcmd is long-polling. Reverse proxies may close
                        # an idle upstream connection (e.g. with 502) although the
                        # robot itself is still perfectly connected. Treat that as
                        # a transient transport failure and retry with the same token.
                        self.emit(State.CONNECTED, f"{self.brick} verbunden – Serververbindung wird erneuert …")
                        log.warning("temporärer Open-Roberta-Fehler, wiederhole push: %s", exc)
                        self.server.abort()
                        if self.stop_evt.wait(2):
                            break
                        continue
                    cmd=response.get("cmd")
                    if cmd == "repeat": continue
                    if cmd == "abort":
                        self.robot.melody("disconnect")
                        self.token = ""
                        self.emit(State.READY, f"{self.robot_kind} weiterhin erkannt: {self.brick} – Open-Roberta-Verbindung beendet")
                        if self.auto_connect:
                            self.connect_evt.set()
                        break
                    if cmd == "update": self._update_ev3(info); break
                    if cmd != "download": raise RuntimeError(f"Unerwartetes Serverkommando {cmd!r}")
                    binary,filename=self.server.download(payload); program=self.robot.upload_and_start(binary,filename)
                    self.robot.melody("download"); self.emit(State.RUNNING,f"Programm läuft: {program}")
                    while not self.stop_evt.is_set() and self.robot.get_current_program_name() is not None: time.sleep(1)
                    self.emit(State.CONNECTED,"Programm beendet")
            except Exception as exc:
                if not self.stop_evt.is_set():
                    self.emit(State.ERROR, str(exc))
                    # Do not immediately rediscover/reconnect after a server
                    # failure. That used to create an endless stream of error
                    # dialogs. Wait for an explicit retry or for application exit.
                    self.connect_evt.clear()
                    while not self.stop_evt.is_set() and not self.connect_evt.wait(.2):
                        pass
                    self.connect_evt.clear()
            finally:
                if self.robot:
                    try: self.robot.close()
                    except Exception: pass
                self.robot=None; self.nxt=None; self.token=""; self.brick=""; self.robot_kind=""; self.robot_system=""; self.connect_evt.clear(); self.disconnect_evt.clear()
        self.server.close()
