# Q4_K_M do Ollama (produção) × Q4_K_M da Unsloth: qwen3-coder-30b (24–25/09/2026)

Resumo público. As respostas, os formulários dos avaliadores e o log da janela ficam na máquina do laboratório
(evidência do Guardian, ignorada pelo git), como no resto do repositório.

## Pergunta e desenho

O Q4_K_M da Unsloth (imatrix + template de chat próprio) muda a síntese do Guardian em relação ao Q4_K_M do Ollama
usado em produção?

- Regras congeladas antes de gerar (`REGRAS.json`, sha `edf8790e…`, 24/09 23:32), autorizadas pelo owner.
- Braços: Ollama `qwen3-coder:30b` (blob `sha256-1194192c…006a`) × Unsloth
  `Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf` (sha `fadc3e5f…88ad`, HF commit `b17cb02d…`).
- Constante: llama-server b11053 (WSL), `-ngl 99 --ctx-size 32768 --jinja --temp 0 --parallel 1`; prompt
  `v3-compact`; t = 0,3; cada braço com o template embutido no próprio arquivo (parte do que se compara).
- 9 respostas por braço, pareadas: seeds 56/57 nos 4 cenários (S1–S4) + seed 58 em S2; ordem embaralhada;
  rubrica 4, avaliadores cegos `rev-1` e `rev-2`, mais o teste de mesa v3.

## Diferenças entre os arquivos

Mesma distribuição de tipos (289 Q4_K / 49 Q6_K / 241 F32). A Unsloth usa imatrix (154 blocos) e template de chat
próprio; os dois templates geram exatamente o mesmo número de tokens de entrada nos 4 cenários.

## Resultado

| | Ollama | Unsloth |
|---|---|---|
| geração (tok/s, mediana) | 237,6 | 241,7 |
| tokens de saída (mediana) | 5.925 | 5.527 |
| `finish` | 9 × stop | 9 × stop |
| A2 total, rev-1 | 93 | 81 |
| A2 total, rev-2 | 52 | 22 |
| A2 total, teste de mesa v3 | 84 | 71 |
| pares com Unsloth menor | rev-1 5/9 · rev-2 6/9 · mesa 6/9 | |
| A1 | 1/9 | 0/9 |
| A1r | 2/9 (+1 div.) | 4/9 |
| C1 / C3 / C4 | 9/9 · 4/9 (+2 div.) · 4/9 | 9/9 · 5/9 · 5/9 |

O prefill não é comparável nesta rodada: o servidor reaproveitou o cache do prompt entre chamadas do mesmo cenário.

## Concordância

O A2 não foi mensurável entre avaliadores (ρ = 0,196; o A5 também reprovou). A causa é ambiguidade da rubrica
num formato novo do `v3-compact`: as pendências escrevem o item e depois o repetem como pergunta. O `rev-1` conta a
afirmação (mesma leitura do teste de mesa); o `rev-2` trata a pergunta como ressalva. A divergência de
interpretação apareceu em 11 de 18 respostas. Pela regra congelada, o critério iria para arbitragem cega; ela não
foi feita (desvio registrado, pendente de decisão do owner).

## Leitura

- Os dois arquivos são praticamente equivalentes em velocidade e em estrutura (C1, C3, C4).
- No A2, os três medidores apontam na mesma direção (Unsloth um pouco menor), mas nos pares o placar é 5–6 de 9,
  compatível com acaso (n = 9). No A1r a Unsloth fica pior (4/9 contra 2/9).
- **Nada aqui justifica trocar o arquivo de produção.**
- A ambiguidade "item + pergunta repetida" precisa de decisão do owner antes de nova rodada com o `v3-compact`.

Nota de 30/09/2026: o arquivo da Unsloth foi apagado do disco na limpeza de 30/09; fica no disco só o do Ollama.
