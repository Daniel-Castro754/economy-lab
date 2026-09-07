from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from economy_lab.abm.economy_zero import EconomyZeroConfig, EconomyZeroModel
from economy_lab.core.schemas import (
    DataProvenanceRecord,
    EconomicObservation,
    MinskyReconciliationRequest,
    MinskyExchangeResponse,
    MinskyGodleyCellMappingSpec,
)
from economy_lab.engines.minsky_adapter import build_godley_export
from economy_lab.engines.minsky_reconciliation import (
    MinskyGodleyCellMapping,
    ReconciliationContractError,
    capture_minsky_values,
    reconcile_godley_payload,
)
from economy_lab.finance.sfc import SECTORS
from economy_lab.main import app


TEMPLATE_HASH = "a" * 64


def canonical_payload():
    model = EconomyZeroModel(EconomyZeroConfig(households=100, firms=5, banks=2, seed=44))
    model.run(1)
    return build_godley_export(model.ledger, tick=model.tick).to_payload()


def full_nonzero_mapping(payload):
    mappings = []
    observed = {}
    for kind in ("stocks", "flows"):
        for row in payload[kind]:
            for sector in SECTORS:
                value = float(row[sector])
                if abs(value) <= 1e-6:
                    continue
                variable_id = f":{kind}_{row['instrument']}_{sector}"
                mappings.append(
                    MinskyGodleyCellMapping(
                        kind=kind,
                        instrument=str(row["instrument"]),
                        sector=sector,
                        variable_id=variable_id,
                    )
                )
                observed[variable_id] = value
    return mappings, observed


def test_complete_read_only_reconciliation_passes_and_is_deterministic():
    canonical = canonical_payload()
    mappings, observed = full_nonzero_mapping(canonical)
    first = reconcile_godley_payload(
        canonical,
        template_id="known-template-v1",
        template_sha256=TEMPLATE_HASH,
        mappings=mappings,
        observed_values=observed,
    )
    second = reconcile_godley_payload(
        canonical,
        template_id="known-template-v1",
        template_sha256=TEMPLATE_HASH,
        mappings=reversed(mappings),
        observed_values=dict(reversed(list(observed.items()))),
    )
    assert first.status == "pass"
    assert first.complete is True
    assert first.drift_count == 0
    assert first.read_only is True
    assert first.external_can_mutate_ledger is False
    assert first.accounting_authority == "ledger_sfc"
    assert first.report_id == second.report_id
    assert first.canonical_hash == second.canonical_hash


def test_sign_conversion_is_explicit_and_drift_fails():
    canonical = canonical_payload()
    mappings, observed = full_nonzero_mapping(canonical)
    target = mappings[0]
    converted = MinskyGodleyCellMapping(
        kind=target.kind,
        instrument=target.instrument,
        sector=target.sector,
        variable_id=target.variable_id,
        external_multiplier=-1.0,
    )
    mappings[0] = converted
    observed[target.variable_id] = -observed[target.variable_id]
    passed = reconcile_godley_payload(
        canonical,
        template_id="sign-template",
        template_sha256=TEMPLATE_HASH,
        mappings=mappings,
        observed_values=observed,
    )
    assert passed.status == "pass"

    observed[target.variable_id] += 100.0
    failed = reconcile_godley_payload(
        canonical,
        template_id="sign-template",
        template_sha256=TEMPLATE_HASH,
        mappings=mappings,
        observed_values=observed,
    )
    assert failed.status == "fail"
    assert failed.drift_count == 1
    assert any(not item.within_tolerance for item in failed.cells)


def test_full_coverage_is_strict_but_partial_mode_is_audited():
    canonical = canonical_payload()
    mappings, observed = full_nonzero_mapping(canonical)
    removed = mappings.pop()
    observed.pop(removed.variable_id)

    strict = reconcile_godley_payload(
        canonical,
        template_id="coverage-template",
        template_sha256=TEMPLATE_HASH,
        mappings=mappings,
        observed_values=observed,
        require_full_coverage=True,
    )
    assert strict.status == "fail"
    assert strict.complete is False
    assert removed.canonical_key in strict.missing_mappings

    partial = reconcile_godley_payload(
        canonical,
        template_id="coverage-template",
        template_sha256=TEMPLATE_HASH,
        mappings=mappings,
        observed_values=observed,
        require_full_coverage=False,
    )
    assert partial.status == "partial"
    assert partial.complete is False
    assert removed.canonical_key in partial.missing_mappings


def test_duplicate_mapping_and_missing_required_observation_are_rejected_or_failed():
    canonical = canonical_payload()
    mappings, observed = full_nonzero_mapping(canonical)
    with pytest.raises(ReconciliationContractError):
        reconcile_godley_payload(
            canonical,
            template_id="duplicate-template",
            template_sha256=TEMPLATE_HASH,
            mappings=[mappings[0], mappings[0]],
            observed_values=observed,
        )

    observed.pop(mappings[0].variable_id)
    report = reconcile_godley_payload(
        canonical,
        template_id="missing-template",
        template_sha256=TEMPLATE_HASH,
        mappings=mappings,
        observed_values=observed,
    )
    assert report.status == "fail"
    assert mappings[0].variable_id in report.missing_observations


