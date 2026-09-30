# Síntese do Guardian numa RTX 5090 local — registro, 21 → 24/09/2026

[English](../en/findings/guardian-local-models-2026-09-21-24.md) | **Português (Brasil)**

> A versão em inglês é a principal; esta é a tradução.

Este registro consolida quatro dias de medição para o **Guardian**: um
componente de outro projeto (`claude-bridge`) que lê a cronologia automática da
tela de um agente e escreve uma síntese para o owner — o que está sendo
construído, o que funcionou, o que falhou, o que não foi verificado e o que
espera decisão dele. O llm-bench mediu; o prompt e o código do Guardian são do
outro projeto e nunca foram editados aqui.

> **O que é público e o que não é.** A evidência bruta (recortes de cronologia,
> respostas dos modelos, formulários cegos, lotes da sombra) tem dados de outros
> projetos — identificadores de conta, nomes de terceiros, credenciais em
> contexto — e fica na máquina do laboratório (`.gitignore`, seção da evidência
> do Guardian). Este documento traz números, métodos e conclusões. As
> ferramentas que os produziram estão em `tools/` e são públicas.

## 1. Método de avaliação (vale para tudo abaixo)

- **Rubrica 4**, formulários cegos, dois avaliadores independentes (`rev-1`,
  `rev-2`) por resposta; discordâncias num critério que reprova no gate de
  concordância vão para arbitragem cega (`scout`), e esses números são marcados
  como *arbitrados*.
- **Gate de concordância** por critério (`GATE-REGRAS-v3`): κ de Cohen / AC1 de
  Gwet, n ≥ 7, e **A2 por Spearman ρ ≥ 0,80** (A2 é contagem). O gate do
  instrumento passou nos dois eixos numa amostra nunca vista, antes de qualquer
  campanha.
- **Só material nunca visto** vai para gate; seeds já avaliadas nunca são
  reusadas (com t = 0 a resposta é determinística e já foi vista).
- **Regras congeladas antes do dado**: todo experimento tem um arquivo de
  regras escrito e com hash antes da primeira chamada ao modelo; emendas são
  registradas, nunca silenciosas.

Critérios principais: **A1** inversão de polaridade (item `funcionou` contado
como falha ou vice-versa), **A1r** rebaixamento de item que funcionou fora da
seção de lacunas, **A2** contagem de itens `não verificado` afirmados como fato
sem ressalva, **A5** máquina, local, causa ou ação sem item-fonte, **C1**
pendências primeiro, **C3** três listas separadas (funcionou / falhou / não
verificado), **C4** nenhuma lacuna falsa.

## 2. Runtime — o mesmo GGUF no Windows 11 e no WSL2

llama.cpp `llama-server` b11053 (commit `1af554f`), CUDA 13.4, `sm_120`, mesmos
bytes de GGUF, timings do próprio servidor, 3 repetições × 3 tamanhos de prompt.

| Modelo | Geração WSL → Windows (tok/s) | Prefill longo WSL → Windows (tok/s) |
|---|---|---|
| qwen3.8-27B Q4, base | 74,2 → 76,2 | 3.074 → 3.494 |
| **qwen3.8-27B Q4, ajustado** | 75,2 → 76,3 | 3.492 → 3.584 |
| NVFP4, base | 74,3 → 76,5 | 3.612 → 4.762 |
| **NVFP4 + MTP, ajustado** | **126,7 → 125,8** | 3.494 → 4.275 |
| Hemmingway-1 Q4, ajustado | 72,7 → 74,0 | 3.579 → 3.628 |
| **Qwen3.8-35B-A3B APEX + MTP** | **271,9 → 302,4** | 7.134 → 8.331 |

- Os ajustes foram decididos por regras congeladas antes de medir:
  `-ub 1024 -b 4096` adotado (+8% no prefill longo); `-fa on` recusado (prefill
  −2,6%); KV `q8_0` só medido (mais lento); **MTP `--spec-draft-n-max 2`**
  adotado no NVFP4 (+70% na geração, 68% de aceitação). A cabeça MTP do APEX vem
  em arquivo separado (`-md … --spec-type draft-mtp`): +17% (WSL) / +24%
  (Windows).
- **Mesmo texto nos dois sistemas:** com as mesmas flags, 79 de 80 respostas de
  síntese saíram idênticas byte a byte WSL × Windows; a exceção é NVFP4 + MTP com
  t = 0,3 (o MTP não é totalmente determinístico). Um 8/16 aparente antes vinha
  de misturar runs com e sem `-ub/-b`, que muda o texto.
- O MTP muda o texto gerado em relação ao sem MTP, mesmo com t = 0.
- Um `llama-server.exe` iniciado do WSL pelo interop mantém a sessão SSH
  aberta; quem lança não pode esperar por ele.

## 3. Qual modelo local para a síntese

Prompt `atual` (o de produção), 16 runs por modelo no WSL, depois amostra
humana cega de 6 por modelo.

