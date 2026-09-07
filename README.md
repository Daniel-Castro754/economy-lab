# Economy Lab

## Current version: v2.14.0 — instalação integrada de motores opcionais

Economy Lab is a local-first economic simulation hub with Simple Macro, Economy Zero and Hybrid simulation levels plus independent Dynare/Minsky/Mesa/HARK labs, profiles, real-data/calibration tooling and safe ModelSpec support.

Para instalar Mesa e HARK pelo aplicativo, consulte [Configurações → Motores](docs/MOTORES-INSTALACAO-v2.14.0.md). O instalador base funciona com motores nativos; instalar pacotes no Python do Windows não altera o backend incorporado.

### Backend Completion phase

v2.14.0 is the current source version and controlled milestone on the path to **v3.0 Backend Freeze**. The v2.11 reproducibility contract remains part of that baseline; visual redesign and new economic domains remain frozen.

v2.13.1 makes the persistent Economy Zero job flow observable in the desktop UI, with progress, cancellation, timeout handling, result/failure display and retry controls. It preserves the v2.11 manifest and replay guarantees below.

- Economy Zero ABM owns realized GDP, inflation, unemployment and productive capital.
- Ledger/SFC owns deposits, credit, reserves, debts and bank capital.
- HARK/native heuristic owns desired household consumption policy only.
- Mesa/native activation owns agent activation/order only.
- Dynare owns structural macro IRFs/guidance, never realized GDP.
- Minsky Financial Profiles own financial-control guidance, never ledger balances.
- Hybrid Coupler may own the applied policy-rate signal in a hybrid scenario, but cannot write balances or realized macro outcomes.

A strict `AuthoritySession` rejects unauthorized writes, duplicate canonical writes, missing claims and silent engine fallback. Every Economy Zero result includes an authority audit and Excel exports include the resolved ownership plan.

v2.11 adds a canonical manifest to every new persisted run. It records scenario/result/experiment SHA-256 hashes, seed, Economy Lab/Python/package versions, selected engine trace, profile hashes and explicit data provenance. Replay always uses the immutable stored scenario, creates a new lineage-linked run and reports `matched`, `environment_changed` or `diverged` without silently accepting drift.

API:

- `GET /api/v1/authority/registry`
- `POST /api/v1/authority/plan`
- `POST /api/v1/minsky/export`
- `POST /api/v1/minsky/reconcile`
- `POST /api/v1/jobs/simulations`
- `POST /api/v1/projects/{id}/jobs/simulations`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{id}`
- `POST /api/v1/jobs/{id}/cancel`
- `GET /api/v1/runs/{id}/manifest`
- `POST /api/v1/runs/{id}/replay`

See `docs/REPRODUCIBILITY_V211.md`, `docs/SIMULATION_JOBS_V210.md`, `docs/ROADMAP.md` and `docs/PROJECT_PROGRESS.md`.

## Running it

### Dev mode (any OS, no build required)

Two terminals:

```powershell
# terminal 1 — backend (Python 3.12+)
powershell -ExecutionPolicy Bypass -File scripts\dev-backend.ps1

# terminal 2 — frontend
powershell -ExecutionPolicy Bypass -File scripts\dev-web.ps1
```

Open `http://127.0.0.1:5173`. On macOS/Linux, run the equivalent commands
inside each script manually (create a venv with any compatible Python 3.12+ interpreter, run `uvicorn
economy_lab.main:app --reload`, then `npm install && npm run dev` in
`frontend`).

### Windows desktop installer

There is no prebuilt executable committed to this repository — compiled
binaries are build output, not source, and don't belong in git history.
Instead, the [`Desktop installer`](.github/workflows/desktop-installer.yml)
GitHub Actions workflow builds one on a Windows runner and:

- uploads it as a workflow artifact on every manual run (Actions tab →
  *Desktop installer* → *Run workflow*), or
- publishes it to the repository's [Releases](../../releases) page when a
  `v*` tag is pushed.

The resulting installer bundles the Python backend as a PyInstaller sidecar
(no Python/Node/Rust needed on the target machine) and also carries the
`uv`-based managed-runtime tooling used to install optional engines
(Mesa/HARK) on demand from **Settings → Engines** — see
`docs/MOTORES-INSTALACAO-v2.14.0.md` for how that works and
`docs/validacao/v2.14.0/` for validation evidence.

To build one locally on Windows: `npm run desktop:check` to verify
prerequisites (Python 3.12, Node.js, Rust/MSVC), then `npm run verify`
(backend tests + frontend typecheck/build) before `npm run desktop:build`.
See `docs/DESKTOP_RUNTIME.md` for the sidecar and shutdown handshake.
