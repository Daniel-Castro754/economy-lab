# Productive capital, household credit and bank resolution — v2.3

v2.3 expands Economy Zero beyond working-capital credit.

## Productive capital

Each firm owns a non-financial `capital_stock`. It depreciates monthly and enters production through a bounded capital-intensity factor. Firms invest by buying goods from other firms; the payment is a real deposit transfer through the ledger, seller inventory falls, and the buyer's physical capital stock rises. Physical capital is deliberately not inserted into the financial Godley matrix because it is a real asset, while the purchase financing remains fully auditable.

Key scenario parameters: `initial_capital_per_worker`, `capital_unit_cost`, `annual_capital_depreciation_rate`, `firm_investment_propensity`, `capital_output_elasticity`.

## Household credit

Household consumer credit uses a separate instrument from corporate credit. A bank loan creates both the household deposit and the matching household loan liability/bank loan asset. Interest can be paid or capitalized, principal amortizes, and sustained unemployment/liquidity stress can trigger a partial write-off.

Key parameters: `household_credit_enabled`, `household_credit_income_multiple`, `household_credit_liquidity_target_months`, `household_credit_spread`, `household_principal_repayment_rate`, `household_default_writeoff_ratio`.

## Bank resolution

A bank can be resolved when regulatory capital is negative or its capital ratio drops below `bank_resolution_trigger_ratio`.

- `government_recapitalization`: government/central-bank balance sheets inject reserves until the target capital buffer is restored.
- `bail_in`: eligible private deposits are written down first; any residual capital gap uses a public backstop.
- `none`: no automatic resolution.

A bail-in reduces depositor assets and the bank's matching deposit liabilities in the same transaction, so bank capital improves without inventing money. Public recapitalization creates bank reserves against central-bank reserve liabilities and matching government debt/central-bank bond assets.

These are transparent structural rules, not implementations of a specific country's legal resolution regime.
