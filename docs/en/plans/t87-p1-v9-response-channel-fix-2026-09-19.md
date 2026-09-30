# T87 P1 — resposta de canal do harness v9

- status: **implemented, not executed**
- harness: `t87-p1-harness-v9`
- generations consumed by this change: **0**

## Evidência que motivou a correção

Na série v8, 224/238 respostas tinham `content` vazio e
`reasoning_content` preenchido. A mesma amostra mostra `tool_calls` presentes
em todas as 224 respostas. As outras 14/238 também tinham `tool_calls`.
Distribuição por tarefa: t1 `52/52`, t2 `105/108` e t3 `67/78` com
`empty_content_reasoning_with_tool_call`.

Portanto a hipótese de que o harness ignorou as ações não é confirmada pelo
artefato. O código v8 já consumia `message.tool_calls`; não há fallback que
execute texto livre de `reasoning_content`. A divergência de eficiência ainda
precisa de investigação própria.

## Mudança implementada

O v9 registra uma classe de canal por resposta:

- `empty_content_reasoning_with_tool_call`: `content` vazio, raciocínio
  presente e ação estruturada presente;
- `content_with_tool_call` e demais classes explícitas;
- `reasoning_only_no_tool_call` e `empty_response_no_tool_call`: classes de
  defeito de canal, sem ação executável.

`tool_calls` continua sendo a única fonte de ação. Quando não há
`tool_calls`, `reasoning_content` pode preencher o texto final registrado como
`reasoning_content_fallback`; ele nunca é interpretado como comando.

O transcript passa a incluir contagens, classe por turno, fonte do texto final
e o estado do gate. O gate observa os cinco primeiros turnos e encerra se a
fração de classes sem ação exceder `0.5`. O padrão vazio-com-tool-call não
conta como defeito, pois contém a ação estruturada que o harness executa.

O v9 é uma série nova. Ainda não há autorização para consumir as 92 gerações
devolvidas pelo fechamento do v8; qualquer execução depende de decisão owner.

Validação local: `py_compile` e fixtures das três classes passaram; nenhum
endpoint, GPU, Ollama, sandbox remoto ou grader foi acionado.
