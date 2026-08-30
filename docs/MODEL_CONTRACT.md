# Model contract

## Input

`ScenarioSpec` is the only public scenario input contract.

Current Economy Zero parameters include:

- horizon in months;
- initial unemployment;
- policy rate;
- income tax;
- public spending change;
- number of households/firms/banks;
- deterministic random seed;
- activation engine: `native` or `mesa`;
- household behavior: `heuristic` or `hark`.

Legacy demo fields are retained for API compatibility but are not all consumed by Economy Zero.

## Output

Each month exposes:

- real GDP index;
- price index and inflation;
- unemployment;
- policy rate;
- household consumption;
- government spending;
- corporate debt;
- bank credit/deposits;
- household deposit-wealth Gini;
- firm default events.

Each simulation also returns an `engines` trace identifying the activation, household-decision and accounting components that actually produced the run.

## Engine ownership rule

- Mesa may choose activation order, but does not own balances.
- HARK may recommend household consumption, but does not post transactions.
- The Economy Lab ledger owns realized financial positions.
- Future Minsky/Dynare adapters must use validated domain/state transitions instead of silently overwriting shared variables.

## Macro fields — v0.7

`ScenarioSpec` adds an optional macro request that remains separate from the
realised ABM/SFC state:

```yaml
macro_engine: off | dynare
dynare_monetary_shock_bp: 100
dynare_irf_periods: 24
```

When `macro_engine: dynare`, the response contains `macro: MacroReport` with a
quarterly IRF. `MacroReport.coupling_mode` is `advisory-only` in v0.7. No field
inside that report is allowed to mutate the ledger or overwrite realised
Economy Zero aggregates.

## Coupling fields — v0.8

`ScenarioSpec` adds `macro_coupling`, `macro_coupling_strength` and
`macro_feedback_strength`. `SimulationResult.coupling` records the authority
map and every monthly guide/feedback observation. `hybrid` requires
`macro_engine=dynare`.


## Quarterly macro fields — v0.9

```yaml
macro_recalibration: static_irf | quarterly
macro_recalibration_strength: 0.25
macro_max_recalibrations: 20
```

`quarterly` requires Dynare + hybrid coupling. The response may include
`macro_recalibration: MacroRecalibrationReport`.
