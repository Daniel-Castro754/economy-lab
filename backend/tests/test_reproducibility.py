from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from economy_lab.api import routes
from economy_lab.core.reproducibility import (
    build_run_manifest,
    canonical_json,
    stable_hash,
)
from economy_lab.core.schemas import DataProvenanceRecord, ScenarioSpec
from economy_lab.core.simulation import run_simulation
from economy_lab.main import app
from economy_lab.storage import ProjectStore


def demo_spec(**changes) -> ScenarioSpec:
    values = {
        "name": "Reproducible",
        "mode": "demo",
        "months": 3,
        "households": 120,
        "firms": 8,
        "banks": 2,
        "seed": 77,
    }
    values.update(changes)
    return ScenarioSpec(**values)


def test_canonical_hash_ignores_mapping_order():
    left = {"b": [2, 3], "a": {"y": 2, "x": 1}}
    right = {"a": {"x": 1, "y": 2}, "b": [2, 3]}

    assert canonical_json(left) == canonical_json(right)
    assert stable_hash(left) == stable_hash(right)


def test_manifest_captures_seed_profiles_data_and_result():
    spec = demo_spec(
        applied_profiles={"macro": "profile-1"},
        data_provenance=[
            DataProvenanceRecord(
                source_id="bcb-sgs",
                series_id="433",
                content_hash="a" * 64,
                observation_start="2020-01-01",
                observation_end="2025-12-31",
                frequency="monthly",
                units="percent",
            )
        ],
    )
    result = run_simulation(spec)
    profile = {
        "module_id": "dynare",
        "compatibility": "active",
        "updated_at": "2026-08-30T00:00:00+00:00",
        "payload": {"phi_pi": 1.5},
        "scenario_patch": {"dynare_phi_pi": 1.5},
    }
    manifest, manifest_hash = build_run_manifest(
        scenario=spec,
        result=result,
        engine_version="2.11.0",
        resolved_profiles={"profile-1": profile},
        versions={"economy_lab": "ignored", "python": "3.12.0"},
    )

    assert manifest.seed == 77
    assert manifest.profiles[0].resolved is True
    assert manifest.profiles[0].payload_hash == stable_hash(profile["payload"])
    assert manifest.data_provenance[0].source_id == "bcb-sgs"
    assert manifest.result_hash == stable_hash(result)
    assert manifest_hash == stable_hash(manifest)


def test_experiment_hash_changes_when_seed_or_data_changes():
    base = demo_spec()
    changed_seed = demo_spec(seed=78)
    changed_data = demo_spec(
        data_provenance=[
            DataProvenanceRecord(
                source_id="bcb-sgs", series_id="433", content_hash="b" * 64
            )
        ]
    )
    versions = {"python": "3.12.0"}
    manifests = [
        build_run_manifest(
            scenario=spec,
            result=run_simulation(spec),
            engine_version="2.11.0",
            versions=versions,
        )[0]
        for spec in (base, changed_seed, changed_data)
    ]

    assert len({item.experiment_hash for item in manifests}) == 3


def test_seeded_economy_zero_result_replays_exactly():
    spec = ScenarioSpec(
        name="Economy Zero replay",
        mode="economy_zero",
        months=2,
        households=120,
        firms=8,
        banks=2,
        seed=2026,
    )
    first = run_simulation(spec)
    second = run_simulation(spec)

    assert stable_hash(first) == stable_hash(second)


def test_store_persists_manifest_and_replay_lineage(tmp_path):
    store = ProjectStore(tmp_path / "manifest.sqlite3")
    spec = demo_spec()
    project = store.create_project(name="Manifest", description="", scenario=spec)
    result = run_simulation(spec)
    source = store.save_run(
        project_id=project["id"],
        scenario=spec,
        result=result,
        duration_ms=1,
        engine_version="2.11.0",
    )
    replay = store.save_run(
        project_id=project["id"],
        scenario=spec,
        result=run_simulation(spec),
        duration_ms=1,
        engine_version="2.11.0",
        save_scenario=False,
        replay_of_run_id=source["id"],
    )

    assert source["manifest_hash"] == stable_hash(source["manifest"])
    assert source["manifest"]["result_hash"] == replay["manifest"]["result_hash"]
    assert source["experiment_hash"] == replay["experiment_hash"]
    assert replay["replay_of_run_id"] == source["id"]
    assert store.get_run_manifest(source["id"])["manifest_hash"] == source["manifest_hash"]


