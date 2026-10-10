"""Where experiments run: this machine, or a connected remote GPU worker (e.g. Google Colab)."""

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from src.reconstruction import config as cfg

from .remote import RemoteClient, RemoteError, make_connection_code, parse_connection_code  # noqa: F401

MODES = ("auto", "local", "remote")
COLAB_REPO = "IshaVats04/Sparse3D"
COLAB_NOTEBOOK_URL = f"https://colab.research.google.com/github/{COLAB_REPO}/blob/main/notebooks/02_colab_backend.ipynb"
NOTEBOOK_PATH = cfg.PROJECT_ROOT / "notebooks" / "02_colab_backend.ipynb"
COLAB_STEPS = [
    "Open the notebook in Colab",
    "Runtime > Change runtime type > T4 GPU",
    "Runtime > Run all",
    "Wait for the last cell to print a connection code (starts with S3D1.)",
    "Paste the code below and press Connect",
]


def local_capabilities() -> Dict[str, Any]:
    ts = cfg.torch_status()
    return {"gpu": bool(cfg.nvidia_gpu_present() or ts.get("cuda_available")), "gpu_name": cfg.gpu_name(),
            "colmap_available": cfg.find_colmap() is not None, "colmap_gpu_usable": cfg.colmap_can_use_gpu(),
            "neural_available": bool(ts["neural_available"]), "neural_backend": ts.get("neural_backend"),
            "neural_reason": ts.get("neural_reason")}


class ExecutionManager:
    """Persists the execution mode and worker connection and reports what a new experiment would use."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path or (cfg.DATA_ROOT / "workspace" / "execution.json"))
        self.lock = threading.Lock()
        self.mode = "auto"
        self.code: Optional[str] = None
        self._status_cache: Dict[str, Any] = {"t": 0.0, "value": None}
        self._load()

    # ------------------------------------------------------------ persistence
    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("mode") in MODES:
                self.mode = data["mode"]
            self.code = data.get("connection_code")
        except (OSError, ValueError):
            pass

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"mode": self.mode, "connection_code": self.code}), encoding="utf-8")
        except OSError:
            pass

    # ------------------------------------------------------------ remote
    def client(self) -> Optional[RemoteClient]:
        if not self.code:
            return None
        try:
            url, token = parse_connection_code(self.code)
        except ValueError:
            return None
        return RemoteClient(url, token)

    def remote_status(self, force: bool = False) -> Optional[Dict[str, Any]]:
        client = self.client()
        if client is None:
            return None
        with self.lock:
            cached = self._status_cache
            if not force and cached["value"] is not None and time.time() - cached["t"] < 10:
                return cached["value"]
        status: Dict[str, Any] = {"configured": True, "connected": False, "host": client.host, "gpu": None,
                                  "gpu_name": None, "colmap_available": None, "colmap_gpu_usable": None,
                                  "neural_available": None, "neural_backend": None, "neural_reason": None,
                                  "error": None, "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        try:
            env = client.health()
            status.update(connected=True, gpu=bool(env.get("gpu")), gpu_name=env.get("gpu_name"),
                          colmap_available=env.get("colmap_available"), colmap_gpu_usable=env.get("colmap_gpu_usable"),
                          neural_available=env.get("neural_available"), neural_backend=env.get("neural_backend"),
                          neural_reason=env.get("neural_reason"))
        except RemoteError as exc:
            status["error"] = str(exc)
        with self.lock:
            self._status_cache = {"t": time.time(), "value": status}
        return status

    def connect(self, code: str) -> None:
        """Validate a connection code against the worker, then store it. Raises ValueError / RemoteError."""
        url, token = parse_connection_code(code)
        RemoteClient(url, token).health()
        with self.lock:
            self.code = code.strip()
            self._status_cache = {"t": 0.0, "value": None}
            self._save()

    def disconnect(self) -> None:
        with self.lock:
            self.code = None
            self._status_cache = {"t": 0.0, "value": None}
            self._save()

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        with self.lock:
            self.mode = mode
            self._save()

    # ------------------------------------------------------------ decision
    def decide(self) -> Dict[str, Any]:
        """Which target a new experiment would use, and why."""
        local = local_capabilities()
        remote = self.remote_status()
        connected = bool(remote and remote["connected"])
        if self.mode == "local":
            return {"effective": "local", "reason": "Set to run on this computer", "local": local, "remote": remote}
        if self.mode == "remote":
            reason = ("Set to run on the remote worker" if connected else
                      "Set to run on the remote worker, but none is connected")
            return {"effective": "remote", "reason": reason, "local": local, "remote": remote}
        if connected and not local["gpu"]:
            return {"effective": "remote", "local": local, "remote": remote,
                    "reason": "This machine has no GPU; using the connected remote worker"}
        if connected:
            return {"effective": "local", "local": local, "remote": remote,
                    "reason": "This machine has a GPU; running here (a remote worker is connected as a spare)"}
        reason = ("This machine has a GPU" if local["gpu"] else
                  "This machine has no GPU and no remote worker is connected: dense reconstruction and the neural "
                  "method will be limited. Connect a Colab worker to use a GPU")
        return {"effective": "local", "reason": reason, "local": local, "remote": remote}

    def status(self) -> Dict[str, Any]:
        d = self.decide()
        eff = d["remote"] if d["effective"] == "remote" and d["remote"] and d["remote"]["connected"] else d["local"]
        caps = {k: eff.get(k) for k in ("gpu", "colmap_available", "colmap_gpu_usable", "neural_available",
                                        "neural_backend", "neural_reason")}
        return {"mode": self.mode, "effective": d["effective"], "reason": d["reason"], "local": d["local"],
                "remote": d["remote"], "capabilities": caps,
                "colab": {"notebook_open_url": COLAB_NOTEBOOK_URL, "notebook_download_url": "/api/colab/notebook",
                          "steps": COLAB_STEPS}}
