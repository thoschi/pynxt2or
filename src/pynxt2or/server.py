from __future__ import annotations
from urllib.parse import urlparse
import requests

class ServerError(Exception): pass

class OpenRobertaServer:
    def __init__(self, address="https://lab.open-roberta.org:443", timeout=70, session=None):
        # pushcmd is long-polling. A short 20 s client timeout races the server.
        self.timeout = timeout
        self.session = session or requests.Session()
        self.set_address(address)

    def set_address(self, address: str):
        if "://" not in address: address = "https://" + address
        u = urlparse(address)
        if not u.hostname: raise ValueError(f"Ungültige Serveradresse: {address}")
        port = u.port or (443 if u.scheme == "https" else 80)
        self.base = f"{u.scheme}://{u.hostname}:{port}"

    def _post(self, path, payload):
        try:
            r = self.session.post(self.base + path, json=payload,
                headers={"User-Agent":"pynxt2or/0.4"}, timeout=self.timeout)
            r.raise_for_status(); return r
        except requests.RequestException as exc: raise ServerError(str(exc)) from exc

    def push(self, payload: dict) -> dict:
        r = self._post("/rest/pushcmd", payload)
        try: return r.json()
        except ValueError as exc: raise ServerError(f"Ungültige Serverantwort: {r.text[:200]}") from exc

    def download(self, payload: dict) -> tuple[bytes, str]:
        r = self._post("/rest/download", payload); filename = r.headers.get("Filename")
        if not filename: raise ServerError("Download ohne Filename-Header")
        return r.content, filename

    def download_update(self, name: str) -> tuple[bytes, str]:
        try:
            r = self.session.get(self.base + "/rest/update/" + name,
                headers={"User-Agent":"pynxt2or/0.4"}, timeout=30)
            r.raise_for_status()
        except requests.RequestException as exc: raise ServerError(str(exc)) from exc
        filename = r.headers.get("Filename") or name.rsplit("/", 1)[-1]
        return r.content, filename

    def abort(self):
        self.session.close(); self.session = requests.Session()
    def close(self): self.session.close()
