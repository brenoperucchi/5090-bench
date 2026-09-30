# PLANO — Qwen3.8 125B, Expert Caching e A/B de Runtimes na RTX 5090

**Data:** 2026-09-16  
**Projeto alvo:** `brenoperucchi/llm-bench`  
**Status:** planejamento / handoff técnico  
**Objetivo:** dar ao `llm-bench` todo o contexto necessário para investigar, reproduzir e medir uma nova geração de inferência local baseada em modelos MoE grandes, expert caching/offload, MTP/speculative decoding e runtimes `llama.cpp` especializados.

> Este documento é um plano de investigação e execução. Ele não deve ser tratado como resultado medido.  
> Sempre separar: **fato já observado**, **claim de terceiro**, **hipótese nossa** e **resultado medido no nosso hardware**.

---

## 1. Por que este plano existe

O `llm-bench` hoje nasceu para medir LLMs locais na **RTX 5090 32 GB**, principalmente via **Ollama**, cobrindo performance, PT/EN, tool calling, qualidade, concorrência e comportamento.

O próximo passo é maior.

A pergunta deixa de ser apenas:

> “Qual modelo cabe inteiro nos 32 GB da 5090 e quantos tokens/s ele entrega?”

e passa a ser:

> “Quanto trabalho útil conseguimos extrair da mesma 5090 quando usamos modelos MoE grandes, memória do host, expert caching/offload, MTP, prefetch e runtimes especializados?”

Isso importa porque a evolução de LLM local não depende apenas de comprar GPUs com mais VRAM. Software pode mudar a relação entre:

- VRAM disponível;
- RAM do sistema;
- tamanho total do modelo;
- parâmetros ativos por token;
- largura de banda PCIe;
- residência de experts;
- KV cache;
- prefill;
- decode;
- speculative decoding / MTP;
- latência total de uma tarefa agentiva;
- qualidade de julgamento.

A hipótese central é que **32 GB de VRAM podem continuar úteis para modelos muito maiores que 32 GB**, especialmente MoE, desde que o runtime use a VRAM como uma camada ativa/cache em vez de exigir residência total dos pesos.

---

# 2. Contexto atual do nosso laboratório

## 2.1 Hardware principal

Servidor de inferência atual:

- **GPU:** NVIDIA RTX 5090, 32 GB VRAM.
- **CPU:** Ryzen 9 5950X.
- **RAM:** 64 GB atualmente.
- **PCIe:** plataforma AM4 / PCIe 4.0 x16.
- **Uso:** inferência local para coding, agentes, benchmark e futuros papéis de Worker / Reviewer / Challenger.
- **Runtime principal atual:** Ollama.
- **Sistema:** Windows nativo é o baseline operacional atual do servidor.
- Já foi medido anteriormente que, no nosso ambiente, Windows nativo apresentou vantagem sobre WSL2 em decode para um teste controlado. Não extrapolar esse resultado automaticamente para `llama.cpp` forkado sem A/B específico.

## 2.2 Estado atual do `llm-bench`

O repositório já possui:

- benchmark de throughput;
- benchmark A/B de engine;
- benchmark de qualidade;
- goldset PT/EN;
- verificações de escalation;
- detecção de reasoning leak;
- histórico de decisões;
- metodologia;
- documentação de infraestrutura;
- manifests de evidência;
- scripts reproduzíveis.

Arquivos particularmente relevantes:

- `bench.py`
- `bench_engine_ab.py`
- `run_chat.py`
- `goldset_chat.json`
- `docs/en/methodology.md`
- `docs/en/infrastructure.md`
- `docs/en/templates/experiment.md`
- `docs/en/benchmarks.md`
- `docs/en/findings.md`

Importante: `run_chat.py` e `bench_engine_ab.py` foram escritos pensando principalmente em Ollama. A nova etapa precisa suportar de forma explícita endpoints `llama.cpp` / OpenAI-compatible sem misturar métricas incompatíveis.

---

# 3. Os três projetos que motivam esta investigação

## 3.1 `thecodacus/spec-wins`

Fonte:

- https://github.com/thecodacus/spec-wins

Esse projeto não mede apenas “teste verde”. Ele mede **julgamento sob evidência conflitante**.

Cada tarefa contém armadilhas deliberadas:

- teste público contradizendo a especificação;
- código legado enganoso;
- documentação de performance conflitante;
- regressão que codifica o bug;
- armadilhas de `float`;
- artefatos projetados para induzir o agente a “consertar o lado errado”.

Resultado publicado:

| Modelo | Resultado |
|---|---:|
| Claude Opus 5 | 17/17 |
| **Qwen3.8-Flash-Next 125B, IQ3_XXS, RTX 3060 12 GB, ~19 tok/s** | **17/17** |
| Qwen3.6-35B-A3B Q4_K_M, ~60 tok/s | 14/17 |

