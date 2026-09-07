from __future__ import annotations

import math

from economy_lab.core.schemas import ScenarioSpec
from .models import (
    SimpleEconomyState,
    SimpleExternalYear,
    SimpleInitialConfig,
    SimplePolicyDecision,
    SimpleRunRequest,
    SimpleRunResult,
    SimpleScenarioInfo,
    SimpleScoreBreakdown,
    SimpleStartResponse,
    SimpleStepRequest,
    SimpleStepResponse,
    SimpleToAdvancedRequest,
    SimpleToAdvancedResponse,
    SimpleYearResult,
)


_SCENARIOS: dict[str, SimpleScenarioInfo] = {
    "baseline": SimpleScenarioInfo(
        id="baseline",
        title="Crescimento global estável",
        description="Ambiente externo relativamente previsível, com crescimento mundial moderado e confiança sem grandes rupturas.",
        years=[
            SimpleExternalYear(year=1, world_growth=2.8, consumer_confidence=62, label="Expansão moderada"),
            SimpleExternalYear(year=2, world_growth=3.0, consumer_confidence=65, label="Confiança melhora"),
            SimpleExternalYear(year=3, world_growth=2.6, consumer_confidence=58, label="Normalização"),
            SimpleExternalYear(year=4, world_growth=2.3, consumer_confidence=54, label="Desaceleração leve"),
            SimpleExternalYear(year=5, world_growth=2.7, consumer_confidence=60, label="Recuperação"),
            SimpleExternalYear(year=6, world_growth=2.9, consumer_confidence=64, label="Expansão"),
            SimpleExternalYear(year=7, world_growth=2.5, consumer_confidence=59, label="Crescimento equilibrado"),
        ],
    ),
    "global_recession": SimpleScenarioInfo(
        id="global_recession",
        title="Recessão global",
        description="O crescimento mundial deteriora-se no meio do jogo e a confiança cai antes de uma recuperação gradual.",
        years=[
            SimpleExternalYear(year=1, world_growth=2.2, consumer_confidence=56, label="Desaceleração"),
            SimpleExternalYear(year=2, world_growth=1.0, consumer_confidence=44, label="Aversão ao risco"),
            SimpleExternalYear(year=3, world_growth=-1.5, consumer_confidence=30, label="Recessão global"),
            SimpleExternalYear(year=4, world_growth=-0.5, consumer_confidence=34, label="Fundo do ciclo"),
            SimpleExternalYear(year=5, world_growth=1.2, consumer_confidence=45, label="Recuperação inicial"),
            SimpleExternalYear(year=6, world_growth=2.4, consumer_confidence=55, label="Recuperação"),
            SimpleExternalYear(year=7, world_growth=2.8, consumer_confidence=61, label="Normalização"),
        ],
    ),
    "volatile": SimpleScenarioInfo(
        id="volatile",
        title="Economia mundial volátil",
        description="Alterna anos fortes e fracos para tornar mais difícil calibrar uma política estável.",
        years=[
            SimpleExternalYear(year=1, world_growth=4.0, consumer_confidence=78, label="Boom global"),
            SimpleExternalYear(year=2, world_growth=0.3, consumer_confidence=40, label="Freada brusca"),
            SimpleExternalYear(year=3, world_growth=3.6, consumer_confidence=72, label="Rebote"),
            SimpleExternalYear(year=4, world_growth=-0.8, consumer_confidence=35, label="Choque externo"),
            SimpleExternalYear(year=5, world_growth=2.0, consumer_confidence=50, label="Estabilização"),
            SimpleExternalYear(year=6, world_growth=3.4, consumer_confidence=70, label="Nova expansão"),
            SimpleExternalYear(year=7, world_growth=1.4, consumer_confidence=47, label="Desaceleração final"),
        ],
    ),
}


def list_simple_scenarios() -> list[SimpleScenarioInfo]:
    return list(_SCENARIOS.values())


def get_simple_scenario(scenario_id: str) -> SimpleScenarioInfo:
    try:
        return _SCENARIOS[scenario_id]
    except KeyError as exc:
        raise ValueError(f"Unknown simple scenario: {scenario_id}") from exc


