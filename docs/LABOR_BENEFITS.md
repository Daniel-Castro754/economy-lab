# Labor, unemployment benefits and HARK bridge — v2.4

v2.4 separates four concepts that earlier Economy Zero versions partially conflated:

1. **employment state** — whether a household currently has an employer;
2. **labor-force participation/search** — whether an unemployed household is actively searching;
3. **job-transition flows** — separations and job finding during the current month;
4. **unemployment benefits** — an explicit government-to-household transfer settled through the SFC ledger.

## Benefits are transfers, not G

An eligible unemployed household receives a deposit transfer from the government. If the government deposit is insufficient, the existing explicit deficit-financing mechanism creates the matching government debt/central-bank positions first. The transfer itself is not counted as government final demand. It can affect GDP indirectly if the household later spends the deposit.

Eligibility is controlled by:

- `unemployment_benefits_enabled`;
- `unemployment_benefit_replacement_rate`;
- `unemployment_benefit_waiting_months`;
- `unemployment_benefit_max_months`;
- `unemployment_benefit_cap`.

## Initial labor-supply bridge

`labor_supply_mode=inelastic` preserves the simple benchmark in which every unemployed household searches.

`labor_supply_mode=reservation_wage` introduces a transparent first labor-supply layer. Liquid wealth and the previous unemployment benefit can reduce search intensity and raise the reservation wage. A vacancy is accepted only if the firm's wage offer meets that reservation wage. These rules are behavioral assumptions for experimentation, not estimated labor-supply elasticities.

## HARK risk bridge

HARK's `UnempPrb` is a transition probability, while the unemployment rate is a stock. v2.4 therefore anchors household unemployment risk primarily on the model's observed monthly job-separation flow, with the unemployment stock retained only as a bounded secondary stress signal. This is closer to the semantics of HARK's `IndShockConsumerType`, while remaining a simplified bridge until transition probabilities are calibrated from labor microdata.

Realized unemployment benefits enter the household's current transitory resources. The HARK decision engine can use those resources to recommend consumption, but it cannot post accounting entries; all realized payments remain under the Economy Lab ledger.

## Output diagnostics

The monthly series now includes:

- unemployment benefits paid;
- labor-force participation;
- job-separation rate;
- job-finding rate.

The Excel export includes a `Mercado de trabalho` sheet and the HARK group report adds current benefit, participation, search intensity and reservation wage diagnostics.

## Limitations

- the labor-supply rule is not yet a solved labor/leisure utility problem;
- benefit eligibility does not yet reproduce a specific country's legal rules;
- unemployment insurance contributions are not modeled as a separate payroll instrument;
- job search is not sector/skill specific;
- transition parameters still require empirical calibration.
