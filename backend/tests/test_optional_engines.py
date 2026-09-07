import pytest

from economy_lab.core.schemas import ScenarioSpec
from economy_lab.core.simulation import run_economy_zero
from economy_lab.engines.hark_adapter import hark_available
from economy_lab.engines.mesa_adapter import mesa_available


@pytest.mark.skipif(not mesa_available(), reason="Mesa optional dependency not installed")
def test_mesa_activation_runtime_executes_and_keeps_ledger_balanced():
    result = run_economy_zero(
        ScenarioSpec(
            months=2,
            households=200,
            firms=8,
            banks=2,
            seed=29,
            activation_engine="mesa",
        )
    )
    assert result.engines is not None
    assert result.engines.activation.startswith("mesa")
    assert result.summary.ledger_balanced is True


@pytest.mark.skipif(not hark_available(), reason="HARK optional dependency not installed")
def test_hark_household_policy_executes_and_keeps_ledger_balanced():
    result = run_economy_zero(
        ScenarioSpec(
            months=2,
            households=200,
            firms=8,
            banks=2,
            seed=31,
            household_behavior="hark",
        )
    )
    assert result.engines is not None
    assert result.engines.household_decision.startswith("hark")
    assert result.summary.ledger_balanced is True
