"""Econ-ARK/HARK bridge for state-aware household consumption decisions.

HARK is intentionally a *decision engine*, not an accounting engine. It can
recommend a consumption budget, but every realized payment still goes through
Economy Lab's ledger and goods market. This keeps SFC identities authoritative.

v1.9 adds an explicit household-state bridge: employment, wage income,
permanent-income estimates, transitory income, unemployment risk and income
strata are synchronized from Economy Zero into HARK's IndShockConsumerType.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.util import find_spec
from math import isfinite
from typing import Protocol

from economy_lab.abm.agents import Household


HARK_TARGET_VERSION = "0.17.2"


class EngineUnavailableError(RuntimeError):
    """Raised when an explicitly requested optional simulation engine is absent."""


def hark_available() -> bool:
    return find_spec("HARK") is not None


@dataclass(frozen=True, slots=True)
class HouseholdIncomeState:
    household_id: int
    employed: bool
    income_group: int
    current_net_income: float
    permanent_income: float
    transitory_income_ratio: float
    unemployment_probability: float
    unemployment_replacement_rate: float
    months_employed: int
    months_unemployed: int


def income_group_risk_multiplier(*, group: int, groups: int, dispersion: float) -> float:
    """Return a symmetric risk multiplier around one across income strata.

    The multiplier is an explicit *modeling assumption*, not an empirical fact.
    With five groups and 0.35 dispersion, the bottom and top groups receive
    approximately 1.35x and 0.65x the baseline unemployment probability.
    """
    groups = max(1, int(groups))
    if groups == 1:
        return 1.0
    group = max(0, min(groups - 1, int(group)))
    dispersion = max(0.0, min(1.0, float(dispersion)))
    position = group / (groups - 1)  # 0 bottom, 1 top
    return max(0.20, 1.0 + dispersion * (1.0 - 2.0 * position))


def update_household_income_state(
    household: Household,
    *,
    income_tax_rate: float,
    aggregate_unemployment_rate: float,
    base_unemployment_probability: float,
    unemployment_replacement_rate: float,
    permanent_income_memory: float,
    income_groups: int,
    income_risk_dispersion: float,
    observed_job_separation_rate: float | None = None,
) -> HouseholdIncomeState:
    """Synchronize one Economy Zero household into a normalized HARK state.

    Permanent income is an exponentially smoothed after-tax income anchor.
    During unemployment it decays slowly instead of collapsing to zero. This is
    a transparent bridge until empirical income-process estimation is added.
    """
    tax = max(0.0, min(1.0, float(income_tax_rate)))
    memory = max(0.01, min(1.0, float(permanent_income_memory)))
    replacement = max(0.0, min(1.0, float(unemployment_replacement_rate)))
    employed = household.employed_by is not None
    labor_net = max(0.0, household.last_income * (1.0 - tax)) if employed else 0.0
    transfer_net = max(0.0, household.last_transfer_income)
    current_net = labor_net + transfer_net
    potential_net_wage = max(1.0, household.wage * (1.0 - tax))

    previous = household.permanent_income_estimate
    if previous <= 0:
        previous = potential_net_wage
    if employed:
        observed = max(1.0, current_net)
        permanent = (1.0 - memory) * previous + memory * observed
        household.months_employed += 1
    else:
        # Job loss is a transitory state in the initial bridge. Let the permanent
        # income anchor adapt, but much more slowly than in an employed month.
        unemployment_anchor = max(1.0, potential_net_wage * replacement)
        slow_memory = memory * 0.15
        permanent = (1.0 - slow_memory) * previous + slow_memory * unemployment_anchor
        household.months_unemployed += 1

    permanent = max(1.0, permanent)
    household.permanent_income_estimate = permanent
    household.transitory_income_ratio = current_net / permanent

    risk_multiplier = income_group_risk_multiplier(
        group=household.income_group,
        groups=income_groups,
        dispersion=income_risk_dispersion,
    )
    # Unemployment is a stock, while UnempPrb is a transition probability. v2.4
    # anchors the expectation primarily on the observed job-separation flow and
    # uses the unemployment stock only as a bounded secondary stress signal.
    prior = max(0.001, min(0.50, float(base_unemployment_probability)))
    observed_separation = prior if observed_job_separation_rate is None else max(0.0, min(0.50, float(observed_job_separation_rate)))
    transition_anchor = 0.35 * prior + 0.65 * observed_separation
    macro_stress = max(-0.30, min(0.75, (aggregate_unemployment_rate - 0.05) * 1.25))
    status_stress = 0.10 if not employed else 0.0
    unemployment_probability = transition_anchor * risk_multiplier * (
        1.0 + macro_stress + status_stress
    )
    unemployment_probability = max(0.001, min(0.50, unemployment_probability))
    household.unemployment_probability = unemployment_probability

    return HouseholdIncomeState(
        household_id=household.id,
        employed=employed,
        income_group=household.income_group,
        current_net_income=current_net,
        permanent_income=permanent,
        transitory_income_ratio=household.transitory_income_ratio,
        unemployment_probability=unemployment_probability,
        unemployment_replacement_rate=replacement,
        months_employed=household.months_employed,
        months_unemployed=household.months_unemployed,
    )


class ConsumptionPolicy(Protocol):
    name: str

    def budget(
        self,
        *,
        household: Household,
        deposit: float,
        income_tax_rate: float,
        annual_policy_rate: float,
        aggregate_unemployment_rate: float,
        observed_job_separation_rate: float,
    ) -> float: ...


@dataclass(slots=True)
class HeuristicConsumptionPolicy:
    """The transparent benchmark rule kept as the benchmark/control behavior."""

    name: str = "heuristic"

    def budget(
        self,
        *,
        household: Household,
        deposit: float,
        income_tax_rate: float,
        annual_policy_rate: float,
        aggregate_unemployment_rate: float,
        observed_job_separation_rate: float,
    ) -> float:
        del income_tax_rate, annual_policy_rate, aggregate_unemployment_rate, observed_job_separation_rate
        income_anchor = max(household.last_income + household.last_transfer_income, 0.08 * deposit)
        return max(
            0.0,
            min(deposit * 0.35, income_anchor * household.propensity_to_consume),
        )


@dataclass(slots=True)
class HarkConsumptionPolicy:
    """HARK-backed, state-aware normalized consumption policy.

    HARK receives a bounded income-process representation derived from the ABM:
    * actual current employment and wage income;
    * a household-specific permanent-income estimate;
    * the realized transitory-income ratio;
    * an unemployment-risk signal combining profile risk, income stratum and
      aggregate labor-market stress.

    HARK still returns only a desired consumption budget. It never posts ledger
    transactions and therefore cannot create/destroy money in Economy Lab.
    """

    crra: float = 2.0
    annual_discount_factor: float = 0.96
    unemployment_probability: float = 0.05
    unemployment_replacement_rate: float = 0.30
    permanent_shock_std: float = 0.04
    transitory_shock_std: float = 0.10
    permanent_income_memory: float = 0.18
    income_groups: int = 5
    income_risk_dispersion: float = 0.35
    state_mode: str = "employment_income"
    name: str = "hark-indshock-stateful"
    _policies: dict[tuple[int, int, int, int], object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not hark_available():
            raise EngineUnavailableError(
                "HARK foi solicitado, mas o pacote econ-ark/HARK não está instalado. "
                'Instale as dependências de simulação com: pip install -e ".[simulation]"'
            )

    def _discount_factor(self, patience_bucket: int) -> float:
        # Three explicit patience cohorts around the profile's center. Keeping
        # the value bucketed makes the HARK cache deterministic and auditable.
        patience_bucket = max(0, min(2, int(patience_bucket)))
        annual = self.annual_discount_factor + (1 - patience_bucket) * 0.015
        annual = max(0.55, min(0.999, annual))
        return annual ** (1.0 / 12.0)

    @staticmethod
    def _patience_bucket(household: Household) -> int:
        normalized = (household.propensity_to_consume - 0.75) / 0.20
        normalized = max(0.0, min(0.999999, normalized))
        return int(normalized * 3)

    def _policy_function(
        self,
        *,
        household: Household,
        annual_policy_rate: float,
        unemployment_probability: float,
    ):
        # Cache by a coarse interest/risk grid. This limits HARK solves when
        # thousands of heterogeneous households share a small number of states.
        rate_bucket = int(round(annual_policy_rate * 400.0))  # 25 bp annual
        risk_bucket = int(round(unemployment_probability * 200.0))  # 50 bp probability
        group_bucket = max(0, min(self.income_groups - 1, household.income_group))
        patience_bucket = self._patience_bucket(household)
        key = (group_bucket, patience_bucket, rate_bucket, risk_bucket)
        if key in self._policies:
            return self._policies[key]

        from HARK.ConsumptionSaving.ConsIndShockModel import IndShockConsumerType

        annual_gross = max(0.01, 1.0 + annual_policy_rate)
        monthly_rfree = max(0.90, annual_gross ** (1.0 / 12.0))
        consumer = IndShockConsumerType(
            cycles=0,
            CRRA=self.crra,
            DiscFac=self._discount_factor(patience_bucket),
            LivPrb=[0.995],
            PermGroFac=[1.0],
            Rfree=[monthly_rfree],
            PermShkStd=[max(0.0, self.permanent_shock_std)],
            TranShkStd=[max(0.0, self.transitory_shock_std)],
            UnempPrb=max(0.001, min(0.50, unemployment_probability)),
            IncUnemp=max(0.0, min(1.0, self.unemployment_replacement_rate)),
            BoroCnstArt=0.0,
            CubicBool=False,
            vFuncBool=False,
            quiet=True,
            seed=group_bucket * 10 + patience_bucket,
        )
        consumer.solve()
        cfunc = consumer.solution[0].cFunc
        self._policies[key] = cfunc
        return cfunc

    def budget(
        self,
        *,
        household: Household,
        deposit: float,
        income_tax_rate: float,
        annual_policy_rate: float,
        aggregate_unemployment_rate: float,
        observed_job_separation_rate: float,
    ) -> float:
        if deposit <= 0:
            return 0.0

        if self.state_mode == "employment_income":
            state = update_household_income_state(
                household,
                income_tax_rate=income_tax_rate,
                aggregate_unemployment_rate=aggregate_unemployment_rate,
                observed_job_separation_rate=observed_job_separation_rate,
                base_unemployment_probability=self.unemployment_probability,
                unemployment_replacement_rate=self.unemployment_replacement_rate,
                permanent_income_memory=self.permanent_income_memory,
                income_groups=self.income_groups,
                income_risk_dispersion=self.income_risk_dispersion,
            )
            permanent_income = state.permanent_income
            unemployment_probability = state.unemployment_probability
        else:
            after_tax_wage = household.wage * max(0.0, 1.0 - income_tax_rate)
            permanent_income = max(
                household.last_income * max(0.0, 1.0 - income_tax_rate),
                after_tax_wage * 0.30,
                1.0,
            )
            unemployment_probability = self.unemployment_probability

        m_nrm = max(0.0, deposit / permanent_income)
        cfunc = self._policy_function(
            household=household,
            annual_policy_rate=annual_policy_rate,
            unemployment_probability=unemployment_probability,
        )
        consumption = float(cfunc(m_nrm)) * permanent_income
        if not isfinite(consumption):
            raise ValueError("HARK returned a non-finite consumption recommendation")
        return max(0.0, min(deposit, consumption))


def create_consumption_policy(
    name: str,
    *,
    crra: float = 2.0,
    annual_discount_factor: float = 0.96,
    state_mode: str = "employment_income",
    unemployment_probability: float = 0.05,
    unemployment_replacement_rate: float = 0.30,
    permanent_shock_std: float = 0.04,
    transitory_shock_std: float = 0.10,
    permanent_income_memory: float = 0.18,
    income_groups: int = 5,
    income_risk_dispersion: float = 0.35,
) -> ConsumptionPolicy:
    if name == "heuristic":
        return HeuristicConsumptionPolicy()
    if name == "hark":
        return HarkConsumptionPolicy(
            crra=crra,
            annual_discount_factor=max(0.55, min(0.999, annual_discount_factor)),
            state_mode=state_mode,
            unemployment_probability=max(0.001, min(0.50, unemployment_probability)),
            unemployment_replacement_rate=max(0.0, min(1.0, unemployment_replacement_rate)),
            permanent_shock_std=max(0.0, permanent_shock_std),
            transitory_shock_std=max(0.0, transitory_shock_std),
            permanent_income_memory=max(0.01, min(1.0, permanent_income_memory)),
            income_groups=max(1, min(10, int(income_groups))),
            income_risk_dispersion=max(0.0, min(1.0, income_risk_dispersion)),
        )
    raise ValueError(f"Unknown household consumption behavior: {name}")
