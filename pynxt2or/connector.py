from __future__ import annotations

import logging
import secrets
import threading
import time
from enum import Enum

from .lcp import NXTUSB, NXTError, NXTNotFound
from .server import (
    OpenRobertaServer,
    ServerTimeout,
)


log = logging.getLogger(__name__)


TOKEN_ALPHABET = "123456789ABCDEFGHIJKLMNPQRSTUVWXYZ"


def make_token():
    return "".join(
        secrets.choice(TOKEN_ALPHABET)
        for _ in range(8)
    )


class State(Enum):
    DISCOVER = "discover"
    READY = "ready"
    WAIT_SERVER = "wait_server"
    CONNECTED = "connected"
    RUNNING = "running"
    ERROR = "error"
    TOKEN_TIMEOUT = "token_timeout"


class Connector:
    def __init__(
        self,
        on_state=lambda *_: None,
        address="https://lab.open-roberta.org:443",
        nxt_factory=NXTUSB,
        server=None,
    ):
        self.on_state = on_state

        self.server = (
            server
            or OpenRobertaServer(address)
        )

        self.nxt_factory = nxt_factory

        self.stop_evt = threading.Event()
        self.connect_evt = threading.Event()
        self.disconnect_evt = threading.Event()

        self.nxt = None
        self.token = ""
        self.brick = ""

        self.state = State.DISCOVER

    def emit(self, state, message=""):
        self.state = state

        log.info(
            "%s %s",
            state.value,
            message,
        )

        self.on_state(
            state,
            message,
        )

    def request_connect(self):
        self.connect_evt.set()

    def request_disconnect(self):
        self.disconnect_evt.set()

        #
        # Versuchen, einen momentan laufenden HTTP-Request
        # sofort zu unterbrechen. Falls requests/liburllib3
        # dies nicht sofort bewirkt, greift spätestens der
        # endliche push_timeout.
        #

        self.server.abort()

    def stop(self):
        self.stop_evt.set()
        self.request_disconnect()

    def _discover(self):
        nxt = self.nxt_factory().open()

        info = nxt.device_info_for_server()

        self.brick = info["brickname"]

        return nxt, info

    def _abort_requested(self):
        return (
            self.stop_evt.is_set()
            or self.disconnect_evt.is_set()
        )

    def _register(self, info):
        """
        Registriert den NXT bei Open Roberta.

        Wichtig:

        Der Token wird außerhalb dieser Methode genau einmal
        erzeugt.

        Ein Netzwerk-Timeout führt NICHT zu einem neuen Token
        und NICHT zu einer erneuten NXT-Erkennung.

        Stattdessen wird die Registrierung mit demselben Token
        erneut versucht.
        """

        payload = dict(
            info,
            token=self.token,
            cmd="register",
        )

        while not self._abort_requested():
            try:
                response = self.server.push(payload)

            except ServerTimeout:
                log.debug(
                    "Registrierung wartet weiter; "
                    "Token %s bleibt gültig",
                    self.token,
                )

                self.emit(
                    State.WAIT_SERVER,
                    f"Warte auf Open Roberta … "
                    f"Token: {self.token}",
                )

                continue

            cmd = response.get("cmd")

            if cmd == "repeat":
                return True

            if cmd == "abort":
                self.emit(
                    State.TOKEN_TIMEOUT,
                    "Open Roberta hat die "
                    "Registrierung beendet",
                )

                return False

            raise RuntimeError(
                "Registrierung: unerwartetes "
                f"Kommando {cmd!r}"
            )

        return False

    def _push(self, info):
        """
        Führt einen normalen Long-Polling-Zyklus aus.

        Auch hier ist ein Read-Timeout kein Verbindungsfehler.
        Wir senden anschließend mit demselben Token den nächsten
        Push-Request.
        """

        payload = dict(
            info,
            token=self.token,
            cmd="push",
        )

        while not self._abort_requested():
            try:
                return (
                    self.server.push(payload),
                    payload,
                )

            except ServerTimeout:
                log.debug(
                    "Push-Long-Polling Timeout; "
                    "Token %s bleibt aktiv",
                    self.token,
                )

                continue

        return None, payload

    def run(self):
        while not self.stop_evt.is_set():
            try:
                #
                # NXT suchen
                #

                self.emit(
                    State.DISCOVER,
                    "Suche NXT …",
                )

                try:
                    self.nxt, info = self._discover()

                except NXTNotFound:
                    time.sleep(1)
                    continue

                #
                # Der NXT darf beim Verbinden nicht bereits
                # ein Programm ausführen.
                #

                if (
                    self.nxt.get_current_program_name()
                    is not None
                ):
                    raise NXTError(
                        "Auf dem NXT läuft bereits "
                        "ein Programm"
                    )

                self.emit(
                    State.READY,
                    f"NXT gefunden: {self.brick}",
                )

                #
                # Auf Benutzeraktion warten.
                #

                while (
                    not self.stop_evt.is_set()
                    and not self.connect_evt.wait(0.2)
                ):
                    if (
                        self.nxt.get_current_program_name()
                        is not None
                    ):
                        raise NXTError(
                            "Auf dem NXT läuft bereits "
                            "ein Programm"
                        )

                if self.stop_evt.is_set():
                    break

                self.connect_evt.clear()
                self.disconnect_evt.clear()

                #
                # Token exakt EINMAL erzeugen.
                #

                self.token = make_token()

                self.emit(
                    State.WAIT_SERVER,
                    f"Token: {self.token}",
                )

                #
                # Registrierung.
                #
                # Timeouts führen innerhalb von _register()
                # lediglich zu einem neuen Versuch mit
                # demselben Token.
                #

                registered = self._register(info)

                if not registered:
                    if self.disconnect_evt.is_set():
                        self.disconnect_evt.clear()

                    continue

                if self._abort_requested():
                    if self.disconnect_evt.is_set():
                        self.disconnect_evt.clear()

                    continue

                #
                # Open Roberta hat den Token akzeptiert.
                #

                self.nxt.melody("connect")

                self.emit(
                    State.CONNECTED,
                    f"Verbunden: {self.brick}",
                )

                #
                # Hauptschleife.
                #

                while not self.stop_evt.is_set():
                    if self.disconnect_evt.is_set():
                        self.disconnect_evt.clear()

                        self.nxt.melody(
                            "disconnect"
                        )

                        break

                    info = (
                        self.nxt
                        .device_info_for_server()
                    )

                    response, payload = (
                        self._push(info)
                    )

                    if response is None:
                        if self.disconnect_evt.is_set():
                            self.disconnect_evt.clear()

                            self.nxt.melody(
                                "disconnect"
                            )

                        break

                    cmd = response.get("cmd")

                    if cmd == "repeat":
                        continue

                    if cmd != "download":
                        raise RuntimeError(
                            "Unerwartetes "
                            "Serverkommando "
                            f"{cmd!r}"
                        )

                    #
                    # Fertiges RXE-Programm laden.
                    #

                    binary, filename = (
                        self.server.download(
                            payload
                        )
                    )

                    #
                    # Auf NXT übertragen und starten.
                    #

                    rxe = (
                        self.nxt.upload_and_start(
                            binary,
                            filename,
                        )
                    )

                    self.nxt.melody(
                        "download"
                    )

                    self.emit(
                        State.RUNNING,
                        f"Programm läuft: {rxe}",
                    )

                    #
                    # Warten, bis der NXT das Programm
                    # beendet hat.
                    #

                    while (
                        not self.stop_evt.is_set()
                        and not self.disconnect_evt.is_set()
                        and self.nxt
                        .get_current_program_name()
                        is not None
                    ):
                        time.sleep(1)

                    if self.disconnect_evt.is_set():
                        self.disconnect_evt.clear()

                        self.nxt.melody(
                            "disconnect"
                        )

                        break

                    self.emit(
                        State.CONNECTED,
                        "Programm beendet",
                    )

            except Exception as exc:
                if not self.stop_evt.is_set():
                    self.emit(
                        State.ERROR,
                        str(exc),
                    )

                    time.sleep(1)

            finally:
                if self.nxt:
                    try:
                        self.nxt.close()
                    except Exception:
                        pass

                    self.nxt = None

                self.token = ""
                self.brick = ""

                self.connect_evt.clear()
                self.disconnect_evt.clear()

        self.server.close()
