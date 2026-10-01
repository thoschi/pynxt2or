from __future__ import annotations
from urllib.parse import urlparse
import requests


class ServerError(Exception):
    pass


class OpenRobertaServer:
    """HTTP client for the Open Roberta connector API.

    /rest/pushcmd is a long-polling endpoint, therefore its read timeout must
    not be too short. Connection establishment, however, should fail quickly.
    """

    CONNECT_TIMEOUT = 5
    READ_TIMEOUT = 60
    DOWNLOAD_TIMEOUT = 30

    def __init__(self, address="https://lab.open-roberta.org", timeout=None, session=None):
        self.connect_timeout = self.CONNECT_TIMEOUT
        self.read_timeout = timeout or self.READ_TIMEOUT
        self.session = session or requests.Session()
        self.set_address(address)

    def set_address(self, address: str):
        if "://" not in address:
            address = "https://" + address
        u = urlparse(address)
        if not u.hostname:
            raise ValueError(f"Ungültige Serveradresse: {address}")
        port = u.port or (443 if u.scheme == "https" else 80)
        default_port = (u.scheme == "https" and port == 443) or (u.scheme == "http" and port == 80)
        host = u.hostname if default_port else f"{u.hostname}:{port}"
        self.base = f"{u.scheme}://{host}"

    def _post(self, path, payload):
        try:
            r = self.session.post(
                self.base + path,
                json=payload,
                headers={"User-Agent": "pynxt2ors/0.5.1"},
                timeout=(self.connect_timeout, self.read_timeout),
            )
            r.raise_for_status()
            return r
        except requests.Timeout as exc:
            raise ServerError(
                f"Zeitüberschreitung beim Open-Roberta-Server {self.base}. "
                "Die Verbindung wurde abgebrochen."
            ) from exc
        except requests.RequestException as exc:
            raise ServerError(f"Open-Roberta-Server {self.base} nicht erreichbar: {exc}") from exc

    def push(self, payload: dict) -> dict:
        r = self._post("/rest/pushcmd", payload)
        try:
            return r.json()
        except ValueError as exc:
            raise ServerError(f"Ungültige Serverantwort: {r.text[:200]}") from exc

    def download(self, payload: dict) -> tuple[bytes, str]:
        r = self._post("/rest/download", payload)
        filename = r.headers.get("Filename")
        if not filename:
            raise ServerError("Download ohne Filename-Header")
        return r.content, filename

    def download_update(self, name: str) -> tuple[bytes, str]:
        try:
            r = self.session.get(
                self.base + "/rest/update/" + name,
                headers={"User-Agent": "pynxt2ors/0.5.1"},
                timeout=(self.connect_timeout, self.DOWNLOAD_TIMEOUT),
            )
            r.raise_for_status()
        except requests.RequestException as exc:
            raise ServerError(str(exc)) from exc
        filename = r.headers.get("Filename") or name.rsplit("/", 1)[-1]
        return r.content, filename

    def abort(self):
        # Closing the pool prevents subsequent requests from reusing a broken
        # connection. The currently blocking request is bounded by READ_TIMEOUT.
        self.session.close()
        self.session = requests.Session()

    def close(self):
        self.session.close()
