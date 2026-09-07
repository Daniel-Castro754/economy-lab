"""Canonical manifests and hashes for reproducible Economy Lab runs."""
from __future__ import annotations

from importlib import metadata
import hashlib
import json
import platform
from typing import Any, Mapping

from pydantic import BaseModel

from economy_lab import __version__
from economy_lab.core.schemas import RunManifest, ScenarioSpec, SimulationResult


MANIFEST_SCHEMA = "economy-lab-run-manifest-v1.0"
RUNTIME_PACKAGES = (
    "numpy",
    "scipy",
    "mesa",
    "econ-ark",
)


def canonical_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def runtime_versions() -> dict[str, str]:
    versions = {
        "economy_lab": __version__,
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "operating_system": platform.system(),
        "machine": platform.machine(),
    }
    for package in RUNTIME_PACKAGES:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = "unavailable"
    return versions


def profile_manifest_entries(
    scenario: ScenarioSpec,
    resolved_profiles: Mapping[str, Mapping[str, Any] | None],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for kind, profile_id in sorted(scenario.applied_profiles.items()):
        profile = resolved_profiles.get(profile_id)
        if profile is None:
            entries.append(
                {"kind": kind, "profile_id": profile_id, "resolved": False}
            )
            continue
        entries.append(
            {
                "kind": kind,
                "profile_id": profile_id,
                "resolved": True,
                "module_id": profile.get("module_id"),
                "compatibility": profile.get("compatibility"),
                "updated_at": profile.get("updated_at"),
                "payload_hash": stable_hash(profile.get("payload", {})),
                "scenario_patch_hash": stable_hash(profile.get("scenario_patch", {})),
            }
        )
    return entries


def build_run_manifest(
    *,
    scenario: ScenarioSpec,
    result: SimulationResult,
    engine_version: str,
    resolved_profiles: Mapping[str, Mapping[str, Any] | None] | None = None,
    versions: Mapping[str, str] | None = None,
) -> tuple[RunManifest, str]:
    profile_entries = profile_manifest_entries(scenario, resolved_profiles or {})
    runtime = dict(versions or runtime_versions())
    runtime["economy_lab"] = engine_version
    runtime_warnings: list[str] = []
    if scenario.macro_engine == "dynare":
        from economy_lab.engines.dynare_adapter import dynare_status

        status = dynare_status()
        runtime["dynare"] = status.dynare_version_hint or "configured-version-unknown"
        runtime["octave_executable"] = status.octave_executable or "unavailable"
        if status.dynare_version_hint is None:
            runtime_warnings.append(
                "Dynare was active but its exact version could not be inferred from the configured path."
            )
    scenario_payload = scenario.model_dump(mode="json")
    result_payload = result.model_dump(mode="json")
    provenance = [
        item.model_dump(mode="json")
        for item in sorted(
            scenario.data_provenance,
            key=lambda item: (item.source_id, item.series_id, item.content_hash),
        )
    ]
    experiment_payload = {
        "schema_name": MANIFEST_SCHEMA,
        "scenario": scenario_payload,
        "runtime_versions": runtime,
        "profiles": profile_entries,
        "data_provenance": provenance,
    }
    warnings = runtime_warnings + [
        f"Profile {item['profile_id']} ({item['kind']}) was not available for hashing."
        for item in profile_entries
        if not item["resolved"]
    ]
    manifest = RunManifest(
        economy_lab_version=engine_version,
        scenario_hash=stable_hash(scenario_payload),
        result_hash=stable_hash(result_payload),
        experiment_hash=stable_hash(experiment_payload),
        seed=scenario.seed,
        runtime_versions=runtime,
        engine_trace={
            key: str(value)
            for key, value in result.engines.model_dump(mode="json").items()
        },
        profiles=profile_entries,
        data_provenance=provenance,
        warnings=warnings,
    )
    return manifest, stable_hash(manifest)


def runtime_differences(
    expected: Mapping[str, str], actual: Mapping[str, str]
) -> dict[str, dict[str, str | None]]:
    differences: dict[str, dict[str, str | None]] = {}
    for key in sorted(set(expected) | set(actual)):
        if expected.get(key) != actual.get(key):
            differences[key] = {
                "expected": expected.get(key),
                "actual": actual.get(key),
            }
    return differences