Ponto extremamente importante:

O Qwen3.6 foi muito mais rápido, mas cometeu um erro semântico grave em uma tarefa financeira: passou nos checks, porém acumulava valores em `float` e só convertia para `Decimal` no final. O próprio autor classificou o resultado como violação da especificação.

Conclusão para o nosso laboratório:

> **tok/s não é proxy de qualidade agentiva.**

Esse benchmark é particularmente relevante para o papel de **Challenger**.

---

## 3.2 `thecodacus/llama.cpp`

Fonte:

- https://github.com/thecodacus/llama.cpp

Foi identificado que o resultado do Qwen3.8 no `spec-wins` usou o **Codacus fork**.

O próprio scorecard do `spec-wins` registra:

```text
qwen38-flash (Codacus fork, router, 64k/1 slot/48 cache/MTP-CPU)
```

Isso transforma o `thecodacus/llama.cpp` no runtime prioritário para a primeira reprodução.

Hoje sabemos:

- é fork do `ggml-org/llama.cpp`;
- branch default: `perf`;
- foi o runtime utilizado no teste do Qwen3.8;
- havia router;
- contexto de 64k;
- 1 slot;
- referência a “48 cache”;
- MTP-CPU.

**Ainda não assumir**:

- qual flag exata representa “48 cache”;
- RAM total usada;
- número exato de layers na GPU;
- política de cache;
- commit exato do runtime;
- GGUF exato além da descrição IQ3_XXS;
- configuração de KV;
- pinned memory;
- batch;
- threads;
- parâmetros do router.

A primeira etapa deste plano é descobrir isso com precisão.

---

## 3.3 `GenerelSchwerz/llama.cpp`

Fontes:

- https://github.com/GenerelSchwerz/llama.cpp
- https://github.com/GenerelSchwerz/llama.cpp/wiki
- https://github.com/GenerelSchwerz/llama.cpp/wiki/Benchmark-Comparison-Showcase

Esse fork é interessante por outro motivo: ele documenta explicitamente uma linha de trabalho focada em:

- expert caching;
- expert offload;
- partial residency;
- prefetch;
- overlap;
- MoE;
- KV residency;
- MTP/speculative decoding;
- otimizações CUDA;
- gerenciamento de memória;
- benchmarks comparativos de modelos MoE.

Ele deve ser tratado como **runtime concorrente** ao Codacus, não como substituto automático.

---

# 4. A tese que queremos testar

A arquitetura de software que estamos perseguindo é aproximadamente:

```text
                        TAREFA
                          |
                          v
                 FAST LOCAL WORKER
                  27B / 30B / 35B
                   RTX 5090 32 GB
                          |
                          v
                       TESTES
                          |
                          v
                 LOCAL CHALLENGER
                 Qwen3.8 125B MoE
             VRAM + RAM + cache/offload
                          |
                 +--------+--------+
                 |                 |
              APROVA             DÚVIDA
                 |                 |
                 v                 v
               DONE        GPT / Claude / frontier
```

Isso permite separar objetivos.

### Worker

Precisa de:

- baixa latência;
- prefill rápido;
- decode alto;
- boa tool use;
- execução repetida;
- capacidade de trabalhar em ciclos curtos.

### Challenger

Precisa de:

- julgamento;
- spec adherence;
- capacidade de encontrar bugs escondidos;
- resistência a testes/documentos contraditórios;
- menos preocupação com tok/s;
- mais preocupação com precisão.

Um Challenger a 20–50 tok/s pode ser muito útil se entrar apenas uma vez por mudança relevante.

---

# 5. Perguntas de pesquisa

O plano deve responder objetivamente:

1. Conseguimos rodar **Qwen3.8-Flash-Next 125B IQ3_XXS** na nossa RTX 5090 + 64 GB RAM de forma estável?
2. Qual a velocidade real na nossa máquina?
3. Qual o TTFT?
4. Qual o prefill real?
5. Qual o decode real?
6. Quanto de VRAM é usado?
7. Quanto de RAM é usado?
8. Qual o pico de memória?
9. Qual o tráfego host ↔ GPU?
10. O PCIe 4.0 x16 vira gargalo?
11. Quanto o 5950X influencia?
12. O modelo mantém a qualidade observada no `spec-wins`?
13. O IQ3_XXS perde qualidade em nossos workloads?
14. O Codacus fork é estável no nosso ambiente?
15. O GenerelSchwerz é mais rápido usando o mesmo modelo e quantização?
16. Expert caching melhora wall-clock de tarefa real, ou apenas benchmark sintético?
17. MTP aumenta velocidade sem causar regressão de qualidade?
18. 64 GB de RAM são suficientes de forma confortável?
19. 96/128 GB trariam benefício material?
20. Qual papel é mais adequado para o 125B: Worker, Reviewer ou Challenger?
21. Quais modelos 30–35B MoE devem substituir ou complementar nossos modelos atuais?
22. Devemos manter Ollama para produção e usar `llama.cpp` apenas para papéis pesados?
23. É possível manter um Worker rápido residente e carregar/invocar um Challenger grande sob demanda?
24. Qual runtime oferece a melhor combinação de qualidade, velocidade, estabilidade e manutenção?

