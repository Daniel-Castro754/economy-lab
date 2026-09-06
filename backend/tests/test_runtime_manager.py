import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from economy_lab import __version__
from economy_lab.main import app
from economy_lab.runtime import manager


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("ECONOMY_LAB_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("ECONOMY_LAB_DB_PATH", raising=False)
    monkeypatch.setenv("ECONOMY_LAB_RUNTIME_RESOURCES", str(tmp_path / "tools"))
    monkeypatch.setattr(manager, "_THREAD", None)
    return tmp_path


def test_activation_rejects_wrong_version_and_path_escape(isolated):
    root = manager.runtime_root()
    outside = isolated / "python.exe"
    outside.touch()
    manager._write(root / "active.json", {"version": __version__, "python": "../../python.exe"})
    assert manager.active_python() is None
    python = root / "environments" / "good" / "python.exe"
    python.parent.mkdir(parents=True)
    python.touch()
    manager._write(root / "active.json", {"version": "0.0.0", "python": str(python.relative_to(root))})
    assert manager.active_python() is None
    manager._write(root / "active.json", {"version": __version__, "python": str(python.relative_to(root))})
    assert manager.active_python() == python.resolve()


def test_failed_install_preserves_previous_environment(isolated, monkeypatch):
    root = manager.runtime_root()
    python = root / "environments" / "working" / "python.exe"
    python.parent.mkdir(parents=True)
    python.touch()
    active = {"version": __version__, "python": str(python.relative_to(root))}
    manager._write(root / "active.json", active)
    tools = manager.resources()
    tools.mkdir()
    (tools / ("uv.exe" if os.name == "nt" else "uv")).touch()
    (tools / f"economy_lab-{__version__}-py3-none-any.whl").touch()
    def fail(*args, **kwargs):
        raise RuntimeError("Download indisponível")
    monkeypatch.setattr(manager, "_run", fail)
    with pytest.raises(RuntimeError, match="Download"):
        manager.install_sync()
    assert manager.active_python() == python.resolve()
    assert manager.status()["state"] == "failed"
    assert list((root / "environments").iterdir()) == [python.parent]


def test_installation_lock_blocks_second_process(isolated):
    lock = manager._installation_lock()
    assert lock is not None
    try:
        result = subprocess.run([sys.executable, "-c", "from economy_lab.runtime.manager import _installation_lock; assert _installation_lock() is None"], capture_output=True)
        assert result.returncode == 0, result.stderr.decode()
    finally:
        lock.close()
    next_lock = manager._installation_lock()
    assert next_lock is not None
    next_lock.close()


def test_untrusted_origin_cannot_install_or_change_paths(isolated, monkeypatch):
    monkeypatch.setenv("ECONOMY_LAB_RUNTIME_MODE", "desktop-sidecar")
    with TestClient(app) as client:
        for origin in ("https://attacker.example", "http://localhost:5173", "null"):
            assert client.post("/api/v1/runtime/engines/install", headers={"Origin": origin}).status_code == 403
            assert client.put("/api/v1/runtime/engines/paths", json={}, headers={"Origin": origin}).status_code == 403
        response = client.post("/api/v1/runtime/engines/install", headers={"Origin": "http://tauri.localhost"})
        assert response.status_code == 409
        assert "Recursos" in response.json()["detail"]


def test_paths_validated_and_loaded(isolated, monkeypatch):
    octave = isolated / "octave-cli.exe"
    octave.touch()
    dynare = isolated / "dynare"
    dynare.mkdir()
    (dynare / "dynare.m").touch()
    monkeypatch.delenv("OCTAVE_EXECUTABLE", raising=False)
    monkeypatch.delenv("DYNARE_MATLAB_PATH", raising=False)
    monkeypatch.delenv("MINSKY_REST_URL", raising=False)
    with TestClient(app) as client:
        assert client.put("/api/v1/runtime/engines/paths", json={"OCTAVE_EXECUTABLE": "does-not-exist"}).status_code == 422
        response = client.put("/api/v1/runtime/engines/paths", json={"OCTAVE_EXECUTABLE": str(octave), "DYNARE_MATLAB_PATH": str(dynare)})
        assert response.status_code == 200
        assert os.environ["OCTAVE_EXECUTABLE"] == str(octave)
        assert client.get("/api/v1/runtime/engines").json()["paths"]["DYNARE_MATLAB_PATH"] == str(dynare)
