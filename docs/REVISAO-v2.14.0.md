# Revisão funcional v2.14.0

## Correções

- Instalação integrada de Mesa/HARK em Python próprio, separado do Python do Windows e do backend base congelado.
- Configurações → Motores com progresso, diagnóstico, reparação e caminhos de Octave, Dynare e Minsky.
- Ativação somente após teste real dos motores; o aplicativo usa o ambiente preparado na próxima abertura.
- Comandos economy-lab-python e economy-lab-pip adicionados ao PATH do usuário durante a preparação dos motores.
- Presets que exigem motores ausentes ficam indisponíveis. Cenários existentes recebem orientação antes de iniciar a execução e ação explícita para aplicar Basic.
- Corrigida a preparação das condições do solver HARK 0.17.2, anteriormente desativada por quiet=True. Parâmetros econômicos preservados.
- Mantidos APIs existentes, níveis de simulação, projetos, histórico, Profiles, lotes, exportações e Ledger/SFC como autoridade contábil única. As rotas de configuração dos motores são aditivas.

## Evidências

- Linux com Mesa/HARK instalados: **259 testes aprovados, nenhum ignorado**.
- Windows, suíte do backend base: **257 testes aprovados e 2 opcionais ignorados**.
- Windows, verificação adicional dos motores instalados: Mesa, HARK e Economy Zero executados com sucesso e Ledger/SFC balanceado.
- Instalador NSIS realmente instalado em uma pasta com espaços. O teste retirou Python/pip do PATH herdado pelo backend, preparou os motores através da API usada pela interface e verificou o reinício no ambiente gerenciado.
- PATH do usuário verificado no registro do Windows; economy-lab-pip aponta para o mesmo ambiente que o aplicativo.
- Backend base empacotado: três cenários Simple Macro, execução de 12 meses, projeto, persistência, Ledger/Godley balanceado e exportação XLSX.
- Frontend TypeScript/Vite compilado. Integração React com DOM emulado e backend HTTP real verificou configurações, diagnóstico, salvamento de caminhos, bloqueio dos presets, Simple Macro e recuperação de consulta de job sem duplicação.

Os arquivos de evidência estão em `validacao/v2.14.0`. Evidências antigas foram mantidas separadamente em `validacao/v2.13.2`.

Commit usado na compilação Windows: `74a3ceef8fb1f83bf5162447265cea196897bb82`.
Execução: https://github.com/Daniel-Castro754/economy-lab/actions/runs/34052845890 — concluída com sucesso.

## Limites

O teste Windows usa instalação silenciosa e o backend realmente instalado; não substitui uma inspeção visual interativa do WebView no computador do usuário. Dynare e Minsky continuam exigindo programas externos e configuração própria. O instalador não é assinado. A primeira preparação dos motores requer internet; simulações posteriores são locais. A adição dos comandos ao PATH ocorre na instalação dos motores pela interface, não na cópia inicial do instalador base.

Projeto inicial: **89,6% (90% arredondado)**, com a mesma régua de `PROJECT_PROGRESS.md`.
