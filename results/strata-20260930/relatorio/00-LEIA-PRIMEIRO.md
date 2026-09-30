# Software × hardware na RTX 5090: o caso Strata (30/09/2026)

Relatório do projeto llm-bench, preparado para a conversa semanal sobre a evolução dos LLMs locais
contra o hardware disponível.

## A tese

A aposta que vínhamos discutindo: **nos LLMs locais, o software ganha participação sobre o hardware.** Na mesma
placa, com o mesmo modelo, a forma de executar decide se ele é inutilizável ou de produção.

O Strata é, até agora, a evidência mais forte dessa aposta no nosso próprio hardware.

## O fato central

**Mesmo modelo (Qwen3.8-Flash-Next, o topo da família Qwen3.8), mesma RTX 5090, mesmo PC:**

| Como executado | Geração (tokens/s) | Carga do modelo | Fonte |
|---|---|---|---|
| llama.cpp (fork Codacus, 19/09), IQ3_XXS dinâmico, especialistas na CPU | **16–27** (a quente) | ~4 min 20 s | medição nossa, 19/09 |
| **Strata v0.1.30 calibrado (30/09), IQ2_XS** | **155–172** | ~30–40 s | medição nossa, 30/09 |

- **Ganho de ~6 a ~10 vezes na geração**, e carga ~7 vezes mais rápida, sem trocar nenhuma peça.
- **Ressalva de comparação:** as quantizações não são idênticas (IQ3_XXS dinâmico da Unsloth no llama.cpp,
  IQ2_XS GSQ-RCO da ISTA-DASLab no Strata). A comparação exata, IQ3_XXS nos dois, está sendo preparada.
- **Na prática:** o modelo passou de "cabe, mas não serve" para **produção**. Desde 30/09 ele é o modelo local de
  produção desta máquina.

## E o software continua acelerando

O Strata foi publicado em **24/09/2026**. Em 6 dias saíram **31 versões** (v0.1.0 → v0.1.30). O projeto tem
**~2.800 estrelas e ~280 forks**, com contribuições de dezenas de pessoas. Só na máquina de teste do autor
(RTX 5070 de 12 GB):
- a leitura de prompt de 32K tokens passou de **572 → 2.170 tokens/s (~3,8×)**, sem mudar o hardware;
- a geração subiu ~10–20%, e as respostas longas mais com o MTP ajustado.

Na nossa 5090, entre a v0.1.27 e a v0.1.30 com calibração automática, a geração **nas respostas longas reais**
(síntese de ~1.200–2.250 tokens) subiu de **106 para 163 tokens/s (+55%)**. Foram ~2 dias de software.

## Os arquivos

1. [`01-flash-next-llamacpp-vs-strata.md`](01-flash-next-llamacpp-vs-strata.md): as medições, o método, cada
   versão e a calibração.
2. [`02-strata-evolucao-releases.md`](02-strata-evolucao-releases.md): a linha do tempo das versões e o que cada
   uma trouxe, no mesmo hardware.
3. [`03-panorama-5090-software.md`](03-panorama-5090-software.md): outros ganhos de software na mesma placa
   (llama.cpp com MTP, Windows × WSL, modelos MoE) e a tabela geral de velocidade.
4. [`04-qualidade-ressalvas-proximos.md`](04-qualidade-ressalvas-proximos.md): o que ainda não sabemos
   (qualidade, determinismo, estabilidade), a questão de uma segunda GPU e os próximos passos.

## O hardware

- GPU: **NVIDIA RTX 5090, 32 GB**, driver 616.64 (Windows 11, build 26200)
- CPU: **AMD Ryzen 9 5950X** (16 núcleos, AVX2, sem AVX-512), memória DDR4
- RAM: **64 GB**
- Disco dos modelos: NVMe (E:)
