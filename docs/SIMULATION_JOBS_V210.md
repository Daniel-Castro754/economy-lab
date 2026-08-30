# v2.10 Persistent simulation jobs

## Contract

The asynchronous API creates a durable SQLite job before scheduling any work. The lifecycle is restricted to:

- `queued` — accepted, waiting for a bounded worker;
- `running` — claimed atomically by one worker;
- `completed` — result persisted; project jobs also reference an immutable run;
- `failed` — controlled timeout, engine error, simulation error or interrupted worker;
- `cancelled` — cancellation accepted before execution or observed at a safe checkpoint.

Progress is monotonic from 0 to 100 and includes a stage plus current/total monthly steps. The worker count is controlled by `ECONOMY_LAB_JOB_WORKERS` (default 2, bounded to 1–16).

## Cancellation and deadlines

Economy Zero and demo simulations check cancellation/deadline controls between monthly steps and before final persistence. Python worker threads are never force-killed because that could leave an in-memory ledger in an unknown state. This means cancellation latency is bounded by the current safe simulation step.

For Dynare/Octave, the remaining job deadline is also passed to `subprocess.run`, giving external execution a hard process timeout. An expired deadline is stored as `status=failed` and `error_code=timeout`.

For project jobs, saving the immutable run and marking the job completed occur in one SQLite transaction. A cancellation race therefore resolves entirely to either a completed job with a run or a cancelled job without a run.

## API

```text
POST /api/v1/jobs/simulations
POST /api/v1/projects/{project_id}/jobs/simulations
GET  /api/v1/jobs?status=running&project_id=...
GET  /api/v1/jobs/{job_id}
POST /api/v1/jobs/{job_id}/cancel
```

The existing synchronous `/simulate` and `/projects/{id}/simulate` endpoints are unchanged for compatibility. New clients should prefer jobs for longer runs so HTTP connection lifetime does not control simulation lifetime.
