<!--
Prompt reformulado (braço "v2") do bench de síntese do Guardian — llm-bench-exec, 2026-09-21.
Mesmo destinatário e mesmas seis exigências da INSTRUCTION original (guardian-synthesis-atual.md),
com quatro mudanças de instrumento, não de conteúdo:
  1. rastreabilidade: toda afirmação de fato carrega o carimbo do item;
  2. cabeçalho separado dos itens: o que só "Estado agora"/"Atividade agora" afirma vai em lista própria;
  3. três listas obrigatórias (funcionou / FALHOU / não verificado) e declaração exigida de indistinção — sem texto pronto, para não virar cópia;
  4. bloco final em JSON (ledger) para pontuação por script.
Tudo abaixo do marcador é enviado, concatenado ao markdown do recorte.
-->
<!-- INSTRUCTION-BEGIN -->
Você vai receber a cronologia de um trabalho técnico em andamento. Ela foi montada por um observador automático que lê a tela do executor e interpreta o que vê — ele nunca leu a tarefa original, então a cronologia é o que dá para saber, e nada além.

Quem vai ler sua resposta é o Breno. Ele é o dono do projeto e decide o que acontece nele, mas não acompanhou os detalhes de execução e não quer relatório técnico. Ele quer saber, em regra de negócio: **o que está sendo construído, em que pé está, e o que depende dele.**

## Regras de rastreabilidade (valem para a resposta inteira)

- Cada item da cronologia tem um carimbo `dd/mm hh:mm`. **Toda afirmação sobre um fato traz o carimbo do item de onde veio**, assim: `[21/09 14:12]`. Quando vários itens têm o mesmo carimbo, cite também quatro ou mais palavras do item.
- Duas coisas diferentes, que não podem se misturar: **a ação** que o item descreve (criar, remover, copiar, verificar — e em qual máquina, em qual direção) e **o resultado** dela, no campo **Resultado**.
  - A ação e a direção vêm do texto do item. Se o item diz que algo foi **criado**, não escreva que foi removido; se diz que a migração sai de uma máquina, não a ponha como destino.
  - O resultado vem do campo, copiado como está: "não verificado" **nunca** vira "funcionou" nem "FALHOU" — os dois afirmam um desfecho que ninguém confirmou.
  - Uma remoção pode ter funcionado, e uma criação pode ter falhado: o resultado não diz qual foi a ação.
- Máquina, local, causa, momento: só se o item disser. Se o item não diz onde ou por quê, escreva "local não informado" / "causa não informada". Inventar uma localização plausível é o pior erro possível aqui.
- O cabeçalho (**Estado agora**, **Atividade agora**) é uma leitura de tela separada da cronologia. Se ele afirma algo que **nenhum item registra**, isso vai na lista "Só o cabeçalho diz" — nunca no corpo como fato, nunca nas listas de resultado.

## O que eu quero de você, nesta ordem

0. **Decisões pendentes — primeiro bloco da resposta, antes de qualquer outra coisa.** Tudo que está parado à espera do Breno, com carimbo. Se não houver nenhuma registrada nos itens, escreva literalmente: "Nenhuma decisão pendente registrada nos itens."

1. **A regra de negócio.** Em poucas frases, sem jargão: qual é o problema real que esse trabalho resolve e por que ele importa. Termo técnico inevitável se explica na própria frase.

2. **Só o cabeçalho diz.** Lista do que "Estado agora"/"Atividade agora" afirmam e nenhum item registra. Se tudo do cabeçalho tem item correspondente, escreva "Nada — o cabeçalho é coberto pelos itens."

3. **Três listas separadas, com carimbo em cada linha:**
   - **Funcionou** — só itens cujo Resultado é "funcionou".
   - **FALHOU** — só itens cujo Resultado é "FALHOU". Se nenhum item tiver esse resultado, diga isso explicitamente, com suas palavras.
   - **Não verificado** — o que o observador viu na tela e ninguém confirmou. Se for longo, agrupe por tema, mas cada linha mantém o carimbo.

4. **A estrutura do trabalho.** A cronologia é uma lista plana, mas o trabalho real pode não ser: tronco, ramos, folhas e becos abandonados. Se os itens permitirem montar isso, monte, com os carimbos de cada nó e o estado de cada um. Se **não** permitirem distinguir ramo de sequência, declare isso explicitamente, com suas palavras, e apresente o que há como linha do tempo. Uma árvore errada é pior que uma lista, porque parece que alguém entendeu a estrutura.

5. **O que NÃO dá para saber por estes itens.** Cada lacuna listada tem de ser algo que **nenhum item responde**. Antes de listar, confira: se um item responde, não é lacuna. Lacuna preenchida com suposição plausível é pior que lacuna declarada, porque ele vai decidir achando que sabe.

6. **Uma forma visual** — escolha o formato que melhor comunica este conteúdo (linha do tempo, tabela, diagrama em texto). O critério é um só: o Breno bate o olho e entende sem ler o texto todo. Não force um formato que não sirva.

## Bloco final obrigatório

Termine a resposta com um bloco de código marcado exatamente como ```json ledger``` contendo um único objeto JSON com esta forma (sem comentários, sem campos a mais):

```
{
  "pendencias": [{"ref": "dd/mm hh:mm", "trecho": "quatro ou mais palavras do item", "o_que_decidir": "..."}],
  "so_cabecalho": ["afirmação do cabeçalho sem item correspondente", "..."],
  "ledger": [{"ref": "dd/mm hh:mm", "trecho": "quatro ou mais palavras do item", "afirmacao": "o que você disse sobre ele", "resultado": "funcionou | FALHOU | não verificado"}],
  "arvore": {"indistinguivel": true_ou_false, "tronco": {"nome": "...", "refs": [{"ref": "dd/mm hh:mm", "trecho": "quatro ou mais palavras do item"}]}, "ramos": [{"nome": "...", "estado": "...", "refs": [{"ref": "dd/mm hh:mm", "trecho": "..."}]}], "mortos": [{"nome": "...", "refs": [{"ref": "dd/mm hh:mm", "trecho": "..."}]}]},
  "nao_da_para_saber": ["...", "..."]
}
```

- `ledger` inclui **todo** item com Resultado "funcionou" ou "FALHOU", e todo item "não verificado" que você citou no texto. `resultado` copia o campo do item.
- `arvore.indistinguivel` é `true` **ou** `false`, conforme o que você concluiu no passo 4 — as duas respostas são igualmente esperadas, decida pelos itens. Quando for `true`, `ramos` e `mortos` podem ser listas vazias; quando for `false`, monte a árvore.
- As refs da árvore têm carimbo **e** trecho, pelo mesmo motivo do ledger: vários itens dividem o mesmo carimbo.
- `so_cabecalho` vazio significa que o cabeçalho é coberto pelos itens.

Responda em português do Brasil. O texto vem antes; o bloco JSON é o último conteúdo da resposta.

---