def initial_state(config: SimpleInitialConfig) -> SimpleEconomyState:
    return SimpleEconomyState(
        year=0,
        gdp_index=config.initial_gdp_index,
        potential_gdp_index=config.initial_potential_gdp_index,
        real_gdp_growth=config.potential_growth,
        inflation=config.initial_inflation,
        unemployment=config.initial_unemployment,
        debt_to_gdp=config.initial_debt_to_gdp,
        budget_deficit_to_gdp=0.0,
        primary_balance_to_gdp=0.0,
        tax_revenue_to_gdp=config.baseline_government_spending,
        debt_interest_cost_to_gdp=0.0,
        output_gap=100 * (config.initial_gdp_index / config.initial_potential_gdp_index - 1),
        approval=config.initial_approval,
        price_index=100.0,
        last_interest_rate=config.neutral_interest_rate,
        last_income_tax=config.baseline_income_tax,
        last_corporate_tax=config.baseline_corporate_tax,
        last_government_spending=config.baseline_government_spending,
    )


def start_simple(config: SimpleInitialConfig) -> SimpleStartResponse:
    scenario = get_simple_scenario(config.scenario_id)
    return SimpleStartResponse(
        warning=(
            "Modelo agregado educacional. As equações são transparentes e próprias do Economy Lab; "
            "não reproduzem fórmulas proprietárias de simuladores externos e não são uma previsão econômica."
        ),
        config=config,
        state=initial_state(config),
        next_external=scenario.years[0],
    )


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def _triangular_score(value: float, ideal_low: float, ideal_high: float, hard_low: float, hard_high: float) -> float:
    if ideal_low <= value <= ideal_high:
        return 25.0
    if value < ideal_low:
        if value <= hard_low:
            return 0.0
        return 25.0 * (value - hard_low) / (ideal_low - hard_low)
    if value >= hard_high:
        return 0.0
    return 25.0 * (hard_high - value) / (hard_high - ideal_high)


def _score(state: SimpleEconomyState, previous_debt: float, potential_growth: float) -> SimpleScoreBreakdown:
    growth = _triangular_score(state.real_gdp_growth, 2.5, 4.5, -2.0, 8.0)
    unemployment = _triangular_score(state.unemployment, 4.0, 5.5, 2.0, 11.0)
    if state.inflation < 0:
        inflation = max(0.0, 8.0 + 8.0 * state.inflation)  # severe deflation penalty
    else:
        inflation = _triangular_score(state.inflation, 1.5, 2.5, 0.0, 9.0)
    fiscal = _triangular_score(state.budget_deficit_to_gdp, -1.5, 2.0, -8.0, 9.0)
    debt_change = state.debt_to_gdp - previous_debt
    if state.debt_to_gdp > 90:
        fiscal -= min(8.0, (state.debt_to_gdp - 90) * 0.15)
    if debt_change > max(1.5, potential_growth):
        fiscal -= min(5.0, debt_change - max(1.5, potential_growth))
    fiscal = _clamp(fiscal, 0.0, 25.0)
    total = _clamp(growth + unemployment + inflation + fiscal, 0.0, 100.0)
    return SimpleScoreBreakdown(
        growth=round(growth, 2), unemployment=round(unemployment, 2),
        inflation=round(inflation, 2), fiscal=round(fiscal, 2), total=round(total, 2),
    )


