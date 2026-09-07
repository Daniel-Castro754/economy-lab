from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from threading import Lock, Thread
from uuid import uuid4

from economy_lab import __version__
from economy_lab.storage import resolve_database_path

_STATE_LOCK = Lock()
_PROCESS_LOCK = Lock()
_THREAD: Thread | None = None


def runtime_root() -> Path:
    return resolve_database_path().parent / "runtime"


def resources() -> Path:
    return Path(os.environ.get("ECONOMY_LAB_RUNTIME_RESOURCES", str(Path(sys.executable).parent / "runtime-tools")))


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def active_python() -> Path | None:
    root = runtime_root().resolve()
    active = _read(root / "active.json")
    if active.get("version") != __version__:
        return None
    relative = active.get("python", "")
    if not relative or Path(relative).is_absolute():
        return None
    path = (root / relative).resolve()
    if not path.is_relative_to(root / "environments") or not path.is_file():
        return None
    return path


def subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    if "LD_LIBRARY_PATH_ORIG" in env:
        env["LD_LIBRARY_PATH"] = env.pop("LD_LIBRARY_PATH_ORIG")
    elif getattr(sys, "frozen", False):
        env.pop("LD_LIBRARY_PATH", None)
    bundled = str(getattr(sys, "_MEIPASS", ""))
    if bundled:
        env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep) if not p.startswith(bundled))
    return env


def spawn(command: list[str], **kwargs) -> subprocess.Popen:
    # PyInstaller changes Windows DLL lookup for its own binary. External
    # Python/uv processes must inherit the normal system DLL search path.
    with _PROCESS_LOCK:
        if os.name == "nt" and getattr(sys, "frozen", False):
            import ctypes
            ctypes.windll.kernel32.SetDllDirectoryW(None)
            try:
                return subprocess.Popen(command, creationflags=subprocess.CREATE_NO_WINDOW, **kwargs)
            finally:
                ctypes.windll.kernel32.SetDllDirectoryW(str(sys._MEIPASS))
        return subprocess.Popen(command, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0, **kwargs)


def status() -> dict:
    root = runtime_root()
    state = _read(root / "installation.json") or {"state": "idle", "progress": 0, "message": "Motores opcionais ainda não preparados."}
    if state.get("state") == "installing" and not installation_running():
        # No active worker in this backend: a previous app session was closed.
        state = {**state, "state": "interrupted", "message": "A instalação foi interrompida. Clique em instalar para tentar novamente."}
    python = active_python()
    return {
        **state,
        "managed_directory": str(root),
        "managed_python": str(python) if python else None,
        "active_python": sys.executable,
        "backend_kind": "managed" if os.getenv("ECONOMY_LAB_MANAGED_BACKEND") == "1" else "bundled" if getattr(sys, "frozen", False) else "development",
        "installer_available": (resources() / ("uv.exe" if os.name == "nt" else "uv")).is_file() and bool(list(resources().glob("economy_lab-*.whl"))),
        "restart_required": python is not None and Path(sys.executable).resolve() != python.resolve(),
        "paths": _read(root / "engine-paths.json"),
        "commands_directory": str(root / "bin"),
    }


def _state(state: str, progress: int, message: str, **extra) -> None:
    _write(runtime_root() / "installation.json", {"state": state, "progress": progress, "message": message, **extra})


def _run(command: list[str], env: dict, log, timeout: int = 1200) -> None:
    process = spawn(command, env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, cwd=str(resources()))
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise RuntimeError("Tempo limite da instalação excedido; confira a conexão e tente novamente.") from None
    if code:
        raise RuntimeError(f"A preparação dos motores retornou código {code}. Consulte o diagnóstico da instalação.")


def _create_commands(python: Path, uv: Path) -> str | None:
    root = runtime_root()
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        return None
    # Distinct names preserve the user's normal python/pip commands.
    for name, command in {
        "economy-lab-python.cmd": f'"{python}" %*',
        "economy-lab-pip.cmd": f'"{python}" -m pip %*',
    }.items():
        (bin_dir / name).write_text("@echo off\n" + command + "\n", encoding="utf-8")
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            try:
                existing, kind = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                existing, kind = "", winreg.REG_EXPAND_SZ
            parts = [p for p in existing.split(";") if p]
            if str(bin_dir).casefold() not in [p.rstrip("\\").casefold() for p in parts]:
                winreg.SetValueEx(key, "Path", 0, kind, existing.rstrip(";") + (";" if existing else "") + str(bin_dir))
        import ctypes
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x1A, 0, ctypes.c_wchar_p("Environment"), 2, 2000, None)
        return None
    except Exception:
        return "Motores instalados. Não foi possível adicionar os comandos ao PATH; o aplicativo usa o caminho absoluto e pode utilizá-los normalmente."


