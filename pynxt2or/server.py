from __future__ import annotations

from urllib.parse import urlparse

import requests


class ServerError(Exception):
    """Allgemeiner Fehler bei der Kommunikation mit Open Roberta."""


class ServerTimeout(ServerError):
    """
    Der Server hat innerhalb des vorgesehenen Long-Polling-Zeitraums
    nicht geantwortet.

    Das ist bei /rest/pushcmd kein fataler Fehler. Der Connector darf
    denselben Request mit demselben Token erneut senden.
    """


class OpenRobertaServer:
    def __init__(
        self,
        address="https://lab.open-roberta.org:443",
        connect_timeout=10,
        push_timeout=30,
        request_timeout=30,
        session=None,
    ):
        self.connect_timeout = connect_timeout
        self.push_timeout = push_timeout
        self.request_timeout = request_timeout

        self.session = session or requests.Session()

        self.set_address(address)

    def set_address(self, address: str):
        if "://" not in address:
            address = "https://" + address

        parsed = urlparse(address)

        if not parsed.hostname:
            raise ValueError(
                f"Ungültige Serveradresse: {address}"
            )

        port = parsed.port or (
            443 if parsed.scheme == "https" else 80
        )

        self.base = (
            f"{parsed.scheme}://{parsed.hostname}:{port}"
        )

    def _post(
        self,
        path: str,
        payload: dict,
        *,
        read_timeout: float,
    ):
        try:
            response = self.session.post(
                self.base + path,
                json=payload,
                headers={
                    "User-Agent": "pynxt2or/0.3",
                },
                timeout=(
                    self.connect_timeout,
                    read_timeout,
                ),
            )

            response.raise_for_status()

            return response

        except requests.exceptions.ReadTimeout as exc:
            raise ServerTimeout(
                f"Open Roberta antwortete innerhalb von "
                f"{read_timeout:g} Sekunden nicht"
            ) from exc

        except requests.exceptions.ConnectTimeout as exc:
            raise ServerError(
                "Zeitüberschreitung beim Verbindungsaufbau "
                "zu Open Roberta"
            ) from exc

        except requests.RequestException as exc:
            raise ServerError(str(exc)) from exc

    def push(self, payload: dict) -> dict:
        """
        Registrierung und Long-Polling über /rest/pushcmd.

        Ein Read-Timeout wird als ServerTimeout signalisiert.
        Der Connector entscheidet anschließend, ob derselbe Request
        erneut gesendet oder die Verbindung beendet wird.
        """

        response = self._post(
            "/rest/pushcmd",
            payload,
            read_timeout=self.push_timeout,
        )

        try:
            return response.json()

        except ValueError as exc:
            raise ServerError(
                "Ungültige Serverantwort: "
                f"{response.text[:200]}"
            ) from exc

    def download(
        self,
        payload: dict,
    ) -> tuple[bytes, str]:
        """
        Fertig kompiliertes NXT-Programm herunterladen.
        """

        response = self._post(
            "/rest/download",
            payload,
            read_timeout=self.request_timeout,
        )

        filename = response.headers.get("Filename")

        if not filename:
            raise ServerError(
                "Download ohne Filename-Header"
            )

        return response.content, filename

    def abort(self):
        """
        Die aktuelle HTTP-Session schließen.

        Der Connector verlässt sich für eine garantiert zeitnahe
        Reaktion zusätzlich auf den endlichen push_timeout.
        """

        self.session.close()
        self.session = requests.Session()

    def close(self):
        self.session.close()
