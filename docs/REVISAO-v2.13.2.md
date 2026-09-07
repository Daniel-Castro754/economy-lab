# Economy Lab v2.13.2 — revisão do pacote enviado

## Fonte e preservação

Base: arquivo `Economy Lab.zip` enviado pelo usuário, comparado byte a byte com o pacote v2.13.1 anterior. O instalador enviado era idêntico ao da versão anterior, apesar das mudanças no código; foi necessária uma nova compilação.

A revisão preserva a modularização das APIs do frontend e backend, a divisão do armazenamento SQLite, os painéis ProjectPanel/ProfilePanel, a proveniência das séries reais, a validação de entradas, as restrições de origem/CSP, o uso do cenário original nas exportações e o bloqueio de operações concorrentes do Simple Macro.

## Correções complementares

- A interface dispara várias consultas na primeira abertura. Elas podiam inicializar ou migrar o SQLite simultaneamente e falhar com `duplicate column name: manifest_json`. A inicialização agora é serializada por processo e a migração usa uma única transação SQLite, com `BEGIN IMMEDIATE` e rollback completo em caso de falha.
- Uma falha ao consultar um job não permite mais que “Tentar novamente” fique sem ação: “Reconectar à simulação” consulta o mesmo identificador e continua acompanhando o resultado, sem criar outro job. A consulta tem limite de 15 segundos.
- Falha na atualização da lista do histórico não invalida um resultado já concluído.
- A troca, criação e exclusão de projetos ficam bloqueadas enquanto há um job ativo, inclusive após falha na consulta de progresso.
- Valores NaN/Infinity enviados à API recebem erro HTTP 422 serializável, em vez de provocar uma falha ao gerar a resposta de validação.
- Erros SQLite durante `quick_check` são apresentados como falhas de integridade identificáveis.
- Os scripts de compilação interrompem o processo se npm, pip, PyInstaller ou Tauri falharem.
- Identificadores de versão atualizados para 2.13.2 no código, interface, manifests e lockfiles.

## Validação local

- Backend: 252 testes aprovados e 2 ignorados por dependências opcionais.
- Frontend: TypeScript e Vite compilados.
- Teste de integração dos componentes React com DOM emulado e backend HTTP real: três cenários disponíveis, avanço anual do Simple Macro, execução Economy Zero, falha de consulta provocada e reconexão ao mesmo job. Uma única submissão foi registrada; o resultado apareceu após a reconexão.
- Teste de inicialização simultânea: oito chamadas ao mesmo banco novo.
- Teste de interrupção da migração: DDL e versão revertidos integralmente; a próxima abertura consegue inicializar o banco.

O DOM emulado verifica comportamento; não substitui inspeção visual de navegador ou WebView. A inspeção visual não pôde ser realizada porque o navegador deste ambiente bloqueou a URL local. Não foi realizada instalação interativa no computador do usuário.

## Validação Windows

A evidência final do processo Windows, incluindo o resultado dos testes e do backend empacotado, acompanha o pacote em `docs/validacao/`. O teste do backend empacotado verifica a versão, CORS Tauri, três cenários, inicialização simultânea, projeto, execução de 12 meses, persistência, equilíbrio Ledger/SFC e exportação XLSX.

Commit de compilação: `287318262390c5af66e5e07c07652a3d670f7158`.
Branch de compilação: `build/review-v2.13.2`. O pacote continua utilizável e compilável localmente no Windows, sem depender dessa branch. A branch principal não foi alterada nesta entrega.

## Limites mantidos

Mesa, HARK, Dynare e Minsky continuam opcionais e não foram qualificados ao vivo nesta revisão. Esta compilação usa o modo sem Mesa/HARK embarcados. O modo nativo Basic e Economy Zero não depende deles. O instalador não é assinado.

Progresso do projeto inicial: **90% arredondado (89,6% na régua fixa)**. Esta entrega corrige e empacota ajustes, sem atribuir pontos a integrações externas ainda não qualificadas.