def _explain(
    previous: SimpleEconomyState,
    state: SimpleEconomyState,
    decision: SimplePolicyDecision,
    config: SimpleInitialConfig,
    external: SimpleExternalYear,
) -> tuple[list[str], list[str]]:
    items: list[str] = []
    warnings: list[str] = []
    rate_gap = decision.interest_rate - config.neutral_interest_rate
    if rate_gap > 1:
        items.append("Juros acima do nível neutro reduziram consumo/investimento e esfriaram a demanda agregada.")
    elif rate_gap < -1:
        items.append("Juros abaixo do nível neutro estimularam consumo/investimento e elevaram a demanda agregada.")
    if decision.government_spending > config.baseline_government_spending + 1:
        items.append("Gasto público elevado sustentou a demanda, mas pressionou o resultado fiscal.")
    elif decision.government_spending < config.baseline_government_spending - 1:
        items.append("Contenção do gasto reduziu a demanda no curto prazo e melhorou o saldo primário.")
    if decision.income_tax > config.baseline_income_tax + 2:
        items.append("Imposto de renda maior reduziu a renda disponível e o consumo privado.")
    elif decision.income_tax < config.baseline_income_tax - 2:
        items.append("Imposto de renda menor elevou a renda disponível e apoiou o consumo.")
    if decision.corporate_tax > config.baseline_corporate_tax + 2:
        items.append("Imposto corporativo maior reduziu o incentivo ao investimento privado.")
    elif decision.corporate_tax < config.baseline_corporate_tax - 2:
        items.append("Imposto corporativo menor apoiou o investimento privado.")
    if external.world_growth < 0:
        items.append("A recessão mundial reduziu exportações e adicionou um choque negativo de demanda.")
    elif external.world_growth > 3.3:
        items.append("O crescimento mundial forte elevou a demanda externa por exportações.")
    if external.consumer_confidence < 40:
        items.append("Confiança do consumidor fraca reduziu a disposição das famílias a gastar.")
    elif external.consumer_confidence > 70:
        items.append("Confiança elevada fortaleceu o consumo privado.")
    if state.output_gap > 2:
        items.append("A atividade ficou acima do PIB potencial, elevando a pressão inflacionária.")
    elif state.output_gap < -2:
        items.append("A atividade ficou abaixo do potencial, reduzindo inflação e aumentando ociosidade.")
    if state.inflation < 0:
        warnings.append("Deflação: o nível de preços está caindo; o score de estabilidade de preços é fortemente penalizado.")
    if state.debt_to_gdp > 90:
        warnings.append("Dívida/PIB elevada: o custo de juros e a sustentabilidade fiscal passaram a pesar mais na avaliação.")
    if state.real_gdp_growth < 0:
        warnings.append("Recessão: o PIB real encolheu neste ano.")
    return items[:6], warnings


def step_simple(request: SimpleStepRequest) -> SimpleStepResponse:
    config, prev, d = request.config, request.state, request.decision
    scenario = get_simple_scenario(config.scenario_id)
    external = scenario.years[prev.year]

    # Transparent aggregate-demand impulses, all expressed approximately in percentage points of annual growth.
    confidence_impulse = 0.045 * (external.consumer_confidence - 50.0)
    world_impulse = 0.35 * (external.world_growth - 2.5)
    interest_impulse = -0.34 * (d.interest_rate - config.neutral_interest_rate)
    income_tax_impulse = -0.11 * (d.income_tax - config.baseline_income_tax)
    corporate_tax_impulse = -0.09 * (d.corporate_tax - config.baseline_corporate_tax)
    fiscal_impulse = 0.38 * (d.government_spending - config.baseline_government_spending)
    gap_correction = -0.18 * prev.output_gap

    growth = config.potential_growth + confidence_impulse + world_impulse + interest_impulse + income_tax_impulse + corporate_tax_impulse + fiscal_impulse + gap_correction
    growth = _clamp(growth, -12.0, 12.0)

    gdp = prev.gdp_index * (1.0 + growth / 100.0)
    potential = prev.potential_gdp_index * (1.0 + config.potential_growth / 100.0)
    output_gap = 100.0 * (gdp / potential - 1.0)

    # Backward-looking, deliberately simple Phillips mechanism with anchored target.
    inflation = (
        0.58 * prev.inflation
        + 0.42 * config.inflation_target
        + 0.28 * output_gap
        + 0.05 * max(-5.0, min(5.0, external.world_growth - 2.5))
    )
    inflation = _clamp(inflation, -5.0, 25.0)

    # Okun-style unemployment dynamics with persistence around a natural rate.
    unemployment = (
        config.natural_unemployment
        + 0.62 * (prev.unemployment - config.natural_unemployment)
        + 0.62 * (config.potential_growth - growth)
    )
    unemployment = _clamp(unemployment, 1.5, 25.0)

    # Simplified tax base shares: labor income, corporate profits and a fixed indirect-tax base.
    cyclical_revenue = 0.18 * output_gap
    tax_revenue = 8.0 + 0.55 * d.income_tax + 0.18 * d.corporate_tax + cyclical_revenue
    tax_revenue = _clamp(tax_revenue, 0.0, 55.0)
    primary_deficit = d.government_spending - tax_revenue

    debt_yield = max(-2.0, 0.55 * d.interest_rate + 0.45 * max(inflation, 0.0))
    interest_cost = prev.debt_to_gdp * debt_yield / 100.0
    deficit = primary_deficit + interest_cost
    nominal_growth = max(-15.0, growth + inflation)
    debt_ratio = prev.debt_to_gdp * (1.0 + debt_yield / 100.0) / max(0.2, 1.0 + nominal_growth / 100.0) + primary_deficit
    debt_ratio = _clamp(debt_ratio, 0.0, 400.0)

    price_index = prev.price_index * max(0.2, 1.0 + inflation / 100.0)
    provisional = SimpleEconomyState(
        year=prev.year + 1,
        gdp_index=round(gdp, 4), potential_gdp_index=round(potential, 4),
        real_gdp_growth=round(growth, 4), inflation=round(inflation, 4), unemployment=round(unemployment, 4),
        debt_to_gdp=round(debt_ratio, 4), budget_deficit_to_gdp=round(deficit, 4),
        primary_balance_to_gdp=round(-primary_deficit, 4), tax_revenue_to_gdp=round(tax_revenue, 4),
        debt_interest_cost_to_gdp=round(interest_cost, 4), output_gap=round(output_gap, 4), approval=prev.approval,
        price_index=round(price_index, 4), last_interest_rate=d.interest_rate, last_income_tax=d.income_tax,
        last_corporate_tax=d.corporate_tax, last_government_spending=d.government_spending,
    )
    score = _score(provisional, prev.debt_to_gdp, config.potential_growth)
    # Approval is smoothed so a single year matters without erasing political memory.
    approval = _clamp(0.35 * prev.approval + 0.65 * score.total, 0.0, 100.0)
    state = provisional.model_copy(update={"approval": round(approval, 2)})
    explanation, warnings = _explain(prev, state, d, config, external)
    result = SimpleYearResult(year=state.year, external=external, decision=d, state=state, score=score, explanation=explanation, warnings=warnings)
    completed = state.year >= 7
    next_external = None if completed else scenario.years[state.year]
    return SimpleStepResponse(result=result, completed=completed, next_external=next_external)


