# Simple Macro — level 1 simulator (v2.5)

Simple Macro is an additional, deliberately small simulation level. It does **not** replace Economy Zero or Hybrid mode.

## Product levels

1. **Simple Macro** — aggregate annual model, 7 turns, four policy levers.
2. **Economy Zero** — monthly households/firms/banks/government/central-bank/external-sector model with SFC accounting.
3. **Hybrid** — Economy Zero combined with optional Mesa, HARK, Minsky and Dynare modules/Profiles.

Simple Macro is inspired by the educational interaction pattern of policy simulators such as Econland, but uses Economy Lab's own transparent equations and scoring. No proprietary Econland equations, score functions or UI assets are copied.

## Annual inputs

The user controls four variables:

- policy interest rate;
- personal income-tax rate;
- corporate tax rate;
- primary government spending as a percentage of GDP.

Each year also has two exogenous inputs:

- world real-GDP growth;
- consumer confidence (0–100).

Three deterministic seven-year environments ship with v2.5: stable baseline, global recession and volatile world economy.

## Transparent behavioral block

The GDP identity is not used as a behavioral equation by itself. Annual real growth starts from potential growth and receives bounded impulses from confidence, world growth, the interest-rate gap, both tax gaps, government spending and the inherited output gap.

Potential GDP grows independently at the configured potential rate. The output gap is therefore explicit:

`output_gap = 100 * (real_gdp / potential_gdp - 1)`

Inflation uses a simple backward-looking Phillips mechanism anchored on the configured inflation target and the output gap. Deflation is allowed and is not clipped to zero.

Unemployment uses an Okun-style dynamic with persistence around a natural unemployment rate and reacts to the gap between actual and potential growth.

## Fiscal block

Tax revenue uses transparent labor-income, profit and indirect-tax base shares plus a bounded cyclical term. Primary spending is the user's government-spending decision. Interest service depends on the inherited debt ratio and a simple effective debt yield.

Debt/GDP evolves with the familiar debt-dynamics structure: inherited debt is rolled forward by the effective interest rate relative to nominal GDP growth, then the primary deficit is added. This is intentionally more defensible than the heuristic statement that GDP growth merely needs to exceed the deficit.

## Approval score

Approval is an Economy Lab function, not an attempt to reproduce another simulator's proprietary score. The current-year welfare score allocates up to 25 points each to:

- real GDP growth;
- unemployment;
- price stability;
- fiscal sustainability.

The functions are nonlinear/triangular around desirable ranges. Deflation is penalized heavily. Fiscal score also reacts to high/rising debt. Political approval is smoothed between the previous approval and current score so one year does not erase all history.

## Promotion to detailed mode

A completed or partial Simple state can be converted into an Economy Zero `ScenarioSpec`. The bridge currently maps inflation, unemployment, policy rate, income tax, government-spending deviation and desired horizon.

The bridge explicitly reports what it cannot map yet: corporate tax has no direct Economy Zero field, while Simple debt/GDP and potential GDP cannot be copied into Economy Zero's detailed balance-sheet/state structure without a separate initialization contract.

## Scope freeze

The Simple v1 feature is considered functionally complete when the seven-year loop, four decisions, external scenarios, macro indicators, approval, history, exports and promotion bridge are operational. New micro detail belongs in Economy Zero/Hybrid instead of being added to Simple.
