import os
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run  # noqa: E402


def test_pick_port_skips_a_busy_port():
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        port = busy.getsockname()[1]
        chosen = run.pick_port(port)
    assert chosen != port and port < chosen <= port + 49


def test_free_port_is_kept():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        free = s.getsockname()[1]
    assert run.pick_port(free) == free


def test_frontend_staleness(tmp_path, monkeypatch):
    fe = tmp_path / "frontend"
    (fe / "src").mkdir(parents=True)
    (fe / "dist").mkdir()
    (fe / "package.json").write_text("{}")
    src = fe / "src" / "App.jsx"
    src.write_text("x")
    index = fe / "dist" / "index.html"
    monkeypatch.setattr(run, "FRONTEND", fe)
    monkeypatch.setattr(run, "DIST_INDEX", index)

    assert run.frontend_is_stale()                       # no build yet
    index.write_text("<html>")
    now = time.time()
    os.utime(src, (now - 100, now - 100))
    os.utime(fe / "package.json", (now - 100, now - 100))
    os.utime(index, (now, now))
    assert not run.frontend_is_stale()                   # build is newer than every source
    os.utime(src, (now + 50, now + 50))
    assert run.frontend_is_stale()                       # a source changed after the build


def test_missing_modules_reports_only_absent_packages(monkeypatch):
    monkeypatch.setattr(run, "REQUIRED_MODULES", {"json": "json-pkg", "definitely_not_installed_xyz": "xyz"})
    assert run.missing_modules() == ["xyz"]
