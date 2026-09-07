# Economy Lab architecture — v0.9

## Principle

The project is local-first and domain-first. Economic balances and identities do not live inside React, Mesa, HARK, Minsky or Dynare. The Economy Lab domain model and accounting kernel remain the source of truth.

```text
React / TypeScript
      |
 Web  |  Tauri desktop
      v
 FastAPI / local API
      |
      v
 ScenarioSpec validator
      |
      v
 Economy Zero domain
      |
      +-------------------+---------------------+----------------------+
      |                   |                     |                      |
 activation           household decision     accounting             external
      |                   |                     |                      |
 native / Mesa        heuristic / HARK     SFC + Godley         Minsky adapter
      |                   |                     |                      |
      +-------------------+---------------------+----------------------+
                          |
                          v
                   realized markets
                          |
                          v
                    state + metrics
```

Dynare remains a later macro adapter. External engines may propose calculations, dynamics or targets, but realized balance-sheet changes must pass through validated Economy Lab operations.

## Mesa integration

Mesa 3.5.x is an optional activation layer. Economy Lab creates Mesa proxy agents for firms and households; proxies hold only domain IDs, never separate economic balances.

Current Mesa-controlled stages:

1. firm production (`shuffle_do`);
2. household goods-market activation (`shuffle_do`);
3. firm price adjustment (`shuffle_do`).

System-wide operations such as payroll, government procurement, credit servicing and labor matching remain explicit domain stages.

## HARK integration

HARK is a decision engine. The current adapter solves `IndShockConsumerType` policy functions for patience cohorts and asks HARK for desired household consumption conditional on normalized liquid resources.

HARK **does not** transfer deposits or modify the ledger. Economy Lab maps the desired budget into the goods market, and only realized purchases become financial transactions.

## SFC / monetary architecture

v0.6 upgrades the ledger into an explicit sector/instrument reporting system.

```text
Depositor A (Bank 0)
      |
      | payment
      v
Depositor B (Bank 1)

Bank 0 deposit liability decreases
Bank 1 deposit liability increases
            +
Bank 0 reserves decrease
Bank 1 reserves increase
            +
Central-bank reserve liabilities mirror the settlement
```

If Bank 0 lacks reserves, the liquidity waterfall is now: interbank borrowing from reserve-surplus banks first, then a central-bank advance for any remaining shortfall.

The banking layer also derives regulatory capital from bank assets minus non-equity liabilities. Corporate credit creation is limited by a configurable capital ratio; defaults reduce bank capital through loan-asset write-offs.

The reporting layer derives:

- balance sheets by sector;
- stock matrix by instrument/sector;
- current-month flow matrix by instrument/sector;
- private net financial wealth;
- commercial-bank reserves;
- central-bank advances;
- government debt.

Every Godley row must sum to zero.

## Minsky integration boundary

The Minsky bridge exports the Economy Lab stock/flow matrices into a deterministic JSON contract and provides a generic REST client. v0.6 deliberately does **not** hard-code Minsky Godley object paths yet.

```text
Economy Lab ledger
      |
      v
Godley export contract
      |
      v
Minsky adapter / REST
      |
      v
Minsky calculations or visualization
      |
      v
validated/reconciled result
```

This boundary prevents Minsky-specific schema details from contaminating the domain model.

## Economy Zero monthly order

1. Service existing corporate credit.
2. Adjust employment using previous sales/inventory.
3. Produce goods.
4. Pay wages and income taxes; cross-bank payments settle reserves.
5. Reset monthly sales counters.
6. Government procurement.
7. Household consumption; cross-bank payments settle reserves.
8. Corporate principal repayment.
9. Partial default/restructuring check.
10. Interbank and central-bank liquidity servicing.
11. Bank capital/P&L measurement.
12. Price adjustment.
13. Ledger + sector + Godley stock/flow invariant checks.
14. Aggregate indicators, bank-level metrics and balance-sheet reports.

The order remains explicit because changing it changes causal interpretation.


## Macro bridge — v0.7

Dynare/Octave is an optional secondary macro engine. The adapter renders an
Economy Lab-owned `.mod` template, executes it in a local subprocess and parses
`oo_.irfs` from Dynare's results file. It is intentionally `advisory-only` in
v0.7: the ABM/SFC kernel owns realised transactions and aggregates, while
Dynare supplies a separate expectation/impulse-response view until explicit
variable-ownership rules are implemented. See `DYNARE_BRIDGE.md`.

## Hybrid coupling — v0.8

v0.8 introduces `HybridMacroCoupler` between Dynare and Economy Zero. The
coupler translates a quarterly IRF into bounded monthly signals before an ABM
step, observes realized ABM/SFC metrics after the step, and computes bounded
feedback for the following month. It never writes ledger balances. See
`COUPLING.md` for authority and feedback rules.


## Quarterly macro loop — v0.9

After every three realized ABM months, `macro_cycle.py` can extract a bounded
state vector, derive reference settings, re-run Dynare and ask the coupler to
replace guidance starting in the next month. Ledger state is never rolled back.
