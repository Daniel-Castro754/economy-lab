# Desktop runtime — v1.1

Economy Lab desktop is a Tauri 2 shell that owns the lifecycle of a bundled Python backend sidecar.

## Startup

1. Tauri asks the OS for a free loopback TCP port.
2. It generates a per-process runtime instance id and shutdown token.
3. It spawns `economy-lab-backend` as a Tauri sidecar bound to `127.0.0.1` only.
4. Tauri polls `/api/v1/health` until the response contains the expected instance id.
5. The main window is shown and React gets the dynamic backend URL through the `backend_api_base` Tauri command.

The web build does not use this mechanism. Outside Tauri, React falls back to `VITE_API_URL` or `http://127.0.0.1:8765/api/v1`.

## Shutdown

On the first Tauri `ExitRequested` event the shell prevents immediate exit, calls the token-protected `/api/v1/runtime/shutdown` endpoint and gives Uvicorn a short grace period to stop. A direct child-process kill is retained only as a fallback. The second exit request is allowed to complete.

The shutdown route exists only when `ECONOMY_LAB_SHUTDOWN_TOKEN` is injected by the desktop shell. Ordinary web/development backends return 404 for this route.

## Packaging

`scripts/build-sidecar.ps1` creates a Python 3.12 environment, installs the backend and PyInstaller, optionally includes Mesa/HARK, builds a one-file backend executable and copies it to the Tauri target-triple naming convention under `src-tauri/binaries/`.

Useful commands on Windows:

```powershell
npm run desktop:check
npm run desktop
npm run desktop:build
```

Use `-SkipSimulationEngines` directly with the PowerShell scripts when you need a smaller/faster package that keeps native activation and heuristic household behavior but omits bundled Mesa/HARK.

## Security boundary

- backend binds to loopback only;
- desktop shutdown requires a per-process token;
- the dynamically chosen API port is not hard-coded;
- user/AI content still reaches the kernel only through validated API contracts;
- no shell capability is exposed to frontend JavaScript for starting arbitrary processes.

## v1.2 persistent data directory

The Tauri shell resolves its OS-specific application-data directory and passes it to the sidecar as `ECONOMY_LAB_DATA_DIR`. The backend stores `economy-lab.sqlite3` there, so projects survive application restarts and application upgrades that preserve the app-data directory.

For diagnostics or portable development, `ECONOMY_LAB_DB_PATH` can override the exact SQLite file path.

## v2.14 managed optional engines

The Tauri resources now include a standalone uv executable and a wheel of the matching backend. The shell passes their absolute directory through ECONOMY_LAB_RUNTIME_RESOURCES. Configurações → Motores prepares an isolated per-user Python, installs the wheel with simulation extras and runs real engine verification before atomically activating it.

On the next launch, the frozen sidecar delegates to that version-matched interpreter and forwards the loopback port, instance identifier and shutdown token. Windows DLL lookup inherited from PyInstaller is reset for external processes. PythonHOME/PYTHONPATH are not inherited. The desktop shell retains the same API discovery and shutdown contract.

See MOTORES-INSTALACAO-v2.14.0.md for PATH commands, external program paths and recovery. The fixed install endpoint accepts no package name or shell command from the frontend.
