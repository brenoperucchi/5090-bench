<!--
Cópia verbatim da constante INSTRUCTION de claude-bridge/guardian/analyze.ts (linha 31),
extraída em 2026-09-21 para o braço "atual" do bench de síntese do Guardian.
analyze.ts sha256: 26f541e344fe1e94945f7a2b398764c414ddbeb8331a3831b8552b80db2b7bee
INSTRUCTION sha256: 74c155159d6376fadca0f3aa25ca4c560f24839f2d85da2df23260a9daba1824
Tudo abaixo do marcador é enviado como está, concatenado ao markdown do recorte
(`?format=prompt`), exatamente como `analyze.ts::main` faz. Não editar.
-->
<!-- INSTRUCTION-BEGIN -->
Você vai receber a cronologia de um trabalho técnico em andamento. Ela foi montada por um observador automático que lê a tela do executor e interpreta o que vê — ele nunca leu a tarefa original, então a cronologia é o que dá para saber, e nada além.

Quem vai ler sua resposta é o Breno. Ele é o dono do projeto e decide o que acontece nele, mas não acompanhou os detalhes de execução e não quer relatório técnico. Ele quer saber, em regra de negócio: **o que está sendo construído, em que pé está, e o que depende dele.**

O que eu quero de você:

1. **A regra de negócio.** Em poucas frases, sem jargão: qual é o problema real que esse trabalho resolve e por que ele importa. Se aparecer um termo técnico inevitável, explique-o na própria frase — não em nota de rodapé.

2. **Uma forma visual.** Escolha o formato que melhor comunica ESTE conteúdo — diagrama em texto, tabela, linha do tempo, fluxo, o que for. Não force um formato que não sirva. O critério é um só: o Breno bate o olho e entende sem ler o texto todo.

3. **A estrutura do trabalho, em ramificações.** A cronologia é uma lista plana, mas o trabalho real não é: há uma frente principal, frentes que saem dela, e becos que foram abandonados no caminho. Monte essa árvore — o que é tronco, o que é ramo, o que é folha, e o que morreu. Em cada nó diga em que pé está. Se dois ramos convergirem para o mesmo ponto, mostre isso.

   Se a cronologia não permitir distinguir ramo de sequência, **diga que não permite** em vez de inventar uma hierarquia plausível. Uma árvore errada é pior que uma lista, porque parece que alguém entendeu a estrutura.

4. **O que funcionou e o que falhou**, separados de forma inequívoca. Vários itens trazem um campo de resultado; use-o, e quando ele disser "não verificado", diga que não foi verificado — não converta em sucesso.

5. **O que espera decisão dele.** Se houver algo parado à espera do Breno, isso vai no topo da resposta, não no fim.

6. **O que NÃO dá para saber por estes itens.** Seja explícito. Lacuna preenchida com suposição plausível é pior que lacuna declarada, porque ele vai decidir achando que sabe.

Responda em português do Brasil, no formato que você julgar melhor. Não precisa seguir a ordem acima se outra organização comunicar melhor.

---

