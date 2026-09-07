# Modular Hub — v1.4

Economy Lab is now organized as a hub of explicit modules. A module declares its capabilities, dependencies, runtime status and public API contracts.

## Modules

- **Simulation Lab** — native Economy Zero execution, shocks, batch experiments, charts and CSV/XLSX exports.
- **Dynare** — DSGE, IRFs, monetary policy and quarterly macro re-solves.
- **Minsky** — SFC/Godley exchange and REST synchronization.
- **Mesa** — agent activation and AgentSet infrastructure.
- **HARK / Econ-ARK** — heterogeneous household consumption/saving decisions.
- **Analytics** — Python statistics with optional DuckDB aggregation.
- **Scenario AI** — safe natural-language compilation into validated `ScenarioSpec`.

The registry endpoint is `GET /api/v1/modules`. External tools remain visible when unavailable; the Hub never silently substitutes them.

## Design rule

External software does not own the Economy Lab ledger. Each adapter exposes a bounded capability. The Simulation Lab composes those capabilities through validated contracts and keeps realized ABM/SFC state authoritative where already defined by the model contract.

## Reporting

The Simulation Lab owns presentation/export concerns. This keeps scientific engines independent from UI formats.

- `POST /api/v1/exports/simulation.csv`
- `POST /api/v1/exports/simulation.xlsx`
- `POST /api/v1/exports/batch.csv`
- `POST /api/v1/exports/batch.xlsx`

Simulation XLSX workbooks contain summary, scenario, monthly series and, when available, sector balances, Godley matrices, banks, Dynare IRFs and coupling diagnostics.
