"""Read-only reconciliation between Minsky Godley cells and Ledger/SFC.

The Economy Lab ledger remains the accounting authority.  This module only
compares values read from a known Minsky ``.mky`` template with the canonical
Godley export; it never posts transactions or writes external balances back to
the ledger.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from math import isfinite
from typing import Iterable, Mapping

from economy_lab.finance.sfc import SECTORS


RECONCILIATION_SCHEMA = "economy-lab-minsky-reconciliation-v1.0"
GODLEY_KINDS = ("stocks", "flows")


class ReconciliationContractError(ValueError):
    """Raised when a template mapping is ambiguous or invalid."""


@dataclass(frozen=True, slots=True)
class MinskyGodleyCellMapping:
    kind: str
    instrument: str
    sector: str
    variable_id: str
    external_multiplier: float = 1.0
    required: bool = True

    @property
    def canonical_key(self) -> str:
        return f"{self.kind}.{self.instrument}.{self.sector}"

    def validate(self) -> None:
        if self.kind not in GODLEY_KINDS:
            raise ReconciliationContractError(f"Unsupported Godley kind: {self.kind!r}")
        if self.sector not in SECTORS:
            raise ReconciliationContractError(f"Unsupported Godley sector: {self.sector!r}")
        if not self.instrument.strip():
            raise ReconciliationContractError("Godley mapping instrument cannot be empty")
        if not self.variable_id.strip():
            raise ReconciliationContractError("Minsky variable_id cannot be empty")
        if not isfinite(self.external_multiplier) or self.external_multiplier == 0:
            raise ReconciliationContractError("external_multiplier must be finite and non-zero")


@dataclass(frozen=True, slots=True)
class MinskyReconciliationCell:
    kind: str
    instrument: str
    sector: str
    variable_id: str
    expected: float
    observed: float
    normalized_observed: float
    absolute_error: float
    relative_error: float
    within_tolerance: bool


@dataclass(frozen=True, slots=True)
class MinskyReconciliationReport:
    schema_name: str
    report_id: str
    status: str
    template_id: str
    template_sha256: str
    tick: int
    canonical_hash: str
    mapping_hash: str
    observed_hash: str
    accounting_authority: str
    read_only: bool
    external_can_mutate_ledger: bool
    complete: bool
    full_coverage_required: bool
    canonical_stocks_balanced: bool
    canonical_flows_balanced: bool
    compared_cells: int
    drift_count: int
    missing_mappings: tuple[str, ...]
    missing_observations: tuple[str, ...]
    extra_observations: tuple[str, ...]
    maximum_absolute_error: float
    maximum_relative_error: float
    cells: tuple[MinskyReconciliationCell, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["cells"] = [asdict(item) for item in self.cells]
        payload["missing_mappings"] = list(self.missing_mappings)
        payload["missing_observations"] = list(self.missing_observations)
        payload["extra_observations"] = list(self.extra_observations)
        payload["warnings"] = list(self.warnings)
        return payload


def _stable_hash(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()


def _normalized_payload(canonical: Mapping[str, object]) -> dict[str, object]:
    schema = canonical.get("schema", canonical.get("schema_name"))
    return {
        "schema": str(schema),
        "tick": int(canonical["tick"]),
        "columns": list(canonical["columns"]),
        "stocks": list(canonical["stocks"]),
        "flows": list(canonical["flows"]),
    }


def _flatten_canonical(payload: Mapping[str, object]) -> dict[str, float]:
    flattened: dict[str, float] = {}
    for kind in GODLEY_KINDS:
        rows = payload.get(kind)
        if not isinstance(rows, list):
            raise ReconciliationContractError(f"Canonical payload field {kind!r} must be a list")
        for raw_row in rows:
            if not isinstance(raw_row, Mapping):
                raise ReconciliationContractError(f"Canonical {kind} row must be an object")
            instrument = str(raw_row.get("instrument", "")).strip()
            if not instrument:
                raise ReconciliationContractError(f"Canonical {kind} row has no instrument")
            for sector in SECTORS:
                value = float(raw_row.get(sector, 0.0))
                if not isfinite(value):
                    raise ReconciliationContractError(
                        f"Canonical value is not finite: {kind}.{instrument}.{sector}"
                    )
                flattened[f"{kind}.{instrument}.{sector}"] = value
    return flattened


def _matrix_balanced(payload: Mapping[str, object], kind: str, tolerance: float) -> bool:
    rows = payload.get(kind)
    if not isinstance(rows, list):
        return False
    for row in rows:
        if not isinstance(row, Mapping):
            return False
        total = sum(float(row.get(sector, 0.0)) for sector in SECTORS)
        if abs(total) > tolerance:
            return False
    return True


def validate_reconciliation_mapping(
    mappings: Iterable[MinskyGodleyCellMapping],
) -> tuple[MinskyGodleyCellMapping, ...]:
    validated = tuple(mappings)
    if not validated:
        raise ReconciliationContractError("At least one Godley cell mapping is required")

    canonical_keys: set[str] = set()
    variable_ids: set[str] = set()
    for item in validated:
        item.validate()
        if item.canonical_key in canonical_keys:
            raise ReconciliationContractError(
                f"Duplicate canonical Godley mapping: {item.canonical_key}"
            )
        if item.variable_id in variable_ids:
            raise ReconciliationContractError(
                f"Minsky variable_id is mapped more than once: {item.variable_id}"
            )
        canonical_keys.add(item.canonical_key)
        variable_ids.add(item.variable_id)
    return tuple(sorted(validated, key=lambda item: item.canonical_key))


def capture_minsky_values(client: object, mappings: Iterable[MinskyGodleyCellMapping]) -> dict[str, float]:
    """Read mapped values from Minsky without using any setter method."""

    return {
        item.variable_id: float(client.get_variable_value(item.variable_id))
        for item in validate_reconciliation_mapping(mappings)
    }


def reconcile_godley_payload(
    canonical: Mapping[str, object],
    *,
    template_id: str,
    template_sha256: str,
    mappings: Iterable[MinskyGodleyCellMapping],
    observed_values: Mapping[str, float],
    absolute_tolerance: float = 1e-6,
    relative_tolerance: float = 1e-6,
    require_full_coverage: bool = True,
) -> MinskyReconciliationReport:
    """Compare a Minsky snapshot with canonical Ledger/SFC Godley cells.

    ``external_multiplier`` converts the external sign/unit into the Economy
    Lab convention before comparison.  Tolerance uses the standard combined
    rule ``abs_error <= abs_tol + rel_tol * max(abs(expected), abs(actual))``.
    """

    if not template_id.strip():
        raise ReconciliationContractError("template_id cannot be empty")
    digest = template_sha256.strip().lower()
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ReconciliationContractError("template_sha256 must be a 64-character SHA-256 hex digest")
    if not isfinite(absolute_tolerance) or absolute_tolerance < 0:
        raise ReconciliationContractError("absolute_tolerance must be finite and non-negative")
    if not isfinite(relative_tolerance) or relative_tolerance < 0:
        raise ReconciliationContractError("relative_tolerance must be finite and non-negative")

    normalized = _normalized_payload(canonical)
    if normalized["schema"] != "economy-lab-godley-v1.0":
        raise ReconciliationContractError(f"Unsupported canonical schema: {normalized['schema']!r}")
    if tuple(normalized["columns"]) != tuple(SECTORS):
        raise ReconciliationContractError("Canonical columns do not match the frozen SFC sectors")

    validated_mapping = validate_reconciliation_mapping(mappings)
    canonical_cells = _flatten_canonical(normalized)
    mapping_by_key = {item.canonical_key: item for item in validated_mapping}
    nonzero_keys = {
        key for key, value in canonical_cells.items() if abs(value) > absolute_tolerance
    }
    missing_mappings = tuple(sorted(nonzero_keys - set(mapping_by_key)))

    observations: dict[str, float] = {}
    for key, raw_value in observed_values.items():
        value = float(raw_value)
        if not isfinite(value):
            raise ReconciliationContractError(f"Observed Minsky value is not finite: {key}")
        observations[str(key)] = value

    required_ids = {
        item.variable_id
        for item in validated_mapping
        if item.required or abs(canonical_cells.get(item.canonical_key, 0.0)) > absolute_tolerance
    }
    missing_observations = tuple(sorted(required_ids - set(observations)))
    extra_observations = tuple(sorted(set(observations) - {item.variable_id for item in validated_mapping}))

    cells: list[MinskyReconciliationCell] = []
    for item in validated_mapping:
        if item.variable_id not in observations:
            continue
        expected = canonical_cells.get(item.canonical_key, 0.0)
        observed = observations[item.variable_id]
        normalized_observed = observed * item.external_multiplier
        absolute_error = abs(normalized_observed - expected)
        denominator = max(abs(expected), abs(normalized_observed))
        relative_error = absolute_error / denominator if denominator > 0 else 0.0
        allowed_error = absolute_tolerance + relative_tolerance * denominator
        cells.append(
            MinskyReconciliationCell(
                kind=item.kind,
                instrument=item.instrument,
                sector=item.sector,
                variable_id=item.variable_id,
                expected=expected,
                observed=observed,
                normalized_observed=normalized_observed,
                absolute_error=absolute_error,
                relative_error=relative_error,
                within_tolerance=absolute_error <= allowed_error,
            )
        )

    canonical_stocks_balanced = _matrix_balanced(normalized, "stocks", absolute_tolerance)
    canonical_flows_balanced = _matrix_balanced(normalized, "flows", absolute_tolerance)
    drift_count = sum(not item.within_tolerance for item in cells)
    structurally_valid = (
        not missing_observations
        and canonical_stocks_balanced
        and canonical_flows_balanced
    )
    complete = structurally_valid and not missing_mappings

    if structurally_valid and drift_count == 0 and not missing_mappings:
        status = "pass"
    elif structurally_valid and drift_count == 0 and missing_mappings and not require_full_coverage:
        status = "partial"
    else:
        status = "fail"

    warnings = [
        "Read-only reconciliation: Ledger/SFC remains the sole accounting authority.",
        "External Minsky values are evidence only and cannot create or overwrite ledger balances.",
    ]
    if missing_mappings and not require_full_coverage:
        warnings.append("The report is partial because not every non-zero canonical Godley cell is mapped.")
    if extra_observations:
        warnings.append("Unmapped observed variables were ignored and recorded as extra observations.")

    mapping_payload = {
        "template_id": template_id,
        "template_sha256": digest,
        "mappings": [asdict(item) for item in validated_mapping],
    }
    canonical_hash = _stable_hash(normalized)
    mapping_hash = _stable_hash(mapping_payload)
    observed_hash = _stable_hash(dict(sorted(observations.items())))
    identity_payload = {
        "schema": RECONCILIATION_SCHEMA,
        "canonical_hash": canonical_hash,
        "mapping_hash": mapping_hash,
        "observed_hash": observed_hash,
        "tolerances": [absolute_tolerance, relative_tolerance],
        "full_coverage": require_full_coverage,
    }
    report_digest = _stable_hash(identity_payload)

    return MinskyReconciliationReport(
        schema_name=RECONCILIATION_SCHEMA,
        report_id=f"minsky-reconciliation-{report_digest[:16]}",
        status=status,
        template_id=template_id,
        template_sha256=digest,
        tick=int(normalized["tick"]),
        canonical_hash=canonical_hash,
        mapping_hash=mapping_hash,
        observed_hash=observed_hash,
        accounting_authority="ledger_sfc",
        read_only=True,
        external_can_mutate_ledger=False,
        complete=complete,
        full_coverage_required=require_full_coverage,
        canonical_stocks_balanced=canonical_stocks_balanced,
        canonical_flows_balanced=canonical_flows_balanced,
        compared_cells=len(cells),
        drift_count=drift_count,
        missing_mappings=missing_mappings,
        missing_observations=missing_observations,
        extra_observations=extra_observations,
        maximum_absolute_error=max((item.absolute_error for item in cells), default=0.0),
        maximum_relative_error=max((item.relative_error for item in cells), default=0.0),
        cells=tuple(cells),
        warnings=tuple(warnings),
    )
