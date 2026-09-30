# Strata: evolução versão a versão (24/09 → 30/09/2026)

Repositório `github.com/Niko1221/Strata`, MIT desde a v0.1.16. Até 30/09: **31 versões, ~2.800 estrelas, ~280
forks.** Os números abaixo são **do autor**, na máquina de teste dele (RTX 5070 12 GB, Ryzen 5 7600, 64 GB DDR5),
salvo quando indicado. Não há medição independente além da nossa.

## Leitura de prompt: o ganho mais forte (mesmo hardware)

Prompt de 32K tokens, modelo Q2_0:

| Versão | Data | Prefill | O que mudou |
|---|---|---|---|
| até v0.1.12 | 24–27/09 | 572 tok/s | — |
| v0.1.13 | 28/09 | 1.290 | prompts longos ~2× mais rápidos |
| v0.1.22 | 29/09 | 1.646 | atenção nos tensor cores |
| v0.1.24 | 29/09 | 1.797 | seleção da atenção esparsa (QSA) nos tensor cores, 3,3–3,9× nessa etapa |
| v0.1.25 | 29/09 | 2.030 | kernels fundidos, cópias fora do motor de cópia |
| README atual | 30/09 | **2.170** | **≈ 3,8× em 5 dias** |

O IQ3_XXS/IQ3_S seguiu o mesmo caminho: IQ3_S de 374–397 tok/s (v0.1.4) para 1.620 tok/s hoje, cerca de 4×.
Ressalva: a v0.1.15 diz que as tabelas antigas subestimavam o prefill (1,2–2,4×), então parte do salto é método de
medição.

## Geração: ganhos menores, mas contínuos

- v0.1.5: KV no RAM para contextos ≥ 64K, que libera VRAM para mais especialistas (Q2_0 a 262K: 50,9 → 62,6 tok/s).
- v0.1.7: "prompt lookup" (rascunho copiado da própria conversa): edições de código 6–11% mais rápidas.
- v0.1.19: `--calibrate`, ajuste por PC (o autor mediu +7,6% no Coder).
- v0.1.23: janela de verificação em lote: 81 → 89 e 105 → 118 tok/s (5080 + 3090), saída idêntica.
- v0.1.29: amostragem (temperatura > 0) até 40% mais rápida, com o mesmo texto para a mesma seed.
- README atual: IQ2_XS 79 tok/s (chat curto) / 63 (128K); Q2_0 93 / 74.

## Funcionalidades e engenharia no período

- Cache de conversa: continuar um chat de 7,7K tokens passou de 12,9 s para 0,3 s para começar (v0.1.3).
- Várias GPUs por divisão de camadas (v0.1.21), AMD ROCm (v0.1.25, RDNA4 na v0.1.30), RTX 20 (v0.1.27).
- Endpoints compatíveis com o llama.cpp e APIs OpenAI e Anthropic (Claude Code funciona, v0.1.17/v0.1.23).
- v0.1.30: `--idle-unload`, `POST /unload`/`/load`, `--min-free-vram-mib` e `--before-load`, para dividir a GPU com
  outros servidores; contextos além dos 262K treinados (experimental).

## Estabilidade: o outro lado da velocidade

Muitas versões corrigem travamentos:
- geração que parava para sempre em placas de muita VRAM (v0.1.12, relatado numa 4090);
- erro na inicialização do MTP (v0.1.6);
- VRAM abaixo da "linha de travamento" depois da cabeça MTP maior da v0.1.27 (v0.1.28). **Nós rodamos a v0.1.27
  com 277 MiB livres, dentro dessa zona.** A v0.1.28 devolveu a margem (421 MiB).
- um pedido cancelado derrubava o seguinte (v0.1.28).

Leitura: um projeto em ritmo de horas entre versões, com checagens explícitas antes de cada uma (saída idêntica
byte a byte à anterior, testes de agulha em 8K–64K, testes do servidor). Mas ainda jovem.

## A comunidade como multiplicador

As notas creditam contribuições de dezenas de pessoas: kernels, AMD, multi-GPU, correções de segurança, Windows. É
o padrão de software aberto em que o ganho não vem de um fabricante de hardware, mas de muita gente otimizando
o mesmo caminho crítico ao mesmo tempo.
