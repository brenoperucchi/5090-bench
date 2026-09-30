# Panorama: outros ganhos de software na mesma RTX 5090 (22–30/09/2026)

O Strata não é um caso isolado. Nas mesmas semanas, na mesma placa, vários ganhos vieram só de software.

## 1. llama.cpp com MTP (predição de vários tokens): +70% num modelo denso

Qwen3.8-27B em NVFP4 com cabeça MTP embutida, llama.cpp b11053 (22/09):

| | Geração (tok/s) |
|---|---|
| NVFP4 sem MTP | 74,7 |
| **NVFP4 com `--spec-type draft-mtp --spec-draft-n-max 2`** | **123,6–126,7** (aceitação 68%) |

- **Mesmo modelo, mesma placa, uma flag: +70%.**
- Ressalva: no llama.cpp o texto com MTP **não** saiu idêntico ao sem MTP, então a qualidade precisa ser conferida.

Outros ajustes medidos no mesmo dia (regras de adoção congeladas antes de medir):
- `-ub 1024 -b 4096`: prefill de prompt longo +8%, geração igual. Adotado.
- `-fa on`: prefill −2,6%. Recusado.
- KV cache q8_0: mais lento. Só medido.

## 2. Windows nativo × WSL: o sistema operacional também é software

Mesmo binário do llama.cpp (b11053), mesmos GGUF (22/09):

| Modelo | Geração WSL → Windows | Prefill longo WSL → Windows |
|---|---|---|
| Qwen3.8-27B Q4 | 75,2 → 76,3 | 3.492 → 3.584 |
| NVFP4 + MTP | 126,7 → 125,8 | 3.494 → 4.275 |
| Hemmingway (27B Q4) | 72,7 → 74,0 | 3.579 → 3.628 |
| APEX 35B-A3B + MTP | 271,9 → **302,4** | 7.134 → 8.331 |

- **Windows nativo 1–2% à frente nos densos e ~11% no MoE pequeno.**
- O WSL ainda trazia custos de operação: limite de RAM da VM (48 GB), interop instável. Em 30/09 a produção passou
  para o Windows nativo.

## 3. Arquitetura MoE: o modelo em si como otimização de software

| Modelo | Ativos por token | Geração na 5090 (melhor configuração) |
|---|---|---|
| Qwen3.8-27B denso (Q4) | 27B | ~75 tok/s |
| Qwen3.8-27B NVFP4 + MTP | 27B | ~126 tok/s |
| **Qwen3.8-35B-A3B "APEX" + MTP** (llama.cpp) | **~3B** | **~272–302 tok/s** |
| **Qwen3.8-Flash-Next IQ2_XS** (Strata) | MoE de 512 especialistas | **~155–172 tok/s** |

- O Flash-Next é de longe o maior e mais forte da lista. **Sem o Strata, ele fazia 16–27 tok/s**. Com o Strata,
  roda na mesma faixa dos modelos 27B otimizados.
- A velocidade nunca responde sozinha à pergunta de qualidade (arquivo 04).

## 4. O que muda na conversa software × hardware

- **Um modelo que "só rodaria bem" em hardware de outra classe** (Mac Studio Ultra, RTX PRO 6000 de 96 GB, várias
  GPUs) **roda em produção numa 5090 de consumo**, por causa de um motor feito sob medida para a arquitetura dele
  (divisão VRAM/RAM/SSD por especialista, cache adaptativo, CPU em paralelo e MTP).
- **O ganho veio em dias, não em gerações de GPU:** 6 dias do Strata publicado a produção nossa; +55% nas respostas
  longas em ~2 dias de versões; 3,8× no prefill em 5 dias (na máquina do autor).
- **A mesma placa ganhou em quatro frentes independentes** no mesmo mês: motor sob medida (Strata), técnica de
  decodificação (MTP), sistema operacional (Windows nativo) e arquitetura do modelo (MoE com poucos ativos).