---

# 6. Hipóteses

Registrar antes dos testes para evitar conclusão retrospectiva.

## H1 — Qwen3.8 125B é operacionalmente viável

Esperamos que o modelo seja executável na 5090 com apoio da RAM, mesmo sem caber integralmente na VRAM.

**Não afirmar velocidade antes de medir.**

## H2 — 5090 melhora muito o cenário em relação à 3060

A 5090 tem 32 GB de VRAM, permitindo maior residência de experts/KV/workspace que uma 3060 12 GB.

Isso deve reduzir parte da pressão de transferências host↔GPU.

Mas o ganho não será necessariamente proporcional ao número de CUDA cores ou VRAM.

## H3 — Codacus deve ser a primeira reprodução

Porque existe evidência de que foi o runtime usado no `spec-wins`.

## H4 — GenerelSchwerz pode oferecer performance superior

Hipótese baseada no foco explícito em expert caching, MoE e offload.

Precisa de A/B controlado.

## H5 — 64 GB de RAM podem funcionar, mas talvez sem folga

A RAM precisa acomodar:

- parte não residente dos pesos;
- buffers;
- runtime;
- sistema operacional;
- page cache;
- estruturas de MTP;
- possíveis cópias temporárias.

Não comprar RAM antes de medir pressão real.

## H6 — 128 GB pode ser um upgrade de alto valor

Se o maior limitador passar a ser host memory em vez de VRAM, aumentar RAM pode destravar:

- quantização menos agressiva;
- modelos maiores;
- contexto maior;
- MTP;
- mais folga contra paging;
- testes de múltiplos modelos/runtimes.

Mas essa compra deve ser baseada em dados.

---

# 7. Regra fundamental: não destruir o baseline atual

O Ollama atual é nosso baseline operacional.

Nenhuma fase deste plano deve:

- substituir o serviço atual sem rollback;
- apagar modelos existentes;
- alterar permanentemente variáveis sem registro;
- usar a mesma porta em paralelo;
- sobrescrever resultados antigos;
- alterar goldsets históricos;
- misturar resultados Ollama e llama.cpp como se fossem diretamente comparáveis.

Preferência:

```text
Ollama baseline       -> porta atual
Codacus llama.cpp     -> porta dedicada
GenerelSchwerz        -> outra porta dedicada
```

Se dois runtimes usam a mesma GPU, **não medir simultaneamente**.

A/B deve ser serial e alternado.

---

# 8. Fase 0 — congelar o estado atual

Antes de instalar qualquer fork, criar um snapshot documental.

Registrar:

- Windows build;
- driver NVIDIA;
- CUDA exposta pelo driver;
- GPU;
- VRAM total/livre;
- CPU;
- RAM;
- BIOS/memory speed se disponível;
- PCIe link negotiated;
- Ollama version;
- modelos residentes;
- variáveis do Ollama;
- power limit;
- temperatura idle;
- processos usando GPU;
- SHA atual do `llm-bench`.

Criar:

```text
results/runtime-next/baseline/environment.json
results/runtime-next/baseline/environment.md
```

Esse snapshot é obrigatório.

---

# 9. Fase 1 — reproduzir a configuração do Codacus

Objetivo:

> descobrir a configuração exata que produziu o Qwen3.8 125B a ~19 tok/s na RTX 3060.

## 9.1 Descobrir o runtime

Investigar no `thecodacus/llama.cpp`:

- branch `perf`;
- commits ao redor de 2026-09-05;
- router implementation;
- README/wiki/commits relacionados a:
  - Qwen3.8;
  - cache;
  - MTP;
  - CPU;
  - MoE;
  - router;
  - slots;
  - 64k context.

Registrar:

```text
runtime_repo
runtime_branch
runtime_commit
build_flags
CUDA version
compiler
```

## 9.2 Descobrir o modelo exato

Registrar:

```text
model_family
model_repo
gguf_filename
quantization
file_size_bytes
sha256
architecture
total_parameters
active_parameters_if_known
```

Não aceitar apenas:

```text
Qwen3.8 125B IQ3_XXS
```

Precisamos do arquivo exato.

## 9.3 Descobrir o significado de “48 cache”

O scorecard registra:

```text
64k / 1 slot / 48 cache / MTP-CPU
```

