"""Standalone module laboratories for Economy Lab Hub v1.5."""
from __future__ import annotations

from math import isfinite
from statistics import fmean
from typing import Any

from economy_lab.engines.dynare_adapter import render_reference_nk_model, run_reference_nk_model
from economy_lab.engines.hark_adapter import EngineUnavailableError, HarkConsumptionPolicy, hark_available, income_group_risk_multiplier
from economy_lab.abm.agents import Household
from economy_lab.engines.mesa_adapter import mesa_available
from economy_lab.engines.minsky_adapter import MinskyRestClient
from economy_lab.core.schemas import FinancialGuidancePoint


def dynare_template(**params: float | int) -> str:
    return render_reference_nk_model(
        irf_periods=int(params.get("irf_periods", 24)),
        monetary_shock_pp=float(params.get("monetary_shock_pp", 1.0)),
        beta=float(params.get("beta", 0.99)),
        sigma=float(params.get("sigma", 1.0)),
        kappa=float(params.get("kappa", 0.10)),
        rho_i=float(params.get("rho_i", 0.80)),
        phi_pi=float(params.get("phi_pi", 1.50)),
        phi_x=float(params.get("phi_x", 0.25)),
    )


def run_dynare_lab(**params: float | int) -> dict[str, Any]:
    result = run_reference_nk_model(
        irf_periods=int(params.get("irf_periods", 24)),
        monetary_shock_pp=float(params.get("monetary_shock_pp", 1.0)),
        neutral_nominal_rate=float(params.get("neutral_nominal_rate", 8.0)),
        beta=float(params.get("beta", 0.99)),
        sigma=float(params.get("sigma", 1.0)),
        kappa=float(params.get("kappa", 0.10)),
        rho_i=float(params.get("rho_i", 0.80)),
        phi_pi=float(params.get("phi_pi", 1.50)),
        phi_x=float(params.get("phi_x", 0.25)),
        timeout_seconds=int(params.get("timeout_seconds", 120)),
    )
    return {
        "engine": "dynare-octave",
        "model_name": result.model_name,
        "model_kind": result.model_kind,
        "period_unit": result.period_unit,
        "shock_name": result.shock_name,
        "shock_size_pp": result.shock_size_pp,
        "neutral_nominal_rate": result.neutral_nominal_rate,
        "parameters": {
            "beta": result.beta, "sigma": result.sigma, "kappa": result.kappa,
            "rho_i": result.rho_i, "phi_pi": result.phi_pi, "phi_x": result.phi_x,
        },
        "irf": [
            {"period": p.period, "output_gap": p.output_gap, "inflation_gap": p.inflation_gap, "policy_rate_gap": p.policy_rate_gap}
            for p in result.points
        ],
        "warning": "Laboratório standalone: o resultado não altera o Simulation Lab automaticamente.",
    }


def _gini(values: list[float]) -> float:
    values = [max(0.0, float(value)) for value in values]
    if not values or sum(values) <= 0:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    weighted = sum((index + 1) * value for index, value in enumerate(ordered))
    total = sum(ordered)
    return (2.0 * weighted) / (n * total) - (n + 1.0) / n


