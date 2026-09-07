# Dynare / Octave bridge — v0.7

## Goal

Dynare is an optional macro engine. Economy Lab remains the source of truth for
agents, realised transactions, balance sheets and SFC identities. Dynare does
not write directly into the ledger in v0.7.

The first built-in model is a compact quarterly New-Keynesian DSGE with:

- dynamic IS curve;
- forward-looking Phillips curve;
- smoothed Taylor rule;
- natural-rate shock process;
- cost-push shock process;
- configurable monetary-policy innovation.

All reported Dynare variables are percentage-point deviations from steady
state. The current UI exposes the monetary-policy IRF first.

## Local execution contract

The backend locates:

1. GNU Octave (`octave-cli` preferred);
2. the Dynare `matlab` directory.

Automatic Windows Dynare discovery checks `C:\dynare\<version>\matlab`.
When Octave or Dynare is elsewhere, set:

```powershell
$env:OCTAVE_EXECUTABLE = "C:\path\to\octave-cli.exe"
$env:DYNARE_MATLAB_PATH = "C:\dynare\7.1\matlab"
```

The API endpoint `GET /api/v1/dynare/status` reports whether both components are
ready.

## Run sequence

```text
ScenarioSpec
    │
    ├── dynare_monetary_shock_bp
    └── dynare_irf_periods
            │
            ▼
known Economy Lab .mod template
            │
            ▼
Octave subprocess
            │
            ▼
Dynare preprocessor + solver
            │
            ▼
<model>/Output/<model>_results.mat
            │
            ▼
SciPy parser → oo_.irfs
            │
            ▼
MacroReport
```

The adapter never executes arbitrary `.mod` text supplied by a UI or AI. Only
an Economy Lab-owned template is rendered. This is both a reproducibility and
security boundary.

## Coupling rule in v0.7

`coupling_mode = advisory-only`.

Dynare IRFs are returned beside the ABM/SFC simulation but cannot overwrite:

- realised GDP;
- realised inflation;
- employment/unemployment;
- bank balance sheets;
- deposits, loans or reserves.

This avoids two engines owning the same variable.

A helper already converts quarterly IRFs into a deliberately simple monthly
hold signal (each quarterly value is repeated for three months). That helper is
only a bridge contract; it is not claimed to be a statistically correct
frequency conversion.

## Next coupling milestone

The next safe step is a reconciliation layer with ownership rules such as:

```text
Dynare            ABM/SFC
------            -------
expected demand → firm planning
policy guidance → CentralBank rule
inflation signal → price expectations
                  │
                  ▼
            realised transactions
                  │
                  ▼
            realised aggregates
                  │
                  └────→ next macro state / calibration targets
```

No averaging of conflicting GDP or inflation numbers is allowed. Each shared
variable must have one owner and explicit translation rules.

## v0.8 hybrid mode

The previous `advisory-only` path is still available. When
`macro_coupling=hybrid`, Economy Lab uses the same fixed Dynare IRF as a
structural marginal guide, then passes bounded signals through
`HybridMacroCoupler`. Dynare still does not own realized GDP, prices,
employment or financial stocks. See `COUPLING.md`.


## v0.9 repeated solve

Hybrid mode can now re-run the same Economy Lab-owned Dynare template after
each completed ABM quarter. The new run is state-conditioned through bounded,
reported reference settings and replaces only future guidance. See
`MACRO_RECALIBRATION.md`.
