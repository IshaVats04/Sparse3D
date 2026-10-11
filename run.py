#!/usr/bin/env python3
"""Start Sparse3D with everything checked first.

    python run.py                 # check, fix what is missing, start, open the browser
    python run.py --port 9000     # preferred port
    python run.py --no-browser

Before starting it
  1. checks the Python version and installs missing Python packages (requirements.txt),
  2. builds the web UI when it is missing or older than its sources (needs Node.js/npm),
  3. finds a free port (an older server on the same port can no longer hide this one),
  4. prints exactly which address to open and which version is running.
"""

import argparse
import importlib.util
import json
import shutil
import socket
import subprocess
import sys
import urllib.request
import webbrowser
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
DIST_INDEX = FRONTEND / "dist" / "index.html"
REQUIRED_MODULES = {"fastapi": "fastapi", "uvicorn": "uvicorn", "cv2": "opencv-python", "open3d": "open3d",
                    "numpy": "numpy", "scipy": "scipy", "httpx": "httpx", "multipart": "python-multipart",
                    "PIL": "Pillow"}


def missing_modules() -> list:
    return [pkg for mod, pkg in REQUIRED_MODULES.items() if importlib.util.find_spec(mod) is None]


def ensure_python_packages() -> None:
    missing = missing_modules()
    if not missing:
        return
    print(f"Installing missing Python packages: {', '.join(missing)}")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])


def frontend_is_stale() -> bool:
    """True when the built UI is missing or any source file is newer than the build."""
    if not DIST_INDEX.is_file():
        return True
    built = DIST_INDEX.stat().st_mtime
    sources = [FRONTEND / "package.json", FRONTEND / "index.html", FRONTEND / "vite.config.js",
               FRONTEND / "tailwind.config.js"]
    sources += [p for p in (FRONTEND / "src").rglob("*") if p.is_file()]
    return any(p.is_file() and p.stat().st_mtime > built for p in sources)


def ensure_frontend() -> str:
    """Build the UI if needed. Returns 'built', 'up to date' or a short reason it is unavailable."""
    if not frontend_is_stale():
        return "up to date"
    npm = shutil.which("npm")
    if npm is None:
        return "NOT built (install Node.js 18+ from https://nodejs.org, then run this again)"
    print("Building the web UI (first run or sources changed) ...")
    try:
        if not (FRONTEND / "node_modules").is_dir():
            subprocess.check_call([npm, "install"], cwd=FRONTEND)
        subprocess.check_call([npm, "run", "build"], cwd=FRONTEND)
    except subprocess.CalledProcessError as exc:
        return f"NOT built (npm failed with exit code {exc.returncode})"
    return "built"


def port_is_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def who_is_on(port: int) -> Optional[str]:
    """Version string of a Sparse3D server answering on the port, or None."""
    try:
        data = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2))
        return f"{data.get('app_name', 'server')} {data.get('version', '?')}"
    except Exception:
        return None


def pick_port(preferred: int) -> int:
    for port in range(preferred, preferred + 50):
        if port_is_free(port):
            if port != preferred:
                other = who_is_on(preferred)
                print(f"Port {preferred} is busy" + (f" ({other}, an older or other server is still running)"
                                                      if other else "") + f"; using {port} instead.")
            return port
    raise SystemExit(f"No free port found between {preferred} and {preferred + 49}.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8000, help="preferred port (default 8000)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)      # show progress immediately, also when output is piped

    if sys.version_info < (3, 10):
        sys.exit(f"Python 3.10 or newer is required (this is {sys.version.split()[0]}).")
    ensure_python_packages()
    ui = ensure_frontend()
    port = pick_port(args.port)

    url = f"http://localhost:{port}"
    print(f"\nSparse3D | web UI: {ui}\nOpen {url}\n")
    if not args.no_browser and not ui.startswith("NOT"):
        webbrowser.open(url)
    return subprocess.call([sys.executable, str(ROOT / "src" / "backend" / "app.py"), "--host", args.host,
                            "--port", str(port)])


if __name__ == "__main__":
    sys.exit(main())
