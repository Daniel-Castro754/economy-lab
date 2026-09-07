# Accounting rules in Economy Zero — v0.6

## Core convention

Assets are positive positions and liabilities are negative positions. Every transaction must sum to zero and the whole ledger must net to zero.

After each simulated month Economy Lab verifies:

1. every stored transaction balances;
2. the global ledger sums to zero;
3. each sector balance sheet closes;
4. every stock-matrix instrument row sums to zero across sectors;
5. every current-month flow-matrix instrument row sums to zero across sectors.

## Sectors

- households;
- firms;
- commercial banks;
- government;
- central bank.

## Financial instruments

- deposits;
- corporate bank loans;
- commercial-bank reserves;
- government bonds / government debt;
- central-bank advances;
- bank equity;
- interbank loans/borrowing.

## Bank equity

At initialization, households convert a fraction of deposits into explicit bank-equity assets. The bank's deposit liability falls and its equity liability rises by the same amount. Household total financial wealth is unchanged by the conversion.

Regulatory capital is not a synthetic balancing posting. It is calculated from the bank balance sheet as assets minus non-equity liabilities, which lets profits and losses alter capital naturally.

## Cross-bank settlement

A cross-bank payment moves both deposits and reserves. If reserves are insufficient, the ledger first tries the interbank market and then the central-bank backstop.

## Opening balance sheets

Because Economy Zero does not yet contain a stock of legacy loans, securities or physical bank assets, the opening commercial-bank asset side is deliberately reserve-heavy. Opening reserves back deposits plus paid-in equity and the central bank holds matching government bonds.

This is a technical initialization device, not an empirical reserve-regime claim. A later calibration milestone should replace it with realistic legacy asset portfolios.

## Godley-style stock example

```text
                    Households   Firms   Banks   Government   Central bank   Total
Deposits                +          +       -         +             0           0
Corporate loans         0          -       +         0             0           0
Reserves                0          0       +         0             -           0
Government bonds        0          0       0         -             +           0
CB advances             0          0       -         0             +           0
Bank equity             +          0       -         0             0           0
Interbank loans         0          0       0*        0             0           0
```

`*` Interbank assets and liabilities are both inside the consolidated banking-sector column, so they cancel at sector aggregation even though they matter bank by bank.

## Still missing

- physical capital and depreciation;
- inventory valuation as a non-financial asset;
- household borrowing;
- bank dividends and external recapitalization;
- bank resolution/deposit insurance;
- government-bond holdings outside the central bank;
- external/foreign sector;
- complete national current/capital accounts;
- securities prices and valuation changes.