def run_mesa_lab(*, agents: int = 100, steps: int = 100, initial_wealth: float = 10.0, transfer_amount: float = 1.0, seed: int = 42) -> dict[str, Any]:
    if not mesa_available():
        raise EngineUnavailableError('Mesa Lab requer Mesa 3.5.x. Instale com: pip install -e ".[simulation]"')
    import mesa

    class WealthAgent(mesa.Agent):
        def __init__(self, model):
            super().__init__(model)
            self.wealth = float(initial_wealth)

        def exchange(self) -> None:
            if self.wealth < transfer_amount or len(self.model.agents) < 2:
                return
            candidates = [agent for agent in self.model.agents if agent is not self]
            recipient = self.model.random.choice(candidates)
            self.wealth -= transfer_amount
            recipient.wealth += transfer_amount

    class WealthModel(mesa.Model):
        def __init__(self):
            super().__init__(seed=seed)
            self.population = [WealthAgent(self) for _ in range(agents)]

        def step_once(self) -> None:
            self.agents.shuffle_do("exchange")

    model = WealthModel()
    path: list[dict[str, float | int]] = []
    sample_every = max(1, steps // 50)
    for step in range(1, steps + 1):
        model.step_once()
        if step == 1 or step == steps or step % sample_every == 0:
            wealth = [float(agent.wealth) for agent in model.agents]
            path.append({
                "step": step,
                "gini": _gini(wealth),
                "zero_wealth_share": sum(value <= 1e-12 for value in wealth) / len(wealth),
                "max_wealth": max(wealth),
            })

    wealth = [float(agent.wealth) for agent in model.agents]
    total = sum(wealth)
    if abs(total - agents * initial_wealth) > 1e-7:
        raise RuntimeError("Mesa Lab wealth conservation invariant failed")
    ordered = sorted(wealth)
    return {
        "engine": "mesa-3.5", "model": "wealth-exchange", "agents": agents, "steps": steps, "seed": seed,
        "initial_total_wealth": agents * initial_wealth, "final_total_wealth": total,
        "mean_wealth": fmean(wealth), "median_wealth": ordered[len(ordered) // 2], "max_wealth": max(wealth),
        "gini": _gini(wealth), "zero_wealth_share": sum(value <= 1e-12 for value in wealth) / len(wealth),
        "path": path,
        "warning": "Modelo didático standalone de troca de riqueza; não é uma economia calibrada.",
    }


def run_hark_lab(
    *,
    annual_interest_rate: float = 0.08,
    crra: float = 2.0,
    annual_discount_factor: float = 0.96,
    unemployment_probability: float = 0.05,
    unemployment_replacement_rate: float = 0.30,
    permanent_shock_std: float = 0.04,
    transitory_shock_std: float = 0.10,
    permanent_income_memory: float = 0.18,
    income_groups: int = 5,
    income_risk_dispersion: float = 0.35,
    max_market_resources: float = 12.0,
    points: int = 25,
) -> dict[str, Any]:
    if not hark_available():
        raise EngineUnavailableError('HARK Lab requer Econ-ARK/HARK. Instale com: pip install -e ".[simulation]"')

    policy = HarkConsumptionPolicy(
        crra=crra,
        annual_discount_factor=annual_discount_factor,
        unemployment_probability=unemployment_probability,
        unemployment_replacement_rate=unemployment_replacement_rate,
        permanent_shock_std=permanent_shock_std,
        transitory_shock_std=transitory_shock_std,
        permanent_income_memory=permanent_income_memory,
        income_groups=income_groups,
        income_risk_dispersion=income_risk_dispersion,
    )

    group_profiles: list[dict[str, Any]] = []
    baseline_rows: list[dict[str, float]] = []
    middle_group = max(0, min(income_groups - 1, income_groups // 2))
    for group in range(income_groups):
        # Standalone curves isolate the structural risk channel by group. Wages
        # and nominal wealth are normalized to one, as in HARK's c(m) setup.
        household = Household(
            id=group, bank_id=0, wage=1.0, propensity_to_consume=0.85,
            employed_by=0, last_income=1.0, income_group=group,
            permanent_income_estimate=1.0,
        )
        group_risk = max(0.001, min(0.50, unemployment_probability * income_group_risk_multiplier(
            group=group, groups=income_groups, dispersion=income_risk_dispersion
        )))
        cfunc = policy._policy_function(
            household=household,
            annual_policy_rate=annual_interest_rate,
            unemployment_probability=group_risk,
        )
        rows: list[dict[str, float]] = []
        for index in range(points):
            m = max_market_resources * index / max(1, points - 1)
            c = float(cfunc(m))
            if not isfinite(c):
                raise ValueError("HARK returned non-finite consumption")
            c = max(0.0, min(m, c))
            rows.append({
                "market_resources": m,
                "consumption": c,
                "saving": max(0.0, m - c),
                "consumption_share": (c / m) if m > 1e-12 else 0.0,
            })
        if group == middle_group:
            baseline_rows = rows
        group_profiles.append({
            "income_group": group + 1,
            "unemployment_probability": group_risk,
            "policy_curve": rows,
        })

    return {
        "engine": "hark-indshock-stateful",
        "model": "IndShockConsumerType",
        "parameters": {
            "annual_interest_rate": annual_interest_rate,
            "crra": crra,
            "annual_discount_factor": annual_discount_factor,
            "unemployment_probability": unemployment_probability,
            "unemployment_replacement_rate": unemployment_replacement_rate,
            "permanent_shock_std": permanent_shock_std,
            "transitory_shock_std": transitory_shock_std,
            "permanent_income_memory": permanent_income_memory,
            "income_groups": float(income_groups),
            "income_risk_dispersion": income_risk_dispersion,
        },
        "policy_curve": baseline_rows,
        "group_profiles": group_profiles,
        "warning": (
            "Curvas normalizadas por grupo de renda. Os multiplicadores de risco e o processo de renda são hipóteses "
            "estruturais auditáveis; ainda não foram calibrados em microdados reais."
        ),
    }


def minsky_command(*, action: str, path: str = "/minsky", variable_id: str | None = None, value: float | None = None) -> dict[str, Any]:
    client = MinskyRestClient()
    if action == "members":
        result = client.list_members(path)
    elif action == "signature":
        result = client.signature(path)
    elif action == "step":
        result = client.step()
    elif action == "reset":
        result = client.reset()
    elif action == "get_variable":
        if not variable_id:
            raise ValueError("variable_id is required for get_variable")
        result = client.get_variable_value(variable_id)
    elif action == "set_variable":
        if not variable_id or value is None:
            raise ValueError("variable_id and value are required for set_variable")
        result = client.set_variable_value(variable_id, float(value))
    else:
        raise ValueError(f"unsupported Minsky Lab action: {action}")
    return {"engine": "minsky-rest", "action": action, "result": result}


def run_minsky_financial_controller(
    *,
    steps: int = 12,
    reset_before: bool = False,
    unit_mode: str = "decimal",
    mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Capture a deterministic banking-control path from a live Minsky model.

    Only explicitly mapped scalar variables are read. Balance-sheet stocks are
    intentionally excluded: the Economy Lab ledger remains accounting authority.
    """
    if unit_mode not in {"decimal", "percent"}:
        raise ValueError("unit_mode must be decimal or percent")
    mapping = dict(mapping or {
        "minimum_bank_capital_ratio": ":bank_min_capital_ratio",
        "target_reserve_ratio": ":bank_target_reserve_ratio",
        "credit_supply_factor": ":credit_supply_factor",
        "default_writeoff_ratio": ":default_writeoff_ratio",
        "interbank_spread": ":interbank_spread",
        "central_bank_penalty_spread": ":cb_penalty_spread",
    })
    required = {
        "minimum_bank_capital_ratio", "target_reserve_ratio", "credit_supply_factor",
        "default_writeoff_ratio", "interbank_spread", "central_bank_penalty_spread",
    }
    if set(mapping) != required:
        missing = sorted(required - set(mapping))
        extra = sorted(set(mapping) - required)
        raise ValueError(f"invalid Minsky financial mapping; missing={missing}, extra={extra}")

    client = MinskyRestClient()
    if reset_before:
        client.reset()

    ratio_fields = {
        "minimum_bank_capital_ratio", "target_reserve_ratio", "default_writeoff_ratio",
        "interbank_spread", "central_bank_penalty_spread",
    }
    points: list[dict[str, float | int]] = []
    for month in range(1, steps + 1):
        raw = {key: float(client.get_variable_value(variable_id)) for key, variable_id in mapping.items()}
        canonical: dict[str, float | int] = {"month": month}
        for key, value in raw.items():
            canonical[key] = value * 100.0 if unit_mode == "decimal" and key in ratio_fields else value
        point = FinancialGuidancePoint.model_validate(canonical)
        points.append(point.model_dump(mode="python"))
        if month < steps:
            client.step()

    return {
        "engine": "minsky-rest-financial-controller",
        "unit_mode": unit_mode,
        "mapping": mapping,
        "points": points,
        "warning": (
            "Trajetória capturada de variáveis Minsky explicitamente mapeadas. Ela pode controlar "
            "regras bancárias do Simulation Lab, mas nunca substitui saldos ou identidades do ledger SFC."
        ),
    }


def run_mesa_component_lab(**params: Any) -> dict[str, Any]:
    """Run a small Mesa-native preview for a component that can be reused by Simulation Lab.

    These previews validate mechanics in isolation. They do not own Economy Zero
    balances or replace the SFC ledger; a saved Profile only transfers validated
    behavioral parameters into the integrated simulator.
    """
    if not mesa_available():
        raise EngineUnavailableError('Mesa Component Lab requer Mesa. Instale com: pip install -e ".[simulation]"')
    import mesa

    component = str(params.get("component", "activation"))
    steps = int(params.get("steps", 60))
    seed = int(params.get("seed", 42))
    activation_pattern = str(params.get("activation_pattern", "random"))
    shopping_sample_size = int(params.get("shopping_sample_size", 4))
    cheapest_choice_probability = float(params.get("cheapest_choice_probability", 1.0))
    price_adjustment_strength = float(params.get("price_adjustment_strength", 1.0))
    hiring_strength = float(params.get("hiring_strength", 1.0))
    layoff_strength = float(params.get("layoff_strength", 1.0))
    matching_efficiency = float(params.get("matching_efficiency", 1.0))

    if component == "activation":
        class OrderedAgent(mesa.Agent):
            def act(self) -> None:
                self.model.order.append(int(self.unique_id))

        class ActivationModel(mesa.Model):
            def __init__(self):
                super().__init__(seed=seed)
                self.order: list[int] = []
                self.population = [OrderedAgent(self) for _ in range(20)]
            def run_once(self) -> None:
                self.order = []
                if activation_pattern == "fixed":
                    self.agents.do("act")
                else:
                    self.agents.shuffle_do("act")

        model = ActivationModel()
        changed = 0
        path: list[dict[str, float | int]] = []
        canonical = sorted(int(agent.unique_id) for agent in model.agents)
        for step in range(1, min(steps, 200) + 1):
            model.run_once()
            differs = int(model.order != canonical)
            changed += differs
            if step <= 20 or step == steps:
                path.append({"step": step, "order_changed": differs})
        patch = {"activation_engine": "mesa", "mesa_activation_pattern": activation_pattern}
        return {
            "engine": "mesa-component-lab", "component": component, "scenario_patch": patch,
            "metrics": {"steps": steps, "changed_order_steps": changed, "pattern": activation_pattern},
            "path": path,
            "warning": "Preview isolado da ordem de ativação Mesa; o Profile controla somente a ativação no Simulation Lab.",
        }

    if component == "household_search":
        prices = [8.5, 9.2, 10.0, 10.8, 11.6, 12.4, 13.2, 14.0]

        class Shopper(mesa.Agent):
            def __init__(self, model):
                super().__init__(model)
                self.last_price = 0.0
                self.chose_cheapest = 0
            def shop(self) -> None:
                n = min(shopping_sample_size, len(prices))
                candidates = self.random.sample(prices, n)
                cheapest = min(candidates)
                if self.random.random() <= cheapest_choice_probability:
                    self.last_price = cheapest
                    self.chose_cheapest = 1
                else:
                    self.last_price = self.random.choice(candidates)
                    self.chose_cheapest = int(self.last_price == cheapest)

        class SearchModel(mesa.Model):
            def __init__(self):
                super().__init__(seed=seed)
                self.population = [Shopper(self) for _ in range(200)]
            def step_once(self) -> None:
                self.agents.shuffle_do("shop")

        model = SearchModel(); path=[]; all_prices=[]; cheapest_hits=0; observations=0
        for step in range(1, steps + 1):
            model.step_once()
            chosen=[float(a.last_price) for a in model.agents]
            hits=sum(int(a.chose_cheapest) for a in model.agents)
            all_prices.extend(chosen); cheapest_hits += hits; observations += len(chosen)
            if step == 1 or step == steps or step % max(1, steps // 25) == 0:
                path.append({"step": step, "average_price": fmean(chosen), "cheapest_share": hits / len(chosen)})
        patch = {
            "activation_engine": "mesa",
            "household_shopping_sample_size": shopping_sample_size,
            "household_cheapest_choice_probability": cheapest_choice_probability,
        }
        return {
            "engine":"mesa-component-lab", "component":component, "scenario_patch":patch,
            "metrics":{"average_chosen_price":fmean(all_prices), "cheapest_choice_share":cheapest_hits/max(1,observations), "sample_size":shopping_sample_size},
            "path":path,
            "warning":"Preview de busca de preços. HARK pode continuar decidindo o orçamento; este componente decide a busca/escolha da firma.",
        }

    if component == "firm_behavior":
        class FirmRuleAgent(mesa.Agent):
            def __init__(self, model):
                super().__init__(model)
                self.price = self.random.uniform(9.5, 10.5)
                self.employees = 50
                self.inventory_ratio = self.random.uniform(0.2, 2.1)
                self.utilization = self.random.uniform(0.6, 1.05)
            def update(self) -> None:
                adjustment = 0.0
                if self.utilization > .95 and self.inventory_ratio < .4: adjustment += .010
                elif self.inventory_ratio > 1.8: adjustment -= .006
                self.price *= 1 + adjustment * price_adjustment_strength
                if self.inventory_ratio > 1.8 and self.employees > 1:
                    self.employees -= max(0, int(self.employees * .03 * layoff_strength))
                elif self.utilization >= .85:
                    self.employees += max(0, int(max(1, self.employees * .02) * hiring_strength))
                self.inventory_ratio = max(.05, self.inventory_ratio + self.random.uniform(-.15,.15))
                self.utilization = max(.2, min(1.2, self.utilization + self.random.uniform(-.08,.08)))

        class FirmRuleModel(mesa.Model):
            def __init__(self):
                super().__init__(seed=seed)
                self.population=[FirmRuleAgent(self) for _ in range(80)]
            def step_once(self): self.agents.shuffle_do("update")
        model=FirmRuleModel(); path=[]
        for step in range(1,steps+1):
            model.step_once()
            if step==1 or step==steps or step%max(1,steps//25)==0:
                path.append({"step":step,"average_price":fmean(float(a.price) for a in model.agents),"average_employment":fmean(float(a.employees) for a in model.agents)})
        patch={"activation_engine":"mesa","firm_price_adjustment_strength":price_adjustment_strength,"firm_hiring_strength":hiring_strength,"firm_layoff_strength":layoff_strength}
        return {"engine":"mesa-component-lab","component":component,"scenario_patch":patch,"metrics":{"final_average_price":fmean(float(a.price) for a in model.agents),"final_average_employment":fmean(float(a.employees) for a in model.agents)},"path":path,"warning":"Preview isolado de regras de firma; os balanços e vendas reais continuam pertencendo ao Simulation Lab."}

    if component == "labor_market":
        class Seeker(mesa.Agent):
            def __init__(self, model):
                super().__init__(model); self.employed=False
            def seek(self) -> None:
                if self.employed or self.model.vacancies <= 0: return
                if self.random.random() <= matching_efficiency:
                    self.employed=True; self.model.vacancies-=1
        class LaborModel(mesa.Model):
            def __init__(self):
                super().__init__(seed=seed); self.vacancies=300; self.population=[Seeker(self) for _ in range(500)]
            def step_once(self): self.agents.shuffle_do("seek")
        model=LaborModel(); path=[]
        for step in range(1,steps+1):
            model.step_once(); employed=sum(bool(a.employed) for a in model.agents)
            if step==1 or step==steps or step%max(1,steps//25)==0:
                path.append({"step":step,"employed":employed,"unemployment_share":1-employed/len(model.agents),"vacancies":model.vacancies})
        patch={"activation_engine":"mesa","labor_matching_efficiency":matching_efficiency}
        return {"engine":"mesa-component-lab","component":component,"scenario_patch":patch,"metrics":{"matched":sum(bool(a.employed) for a in model.agents),"remaining_vacancies":model.vacancies,"matching_efficiency":matching_efficiency},"path":path,"warning":"Preview de matching. No Simulation Lab a regra atua sobre vagas endógenas geradas pelas empresas."}

    raise ValueError(f"unsupported Mesa component: {component}")
