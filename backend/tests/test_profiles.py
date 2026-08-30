from __future__ import annotations

from economy_lab.core.schemas import ScenarioSpec
from economy_lab.profiles import apply_preset, apply_profile_to_scenario, build_lab_profile, list_simulation_presets
from economy_lab.storage.sqlite_store import ProjectStore


def test_dynare_profile_maps_structural_parameters_into_simulation():
    built = build_lab_profile(module_id="dynare", inputs={
        "irf_periods": 18, "monetary_shock_bp": 175, "neutral_nominal_rate": 6.5,
        "beta": 0.985, "sigma": 1.4, "kappa": 0.16, "rho_i": 0.72,
        "phi_pi": 1.85, "phi_x": 0.4, "timeout_seconds": 90,
    })
    built["id"] = "macro-test"
    scenario, changes = apply_profile_to_scenario(ScenarioSpec(), built)
    assert scenario.macro_engine == "dynare"
    assert scenario.dynare_monetary_shock_bp == 175
    assert scenario.dynare_irf_periods == 18
    assert scenario.dynare_neutral_nominal_rate == 6.5
    assert scenario.dynare_beta == 0.985
    assert scenario.dynare_sigma == 1.4
    assert scenario.dynare_kappa == 0.16
    assert scenario.dynare_rho_i == 0.72
    assert scenario.dynare_phi_pi == 1.85
    assert scenario.dynare_phi_x == 0.4
    assert scenario.applied_profiles["macro"] == "macro-test"
    assert changes


def test_hark_profile_maps_preferences_into_household_engine():
    built = build_lab_profile(module_id="hark", inputs={
        "annual_interest_rate": 0.09, "crra": 3.1, "annual_discount_factor": 0.975,
        "max_market_resources": 15, "points": 40,
    })
    built["id"] = "hark-test"
    scenario, _ = apply_profile_to_scenario(ScenarioSpec(), built)
    assert scenario.household_behavior == "hark"
    assert scenario.hark_crra == 3.1
    assert scenario.hark_annual_discount_factor == 0.975
    assert scenario.applied_profiles["households"] == "hark-test"


def test_minsky_profile_is_assistive_and_does_not_mutate_native_ledger_controls():
    built = build_lab_profile(module_id="minsky", inputs={"path": "/minsky", "selected_tool": "minsky-introspection"})
    built["id"] = "minsky-test"
    base = ScenarioSpec(minimum_bank_capital_ratio=9.0, target_reserve_ratio=11.0)
    scenario, changes = apply_profile_to_scenario(base, built)
    assert changes == []
    assert scenario.minimum_bank_capital_ratio == 9.0
    assert scenario.target_reserve_ratio == 11.0
    assert scenario.applied_profiles["financial"] == "minsky-test"
    assert built["compatibility"] == "assistive-only"


def test_basic_and_full_current_presets():
    base = ScenarioSpec()
    basic = apply_preset(base.model_copy(update={"activation_engine": "native"}), "basic")
    assert basic.activation_engine == "native"
    assert basic.household_behavior == "heuristic"
    assert basic.macro_engine == "off"
    full = apply_preset(base, "full-current")
    assert full.activation_engine == "mesa"
    assert full.household_behavior == "hark"
    assert full.macro_engine == "dynare"
    assert full.macro_coupling == "hybrid"
    assert full.macro_recalibration == "quarterly"
    assert {item["id"] for item in list_simulation_presets()} >= {"basic", "intermediate", "macro-hybrid", "full-current", "custom"}


def test_profile_store_roundtrip_and_schema_v5(tmp_path):
    store = ProjectStore(tmp_path / "profiles.sqlite3")
    item = store.create_profile(
        name="Macro teste", description="", kind="macro", module_id="dynare", compatibility="active",
        payload={"inputs": {"phi_pi": 1.7}}, scenario_patch={"macro_engine": "dynare", "dynare_phi_pi": 1.7},
    )
    assert store.status()["schema_version"] == 5
    assert store.status()["profiles"] == 1
    assert store.get_profile(item["id"])["scenario_patch"]["dynare_phi_pi"] == 1.7
    assert store.list_profiles(module_id="dynare")[0]["name"] == "Macro teste"
    assert store.delete_profile(item["id"]) is True
    assert store.status()["profiles"] == 0
