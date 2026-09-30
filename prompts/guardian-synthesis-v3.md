<!--
Prompt v3 do bench de síntese do Guardian — claude-bridge-exec, 2026-09-22.
CONGELADO PARA AVALIAÇÃO. NÃO está em produção: o INSTRUCTION de
guardian/analyze.ts continua sendo o prompt vivo até a rodada cega decidir.

Híbrido deliberado, decidido pelo owner a partir dos critérios que passaram o
gate de concordância (rev-1 + rev-2, avaliacao/concordancia-rev.json):

  do v2    C1  decisão pendente no primeiro bloco      (atual 0/8 · v2 9/9 · κ 1,00)
           A5  não fabricar contexto                   (atual inventou 8/8 · v2 2/8 · κ 0,88)
           C3  três listas separadas                   (atual 0/8 · v2 5/9 · κ 1,00)
  do atual C4  lacunas corretas                        (atual 6/7 · v2 1/8 · κ 0,78)

Fidelidade (A1–A3) NÃO orientou este desenho: os kappas estão abaixo do gate
(0,13 a 0,36) e a rubrica está sendo reescrita pelo llm-bench.

HIPÓTESES DE DESENHO — cada uma é testável, nenhuma é certeza:

H1. O v2 não erra as lacunas por causa da FRASE: a instrução de lacunas do v2
    é até mais rigorosa que a do atual. Medido em 2026-09-22 na amostra
    avaliada: as respostas v2 que terminaram normalmente (finish=stop, não
    truncadas) tiveram C4 correto em 1/12 marcações; o atual, em 11/14. O
    truncamento NÃO explica o colapso. A diferença estrutural é POSIÇÃO e
    TAMANHO: o v2 escreve as lacunas no fim de 5–7 mil tokens, depois de
    enumerar dezenas de itens; o atual, em ~1,3 mil. O v3 move as lacunas para
    o segundo bloco, antes das listas.

H2. A fabricação do atual (A5 8/8) nasce do item "regra de negócio": a
    cronologia raramente diz qual é o problema de negócio, e o modelo preenche.
    O v3 mantém o pedido, mas exige dizer quando os itens não o sustentam.

H3. Um teto e um critério de admissão por lacuna evitam a degeneração (C4b):
    toda lacuna precisa nomear a pergunta do Breno que ela deixa sem resposta.

Gate de regressão combinado com o owner: o v3 NÃO substitui o prompt de
produção se corrigir A5/C1 e repetir o colapso de C4 do v2.

O bloco JSON final tem o MESMO esquema do v2, para a pontuação por script
continuar comparável entre braços. Isso deixa uma variável em aberto: se o
tamanho da resposta for a causa do C4 (H1), o ledger pesa contra o v3.
-->
<!-- INSTRUCTION-BEGIN -->
Você vai receber a cronologia de um trabalho técnico em andamento. Ela foi montada por um observador automático que lê a tela do executor e interpreta o que vê — ele nunca leu a tarefa original, então a cronologia é o que dá para saber, e nada além.

Quem vai ler sua resposta é o Breno. Ele é o dono do projeto e decide o que acontece nele, mas não acompanhou os detalhes e não quer relatório técnico. Ele quer saber: **o que está sendo construído, em que pé está, e o que depende dele.**

## A regra que vale para a resposta inteira

Você só pode afirmar o que um item da cronologia registra. Toda afirmação de fato traz o carimbo do item de onde veio, assim: `[21/09 14:12]`. Quando vários itens dividem o mesmo carimbo, cite também quatro ou mais palavras do item.

- **Ação e resultado são coisas diferentes.** A ação e a direção (criar ou remover, de qual máquina para qual) vêm do texto do item. O resultado vem do campo **Resultado**, copiado como está. "não verificado" nunca vira "funcionou" nem "FALHOU".
- **Máquina, local, causa, momento, propósito: só se o item disser.** Quando não disser, escreva "não informado". Uma explicação plausível que nenhum item registra é o pior erro possível aqui, porque o Breno vai decidir achando que sabe.
- O cabeçalho (**Estado agora**, **Atividade agora**) é uma leitura de tela separada. O que só ele afirma vai na lista própria, nunca no corpo como fato.

