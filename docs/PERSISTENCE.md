# Persistence architecture — schema v5

## Goals

Persistence is local-first and must not compromise experiment reproducibility.

A **project** is mutable: its name, description and current validated `ScenarioSpec` can change.
A **run** is immutable: it stores a copy of the exact scenario plus the complete `SimulationResult` produced at execution time.

Changing a project after a run therefore cannot rewrite experimental history.

A **job** is a persistent execution envelope. Its state and progress survive HTTP client disconnects, while a completed project job creates its immutable run in the same SQLite transaction that closes the job.

## SQLite

SQLite is used for transactional product state because it:

- ships with Python;
- requires no database server;
- supports ACID transactions and foreign keys;
- is easy to bundle in the desktop sidecar;
- is appropriate for project metadata and individual run documents.

Connections are short-lived and configured with WAL, foreign-key enforcement and `synchronous=NORMAL`.

DuckDB is intentionally deferred. It is a better fit for later batch simulation analytics, sensitivity grids and columnar queries over very large run sets, not as the primary mutable project store.

## Database location

Resolution order:

1. `ECONOMY_LAB_DB_PATH` — exact file override;
2. `ECONOMY_LAB_DATA_DIR/economy-lab.sqlite3` — desktop sidecar path;
3. `~/.economy-lab/economy-lab.sqlite3` — normal local backend fallback.

Tauri resolves its OS-specific application-data directory and injects it into the sidecar as `ECONOMY_LAB_DATA_DIR`.

## Schema v1

### projects

- `id` UUID
- `name`
- `description`
- `scenario_json`
- `created_at`
- `updated_at`
- `last_run_id`

### runs

- `id` UUID
- `project_id`
- exact `scenario_json`
- exact `result_json`
- `created_at`
- execution duration
- engine version
- summary columns for fast history lists

Deleting a project cascades to its runs.

SQLite `PRAGMA user_version` is used as a migration guard. A database newer than the running Economy Lab is rejected rather than silently modified.

## Schema v4: simulation jobs

The `jobs` table stores the exact scenario, optional project, lifecycle timestamps, monotonic progress, safe-cancellation request, timeout, result/run reference and a bounded error record. Valid terminal states are `completed`, `failed` and `cancelled`; timeout is represented by `failed` plus `error_code=timeout`.

Rows left `running` by a terminated backend are marked `failed` with `worker_interrupted` on startup. Rows still `queued` are submitted again to the bounded local worker pool.

## Schema v5: manifests and replay lineage

Every new persisted run stores `manifest_json`, `manifest_hash`, `experiment_hash` and optional `replay_of_run_id`. The manifest and immutable run are written in the same transaction. Existing v4 rows migrate with null manifest fields: the system does not fabricate evidence that was not captured at execution time.

The experiment hash covers the complete scenario, runtime versions, profile hashes and data-provenance records. The result has a separate hash so replay can distinguish changed execution context from changed numerical output.

## API

- `GET /api/v1/storage/status`
- `GET /api/v1/projects`
- `POST /api/v1/projects`
- `GET /api/v1/projects/{id}`
- `PUT /api/v1/projects/{id}`
- `DELETE /api/v1/projects/{id}`
- `POST /api/v1/projects/{id}/simulate`
- `GET /api/v1/projects/{id}/runs`
- `GET /api/v1/runs/{id}`
- `POST /api/v1/jobs/simulations`
- `POST /api/v1/projects/{id}/jobs/simulations`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{id}`
- `POST /api/v1/jobs/{id}/cancel`
- `GET /api/v1/runs/{id}/manifest`
- `POST /api/v1/runs/{id}/replay`

`POST /api/v1/simulate` remains intentionally ephemeral.
