"""Client for a remote Sparse3D worker (the same backend, started on a GPU machine such as a Colab runtime).

A worker is identified by a *connection code*, the single string the Colab notebook prints:

    S3D1.<urlsafe base64 of {"u": "<https url>", "t": "<access token>"}>

The token is sent in the `X-Sparse3D-Token` header on every request and is checked by the worker.
"""

import base64
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

CODE_PREFIX = "S3D1."
TOKEN_HEADER = "X-Sparse3D-Token"


class RemoteError(RuntimeError):
    """The worker could not be reached or refused the request. The message is meant for the user."""


def make_connection_code(url: str, token: str) -> str:
    raw = json.dumps({"u": url, "t": token}, separators=(",", ":")).encode()
    return CODE_PREFIX + base64.urlsafe_b64encode(raw).decode().rstrip("=")


def parse_connection_code(code: str) -> Tuple[str, str]:
    """Return (base_url, token), or raise ValueError with a readable message."""
    code = (code or "").strip()
    if not code.startswith(CODE_PREFIX):
        raise ValueError(f"A connection code starts with '{CODE_PREFIX}'. Copy it from the last cell of the notebook.")
    body = code[len(CODE_PREFIX):]
    try:
        data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        url, token = str(data["u"]).rstrip("/"), str(data["t"])
    except Exception:
        raise ValueError("The connection code is damaged. Copy it again from the notebook, without extra spaces.")
    parsed = urlparse(url)
    local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
    if parsed.scheme not in ("http", "https") or not parsed.hostname or (parsed.scheme == "http" and not local):
        raise ValueError("The connection code must point to an https address.")
    if not token:
        raise ValueError("The connection code has no access token.")
    return url, token


class RemoteClient:
    def __init__(self, url: str, token: str):
        self.url, self.token = url.rstrip("/"), token

    @property
    def host(self) -> str:
        return urlparse(self.url).hostname or self.url

    def _request(self, method: str, path: str, timeout: float = 20.0, **kw: Any) -> httpx.Response:
        try:
            r = httpx.request(method, self.url + path, headers={TOKEN_HEADER: self.token}, timeout=timeout, **kw)
        except httpx.TimeoutException:
            raise RemoteError(f"The worker at {self.host} did not answer in time.")
        except httpx.HTTPError as exc:
            raise RemoteError(f"Cannot reach the worker at {self.host} ({type(exc).__name__}). "
                              "Is the Colab notebook still running?")
        if r.status_code == 401:
            raise RemoteError("The worker rejected the access token. Reconnect with a fresh connection code.")
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except Exception:
                detail = r.text
            raise RemoteError(f"The worker answered {r.status_code}: {str(detail)[:300]}")
        return r

    def health(self) -> Dict[str, Any]:
        data = self._request("GET", "/api/health", timeout=8.0).json()
        if data.get("app_name") != "3D RECON LAB":
            raise RemoteError(f"{self.host} is not a Sparse3D worker.")
        return data["environment"]

    def submit(self, images: List[Path], fields: Dict[str, str], ground_truth: Optional[Path] = None) -> str:
        files = [("images", (p.name, p.read_bytes(), "application/octet-stream")) for p in images]
        if ground_truth is not None:
            files.append(("ground_truth", (ground_truth.name, ground_truth.read_bytes(), "application/octet-stream")))
        r = self._request("POST", "/api/jobs", timeout=300.0, data=fields, files=files)
        return r.json()["job_id"]

    def get(self, job_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/api/jobs/{job_id}", timeout=15.0).json()

    def cancel(self, job_id: str) -> None:
        self._request("POST", f"/api/jobs/{job_id}/cancel", timeout=15.0)

    def delete(self, job_id: str) -> None:
        self._request("DELETE", f"/api/jobs/{job_id}", timeout=15.0)

    def download(self, job_id: str, file_type: str, dest: Path) -> bool:
        """Stream one output file to `dest`. Returns False if the worker does not have it."""
        try:
            with httpx.stream("GET", f"{self.url}/api/jobs/{job_id}/files/{file_type}",
                              headers={TOKEN_HEADER: self.token}, timeout=300.0) as r:
                if r.status_code == 404:
                    return False
                if r.status_code >= 400:
                    raise RemoteError(f"The worker answered {r.status_code} for {file_type}")
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, "wb") as f:
                    for chunk in r.iter_bytes():
                        f.write(chunk)
        except httpx.HTTPError as exc:
            raise RemoteError(f"Download of {file_type} failed ({type(exc).__name__})")
        return True
