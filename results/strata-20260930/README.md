# Strata v0.1.27 — Qwen3.8-Flash-Next IQ2_XS na RTX 5090 (30/09/2026)

Janela sem produção: 14:21:26 → 14:28:51 (-03), autorizada pelo Breno; coordenada com o
claude-bridge-exec (timer da sombra não tocado). Produção religada por
`systemctl start llama-server-18194`, PID novo 45139; /props: 1 slot, n_ctx 32768, qwen3-coder-30b.

## Montagem
- Motor: `strata.exe` 0.1.27, sha256 `814c0162…d4b3e0`, idêntico ao de dentro do zip do release
  (zip sha256 `cbb44dd8…00b839`, publicado no release). Windows nativo, driver 616.64.
- Modelo: ISTA-DASLab Qwen3.8-Flash-Next-GSQ-RCO IQ2_XS (2 shards, sha256 conferidos em 28/09).
- Config do instalador: contexto 32768, KV int8, `--spec 4` (MTP), sem imagens, `127.0.0.1:18199`,
  "experimental speed projection" DESLIGADA.
- Na carga: 33,02 GiB de especialistas na RAM; 18.494 especialistas (24,84 GiB) no cache da VRAM.

## Velocidade (`strata-iq2xs-20260930.json`, instrumento `os_runtime_ab.py`, 3 repetições, 256 tokens)
| prompt | prefill (tok/s) | geração (tok/s) |
|---|---|---|
| médio (2.671 tokens) | 2.700 | 171,0 |
| longo (5.952 tokens) | 3.980 | 156,5 |

Timings reportados pelo próprio servidor. Cópia do instrumento no Windows alterada só para aceitar
`model_alias` quando `/props` não traz `model_path` (não foi necessário: ele traz).

## Síntese do Guardian (16 runs em `../guardian-synthesis-20260921/runs/atual~strata-iq2xs-win~*`)
Prompt `atual`, `enable_thinking=false`, 4 snapshots × (t=0 ×1 + t=0,3 ×3).
Diferença de desenho: o Strata não tem `/tokenize`, então `--max-tokens 12000` fixo em vez de
`--max-tokens-auto` (nos outros modelos o auto deu 12.081–13.087). Todos terminaram em `stop`.

Pré-triagem textual (não é o número final; o que vale é o checklist dos avaliadores cegos):
hit da âncora A3.2b (inversão do papel de um host) no cenário S2 — strata 0/4; qwen3-coder-30b 7/9.

## v0.1.29 (14:38–14:39) e v0.1.30 calibrada (15:08–15:20)
- v0.1.29 (`strata-0129-iq2xs-20260930.json`): geração 159,2 / 154,3 tok/s (médio/longo), prefill longo 4.032;
  cache 18.390 especialistas, 421 MiB de VRAM livre (0.1.27: 277 MiB, abaixo da linha de travamento do autor).
- v0.1.30 (motor sha256 `f0b05726…ba8fb`, igual ao do zip `e6eaf4bd…c1e01`) + `--calibrate`
  (`calibrate-v0.1.30.log`): adotou `--pcie-frac 0.55 --spec-min-p 0.70` (180,7 tok/s na medição dele);
  config ganhou `env.STRATA_IQ_MT_MIN=1` (backup `strata-iq2_xs.json.bak-pre-mtmin`).
  - teste curto de 256 tokens (`strata-0130cal-iq2xs-20260930.json`): geração 155,7 / 151,2; prefill longo 3.552
    (sem ganho visível; 3 repetições; download do Swift rodando em paralelo no disco E:).
  - **na síntese (16 runs, respostas de ~1.200–2.250 tokens)**, timings do servidor, mediana:
    0.1.27 sem calibrar 105,6 tok/s (97–172), aceitação MTP 0,62 → 0.1.30 calibrada **163,4 tok/s (159–172)**,
    aceitação MTP 0,75. Latência por run: 9–22 s → 7,5–13,6 s.
  - pré-triagem A3.2b no cenário S2: 0/4 de novo. Todos os 16 em `stop`.

## Swift 1.5 IQ2_XS e IQ3_XXS (16:20–16:40), mesma calibração e env do IQ2_XS
- Swift: GGUF conferidos contra o SHA256SUMS da UkisAI; IQ3_XXS: parte 1 `219ea929…6d15` e parte 2 idêntica à do
  IQ2_XS (`316b46f3…e113`), ambas conferidas. Configs `strata-swift-iq2_xs.json` e `strata-iq3_xxs.json` com
  `--pcie-frac 0.55 --spec-min-p 0.70` e `STRATA_IQ_MT_MIN=1` (calibração herdada do IQ2_XS, não refeita por modelo).
- Cache na VRAM: IQ2_XS e Swift 18.390 especialistas (24,70 GiB); IQ3_XXS 14.866 (24,17 GiB), RAM 39,97 GiB.
- Teste de mesa v3 (prompt v3-compact, t=0,3, seeds 53–55, 12 respostas; indicador, ρ≈0,7 com humanos):

