# Economy Lab

## Current version: v2.11 — reproducible run manifests and replay

Economy Lab is a local-first economic simulation hub with Simple Macro, Economy Zero and Hybrid simulation levels plus independent Dynare/Minsky/Mesa/HARK labs, profiles, real-data/calibration tooling and safe ModelSpec support.

### Backend Completion phase

v2.11 is the fifth controlled milestone on the path to **v3.0 Backend Freeze**. Visual redesign and new economic domains remain frozen.

The key backend contract is now executable, not only documented:

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

## Executável na raiz

`EconomyLab.exe` is kept directly in the package root beside `backend`, `docs`, `frontend`, `scripts` and `src-tauri` so it is easy to locate. This package still carries the Windows x64 preview executable; the final full Tauri build is part of the backend/release qualification sequence before v3.0.
