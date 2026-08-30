from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from economy_lab.abm.economy_zero import EconomyZeroConfig, EconomyZeroModel
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
