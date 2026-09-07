# Minsky Active Financial Profile — v1.7

## Goal

Use Minsky's system-dynamics output inside Simulation Lab without creating a second accounting authority. The integration imports **controls**, never account balances.

## Canonical controls

A Financial Profile may carry a monthly path with:

- `minimum_bank_capital_ratio` (%);
- `target_reserve_ratio` (%);
- `credit_supply_factor` (0.05–1.00);
- `default_writeoff_ratio` (%);
- `interbank_spread` (percentage points);
- `central_bank_penalty_spread` (percentage points).

## Live capture

`POST /api/v1/labs/minsky/financial/run` reads six explicitly mapped Minsky scalar variables through the REST `variableValues` container. The user chooses whether Minsky values are decimals (`0.08`) or percentages (`8`). The endpoint can optionally reset the Minsky model, then captures one point and advances with `step` between observations.

The default variable IDs are only a convention and must exist in the user's `.mky` model:

```text
:bank_min_capital_ratio
:bank_target_reserve_ratio
:credit_supply_factor
:default_writeoff_ratio
:interbank_spread
:cb_penalty_spread
```

## Reproducibility

After capture, the full path is stored in the Profile and copied into `ScenarioSpec.financial_guidance`. Simulation does **not** need a live Minsky connection after that. Historical runs therefore preserve the exact controls used.

## Authority boundary

Minsky may influence behavioral/regulatory banking rules. It cannot set deposits, loans, reserves, bank equity, public debt or other ledger positions directly. Every realized transaction still passes through the Economy Lab double-entry ledger and Godley closure assertions.

## Runtime effects

At the start of each month, Simulation Lab selects the most recent guidance point. The controls affect:

- corporate loan approval fraction and capital-constrained lending;
- required reserve floor used in payment settlement;
- write-off share on modeled firm defaults;
- interbank interest spread;
- central-bank advance penalty spread.

## Compatibility

Old Minsky Profiles containing only introspection/runtime snapshots remain `assistive-only`. Profiles created from the Financial Controller become `active-static` (one point) or `active-path` (multiple points).
