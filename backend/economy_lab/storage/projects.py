from __future__ import annotations

import json
import sqlite3
from typing import Any
from uuid import uuid4

from economy_lab.core.schemas import ScenarioSpec
from economy_lab.storage.jobs import utc_now


class ProjectRecordStoreMixin:
    def create_project(
        self,
        *,
        name: str,
        description: str,
        scenario: ScenarioSpec,
    ) -> dict[str, Any]:
        project_id = str(uuid4())
        timestamp = utc_now()
        with self._session() as db:
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
        with self._session() as db:
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
        with self._session() as db:
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
        with self._session() as db:
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
        with self._session() as db:
            cursor = db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            return cursor.rowcount > 0
