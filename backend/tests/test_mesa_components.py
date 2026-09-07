from economy_lab.core.schemas import ScenarioSpec
from economy_lab.profiles.service import build_lab_profile, apply_profile_to_scenario
from economy_lab.core.simulation import run_simulation


def _component(component: str, **updates):
    base = {
        "component": component,
        "steps": 20,
        "seed": 42,
        "activation_pattern": "random",
        "shopping_sample_size": 4,
        "cheapest_choice_probability": 1.0,
        "price_adjustment_strength": 1.0,
        "hiring_strength": 1.0,
        "layoff_strength": 1.0,
        "matching_efficiency": 1.0,
    }
    base.update(updates)
    return build_lab_profile(module_id="mesa", inputs=base)


def test_household_search_component_profile_is_independent_from_hark_budget():
    profile = _component("household_search", shopping_sample_size=9, cheapest_choice_probability=.7)
    assert profile["kind"] == "households_market"
    scenario, changes = apply_profile_to_scenario(ScenarioSpec(), {**profile, "id": "mesa-shopping"})
    assert scenario.activation_engine == "mesa"
    assert scenario.household_shopping_sample_size == 9
    assert scenario.household_cheapest_choice_probability == .7
    assert scenario.household_behavior == "heuristic"
    assert scenario.applied_profiles["households_market"] == "mesa-shopping"
    assert changes


def test_firm_component_profile_transfers_rules():
    profile = _component("firm_behavior", price_adjustment_strength=1.8, hiring_strength=1.4, layoff_strength=.6)
    scenario, _ = apply_profile_to_scenario(ScenarioSpec(), {**profile, "id": "mesa-firms"})
    assert scenario.firm_price_adjustment_strength == 1.8
    assert scenario.firm_hiring_strength == 1.4
    assert scenario.firm_layoff_strength == .6
    assert scenario.applied_profiles["firms"] == "mesa-firms"


def test_labor_component_profile_transfers_matching_rule():
    profile = _component("labor_market", matching_efficiency=.55)
    scenario, _ = apply_profile_to_scenario(ScenarioSpec(), {**profile, "id": "mesa-labor"})
    assert scenario.labor_matching_efficiency == .55
    assert scenario.applied_profiles["labor_market"] == "mesa-labor"


def test_activation_component_profile_transfers_order_pattern():
    profile = _component("activation", activation_pattern="fixed")
    scenario, _ = apply_profile_to_scenario(ScenarioSpec(), {**profile, "id": "mesa-activation"})
    assert scenario.activation_engine == "mesa"
    assert scenario.mesa_activation_pattern == "fixed"


def test_native_simulator_accepts_component_rules_without_breaking_accounting():
    # Component parameters are plain kernel contracts; Basic/native remains usable
    # even if Mesa is absent. Only activation_engine=mesa requires Mesa itself.
    spec = ScenarioSpec(
        months=4,
        households=200,
        firms=10,
        banks=2,
        activation_engine="native",
        household_shopping_sample_size=7,
        household_cheapest_choice_probability=.5,
        firm_price_adjustment_strength=1.4,
        firm_hiring_strength=.8,
        firm_layoff_strength=1.2,
        labor_matching_efficiency=.7,
    )
    result = run_simulation(spec)
    assert result.summary.ledger_balanced
    assert result.summary.godley_stocks_balanced
    assert result.summary.godley_flows_balanced
