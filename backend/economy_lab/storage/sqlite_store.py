from __future__ import annotations

from contextlib import contextmanager
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from economy_lab.core.schemas import ScenarioSpec, SimulationResult
from economy_lab.storage.experiments import ExperimentStoreMixin
from economy_lab.storage.jobs import JobStoreMixin, utc_now
from economy_lab.storage.profiles import ProfileStoreMixin
from economy_lab.storage.projects import ProjectRecordStoreMixin
from economy_lab.storage.runs import RunStoreMixin
from economy_lab.storage.schema import SCHEMA_VERSION, initialize_database


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


class ProjectStore(
    JobStoreMixin,
    ProfileStoreMixin,
    ExperimentStoreMixin,
    ProjectRecordStoreMixin,
    RunStoreMixin,
):
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

    @contextmanager
    def _session(self) -> Iterator[sqlite3.Connection]:
        """Open a connection for one unit of work and always close it.

        ``sqlite3.Connection.__enter__``/``__exit__`` only commit or roll back
        the transaction; they never close the underlying connection/file
        descriptor. Every store method opens a fresh connection per call (so
        FastAPI worker threads never share one), so without an explicit
        ``close()`` here each request/job-progress tick would leak a
        connection for the lifetime of the desktop process.
        """
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        initialize_database(self.path)

    @staticmethod
    def _dump_model(model: Any) -> str:
        if hasattr(model, "model_dump"):
            value = model.model_dump(mode="json")
        else:
            value = model
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    def status(self) -> dict[str, Any]:
        with self._session() as db:
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
        with self._session() as db:
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