def _installation_lock():
    root = runtime_root()
    root.mkdir(parents=True, exist_ok=True)
    lock = (root / "installation.lock").open("a+b")
    if lock.tell() == 0:
        lock.write(b"0")
        lock.flush()
    lock.seek(0)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock.close()
        return None
    return lock


def installation_running() -> bool:
    if _THREAD and _THREAD.is_alive():
        return True
    lock = _installation_lock()
    if lock is None:
        return True
    lock.close()
    return False


def install_sync() -> None:
    lock = _installation_lock()
    if lock is None:
        raise RuntimeError("Uma instalação já está em andamento em outra janela.")
    try:
        _install_candidate()
    finally:
        lock.close()


def _install_candidate() -> None:
    root = runtime_root()
    candidate = root / "environments" / f"{__version__}-{uuid4().hex[:12]}"
    uv = resources() / ("uv.exe" if os.name == "nt" else "uv")
    wheel = resources() / f"economy_lab-{__version__}-py3-none-any.whl"
    if not uv.is_file() or not wheel.is_file():
        raise RuntimeError("Este pacote não contém os recursos do instalador de motores. Reinstale o Economy Lab atualizado.")
    root.mkdir(parents=True, exist_ok=True)
    env = subprocess_env()
    env.update(UV_PYTHON_INSTALL_DIR=str(root / "python"), UV_CACHE_DIR=str(root / "cache"), UV_NO_CONFIG="1", UV_NO_PROGRESS="1")
    activated = False
    try:
        with (root / "installation.log").open("w", encoding="utf-8") as log:
            _state("installing", 10, "Preparando Python próprio do Economy Lab…")
            _run([str(uv), "venv", "--python", "3.12", "--managed-python", "--seed", str(candidate)], env, log)
            python = candidate / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            _state("installing", 35, "Instalando Mesa, HARK e dependências…")
            _run([str(uv), "pip", "install", "--python", str(python), str(wheel) + "[simulation]"], env, log)
            _state("installing", 80, "Testando os motores no ambiente instalado…")
            _run([str(python), "-m", "economy_lab.runtime.verify"], env, log, timeout=300)
            # Only a tested candidate can replace the active environment.
            _write(root / "active.json", {"version": __version__, "python": str(python.relative_to(root))})
            activated = True
            warning = _create_commands(python, uv)
            _state("ready", 100, warning or "Mesa e HARK instalados e testados. Feche e abra o Economy Lab para ativá-los.")
    except Exception as exc:
        _state("failed", 0, str(exc))
        if not activated:
            shutil.rmtree(candidate, ignore_errors=True)
        raise


def start_install() -> dict:
    global _THREAD
    with _STATE_LOCK:
        if installation_running():
            return status()
        if not status()["installer_available"]:
            raise RuntimeError("Recursos de instalação indisponíveis neste pacote.")
        def worker():
            try:
                install_sync()
            except Exception:
                pass  # Failure is persisted for the UI and survives restarts.
        _state("installing", 1, "Iniciando instalação dos motores…")
        _THREAD = Thread(target=worker, name="economy-lab-runtime-install", daemon=True)
        _THREAD.start()
        return status()


def installation_log() -> str:
    path = runtime_root() / "installation.log"
    try:
        with path.open("rb") as log:
            log.seek(max(0, path.stat().st_size - 24000))
            return log.read().decode("utf-8", errors="replace")
    except OSError:
        return "Nenhuma instalação registrada."


def save_paths(values: dict[str, str]) -> dict:
    cleaned = {k: str(v).strip().strip('"') for k, v in values.items()}
    octave = cleaned.get("OCTAVE_EXECUTABLE", "")
    dynare = cleaned.get("DYNARE_MATLAB_PATH", "")
    if octave and not Path(octave).is_file():
        raise ValueError("O executável do Octave não foi encontrado nesse caminho.")
    if dynare and not (Path(dynare) / "dynare.m").is_file():
        raise ValueError("A pasta do Dynare precisa conter dynare.m (geralmente a pasta matlab).")
    if cleaned.get("MINSKY_REST_URL"):
        from economy_lab.engines.minsky_adapter import _validated_minsky_rest_url
        cleaned["MINSKY_REST_URL"] = _validated_minsky_rest_url(cleaned["MINSKY_REST_URL"])
    _write(runtime_root() / "engine-paths.json", cleaned)
    load_paths()
    return cleaned


def load_paths() -> None:
    for key, value in _read(runtime_root() / "engine-paths.json").items():
        if key in {"OCTAVE_EXECUTABLE", "DYNARE_MATLAB_PATH", "MINSKY_REST_URL"}:
            if value:
                os.environ[key] = str(value)
            else:
                os.environ.pop(key, None)
