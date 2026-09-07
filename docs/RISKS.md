# Main risks

## 1. Accounting consistency

Mitigation already started: every financial transaction is posted to a balanced ledger and checked each month.

## 2. False economic realism

Economy Zero is intentionally uncalibrated. A balanced ledger does not mean a correct economic model. UI and API warnings must remain until empirical calibration/validation exists.

## 3. Double ownership of variables

Mesa, HARK, Minsky and Dynare cannot independently overwrite the same aggregate. The future adapter protocol must define which engine owns each variable and which outputs are advisory/target values.

## 4. Time-scale mismatch

ABM can be event-level, financial flows can be daily, macro models often quarterly. v0.3 still fixes one simulation tick to one month. Multi-frequency scheduling comes later.

## 5. Feedback instability

Naive rules can create explosive credit, deflation or employment cycles. Hard caps are only temporary safety rails. Calibration and sensitivity analysis must replace arbitrary coefficients.

## 6. AI hallucination

The AI layer must emit validated `ScenarioSpec`/`ModelSpec` objects. It must never mutate balances or engine internals directly.

## 7. Performance

The current 5,000-household economy is Python-level and optimized for clarity. Scaling to hundreds of thousands or millions of agents may require vectorization, parallel runs, Rust/C++ kernels or representative-agent cohorts.


## 8. HARK state mismatch

The first HARK bridge normalizes current deposits with an income anchor, but HARK's internal permanent/transitory income process is not yet the same process that generated Economy Zero wages and unemployment. Treat HARK runs as integration experiments until those states are synchronized and calibrated.

## 9. Optional-engine reproducibility

Mesa uses its own seeded activation RNG while Economy Zero has a domain RNG. Runs are deterministic by seed inside a fixed engine configuration, but switching native ↔ Mesa changes activation ordering and therefore is a model change, not a numerically identical backend swap.

## v0.6 accounting/banking risks

### Opening reserve regime is deliberately unrealistic

Commercial banks currently start with reserves equal to opening deposits. This makes the first complete sector balance sheets easy to audit, but it is not an empirical claim about banking systems. Before calibration, replace this with realistic legacy assets, reserve balances, equity and central-bank operating rules.

### Central-bank advances do not yet have a repayment policy

A reserve shortfall first uses the interbank market and then an explicit central-bank advance. v0.6 adds a penalty spread and automatic servicing from excess reserves, but collateral, haircuts, maturity structure and resolution rules are still absent.

The capital requirement is intentionally simplified. Risk weights are model conventions, not an implementation of Basel standards. A bank can become undercapitalized or insolvent because automatic recapitalization/resolution is not yet modeled.

### Net worth is financial, not total wealth

Sector net financial worth currently omits physical capital, inventories as valued non-financial assets, land and equity ownership. Do not interpret it as household or national wealth.

### Godley-compatible does not mean Minsky-equivalent

Economy Lab now exports balanced stock/flow matrices, but a live Minsky model has its own object model, equations and dynamic semantics. Automatic round-trip integration must be validated rather than assumed.

## Dual authority between macro and micro engines

Dynare and the ABM can both produce quantities that look like GDP, inflation or
interest rates. Treating both as simultaneous truths would make the model
internally inconsistent. v0.7 therefore keeps Dynare `advisory-only`; future
coupling must define one owner for every shared state variable and a documented
translation rule before any feedback is enabled.

## Hybrid-coupling identification risk — v0.8

A bridge can be internally consistent and still be empirically wrong. The v0.8
feedback weights and ABM pass-through coefficients are deliberately exposed and
bounded, but they are not estimated from data. The output-gap field used for
feedback is an EWMA cyclical proxy, not potential output. Do not interpret the
hybrid result as a causal forecast until the coupling parameters and macro state
mapping are calibrated and validated out of sample.


## State-conditioned DSGE parameter risk — v0.9

The quarterly controller changes a few reference coefficients with bounded rules.
This proves orchestration but can create apparent precision without identification.
Every change is therefore exposed in the API, hard-bounded, and documented as
experimental. Production/economic inference requires formal calibration or
estimation rather than these controller rules.
