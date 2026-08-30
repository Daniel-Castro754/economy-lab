from __future__ import annotations

from dataclasses import dataclass
from math import isclose

from economy_lab.finance.ledger import Ledger, Posting

SECTORS = ("households", "firms", "banks", "government", "central_bank", "rest_of_world")


def account_sector(account: str) -> str:
    if account.startswith("household:"):
        return "households"
    if account.startswith("firm:"):
        return "firms"
    if account.startswith("bank:"):
        return "banks"
    if account.startswith("government:"):
        return "government"
    if account.startswith("central_bank:"):
        return "central_bank"
    if account.startswith("rest_of_world:"):
        return "rest_of_world"
    return "other"


def account_instrument(account: str) -> str:
    if "deposit_" in account or account.endswith(":deposit"):
        return "deposits"
    if "reserve_" in account:
        return "reserves"
    if "interbank_loan_asset" in account or "interbank_borrowing_liability" in account:
        return "interbank_loans"
    if "government_bond" in account or account == "government:debt_liability":
        return "government_bonds"
    if "advance_asset" in account or "central_bank_borrowing_liability" in account:
        return "central_bank_advances"
    if "bank_equity_asset" in account or "equity_liability" in account:
        return "bank_equity"
    if "consumer_loan" in account:
        return "household_loans"
    if "loan_" in account:
        return "loans"
    return "other"


@dataclass(frozen=True, slots=True)
class SectorBalanceSheet:
    sector: str
    assets: float
    liabilities: float
    net_financial_worth: float
    positions: dict[str, float]

    @property
    def closes(self) -> bool:
        return isclose(
            self.assets,
            self.liabilities + self.net_financial_worth,
            abs_tol=1e-6,
        )


@dataclass(frozen=True, slots=True)
class MatrixRow:
    instrument: str
    sectors: dict[str, float]

    @property
    def total(self) -> float:
        return sum(self.sectors.values())


@dataclass(frozen=True, slots=True)
class GodleyMatrix:
    kind: str
    tick: int
    rows: tuple[MatrixRow, ...]

    @property
    def balanced(self) -> bool:
        return all(isclose(row.total, 0.0, abs_tol=1e-6) for row in self.rows)

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "tick": self.tick,
            "balanced": self.balanced,
            "rows": [
                {
                    "instrument": row.instrument,
                    "sectors": dict(row.sectors),
                    "total": row.total,
                }
                for row in self.rows
            ],
        }


def _empty_sector_map() -> dict[str, float]:
    return {sector: 0.0 for sector in SECTORS}


def sector_balance_sheets(ledger: Ledger) -> tuple[SectorBalanceSheet, ...]:
    by_sector: dict[str, dict[str, float]] = {sector: {} for sector in SECTORS}
    for account, value in ledger.balances.items():
        sector = account_sector(account)
        if sector not in by_sector:
            continue
        instrument = account_instrument(account)
        by_sector[sector][instrument] = by_sector[sector].get(instrument, 0.0) + value

    reports: list[SectorBalanceSheet] = []
    for sector in SECTORS:
        positions = by_sector[sector]
        assets = sum(value for value in positions.values() if value > 0)
        liabilities = -sum(value for value in positions.values() if value < 0)
        reports.append(
            SectorBalanceSheet(
                sector=sector,
                assets=assets,
                liabilities=liabilities,
                net_financial_worth=assets - liabilities,
                positions=dict(sorted(positions.items())),
            )
        )
    return tuple(reports)


def stock_matrix(ledger: Ledger, *, tick: int) -> GodleyMatrix:
    matrix: dict[str, dict[str, float]] = {}
    for account, value in ledger.balances.items():
        sector = account_sector(account)
        if sector not in SECTORS:
            continue
        instrument = account_instrument(account)
        matrix.setdefault(instrument, _empty_sector_map())[sector] += value

    rows = tuple(
        MatrixRow(instrument=instrument, sectors=matrix[instrument])
        for instrument in sorted(matrix)
        if any(abs(value) > ledger.tolerance for value in matrix[instrument].values())
    )
    return GodleyMatrix(kind="stocks", tick=tick, rows=rows)


def flow_matrix(ledger: Ledger, *, tick: int) -> GodleyMatrix:
    matrix: dict[str, dict[str, float]] = {}
    for transaction in ledger.transactions_for_tick(tick):
        for posting in transaction.postings:
            _add_posting(matrix, posting)

    rows = tuple(
        MatrixRow(instrument=instrument, sectors=matrix[instrument])
        for instrument in sorted(matrix)
        if any(abs(value) > ledger.tolerance for value in matrix[instrument].values())
    )
    return GodleyMatrix(kind="flows", tick=tick, rows=rows)


def _add_posting(matrix: dict[str, dict[str, float]], posting: Posting) -> None:
    sector = account_sector(posting.account)
    if sector not in SECTORS:
        return
    instrument = account_instrument(posting.account)
    matrix.setdefault(instrument, _empty_sector_map())[sector] += posting.amount


def assert_sector_accounting(ledger: Ledger, *, tick: int) -> None:
    """Check global, sector-balance-sheet and Godley instrument invariants."""
    ledger.assert_balanced()
    reports = sector_balance_sheets(ledger)
    for report in reports:
        if not report.closes:
            raise AssertionError(f"Sector balance sheet does not close: {report.sector}")
    stocks = stock_matrix(ledger, tick=tick)
    if not stocks.balanced:
        bad = {row.instrument: row.total for row in stocks.rows if abs(row.total) > 1e-6}
        raise AssertionError(f"Godley stock rows do not close: {bad}")
    flows = flow_matrix(ledger, tick=tick)
    if not flows.balanced:
        bad = {row.instrument: row.total for row in flows.rows if abs(row.total) > 1e-6}
        raise AssertionError(f"Godley flow rows do not close: {bad}")
