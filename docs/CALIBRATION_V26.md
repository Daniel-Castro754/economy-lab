# Calibration v2.6

## What is new

The calibration layer now supports two comparison modes:

1. **Moment** — last value, mean, median or standard deviation.
2. **Aligned path** — real and simulated observations are grouped into the same monthly, quarterly or annual periods and only overlapping periods enter the loss.

Daily/weekly public series are collapsed to monthly when automatic alignment is used because Economy Zero currently runs at monthly frequency.

## Multi-target objective

Each target has an explicit weight. The global loss is a weighted normalized RMSE, which is converted to the existing 0–100 comparison score. The score is useful for comparing candidate configurations under the same target basket; it is not a probability that the model is correct.

## Bounded fitting

Automatic fitting is restricted to an allowlist:

- initial inflation;
- initial unemployment;
- policy rate;
- public-spending change;
- minimum bank capital ratio;
- target reserve ratio;
- labor matching efficiency.

The engine uses a bounded coordinate search and records every attempted value and score. No structural Dynare or HARK parameter is estimated automatically.

## Train / validation

When both dates are supplied, observations through `training_end_date` guide the search. Observations from `validation_start_date` onward are held out and scored only after the best training patch is selected.

This is a basic out-of-sample guardrail, not a substitute for formal econometric identification, cross-validation design or model-selection theory.

## Authority

Calibration produces a proposal. It never changes the ledger, transactions or saved project automatically. A user must review and apply the patch to a ScenarioSpec before another simulation is run.
