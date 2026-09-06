from __future__ import annotations

import json
import sqlite3
from typing import Any
from uuid import uuid4

from economy_lab.storage.jobs import utc_now


class ProfileStoreMixin:
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
        with self._session() as db:
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
        with self._session() as db:
            rows = db.execute(
                "SELECT id, name, description, kind, module_id, compatibility, created_at, updated_at "
                f"FROM profiles{where} ORDER BY updated_at DESC, created_at DESC",
                values,
            ).fetchall()
        return [self._profile_row(row, include_payload=False) for row in rows]

    def get_profile(self, profile_id: str) -> dict[str, Any] | None:
        with self._session() as db:
            row = db.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if row is None:
            return None
        return self._profile_row(row, include_payload=True)

    def delete_profile(self, profile_id: str) -> bool:
        with self._session() as db:
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
