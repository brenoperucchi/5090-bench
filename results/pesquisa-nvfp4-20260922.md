# NVFP4 em RTX 5090, Linux e WSL — pesquisa em 22/09/2026

**Escopo:** fontes públicas consultadas em 22/09/2026; nenhum modelo ou benchmark executado nesta pesquisa. Datas abaixo são de publicação/release/merge quando disponíveis. “Consulta 22/09/2026” identifica documentação viva sem data editorial explícita. Uma versão que introduziu o formato não é necessariamente suficiente para uma arquitetura ou checkpoint lançado depois.

**Resultado prático:** para `nvidia/Qwen3.8-27B-NVFP4`, os caminhos documentados são **vLLM e SGLang**. Há receita de SGLang com esse export e RTX 5090. **llama.cpp já suporta NVFP4, inclusive CUDA nativo Blackwell; Ollama também tem execução confirmada de GGUF NVFP4 pelo motor llama.cpp**, além de seu suporte MLX. Isso não demonstra importação direta desse Safetensors específico nos dois últimos. [NVIDIA, lançamento 08/09/2026](https://huggingface.co/nvidia/Qwen3.8-27B-NVFP4); [SGLang, documentação consultada 22/09/2026](https://docs.sglang.io/cookbook/autoregressive/Qwen/Qwen3.8-27B); [llama.cpp b8967, 29/04/2026](https://github.com/ggml-org/llama.cpp/releases/tag/b8967); [Ollama, confirmação 01–02/07/2026](https://github.com/ollama/ollama/issues/16056#issuecomment-4858809201).

## 1. Runtimes e versões

| Runtime | Marco verificável de suporte | Situação relevante para a RTX 5090 e o checkpoint solicitado |
|---|---|---|
| **vLLM** | **v0.8.0, 18/03/2025**, inclui carregamento de checkpoints ModelOpt FP4, PR #12520 integrado em 12/03. **v0.10.1, 18/08/2025**, acrescenta CUTLASS NVFP4 W4A4 em **SM120 / RTX 5090**, PR #21309. | Serve NVFP4 diretamente, mas não basta instalar a versão histórica mínima para servir Qwen3.8. A ficha NVIDIA usa imagem `nightly`; a receita específica registra testes em `0.26.1rc1.dev608+g99a10304d` para outros exports NVFP4 do mesmo modelo. **Não achei uma versão estável mínima garantida para o export NVIDIA exato.** [v0.8.0](https://github.com/vllm-project/vllm/releases/tag/v0.8.0), [v0.10.1](https://github.com/vllm-project/vllm/releases/tag/v0.10.1), datas acima; [receita, consulta 22/09/2026](https://recipes.vllm.ai/Qwen/Qwen3.8-27B); [ficha NVIDIA, 08/09/2026](https://huggingface.co/nvidia/Qwen3.8-27B-NVFP4). |
| **TensorRT-LLM** | **v0.17.0, 07/02/2025**: NVFP4 GEMM, Llama/Mixtral e APIs de inferência em Blackwell. Para **SM120**, suporte explícito a GEMM/MoE NVFP4 em **v0.20.0rc2, 13/05/2025**, PR #3770; versão estável **v0.20.0, 19/06/2025**. | É runtime NVFP4, mas suporte Blackwell de datacenter não implica automaticamente todos os kernels de GeForce. **Não achei validação primária do checkpoint `nvidia/Qwen3.8-27B-NVFP4` no TensorRT-LLM**; a ficha desse modelo lista vLLM/SGLang. [v0.17.0](https://github.com/NVIDIA/TensorRT-LLM/releases/tag/v0.17.0), [v0.20.0rc2](https://github.com/NVIDIA/TensorRT-LLM/releases/tag/v0.20.0rc2), [v0.20.0](https://github.com/NVIDIA/TensorRT-LLM/releases/tag/v0.20.0), datas acima; [ficha, 08/09/2026](https://huggingface.co/nvidia/Qwen3.8-27B-NVFP4). |
| **SGLang** | **v0.4.5, 07/04/2025** trouxe os kernels FP4; **v0.4.6, 27/04/2025** inclui carregamento e inferência FP4, PR #3972 integrado em 09/04. | Para o modelo solicitado há validação atual da receita em **v0.5.19**, incluindo export NVIDIA e RTX 5090. É um marco confirmado de funcionamento, não uma afirmação de que seja a primeira versão capaz de rodá-lo. [v0.4.5](https://github.com/sgl-project/sglang/releases/tag/v0.4.5), [v0.4.6](https://github.com/sgl-project/sglang/releases/tag/v0.4.6), datas acima; [receita, consulta 22/09/2026](https://docs.sglang.io/cookbook/autoregressive/Qwen/Qwen3.8-27B). |
| **llama.cpp / llama-server** | Tipo GGUF NVFP4, CPU e conversão ModelOpt integrados em **11/03/2026**, PR #19769. CUDA nativo Blackwell integrado em **28/04/2026**, PR #22196, publicado como **b8967 em 29/04/2026**. | **Sim**, há suporte upstream, não apenas uma proposta. Precisa de **GGUF convertido/reempacotado** e build CUDA apropriado; não equivale a servir arbitrariamente um diretório HF Safetensors. Há correções posteriores para checkpoints mistos e cabeça NVFP4; b8967 é marco histórico, não recomendação para esse export de setembro. [PR #19769](https://github.com/ggml-org/llama.cpp/pull/19769), [PR #22196](https://github.com/ggml-org/llama.cpp/pull/22196), [b8967](https://github.com/ggml-org/llama.cpp/releases/tag/b8967), datas acima; [cabeça NVFP4, 16/05/2026](https://github.com/ggml-org/llama.cpp/pull/23046). |
| **Ollama** | Importação NVFP4 no MLX integrada em **24/03/2026**, PR #15015. Execução **GGUF NVFP4 no motor llama.cpp confirmada em v0.31.1**, release de **30/06/2026**, com testes publicados em 01–02/07. | **Sim, com distinção entre motores.** MLX/macOS não prova CUDA, mas os comentários posteriores mostram GGUF pelo motor llama.cpp e confirmação em Blackwell. Não identifiquei a primeira versão exata que introduziu o caminho CUDA; **0.31.1 é a primeira versão explicitamente confirmada nas fontes verificadas**. Não achei teste do Qwen3.8 NVIDIA exato convertido e servido no Ollama. [PR MLX](https://github.com/ollama/ollama/pull/15015), [v0.31.1](https://github.com/ollama/ollama/releases/tag/v0.31.1), [teste 01/07](https://github.com/ollama/ollama/issues/16056#issuecomment-4858809201), [Blackwell 02/07](https://github.com/ollama/ollama/issues/16056#issuecomment-4865912303), [explicação do motor 02/07](https://github.com/ollama/ollama/issues/16056#issuecomment-4866857329). |

### Estado de llama.cpp e Ollama: o que não confundir

No llama.cpp, o suporte começou com armazenamento/conversão e execução genérica, antes do kernel NVFP4 × NVFP4 acelerado em Blackwell. O PR original do kernel, #21896, foi fechado por problema de rebase e restaurado como **#22196, que foi integrado**. Portanto, olhar apenas o primeiro PR fechado leva a uma conclusão errada. O ganho anunciado pelo autor era principalmente de prefill, não de geração token a token. [PR original, 14/04/2026](https://github.com/ggml-org/llama.cpp/pull/21896); [restauração integrada, 28/04/2026](https://github.com/ggml-org/llama.cpp/pull/22196).

No Ollama, a issue #16056 permanece aberta na consulta, mas **isso não significa ausência de suporte atual**: a resposta de 09/05 dizia “MLX/macOS”; os comentários de julho mostram execução GGUF no motor llama.cpp, após atualização do motor para build 9840 na v0.31.1. Melhorias anunciadas em **v0.32.10, 12/08/2026**, de 7–8% no prefill NVFP4 referem-se a **MLX**, não à RTX 5090. [Histórico completo da issue, 09/05–02/07/2026](https://github.com/ollama/ollama/issues/16056); [v0.31.1, 30/06/2026](https://github.com/ollama/ollama/releases/tag/v0.31.1); [v0.32.10, 12/08/2026](https://github.com/ollama/ollama/releases/tag/v0.32.10).

## 2. Qualidade publicada em modelos de 20–35B

### Medição independente: Qwen3.8-27B, BF16 versus FP8 versus NVFP4

**Autor Rieker**, publicação inicial **09/09/2026**, inclusão do export NVIDIA em **12/09/2026**. DGX Spark GB10, vLLM nightly; perplexidade WikiText-2 em 323 janelas; MBPP com 257 problemas, HumanEval com 164, GSM8K com 500. Geração greedy com thinking desligado nesses testes; teste separado de ferramentas tem apenas 20 cenários. A fonte informa configuração e metodologia, mas não é estudo revisado nem apresenta intervalos de confiança. [Medição original e histórico](https://huggingface.co/Qwen/Qwen3.8-27B/discussions/192), 09–12/09/2026.

| Variante do mesmo Qwen3.8-27B | PPL ↓ | MBPP % | HumanEval % | GSM8K % |
|---|---:|---:|---:|---:|
| BF16 | 7,993 | 70,8 | 93,3 | 97,0 |
| FP8 | 8,029 | 69,3 | 95,1 | 97,4 |
| NVFP4 NVIDIA | **8,139** | **70,4** | **94,5** | **97,2** |
| NVFP4 Unsloth | 8,131 | 68,9 | 95,1 | 97,2 |
| NVFP4 Radix, cabeça BF16 | 8,286 | 70,0 | 91,5 | 97,0 |
| NVFP4 Radix, cabeça FP4 | 8,385 | 70,0 | 93,9 | 97,4 |

**Fonte de todas as células:** [Rieker, atualização 12/09/2026](https://huggingface.co/Qwen/Qwen3.8-27B/discussions/192). A PPL NVIDIA aumenta aproximadamente **1,83% sobre BF16** e **1,37% sobre FP8** — cálculos a partir da tabela, não números adicionais medidos. A oscilação de alguns acertos nos benchmarks não demonstra superioridade do quantizado. Todos marcaram 100% no pequeno teste de ferramentas; isso não elimina falhas em sessões longas.

O mesmo teste registra divergência KL texto/código de **0,0758/0,0297** para NVIDIA e **0,0117/não disponível** para FP8. O caso indisponível é NaN nos logprobs de prompts de código do FP8, não uma falha de geração atribuível ao NVFP4. Os resultados também mostram que “NVFP4” não define sozinho a fidelidade: export, calibração e camadas preservadas mudam o resultado. [Rieker, 12/09/2026](https://huggingface.co/Qwen/Qwen3.8-27B/discussions/192).

### Medição independente: comparação com Q4/INT4 em 27B

**thr3e, 19/08/2026**, comparou exports de Qwen3.8-27B usando **7.114 tokens reais de respostas**, extraídos de dois fluxos técnicos com ferramentas; profundidades de contexto entre aproximadamente 18,8K e 123,6K. Candidatos na RTX 5090 e referência BF16 na RTX PRO 6000 Blackwell; mesmo tokenizer, execução eager, atenção Triton, KV BF16, MTP e thinking desligados. A diferença de placa da referência é uma limitação. Isso mede divergência nos tokens amostrados, não taxa de sucesso de agentes. [Experimento original](https://forum.level1techs.com/t/qwen-3-8-quant-selection-guide-for-rtx-5090/254095), 19/08/2026.

| Export / quantização | Mudanças do token top-1 contra BF16 ↓ | KL mediana ↓ | KL percentil 95 ↓ |
|---|---:|---:|---:|
| cyankiwi AWQ INT4 assimétrico, grupo 32, W4A16 | **2,193%** | 0,00003475 | **0,04826** |
| Unsloth NVFP4 misto W8A8/W4A4 | 2,586% | 0,00004580 | 0,06029 |
| dbirks AutoRound INT4, grupo 128 | 2,966% | 0,00007520 | 0,11872 |
| philbert AWQ INT4, grupo 128 | 3,388% | 0,00007198 | 0,09133 |
| Radix NVFP4 misto | 4,484% | 0,00007147 | 0,14041 |

**Fonte de todas as células:** [thr3e, 19/08/2026](https://forum.level1techs.com/t/qwen-3-8-quant-selection-guide-for-rtx-5090/254095). Nesse recorte, AWQ grupo 32 foi mais fiel que os exports NVFP4 testados. **O checkpoint NVIDIA de setembro não participou. AWQ INT4 não é GGUF Q4_K_M.** Não achei comparação controlada de PPL/benchmarks do checkpoint NVIDIA solicitado contra Q4_K_M em 27B. Não há fundamento nessas fontes para dizer que NVFP4 sempre supera “Q4”.

### Medições do fabricante: não são validação independente

A **NVIDIA**, na ficha lançada em **08/09/2026**, publica os seguintes resultados para Qwen3.8-27B, medidos com **vLLM em Grace Blackwell GB300**, temperatura 1, top-p 0,95, contexto 262.144; limite de geração 65.536, com exceção descrita para Terminal-Bench. Não são medições na RTX 5090. [Ficha e protocolo do fabricante](https://huggingface.co/nvidia/Qwen3.8-27B-NVFP4), 08/09/2026.

| Benchmark | BF16 | NVFP4 NVIDIA | Diferença NVFP4 − BF16, pontos |
|---|---:|---:|---:|
| GPQA Diamond | 88,92 | 88,01 | −0,91 |
| Terminal-Bench | 75,56 | 74,02 | −1,54 |
| AA-LCR | 72,63 | 73,38 | +0,75 |
| MMMU-Pro | 75,14 | 74,86 | −0,28 |
| SciCode | 47,93 | 48,41 | +0,48 |
| IFBench | 80,07 | 78,93 | −1,14 |

**Fonte de todas as células:** [NVIDIA, 08/09/2026](https://huggingface.co/nvidia/Qwen3.8-27B-NVFP4); diferenças calculadas. A ficha não fornece nessa tabela comparativo FP8 ou Q4 nem intervalos de confiança. Não interpretar pequenas altas como melhoria comprovada.

### Medições dos desenvolvedores de runtime

A receita **SGLang** informa validação em **v0.5.19**, com GSM8K completo de **1.319 questões por configuração**. No export NVIDIA, as 15 combinações executáveis na RTX 5090 pontuam **93,93–94,92%**. Isso confirma funcionamento em várias configurações, mas não constitui comparação BF16/FP8/NVFP4 perfeitamente pareada: hardware e combinações viáveis variam. É evidência dos mantenedores do runtime, separada tanto da ficha NVIDIA quanto de avaliações independentes. [Receita SGLang, consulta 22/09/2026](https://docs.sglang.io/cookbook/autoregressive/Qwen/Qwen3.8-27B).

O autor do kernel llama.cpp relata, para **Nemotron-Cascade-2-30B**, PPL **9,81 → 9,85** ao trocar o caminho de ativações Q8 pelo NVFP4 nativo. É uma comparação de kernels/precisão de ativações, **não BF16 versus checkpoint NVFP4**, e o trecho não documenta suficientemente o corpus para juntar esse número ao WikiText acima. [PR #21896, 14/04/2026](https://github.com/ggml-org/llama.cpp/pull/21896).

## 3. Velocidade em RTX 5090 e outras Blackwell de uso local

| Origem e data | Hardware / modelo / configuração | Resultado publicado | Limites de interpretação |
|---|---|---|---|
| **Independente, relato específico do checkpoint**, 10/09/2026 | RTX 5090, `nvidia/Qwen3.8-27B-NVFP4`; MTP com 1–3 tokens | Decode **68 tok/s sem MTP → aproximadamente 50 tok/s com MTP**. Autor menciona cerca de 100 tok/s em Qwen3.6-27B NVIDIA com MTP. | Sem versão, tamanho do prompt, concorrência ou protocolo completo; não é benchmark controlado nem prova de regressão geral do MTP. [Issue #5](https://huggingface.co/nvidia/Qwen3.8-27B-NVFP4/discussions/5). |
| **Independente, experimento comparativo**, atualizado 12/09/2026 | **DGX Spark GB10**, 128 GB unificados; Qwen3.8-27B; vLLM nightly, contexto configurado em 262K, KV FP8, MTP com 5 tokens; 10 prompts | Médias: **NVIDIA NVFP4 38,55 tok/s**, Unsloth NVFP4 31,21, FP8 20,58, BF16 14,61. NVIDIA varia de 32,85 a 45,85. | GB10 é máquina de desenvolvimento local, **não RTX 5090**. Contexto configurado não significa que todos os prompts tinham 262K. Inclui ganho de especulação; não mede isoladamente o kernel NVFP4. [Experimento](https://huggingface.co/Qwen/Qwen3.8-27B/discussions/192). |
| **Mantenedores SGLang**, documentação consultada 22/09/2026 | RTX 5090, família Qwen3.8-27B NVFP4; DFlash2, estado GDN BF16 | Melhor configuração indicada: **TPOT mediano 4,92 ms**, aceitação média 4,29 tokens; aproximadamente **203 tok/s**, recíproco calculado do TPOT. | Resultado com modelo especulativo auxiliar. Não atribuir automaticamente ao export NVIDIA: a receita reúne vários exports. A página declara que a nova rodada de validação v0.5.19 **não refez throughput/aceitação**. [Receita](https://docs.sglang.io/cookbook/autoregressive/Qwen/Qwen3.8-27B). |
| **Mantenedores SGLang**, consulta 22/09/2026 | RTX 5090, Qwen3.8-27B, EAGLE | NVFP4: **152,9 tok/s/usuário** com estado FP32 e **144,5** com BF16; FP8: **106,3 / 116,1**, respectivamente. | Novamente especulação e configurações distintas; estado BF16 nem sempre é mais rápido. Não é comparação isolada de formato. [Receita](https://docs.sglang.io/cookbook/autoregressive/Qwen/Qwen3.8-27B). |
| **Independente, guia experimental de baixa confiança**, 26/11/2025 | RTX 5090, Linux kernel 6.14, driver 580, Qwen3-30B-A3B MoE, TensorRT-LLM 1.2.0rc4 **modificado** | Autor declara **~135 tok/s**, **158,4 tok/s agregados com 5 requisições**, 24,1 GB VRAM. | README mistura referências a versões/modelos, não detalha comprimentos do teste e usa patch C++ com vazamento intencional de memória. Não é validação reproduzida nem recomendação de instalação. MoE 30B não equivale ao denso 27B. [Repositório e relatório do autor](https://github.com/JohnTDI-cpu/trtllm-nvfp4-blackwell-fix). |

Como evidência adicional de engenharia, o PR llama.cpp de **14/04/2026** apresenta Qwen3.5-27B com prefill `pp512` **3.208,98 → 4.691,13 tok/s** e geração `tg128` **65,64 → 66,21 tok/s** ao introduzir o kernel nativo. **Não identifiquei a placa da tabela inicial com segurança**, por isso não a classifico como benchmark RTX 5090. A comparação é antes/depois do kernel sobre NVFP4, não NVFP4 contra GGUF Q4. [PR original](https://github.com/ggml-org/llama.cpp/pull/21896), 14/04/2026.

No Ollama v0.31.1, um colaborador publicou Gemma4-26B-A4B GGUF NVFP4 a cerca de **150 tok/s**, contra aproximadamente **201–203 tok/s em Q4_K_M**, e outro usuário confirmou o comportamento em Blackwell. O primeiro comentário não identifica a GPU; **não atribuo esses números à RTX 5090**. Também não é avaliação de qualidade: o teste consiste em uma solicitação curta com lista de palavras, e o colaborador observa que só 90 de 838 tensores daquele GGUF eram NVFP4. [Teste de 01/07/2026](https://github.com/ollama/ollama/issues/16056#issuecomment-4858809201); [confirmação e explicação de 02/07/2026](https://github.com/ollama/ollama/issues/16056#issuecomment-4866857329).

**Não achei medição controlada Linux nativo versus WSL2 de NVFP4 na mesma RTX 5090**, nem uma bateria independente completa do checkpoint NVIDIA exato que compare velocidade e qualidade contra BF16, FP8 e Q4 na mesma 5090. Os números acima não devem ser combinados em um ranking entre runtimes: prompts, caches, concorrência, especulação e modelos diferem.

## 4. `nvidia/Qwen3.8-27B-NVFP4`: requisitos e problemas

### O que o checkpoint realmente contém

Lançado em **08/09/2026**, tem 27B parâmetros e arquitetura HF `Qwen3_5ForConditionalGeneration`, com texto/imagem/vídeo e contexto nativo 262K. Foi quantizado com **ModelOpt v0.48.0**, calibração Local-Hessian em 2.048 amostras Nemotron Post Training v3. **É misto:** MLP e `lm_head` em NVFP4; self-attention e linear-attention em FP8. Portanto, não estimar seu tamanho como simplesmente 27 bilhões × 4 bits. A medição independente informa **21,92 GB de arquivos**, versus 28,77 GB FP8 e 51,77 GB BF16; tamanho em disco não é VRAM total de execução. [NVIDIA, 08/09/2026](https://huggingface.co/nvidia/Qwen3.8-27B-NVFP4); [Rieker, 12/09/2026](https://huggingface.co/Qwen/Qwen3.8-27B/discussions/192).

A ficha lista **Blackwell e Linux**, motores **vLLM/SGLang**, e fornece exemplos com imagens `nightly`/`dev`. O comando vLLM publicado usa TP=4, mas isso é configuração do exemplo, **não requisito de quatro GPUs**: a receita SGLang testa esse export em uma RTX 5090 de 32 GB. Não achei requisito oficial único de RAM de sistema ou versão mínima do driver para esse checkpoint; dependem do runtime escolhido. [Ficha, 08/09/2026](https://huggingface.co/nvidia/Qwen3.8-27B-NVFP4); [SGLang, consulta 22/09/2026](https://docs.sglang.io/cookbook/autoregressive/Qwen/Qwen3.8-27B).

### Pontos de configuração confirmados

- **Kernels da 5090:** ela usa SM120. A receita SGLang seleciona atenção `flashinfer` em SM120/121; `trtllm_mha` é caminho SM100 nessa receita. O nome Blackwell sozinho não garante compatibilidade de todos os kernels. [SGLang, consulta 22/09/2026](https://docs.sglang.io/cookbook/autoregressive/Qwen/Qwen3.8-27B).
- **KV cache:** o export NVIDIA não traz `kv_cache_scheme`; no SGLang, `auto` deixaria o cache BF16. A receita explicita **`--kv-cache-dtype fp8_e4m3`**. Isso é precisão do cache, separada da precisão dos pesos. [SGLang, consulta 22/09/2026](https://docs.sglang.io/cookbook/autoregressive/Qwen/Qwen3.8-27B).
- **Memória e contexto:** pesos, KV, estados GDN, ativações e CUDA graphs precisam caber juntos. No SGLang, a configuração sem especulação da 5090 usa fração estática 0,90; DFlash2 exige, entre outros ajustes, 0,91 e chunk de prefill 1.024. A receita ajusta também o pool de estados e a relação `--mamba-full-memory-ratio`; não existe um único ajuste universal para todas as modalidades. [SGLang, consulta 22/09/2026](https://docs.sglang.io/cookbook/autoregressive/Qwen/Qwen3.8-27B).
- **OOM no vLLM:** a receita documenta uma 5090 com export **Inferact**, contexto 32.768 e KV FP8, precisando de `--enforce-eager`; sem isso houve OOM durante captura de CUDA graphs, incluindo alocação de 784 MiB. Não é relato do export NVIDIA e não demonstra que todo runtime precise dessa flag. A validação de kernels W4A4 em duas 5090 também foi com Inferact/Unsloth. [vLLM, consulta 22/09/2026](https://recipes.vllm.ai/Qwen/Qwen3.8-27B).
- **Dependências:** a receita vLLM pede `transformers>=5.8.0` para o processador de visão. A receita SGLang alerta que MTP com atenção FlashInfer pode encontrar erro de `uniform_q_len` com versões até 0.6.15.post1, indicando versão mais nova ou backend Triton. Não extrapolar esses mínimos para todas as combinações de imagens. [vLLM](https://recipes.vllm.ai/Qwen/Qwen3.8-27B) e [SGLang](https://docs.sglang.io/cookbook/autoregressive/Qwen/Qwen3.8-27B), consulta 22/09/2026.

### Problemas relatados especificamente nesse repositório

| Relato | Evidência e data | O que permite concluir |
|---|---|---|
| **MTP reduz decode em RTX 5090** | Issue #5, **10/09/2026**, 68 → 50 tok/s ao ativar MTP com 1–3 tokens; aberta na consulta. [Fonte](https://huggingface.co/nvidia/Qwen3.8-27B-NVFP4/discussions/5). | É um relato real sobre o checkpoint exato, mas sem configuração completa ou diagnóstico. Não garante que MTP seja sempre prejudicial. |
| **Respostas descontroladas / falha em benchmark pessoal** | Issue #6, **10/09/2026**, autor afirma ter observado o problema também no base, FP8 e vários NVFP4, com diferentes templates vLLM; aberta na consulta. [Fonte](https://huggingface.co/nvidia/Qwen3.8-27B-NVFP4/discussions/6). | Não há isolamento causal do formato NVFP4 nem benchmark reproduzível suficiente no texto. Não tratar como defeito confirmado da quantização NVIDIA. |
| **Loops de raciocínio em sessões com ferramentas** | Discussão independente iniciada **09/09**, NVIDIA acrescentado **12/09/2026**, com comentários posteriores até a consulta. [Fonte](https://huggingface.co/Qwen/Qwen3.8-27B/discussions/192). | Autor relata loops nos NVFP4 inclusive NVIDIA, mas reconhece incerteza sobre ocorrência nas outras precisões. Teste curto de ferramentas com 100% não cobre sessões longas. |

Não achei correção oficial conclusiva para as duas issues específicas acima até a consulta. Não confundir a falha ocasional de texto ilegível atribuída ao export Unsloth, ou NaNs nos logprobs FP8 na comparação independente, com bugs demonstrados no export NVIDIA. [Discussões #5](https://huggingface.co/nvidia/Qwen3.8-27B-NVFP4/discussions/5), [#6](https://huggingface.co/nvidia/Qwen3.8-27B-NVFP4/discussions/6), ambas 10/09/2026; [comparação, atualização 12/09/2026](https://huggingface.co/Qwen/Qwen3.8-27B/discussions/192).

### Linux versus WSL2

O suporte CUDA documentado pela NVIDIA é para **WSL2**, com driver NVIDIA instalado no **Windows**; não instalar um segundo driver Linux de GPU dentro do WSL. O guia recomenda driver Windows atual e pacotes de toolkit que não tentem instalar driver Linux. Há limitações de memória pinned e de algumas funções de gerenciamento. Esse guia estabelece a infraestrutura CUDA, **não certifica o checkpoint nem promete igualdade de desempenho com Linux nativo**. [Guia oficial CUDA on WSL, documentação viva consultada 22/09/2026](https://docs.nvidia.com/cuda/wsl-user-guide/index.html).

**Escolha sugerida a partir das evidências:** começar pela receita SGLang que explicita **NVIDIA + RTX 5090**, ou por vLLM atual com versão/imagem fixada e configuração adaptada à VRAM; validar sem especulação antes de acrescentar MTP/DFlash. É uma recomendação desta pesquisa, baseada nas validações e no relato de regressão MTP, não medição local. Para llama.cpp/Ollama, exigir GGUF compatível e verificar o caminho CUDA usado; não presumir que o suporte genérico garante esse export. [SGLang, consulta 22/09/2026](https://docs.sglang.io/cookbook/autoregressive/Qwen/Qwen3.8-27B); [vLLM, consulta 22/09/2026](https://recipes.vllm.ai/Qwen/Qwen3.8-27B); [MTP, 10/09/2026](https://huggingface.co/nvidia/Qwen3.8-27B-NVFP4/discussions/5); [Ollama, 02/07/2026](https://github.com/ollama/ollama/issues/16056#issuecomment-4866857329).

## 5. Lacunas explícitas

Não localizei, nas fontes verificadas:

- primeira release exata de Ollama com NVFP4 CUDA; **v0.31.1 funciona segundo os relatos**, o que é diferente de provar que foi a primeira;
- versão estável mínima garantida do vLLM para o checkpoint NVIDIA exato, ou sua validação no TensorRT-LLM, llama.cpp e Ollama;
- comparação controlada de qualidade do checkpoint NVIDIA contra **GGUF Q4_K_M**, em vez de INT4 AWQ de outros exports;
- bateria independente pareada BF16/FP8/NVFP4/Q4 na **mesma RTX 5090**, incluindo contexto longo, velocidade e sucesso em ferramentas;
- comparação controlada **Linux nativo versus WSL2** para esse caso;
- requisito oficial único de RAM de sistema/driver ou solução oficial conclusiva para as issues #5/#6.

Essas ausências delimitam a pesquisa; não provam inexistência de implementação ou de resultados não indexados. Os links junto de cada conclusão permitem distinguir o que foi medido, o que foi anunciado e o que continua sem comprovação.