| Modelo | A1 inversão | A2 ≥ 6 itens | A5 sem fonte | C1 |
|---|---|---|---|---|
| `qwen3-coder-30b` de produção (referência) | inverte um fato-chave na pré-triagem | 8/8 (rodada anterior) | — | 0 |
| qwen3.8-27B Q4 | 2/6 *(arbitrado)* | 5–6/6 | 4/6 | 5/6 |
| NVFP4 + MTP | 2/6 *(arbitrado)* | 4–6/6 | 6/6 | 6/6 |
| APEX 35B-A3B + MTP | **5/6** *(arbitrado)* | 5–6/6 | 6/6 | 0/6 |

- **A2 e A5 aparecem com todos os modelos** — vêm do prompt, não do modelo. Isso
  redirecionou o trabalho para o prompt (seções 4–6).
- Q4 e NVFP4 ficam equivalentes em A1 nesta amostra; o APEX fica registrado como
  **sinal de risco** (n = 6, decidido por arbitragem). O APEX também entra em
  loop com t = 0,3 (2/16 respostas foram até o limite de contexto), como o autor
  avisa para uso guloso.
- Avaliados e não seguidos: Ternary Bonsai (PQ2/PTQ1, exige o fork PrismML;
  errou o fato-chave 0/4), Xing4.0-29B-A4B (exige um PR não aceito do llama.cpp;
  apagado), TAARDIS ternário, variantes *abliterated* (sem ganho para a tarefa).

## 4. Campanha de prompt: `atual` × `v2` × `v3` (modelo de produção)

18 respostas nunca vistas (6 por braço, t = 0,3, seeds 48/49). A1r, A5 e C2
reprovaram no gate de concordância e foram arbitrados.

| | atual | v2 | v3 |
|---|---|---|---|
| A2 (soma das faixas, máx. 18) | **13,5** | 17,0 | 15,5 |
| A5 | 6/6 | 2/6 | 2/6 |
| C1 | 0/6 | 6/6 | 6/6 |
| C3 | 0/6 | 4/6 | 4/6 |
| A1 | 3/6 | 0/6 | 0/6 |
| tokens de saída | 1,3k–1,6k | 5k–9k | 5k–8,7k |

**O v3 não reduz o A2 e não devolve o A5.** As respostas do v2/v3 são 4–6× mais
longas e batem no contexto de 16K no recorte mais longo.

## 5. De onde vem o A2

**H-LEDGER-A2** (v3 com × sem o *ledger* JSON final, 9 cada, A2 ρ = 0,986): sem
o ledger, o A2 absoluto cai (média 16,2 → 13,8), mas **o A5 volta (2/9 → 8/9) e
o C4 piora (8/9 → 4/9)**. O ledger fica.

> **Correção.** Este registro disse primeiro que "o A2 por 1k tokens sobe sem o
> ledger, então o efeito é do comprimento". Era um **artefato do denominador**:
> o ledger é ~58% da saída e quase não tem violações. Contra a prosa, a
> densidade de A2 é *maior* com o ledger (1,67 × 1,31 por 1k caracteres). A
> leitura original fica no relatório bruto; esta é a corrigida.

**H-PROSA-A2** (regra de atribuição congelada antes, 24 violações sorteadas
validadas à mão, lugar confirmado em 24/24): **toda violação A2 resolvida está
na prosa, nenhuma no ledger** — o ledger rotula `não verificado` corretamente em
254 de 256 entradas casadas. Densidade de A2 na prosa 5,39 / 3,14 por 1k tokens
(rev-1 / rev-2) contra 0,02 no ledger.

## 6. `v3-compact` e a janela de contexto

**H-PROSA-COMPACT**: tirar a árvore em texto e a forma visual (as duas já estão
no ledger), todo o resto igual byte a byte. 9 por braço, A2 ρ = 0,84.

| | v3 | v3-compact |
|---|---|---|
| A2 da prosa (rev-1 / rev-2) | 145 / 96 | **52 / 38** |
| A2 da prosa por 1k tokens | 5,22 / 3,45 | **2,54 / 1,86** |
| A2 do ledger | 1 / 1 | 0 / 0 |
| C1 · C3 · A5 · C4 | 9 · 5 · 2 · 4 | 9 · **7** · 2 · **6** |

O A2 da prosa cai à metade em absoluto e em densidade; nenhuma proteção
regride. Por bloco, ~40% das violações do v3 estavam **só** na árvore em texto
ou na forma visual; o que sobra no compact fica no **bloco de pendências**.

**H-NCTX-COMPACT**: o compact ainda cortava no recorte mais longo com 16K. KV
cache f16 = 96 KiB/token neste modelo → 32K custa +1,5 GiB; medido +1,43 GiB.
Com 32K os dois casos cortados terminam em `stop`, sem perda de vazão
(226 → 229 e 224 → 232 tok/s). São gerações novas, não o mesmo texto
completado. A produção agora roda com 32K; o compact virou candidato de sombra.