def run_simple(request: SimpleRunRequest) -> SimpleRunResult:
    state = initial_state(request.config)
    first = state
    years: list[SimpleYearResult] = []
    for decision in request.decisions:
        if state.year >= 7:
            break
        response = step_simple(SimpleStepRequest(config=request.config, state=state, decision=decision))
        years.append(response.result)
        state = response.result.state
    return SimpleRunResult(
        warning="Modelo educacional agregado; use Economy Zero/Hybrid para mecanismos microeconômicos e financeiros detalhados.",
        config=request.config,
        initial_state=first,
        years=years,
        final_state=state,
        completed_years=len(years),
    )


def simple_to_advanced(request: SimpleToAdvancedRequest) -> SimpleToAdvancedResponse:
    state = request.state
    decision = request.decision or SimplePolicyDecision(
        interest_rate=state.last_interest_rate,
        income_tax=state.last_income_tax,
        corporate_tax=state.last_corporate_tax,
        government_spending=state.last_government_spending,
    )
    baseline_g = request.config.baseline_government_spending
    spending_change = 0.0 if baseline_g == 0 else 100.0 * (decision.government_spending / baseline_g - 1.0)
    scenario = ScenarioSpec(
        name=f"Detalhamento após Simple — ano {state.year}",
        months=request.months,
        initial_gdp=100.0,
        initial_inflation=state.inflation,
        initial_unemployment=state.unemployment,
        policy_rate=decision.interest_rate,
        income_tax=decision.income_tax,
        public_spending_change=_clamp(spending_change, -50.0, 100.0),
        mode="economy_zero",
    )
    return SimpleToAdvancedResponse(
        scenario=scenario.model_dump(mode="python"),
        mapped_fields=["initial_inflation", "initial_unemployment", "policy_rate", "income_tax", "public_spending_change", "months"],
        limitations=[
            "O imposto corporativo do Simple ainda não possui campo equivalente direto no ScenarioSpec detalhado.",
            "Dívida/PIB e PIB potencial não são transferidos diretamente porque Economy Zero usa balanços e estoques próprios.",
            "A conversão cria condições iniciais comparáveis; ela não garante que os dois motores produzam a mesma trajetória.",
        ],
    )
