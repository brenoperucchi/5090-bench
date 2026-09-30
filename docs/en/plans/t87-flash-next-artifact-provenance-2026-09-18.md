# T87 — Proveniência do artefato do resultado Qwen3.8 17/17

- status: **ambiguous**
- classification: **(c) ambiguous**
- observed_at: 2026-09-18
- method: leitura local e consulta pública somente; nenhum GGUF do Flash-Next foi baixado e nenhuma GPU foi usada
- decision: não iniciar teste de quantização nem chamar um candidato por “parecença” de nome

## Pergunta

Qual artefato exato produziu o resultado publicado como `Qwen3.8-Flash-Next
125B, IQ3_XXS, RTX 3060 12 GB, ~19 tok/s, 17/17` no `spec-wins`?

## Evidência confirmada

1. O README público do `thecodacus/spec-wins` registra o scorecard de 17/17
   como `Qwen3.8-Flash-Next 125B (IQ3_XXS, RTX 3060 12 GB, ~19 tok/s)`. Ele
   também registra o `Qwen3.6-35B-A3B Q4_K_M` como 14/17. A entrada não informa
   repositório de pesos, nome de arquivo, shards, SHA-256, RAM do host ou
   revisão exata do runtime.
2. O resultado histórico `t1-qwen38-flash.md`, no commit pinned
   `776e799c7e0a24271e021aca2ea4b1c1b1f10017`, identifica a configuração como
   `qwen38-flash (Codacus fork, router, 64k/1 slot/48 cache/MTP-CPU)`. Também
   não contém nome de GGUF, shards ou hash dos pesos.
3. A história visível do `spec-wins` contém o resultado, mas não contém um
   snapshot pré-corrida que vincule o resultado a um arquivo de pesos ou a uma
   revisão completa do ambiente.
4. O README atual do fork `thecodacus/llama.cpp`, na branch `perf`, documenta
   `Qwen3.8-Flash-Next 177B UD-IQ3_XXS` e suporte `qwen4exp`. Isso demonstra um
   candidato atual do fork, não que esse foi o artefato usado no resultado
   histórico de 125B/IQ3_XXS.

## Candidatos públicos e limites

| candidato | a favor | contra / não comprovado |
|---|---|---|
| Artefato histórico não nomeado: Qwen3.8-Flash-Next 125B, IQ3_XXS | coincide com o scorecard e com a configuração publicada | arquivo, shards, origem, hashes, RAM original e revisão completa não publicados |
| `Qwen3.8-Flash-Next` público `IQ3_XXS` (por exemplo, listing da bartowski) | nome e rótulo de quantização coincidem | não há evidência de que tenha sido usado na corrida; listing atual não prova identidade histórica |
| `unsloth/Qwen3.8-Flash-Next-GGUF`, `UD-IQ3_XXS` | é um artefato público atual compatível com o README atual do fork | identidade publicada é 177B/qwen4exp, não 125B; split atual tem três shards e aproximadamente 81.96 GB; não pode substituir silenciosamente o scorecard |

O artefato histórico não foi classificado como extinto/não publicado porque
existem candidatos públicos com nomes relacionados. Eles, porém, permanecem
sem vínculo comprovado com a corrida de 2026-09-05. Portanto o resultado é
**ambíguo**, não “identificado” e não “extinto”.

## O que falta para desempatar

É necessário obter do autor da corrida, ou de um snapshot público verificável:

- repositório/origem dos pesos;
- nome exato de cada shard e SHA-256 de cada arquivo;
- identidade estrutural do modelo (125B versus 177B/qwen4exp);
- revisão/commit exato do fork e configuração do router/expert cache;
- RAM do host original e parâmetros relevantes de offload/cache.

Pergunta a enviar ao autor:

> Qual foi o artefato exato usado para o `Qwen3.8-Flash-Next 125B IQ3_XXS`
> que marcou 17/17 no `spec-wins` em 2026-09-05? Informe a origem pública ou
> privada dos pesos, nome e SHA-256 de cada shard, revisão do runtime, flags do
> router/expert cache, RAM do host e, se o artefato não estiver mais disponível,
> declare explicitamente que ele não foi publicado ou não é recuperável.

## Consequência operacional

O P1 autorizado em `qwen3.6-35b-a3b` é uma medição do par
`(Qwen3.6, thecodacus/llama.cpp, protocolo pinned, rota LAN)` e não é uma
reprodução nem um proxy comprovado do Flash-Next 17/17. A investigação do
artefato Flash-Next deve continuar separada até que a identidade seja
desempatada. Nenhum download de 82 GB está autorizado por este registro.

## Fontes

- [thecodacus/spec-wins](https://github.com/thecodacus/spec-wins)
- [resultado histórico t1-qwen38-flash](https://raw.githubusercontent.com/thecodacus/spec-wins/776e799c7e0a24271e021aca2ea4b1c1b1f10017/results/t1-qwen38-flash.md)
- [README atual do fork thecodacus/llama.cpp](https://raw.githubusercontent.com/thecodacus/llama.cpp/perf/README.md)
- [listing público IQ3_XXS da bartowski](https://huggingface.co/bartowski/Qwen3.8-Flash-Next-GGUF)
- [artefato público UD-IQ3_XXS da unsloth](https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF/tree/main/UD-IQ3_XXS)
