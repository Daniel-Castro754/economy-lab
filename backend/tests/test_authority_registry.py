import pytest
from fastapi.testclient import TestClient

from economy_lab.core.authority import (
    AuthorityConflictError,
    AuthoritySession,
    UnauthorizedWriteError,
    authority_plan_payload,
    authority_registry_payload,
)
from economy_lab.core.schemas import ScenarioSpec
from economy_lab.core.simulation import run_economy_zero
from economy_lab.main import app


def small_spec(**changes):
    base = dict(
        name="Authority smoke",
        months=2,
        households=100,
        firms=5,
        banks=1,
        seed=17,
        unemployment_benefits_enabled=False,
        household_credit_enabled=False,
        bank_resolution_mode="none",
    )
    base.update(changes)
    return ScenarioSpec(**base)


def test_registry_declares_ledger_as_only_balance_authority():
    rows = {item["field"]: item for item in authority_registry_payload()}
    assert rows["financial.bank_deposits"]["allowed_sources"] == ["ledger_sfc"]
    assert rows["financial.bank_credit"]["allowed_sources"] == ["ledger_sfc"]
    assert rows["macro.realized_gdp"]["allowed_sources"] == ["economy_zero_abm"]
    assert "dynare" not in rows["macro.realized_gdp"]["allowed_sources"]


def test_plan_resolves_dynamic_engines_without_changing_realized_authorities():
    spec = small_spec(
        activation_engine="mesa",
        household_behavior="hark",
        financial_engine="minsky_profile",
        macro_engine="dynare",
        macro_coupling="hybrid",
    )
    plan = {item["field"]: item["source"] for item in authority_plan_payload(spec)}
    assert plan["activation.agent_order_policy"] == "mesa"
    assert plan["household.consumption_policy"] == "hark"
    assert plan["financial.control_policy"] == "minsky_profile"
    assert plan["macro.structural_irf"] == "dynare"
    assert plan["macro.applied_policy_rate"] == "hybrid_coupler"
    assert plan["macro.realized_gdp"] == "economy_zero_abm"
    assert plan["financial.bank_deposits"] == "ledger_sfc"


def test_unauthorized_engine_cannot_claim_ledger_balance():
    session = AuthoritySession(small_spec())
    with pytest.raises(UnauthorizedWriteError):
        session.claim("financial.bank_deposits", "hark", tick=1, value=100.0)


def test_dynare_cannot_claim_realized_gdp():
    session = AuthoritySession(small_spec(macro_engine="dynare"))
    with pytest.raises(UnauthorizedWriteError):
        session.claim("macro.realized_gdp", "dynare", tick=1, value=101.0)


def test_duplicate_canonical_write_is_rejected_even_from_same_owner():
    session = AuthoritySession(small_spec())
    session.claim("macro.realized_gdp", "economy_zero_abm", tick=1, value=100.0)
    with pytest.raises(AuthorityConflictError):
        session.claim("macro.realized_gdp", "economy_zero_abm", tick=1, value=100.1)


def test_binding_check_detects_silent_fallback():
    session = AuthoritySession(small_spec(household_behavior="heuristic"))
    with pytest.raises(UnauthorizedWriteError):
        session.assert_binding("household.consumption_policy", "hark")


def test_economy_zero_emits_complete_clean_authority_audit():
    result = run_economy_zero(small_spec())
    assert result.authority is not None
    assert result.authority.status == "pass"
    assert result.authority.complete is True
    assert result.authority.violations == []
    fields = {item.field: item.source for item in result.authority.assignments}
    assert fields["macro.realized_gdp"] == "economy_zero_abm"
    assert fields["financial.bank_deposits"] == "ledger_sfc"
    assert fields["household.consumption_policy"] == "native_heuristic"
    assert result.authority.claims_by_field["macro.realized_gdp"] == 2
    assert result.authority.claims_by_field["financial.bank_deposits"] == 2


def test_authority_registry_and_plan_api():
    client = TestClient(app)
    registry = client.get("/api/v1/authority/registry")
    assert registry.status_code == 200
    assert any(item["field"] == "financial.bank_deposits" for item in registry.json())

    plan = client.post("/api/v1/authority/plan", json=small_spec().model_dump())
    assert plan.status_code == 200
    resolved = {item["field"]: item["source"] for item in plan.json()}
    assert resolved["macro.applied_policy_rate"] == "scenario_central_bank"
    assert resolved["financial.control_policy"] == "native_finance"


def test_canonical_economy_state_schema_is_frozen_and_source_labeled():
    result = run_economy_zero(small_spec(months=1))
    assert result.authority is not None
    assert result.authority.registry_version == "1.0"
    # The authority plan is the public source-of-truth mapping; realized state
    # stays Economy Zero / ledger-owned even when external engines are possible.
    owners = {item.field: item.source for item in result.authority.assignments}
    assert owners["macro.realized_inflation"] == "economy_zero_abm"
    assert owners["financial.household_debt"] == "ledger_sfc"
