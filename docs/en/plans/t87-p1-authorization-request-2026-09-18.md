# T87 P1 — autorização necessária antes da execução

Status: **aguardando autorização operacional do owner; nenhuma chamada P1
executada neste registro**.

## O que P1 mede

P1 mede somente a variância do instrumento `spec-wins` que sustenta a
comparação publicada 17/17 contra 14/17. Não é ainda a reprodução do Qwen3.8,
uma decisão de adoção, um benchmark do watcher ou uma alteração de produção.

## Carga autorizável

- Modelo: `qwen3.6:35b-a3b`, já indicado como disponível no endpoint local.
- Runtime: fork `thecodacus/llama.cpp`, em diretório isolado, com commit,
  flags de build, arquitetura CUDA, binary hash e endpoint registrados. Ollama
  não é o runtime de P1.
- Suíte: `spec-wins` **sem modificar** `hidden/`, `solutions/` ou
  `docs/answer-key.md`.
- Repetições: **5 execuções completas**, com seeds distintos e registrados.
- Tarefas por execução: **17**.
- Gerações mínimas: **85 chamadas** (`5 × 17`), fora qualquer warm-up técnico.
  O plano P1 não define warm-up adicional; se o harness exigir um, ele deve
  ser contado e rotulado separadamente.
- Saída obrigatória: pass/fail por tarefa, total por execução, seed efetivo e
  transcript completo de cada tarefa.

## Pré-condições que precisam ser fixadas

1. O fork deve ser construído isoladamente, sem substituir o Ollama. O
   endpoint/runtime controlado e seu commit/configuração devem ser registrados
   antes da primeira chamada. O gateway usado no smoke do watcher não deve ser
   presumido como o harness de P1: seu contrato observado não expõe seed.
2. A configuração deve aceitar e registrar os cinco seeds distintos; sem isso
   a pergunta de variância não é respondida.
3. O modelo precisa estar disponível para llama.cpp como GGUF standalone (ou
   conjunto de shards/draft explicitamente documentado). O catálogo Ollama
   observado informa formato GGUF e total de `22621314381` bytes, mas seu
   digest é de tag/manifesto e não substitui o SHA-256 de cada arquivo.
4. O artefato do harness, o commit do `spec-wins`, o modelo efetivamente
   resolvido e os parâmetros de geração precisam ser hash-addressed.
5. Não pode haver mistura de métricas Ollama/llama.cpp, nem dois runtimes
   usando a GPU simultaneamente. Native Windows, WSL2 e sessão do processo
   devem ser registrados como contexto distinto.

## Autorização que deve ser dada de uma vez

O owner precisa autorizar diretamente, em um único pacote:

- as 85 chamadas de geração controladas para `qwen3.6:35b-a3b`;
- construir e executar o fork thecodacus `llama.cpp` em diretório isolado,
  incluindo qualquer toolchain/artefato local necessário;
- copiar ou baixar o(s) GGUF(s) exato(s) para o diretório dedicado. Se o blob
  do Ollama for extraível e compatível, a cópia local pode evitar novo
  download; se não for, o download do artefato exato deve ser autorizado
  dentro deste mesmo pacote;
- iniciar um `llama-server`/endpoint OpenAI-compatible dedicado para P1;
- carregar/usar o modelo na máquina da RTX 5090 e reservar a GPU
  exclusivamente para esse runtime durante as 85 chamadas;
- a persistência dos transcripts e métricas somente nos artefatos próprios do
  experimento;
- qualquer warm-up estritamente técnico adicional, se necessário, com
  quantidade informada antes da execução.

Não está incluído automaticamente: mudança de configuração do gateway/Ollama,
promoção para produção ou uso simultâneo de runtimes. O pacote deve dizer se
será necessário descarregar/parar uma residência Ollama para obter exclusividade
da GPU; essa ação precisa estar explicitamente incluída e autorizada, ou P1
fica bloqueado. Qualquer cleanup ou reset futuro exigirá autorização separada e preservará
`gpt-5.6-luna` com `reasoning_effort=xhigh`, com estado before/after e
`unknown` quando não observável.

## Saída e gate

O resultado deve registrar os cinco totais, a matriz 5×17, transcripts e a
variância. Se os totais atravessarem 17 ou a dispersão tornar 14 versus 17
indistinguível, registrar **NO-GO da justificativa do programa** e parar antes
da Fase 1. Caso contrário, registrar o go/no-go de Fase 0 com as limitações
de proveniência P2/P3.