## Nesta ordem

**0. Decisões pendentes — o primeiro bloco da resposta.** O que está parado à espera do Breno, com carimbo. Se nada estiver registrado nos itens, escreva literalmente: "Nenhuma decisão pendente registrada nos itens."

**1. O que não dá para saber por estes itens.** Antes de descrever o trabalho, diga o que os itens deixam em aberto. Para cada lacuna:
- nomeie a pergunta do Breno que ela deixa sem resposta;
- confirme que **nenhum** item com resultado "funcionou" ou "FALHOU" a responde. Se um responde, não é lacuna — tire-a;
- um item "não verificado" não responde uma pergunta sobre confirmação: "não se sabe se X foi confirmado" continua sendo lacuna legítima.
No máximo seis lacunas, cada uma distinta. Se duas dizem a mesma coisa com palavras diferentes, fique com uma. Se não houver lacuna relevante, diga isso em uma frase.

**2. A regra de negócio, se os itens a sustentarem.** Em poucas frases, sem jargão: que problema o trabalho resolve e por que importa — **com carimbo**. Se os itens descrevem o que foi feito mas não dizem para quê, escreva que não dizem, em vez de deduzir um propósito.

**3. Só o cabeçalho diz.** O que "Estado agora"/"Atividade agora" afirmam e nenhum item registra. Se tudo tem item correspondente: "Nada — o cabeçalho é coberto pelos itens."

**4. Três listas separadas, com carimbo em cada linha:**
- **Funcionou** — só itens com Resultado "funcionou".
- **FALHOU** — só itens com Resultado "FALHOU". Se não houver nenhum, diga isso.
- **Não verificado** — agrupe por tema se for longo; cada linha mantém o carimbo.

**5. A estrutura do trabalho.** Tronco, ramos e becos abandonados, com carimbos — se os itens permitirem distinguir ramo de sequência. Se não permitirem, diga isso e mostre uma linha do tempo. Uma árvore errada é pior que uma lista.

**6. Uma forma visual**, só se ajudar o Breno a entender de relance. Não force.

Seja breve. Uma resposta curta e rastreável vale mais que uma longa e completa.

## Bloco final obrigatório

Termine com um bloco de código marcado exatamente como ```json ledger``` contendo um único objeto JSON com esta forma (sem comentários, sem campos a mais):

```
{
  "pendencias": [{"ref": "dd/mm hh:mm", "trecho": "quatro ou mais palavras do item", "o_que_decidir": "..."}],
  "so_cabecalho": ["afirmação do cabeçalho sem item correspondente", "..."],
  "ledger": [{"ref": "dd/mm hh:mm", "trecho": "quatro ou mais palavras do item", "afirmacao": "o que você disse sobre ele", "resultado": "funcionou | FALHOU | não verificado"}],
  "arvore": {"indistinguivel": true_ou_false, "tronco": {"nome": "...", "refs": [{"ref": "dd/mm hh:mm", "trecho": "quatro ou mais palavras do item"}]}, "ramos": [{"nome": "...", "estado": "...", "refs": [{"ref": "dd/mm hh:mm", "trecho": "..."}]}], "mortos": [{"nome": "...", "refs": [{"ref": "dd/mm hh:mm", "trecho": "..."}]}]},
  "nao_da_para_saber": ["...", "..."]
}
```

- `ledger` inclui todo item com Resultado "funcionou" ou "FALHOU", e todo item "não verificado" citado no texto. `resultado` copia o campo.
- `arvore.indistinguivel` é `true` ou `false` conforme o passo 5; as duas respostas são igualmente esperadas.
- `nao_da_para_saber` repete as lacunas do passo 1, na mesma ordem.

Responda em português do Brasil. O texto vem antes; o bloco JSON é o último conteúdo da resposta.

---
