from __future__ import annotations

from fastapi.testclient import TestClient

from economy_lab.abm.economy_zero import EconomyZeroConfig, EconomyZeroModel
from economy_lab.core.schemas import FinancialGuidancePoint, ScenarioSpec
from economy_lab.core.simulation import run_simulation
from economy_lab.labs.standalone import run_minsky_financial_controller
from economy_lab.main import app
from economy_lab.profiles import apply_profile_to_scenario, build_lab_profile


def _point(month: int, credit: float = 1.0, capital: float = 8.0) -> dict[str, float | int]:
    return {
        "month": month,
        "minimum_bank_capital_ratio": capital,
        "target_reserve_ratio": 10.0,
        "credit_supply_factor": credit,
        "default_writeoff_ratio": 35.0,
        "interbank_spread": 1.0,
        "central_bank_penalty_spread": 2.0,
    }


def test_minsky_financial_capture_reads_explicit_variables_and_steps(monkeypatch):
    class FakeClient:
        values = {
            ":bank_min_capital_ratio": 0.08,
            ":bank_target_reserve_ratio": 0.10,
            ":credit_supply_factor": 0.75,
            ":default_writeoff_ratio": 0.35,
            ":interbank_spread": 0.01,
            ":cb_penalty_spread": 0.02,
        }
        steps = 0
        resets = 0

        def __init__(self):
            pass

        def get_variable_value(self, variable_id):
            return self.values[variable_id]

        def step(self):
            type(self).steps += 1
            self.values[":credit_supply_factor"] = max(0.05, self.values[":credit_supply_factor"] - 0.10)
            return {"t": type(self).steps}

        def reset(self):
            type(self).resets += 1
            return {"t": 0}

    monkeypatch.setattr("economy_lab.labs.standalone.MinskyRestClient", FakeClient)
    result = run_minsky_financial_controller(steps=3, reset_before=True, unit_mode="decimal")
    assert FakeClient.resets == 1
    assert FakeClient.steps == 2
    assert [p["month"] for p in result["points"]] == [1, 2, 3]
    assert result["points"][0]["minimum_bank_capital_ratio"] == 8.0
    assert result["points"][0]["target_reserve_ratio"] == 10.0
    assert result["points"][0]["default_writeoff_ratio"] == 35.0
    assert result["points"][0]["interbank_spread"] == 1.0
    assert result["points"][0]["credit_supply_factor"] == 0.75
    assert result["points"][2]["credit_supply_factor"] == 0.55


def test_minsky_financial_profile_becomes_active_and_trims_path_to_horizon():
    built = build_lab_profile(
        module_id="minsky",
        inputs={"selected_tool": "minsky-financial-controller"},
        outputs={"points": [_point(1, 0.9), _point(2, 0.6), _point(5, 0.4)]},
    )
    built["id"] = "financial-test"
    scenario, changes = apply_profile_to_scenario(ScenarioSpec(months=3), built)
    assert built["compatibility"] == "active-path"
    assert scenario.financial_engine == "minsky_profile"
    assert scenario.bank_credit_supply_factor == 0.9
    assert [p.month for p in scenario.financial_guidance] == [1, 2]
    assert scenario.applied_profiles["financial"] == "financial-test"
    assert changes


def test_financial_guidance_changes_credit_supply_and_preserves_ledger():
    loose = EconomyZeroModel(EconomyZeroConfig(households=100, firms=5, banks=1, seed=31, credit_supply_factor=1.0))
    tight = EconomyZeroModel(EconomyZeroConfig(households=100, firms=5, banks=1, seed=31, credit_supply_factor=0.25))
    loose_firm = loose.firms[0]
    tight_firm = tight.firms[0]
    loose_cash = loose.ledger.balance(loose_firm.deposit_account)
    tight_cash = tight.ledger.balance(tight_firm.deposit_account)
    loose._ensure_deposit(loose_firm, loose_cash + 100_000)
    tight._ensure_deposit(tight_firm, tight_cash + 100_000)
    loose_debt = max(0.0, -loose.ledger.balance(loose_firm.loan_liability))
    tight_debt = max(0.0, -tight.ledger.balance(tight_firm.loan_liability))
    assert tight_debt < loose_debt
    tight.ledger.assert_balanced()


def test_dynamic_financial_path_is_applied_month_by_month():
    model = EconomyZeroModel(EconomyZeroConfig(
        households=100,
        firms=5,
        banks=1,
        seed=5,
        financial_guidance=(
            # Kernel units are decimals except credit factor.
            __import__("economy_lab.finance", fromlist=["FinancialGuidance"]).FinancialGuidance(
                month=1, minimum_capital_ratio=0.08, target_reserve_ratio=0.10,
                credit_supply_factor=0.9, default_writeoff_ratio=0.35,
                interbank_spread=0.01, central_bank_penalty_spread=0.02,
            ),
            __import__("economy_lab.finance", fromlist=["FinancialGuidance"]).FinancialGuidance(
                month=2, minimum_capital_ratio=0.12, target_reserve_ratio=0.15,
                credit_supply_factor=0.4, default_writeoff_ratio=0.50,
                interbank_spread=0.02, central_bank_penalty_spread=0.04,
            ),
        ),
    ))
    model.step()
    assert model.financial_controls.credit_supply_factor == 0.9
    model.step()
    assert model.financial_controls.credit_supply_factor == 0.4
    assert model.financial_controls.minimum_capital_ratio == 0.12
    model.ledger.assert_balanced()


def test_simulation_reports_active_minsky_financial_profile():
    spec = ScenarioSpec(
        months=3,
        households=120,
        firms=6,
        banks=2,
        financial_engine="minsky_profile",
        bank_credit_supply_factor=0.75,
        financial_guidance=[FinancialGuidancePoint(**_point(1, 0.75)), FinancialGuidancePoint(**_point(2, 0.55))],
        applied_profiles={"financial": "profile-fin-1"},
    )
    result = run_simulation(spec)
    assert result.financial is not None
    assert result.financial.engine == "minsky-profile-controller-v1.0"
    assert result.financial.profile_id == "profile-fin-1"
    assert result.financial.current.credit_supply_factor == 0.55
    assert result.engines is not None
    assert result.engines.minsky == "minsky-profile-active-path-v1.0"
    assert result.summary.ledger_balanced is True
    assert result.summary.godley_stocks_balanced is True
    assert result.summary.godley_flows_balanced is True


def test_minsky_financial_api_returns_typed_path(monkeypatch):
    monkeypatch.setattr(
        "economy_lab.api.routes.run_minsky_financial_controller",
        lambda **kwargs: {
            "engine": "minsky-rest-financial-controller",
            "unit_mode": kwargs["unit_mode"],
            "mapping": kwargs["mapping"],
            "points": [_point(1, 0.8)],
            "warning": "test",
        },
    )
    response = TestClient(app).post("/api/v1/labs/minsky/financial/run", json={"steps": 1, "unit_mode": "decimal"})
    assert response.status_code == 200
    assert response.json()["points"][0]["credit_supply_factor"] == 0.8
