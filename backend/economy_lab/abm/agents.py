from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Household:
    id: int
    bank_id: int
    wage: float
    propensity_to_consume: float
    employed_by: int | None = None
    last_income: float = 0.0
    last_consumption: float = 0.0
    income_group: int = 0
    permanent_income_estimate: float = 0.0
    transitory_income_ratio: float = 0.0
    unemployment_probability: float = 0.05
    months_employed: int = 0
    months_unemployed: int = 0
    credit_defaults: int = 0
    months_credit_distressed: int = 0
    last_transfer_income: float = 0.0
    unemployment_spell_months: int = 0
    benefit_months_received: int = 0
    last_unemployment_benefit: float = 0.0
    labor_force_participating: bool = True
    reservation_wage: float = 0.0
    search_intensity: float = 1.0
    accepted_jobs: int = 0
    job_separations: int = 0

    @property
    def deposit_account(self) -> str:
        return f"household:{self.id}:deposit_asset"

    @property
    def bank_deposit_liability(self) -> str:
        return f"bank:{self.bank_id}:deposit_liability:household:{self.id}"

    @property
    def bank_equity_asset(self) -> str:
        return f"household:{self.id}:bank_equity_asset:bank:{self.bank_id}"

    @property
    def consumer_loan_liability(self) -> str:
        return f"household:{self.id}:consumer_loan_liability"

    @property
    def bank_consumer_loan_asset(self) -> str:
        return f"bank:{self.bank_id}:consumer_loan_asset:household:{self.id}"


@dataclass(slots=True)
class Firm:
    id: int
    bank_id: int
    price: float
    productivity: float
    wage_offer: float
    inventory: float = 0.0
    employees: set[int] = field(default_factory=set)
    last_units_sold: float = 0.0
    last_revenue: float = 0.0
    defaults: int = 0
    capital_stock: float = 0.0
    last_investment: float = 0.0
    last_depreciation: float = 0.0

    @property
    def deposit_account(self) -> str:
        return f"firm:{self.id}:deposit_asset"

    @property
    def bank_deposit_liability(self) -> str:
        return f"bank:{self.bank_id}:deposit_liability:firm:{self.id}"

    @property
    def loan_liability(self) -> str:
        return f"firm:{self.id}:loan_liability"

    @property
    def bank_loan_asset(self) -> str:
        return f"bank:{self.bank_id}:loan_asset:firm:{self.id}"


@dataclass(slots=True)
class Bank:
    id: int
    spread: float = 0.04
    resolutions: int = 0
    last_resolution_mode: str = "none"

    @property
    def reserve_asset(self) -> str:
        return f"bank:{self.id}:reserve_asset"

    @property
    def central_bank_borrowing_liability(self) -> str:
        return f"bank:{self.id}:central_bank_borrowing_liability"

    @property
    def equity_liability(self) -> str:
        return f"bank:{self.id}:equity_liability"

    def interbank_loan_asset(self, borrower_id: int) -> str:
        return f"bank:{self.id}:interbank_loan_asset:bank:{borrower_id}"

    def interbank_borrowing_liability(self, lender_id: int) -> str:
        return f"bank:{self.id}:interbank_borrowing_liability:bank:{lender_id}"


@dataclass(slots=True)
class Government:
    bank_id: int = 0

    @property
    def deposit_account(self) -> str:
        return "government:deposit_asset"

    @property
    def bank_deposit_liability(self) -> str:
        return f"bank:{self.bank_id}:deposit_liability:government"

    @property
    def debt_liability(self) -> str:
        return "government:debt_liability"


@dataclass(slots=True)
class CentralBank:
    policy_rate: float

    @property
    def government_bond_asset(self) -> str:
        return "central_bank:government_bond_asset"

    def reserve_liability(self, bank_id: int) -> str:
        return f"central_bank:reserve_liability:bank:{bank_id}"

    def advance_asset(self, bank_id: int) -> str:
        return f"central_bank:advance_asset:bank:{bank_id}"


@dataclass(slots=True)
class RestOfWorld:
    bank_id: int = 0

    @property
    def deposit_account(self) -> str:
        return "rest_of_world:deposit_asset"

    @property
    def bank_deposit_liability(self) -> str:
        return f"bank:{self.bank_id}:deposit_liability:rest_of_world"
