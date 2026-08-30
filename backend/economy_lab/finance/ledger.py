from __future__ import annotations

from dataclasses import dataclass, field
from math import isclose
import re


class UnbalancedTransaction(ValueError):
    """Raised when postings do not conserve the accounting unit."""


@dataclass(frozen=True, slots=True)
class Posting:
    account: str
    amount: float


@dataclass(frozen=True, slots=True)
class Transaction:
    tick: int
    description: str
    postings: tuple[Posting, ...]

    @property
    def total(self) -> float:
        return sum(posting.amount for posting in self.postings)


_DEPOSIT_LIABILITY = re.compile(r"^bank:(\d+):deposit_liability(?::|$)")
_RESERVE_ASSET = re.compile(r"^bank:(\d+):reserve_asset$")
_INTERBANK_BORROWING = re.compile(
    r"^bank:(\d+):interbank_borrowing_liability:bank:(\d+)$"
)


def _bank_id_from_deposit_liability(account: str) -> int | None:
    match = _DEPOSIT_LIABILITY.match(account)
    return int(match.group(1)) if match else None


def bank_reserve_asset(bank_id: int) -> str:
    return f"bank:{bank_id}:reserve_asset"


def central_bank_reserve_liability(bank_id: int) -> str:
    return f"central_bank:reserve_liability:bank:{bank_id}"


def central_bank_advance_asset(bank_id: int) -> str:
    return f"central_bank:advance_asset:bank:{bank_id}"


def bank_central_bank_borrowing_liability(bank_id: int) -> str:
    return f"bank:{bank_id}:central_bank_borrowing_liability"


def bank_interbank_loan_asset(lender_id: int, borrower_id: int) -> str:
    return f"bank:{lender_id}:interbank_loan_asset:bank:{borrower_id}"


def bank_interbank_borrowing_liability(borrower_id: int, lender_id: int) -> str:
    return f"bank:{borrower_id}:interbank_borrowing_liability:bank:{lender_id}"


