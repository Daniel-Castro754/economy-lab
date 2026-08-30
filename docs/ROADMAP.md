# Controlled backend roadmap

## Current milestone: v2.11 Reproducibility / Run Manifest

The project is in **Backend Completion**. Visual redesign and new economic domains remain frozen until backend contracts are stable.

### Backend completion sequence

1. **v2.7 — External Engine Real Qualification — infrastructure complete, target-machine evidence pending**
   - staged Mesa/HARK/Dynare/Minsky evidence;
   - real integration smoke paths;
   - Windows qualification report.
2. **v2.8 — Authority Registry + engine contracts — implemented**
   - explicit ownership of canonical state variables;
   - strict conflict/duplicate-write detection;
   - frozen `EconomyState` v1.0 inter-engine contract;
   - no silent engine fallback.
3. **v2.9 — Minsky reconciliation + SFC final — implemented**
   - controlled, hashed Godley reconciliation against a known `.mky` template;
   - explicit mapping, sign/unit conversion, coverage and tolerance contracts;
   - provided-snapshot and verified live read-only capture modes;
   - no competing source of truth and no ledger mutation path.
4. **v2.10 — Simulation jobs — implemented**
   - queued/running/completed/failed/cancelled;
   - persistent monotonic progress and cooperative cancellation;
   - bounded worker pool, crash recovery and external-engine hard timeouts.
5. **v2.11 — Reproducibility / Run Manifest — implemented**
   - versions, seeds, profiles, data provenance and experiment hash;
   - verified replay with immutable lineage and drift reporting.
6. **v2.12 — Live data qualification + Calibration Profiles**
   - BCB/IBGE/World Bank/Ipeadata live qualification;
   - reusable calibrated profiles.
7. **v2.13 — AI providers + persistent ModelSpec**
   - provider contract, at least one real provider, artifact persistence;
   - no direct code execution.
8. **v2.14 — hardening**
   - DB backup/migrations, logging, diagnostic export.
9. **v2.15 — stress/performance/golden tests**
   - release benchmarks and invariant suite.
10. **v3.0 — BACKEND FREEZE**
   - backend contract freeze; visual/product redesign becomes the primary workstream.

### Scope lock

Until v3.0, do not add new economic domains such as detailed housing, crypto, climate, energy or full industry matrices unless required to fix an existing backend contract.
