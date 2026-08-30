from __future__ import annotations

from dataclasses import dataclass

from economy_lab.finance.ledger import Ledger


@dataclass(frozen=True, slots=True)
class BankFinancials:
    bank_id: int
    reserves: float
    deposits: float
    corporate_loans: float
    household_loans: float
    interbank_assets: float
    interbank_borrowing: float
    central_bank_borrowing: float
    paid_in_equity: float
    retained_earnings: float
    regulatory_capital: float
    risk_weighted_assets: float
    capital_ratio: float

    def lending_headroom(self, minimum_capital_ratio: float) -> float:
        if minimum_capital_ratio <= 0:
            return float("inf")
        if self.regulatory_capital <= 0:
            return 0.0
        maximum_rwa = self.regulatory_capital / minimum_capital_ratio
        return max(0.0, maximum_rwa - self.risk_weighted_assets)

    def compliant(self, minimum_capital_ratio: float) -> bool:
        if self.risk_weighted_assets <= 1e-9:
            return self.regulatory_capital >= -1e-9
        return self.capital_ratio + 1e-12 >= minimum_capital_ratio


def bank_financials(ledger: Ledger, bank_id: int) -> BankFinancials:
    reserves = max(0.0, ledger.balance(f"bank:{bank_id}:reserve_asset"))
    deposits = max(0.0, -ledger.sum_prefix(f"bank:{bank_id}:deposit_liability"))
    corporate_loans = max(0.0, ledger.sum_prefix(f"bank:{bank_id}:loan_asset:firm"))
    household_loans = max(0.0, ledger.sum_prefix(f"bank:{bank_id}:consumer_loan_asset"))
    interbank_assets = max(0.0, ledger.sum_prefix(f"bank:{bank_id}:interbank_loan_asset"))
    interbank_borrowing = max(
        0.0, -ledger.sum_prefix(f"bank:{bank_id}:interbank_borrowing_liability")
    )
    central_bank_borrowing = max(
        0.0, ledger.balance(f"bank:{bank_id}:central_bank_borrowing_liability") * -1.0
    )
    paid_in_equity = max(0.0, -ledger.balance(f"bank:{bank_id}:equity_liability"))

    # Capital is the residual claim after non-equity liabilities. Because the
    # explicit equity instrument is excluded from non-equity liabilities, this
    # measure equals paid-in capital + retained earnings/losses.
    assets = reserves + corporate_loans + household_loans + interbank_assets
    non_equity_liabilities = deposits + interbank_borrowing + central_bank_borrowing
    regulatory_capital = assets - non_equity_liabilities
    retained_earnings = regulatory_capital - paid_in_equity

    # MVP risk weights: corporate credit 100%, household credit 75%, interbank claims 20%, reserves 0%.
    risk_weighted_assets = corporate_loans + 0.75 * household_loans + 0.20 * interbank_assets
    if risk_weighted_assets <= 1e-9:
        capital_ratio = 1.0 if regulatory_capital >= -1e-9 else -1.0
    else:
        capital_ratio = regulatory_capital / risk_weighted_assets

    return BankFinancials(
        bank_id=bank_id,
        reserves=reserves,
        deposits=deposits,
        corporate_loans=corporate_loans,
        household_loans=household_loans,
        interbank_assets=interbank_assets,
        interbank_borrowing=interbank_borrowing,
        central_bank_borrowing=central_bank_borrowing,
        paid_in_equity=paid_in_equity,
        retained_earnings=retained_earnings,
        regulatory_capital=regulatory_capital,
        risk_weighted_assets=risk_weighted_assets,
        capital_ratio=capital_ratio,
    )


def aggregate_capital_ratio(financials: list[BankFinancials]) -> float:
    total_capital = sum(item.regulatory_capital for item in financials)
    total_rwa = sum(item.risk_weighted_assets for item in financials)
    if total_rwa <= 1e-9:
        return 1.0 if total_capital >= 0 else -1.0
    return total_capital / total_rwa