Não assumir que “48” são:

- experts;
- layers;
- cache slots;
- MB/GB;
- tokens;
- outra métrica.

Localizar no runtime/configuração.

Documentar a flag e a unidade.

## 9.4 Descobrir MTP-CPU

Determinar:

- qual modelo draft/MTP foi usado;
- se MTP roda em CPU;
- memória necessária;
- acceptance rate se disponível;
- custo de CPU;
- impacto no decode.

---

# 10. Fase 2 — build isolado do Codacus

Objetivo:

> compilar o runtime sem tocar no Ollama atual.

Criar diretório dedicado, por exemplo:

```text
C:\llm-runtime\codacus\
```

ou equivalente.

Registrar:

```text
source_commit
build_command
compiler
CUDA toolkit
CMake flags
target architecture
binary hash
```

## Regra

Nunca publicar resultado do tipo:

> “Codacus é X% mais rápido”

sem registrar o commit exato do binário.

Forks de performance mudam rápido.

---

# 11. Fase 3 — smoke test do Qwen3.8

Antes de fazer benchmark longo:

1. subir runtime;
2. carregar modelo;
3. prompt mínimo;
4. verificar resposta coerente;
5. verificar memória;
6. verificar se há CPU fallback não intencional;
7. verificar se expert cache realmente está ativo;
8. verificar se MTP está ativo quando esperado.

Registrar:

- load time;
- VRAM idle;
- VRAM após load;
- RAM idle;
- RAM após load;
- peak RAM;
- peak VRAM;
- primeira resposta;
- TTFT;
- decode;
- warnings do runtime.

Se houver paging intenso do Windows ou OOM, parar.

Não “resolver” aumentando pagefile e continuar sem documentar.

---

# 12. Fase 4 — benchmark micro de performance

Criar um novo harness genérico, não preso ao `/api/generate` do Ollama.

Sugestão:

```text
bench_runtime_ab.py
```

Ele deve falar com API OpenAI-compatible:

```text
/v1/chat/completions
```

e permitir:

```text
ENDPOINT_A
ENDPOINT_B
MODEL_A
MODEL_B
LABEL_A
LABEL_B
NUM_CTX
NUM_PREDICT
REPS
TEMPERATURE
SEED
```

## 12.1 Desenho

Inspirar-se em `bench_engine_ab.py`:

- A/B serial;
- ordem alternada;
- warmup descartado;
- nunca dois runtimes simultâneos na mesma GPU;
- temperatura fixa;
- seed quando suportado;
- mesmo prompt;
- mesmo contexto;
- mesmo `num_predict`;
- mesma quantização;
- mesma GPU;
- mesmo power limit;
- mesmo estado térmico.

## 12.2 Prompts

Usar quatro classes:

1. curto;
2. médio;
3. longo;
4. very-long/context-heavy.

O prompt muito curto **não serve para medir prefill**.

## 12.3 Métricas

Obrigatórias:

```text
wall_s
ttft_s
prompt_tokens
output_tokens
prefill_tok_s
decode_tok_s
load_s
peak_vram_mb
avg_vram_mb
peak_ram_mb
avg_ram_mb
gpu_util_avg
gpu_power_avg_w
gpu_power_peak_w
cpu_util_avg
pcie_rx
pcie_tx
```

Quando o runtime expuser:

```text
expert_cache_hits
expert_cache_misses
expert_cache_hit_rate
experts_resident
expert_swaps
prefetch_hits
prefetch_misses
mtp_acceptance_rate
draft_tokens
accepted_draft_tokens
```

salvar também.

Se alguma métrica não estiver disponível, escrever `null`.

Nunca fabricar.

---

# 13. Fase 5 — context ladder

Testar o mesmo modelo em:

```text
8k
16k
32k
64k
```

e opcionalmente maior apenas se a configuração suportar.

Objetivo:

- medir crescimento de KV;
- TTFT;
- prefill;
- VRAM;
- RAM;
- impacto no cache de experts;
- trade-off entre contexto e residência.

Importante:

Não usar automaticamente o maior contexto só porque cabe.

Para agentes, um contexto menor pode permitir:

- maior expert residency;
- menos cache miss;
- menor TTFT;
- melhor throughput.

---

# 14. Fase 6 — reproduzir `spec-wins`

Essa fase é obrigatória antes de declarar Qwen3.8 “melhor”.

Fonte:

- https://github.com/thecodacus/spec-wins

## 14.1 Objetivo

Responder:

> O nosso Qwen3.8, no nosso runtime e na nossa quantização, mantém o julgamento demonstrado no benchmark original?

## 14.2 Não modificar o benchmark

Manter:

- tarefas originais;
- hidden graders;
- prompts;
- sandbox;
- isolamento.