def test_capture_reads_mapped_variables_without_calling_a_setter():
    class ReadOnlyClient:
        def __init__(self):
            self.reads = []

        def get_variable_value(self, variable_id):
            self.reads.append(variable_id)
            return 12.5

        def set_variable_value(self, *_args, **_kwargs):
            raise AssertionError("reconciliation must never call a setter")

    mapping = MinskyGodleyCellMapping(
        kind="stocks", instrument="deposits", sector="households", variable_id=":hh_deposits"
    )
    client = ReadOnlyClient()
    assert capture_minsky_values(client, [mapping]) == {":hh_deposits": 12.5}
    assert client.reads == [":hh_deposits"]


def test_reconciliation_api_accepts_provided_snapshot():
    canonical = canonical_payload()
    mappings, observed = full_nonzero_mapping(canonical)
    response = TestClient(app).post(
        "/api/v1/minsky/reconcile",
        json={
            "canonical": {
                "schema_name": canonical["schema"],
                "tick": canonical["tick"],
                "columns": canonical["columns"],
                "stocks": canonical["stocks"],
                "flows": canonical["flows"],
            },
            "template_id": "api-template-v1",
            "template_sha256": TEMPLATE_HASH,
            "mappings": [
                {
                    "kind": item.kind,
                    "instrument": item.instrument,
                    "sector": item.sector,
                    "variable_id": item.variable_id,
                    "external_multiplier": item.external_multiplier,
                    "required": item.required,
                }
                for item in mappings
            ],
            "source_mode": "provided",
            "observed_values": observed,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pass"
    assert data["accounting_authority"] == "ledger_sfc"
    assert data["external_can_mutate_ledger"] is False


# ---------------------------------------------------------------------------
# Template-path hardening tests (sandbox)
# ---------------------------------------------------------------------------

def _api_mapping_dicts(mappings):
    """Convert MinskyGodleyCellMapping list to JSON-ready dicts for the API."""
    return [
        {
            "kind": m.kind,
            "instrument": m.instrument,
            "sector": m.sector,
            "variable_id": m.variable_id,
            "external_multiplier": m.external_multiplier,
            "required": m.required,
        }
        for m in mappings
    ]


def _api_canonical_dict(canonical):
    return {
        "schema_name": canonical["schema"],
        "tick": canonical["tick"],
        "columns": canonical["columns"],
        "stocks": canonical["stocks"],
        "flows": canonical["flows"],
    }


def test_live_mode_rejected_when_template_dir_not_configured(monkeypatch):
    """live source_mode must fail with actionable error when env var is unset."""
    monkeypatch.delenv("ECONOMY_LAB_MINSKY_TEMPLATE_DIR", raising=False)
    canonical = canonical_payload()
    mappings, _ = full_nonzero_mapping(canonical)
    response = TestClient(app).post(
        "/api/v1/minsky/reconcile",
        json={
            "canonical": _api_canonical_dict(canonical),
            "template_id": "env-test",
            "template_sha256": TEMPLATE_HASH,
            "mappings": _api_mapping_dicts(mappings),
            "source_mode": "live",
            "model_path": "templates/model.mky",
        },
    )
    assert response.status_code == 422
    assert "ECONOMY_LAB_MINSKY_TEMPLATE_DIR" in response.json()["detail"]


def test_live_mode_rejects_path_outside_template_dir(monkeypatch, tmp_path):
    """model_path outside the trusted directory must be rejected."""
    trusted_dir = tmp_path / "trusted"
    trusted_dir.mkdir()
    untrusted_dir = tmp_path / "untrusted"
    untrusted_dir.mkdir()

    rogue_model = untrusted_dir / "rogue.mky"
    rogue_content = b"fake-mky-content"
    rogue_model.write_bytes(rogue_content)
    rogue_hash = hashlib.sha256(rogue_content).hexdigest()

    monkeypatch.setenv("ECONOMY_LAB_MINSKY_TEMPLATE_DIR", str(trusted_dir))

    canonical = canonical_payload()
    mappings, _ = full_nonzero_mapping(canonical)
    response = TestClient(app).post(
        "/api/v1/minsky/reconcile",
        json={
            "canonical": _api_canonical_dict(canonical),
            "template_id": "rogue-template",
            "template_sha256": rogue_hash,
            "mappings": _api_mapping_dicts(mappings),
            "source_mode": "live",
            "model_path": str(rogue_model),
        },
    )
    assert response.status_code == 422
    assert "ECONOMY_LAB_MINSKY_TEMPLATE_DIR" in response.json()["detail"]


def test_live_mode_allows_trusted_path_to_reach_hash_verification(monkeypatch, tmp_path):
    """model_path inside the trusted directory passes containment and reaches SHA-256 check."""
    trusted_dir = tmp_path / "trusted"
    trusted_dir.mkdir()

    valid_model = trusted_dir / "valid.mky"
    valid_model.write_bytes(b"dummy-model")

    monkeypatch.setenv("ECONOMY_LAB_MINSKY_TEMPLATE_DIR", str(trusted_dir))

    canonical = canonical_payload()
    mappings, _ = full_nonzero_mapping(canonical)
    response = TestClient(app).post(
        "/api/v1/minsky/reconcile",
        json={
            "canonical": _api_canonical_dict(canonical),
            "template_id": "valid-template",
            "template_sha256": TEMPLATE_HASH,
            "mappings": _api_mapping_dicts(mappings),
            "source_mode": "live",
            "model_path": str(valid_model),
        },
    )
    # Should pass containment, then fail at SHA-256 mismatch (not containment error)
    assert response.status_code == 422
    assert "SHA-256" in response.json()["detail"]


def test_live_mode_rejects_traversal_attack(monkeypatch, tmp_path):
    """Paths using .. to escape the trusted directory must be rejected."""
    trusted_dir = tmp_path / "trusted"
    trusted_dir.mkdir()

    escape_dir = tmp_path / "escape"
    escape_dir.mkdir()
    escaped_model = escape_dir / "escaped.mky"
    escaped_model.write_bytes(b"escaped-content")

    monkeypatch.setenv("ECONOMY_LAB_MINSKY_TEMPLATE_DIR", str(trusted_dir))

    canonical = canonical_payload()
    mappings, _ = full_nonzero_mapping(canonical)
    traversal_path = str(trusted_dir / ".." / "escape" / "escaped.mky")
    response = TestClient(app).post(
        "/api/v1/minsky/reconcile",
        json={
            "canonical": _api_canonical_dict(canonical),
            "template_id": "traversal-template",
            "template_sha256": hashlib.sha256(b"escaped-content").hexdigest(),
            "mappings": _api_mapping_dicts(mappings),
            "source_mode": "live",
            "model_path": traversal_path,
        },
    )
    assert response.status_code == 422
    assert "ECONOMY_LAB_MINSKY_TEMPLATE_DIR" in response.json()["detail"]


def test_provided_mode_works_without_template_dir_env(monkeypatch):
    """provided source_mode must not require ECONOMY_LAB_MINSKY_TEMPLATE_DIR."""
    monkeypatch.delenv("ECONOMY_LAB_MINSKY_TEMPLATE_DIR", raising=False)
    canonical = canonical_payload()
    mappings, observed = full_nonzero_mapping(canonical)
    response = TestClient(app).post(
        "/api/v1/minsky/reconcile",
        json={
            "canonical": _api_canonical_dict(canonical),
            "template_id": "provided-no-env",
            "template_sha256": TEMPLATE_HASH,
            "mappings": _api_mapping_dicts(mappings),
            "source_mode": "provided",
            "observed_values": observed,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pass"


# ---------------------------------------------------------------------------
# Schema hardening tests (extra="forbid", allow_inf_nan)
# ---------------------------------------------------------------------------

def test_data_provenance_record_rejects_extra_fields():
    """DataProvenanceRecord must reject unknown fields."""
    with pytest.raises(ValidationError):
        DataProvenanceRecord(
            source_id="bcb_sgs",
            series_id="433",
            content_hash="a" * 64,
            rogue_field="unexpected",
        )


def test_economic_observation_rejects_nan_and_inf():
    """EconomicObservation must reject NaN and Inf values."""
    with pytest.raises(ValidationError):
        EconomicObservation(date="2024-01-01", value=float("nan"))
    with pytest.raises(ValidationError):
        EconomicObservation(date="2024-01-01", value=float("inf"))
    with pytest.raises(ValidationError):
        EconomicObservation(date="2024-01-01", value=float("-inf"))


def test_economic_observation_rejects_extra_fields():
    """EconomicObservation must reject unknown fields."""
    with pytest.raises(ValidationError):
        EconomicObservation(date="2024-01-01", value=1.0, extra_field="nope")


def test_schema_live_mode_requires_model_path():
    """Schema must reject live mode without model_path."""
    with pytest.raises(ValidationError, match="model_path"):
        MinskyReconciliationRequest(
            canonical=MinskyExchangeResponse(
                schema_name="test", tick=1, columns=[], stocks=[], flows=[]
            ),
            template_id="test",
            template_sha256=TEMPLATE_HASH,
            mappings=[
                MinskyGodleyCellMappingSpec(
                    kind="stocks", instrument="deposits", sector="households",
                    variable_id=":hh_deposits",
                )
            ],
            source_mode="live",
            model_path=None,
        )


def test_schema_rejects_non_mky_extension():
    """Schema must reject model_path without .mky extension."""
    with pytest.raises(ValidationError, match="mky"):
        MinskyReconciliationRequest(
            canonical=MinskyExchangeResponse(
                schema_name="test", tick=1, columns=[], stocks=[], flows=[]
            ),
            template_id="test",
            template_sha256=TEMPLATE_HASH,
            mappings=[
                MinskyGodleyCellMappingSpec(
                    kind="stocks", instrument="deposits", sector="households",
                    variable_id=":hh_deposits",
                )
            ],
            source_mode="provided",
            observed_values={":hh_deposits": 1.0},
            model_path="template.zip",
        )
