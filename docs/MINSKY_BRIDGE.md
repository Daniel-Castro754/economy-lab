# Minsky bridge — v0.6

Economy Lab v0.6 has an operational Minsky bridge with two modes.

1. **Exchange mode** exports deterministic Godley stock/flow matrices as `economy-lab-godley-v1.0` JSON and CSV-compatible tables.
2. **REST/template mode** connects to a running Minsky REST service through `MINSKY_REST_URL`, performs a documented REST handshake, can load/save/reset/step a model, and synchronises explicitly mapped Minsky variables through `variableValues`.

The bridge intentionally does not guess or mutate Minsky Godley object internals. A `.mky` template defines semantics; Economy Lab pushes inputs and can pull outputs. This keeps the Economy Lab ledger as the accounting source of truth and prevents two engines from independently creating money.

Example environment variable on Windows:

```powershell
$env:MINSKY_REST_URL = "http://127.0.0.1:8000"
```

Minsky documents GET/PUT REST access, `/minsky/@type`, `@list`, `@signature`, `/minsky/load`, and container access through `@elem`.
