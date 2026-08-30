# Banking model — v0.6

## Capital

Economy Lab distinguishes the explicit paid-in equity instrument from regulatory capital.

```text
regulatory capital = bank assets - non-equity liabilities
```

Current bank assets used in the calculation:

- reserves at the central bank;
- corporate loan assets;
- interbank loan assets.

Current non-equity liabilities:

- customer deposits;
- interbank borrowing;
- central-bank borrowing.

Paid-in equity is an explicit bank liability matched by household bank-equity assets. Retained earnings are currently the residual difference between regulatory capital and paid-in equity.

## Risk-weighted assets

The v0.6 MVP uses deliberately simple weights:

```text
corporate loans  = 100%
interbank assets = 20%
reserves         = 0%
```

These are model parameters/conventions, not a claim that the implementation reproduces Basel rules.

## Credit supply

A bank can create a new corporate loan only while the post-loan capital position can satisfy the configured minimum capital ratio.

```text
maximum RWA = regulatory capital / minimum capital ratio
lending headroom = maximum RWA - current RWA
```

The actual loan is also constrained by the firm's own toy-model credit cap. Credit blocked specifically by the bank-capital constraint is reported as `credit_rationed`.

## Defaults

A corporate write-off reduces the bank loan asset and the firm's loan liability by the same amount. The bank therefore loses regulatory capital while the borrower receives debt relief.

No automatic bank resolution or recapitalization exists yet. A bank can therefore become undercapitalized or economically insolvent in stress scenarios.

## Interbank liquidity

When a cross-bank customer payment requires more settlement reserves than the paying bank has available, Economy Lab uses this order:

1. borrow reserves from banks with reserves above their target floor;
2. if a shortfall remains, borrow from the central bank.

Interbank borrowing creates:

```text
lender bank:   + interbank loan asset
borrower bank: - interbank borrowing liability
```

and transfers reserves between the two banks.

At month-end, a borrower uses reserves above its target floor to service interbank interest and principal.

## Central-bank advances

The remaining reserve shortfall becomes a central-bank advance. v0.6 adds:

- penalty interest = policy rate + configurable spread;
- capitalization of unpaid interest;
- principal repayment from reserves above the target floor.

Collateral, haircuts, maturity structure and bank resolution are not implemented yet.

## Opening-liquidity convention

v0.6 still initializes commercial banks with deliberately abundant reserves. This is a technical initialization choice, not a banking-theory claim and not a representation of fractional-reserve banking. It keeps the first SFC balance sheets transparent while the bank module is being built.

As a consequence, ordinary baseline runs can show little or no interbank borrowing. Stress tests and dedicated unit tests deliberately create reserve shortages and verify the interbank-first / central-bank-second funding sequence. A future calibration step should seed realistic opening portfolios with reserves, government securities, loans, deposits and equity.