O agente não pode ver:

- `hidden/`;
- `solutions/`;
- `docs/answer-key.md`.

## 14.3 Executar com três braços inicialmente

```text
A. Qwen3.8 + Codacus
B. Qwen3.6 35B-A3B controle local
C. modelo local atual de referência, se o harness suportar
```

Claude/Opus não é necessário para a primeira reprodução porque já existe resultado externo publicado.

## 14.4 Guardar transcript completo

Salvar:

```text
results/spec-wins/<runtime>/<model>/<task>/transcript.txt
results/spec-wins/<runtime>/<model>/<task>/grader.json
results/spec-wins/<runtime>/<model>/<task>/summary.md
```

## 14.5 Critério

Para considerar Qwen3.8 candidato a Heavy Challenger:

- nenhum erro semântico crítico;
- nenhuma violação clara de spec;
- resultado consistente com os hidden checks;
- relatório reconhecendo artefatos contraditórios;
- nenhuma conclusão falsa de “pronto”.

O número 17/17 é forte, mas não deve ser o único critério.

---

# 15. Fase 7 — benchmark interno de “judgment”

A filosofia do `spec-wins` deve entrar no `llm-bench`.

Não copiar apenas as tarefas Python.

Criar tarefas nossas.

## 15.1 Categoria nova

```text
Judgment Under Conflicting Evidence
```

## 15.2 Exemplos Rails

### Caso A — callback vs ADR

- README antigo recomenda callback;
- ADR mais novo proíbe callback no domínio;
- teste aceita os dois;
- agente precisa escolher a fonte autoritativa.

### Caso B — multi-tenant

- teste unitário passa;
- implementação não filtra `account_id`;
- hidden check detecta cross-tenant leak.

### Caso C — migration

- migration funciona no dataset pequeno;
- lock/alter destrutivo quebra requisito de zero-downtime.

### Caso D — idempotência

- webhook test passa sequencialmente;
- concorrência gera duplicação;
- DB não possui unique constraint.

### Caso E — dinheiro

- sample passa;
- uso de float falha em tie HALF_UP;
- hidden inputs detectam centavo incorreto.

### Caso F — N+1

- teste funcional passa;
- query count viola requisito explícito.

### Caso G — falso “fix”

- erro parece resolvido;
- test mocka a camada responsável;
- integração real continua quebrada.

## 15.3 Hidden graders

O modelo não deve conhecer todos os checks.

Guardar:

```text
tasks/
hidden/
solutions/
results/
```

como no `spec-wins`.

---

# 16. Fase 8 — A/B Codacus vs GenerelSchwerz

Somente depois de termos:

- modelo exato;
- quantização exata;
- baseline Codacus funcional.

Objetivo:

> trocar o runtime mantendo o máximo possível constante.

## 16.1 Variável principal

```text
runtime
```

Não misturar:

- runtime diferente;
- quantização diferente;
- contexto diferente;
- MTP diferente;
- cache diferente;

na mesma comparação.

## 16.2 Ordem

Primeiro:

```text
Codacus sem MTP
vs
Generel sem MTP
```

Depois:

```text
Codacus com MTP
vs
Generel com MTP
```

Depois testar expert cache tuning.

## 16.3 Métricas

Além das métricas micro:

- wall-clock do `spec-wins`;
- qualidade;
- número de tool calls;
- estabilidade;
- crashes;
- OOM;
- consistency entre runs;
- reasoning leaks;
- respostas truncadas;
- repeatability.

---

# 17. Fase 9 — tuning de expert caching

Só fazer tuning depois de um baseline válido.

Variáveis possíveis:

- tamanho do expert cache;
- quantos experts permanecem residentes;
- política de eviction;
- prefetch;
- pinned host memory;
- overlap;
- batch;
- context;
- KV quantization;
- MTP.

## Regra

Alterar **uma variável principal por experimento**.

Exemplo:

```text
cache = 16
cache = 32
cache = 48
cache = 64
```

Mantendo o restante fixo.

## Resultado esperado

Construir curva:

```text
cache size
   |
   +--> hit rate
   +--> decode
   +--> TTFT
   +--> VRAM
   +--> RAM
   +--> PCIe traffic
```

O melhor cache não é necessariamente o que ocupa mais VRAM.

---

# 18. Fase 10 — avaliar 64 GB vs upgrade de RAM

Não comprar RAM antes desse ponto.

## 18.1 Com 64 GB, registrar

- committed memory;
- working set;
- standby;
- page faults;
- swap/pagefile activity;
- model backing;
- runtime buffers;
- peak RAM;
- headroom.

## 18.2 Sinais de que 64 GB são insuficientes

