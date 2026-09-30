# llm-bench — benchmarks da RTX 5090

[English](README.md) | **Português (Brasil)**

Acervo de medições de desempenho, qualidade e comportamento de LLMs locais
com Ollama na **RTX 5090 de 32 GB**. Reúne experimentos, dados brutos,
scripts, decisões e correções registrados nesta bancada em setembro de 2026.

O foco é entender o que funciona em cada carga: atendimento PT/EN,
tool-calling, pesquisa em múltiplas rodadas, concorrência e contexto longo.
Os resultados pertencem às configurações e amostras descritas nas fontes.

## Comece aqui

| Quero consultar | Documento |
|---|---|
| Prompt completo para pesquisa profunda no ChatGPT (em inglês) | [Brief da pesquisa](docs/en/research/rtx5090-deep-research-brief.md) |
| Experimentos, resultados e evidências por fase | [Catálogo de benchmarks](docs/rtx5090/experimentos.md) |
| Modelos testados e limites de comparação | [Modelos](docs/rtx5090/modelos.md) |
| Achados consolidados e suas ressalvas | [Catálogo de achados](docs/rtx5090/achados.md) |
| Síntese do Guardian: runtime, modelos, prompts, teste de mesa e decisões tipadas (21–24/09) | [Registro dos modelos locais do Guardian](docs/achados/REGISTRO-GUARDIAN-MODELOS-LOCAIS-2026-09-24.md) |
| Registro público detalhado da campanha de setembro | [Registro público de achados](docs/achados/REGISTRO-PUBLICO-LLM-BENCH-2026-09-20.md) |
| Respostas em inglês a perguntas em português | [Achado PT→EN](docs/achados/ACHADO-qwen3-14b-idioma-template-2026-09-12.md) |
| Decisões adotadas e recomendações retiradas | [Decisões](docs/decisoes.md) |
| Método, métricas e como reproduzir | [Metodologia](docs/metodologia.md) |
| Ambiente e cuidados operacionais | [Infraestrutura](docs/infraestrutura.md) |
| Proposta do teste discriminante NUM_PARALLEL (em inglês; não executado) | [Desenho do teste](docs/en/plans/num-parallel-discriminating-test.md) |
| O que falta investigar | [Pendências](docs/pendencias.md) |
| Origem dos documentos e integridade | [Proveniência](docs/proveniencia.md) |

## Como interpretar os resultados

- **Qualidade e velocidade são eixos distintos.** A decisão registrada manteve
  `qwen3:14b` como default e `qwen3.5:9b` como segundo residente; consulte o
  [escopo da decisão](docs/decisoes.md) antes de extrapolar para outra carga.
- **`auto_score` mudou em 10/09/2026:** o denominador passou de 5–6 para 6–7
  checks. Não compare diretamente notas agregadas anteriores e posteriores.
- **Concorrência:** `NUM_PARALLEL=2` reduziu o tempo do lote em 28% e o tempo
  por requisição em 41% na re-medição com `qwen3:14b` e prompt de 2.108 tokens.
  O efeito sobre o teto de prompts muito longos continua sem isolamento causal.
- **Goldset rotulado:** o check determinístico identificou 12/12 defeitos de
  escalação sem falsos positivos no conjunto usado para comparar juízes. Isso
  não demonstra detecção universal de erros em produção.
- **O handoff é fonte de partida.** A conferência do PT→EN encontrou diferenças
  entre seu resumo e os dados brutos; leia o [achado dedicado](docs/achados/ACHADO-qwen3-14b-idioma-template-2026-09-12.md).

As evidências detalhadas estão nos catálogos de experimentos e achados acima.

## Organização

```text
docs/
  rtx5090/              experimentos, modelos e achados consolidados
  achados/              documentação detalhada de achados novos
  history/              handoff e README anterior preservados
  templates/            modelo de registro para novos experimentos
results/                relatórios originais e resultados JSON
prompts/                prompt canônico, backup e tentativas históricas
baseline-3080ti/         baseline antiga e scripts com localização histórica
artifacts/manifest.json  inventário de evidências com SHA-256
tools/inventory.py      verificação offline do acervo
run_chat.py             avaliação de qualidade com goldset PT/EN
bench.py                throughput de geração
bench_engine_ab.py      comparação alternada entre dois endpoints
goldset_chat.json       18 casos com expectativas e rubricas
```

Os caminhos originais foram preservados: vários scripts da **5090** estão em
`baseline-3080ti/repro/`. O [catálogo](docs/rtx5090/experimentos.md) identifica
a que medição pertencem. O nome da pasta não identifica sozinho a GPU usada.

## Verificar o acervo, sem GPU

Requer Python 3.10 ou superior, sem dependências adicionais:

```bash
python3 tools/inventory.py check
```

A verificação confere inventário, tamanhos, hashes, JSONs e links locais da
documentação nova. O mesmo comando roda no GitHub Actions. Ele verifica a
integridade dos arquivos; não confirma as conclusões científicas.

Para rodar novos benchmarks, consulte primeiro a [metodologia](docs/metodologia.md).
As ferramentas de inferência fazem chamadas reais ao Ollama; algumas rotinas
históricas dependem desta bancada ou alteram processos remotos.

## Arquivo histórico

- [Relatório consolidado original](RELATORIO-FINAL-2026-09-04.md): leitura
  histórica, com atualizações e ressalvas posteriores.
- [Baseline RTX 3080 Ti](baseline-3080ti/README.md): métricas de produção
  incluem prefill e não equivalem ao throughput de decode isolado da 5090.
- [Handoff de partida](docs/history/handoff-2026-09-12.md): snapshot do resumo
  da sessão anterior, preservado com suas limitações.
- [Sessões de origem](SESSOES.md): referências de proveniência; transcripts
  completos e estado local do Herdr não fazem parte do repositório público.

O benchmark dedicado de tok/s da 3080 Ti mencionado no README anterior não
foi preservado. Não existe aqui uma comparação controlada entre as duas GPUs.
