from __future__ import annotations

from contextlib import contextmanager
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = 5


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=10.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection


@contextmanager
def _session(path: Path) -> Iterator[sqlite3.Connection]:
    connection = _connect(path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _backup_before_migration(path: Path, from_version: int, to_version: int) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    stem = path.stem
    suffix = path.suffix
    final_name = f"{stem}.v{from_version}_to_v{to_version}.{ts}.backup{suffix}"
    tmp_name = final_name + ".tmp"
    final_path = path.parent / final_name
    tmp_path = path.parent / tmp_name
    try:
        source = sqlite3.connect(path)
        try:
            dest = sqlite3.connect(tmp_path)
            try:
                source.backup(dest)
            finally:
                dest.close()
        finally:
            source.close()
        tmp_path.replace(final_path)
    except Exception as exc:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeError(
            f"Failed to back up database before migration "
            f"(v{from_version} -> v{to_version}): {exc}"
        ) from exc
    return final_path


def initialize_database(path: Path) -> None:
    pre_conn = sqlite3.connect(path, timeout=10.0)
    try:
        version = int(pre_conn.execute("PRAGMA user_version").fetchone()[0])
    finally:
        pre_conn.close()

    if version > SCHEMA_VERSION:
        raise RuntimeError(
            f"Database schema {version} is newer than supported {SCHEMA_VERSION}"
        )

    if 0 < version < SCHEMA_VERSION:
        _backup_before_migration(path, version, SCHEMA_VERSION)

    with _session(path) as db:
        version = int(db.execute("PRAGMA user_version").fetchone()[0])
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

    post_conn = _connect(path)
    try:
        try:
            rows = post_conn.execute("PRAGMA quick_check").fetchall()
        except sqlite3.DatabaseError as exc:
            raise RuntimeError(f"Database integrity check failed after initialization: {exc}") from exc
        if len(rows) != 1 or rows[0][0] != "ok":
            details = "; ".join(str(r[0]) for r in rows[:20])
            raise RuntimeError(
                f"Database integrity check failed after initialization: {details}"
            )
    finally:
        post_conn.close()
