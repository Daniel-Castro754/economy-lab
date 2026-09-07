# Economy Lab Hub — Tools

A v1.5 introduz dois níveis de composição:

1. **Module** — tecnologia ou domínio (Dynare, Minsky, Mesa, HARK, Simulation, Analytics).
2. **Tool** — ação isolada com entrada/saída própria.

Uma ferramenta standalone nunca altera o Simulation Lab implicitamente. A transferência de configuração/resultados entre ferramentas e o simulador deve ser uma ação explícita e validada.

## Catálogo inicial

- `simulation-run`
- `simulation-batch`
- `simulation-charts`
- `simulation-export`
- `dynare-template`
- `dynare-irf`
- `minsky-introspection`
- `minsky-variables`
- `minsky-runtime`
- `mesa-wealth`
- `hark-policy`
- `analytics-compare`
- `analytics-sql`
- `scenario-compiler`

Cada entrada informa módulo pai, capability, rota, formatos de saída, disponibilidade e status.
