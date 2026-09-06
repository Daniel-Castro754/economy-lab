# Minsky bridge — v0.6

Economy Lab v0.6 has an operational Minsky bridge with two modes.

1. **Exchange mode** exports deterministic Godley stock/flow matrices as `economy-lab-godley-v1.0` JSON and CSV-compatible tables.
2. **REST/template mode** connects to a running Minsky REST service through `MINSKY_REST_URL`, performs a documented REST handshake, can load/save/reset/step a model, and synchronises explicitly mapped Minsky variables through `variableValues`.

The bridge intentionally does not guess or mutate Minsky Godley object internals. A `.mky` template defines semantics; Economy Lab pushes inputs and can pull outputs. This keeps the Economy Lab ledger as the accounting source of truth and prevents two engines from independently creating money.

Example environment variable on Windows (local service):

```powershell
$env:MINSKY_REST_URL = "http://127.0.0.1:8000"
```

## Segurança da URL REST

A URL é validada antes de qualquer solicitação de rede. Use `http://` somente para `localhost` ou um endereço IP de loopback real, como `127.0.0.1` ou `[::1]`. Para qualquer host remoto, use `https://`:

```powershell
$env:MINSKY_REST_URL = "https://minsky.example.com/api"
```

URLs não podem conter credenciais embutidas, query string ou fragmento. A barra final da raiz é normalizada; paths configurados, inclusive os que terminam em `/`, são preservados.

Minsky documents GET/PUT REST access, `/minsky/@type`, `@list`, `@signature`, `/minsky/load`, and container access through `@elem`.
