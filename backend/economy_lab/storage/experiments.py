from __future__ import annotations

import json
import sqlite3
from typing import Any
from uuid import uuid4

from economy_lab.storage.jobs import utc_now


class ExperimentStoreMixin:
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
        with self._session() as db:
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
        with self._session() as db:
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
        with self._session() as db:
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