- paging contínuo;
- OOM;
- runtime precisa reduzir quantização/contexto;
- expert cache limitado pelo host;
- load/reload excessivo;
- MTP não cabe;
- sistema fica sem margem para OS;
- wall-clock degrada por pressão de RAM.

## 18.3 Quando 96/128 GB ganha justificativa

Se um upgrade permitir:

- quantização melhor;
- contexto maior sem paging;
- modelo mais inteligente;
- MTP;
- maior cache;
- dois modelos úteis;
- menor latência total.

Documentar o ganho esperado antes da compra.

---

# 19. Fase 11 — nova geração de modelos 30–35B para Worker

O `GenerelSchwerz Benchmark-Comparison-Showcase` contém candidatos interessantes.

Tratar como **candidatos**, não como vencedores.

Exemplos para benchmark:

- Qwen3.6 35B-A3B;
- Nemotron 3.5 Lightning 30B-A3B;
- Ornith 1.5 35B-A3B;
- Gemma 4 26B-A4B;
- GPT-OSS 20B como controle conhecido.

## Avaliar para Worker

Prioridades:

1. tool calling;
2. coding;
3. autonomy;
4. false completion;
5. spec adherence;
6. prefill;
7. decode;
8. wall-clock;
9. context handling.

O Worker pode ser menor que o Challenger.

---

# 20. Fase 12 — matriz de papéis

Ao final, classificar os modelos por função.

Não criar um ranking universal.

Exemplo:

| Papel | O que mais pesa |
|---|---|
| Worker | velocidade + tool calling + autonomia |
| Reviewer | code review + detecção de regressão |
| Challenger | julgamento + resistência a traps |
| Shunt/Bulk Reader | prefill + factual extraction + baixo custo |
| Second Brain | contexto + síntese + estabilidade |
| Frontier Escalation | fora do escopo local |

Possível resultado futuro:

```text
Worker:
Qwen 30–35B MoE

Bulk Reader:
7B/14B rápido

Reviewer:
30–35B especializado

Heavy Challenger:
Qwen3.8 125B

Escalation:
GPT / Claude
```

Isso é uma hipótese de arquitetura, não decisão atual.

---

# 21. Métrica principal: trabalho útil

Não deixar o projeto virar um ranking de tok/s.

Precisamos medir:

```text
Useful Work per Wall-Clock Minute
```

Para uma tarefa real:

```text
Tarefa começou
  ->
leu arquivos
  ->
alterou código
  ->
rodou testes
  ->
corrigiu
  ->
revisou
  ->
terminou corretamente
```

Métricas:

- tempo total;
- tokens;
- tool calls;
- retries;
- failures;
- test passes;
- hidden checks;
- qualidade;
- necessidade de frontier escalation.

Um modelo a 40 tok/s pode vencer outro a 150 tok/s se precisar de menos ciclos e errar menos.

---

# 22. Quality gates

Um modelo não pode ser promovido só por ser rápido.

## Falhas críticas

Qualquer uma destas deve bloquear promoção:

- falsa alegação de testes executados;
- falsa alegação de sucesso;
- editar para satisfazer teste que contradiz spec;
- cross-tenant leak;
- erro financeiro conhecido;
- destructive migration ignorada;
- tool hallucination;
- reasoning leak grave quando contrato proíbe;
- ignorar escalation obrigatório;
- manipular grader/teste para passar.

## Para Heavy Challenger

Exigir:

- excelente spec adherence;
- capacidade de contestar artefatos errados;
- honestidade sobre incerteza;
- detectar soluções que “passam testes, mas estão erradas”.

---

# 23. Extensão do `run_chat.py`

Hoje `run_chat.py` fala com Ollama:

```text
/api/chat
```

Criar nova abstração de transporte.

Sugestão:

```text
providers/
  ollama.py
  openai_compatible.py
```

ou uma camada simples dentro de um novo harness.

Objetivo:

```text
same goldset
same prompt
same scoring
different runtime
```

Não reescrever os auto-checks se não for necessário.

Separar transporte de avaliação.

---

# 24. Extensão do `bench_engine_ab.py`

O desenho A/B atual é bom:

- serial;
- ordem alternada;
- warmup;
- mesma GPU;
- mesmo modelo;
- context fixo;
- prefill separado de decode.

Reutilizar essa filosofia.

Criar versão genérica OpenAI-compatible ou refatorar sem quebrar resultados históricos.

Não modificar resultado antigo em place.

---

# 25. Estrutura de diretórios sugerida

```text
docs/
  en/
    plans/
      qwen38-expert-cache-runtime-ab.md
  rtx5090/
    plans/
      qwen38-expert-cache-runtime-ab.md

configs/
  codacus/
  generelschwerz/

results/
  runtime-next/
    baseline/
    codacus/
    generelschwerz/
    ab/
  spec-wins/
  judgment/

scripts/
  collect_system_metrics.py
  run_runtime_ab.py
  run_spec_wins.py
```

