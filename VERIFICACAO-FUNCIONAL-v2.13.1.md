# Verificação funcional — Economy Lab v2.13.1

## Correções desta versão

- **Configurações:** o botão da engrenagem agora abre um painel real com timeout do Economy Zero, abertura automática de resultados, densidade da interface e diagnóstico do ambiente local.
- **Economy Zero:** a interface usa a fila persistente já existente no backend. Exibe fila/etapa/mês/percentual, permite cancelar, respeita timeout e mostra o resultado ou o erro na própria tela.
- **Desempenho percebido:** foi adicionado um preset explícito **Teste rápido** (300 famílias, 15 empresas, 3 bancos, 12 meses). A escala econômica padrão continua em 5.000 famílias, 100 empresas, 3 bancos e 24 meses.
- **Rolagem:** parâmetros e resultados agora têm rolagem independente. O painel de resultados não desaparece quando o formulário longo é percorrido.
- **Abas da Simulation Lab:** Simulação única, Fila, Manifesto/replay, Lotes, Gráficos e Exportações levam às áreas correspondentes.
- **Ações globais:** Executar inicia a simulação/fila ou o lote conforme a ferramenta ativa; Salvar, Exportar, Configurações e Ajuda possuem ações reais.
- **Níveis:** Simple Macro, Economy Zero e Hybrid/Advanced mantêm seleção visual independente.

## Auditoria dos controles

| Área | Estado verificado |
|---|---|
| Simple Macro e cenários externos | API, seleção, reinício, 7 anos, abas e exportações conectados |
| Economy Zero | envio, polling, progresso, conclusão, falha, nova tentativa e cancelamento conectados |
| Projetos, histórico e Profiles | criar, abrir, salvar, excluir, aplicar e listar conectados ao SQLite local |
| Experimentos em lote | parâmetros, execução, histórico, gráfico e exportações conectados |
| Scenario AI / Model Builder | gerar, validar, aplicar e baixar JSON conectados |
| Dados, Calibração e Validação | controles ligados às APIs; fontes públicas continuam dependentes de rede |
| Dynare, Minsky, Mesa e HARK | continuam visíveis; execução fica desabilitada quando a dependência não está instalada |
| Ledger/SFC | permanece a autoridade contábil única; o Teste rápido também fechou ledger, estoques e fluxos |

## Evidência automatizada

- Backend: **192 testes aprovados, 2 ignorados** (dependências externas opcionais), 1 aviso de depreciação de biblioteca.
- Frontend: TypeScript e build Vite de produção concluídos sem erro.
- Simulação funcional local do preset Teste rápido: 12 pontos mensais em **2,527 s** no ambiente de validação, com ledger, estoques e fluxos balanceados.
- Auditoria estática: todos os elementos `<button>` visíveis possuem ação; desabilitações encontradas são condicionais e intencionais.

## Limites honestos

- A escala padrão usa 5.000 agentes familiares e é naturalmente muito mais pesada que o Teste rápido. Agora ela não aparenta travar: há progresso, cancelamento e erro observável, mas não foi reduzida para evitar alterar a escala econômica padrão.
- Dynare, Minsky, Mesa e HARK só podem ser executados quando instalados/qualificados. A ausência deles não bloqueia Simple Macro nem Economy Zero Basic.
- Consultas a BCB, IBGE, World Bank e Ipeadata dependem da disponibilidade da internet e da fonte pública no momento da execução.

**Conclusão da correção solicitada: 100%.**
