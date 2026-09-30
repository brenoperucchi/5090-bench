<!--
Prompt v3-NL (sem ledger) do bench de síntese do Guardian — claude-bridge-exec, 2026-09-23.
CONGELADO PARA AVALIAÇÃO. Não está em produção.

Derivado MECANICAMENTE de guardian-synthesis-v3.md (sha256 95dd113d…70c9e7),
para o experimento H-LEDGER-A2 (v3 com ledger × v3 sem ledger), autorizado pelo
owner em 2026-09-23 11:23. Duas remoções, e só elas:
  1. a seção "## Bloco final obrigatório" inteira (o esquema JSON e as três
     regras sobre ledger, arvore e nao_da_para_saber);
  2. a frase "O texto vem antes; o bloco JSON é o último conteúdo da resposta.",
     que só existe para posicionar o ledger.
Todo o resto da instrução é byte a byte idêntico ao v3. Conferível com diff.
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

Responda em português do Brasil.

---
