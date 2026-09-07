from pathlib import Path

from scipy.io import savemat

from economy_lab.engines.dynare_adapter import (
    irf_to_monthly_guidance,
    parse_dynare_irfs,
    render_reference_nk_model,
)


def test_reference_model_contains_core_nk_equations():
    source = render_reference_nk_model(irf_periods=12, monetary_shock_pp=1.25)
    assert "x = x(+1)" in source
    assert "pi = beta*pi(+1) + kappa*x + u;" in source
    assert "phi_pi*pi" in source
    assert "stderr 1.25" in source
    assert "irf=12" in source


def test_parse_dynare_irfs_from_results_mat(tmp_path: Path):
    results = tmp_path / "economy_lab_nk_results.mat"
    savemat(
        results,
        {
            "oo_": {
                "irfs": {
                    "x_e_i": [-0.25, -0.10, -0.03],
                    "pi_e_i": [-0.08, -0.04, -0.01],
                    "i_e_i": [1.00, 0.65, 0.40],
                }
            }
        },
    )
    points = parse_dynare_irfs(results)
    assert len(points) == 3
    assert points[0].output_gap == -0.25
    assert points[0].policy_rate_gap == 1.0
    assert points[-1].period == 3


def test_monthly_guidance_is_explicit_hold_not_hidden_interpolation(tmp_path: Path):
    # Reuse the IRF dataclass through a tiny synthetic .mat to exercise public API.
    temp = tmp_path / "economy_lab_test_irf.mat"
    savemat(
        temp,
        {"oo_": {"irfs": {"x_e_i": [-0.2], "pi_e_i": [-0.1], "i_e_i": [1.0]}}},
    )
    points = parse_dynare_irfs(temp)
    monthly = irf_to_monthly_guidance(points)
    assert len(monthly) == 3
    assert [item["month"] for item in monthly] == [1.0, 2.0, 3.0]
    assert all(item["output_gap"] == -0.2 for item in monthly)


def test_hybrid_coupler_applies_bounded_policy_and_records_feedback():
    from economy_lab.core.coupling import HybridMacroCoupler
    from economy_lab.engines.dynare_adapter import DynareIRFPoint

    class Metrics:
        gdp_index = 100.0
        inflation = 4.5
        unemployment = 7.0
        bank_credit = 1000.0
        credit_rationed = 100.0
        undercapitalized_banks = 1

    coupler = HybridMacroCoupler(
        points=[DynareIRFPoint(period=1, output_gap=-0.4, inflation_gap=-0.1, policy_rate_gap=1.0)],
        base_policy_rate_pct=10.0,
        inflation_anchor_pct=4.0,
        coupling_strength=0.5,
        feedback_strength=0.2,
    )
    signal = coupler.signal_for_month(1)
    assert signal.applied_policy_rate_pct == 10.5
    assert signal.demand_signal_pp == -0.2
    observation = coupler.observe(signal=signal, metrics=Metrics())
    assert 0.0 <= observation.financial_stress <= 1.0
    next_signal = coupler.signal_for_month(2)
    assert -3.0 <= next_signal.feedback_policy_gap_pp <= 3.0


def test_replacing_future_guidance_does_not_rewrite_past_months():
    from economy_lab.core.coupling import HybridMacroCoupler
    from economy_lab.engines.dynare_adapter import DynareIRFPoint

    coupler = HybridMacroCoupler(
        points=[DynareIRFPoint(period=1, output_gap=-0.2, inflation_gap=-0.1, policy_rate_gap=1.0)],
        base_policy_rate_pct=10.0,
        inflation_anchor_pct=4.0,
        coupling_strength=1.0,
        feedback_strength=0.0,
    )
    before = coupler.signal_for_month(1)
    coupler.replace_guidance(
        points=[DynareIRFPoint(period=1, output_gap=0.4, inflation_gap=0.2, policy_rate_gap=-0.5)],
        start_month=4,
        base_policy_rate_pct=11.0,
    )
    historical = coupler.signal_for_month(1)
    future = coupler.signal_for_month(4)
    assert historical.output_gap_guidance_pp == before.output_gap_guidance_pp
    assert historical.dynare_policy_gap_pp == before.dynare_policy_gap_pp
    assert future.output_gap_guidance_pp == 0.4
    assert future.dynare_policy_gap_pp == -0.5