Se não quiser reorganizar o repositório agora, manter o plano em root inicialmente:

```text
PLANO-qwen38-expert-cache-2026-09-16.md
```

e migrar depois para `docs/`.

---

# 26. Esquema mínimo de resultado

Cada run deve gerar JSON com algo semelhante a:

```json
{
  "timestamp": "",
  "host": {
    "gpu": "",
    "driver": "",
    "cpu": "",
    "ram_gb": 64,
    "pcie": ""
  },
  "runtime": {
    "repo": "",
    "branch": "",
    "commit": "",
    "build_flags": []
  },
  "model": {
    "name": "",
    "file": "",
    "sha256": "",
    "quantization": "",
    "size_bytes": 0
  },
  "config": {
    "context": 0,
    "batch": 0,
    "slots": 0,
    "expert_cache": null,
    "mtp": null
  },
  "performance": {
    "ttft_s": null,
    "prefill_tok_s": null,
    "decode_tok_s": null,
    "wall_s": null
  },
  "resources": {
    "peak_vram_mb": null,
    "peak_ram_mb": null,
    "pcie_rx": null,
    "pcie_tx": null,
    "gpu_power_avg_w": null
  },
  "cache": {
    "hits": null,
    "misses": null,
    "hit_rate": null
  },
  "quality": {
    "benchmark": "",
    "passed": null,
    "critical_failures": []
  }
}
```

---

# 27. Reprodutibilidade

Cada resultado precisa permitir responder:

- qual código?
- qual commit?
- qual modelo?
- qual arquivo?
- qual hash?
- qual prompt?
- qual contexto?
- qual runtime?
- qual comando?
- qual temperatura?
- qual seed?
- qual GPU?
- qual estado térmico?
- qual RAM?
- qual power limit?
- qual versão do driver?
- qual resultado bruto?

Sem isso, resultado entra como anedota, não evidência.

---

# 28. Resultados externos: regra de citação

Quando registrar algo de terceiros:

Usar rótulo explícito:

```text
EXTERNAL CLAIM
```

ou:

```text
EXTERNAL MEASUREMENT
```

Nunca misturar com:

```text
MEASURED ON OUR RTX 5090
```

Exemplo correto:

> `spec-wins` reporta Qwen3.8 125B IQ3_XXS em RTX 3060 12 GB a ~19 tok/s.

Não escrever:

> Qwen3.8 faz 19 tok/s em 12 GB.

A primeira frase preserva o contexto do experimento.

---

# 29. Comparação de runtime: critérios de decisão

Ao final, cada runtime recebe um perfil, não uma nota única.

## Codacus

Avaliar:

- reproduz resultado Qwen3.8?
- qualidade?
- estabilidade?
- velocidade?
- documentação?
- facilidade de build?
- atualização?
- compatibilidade Windows?
- manutenção do fork?

## GenerelSchwerz

Avaliar:

- expert cache?
- hit rate?
- prefetch?
- MTP?
- VRAM?
- RAM?
- throughput?
- estabilidade?
- facilidade operacional?
- diferença para upstream?

## Upstream llama.cpp

Manter como controle quando possível.

Pergunta importante:

> Quanto do ganho do fork já entrou no upstream?

---

# 30. Critérios para adoção

## Adotar Codacus para Heavy Challenger se

- Qwen3.8 roda estável;
- qualidade é forte;
- wall-clock é aceitável;
- sem paging destrutivo;
- configuração reproduzível.

## Adotar GenerelSchwerz se

- melhora wall-clock de forma clara;
- não piora qualidade;
- não cria instabilidade operacional relevante;
- cache/offload é mensurável e reproduzível.

## Permanecer em Ollama para Worker se

- Ollama continuar simples;
- mais estável;
- suficientemente rápido;
- integração existente já funciona.

É perfeitamente aceitável usar:

```text
Ollama -> Worker
llama.cpp fork -> Heavy Challenger
```

Não precisamos de um runtime único.

---

# 31. Experimentos prioritários

Ordem sugerida.

## EXP-01 — Codacus Qwen3.8 Smoke

Pergunta:

> Qwen3.8 125B carrega e responde na RTX 5090 + 64 GB?

Resultado binário inicial:

```text
PASS / FAIL
```

## EXP-02 — Codacus Performance Baseline

Medir:

```text
TTFT
prefill
decode
VRAM
RAM
power
```

## EXP-03 — Context Ladder

```text
8k
16k
32k
64k
```

## EXP-04 — spec-wins reproduction

Medir julgamento.

## EXP-05 — MTP A/B

```text
MTP off
vs
MTP on
```

## EXP-06 — Expert cache ladder

Variação controlada de cache.

## EXP-07 — GenerelSchwerz baseline

