# Profiles e presets — v1.7

## Objetivo

Cada laboratório externo pode trabalhar isoladamente e produzir um **Profile reutilizável**. O Simulation Lab resolve o Profile para campos validados do `ScenarioSpec` antes da execução; o kernel não consulta o banco de Profiles durante a simulação.

Isso cria dois modos legítimos:

- **Basic:** Economy Lab nativo, sem dependências externas.
- **Composto:** um cenário simples recebe Profiles de Dynare, Mesa, HARK e, de forma assistiva, Minsky.

## Profile kinds

- `macro` — Dynare.
- `agents` — Mesa.
- `households` — HARK/Econ-ARK.
- `financial` — Minsky (assistive-only nesta versão).

Um Profile contém:

- nome e descrição;
- módulo de origem;
- inputs do laboratório;
- outputs obtidos (quando existirem);
- `scenario_patch` validado;
- nível de compatibilidade (`active` ou `assistive-only`).

## Aplicação

`POST /profiles/{id}/apply` recebe um `ScenarioSpec`, aplica somente chaves permitidas e revalida o cenário inteiro. O resultado é um novo `ScenarioSpec` resolvido e uma lista das alterações.

A origem é registrada em `ScenarioSpec.applied_profiles`, permitindo saber qual Profile forneceu a configuração de macro, agentes, famílias ou finanças.

## Dynare Profile

Transfere de verdade para o simulador:

- motor Dynare;
- choque monetário;
- horizonte IRF;
- taxa nominal neutra;
- beta, sigma, kappa;
- rho_i, phi_pi e phi_x.

A recalibração trimestral parte desses parâmetros-base e aplica somente adaptações limitadas.

## HARK Profile

Transfere:

- ativação do comportamento HARK;
- CRRA;
- fator de desconto anual.

O simulador converte o fator de desconto central em pequenos cohorts de paciência ao redor do valor selecionado.

## Mesa Profile

Ativa o runtime Mesa para os agentes do Economy Zero. Os parâmetros do demo Wealth Exchange ficam preservados como metadados/resultado do Profile, mas não são confundidos com a população do Economy Zero.

## Minsky Profile

É **assistive-only**. O snapshot/configuração é associado ao cenário para auditoria e futura integração, mas não substitui o ledger SFC nativo. Esta restrição é intencional para impedir duas fontes de verdade contábil.

## Presets

- **Basic** — native + heuristic + macro off.
- **Intermediate** — Mesa + HARK + macro simplificada.
- **Macro Hybrid** — Dynare híbrido com re-solução trimestral.
- **Full atual** — Mesa + HARK + Dynare; Minsky pode ser anexado assistivamente.
- **Custom** — nenhuma alteração automática.

## Persistência

SQLite schema v3 adiciona a tabela `profiles`. Profiles são globais ao workspace, não pertencem a um projeto específico, porque devem ser reutilizáveis em vários projetos.


## Minsky Financial Profile ativo

A partir da v1.7, um Profile Minsky pode ser `active-static` ou `active-path` quando contém controles financeiros canônicos. O Profile pode alterar regras bancárias do Simulation Lab (`financial_engine=minsky_profile`), mas não pode escrever saldos no ledger. Profiles antigos sem controles canônicos continuam `assistive-only`.