@dataclass(slots=True)
class Ledger:
    """Signed-position double-entry ledger used by Economy Zero.

    Assets are positive and liabilities are negative. Every transaction must
    sum to zero. v0.6 adds an interbank reserve market before the central bank
    backstop. Banks with reserves above their target can fund banks that need
    settlement liquidity; only the remaining shortfall becomes a central-bank
    advance.
    """

    balances: dict[str, float] = field(default_factory=dict)
    transactions: list[Transaction] = field(default_factory=list)
    tolerance: float = 1e-8

    def post(self, *, tick: int, description: str, postings: list[Posting]) -> None:
        total = sum(item.amount for item in postings)
        if not isclose(total, 0.0, abs_tol=self.tolerance):
            raise UnbalancedTransaction(
                f"Transaction '{description}' is unbalanced by {total:.12f}"
            )

        for posting in postings:
            self.balances[posting.account] = self.balances.get(posting.account, 0.0) + posting.amount
            if abs(self.balances[posting.account]) < self.tolerance:
                self.balances[posting.account] = 0.0

        self.transactions.append(
            Transaction(tick=tick, description=description, postings=tuple(postings))
        )

    def open_instrument_pair(
        self,
        *,
        tick: int,
        description: str,
        asset_account: str,
        liability_account: str,
        amount: float,
    ) -> None:
        if amount < 0:
            raise ValueError("Opening amount must be non-negative")
        if amount == 0:
            return
        self.post(
            tick=tick,
            description=description,
            postings=[Posting(asset_account, amount), Posting(liability_account, -amount)],
        )

    def bank_ids(self) -> list[int]:
        ids: set[int] = set()
        for account in self.balances:
            match = _RESERVE_ASSET.match(account)
            if match:
                ids.add(int(match.group(1)))
        return sorted(ids)

    def bank_deposits(self, bank_id: int) -> float:
        return max(0.0, -self.sum_prefix(f"bank:{bank_id}:deposit_liability"))

    def reserve_floor(self, bank_id: int, target_reserve_ratio: float) -> float:
        return max(0.0, target_reserve_ratio) * self.bank_deposits(bank_id)

    def create_interbank_loan(
        self,
        *,
        tick: int,
        lender_id: int,
        borrower_id: int,
        amount: float,
    ) -> float:
        if amount <= self.tolerance or lender_id == borrower_id:
            return 0.0
        self.post(
            tick=tick,
            description=f"Interbank reserve loan bank {lender_id} -> bank {borrower_id}",
            postings=[
                Posting(bank_reserve_asset(lender_id), -amount),
                Posting(central_bank_reserve_liability(lender_id), amount),
                Posting(bank_reserve_asset(borrower_id), amount),
                Posting(central_bank_reserve_liability(borrower_id), -amount),
                Posting(bank_interbank_loan_asset(lender_id, borrower_id), amount),
                Posting(bank_interbank_borrowing_liability(borrower_id, lender_id), -amount),
            ],
        )
        return amount

    def ensure_bank_reserves(
        self,
        *,
        tick: int,
        bank_id: int,
        required: float,
        target_reserve_ratio: float = 0.10,
        use_interbank: bool = True,
    ) -> tuple[float, float]:
        """Fund a reserve shortfall, using interbank liquidity before the CB.

        Returns (interbank_borrowed, central_bank_advance).
        """
        if required <= 0:
            return (0.0, 0.0)
        reserve_account = bank_reserve_asset(bank_id)
        available = max(0.0, self.balance(reserve_account))
        shortfall = max(0.0, required - available)
        if shortfall <= self.tolerance:
            return (0.0, 0.0)

        interbank_borrowed = 0.0
        if use_interbank:
            candidates: list[tuple[float, int]] = []
            for lender_id in self.bank_ids():
                if lender_id == bank_id:
                    continue
                reserves = max(0.0, self.balance(bank_reserve_asset(lender_id)))
                excess = max(0.0, reserves - self.reserve_floor(lender_id, target_reserve_ratio))
                if excess > self.tolerance:
                    candidates.append((excess, lender_id))
            # Deepest-liquidity banks lend first, keeping the rule deterministic.
            candidates.sort(reverse=True)
            for excess, lender_id in candidates:
                if shortfall <= self.tolerance:
                    break
                amount = min(shortfall, excess)
                interbank_borrowed += self.create_interbank_loan(
                    tick=tick,
                    lender_id=lender_id,
                    borrower_id=bank_id,
                    amount=amount,
                )
                shortfall -= amount

        central_bank_advance = 0.0
        if shortfall > self.tolerance:
            self.post(
                tick=tick,
                description=f"Central bank reserve advance to bank {bank_id}",
                postings=[
                    Posting(reserve_account, shortfall),
                    Posting(central_bank_reserve_liability(bank_id), -shortfall),
                    Posting(central_bank_advance_asset(bank_id), shortfall),
                    Posting(bank_central_bank_borrowing_liability(bank_id), -shortfall),
                ],
            )
            central_bank_advance = shortfall
        return (interbank_borrowed, central_bank_advance)

    def transfer_deposit(
        self,
        *,
        tick: int,
        description: str,
        source_asset: str,
        source_bank_liability: str,
        destination_asset: str,
        destination_bank_liability: str,
        amount: float,
        settle_reserves: bool = True,
        target_reserve_ratio: float = 0.10,
    ) -> float:
        if amount <= 0:
            return 0.0
        available = max(0.0, self.balance(source_asset))
        paid = min(amount, available)
        if paid <= self.tolerance:
            return 0.0

        source_bank = _bank_id_from_deposit_liability(source_bank_liability)
        destination_bank = _bank_id_from_deposit_liability(destination_bank_liability)
        reserve_postings: list[Posting] = []

        if (
            settle_reserves
            and source_bank is not None
            and destination_bank is not None
            and source_bank != destination_bank
        ):
            deposits_after = max(0.0, self.bank_deposits(source_bank) - paid)
            desired_after = target_reserve_ratio * deposits_after
            self.ensure_bank_reserves(
                tick=tick,
                bank_id=source_bank,
                required=paid + desired_after,
                target_reserve_ratio=target_reserve_ratio,
                use_interbank=True,
            )
            reserve_postings = [
                Posting(bank_reserve_asset(source_bank), -paid),
                Posting(central_bank_reserve_liability(source_bank), paid),
                Posting(bank_reserve_asset(destination_bank), paid),
                Posting(central_bank_reserve_liability(destination_bank), -paid),
            ]

        self.post(
            tick=tick,
            description=description,
            postings=[
                Posting(source_asset, -paid),
                Posting(source_bank_liability, paid),
                Posting(destination_asset, paid),
                Posting(destination_bank_liability, -paid),
                *reserve_postings,
            ],
        )
        return paid

    def create_bank_loan(
        self,
        *,
        tick: int,
        description: str,
        bank_loan_asset: str,
        borrower_loan_liability: str,
        borrower_deposit_asset: str,
        bank_deposit_liability: str,
        amount: float,
    ) -> float:
        if amount <= 0:
            return 0.0
        self.post(
            tick=tick,
            description=description,
            postings=[
                Posting(bank_loan_asset, amount),
                Posting(borrower_loan_liability, -amount),
                Posting(borrower_deposit_asset, amount),
                Posting(bank_deposit_liability, -amount),
            ],
        )
        return amount

    def capitalize_interest(
        self,
        *,
        tick: int,
        description: str,
        bank_loan_asset: str,
        borrower_loan_liability: str,
        amount: float,
    ) -> float:
        if amount <= 0:
            return 0.0
        self.post(
            tick=tick,
            description=description,
            postings=[Posting(bank_loan_asset, amount), Posting(borrower_loan_liability, -amount)],
        )
        return amount

    def write_off_loan(
        self,
        *,
        tick: int,
        description: str,
        bank_loan_asset: str,
        borrower_loan_liability: str,
        amount: float,
    ) -> float:
        if amount <= 0:
            return 0.0
        self.post(
            tick=tick,
            description=description,
            postings=[Posting(bank_loan_asset, -amount), Posting(borrower_loan_liability, amount)],
        )
        return amount

    def _reserve_transfer(self, *, tick: int, payer: int, receiver: int, amount: float, description: str) -> float:
        if amount <= self.tolerance:
            return 0.0
        available = max(0.0, self.balance(bank_reserve_asset(payer)))
        paid = min(amount, available)
        if paid <= self.tolerance:
            return 0.0
        self.post(
            tick=tick,
            description=description,
            postings=[
                Posting(bank_reserve_asset(payer), -paid),
                Posting(central_bank_reserve_liability(payer), paid),
                Posting(bank_reserve_asset(receiver), paid),
                Posting(central_bank_reserve_liability(receiver), -paid),
            ],
        )
        return paid

    def service_interbank_positions(
        self,
        *,
        tick: int,
        borrower_id: int,
        annual_rate: float,
        target_reserve_ratio: float,
    ) -> tuple[float, float]:
        """Pay interbank interest and principal from reserves above the target floor."""
        interest_paid = 0.0
        principal_repaid = 0.0
        accounts = sorted(self.balances)
        for account in accounts:
            match = _INTERBANK_BORROWING.match(account)
            if not match or int(match.group(1)) != borrower_id:
                continue
            lender_id = int(match.group(2))
            outstanding = max(0.0, -self.balance(account))
            if outstanding <= self.tolerance:
                continue

            floor = self.reserve_floor(borrower_id, target_reserve_ratio)
            free = max(0.0, self.balance(bank_reserve_asset(borrower_id)) - floor)
            interest_due = outstanding * max(0.0, annual_rate) / 12.0
            paid_interest = self._reserve_transfer(
                tick=tick,
                payer=borrower_id,
                receiver=lender_id,
                amount=min(free, interest_due),
                description=f"Interbank interest bank {borrower_id} -> bank {lender_id}",
            )
            interest_paid += paid_interest
            unpaid_interest = max(0.0, interest_due - paid_interest)
            if unpaid_interest > self.tolerance:
                self.post(
                    tick=tick,
                    description=f"Capitalized interbank interest bank {borrower_id}",
                    postings=[
                        Posting(bank_interbank_loan_asset(lender_id, borrower_id), unpaid_interest),
                        Posting(account, -unpaid_interest),
                    ],
                )
                outstanding += unpaid_interest

            floor = self.reserve_floor(borrower_id, target_reserve_ratio)
            free = max(0.0, self.balance(bank_reserve_asset(borrower_id)) - floor)
            principal = min(outstanding, free)
            if principal <= self.tolerance:
                continue
            self.post(
                tick=tick,
                description=f"Interbank principal repayment bank {borrower_id} -> bank {lender_id}",
                postings=[
                    Posting(bank_reserve_asset(borrower_id), -principal),
                    Posting(central_bank_reserve_liability(borrower_id), principal),
                    Posting(bank_reserve_asset(lender_id), principal),
                    Posting(central_bank_reserve_liability(lender_id), -principal),
                    Posting(account, principal),
                    Posting(bank_interbank_loan_asset(lender_id, borrower_id), -principal),
                ],
            )
            principal_repaid += principal
        return (interest_paid, principal_repaid)

    def service_central_bank_advance(
        self,
        *,
        tick: int,
        bank_id: int,
        annual_rate: float,
        target_reserve_ratio: float,
    ) -> tuple[float, float]:
        """Pay penalty interest and principal on a central-bank advance."""
        borrowing = bank_central_bank_borrowing_liability(bank_id)
        outstanding = max(0.0, -self.balance(borrowing))
        if outstanding <= self.tolerance:
            return (0.0, 0.0)

        floor = self.reserve_floor(bank_id, target_reserve_ratio)
        free = max(0.0, self.balance(bank_reserve_asset(bank_id)) - floor)
        interest_due = outstanding * max(0.0, annual_rate) / 12.0
        paid_interest = min(free, interest_due)
        if paid_interest > self.tolerance:
            self.post(
                tick=tick,
                description=f"Central bank advance interest bank {bank_id}",
                postings=[
                    Posting(bank_reserve_asset(bank_id), -paid_interest),
                    Posting(central_bank_reserve_liability(bank_id), paid_interest),
                ],
            )
        unpaid_interest = max(0.0, interest_due - paid_interest)
        if unpaid_interest > self.tolerance:
            self.post(
                tick=tick,
                description=f"Capitalized central bank advance interest bank {bank_id}",
                postings=[
                    Posting(central_bank_advance_asset(bank_id), unpaid_interest),
                    Posting(borrowing, -unpaid_interest),
                ],
            )
            outstanding += unpaid_interest

        floor = self.reserve_floor(bank_id, target_reserve_ratio)
        free = max(0.0, self.balance(bank_reserve_asset(bank_id)) - floor)
        principal = min(outstanding, free)
        if principal > self.tolerance:
            self.post(
                tick=tick,
                description=f"Central bank advance principal repayment bank {bank_id}",
                postings=[
                    Posting(bank_reserve_asset(bank_id), -principal),
                    Posting(central_bank_reserve_liability(bank_id), principal),
                    Posting(central_bank_advance_asset(bank_id), -principal),
                    Posting(borrowing, principal),
                ],
            )
        return (paid_interest, principal)

    def balance(self, account: str) -> float:
        return self.balances.get(account, 0.0)

    def sum_prefix(self, prefix: str) -> float:
        return sum(value for account, value in self.balances.items() if account.startswith(prefix))

    def transactions_for_tick(self, tick: int) -> list[Transaction]:
        return [transaction for transaction in self.transactions if transaction.tick == tick]

    def assert_balanced(self) -> None:
        for transaction in self.transactions:
            if not isclose(transaction.total, 0.0, abs_tol=self.tolerance):
                raise AssertionError(
                    f"Stored transaction '{transaction.description}' is unbalanced: {transaction.total}"
                )
        if not isclose(sum(self.balances.values()), 0.0, abs_tol=1e-6):
            raise AssertionError(
                f"Global ledger does not net to zero: {sum(self.balances.values())}"
            )
