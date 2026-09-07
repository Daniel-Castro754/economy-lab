from __future__ import annotations

import json
import sqlite3
from typing import Any
from uuid import uuid4

from economy_lab.core.reproducibility import build_run_manifest
from economy_lab.core.schemas import ScenarioSpec, SimulationResult
from economy_lab.storage.jobs import utc_now


class RunStoreMixin:
    def save_run(
        self,
        *,
        project_id: str,
        scenario: ScenarioSpec,
        result: SimulationResult,
        duration_ms: float,
        engine_version: str,
        save_scenario: bool = True,
        replay_of_run_id: str | None = None,
    ) -> dict[str, Any]:
        if self.get_project(project_id) is None:
            raise KeyError(project_id)
        run_id = str(uuid4())
        timestamp = utc_now()
        summary = result.summary
        if replay_of_run_id is not None and self.get_run(replay_of_run_id) is None:
            raise KeyError(replay_of_run_id)
        manifest, manifest_hash = self._build_manifest(
            scenario=scenario, result=result, engine_version=engine_version
        )
        with self._session() as db:
            db.execute(
                """
                INSERT INTO runs(
                    id, project_id, scenario_json, result_json, created_at,
                    duration_ms, engine_version, final_gdp_index, final_inflation,
                    final_unemployment, ledger_balanced, godley_stocks_balanced,
                    godley_flows_balanced, manifest_json, manifest_hash,
                    experiment_hash, replay_of_run_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    project_id,
                    self._dump_model(scenario),
                    self._dump_model(result),
                    timestamp,
                    float(duration_ms),
                    engine_version,
                    summary.final_gdp_index,
                    summary.final_inflation,
                    summary.final_unemployment,
                    int(summary.ledger_balanced),
                    int(summary.godley_stocks_balanced),
                    int(summary.godley_flows_balanced),
                    self._dump_model(manifest),
                    manifest_hash,
                    manifest.experiment_hash,
                    replay_of_run_id,
                ),
            )
            if save_scenario:
                db.execute(
                    """
                    UPDATE projects
                    SET scenario_json = ?, updated_at = ?, last_run_id = ?
                    WHERE id = ?
                    """,
                    (self._dump_model(scenario), timestamp, run_id, project_id),
                )
            else:
                db.execute(
                    "UPDATE projects SET updated_at = ?, last_run_id = ? WHERE id = ?",
                    (timestamp, run_id, project_id),
                )
        return self.get_run(run_id)

    def list_runs(self, project_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        with self._session() as db:
            rows = db.execute(
                """
                SELECT id, project_id, created_at, duration_ms, engine_version,
                       final_gdp_index, final_inflation, final_unemployment,
                       ledger_balanced, godley_stocks_balanced, godley_flows_balanced,
                       scenario_json, manifest_hash, experiment_hash, replay_of_run_id
                FROM runs
                WHERE project_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                (project_id, limit),
            ).fetchall()
        return [self._run_summary(row) for row in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._session() as db:
            row = db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        payload = self._run_summary(row)
        payload["scenario"] = json.loads(row["scenario_json"])
        payload["result"] = json.loads(row["result_json"])
        payload["manifest"] = (
            json.loads(row["manifest_json"])
            if "manifest_json" in row.keys() and row["manifest_json"] is not None
            else None
        )
        return payload

    def get_run_manifest(self, run_id: str) -> dict[str, Any] | None:
        with self._session() as db:
            row = db.execute(
                "SELECT manifest_json, manifest_hash FROM runs WHERE id = ?", (run_id,)
            ).fetchone()
        if row is None or row["manifest_json"] is None:
            return None
        return {
            "run_id": run_id,
            "manifest_hash": row["manifest_hash"],
            "manifest": json.loads(row["manifest_json"]),
        }

    @staticmethod
    def _run_summary(row: sqlite3.Row) -> dict[str, Any]:
        scenario_name = row["scenario_name"] if "scenario_name" in row.keys() else None
        if scenario_name is None and "scenario_json" in row.keys():
            scenario_name = json.loads(row["scenario_json"]).get("name", "Scenario")
        return {
            "id": row["id"],
            "project_id": row["project_id"],
            "scenario_name": scenario_name or "Scenario",
            "created_at": row["created_at"],
            "duration_ms": float(row["duration_ms"]),
            "engine_version": row["engine_version"],
            "final_gdp_index": float(row["final_gdp_index"]),
            "final_inflation": float(row["final_inflation"]),
            "final_unemployment": float(row["final_unemployment"]),
            "ledger_balanced": bool(row["ledger_balanced"]),
            "godley_stocks_balanced": bool(row["godley_stocks_balanced"]),
            "godley_flows_balanced": bool(row["godley_flows_balanced"]),
            "manifest_hash": (
                row["manifest_hash"] if "manifest_hash" in row.keys() else None
            ),
            "experiment_hash": (
                row["experiment_hash"] if "experiment_hash" in row.keys() else None
            ),
            "replay_of_run_id": (
                row["replay_of_run_id"] if "replay_of_run_id" in row.keys() else None
            ),
        }

    def _build_manifest(
        self,
        *,
        scenario: ScenarioSpec,
        result: SimulationResult,
        engine_version: str,
    ):
        resolved = {
            profile_id: self.get_profile(profile_id)
            for profile_id in scenario.applied_profiles.values()
        }
        return build_run_manifest(
            scenario=scenario,
            result=result,
            engine_version=engine_version,
            resolved_profiles=resolved,
        )
