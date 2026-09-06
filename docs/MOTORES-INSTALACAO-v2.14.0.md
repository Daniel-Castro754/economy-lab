# Instalação de motores — Economy Lab v2.14.0

## Causa do erro da v2.13.2

O instalador base da v2.13.2 não incluía Mesa e HARK. Um cenário ou preset podia solicitar HARK mesmo quando esse motor não estava disponível. O backend estava pronto para atender à interface e executar o modo nativo, mas isso não significava que todos os motores opcionais estavam instalados.

O comando `py -m pip install -e ".[simulation]"` registrado pelo usuário terminou com sucesso no Python 3.12 do Windows. Esse Python é diferente do backend congelado com PyInstaller. Adicionar o Python do Windows ao PATH ou repetir o comando não incorpora esses pacotes ao executável instalado.

## Como usar a instalação integrada

1. Instale o Economy Lab atualizado e abra **Configurações → Motores**.
2. Clique em **Instalar Mesa e HARK**. Mantenha o aplicativo aberto e conectado à internet durante a preparação.
3. Aguarde o teste dos motores e a mensagem de conclusão.
4. Feche todas as janelas do Economy Lab e abra o aplicativo novamente.
5. O preset Intermediate passa a ficar disponível quando Mesa e HARK forem detectados no ambiente ativo. Dynare continua sendo um requisito separado para os presets que o solicitam.

O modo **Basic** continua disponível sem baixar motores. Para um cenário existente que peça dependências ausentes, a interface oferece **Aplicar Basic (motores nativos)**. Essa troca é uma escolha explícita: não substituímos silenciosamente o comportamento econômico selecionado.

## Ambiente próprio e PATH

A preparação cria um Python exclusivo sob a pasta de dados do usuário do Economy Lab, exibida nas configurações. O aplicativo usa caminhos absolutos para instalar e executar os pacotes. Não precisa encontrar `py`, `python` ou `pip` no PATH do Windows.

Após a instalação dos motores, são adicionados ao PATH do usuário os comandos:

- `economy-lab-python`: executa o Python usado pelo Economy Lab.
- `economy-lab-pip`: executa o pip desse mesmo ambiente.

Abra um novo terminal para usar esses comandos. Exemplo de diagnóstico: `economy-lab-pip show econ-ark mesa`. Os comandos normais `python`, `py` e `pip` do computador continuam com seus destinos existentes. A adição ao PATH ocorre na preparação dos motores pelo aplicativo, não na cópia inicial do instalador base.

A instalação integrada usa uv 0.8.22 e um pacote do backend da mesma versão do aplicativo. O Python é obtido da distribuição gerenciada pelo uv. Mesa 3.5.1 e Econ-ARK/HARK 0.17.2 são instalados no ambiente próprio. A ativação só é gravada após importar e exercitar os motores e verificar uma simulação com Ledger/SFC balanceado. Se uma tentativa falhar, o ambiente anterior permanece registrado.

## Dynare e Minsky

Esses programas continuam com instalação própria. Em **Configurações → Motores**, informe o executável do Octave, a pasta `matlab` do Dynare (contendo `dynare.m`) e, se utilizado, o endereço REST do Minsky. Salve e reabra o aplicativo para atualizar todos os indicadores.

Ter um caminho configurado não garante que o programa esteja executando ou qualificado. Use **Validação** para conferir a integração. O Ledger/SFC permanece a autoridade contábil única.

## Diagnóstico e recuperação

O botão **Ver diagnóstico da instalação** mostra a saída recente do instalador de motores. Erros de rede, resolução de dependências e teste são apresentados na interface. Instalações interrompidas podem ser tentadas novamente. Uma nova versão do aplicativo exige um ambiente compatível com sua versão; ambientes antigos não são ativados automaticamente com código novo.

Referências técnicas: [processos externos em aplicativos PyInstaller](https://pyinstaller.org/en/v6.11.1/common-issues-and-pitfalls.html) e [Python gerenciado pelo uv](https://docs.astral.sh/uv/guides/install-python/).

## Compatibilidade HARK corrigida

A validação com o HARK realmente instalado encontrou também uma incompatibilidade no adaptador anterior: `quiet=True` impedia `IndShockConsumerType.pre_solve()` de preparar as condições usadas por `post_solve()` no HARK 0.17.2. A chamada agora mantém `quiet=False` e `verbose=False`. Os parâmetros econômicos e a política de autoridade contábil não foram alterados. O teste integrado de Mesa + HARK passou após essa correção.