| modelo | A2 média (menor melhor) | por cenário S3 / S2 / S4 / S1 | C1 | geração na síntese |
|---|---|---|---|---|
| Swift 1.5 IQ2_XS | **4,00** | 7,3,6 / 7,6,1 / 0,2,2 / 3,6,5 | 12/12 | 219 tok/s |
| Flash-Next IQ3_XXS | 4,92 | 5,7,6 / 6,2,5 / 5,4,6 / 3,4,6 | 12/12 | 191 tok/s |
| qwen3-coder-30b (llama.cpp, referência antiga) | 5,64 | 6,10 / 6,7,5 / 4,5,4,4 / 6,5 | 11/11 | 239 tok/s |
| Flash-Next IQ2_XS | 9,75 | 16,16,16 / 6,0,7 / 18,15,9 / 7,6,1 | 12/12 | 232 tok/s |

- Velocidade, teste curto (5 rep., t=0), geração médio/longo e prefill longo: IQ2_XS 163,1/155,4, 3.889;
  Swift 157,1/154,0, 4.024; IQ3_XXS 147,2/151,3, 4.081.

## Produção provisória (30/09, 17:46)
Swift 1.5 IQ2_XS (`strata-swift-iq2_xs.json`), decisão do Breno. Cache 18.390 especialistas, 419 MiB de VRAM
livre, teste de fumaça HTTP 200 `ok`/`stop`. Swift IQ3_XXS medido antes: A2 4,58 (1,3,7 / 5,9,3 / 4,7,7 / 2,1,6),
síntese 188,7 tok/s, teste curto 159,0/150,0, prefill longo 4.063. Leitura: Swift IQ2, Swift IQ3 e Flash IQ3 são
equivalentes no A2 dentro do ruído; só a avaliação humana cega ou mais amostras os separariam.

## 96 GB de RAM, recalibração e produção Swift IQ3_XXS (01/10)
- RAM: 2×32 GB Kingston + 2×16 GB ADATA, DDR4-3200 (antes 64 GB a 2400). Velocidade "limpa" (sem outros
  programas): `strata0131-96gb-*-limpo-r5-20261001.json`. Medições com o CPU-Z aberto a 100% estão separadas e
  **inválidas** em `invalidas-cpuz-20261001/`.
- Swift IQ3_XXS recalibrado (`--calibrate`): `--pcie-frac 0.20 --spec-min-p 0.70` (`…-recal-r5`); depois do ajuste
  da BIOS: `…-posbios-r5` (geração 163/157, leitura longa 4.175). É a produção desde 01/10 (motor 0.1.31).

## Versões 0.1.32, 0.1.33 e 0.1.34 com o Swift IQ3_XXS (01–02/10)
Mesma config da produção, só trocando motor e pasta (`E:\strata-013x`), uma versão por vez na GPU. Instrumento de
velocidade igual (`os_runtime_ab.py`, 5 repetições); mesa Guardian v3-compact (12 respostas, A2).

| motor | geração médio/longo | leitura longo | A2 |
|---|---|---|---|
| 0.1.31 | 163,1 / 157,2 | 4.175 | 6,67 |
| 0.1.32 | 165,6 / 160,9 | 4.123 | 5,50 |
| 0.1.33 | 165,4 / 159,9 | 4.144 | 5,50 |
| 0.1.33 + stager antigo (`STRATA_STAGER_THREADS=4`, `STRATA_STAGER_RING=16`) | 169,6 / 163,7 | 4.126 | 5,08 |
| 0.1.34 | 166,9 / 161,0 | 4.147 | 7,33 |
| 0.1.34 + `--prefill auto:32768` | 166,1 / 159,8 | 4.147 | 5,58 |
| 0.1.34 + `auto:32768` + stager antigo | 164,7 / 161,6 | 4.142 | 5,58 |

Leitura: empate. O A2 do mesmo Swift na 0.1.31 foi 4,58 (config antiga, 30/09) e 6,67 (recalibrado, 01/10), então
variações dessa ordem são ruído de 12 respostas. O benchmark de compreensão de um projeto consumidor (privado, não
publicado) também não mudou entre versões; ligar o raciocínio do modelo mudou muito mais que qualquer versão.

### Prompts longos (`*-longos-20261002.json`, `run_bench.py` do benchmark da comunidade Strata, 3 execuções)
| 0.1.34 | leitura 14,7K | leitura 28,9K | geração | VRAM livre mínima |
|---|---|---|---|---|
| padrão | 4.704 | 4.790 | 151–164 | 779 MiB |
| `auto:32768` | 5.525 (+17%) | 6.226 (+30%) | 153–167 | 771 MiB |
| `auto:32768` + stager | 5.519 | 6.236 | 154–163 | 763 MiB |

O registro do gateway (8.918 pedidos, 30/09) tem mediana de 433 tokens de entrada e máximo de 10.129: nenhum pedido
acima de 15K. Por isso a produção segue na 0.1.31; a 0.1.34 com `auto:32768` fica pronta para quando houver prompts
longos ou contexto maior (o PR #440 rodou 262K numa 5090).
