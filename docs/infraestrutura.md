# Infraestrutura da bancada

[English](en/infrastructure.md) | **Português (Brasil)**

> **Historical operational snapshot — through 2026-09-12.**
> This document describes the earlier Windows/Ollama production baseline.
> For the current Guardian research campaign and the WSL/llama.cpp environment,
> see [the current public record](en/findings/public-record-llm-bench-2026-09-20.md).

Esta página descreve o estado registrado no [handoff de 12/09/2026](history/handoff-2026-09-12.md)
e na [decisão de produção](../results/DECISAO-producao-2026-09-09.md).
Não houve consulta ao Ollama durante a organização deste acervo.

| Componente | Estado registrado |
|---|---|
| GPU | NVIDIA GeForce RTX 5090, 32 GB; cerca de 30,3 GiB utilizáveis no cenário documentado |
| Servidor | Ryzen9, Windows nativo, Ollama 0.33.3 |
| Inicialização | Tarefa `OllamaServer` executada como SYSTEM |
| Acesso desta bancada | Túnel SSH com endpoint local `127.0.0.1:11434` |
| Store | `E:\ollama\models`; cópias antigas em C: e D: removidas |
| Modelo default | `qwen3:14b` |
| Segundo residente configurado | `qwen3.5:9b` |
| `OLLAMA_MAX_LOADED_MODELS` | `2` |
| `OLLAMA_NUM_PARALLEL` | `2` |
| `OLLAMA_KV_CACHE_TYPE` | `q8_0` |
| `OLLAMA_CONTEXT_LENGTH` | Não definida; contexto automático dependente do ambiente, não uma garantia por requisição |
| `OLLAMA_FLASH_ATTENTION` | Não definida |

O [runbook original](../MIGRACAO-windows-nativo-2026-09-04.md) preserva a
migração de WSL2 para Windows nativo, os diagnósticos e a configuração da tarefa.
O [script PowerShell](../ollama-restart.ps1) altera processos do servidor e
não deve ser tratado como comando de instalação genérico.

## Memória e interferência entre medições

O `gemma4:26b` não coexiste com `qwen3:14b` na VRAM disponível: carregar um
expulsou o outro. Na bancada compartilhada, o acordo registrado exige combinar
uma janela com `llm-exec` **antes** de carregar o Gemma. O `qwen3.5:9b` cabe
ao lado do default. Ao terminar uma medição que mudou a residência, o procedimento
registrado é descarregar o modelo temporário com `keep_alive:0` e recarregar
`qwen3:14b`. [Fonte](../results/RESULTADO-juiz-familia-2026-09-10.md).

Para o modelo especulativo Gemma, `/api/ps` informa apenas cerca de 1,38 GiB,
omitindo o custo principal. O check de spill da Fase 6 continua com um TODO;
uma igualdade entre `size` e `size_vram` não valida essa residência. A leitura
de camadas no log foi a evidência usada. [Código e ressalva](../baseline-3080ti/repro/fase6_concurrency.py).

## Contexto longo

O caso observado registra 111.288 tokens de entrada, limite de 49.154 e
`keep=4`, com slots de 98.304 tokens. `num_ctx` pedido, alocação por slot,
limite de entrada e tokens efetivamente avaliados são grandezas distintas.
A correção da [Fase 6b](../results/RESULTADO-fase6b-numparallel-contexto-longo-2026-09-12.md)
deixa o mecanismo causal em aberto. A migração de configuração proposta para
testá-lo exige decisão separada; não faz parte desta organização documental.

## Portabilidade

Os endpoints, nomes de tarefas e caminhos Windows dos scripts históricos
descrevem esta bancada. Scripts antigos de tool-calling também importam um
checkout externo do `llm-gateway`. Consulte a [metodologia](metodologia.md)
antes de reutilizar um harness. Dados de placa antiga e CPU são identificados
no [catálogo](rtx5090/experimentos.md).
