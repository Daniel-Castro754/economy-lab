# Quarterly macro re-solve — v0.9

v0.9 adds an optional quarterly loop from realized Economy Zero state back into
Dynare. It proves the orchestration contract for repeated macro solves; it is
**not** online DSGE estimation.

## Loop

1. Run three ABM/SFC months under the current bounded macro guidance.
2. Freeze the completed quarter; historical ledger postings are immutable.
3. Extract a small macro vector: GDP index/growth, inflation, unemployment,
   policy rate, bank credit/growth, bank capital ratio and financial stress.
4. Map that vector to bounded reference-model settings.
5. Re-run the fixed Economy Lab New-Keynesian Dynare template.
6. Replace only future monthly guidance beginning with the next month.
7. Continue the ABM and repeat at the next completed quarter.

## What is adapted

The current bridge permits small bounded changes in `sigma`, `kappa`, `rho_i`,
`phi_pi` and `phi_x`, plus a decaying effective monetary impulse and a new
policy-rate baseline. Every value is returned in `MacroRecalibrationReport`.

This mapping is intentionally transparent and conservative. These coefficients
must **not** be interpreted as estimated time-varying structural parameters.
Formal calibration/estimation is a later milestone.

## Safety / stability rules

- quarterly mode requires `macro_engine=dynare` and `macro_coupling=hybrid`;
- adaptation strength is constrained to 0..1;
- every adapted parameter has hard bounds;
- the effective impulse decays over time and is bounded;
- only future guidance is replaced;
- no re-solve can post directly to the ledger;
- a configurable maximum number of re-solves prevents runaway execution (default 80, enough for the maximum 240-month scenario).

## Authority

Realized GDP, inflation and unemployment remain ABM outputs. Credit, reserves,
debt and balance sheets remain SFC-ledger outputs. Dynare owns a structural
reference trajectory only, even when it is re-solved each quarter.
