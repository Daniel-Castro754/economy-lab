"""Frozen canonical inter-engine state contract (v2.8).

`EconomyState` is intentionally small. Engines exchange only canonical realized
state through this contract; engine-specific details stay in their own reports.
The authority registry defines which source may populate each field.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


CANONICAL_STATE_SCHEMA = "economy-state-v1.0"


@dataclass(slots=True)
class MacroState:
    # Human-facing units: GDP is the Economy Zero index, rates are percentage points.
    gdp: float = 0.0
    inflation: float = 0.0
    unemployment: float = 0.0
    policy_rate: float = 0.0


@dataclass(slots=True)
class RealEconomyState:
    productive_capital: float = 0.0


@dataclass(slots=True)
class FinancialState:
    household_debt: float = 0.0
    corporate_debt: float = 0.0
    bank_credit: float = 0.0
    bank_deposits: float = 0.0
    bank_reserves: float = 0.0
    bank_capital: float = 0.0
    central_bank_advances: float = 0.0
    government_debt: float = 0.0
    private_net_financial_wealth: float = 0.0


@dataclass(slots=True)
class DecisionState:
    """Source labels only; values remain in the owning engine/report."""

    activation_source: str = "native_activation"
    household_policy_source: str = "native_heuristic"
    financial_control_source: str = "native_finance"
    macro_policy_source: str = "scenario_central_bank"


@dataclass(slots=True)
class EconomyState:
    """Canonical state shared across engine boundaries.

    This object contains realized state only plus source labels. Dynare IRFs,
    HARK policy functions and Minsky control trajectories are *not* stored as
    realized state; they remain guidance in their dedicated reports/contracts.
    """

    schema: str = CANONICAL_STATE_SCHEMA
    tick: int = 0
    macro: MacroState = field(default_factory=MacroState)
    real: RealEconomyState = field(default_factory=RealEconomyState)
    financial: FinancialState = field(default_factory=FinancialState)
    decisions: DecisionState = field(default_factory=DecisionState)

    @classmethod
    def from_runtime_metrics(
        cls,
        metrics: object,
        *,
        activation_source: str,
        household_policy_source: str,
        financial_control_source: str,
        macro_policy_source: str,
    ) -> "EconomyState":
        return cls(
            tick=int(getattr(metrics, "month")),
            macro=MacroState(
                gdp=float(getattr(metrics, "gdp_index")),
                inflation=float(getattr(metrics, "inflation")),
                unemployment=float(getattr(metrics, "unemployment")),
                policy_rate=float(getattr(metrics, "policy_rate")),
            ),
            real=RealEconomyState(
                productive_capital=float(getattr(metrics, "productive_capital", 0.0)),
            ),
            financial=FinancialState(
                household_debt=float(getattr(metrics, "household_debt", 0.0)),
                corporate_debt=float(getattr(metrics, "corporate_debt", 0.0)),
                bank_credit=float(getattr(metrics, "bank_credit", 0.0)),
                bank_deposits=float(getattr(metrics, "bank_deposits", 0.0)),
                bank_reserves=float(getattr(metrics, "bank_reserves", 0.0)),
                bank_capital=float(getattr(metrics, "bank_capital", 0.0)),
                central_bank_advances=float(getattr(metrics, "central_bank_advances", 0.0)),
                government_debt=float(getattr(metrics, "government_debt", 0.0)),
                private_net_financial_wealth=float(
                    getattr(metrics, "private_net_financial_wealth", 0.0)
                ),
            ),
            decisions=DecisionState(
                activation_source=activation_source,
                household_policy_source=household_policy_source,
                financial_control_source=financial_control_source,
                macro_policy_source=macro_policy_source,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
