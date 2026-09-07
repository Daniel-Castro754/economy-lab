from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from economy_lab.core.schemas import ScenarioSpec, SimulationResult


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class JobStoreMixin:
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
        with self._session() as db:
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
        with self._session() as db:
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
        with self._session() as db:
            rows = db.execute(
                f"SELECT * FROM jobs{where} ORDER BY created_at DESC, rowid DESC LIMIT ?",
                values,
            ).fetchall()
        return [self._job_row(row, include_payload=False) for row in rows]

    def start_job(self, job_id: str) -> bool:
        timestamp = utc_now()
        with self._session() as db:
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
        with self._session() as db:
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
        with self._session() as db:
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
        with self._session() as db:
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
        with self._session() as db:
            row = db.execute(
                "SELECT cancellation_requested FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return bool(row and row["cancellation_requested"])

    def request_job_cancel(self, job_id: str) -> dict[str, Any] | None:
        timestamp = utc_now()
        with self._session() as db:
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
        with self._session() as db:
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

    def fail_job(self, job_id: str, *, error_code: str, error_message: str) -> bool:
        timestamp = utc_now()
        with self._session() as db:
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
        with self._session() as db:
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