Mesmo modelo/configuração.

## EXP-08 — Runtime A/B

Codacus vs GenerelSchwerz.

## EXP-09 — Internal judgment set

Rails / multi-tenant / financeiro.

## EXP-10 — RAM pressure

Determinar necessidade de 96/128 GB.

## EXP-11 — Worker candidates

30–35B MoE.

---

# 32. Critério de sucesso do projeto

O plano é considerado concluído quando soubermos, com evidência:

1. se Qwen3.8 125B é utilizável na nossa máquina;
2. em qual runtime;
3. em qual quantização;
4. em qual contexto;
5. com qual velocidade;
6. com quanta RAM;
7. com quanta VRAM;
8. com qual qualidade;
9. com qual estabilidade;
10. em qual papel da arquitetura ele deve entrar.

E também:

11. se expert caching vale a pena na 5090;
12. se 64 GB de RAM limitam;
13. se 128 GB justificam upgrade;
14. qual modelo deve ser o Worker;
15. qual modelo deve ser o Challenger;
16. quando frontier escalation ainda é necessária.

---

# 33. Definition of Done

Antes de declarar esta etapa encerrada:

- [ ] commit do runtime registrado;
- [ ] modelo/quantização/hash registrados;
- [ ] ambiente registrado;
- [ ] benchmark bruto salvo;
- [ ] performance separa prefill/decode/TTFT;
- [ ] VRAM medida;
- [ ] RAM medida;
- [ ] wall-clock medido;
- [ ] spec-wins executado;
- [ ] quality gate executado;
- [ ] Codacus vs Generel comparado;
- [ ] MTP A/B executado;
- [ ] expert cache testado;
- [ ] conclusão sobre RAM escrita;
- [ ] papel Worker/Challenger definido;
- [ ] findings catalog atualizado;
- [ ] decisions atualizado;
- [ ] provenance atualizado;
- [ ] manifest validado.

---

# 34. Primeira sessão de trabalho

A próxima sessão do `llm-bench` deve fazer **somente isto**:

1. Ler este documento inteiro.
2. Inspecionar o estado atual do repositório.
3. Não alterar decisões históricas.
4. Criar uma branch de trabalho.
5. Registrar baseline do servidor.
6. Investigar o `thecodacus/llama.cpp`.
7. Descobrir o commit/configuração usados no `spec-wins`.
8. Identificar o GGUF exato Qwen3.8 IQ3_XXS.
9. Documentar “64k / 1 slot / 48 cache / MTP-CPU”.
10. Produzir um plano executável para o primeiro smoke test.
11. **Não baixar dezenas de modelos ainda.**
12. **Não começar pelo GenerelSchwerz ainda.**
13. **Não comprar RAM ainda.**

A prioridade é reproduzir a evidência mais forte que já temos:

```text
Qwen3.8-Flash-Next 125B
IQ3_XXS
Codacus fork
RTX 3060 12 GB
~19 tok/s
17/17 no spec-wins
```

Depois disso, usar a RTX 5090 para descobrir quanto essa arquitetura escala no nosso hardware.

---

# 35. Fontes principais

## Nosso laboratório

- https://github.com/brenoperucchi/llm-bench
- `README.md`
- `bench_engine_ab.py`
- `run_chat.py`
- `goldset_chat.json`
- `docs/en/templates/experiment.md`

## Qualidade / julgamento

- https://github.com/thecodacus/spec-wins
- https://github.com/thecodacus/spec-wins/blob/main/results/t1-qwen38-flash.md
- https://github.com/thecodacus/spec-wins/blob/main/results/qwen36-scorecards.md

## Runtime usado no Qwen3.8 do spec-wins

- https://github.com/thecodacus/llama.cpp

## Expert caching / runtime concorrente

- https://github.com/GenerelSchwerz/llama.cpp
- https://github.com/GenerelSchwerz/llama.cpp/wiki
- https://github.com/GenerelSchwerz/llama.cpp/wiki/Benchmark-Comparison-Showcase

---

# 36. Princípio final

O objetivo não é provar que “local venceu cloud”.

Também não é provar que “125B é melhor que 35B”.

O objetivo é construir uma arquitetura mensurável onde cada modelo ocupa o papel em que entrega maior valor.

A tese a testar é:

```text
FAST LOCAL WORKER
        +
HEAVY LOCAL CHALLENGER
        +
FRONTIER ESCALATION
```

com a RTX 5090 servindo como infraestrutura permanente, e não apenas como uma GPU que precisa conter o modelo inteiro em VRAM.

Se expert caching, MTP e MoE funcionarem bem no nosso hardware, a vida útil prática da 5090 pode ser definida muito mais pela evolução do software e dos modelos do que pelo número “32 GB” isoladamente.