## 7. Teste de mesa determinístico (A2 / A5 / C1 sem humanos)

| Versão | Onde foi medido | A2 Spearman rev-1 / rev-2 | C1 | Resultado |
|---|---|---|---|---|
| v1 | 54 respostas avaliadas | 0,276 / 0,149 | 100% | recusado |
| v2 | as mesmas 54 (in-sample) | 0,871 / 0,850 | 100% | só provisório |
| v2 | **lote da sombra V1** (20 novas) | 0,719 / 0,753 | 100% | **reprovado** |
| v3 (última) | **lote da sombra V2** (20 novas) | 0,752 / 0,670 | 100% | **reprovado** |

- A v1 punia respostas que listam os itens certo sob o subtítulo "Não
  verificado" (a ressalva está no subtítulo); a v2 herdou a ressalva e corrigiu;
  a v3 acrescentou a árvore do ledger, o item lógico e os itens curtos.
- No lote V2 os dois humanos concordaram só ρ = 0,782 entre si (0,965 no V1): o
  teto do teste ficou abaixo do próprio limiar.
- **Desfecho:** o teste de mesa é **indicador, não gate**. O C1 é confiável
  (100% em todos os lotes). O A5 por entidades nomeadas é só descritivo.

## 8. Decisões tipadas: Laya, Jev, Eikos

Mesmo lote rotulado (27 casos, um positivo por pergunta — sinal de direção, não
número fino).

| Sistema | `encerra`: posição do positivo | `quem_decide`: precisão / acc / posição | margem acerto × erro | latência |
|---|---|---|---|---|
| trivial "sempre não" | empate | — / 0,95 | — | — |
| Laya (22/09 e 24/09, pacote 0.3.17) | 5º | 0,06 / 0,25 / 5º | 0,37 × 0,53 (invertida) | 0,03 s |
| Jev (hospedado) | 1º | 0,25 / 0,85 / 1º | 0,69 × 0,20 | 0,66 s |
| Eikos-4B (local) | 4º | 0,33 / 0,90 / 2º | 0,60 × 0,37 | 0,11 s |
| **Eikos-27B-INT4 (local, vLLM)** | **1º** | **0,33 / 0,90 / 1º** | **0,69 × 0,21** | **0,14 s** |

- **O Eikos-27B empata ou supera o Jev hospedado neste lote**, roda local (os
  dados não saem da máquina), é determinístico e ~4,7× mais rápido. Exige vLLM
  ≥ 0,30 (`--enforce-eager` aqui: a captura de CUDA graphs travou) e ~26 GB de
  VRAM, então não cabe junto do modelo de produção.
- O `laya-multilingual` atualizado reproduziu exatamente os scores de 22/09
  (27/27).
- **Experimento 1** — o modelo tipado só filtra os candidatos de A2 do teste de
  mesa ("este trecho afirma o item como fato?"): nenhum sistema leva o teste
  acima de 0,80 no lote V2 (Jev 0,650/0,736, Eikos-4B 0,740/0,742, Eikos-27B
  0,746/0,715); no lote V1 todo filtro piora. O gargalo é a pergunta, não o
  modelo.

## 9. Custo operacional e lições

- **Trocar a produção pelo Eikos-27B e voltar** custa ~4 min na ida (pesos em 1
  min 53 s de `/mnt/e` pelo sistema de arquivos 9P do WSL, perfil do vLLM ~1 min
  40 s) e ~2 min na volta — ~6 min sem o modelo de produção.
- Um `llama-server` parado pode soltar a porta e continuar segurando 21,6 GB de
  VRAM; pare servidores pelo pid da porta, mate o grupo de processos e espere a
  VRAM ser liberada de fato.
- Nunca `pkill -f` / `pgrep -f` com texto que aparece no próprio comando.
- No Herdr, uma linha esmaecida (`ESC[2m`) na caixa de um pane é sugestão do
  CLI, não rascunho humano; leia com `--format ansi` antes de decidir.
- Com a produção fora, um cliente desconhecido carregou um modelo no serviço
  Ollama do Windows, e algo consultou `GET /props` na porta do vLLM. O controle
  de quem usa cada serviço e um comando de pausar/retomar foram levados ao
  projeto do gateway.

## Ferramentas

`tools/os_runtime_ab.py`, `tools/optimization_campaign.py`,
`tools/synthesis_wsl_campaign.py`, `tools/guardian_synthesis_bench.py`,
`tools/guardian_agreement.py`, `tools/h_prosa_attribution.py`,
`tools/h_block_attribution.py`, `tools/desk_test.py` (v1),
`tools/desk_test_v2.py`, `tools/desk_test_v3.py`,
`tools/shadow_lot_forms.py`, `tools/typification_eval.py`,
`tools/jev_hybrid_a2.py`, `tools/eikos27_window.sh`.
