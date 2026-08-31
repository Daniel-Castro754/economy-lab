# Economy Lab v2.13

## v2.13.0 — Tabler-inspired compact desktop design

- Reorganiza a navegação em Simulation Lab, Modelagem, Análise e Trabalho local, preservando todas as rotas e terminologia.
- Substitui símbolos inconsistentes por uma família local de ícones SVG no estilo Tabler, sem dependência visual externa.
- Adiciona cabeçalho de página, estados semânticos de módulos, ações globais e hierarquia mais clara entre módulo e ferramenta.
- Transforma os cenários externos do Simple Macro em opções visuais alimentadas pela API e mantém erro/nova tentativa explícitos.
- Agrupa decisões monetárias e fiscais, melhora KPIs e adiciona estado vazio orientado para a primeira simulação.
- Mantém Ledger/SFC como autoridade contábil única e motores externos visíveis mesmo quando não instalados.

# Economy Lab v2.12

## v2.12.1 — Functional desktop connectivity audit

- Corrige o CORS da origem `http://tauri.localhost`, permitindo que o aplicativo instalado consulte a API local.
- Restaura os três cenários externos e a inicialização funcional do Simple Macro no executável.
- Exibe falhas de carregamento do Simple Macro com ação de nova tentativa, sem esconder o erro.
- Conecta Salvar, Exportar e os menus do shell desktop às ações e módulos reais.
- Adiciona teste de regressão para a comunicação entre WebView e backend local.

## v2.12.0 — Dense desktop workspace redesign

- Replaced the oversized hub header with a compact desktop topbar, menu bar and collapsible module sidebar.
- Redesigned Simple Macro around dense policy controls, nine result views and real backend data.
- Preserved the three simulation levels, modules, Profiles, local projects, exports and SFC authority contracts.
- Kept optional engines visible with explicit availability states and no Basic-mode blockage.
- Kept the desktop UI fully local-first by using system fonts and local assets.
- Retained the Windows GUI subsystem so the release executable opens without a console window.

## v2.11.0 — Reproducible run manifests and verified replay

- Added canonical JSON and SHA-256 hashing for scenarios, results, manifests and experiment identity.
- Added runtime capture for Economy Lab, Python, OS/machine and numerical/optional engine packages.
- Added profile payload/patch hashes and explicit `ScenarioSpec.data_provenance` records.
- Added SQLite schema v5 with manifest fields and immutable replay lineage.
- Added manifest integrity checks before replay; tampered scenario, result or manifest data is rejected.
- Added replay status `matched`, `environment_changed` or `diverged` with runtime differences.
- Kept legacy v4 runs readable without fabricating retroactive manifests.
- Added `GET /runs/{id}/manifest` and `POST /runs/{id}/replay`.

# Economy Lab v2.10

## v2.10.0 — Persistent simulation jobs

- Added SQLite schema v4 with durable simulation jobs and atomic lifecycle transitions.
- Added a bounded worker pool with queued/running/completed/failed/cancelled states.
- Added monotonic stage/month progress and safe cooperative cancellation checkpoints.
- Added per-job deadlines and propagation of the remaining hard timeout to Dynare/Octave.
- Added atomic project-job completion: immutable run creation and job completion share one transaction.
- Added startup recovery: interrupted running jobs fail explicitly and queued jobs are rescheduled.
- Added create/list/get/cancel job endpoints, including the project convenience route.
- Preserved all existing synchronous simulation endpoints.
- Expanded regression coverage for persistence, progress, cancellation, timeout and API behavior.

# Economy Lab v2.9

## v2.9.0 — Minsky/Godley reconciliation + SFC final

- Added a deterministic, read-only Minsky reconciliation contract for known `.mky` templates.
- Added explicit cell mappings for stock/flow kind, instrument, sector, Minsky variable ID and sign/unit multiplier.
- Added strict duplicate-mapping, missing-observation and non-zero canonical-cell coverage checks.
- Added combined absolute/relative tolerances with per-cell drift evidence.
- Added canonical, mapping and observed SHA-256 hashes plus a deterministic reconciliation report ID.
- Added `pass`, `partial` and `fail` outcomes without granting Minsky ledger authority.
- Added local `.mky` SHA-256 verification before live REST capture.
- Added `POST /api/v1/minsky/reconcile` for provided snapshots or verified live, read-only capture.
- Added regression coverage proving the reconciliation path never calls a Minsky setter.
- Preserved the frozen v2.8 Authority Registry and Ledger/SFC as the only balance authority.

# Economy Lab v2.8

## v2.8.0 — Authority Registry + engine contracts

- Added a frozen canonical-variable Authority Registry (`economy_lab.core.authority`).
- Added strict scenario-specific ownership plans for Mesa/native activation, HARK/native household decisions, Minsky/native financial controls and Dynare macro guidance.
- Locked realized GDP, inflation and unemployment to Economy Zero ABM authority.
- Locked deposits, credit, reserves, household/corporate/government debt and bank capital to Ledger/SFC authority.
- Added duplicate-write/conflict detection. A canonical field cannot be silently overwritten in the same run/tick.
- Added binding checks so an explicitly requested engine cannot silently fall back to a different implementation.
- Froze `EconomyState` schema v1.0 as the realized inter-engine state contract.
- Added strict authority claims to every Economy Zero month and fail-fast completeness checks.
- Added `SimulationResult.authority` with ownership plan, claim counts and violations.
- Added `GET /api/v1/authority/registry` and `POST /api/v1/authority/plan`.
- Added Authority sheets to simulation XLSX exports.
- Kept external signals separated from realized state: Dynare owns IRFs, Minsky owns financial guidance, HARK owns desired consumption and Mesa owns activation order only.
- Backend regression: 164 passed, 2 optional skips in this environment.