def test_v4_run_migrates_without_inventing_manifest(tmp_path):
    path = tmp_path / "legacy-v4.sqlite3"
    spec = demo_spec()
    result = run_simulation(spec)
    with sqlite3.connect(path) as db:
        db.executescript(
            """
            CREATE TABLE projects (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
                scenario_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                last_run_id TEXT NULL
            );
            CREATE TABLE runs (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, scenario_json TEXT NOT NULL,
                result_json TEXT NOT NULL, created_at TEXT NOT NULL, duration_ms REAL NOT NULL,
                engine_version TEXT NOT NULL, final_gdp_index REAL NOT NULL,
                final_inflation REAL NOT NULL, final_unemployment REAL NOT NULL,
                ledger_balanced INTEGER NOT NULL, godley_stocks_balanced INTEGER NOT NULL,
                godley_flows_balanced INTEGER NOT NULL
            );
            CREATE TABLE experiments (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, created_at TEXT NOT NULL,
                axis TEXT NOT NULL, values_json TEXT NOT NULL, repetitions INTEGER NOT NULL,
                total_runs INTEGER NOT NULL, duration_ms REAL NOT NULL,
                engine_version TEXT NOT NULL, result_json TEXT NOT NULL
            );
            CREATE TABLE profiles (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
                kind TEXT NOT NULL, module_id TEXT NOT NULL, compatibility TEXT NOT NULL,
                payload_json TEXT NOT NULL, scenario_patch_json TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE jobs (
                id TEXT PRIMARY KEY, project_id TEXT NULL, kind TEXT NOT NULL, status TEXT NOT NULL,
                scenario_json TEXT NOT NULL, result_json TEXT NULL, run_id TEXT NULL,
                save_scenario INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                started_at TEXT NULL, finished_at TEXT NULL, progress REAL NOT NULL,
                current_step INTEGER NOT NULL, total_steps INTEGER NOT NULL, stage TEXT NOT NULL,
                timeout_seconds REAL NOT NULL, cancellation_requested INTEGER NOT NULL,
                error_code TEXT NULL, error_message TEXT NULL
            );
            """
        )
        now = "2026-08-30T00:00:00+00:00"
        db.execute("INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?)", (
            "p1", "Legacy", "", spec.model_dump_json(), now, now, "r1"
        ))
        summary = result.summary
        db.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
            "r1", "p1", spec.model_dump_json(), result.model_dump_json(), now, 1.0,
            "2.10.0", summary.final_gdp_index, summary.final_inflation,
            summary.final_unemployment, 1, 1, 1
        ))
        db.execute("PRAGMA user_version = 4")

    store = ProjectStore(path)
    assert store.status()["schema_version"] == 5
    assert store.get_run("r1")["manifest"] is None
    assert store.get_run_manifest("r1") is None


def test_replay_api_matches_source_run(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path / "replay-api.sqlite3")
    spec = demo_spec()
    project = store.create_project(name="Replay", description="", scenario=spec)
    source = store.save_run(
        project_id=project["id"], scenario=spec, result=run_simulation(spec),
        duration_ms=1, engine_version="2.13.0"
    )
    monkeypatch.setattr(routes, "_project_store", lambda: store)

    with TestClient(app) as client:
        manifest_response = client.get(f"/api/v1/runs/{source['id']}/manifest")
        replay_response = client.post(f"/api/v1/runs/{source['id']}/replay")

    assert manifest_response.status_code == 200
    assert manifest_response.json()["manifest_hash"] == source["manifest_hash"]
    assert replay_response.status_code == 201
    payload = replay_response.json()
    assert payload["verification"]["status"] == "matched"
    assert payload["verification"]["result_match"] is True
    assert payload["replay_run"]["replay_of_run_id"] == source["id"]


def test_replay_api_reports_diverged_result(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path / "replay-diverged.sqlite3")
    spec = demo_spec()
    project = store.create_project(name="Divergence", description="", scenario=spec)
    source = store.save_run(
        project_id=project["id"], scenario=spec, result=run_simulation(spec),
        duration_ms=1, engine_version="2.11.0"
    )
    original_runner = run_simulation

    def divergent_runner(scenario):
        return original_runner(scenario).model_copy(update={"scenario": "Diverged"})

    monkeypatch.setattr(routes, "_project_store", lambda: store)
    monkeypatch.setattr(routes, "run_simulation", divergent_runner)

    with TestClient(app) as client:
        response = client.post(f"/api/v1/runs/{source['id']}/replay")

    assert response.status_code == 201
    assert response.json()["verification"]["status"] == "diverged"
    assert response.json()["verification"]["result_match"] is False


def test_manifest_api_rejects_tampered_manifest(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path / "manifest-tampered.sqlite3")
    spec = demo_spec()
    project = store.create_project(name="Tamper", description="", scenario=spec)
    source = store.save_run(
        project_id=project["id"], scenario=spec, result=run_simulation(spec),
        duration_ms=1, engine_version="2.11.0"
    )
    with store._connect() as db:
        db.execute(
            "UPDATE runs SET manifest_json = replace(manifest_json, ?, ?) WHERE id = ?",
            (source["manifest"]["scenario_hash"], "0" * 64, source["id"]),
        )
    monkeypatch.setattr(routes, "_project_store", lambda: store)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/runs/{source['id']}/manifest")

    assert response.status_code == 409
    assert response.json()["detail"] == "Stored run manifest hash is invalid"
