<!--
Prompt v3-L-compact do bench de síntese do Guardian — claude-bridge-exec, 2026-09-23.
CONGELADO PARA AVALIAÇÃO. Não está em produção.

Derivado de guardian-synthesis-v3.md (sha256 95dd113d…70c9e7) para o
experimento H-PROSA-COMPACT, autorizado pelo owner em 2026-09-23 12:06.
Motivo medido (RESULTADO-H-PROSA-A2.md): o A2 do v3 está quase todo na prosa,
"em geral repetido literalmente em pendências, árvore ou forma visual"; o
ledger rotula `não verificado` certo em 254/256 entradas.

Duas mudanças, e só elas (opção (a) do owner):
  1. passo 5: a árvore NÃO é mais escrita em texto; vai apenas no campo
     `arvore` do bloco JSON. O passo continua existindo porque o ledger o
     referencia ("conforme o passo 5") e a árvore estruturada precisa dele.
  2. passo 6 (forma visual) removido inteiro.
Pendências, lacunas, três listas, regras de rastreabilidade e o bloco ledger
completo (inclusive `arvore`) ficam byte a byte idênticos ao v3.
Princípio que o experimento testa: visualizações derivadas devem ser
renderizadas pelo código a partir do ledger, não recontadas pelo LLM.
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

**5. A estrutura do trabalho — só no bloco final, não em texto.** Tronco, ramos e becos abandonados vão APENAS no campo `arvore` do bloco JSON, com carimbo e trecho em cada ref. Não escreva a árvore na resposta. Se os itens não permitirem distinguir ramo de sequência, use `"indistinguivel": true`.

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
