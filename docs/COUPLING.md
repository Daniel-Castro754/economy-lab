# Macro ↔ micro coupling — v0.9

Economy Lab v0.8 introduced the first **bidirectional** coupling contract between the
Dynare reference DSGE and Economy Zero's ABM/SFC kernel.

## Authority rules

The engines do not vote and their outputs are never averaged.

| Variable/domain | Authority |
|---|---|
| Realized GDP / demand | Economy Zero ABM |
| Realized prices / inflation | Economy Zero ABM |
| Employment / unemployment | Economy Zero ABM |
| Credit, reserves, debt and balance sheets | SFC ledger |
| Structural marginal IRF | Dynare reference NK model |
| Translation / bounded feedback signals | HybridMacroCoupler |

Dynare therefore supplies **guidance**, while the ABM realizes transactions and
the ledger remains the financial source of truth.

## Dynare → ABM channels

A quarterly Dynare IRF is expanded to monthly guidance with an explicit
zero-order hold (the quarterly value is repeated for three months). In hybrid
mode, only a configurable fraction of that signal is transmitted:

1. `policy_rate_gap` changes the monthly policy-rate path;
2. `output_gap` becomes a bounded demand signal affecting consumption,
   production and hiring/layoffs weakly;
3. `inflation_gap` becomes a bounded weak pricing signal.

No macro signal creates a ledger posting directly.

## ABM/SFC → macro feedback

After each ABM month the coupler observes:

- realized GDP index;
- a short-run EWMA output-gap **proxy**;
- realized inflation;
- unemployment;
- credit rationing;
- number of undercapitalized banks.

The coupler computes output/inflation residuals versus Dynare guidance and a
bounded financial-stress score. These update the **next month's** policy and
demand signals.

This feedback controller is deliberately small and transparent. It is not an
estimated central-bank reaction function and is not a substitute for solving a
fully integrated mixed-frequency DSGE-ABM model.

## Scenario controls

- `macro_coupling`: `advisory` or `hybrid`
- `macro_coupling_strength`: 0..1, default 0.35
- `macro_feedback_strength`: 0..1, default 0.15

`hybrid` is invalid when `macro_engine=off`.

## Main limitation

The realized output-gap field in `CouplingReport` is a cyclical proxy based on
an EWMA trend, **not** an estimate of potential output. All coupling weights are
experimental. Calibration and validation against data are future milestones.


## v0.9 quarterly replacement

When `macro_recalibration=quarterly`, the same coupler can replace its future
guidance map after each completed ABM quarter. Months already observed are never
rewritten. See `MACRO_RECALIBRATION.md`.
