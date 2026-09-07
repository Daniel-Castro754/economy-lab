from economy_lab.core.schemas import ScenarioSpec
from economy_lab.core.simulation import run_demo_simulation, run_simulation


def test_demo_simulation_returns_requested_horizon():
    result = run_demo_simulation(ScenarioSpec(months=12, mode="demo"))
    assert len(result.series) == 12
    assert result.series[-1].month == 12


def test_tighter_policy_reduces_demo_gdp_relative_to_looser_policy():
    loose = run_demo_simulation(ScenarioSpec(months=24, policy_rate=6.0, mode="demo"))
    tight = run_demo_simulation(ScenarioSpec(months=24, policy_rate=14.0, mode="demo"))
    assert tight.summary.final_gdp_index < loose.summary.final_gdp_index


def test_dispatch_defaults_to_economy_zero():
    result = run_simulation(ScenarioSpec(months=2, households=200, firms=8, banks=2))
    assert result.model == "economy-zero-labor-benefits-v2.4"


def test_dynare_macro_report_is_advisory(monkeypatch):
    from economy_lab.engines.dynare_adapter import DynareIRFPoint, DynareMacroResult
    import economy_lab.core.simulation as simulation

    fake = DynareMacroResult(
        model_name="economy-lab-reference-nk",
        model_kind="new-keynesian-dsge",
        period_unit="quarter",
        shock_name="monetary_policy",
        shock_size_pp=1.0,
        neutral_nominal_rate=8.0,
        beta=0.99,
        sigma=1.0,
        kappa=0.1,
        rho_i=0.8,
        phi_pi=1.5,
        phi_x=0.25,
        points=(
            DynareIRFPoint(period=1, output_gap=-0.2, inflation_gap=-0.05, policy_rate_gap=1.0),
            DynareIRFPoint(period=2, output_gap=-0.1, inflation_gap=-0.03, policy_rate_gap=0.7),
        ),
        workdir="test",
        results_file="test.mat",
    )
    monkeypatch.setattr(simulation, "run_reference_nk_model", lambda **kwargs: fake)
    result = simulation.run_simulation(
        ScenarioSpec(
            months=1,
            households=120,
            firms=8,
            banks=2,
            macro_engine="dynare",
            dynare_monetary_shock_bp=100,
        )
    )
    assert result.macro is not None
    assert result.macro.coupling_mode == "advisory-only"
    assert result.macro.irf[0].output_gap == -0.2
    assert result.engines is not None
    assert result.engines.macro == "dynare-7.x-reference-nk-v1.0"
    assert result.coupling is None


def test_dynare_hybrid_coupling_changes_policy_path_and_preserves_accounting(monkeypatch):
    from economy_lab.engines.dynare_adapter import DynareIRFPoint, DynareMacroResult
    import economy_lab.core.simulation as simulation

    fake = DynareMacroResult(
        model_name="economy-lab-reference-nk",
        model_kind="new-keynesian-dsge",
        period_unit="quarter",
        shock_name="monetary_policy",
        shock_size_pp=1.0,
        neutral_nominal_rate=8.0,
        beta=0.99, sigma=1.0, kappa=0.1, rho_i=0.8, phi_pi=1.5, phi_x=0.25,
        points=(
            DynareIRFPoint(period=1, output_gap=-0.3, inflation_gap=-0.08, policy_rate_gap=1.0),
            DynareIRFPoint(period=2, output_gap=-0.15, inflation_gap=-0.04, policy_rate_gap=0.6),
        ),
        workdir="test", results_file="test.mat",
    )
    monkeypatch.setattr(simulation, "run_reference_nk_model", lambda **kwargs: fake)
    result = simulation.run_simulation(
        ScenarioSpec(
            months=4, households=120, firms=8, banks=2,
            macro_engine="dynare", macro_coupling="hybrid",
            macro_coupling_strength=0.5, macro_feedback_strength=0.1,
        )
    )
    assert result.coupling is not None
    assert result.macro is not None
    assert result.macro.coupling_mode == "hybrid-feedback"
    assert result.series[0].policy_rate == 10.5
    assert len(result.coupling.points) == 4
    assert result.summary.ledger_balanced is True
    assert result.summary.godley_stocks_balanced is True
    assert result.engines is not None
    assert result.engines.macro == "dynare-7.x-reference-nk-hybrid-v1.0"


def test_hybrid_coupling_requires_dynare_engine():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ScenarioSpec(macro_engine="off", macro_coupling="hybrid")


def test_quarterly_dynare_recalibration_resolves_and_preserves_ledger(monkeypatch):
    from economy_lab.engines.dynare_adapter import DynareIRFPoint, DynareMacroResult
    import economy_lab.core.simulation as simulation

    calls = []

    def fake_run(**kwargs):
        calls.append(dict(kwargs))
        phi_pi = float(kwargs.get("phi_pi", 1.5))
        shock = float(kwargs.get("monetary_shock_pp", 1.0))
        return DynareMacroResult(
            model_name="economy-lab-reference-nk",
            model_kind="new-keynesian-dsge",
            period_unit="quarter",
            shock_name="monetary_policy",
            shock_size_pp=shock,
            neutral_nominal_rate=float(kwargs.get("neutral_nominal_rate", 8.0)),
            beta=float(kwargs.get("beta", 0.99)),
            sigma=float(kwargs.get("sigma", 1.0)),
            kappa=float(kwargs.get("kappa", 0.1)),
            rho_i=float(kwargs.get("rho_i", 0.8)),
            phi_pi=phi_pi,
            phi_x=float(kwargs.get("phi_x", 0.25)),
            points=(
                DynareIRFPoint(period=1, output_gap=-0.2 * shock, inflation_gap=-0.05 * phi_pi, policy_rate_gap=shock),
                DynareIRFPoint(period=2, output_gap=-0.1 * shock, inflation_gap=-0.02 * phi_pi, policy_rate_gap=0.5 * shock),
            ),
            workdir="test",
            results_file="test.mat",
        )

    monkeypatch.setattr(simulation, "run_reference_nk_model", fake_run)
    result = simulation.run_simulation(
        ScenarioSpec(
            months=7,
            households=160,
            firms=8,
            banks=2,
            macro_engine="dynare",
            macro_coupling="hybrid",
            macro_recalibration="quarterly",
            macro_recalibration_strength=0.4,
        )
    )
    assert len(calls) == 3  # initial + after month 3 + after month 6
    assert result.macro_recalibration is not None
    assert result.macro_recalibration.completed_recalibrations == 2
    assert [run.trigger_month for run in result.macro_recalibration.runs] == [3, 6]
    assert result.macro is not None
    assert result.macro.coupling_mode == "hybrid-quarterly-resolve"
    assert result.engines is not None
    assert result.engines.macro == "dynare-7.x-reference-nk-quarterly-v1.0"
    assert result.summary.ledger_balanced is True
    assert result.summary.godley_stocks_balanced is True
    assert result.summary.godley_flows_balanced is True
    # The second/third calls must be state-conditioned rather than exact copies.
    assert calls[1]["monetary_shock_pp"] < calls[0]["monetary_shock_pp"]
    assert "phi_pi" in calls[1]


def test_quarterly_recalibration_requires_dynare_hybrid():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ScenarioSpec(macro_recalibration="quarterly")
