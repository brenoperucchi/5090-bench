# Flash-Next na 5090: llama.cpp × Strata, medições

## O modelo

**Qwen3.8-Flash-Next** é um MoE muito grande, com 512 especialistas por camada. Mesmo quantizado em 2–3 bits, os
pesos (~66–84 GB) não cabem nos 32 GB da 5090. Um motor genérico precisa então deixar parte na CPU, e a velocidade
despenca.

## Antes: llama.cpp (19/09/2026)

Fork Codacus do llama.cpp (necessário para a arquitetura), GGUF **UD-IQ3_XXS** (Unsloth), `--flash-attn on`,
`--parallel 1`, `--load-mode mmap`, temperatura 0:

| Especialistas na CPU | Geração a frio | Geração a quente | Carga |
|---|---|---|---|
| `--cpu-moe` (todos na CPU) | 11,2 tok/s | **16,2 tok/s** | — |
| `--n-cpu-moe 32` (parte na GPU) | 15,5 tok/s | **27,0 tok/s** | ~4 min 20 s |

- Com 16K de contexto, a geração começou e não concluiu na sessão.
- A sondagem foi suspensa: o modelo não era viável para uso.

## Como o Strata faz diferente

Motor próprio em C++ (MIT), feito só para essa arquitetura:
- **Na VRAM:** a parte densa e um **cache dos especialistas mais usados**, que se ajusta com o uso. Na nossa 5090,
  **~18.400 especialistas (24,7 GiB)**.
- **Na RAM:** todos os especialistas (33 GiB no IQ2_XS). A **CPU calcula em paralelo** os que faltam na GPU, e uma
  fração deles vai pela PCIe.
- **No SSD:** a tabela PLE (~29 GB), da qual lê só algumas linhas por token.
- **Decodificação especulativa com a camada MTP** do próprio modelo, com a mesma saída.
- No nosso uso, **o cache acerta 99,6–99,8% dos especialistas** pedidos na geração (log do servidor).

## Depois: Strata na 5090 (30/09/2026)

Modelo **IQ2_XS** GSQ-RCO (ISTA-DASLab), Windows nativo, contexto 32K, KV int8, raciocínio desligado.
Instrumento `os_runtime_ab.py`: prompts de 2.671 (médio) e 5.952 tokens (longo), 256 tokens de saída,
temperatura 0, métrica = timings do próprio servidor, mediana.

| Versão | Repetições | Geração, médio | Geração, longo | Prefill, médio | Prefill, longo | VRAM livre |
|---|---|---|---|---|---|---|
| v0.1.27 | 3 | 171,0 | 156,5 | 2.700 | 3.980 | 277 MiB |
| v0.1.29 | 3 | 159,2 | 154,3 | 2.687 | 4.032 | 421 MiB |
| v0.1.30 calibrada | 5 | 163,1 | 155,4 | 2.589 | 3.889 | 419 MiB |

- **Nas respostas curtas (256 tokens), as versões empatam.** A variação entre repetições (~150–166) é maior
  que a diferença entre as versões.
- **A diferença aparece nas respostas longas reais.** Na síntese do Guardian (16 respostas de 1.200–2.250 tokens),
  com timings do servidor:

| | Geração, mediana (mín–máx) | Aceitação do MTP | Tempo por resposta |
|---|---|---|---|
| v0.1.27, sem calibrar | 105,6 tok/s (97–172) | 62% | 9–22 s |
| **v0.1.30 calibrada** | **163,4 tok/s (159–172)** | **75%** | **7,5–13,6 s** |

## A calibração (`--calibrate`, ~5 min)

Os padrões do Strata foram medidos numa 5070 com Ryzen 5 7600. O `--calibrate` mede, na máquina, três ajustes que
dependem do PC. Resultado na nossa:

| Ajuste | Testado | Escolhido |
|---|---|---|
| `--pcie-frac` (fração dos especialistas ausentes que vai pela PCIe em vez da CPU) | 0 / 0,20 / 0,35 / 0,55 / 0,75 → 174–179 tok/s | **0,55** |
| `--spec-min-p` (confiança mínima do rascunho MTP para arriscar mais um token) | 0,30 / 0,50 / 0,70 → 174–185 tok/s | **0,70** |
| `--pool-workers` (threads de CPU para especialistas) | 15 / 10 / 8 → 179–181 tok/s | padrão mantido |

Medição final da própria calibração: **180,7 tok/s**. O efeito mais visível é na aceitação do MTP, que subiu de 62%
para 75%.

## Comparação com a tabela do autor (RTX 5070 12 GB, Ryzen 5 7600, DDR5)

| | 5070 do autor | Nossa 5090 |
|---|---|---|
| IQ2_XS, geração | 79 tok/s (chat curto) | 155–172 tok/s |
| IQ2_XS, leitura de prompt | 2.090 tok/s (32K) | 2.600–4.000 tok/s (2,7K–6K) |

Os prompts não são iguais, então a comparação é aproximada: cerca do dobro. A diferença vem principalmente de
quantos especialistas cabem na VRAM.

## Custo em memória

- RAM: ~33 GiB de especialistas fixos (IQ2_XS), mais o sistema.
- VRAM: praticamente toda, com ~420 MiB livres. Não sobra espaço para outro modelo na GPU ao mesmo tempo.
- Disco: ~72 GB entre GGUF, pack convertido e MTP.
