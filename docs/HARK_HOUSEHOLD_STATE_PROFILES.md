# HARK Household State Profiles — v1.9

## Goal

Move the HARK integration from a generic normalized consumption function to a household decision engine that receives the state of the simulated economy.

## Authority boundary

HARK may decide **desired consumption**. It may not post transactions or overwrite accounting stocks.

```text
Economy Zero employment + wages + deposits
                 ↓
          Household state bridge
                 ↓
      permanent / transitory income
      unemployment-risk signal
      income group + preferences
                 ↓
          HARK IndShockConsumerType
                 ↓
         desired consumption budget
                 ↓
         Economy Lab goods market
                 ↓
              SFC ledger
```

## Household state

Each household carries:

- current employment status;
- current realized gross wage income;
- permanent-income estimate;
- transitory-income ratio;
- income group;
- bounded unemployment probability;
- months employed/unemployed;
- last realized consumption.

Permanent income uses an explicit exponential-memory bridge. In an unemployed month it adapts slowly toward the configured unemployment replacement-income anchor instead of collapsing immediately to zero.

## Income groups

Households are ranked by their generated wage and divided into `hark_income_groups` strata. The Profile can define `hark_income_risk_dispersion`; this creates a symmetric multiplier around the baseline unemployment probability.

This is a modeling assumption for experimentation, **not an empirical claim**. A future calibration milestone must replace these defaults with microdata-estimated transition risks.

## Aggregate labor-market feedback

The current aggregate unemployment rate is used as a bounded stress modifier on the Profile's baseline unemployment probability. The model does **not** set HARK `UnempPrb` equal to the unemployment rate, because one is a transition probability and the other is a stock share.

## Profile parameters

A HARK Household Profile can now carry:

- `hark_crra`;
- `hark_annual_discount_factor`;
- `hark_unemployment_probability`;
- `hark_unemployment_replacement_rate`;
- `hark_permanent_shock_std`;
- `hark_transitory_shock_std`;
- `hark_permanent_income_memory`;
- `hark_income_groups`;
- `hark_income_risk_dispersion`;
- `hark_state_mode=employment_income`.

## Diagnostics

When HARK is active, `SimulationResult.household_engine` reports the final state in aggregate and by income group:

- employment rate;
- average wage;
- average permanent income;
- average transitory/permanent income ratio;
- average unemployment probability;
- average realized consumption;
- average deposits.

## Known limitations

- Income-process parameters are not calibrated to household microdata.
- The current HARK bridge uses `IndShockConsumerType`; labor supply itself remains determined by Economy Zero/Mesa rather than optimized jointly by HARK.
- Unemployment benefits are represented inside the HARK income process for decision-making, but Economy Zero does not yet post a dedicated government unemployment-benefit transfer to the ledger.
- HARK real-runtime validation is still pending on a machine with the optional dependency installed.
