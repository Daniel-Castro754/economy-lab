# v2.8 Authority Registry and canonical EconomyState

## Purpose

Economy Lab combines engines with different semantics. v2.8 freezes a backend rule: no engine may silently become the source of truth for a variable outside its contract.

## Canonical owners

| Canonical field | Owner |
|---|---|
| realized GDP / inflation / unemployment | Economy Zero ABM |
| productive capital | Economy Zero ABM |
| deposits / credit / reserves / debts / bank capital | Ledger + SFC |
| household desired-consumption policy | HARK or native heuristic, selected by scenario |
| agent activation/order policy | Mesa or native activation, selected by scenario |
| structural macro IRF | Dynare |
| applied policy rate | scenario central bank or Hybrid Coupler |
| financial control path | Minsky Financial Profile or native finance |

Dynare is never allowed to claim realized GDP. HARK is never allowed to claim a deposit. Minsky is never allowed to write a ledger balance. Mesa owns activation/order only, not agent balances.

## Strict write claims

`AuthoritySession` resolves an ownership plan from `ScenarioSpec`. Each canonical field may be claimed once per run or once per tick according to its contract.

The runtime rejects:

- an unauthorized source;
- a field that is inactive in the current scenario;
- a second write to the same canonical field/tick, including from the same source;
- a requested engine silently falling back to another runtime;
- missing canonical claims at the end of a simulation.

## Frozen EconomyState v1.0

`economy_lab.core.state.EconomyState` is the inter-engine realized-state contract. It contains:

- `MacroState`: GDP, inflation, unemployment and applied policy rate;
- `RealEconomyState`: productive capital;
- `FinancialState`: household/corporate debt, credit, deposits, reserves, bank capital, central-bank advances, government debt and private net financial wealth;
- `DecisionState`: source labels for activation, household policy, finance controls and macro policy.

Engine-specific objects such as Dynare IRFs, HARK policy functions and Minsky trajectories remain outside realized state.

## API

- `GET /api/v1/authority/registry` returns the static allowed-source contracts.
- `POST /api/v1/authority/plan` accepts a `ScenarioSpec` and returns the active owner selected for each field.
- `SimulationResult.authority` contains the strict runtime audit for the completed simulation.

## Export

Simulation XLSX exports include:

- `Autoridade - resumo`
- `Autoridade - plano`

This allows an archived simulation to show not only its results but also which engine was authoritative for each critical variable.

## Scope boundary

v2.8 does not make Minsky a second accounting engine and does not let Dynare overwrite ABM outcomes. The next backend milestone, v2.9, is controlled Minsky/Godley reconciliation against the Ledger/SFC source of truth.
