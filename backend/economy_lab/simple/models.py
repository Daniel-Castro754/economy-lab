from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SimpleScenarioId = Literal["baseline", "global_recession", "volatile"]


class SimpleModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class SimpleExternalYear(SimpleModel):
    year: int = Field(ge=1, le=7)
    world_growth: float
    consumer_confidence: float = Field(ge=0, le=100)
    label: str = ""


class SimpleScenarioInfo(SimpleModel):
    id: SimpleScenarioId
    title: str
    description: str
    years: list[SimpleExternalYear]


class SimpleInitialConfig(SimpleModel):
    scenario_id: SimpleScenarioId = "baseline"
    initial_gdp_index: float = Field(default=100.0, gt=0)
    initial_potential_gdp_index: float = Field(default=100.0, gt=0)
    initial_inflation: float = Field(default=2.5, ge=-10, le=50)
    initial_unemployment: float = Field(default=5.5, ge=0, le=40)
    initial_debt_to_gdp: float = Field(default=50.0, ge=0, le=300)
    initial_approval: float = Field(default=65.0, ge=0, le=100)
    potential_growth: float = Field(default=2.5, ge=-5, le=10)
    inflation_target: float = Field(default=2.0, ge=0, le=10)
    natural_unemployment: float = Field(default=5.0, ge=0, le=20)
    neutral_interest_rate: float = Field(default=4.0, ge=-5, le=30)
    baseline_income_tax: float = Field(default=20.0, ge=0, le=60)
    baseline_corporate_tax: float = Field(default=22.0, ge=0, le=60)
    baseline_government_spending: float = Field(default=22.0, ge=0, le=60)


class SimplePolicyDecision(SimpleModel):
    interest_rate: float = Field(default=4.0, ge=-5, le=40)
    income_tax: float = Field(default=20.0, ge=0, le=60)
    corporate_tax: float = Field(default=22.0, ge=0, le=60)
    government_spending: float = Field(default=22.0, ge=0, le=60, description="Government primary spending as % of GDP")


class SimpleEconomyState(SimpleModel):
    year: int = Field(default=0, ge=0, le=7)
    gdp_index: float = Field(gt=0)
    potential_gdp_index: float = Field(gt=0)
    real_gdp_growth: float
    inflation: float
    unemployment: float = Field(ge=0, le=60)
    debt_to_gdp: float = Field(ge=0, le=500)
    budget_deficit_to_gdp: float
    primary_balance_to_gdp: float
    tax_revenue_to_gdp: float
    debt_interest_cost_to_gdp: float
    output_gap: float
    approval: float = Field(ge=0, le=100)
    price_index: float = Field(gt=0)
    last_interest_rate: float
    last_income_tax: float
    last_corporate_tax: float
    last_government_spending: float


class SimpleScoreBreakdown(SimpleModel):
    growth: float = Field(ge=0, le=25)
    unemployment: float = Field(ge=0, le=25)
    inflation: float = Field(ge=0, le=25)
    fiscal: float = Field(ge=0, le=25)
    total: float = Field(ge=0, le=100)


class SimpleYearResult(SimpleModel):
    year: int = Field(ge=1, le=7)
    external: SimpleExternalYear
    decision: SimplePolicyDecision
    state: SimpleEconomyState
    score: SimpleScoreBreakdown
    explanation: list[str]
    warnings: list[str] = Field(default_factory=list)


class SimpleStartResponse(SimpleModel):
    model: str = "simple-macro-policy-v1"
    warning: str
    config: SimpleInitialConfig
    state: SimpleEconomyState
    next_external: SimpleExternalYear


class SimpleStepRequest(SimpleModel):
    config: SimpleInitialConfig
    state: SimpleEconomyState
    decision: SimplePolicyDecision

    @model_validator(mode="after")
    def horizon_not_finished(self):
        if self.state.year >= 7:
            raise ValueError("The simple simulation already completed all 7 years")
        return self


class SimpleStepResponse(SimpleModel):
    model: str = "simple-macro-policy-v1"
    result: SimpleYearResult
    completed: bool
    next_external: SimpleExternalYear | None = None


class SimpleRunRequest(SimpleModel):
    config: SimpleInitialConfig = Field(default_factory=SimpleInitialConfig)
    decisions: list[SimplePolicyDecision] = Field(min_length=1, max_length=7)


class SimpleRunResult(SimpleModel):
    model: str = "simple-macro-policy-v1"
    warning: str
    config: SimpleInitialConfig
    initial_state: SimpleEconomyState
    years: list[SimpleYearResult]
    final_state: SimpleEconomyState
    completed_years: int


class SimpleToAdvancedRequest(SimpleModel):
    config: SimpleInitialConfig
    state: SimpleEconomyState
    decision: SimplePolicyDecision | None = None
    months: int = Field(default=24, ge=1, le=240)


class SimpleToAdvancedResponse(SimpleModel):
    scenario: dict[str, object]
    mapped_fields: list[str]
    limitations: list[str]
