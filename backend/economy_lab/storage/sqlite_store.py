from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from economy_lab.core.schemas import ScenarioSpec, SimulationResult
from economy_lab.core.reproducibility import build_run_manifest

SCHEMA_VERSION = 5


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_database_path() -> Path:
    explicit = os.getenv("ECONOMY_LAB_DB_PATH")
    if explicit:
        return Path(explicit).expanduser().resolve()

    data_dir = os.getenv("ECONOMY_LAB_DATA_DIR")
    if data_dir:
        root = Path(data_dir).expanduser().resolve()
    else:
        root = Path.home() / ".economy-lab"
    return root / "economy-lab.sqlite3"


class ProjectStore:
    """SQLite persistence for projects and immutable simulation runs.

    Connections are short-lived so FastAPI worker threads do not share sqlite
    connection objects. The database uses WAL and foreign-key enforcement.
    """

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path).expanduser().resolve() if path else resolve_database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            version = int(db.execute("PRAGMA user_version").fetchone()[0])
            if version > SCHEMA_VERSION:
                raise RuntimeError(
                    f"Database schema {version} is newer than supported {SCHEMA_VERSION}"
                )
            if version == 0:
                db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS projects (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        scenario_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        last_run_id TEXT NULL
                    );

                    CREATE TABLE IF NOT EXISTS runs (
                        id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        scenario_json TEXT NOT NULL,
                        result_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        duration_ms REAL NOT NULL DEFAULT 0,
                        engine_version TEXT NOT NULL,
                        final_gdp_index REAL NOT NULL,
                        final_inflation REAL NOT NULL,
                        final_unemployment REAL NOT NULL,
                        ledger_balanced INTEGER NOT NULL,
                        godley_stocks_balanced INTEGER NOT NULL,
                        godley_flows_balanced INTEGER NOT NULL,
                        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_runs_project_created
                    ON runs(project_id, created_at DESC);
                    """
                )
                version = 1
                db.execute("PRAGMA user_version = 1")

            if version < 2:
                db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS experiments (
                        id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        axis TEXT NOT NULL,
                        values_json TEXT NOT NULL,
                        repetitions INTEGER NOT NULL,
                        total_runs INTEGER NOT NULL,
                        duration_ms REAL NOT NULL,
                        engine_version TEXT NOT NULL,
                        result_json TEXT NOT NULL,
                        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_experiments_project_created
                    ON experiments(project_id, created_at DESC);
                    """
                )
                version = 2
                db.execute("PRAGMA user_version = 2")

            if version < 3:
                db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS profiles (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        kind TEXT NOT NULL,
                        module_id TEXT NOT NULL,
                        compatibility TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        scenario_patch_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_profiles_kind_updated
                    ON profiles(kind, updated_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_profiles_module_updated
                    ON profiles(module_id, updated_at DESC);
                    """
                )
                version = 3
                db.execute("PRAGMA user_version = 3")

            if version < 4:
                db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS jobs (
                        id TEXT PRIMARY KEY,
                        project_id TEXT NULL,
                        kind TEXT NOT NULL,
                        status TEXT NOT NULL,
                        scenario_json TEXT NOT NULL,
                        result_json TEXT NULL,
                        run_id TEXT NULL,
                        save_scenario INTEGER NOT NULL DEFAULT 1,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        started_at TEXT NULL,
                        finished_at TEXT NULL,
                        progress REAL NOT NULL DEFAULT 0,
                        current_step INTEGER NOT NULL DEFAULT 0,
                        total_steps INTEGER NOT NULL DEFAULT 1,
                        stage TEXT NOT NULL DEFAULT 'queued',
                        timeout_seconds REAL NOT NULL,
                        cancellation_requested INTEGER NOT NULL DEFAULT 0,
                        error_code TEXT NULL,
                        error_message TEXT NULL,
                        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE SET NULL,
                        FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE SET NULL,
                        CHECK(status IN ('queued', 'running', 'completed', 'failed', 'cancelled'))
                    );

                    CREATE INDEX IF NOT EXISTS idx_jobs_status_created
                    ON jobs(status, created_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_jobs_project_created
                    ON jobs(project_id, created_at DESC);
                    """
                )
                version = 4
                db.execute("PRAGMA user_version = 4")

            if version < 5:
                db.executescript(
                    """
                    ALTER TABLE runs ADD COLUMN manifest_json TEXT NULL;
                    ALTER TABLE runs ADD COLUMN manifest_hash TEXT NULL;
                    ALTER TABLE runs ADD COLUMN experiment_hash TEXT NULL;
                    ALTER TABLE runs ADD COLUMN replay_of_run_id TEXT NULL;

                    CREATE INDEX IF NOT EXISTS idx_runs_manifest_hash
                    ON runs(manifest_hash);
                    CREATE INDEX IF NOT EXISTS idx_runs_experiment_hash
                    ON runs(experiment_hash);
                    CREATE INDEX IF NOT EXISTS idx_runs_replay_of
                    ON runs(replay_of_run_id, created_at DESC);
                    """
                )
                version = 5
                db.execute("PRAGMA user_version = 5")

    @staticmethod
    def _dump_model(model: Any) -> str:
        if hasattr(model, "model_dump"):
            value = model.model_dump(mode="json")
        else:
            value = model
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    def status(self) -> dict[str, Any]:
        with self._connect() as db:
            projects = int(db.execute("SELECT COUNT(*) FROM projects").fetchone()[0])
            runs = int(db.execute("SELECT COUNT(*) FROM runs").fetchone()[0])
            experiments = int(db.execute("SELECT COUNT(*) FROM experiments").fetchone()[0])
            profiles = int(db.execute("SELECT COUNT(*) FROM profiles").fetchone()[0])
            jobs = int(db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])
        return {
            "database_path": str(self.path),
            "schema_version": SCHEMA_VERSION,
            "projects": projects,
            "runs": runs,
            "experiments": experiments,
            "profiles": profiles,
            "jobs": jobs,
        }

    def create_job(
        self,
        *,
        scenario: ScenarioSpec,
        project_id: str | None = None,
        save_scenario: bool = True,
        timeout_seconds: float = 300.0,
        kind: str = "simulation",
    ) -> dict[str, Any]:
        if project_id is not None and self.get_project(project_id) is None:
            raise KeyError(project_id)
        job_id = str(uuid4())
        timestamp = utc_now()
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO jobs(
                    id, project_id, kind, status, scenario_json, save_scenario,
                    created_at, updated_at, progress, current_step, total_steps,
                    stage, timeout_seconds, cancellation_requested
                ) VALUES (?, ?, ?, 'queued', ?, ?, ?, ?, 0, 0, ?, 'queued', ?, 0)
                """,
                (
                    job_id,
                    project_id,
                    kind,
                    self._dump_model(scenario),
                    int(save_scenario),
                    timestamp,
                    timestamp,
                    max(1, scenario.months),
                    float(timeout_seconds),
                ),
            )
        item = self.get_job(job_id)
        assert item is not None
        return item

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return self._job_row(row, include_payload=True)

    def list_jobs(
        self,
        *,
        status: str | None = None,
        project_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        values: list[Any] = []
        if status:
            clauses.append("status = ?")
            values.append(status)
        if project_id:
            clauses.append("project_id = ?")
            values.append(project_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        values.append(max(1, min(int(limit), 200)))
        with self._connect() as db:
            rows = db.execute(
                f"SELECT * FROM jobs{where} ORDER BY created_at DESC, rowid DESC LIMIT ?",
                values,
            ).fetchall()
        return [self._job_row(row, include_payload=False) for row in rows]

    def start_job(self, job_id: str) -> bool:
        timestamp = utc_now()
        with self._connect() as db:
            cursor = db.execute(
                """
                UPDATE jobs
                SET status = 'running', stage = 'starting', started_at = ?, updated_at = ?
                WHERE id = ? AND status = 'queued' AND cancellation_requested = 0
                """,
                (timestamp, timestamp, job_id),
            )
            return cursor.rowcount > 0

    def recover_interrupted_jobs(self) -> int:
        """Mark work left running by a terminated process as failed."""

        timestamp = utc_now()
        with self._connect() as db:
            cursor = db.execute(
                """
                UPDATE jobs
                SET status = 'failed', stage = 'failed', error_code = 'worker_interrupted',
                    error_message = 'The worker process stopped before the job finished',
                    finished_at = ?, updated_at = ?
                WHERE status = 'running'
                """,
                (timestamp, timestamp),
            )
            return cursor.rowcount

    def queued_job_ids(self) -> list[str]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT id FROM jobs WHERE status = 'queued' ORDER BY created_at, rowid"
            ).fetchall()
        return [str(row["id"]) for row in rows]

    def update_job_progress(
        self,
        job_id: str,
        *,
        stage: str,
        progress: float,
        current_step: int,
        total_steps: int,
    ) -> bool:
        with self._connect() as db:
            cursor = db.execute(
                """
                UPDATE jobs
                SET stage = ?, progress = MAX(progress, ?), current_step = ?,
                    total_steps = ?, updated_at = ?
                WHERE id = ? AND status = 'running'
                """,
                (
                    stage,
                    max(0.0, min(100.0, float(progress))),
                    max(0, int(current_step)),
                    max(1, int(total_steps)),
                    utc_now(),
                    job_id,
                ),
            )
            return cursor.rowcount > 0

    def cancellation_requested(self, job_id: str) -> bool:
        with self._connect() as db:
            row = db.execute(
                "SELECT cancellation_requested FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return bool(row and row["cancellation_requested"])

    def request_job_cancel(self, job_id: str) -> dict[str, Any] | None:
        timestamp = utc_now()
        with self._connect() as db:
            db.execute(
                """
                UPDATE jobs
                SET cancellation_requested = 1,
                    status = CASE WHEN status = 'queued' THEN 'cancelled' ELSE status END,
                    stage = CASE WHEN status = 'queued' THEN 'cancelled' ELSE 'cancelling' END,
                    finished_at = CASE WHEN status = 'queued' THEN ? ELSE finished_at END,
                    updated_at = ?
                WHERE id = ? AND status IN ('queued', 'running')
                """,
                (timestamp, timestamp, job_id),
            )
        return self.get_job(job_id)

    def complete_job(
        self,
        job_id: str,
        *,
        result: SimulationResult,
        run_id: str | None = None,
    ) -> bool:
        timestamp = utc_now()
        with self._connect() as db:
            cursor = db.execute(
                """
                UPDATE jobs
                SET status = 'completed', result_json = ?, run_id = ?, progress = 100,
                    stage = 'completed', current_step = total_steps, finished_at = ?, updated_at = ?
                WHERE id = ? AND status = 'running' AND cancellation_requested = 0
                """,
                (self._dump_model(result), run_id, timestamp, timestamp, job_id),
            )
            return cursor.rowcount > 0

    def complete_project_job(
        self,
        job_id: str,
        *,
        project_id: str,
        scenario: ScenarioSpec,
        result: SimulationResult,
        duration_ms: float,
        engine_version: str,
        save_scenario: bool = True,
    ) -> str | None:
        """Atomically save an immutable run and complete its owning job."""

        run_id = str(uuid4())
        timestamp = utc_now()
        summary = result.summary
        manifest, manifest_hash = self._build_manifest(
            scenario=scenario, result=result, engine_version=engine_version
        )
        with self._connect() as db:
            cursor = db.execute(
                """
                UPDATE jobs
                SET status = 'completed', result_json = ?, progress = 100,
                    stage = 'completed', current_step = total_steps,
                    finished_at = ?, updated_at = ?
                WHERE id = ? AND project_id = ? AND status = 'running'
                    AND cancellation_requested = 0
                """,
                (self._dump_model(result), timestamp, timestamp, job_id, project_id),
            )
            if cursor.rowcount == 0:
                return None
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
                    None,
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
            db.execute("UPDATE jobs SET run_id = ? WHERE id = ?", (run_id, job_id))
        return run_id

    def fail_job(self, job_id: str, *, error_code: str, error_message: str) -> bool:
        timestamp = utc_now()
        with self._connect() as db:
            cursor = db.execute(
                """
                UPDATE jobs
                SET status = 'failed', stage = 'failed', error_code = ?, error_message = ?,
                    finished_at = ?, updated_at = ?
                WHERE id = ? AND status IN ('queued', 'running')
                """,
                (error_code, error_message[:2000], timestamp, timestamp, job_id),
            )
            return cursor.rowcount > 0

    def cancel_job(self, job_id: str) -> bool:
        timestamp = utc_now()
        with self._connect() as db:
            cursor = db.execute(
                """
                UPDATE jobs
                SET status = 'cancelled', stage = 'cancelled', cancellation_requested = 1,
                    finished_at = ?, updated_at = ?
                WHERE id = ? AND status IN ('queued', 'running')
                """,
                (timestamp, timestamp, job_id),
            )
            return cursor.rowcount > 0

    @staticmethod
    def _job_row(row: sqlite3.Row, *, include_payload: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": row["id"],
            "project_id": row["project_id"],
            "kind": row["kind"],
            "status": row["status"],
            "run_id": row["run_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "progress": float(row["progress"]),
            "current_step": int(row["current_step"]),
            "total_steps": int(row["total_steps"]),
            "stage": row["stage"],
            "timeout_seconds": float(row["timeout_seconds"]),
            "cancellation_requested": bool(row["cancellation_requested"]),
            "error_code": row["error_code"],
            "error_message": row["error_message"],
        }
        if include_payload:
            payload["scenario"] = json.loads(row["scenario_json"])
            payload["result"] = (
                json.loads(row["result_json"]) if row["result_json"] is not None else None
            )
            payload["save_scenario"] = bool(row["save_scenario"])
        return payload

    def create_project(
        self,
        *,
        name: str,
        description: str,
        scenario: ScenarioSpec,
    ) -> dict[str, Any]:
        project_id = str(uuid4())
        timestamp = utc_now()
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO projects(id, name, description, scenario_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    name.strip(),
                    description.strip(),
                    self._dump_model(scenario),
                    timestamp,
                    timestamp,
                ),
            )
        return self.get_project(project_id)

    def update_project(
        self,
        project_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        scenario: ScenarioSpec | None = None,
    ) -> dict[str, Any] | None:
        current = self.get_project(project_id)
        if current is None:
            return None
        next_name = current["name"] if name is None else name.strip()
        next_description = current["description"] if description is None else description.strip()
        next_scenario = current["scenario"] if scenario is None else scenario
        if not isinstance(next_scenario, ScenarioSpec):
            next_scenario = ScenarioSpec.model_validate(next_scenario)
        with self._connect() as db:
            db.execute(
                """
                UPDATE projects
                SET name = ?, description = ?, scenario_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    next_name,
                    next_description,
                    self._dump_model(next_scenario),
                    utc_now(),
                    project_id,
                ),
            )
        return self.get_project(project_id)

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT p.*,
                       (SELECT COUNT(*) FROM runs r WHERE r.project_id = p.id) AS run_count
                FROM projects p WHERE p.id = ?
                """,
                (project_id,),
            ).fetchone()
        if row is None:
            return None
        return self._project_row(row, include_scenario=True)

    def list_projects(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT p.*,
                       (SELECT COUNT(*) FROM runs r WHERE r.project_id = p.id) AS run_count
                FROM projects p
                ORDER BY p.updated_at DESC, p.created_at DESC
                """
            ).fetchall()
        return [self._project_row(row, include_scenario=False) for row in rows]

    @staticmethod
    def _project_row(row: sqlite3.Row, *, include_scenario: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_run_id": row["last_run_id"],
            "run_count": int(row["run_count"]),
        }
        if include_scenario:
            payload["scenario"] = json.loads(row["scenario_json"])
        return payload

    def delete_project(self, project_id: str) -> bool:
        with self._connect() as db:
            cursor = db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            return cursor.rowcount > 0

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
        with self._connect() as db:
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
        with self._connect() as db:
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
        with self._connect() as db:
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
        with self._connect() as db:
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


    def save_experiment(
        self,
        *,
        project_id: str,
        result: Any,
        engine_version: str,
    ) -> dict[str, Any]:
        if self.get_project(project_id) is None:
            raise KeyError(project_id)
        experiment_id = str(uuid4())
        timestamp = utc_now()
        payload = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO experiments(
                    id, project_id, created_at, axis, values_json, repetitions, total_runs,
                    duration_ms, engine_version, result_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment_id, project_id, timestamp, str(payload["axis"]),
                    json.dumps(payload["values"], separators=(",", ":")), int(payload["repetitions"]),
                    int(payload["total_runs"]), float(payload["duration_ms"]), engine_version,
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                ),
            )
            db.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (timestamp, project_id))
        item = self.get_experiment(experiment_id)
        assert item is not None
        return item

    def list_experiments(self, project_id: str, *, limit: int = 30) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT id, project_id, created_at, axis, values_json, repetitions, total_runs,
                       duration_ms, engine_version
                FROM experiments WHERE project_id = ?
                ORDER BY created_at DESC, rowid DESC LIMIT ?
                """,
                (project_id, limit),
            ).fetchall()
        return [self._experiment_summary(row) for row in rows]

    def get_experiment(self, experiment_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
        if row is None:
            return None
        payload = self._experiment_summary(row)
        payload["result"] = json.loads(row["result_json"])
        return payload

    @staticmethod
    def _experiment_summary(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "project_id": row["project_id"],
            "created_at": row["created_at"],
            "axis": row["axis"],
            "values": [float(v) for v in json.loads(row["values_json"])],
            "repetitions": int(row["repetitions"]),
            "total_runs": int(row["total_runs"]),
            "duration_ms": float(row["duration_ms"]),
            "engine_version": row["engine_version"],
        }

    def create_profile(
        self,
        *,
        name: str,
        description: str,
        kind: str,
        module_id: str,
        compatibility: str,
        payload: dict[str, Any],
        scenario_patch: dict[str, Any],
    ) -> dict[str, Any]:
        profile_id = str(uuid4())
        timestamp = utc_now()
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO profiles(
                    id, name, description, kind, module_id, compatibility, payload_json,
                    scenario_patch_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (profile_id, name.strip(), description.strip(), kind, module_id, compatibility,
                 json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                 json.dumps(scenario_patch, ensure_ascii=False, separators=(",", ":")),
                 timestamp, timestamp),
            )
        item = self.get_profile(profile_id)
        assert item is not None
        return item

    def list_profiles(self, *, kind: str | None = None, module_id: str | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        values: list[Any] = []
        if kind:
            clauses.append("kind = ?")
            values.append(kind)
        if module_id:
            clauses.append("module_id = ?")
            values.append(module_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect() as db:
            rows = db.execute(
                "SELECT id, name, description, kind, module_id, compatibility, created_at, updated_at "
                f"FROM profiles{where} ORDER BY updated_at DESC, created_at DESC",
                values,
            ).fetchall()
        return [self._profile_row(row, include_payload=False) for row in rows]

    def get_profile(self, profile_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if row is None:
            return None
        return self._profile_row(row, include_payload=True)

    def delete_profile(self, profile_id: str) -> bool:
        with self._connect() as db:
            cursor = db.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
            return cursor.rowcount > 0

    @staticmethod
    def _profile_row(row: sqlite3.Row, *, include_payload: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": row["id"], "name": row["name"], "description": row["description"],
            "kind": row["kind"], "module_id": row["module_id"], "compatibility": row["compatibility"],
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        }
        if include_payload:
            payload["payload"] = json.loads(row["payload_json"])
            payload["scenario_patch"] = json.loads(row["scenario_patch_json"])
        return payload
