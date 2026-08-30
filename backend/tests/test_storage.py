from __future__ import annotations

from economy_lab.core.schemas import ScenarioSpec
from economy_lab.core.simulation import run_simulation
from economy_lab.storage.sqlite_store import ProjectStore


def test_project_crud_and_immutable_run_history(tmp_path):
    store = ProjectStore(tmp_path / "test.sqlite3")
    spec = ScenarioSpec(name="Persisted", months=1, households=120, firms=8, banks=2, seed=7)
    project = store.create_project(name="Meu projeto", description="teste", scenario=spec)

    assert project["name"] == "Meu projeto"
    assert project["scenario"]["seed"] == 7
    assert project["run_count"] == 0

    result = run_simulation(spec)
    run = store.save_run(
        project_id=project["id"],
        scenario=spec,
        result=result,
        duration_ms=12.5,
        engine_version="1.3.0",
    )
    assert run["result"]["summary"]["ledger_balanced"] is True
    assert store.get_project(project["id"])["run_count"] == 1

    changed = ScenarioSpec(name="Persisted changed", months=1, households=120, firms=8, banks=2, seed=99)
    store.update_project(project["id"], name="Renomeado", scenario=changed)
    old_run = store.get_run(run["id"])
    assert old_run["scenario"]["seed"] == 7
    assert store.get_project(project["id"])["scenario"]["seed"] == 99


def test_project_delete_cascades_runs(tmp_path):
    store = ProjectStore(tmp_path / "cascade.sqlite3")
    spec = ScenarioSpec(months=1, households=120, firms=8, banks=2)
    project = store.create_project(name="Cascade", description="", scenario=spec)
    result = run_simulation(spec)
    run = store.save_run(
        project_id=project["id"],
        scenario=spec,
        result=result,
        duration_ms=1,
        engine_version="1.3.0",
    )
    assert store.delete_project(project["id"]) is True
    assert store.get_run(run["id"]) is None
    assert store.status()["runs"] == 0


def test_database_schema_status(tmp_path):
    store = ProjectStore(tmp_path / "status.sqlite3")
    status = store.status()
    assert status["schema_version"] == 5
    assert status["projects"] == 0
    assert status["runs"] == 0
    assert status["profiles"] == 0
    assert status["jobs"] == 0


def test_store_operations_close_every_connection(tmp_path):
    """Regression guard for the ``_session`` connection leak.

    ``sqlite3.Connection`` used as a context manager only commits/rolls back
    the transaction; it never closes the connection. ``ProjectStore`` opens a
    fresh connection per call, so without an explicit ``close()`` a
    long-running desktop backend would leak one file descriptor per request
    and per job-progress tick. Every connection opened by the store must be
    closed by the time the call returns.
    """
    import sqlite3

    import pytest

    store = ProjectStore(tmp_path / "leak-check.sqlite3")
    opened: list[sqlite3.Connection] = []
    original_connect = store._connect

    def tracking_connect() -> sqlite3.Connection:
        connection = original_connect()
        opened.append(connection)
        return connection

    store._connect = tracking_connect  # type: ignore[method-assign]

    spec = ScenarioSpec(name="Leak check", months=1, households=120, firms=8, banks=2)
    project = store.create_project(name="Leak", description="", scenario=spec)
    store.status()
    store.get_project(project["id"])

    assert len(opened) >= 3
    for connection in opened:
        with pytest.raises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")


def test_schema_v1_migrates_to_v5_without_dropping_projects(tmp_path):
    import sqlite3
    path = tmp_path / "legacy-v1.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE projects (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
                scenario_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                last_run_id TEXT NULL
            );
            CREATE TABLE runs (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, scenario_json TEXT NOT NULL,
                result_json TEXT NOT NULL, created_at TEXT NOT NULL, duration_ms REAL NOT NULL DEFAULT 0,
                engine_version TEXT NOT NULL, final_gdp_index REAL NOT NULL, final_inflation REAL NOT NULL,
                final_unemployment REAL NOT NULL, ledger_balanced INTEGER NOT NULL,
                godley_stocks_balanced INTEGER NOT NULL, godley_flows_balanced INTEGER NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
        """)
        db.execute("PRAGMA user_version = 1")
        db.execute(
            "INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("legacy", "Legacy", "", ScenarioSpec(months=1, households=120, firms=8, banks=2).model_dump_json(),
             "2026-08-29T00:00:00+00:00", "2026-08-29T00:00:00+00:00", None),
        )
    store = ProjectStore(path)
    assert store.status()["schema_version"] == 5
    assert store.get_project("legacy")["name"] == "Legacy"
    assert store.status()["experiments"] == 0
    assert store.status()["profiles"] == 0
    assert store.status()["jobs"] == 0
