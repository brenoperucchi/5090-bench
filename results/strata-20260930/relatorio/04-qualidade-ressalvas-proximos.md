# Qualidade, ressalvas e próximos passos

## Velocidade não é qualidade: o que medimos até agora

A tarefa: o Guardian resume o estado de agentes de código a partir de uma cronologia de fatos, cada um marcado
como funcionou, falhou ou **não verificado**. O erro que importa é **afirmar como fato o que não foi verificado**
ou inverter fatos.

| Modelo (prompt `v3-compact`, 12 respostas) | A2: "não verificado" afirmado como fato, média (menor é melhor) | Geração na síntese |
|---|---|---|
| **Swift 1.5 IQ2_XS** (fine-tune, Strata) | **4,0** | 219 tok/s |
| **Flash-Next IQ3_XXS** (Strata) | **4,9** | 191 tok/s |
| qwen3-coder-30b (produção anterior, llama.cpp) | 5,6 | 239 tok/s |
| Flash-Next IQ2_XS (Strata) | 9,8 | 232 tok/s |

- **A compressão pesa na qualidade:** o mesmo Flash-Next cai de 9,8 para 4,9 erros ao passar de 2 bits (IQ2_XS) para
  3 bits (IQ3_XXS), de forma consistente nos quatro cenários. O custo foi só ~10–18% de velocidade.
- **O fine-tune Swift 1.5 foi o melhor,** mesmo em 2 bits e com o raciocínio desligado: 4,0, sem perder velocidade.
- Os três passam no C1 (pendências primeiro), e nenhum repetiu a inversão do papel de um host (âncora A3.2b) que o Coder comete.
- **O teste de mesa é um indicador, não um veredito:** concorda com os avaliadores humanos em torno de ρ ≈ 0,7.
  A avaliação cega humana ainda não foi feita.

## Ressalvas técnicas

1. **Determinismo:** com temperatura 0, o Strata ainda gera tamanhos diferentes entre repetições (78–88 tokens
   no prompt curto), mesmo com `STRATA_IQ_MT_MIN=1`. Isso atrapalha comparações que exigem reprodutibilidade.
2. **Estabilidade:** projeto de 6 dias e 31 versões, várias delas com correções de travamento.
3. **Especificidade:** o Strata só roda o Flash-Next (original, Swift 1.5, Coder) em quantizações específicas.
   Não é um motor geral; para outros modelos continua o llama.cpp.
4. **Números do autor não são independentes.** Os nossos são, mas vêm de um único PC.
5. **Disputa pela VRAM:** o Strata ocupa a placa quase inteira. Quando outro serviço (o Ollama do Windows)
   carregou um modelo durante a nossa janela, o Strata subiu com o cache reduzido (12.705 contra 18.390
   especialistas). A v0.1.30 trouxe `--min-free-vram-mib` e `--before-load` para isso.

## Uma segunda GPU ajudaria?

O Strata divide o modelo por camadas entre 2–3 GPUs NVIDIA (sem NVLink). Números do autor (5080 + 3090, Coder):
- leitura de prompt **+18–20%**;
- geração **empatada** com a placa mais rápida sozinha.

Na nossa 5090 o cache já acerta 99,6–99,8% na geração, então **uma 3090/4090 extra quase não aceleraria o
IQ2_XS**. O ganho seria de **qualidade**: com 5090 + 4090 (56 GB de VRAM), versões maiores (IQ3_XXS/IQ3_S, esta
última igual ao modelo cheio nos testes publicados) caberiam quase inteiras nas GPUs. É uma estimativa nossa, ainda
não medida. Preferência: 4090 (a geração acompanha a placa mais rápida). A 3080 12 GB que já temos permitiria
testar o conceito.

## Próximos passos

1. Swift em 3 bits (IQ3_XXS), combinando os dois ganhos, e calibração por modelo.
2. Checar a licença do Swift (Swift Open License 1.0) antes de adotá-lo.
3. Avaliação cega humana, reduzida, entre Coder, IQ2_XS e IQ3_XXS.
4. Investigar o não determinismo com temperatura 0.
5. Ligar o Guardian ao Strata como produção (com o projeto dono do Guardian).

## Perguntas para a conversa

- Até onde vai a curva "software sobre hardware" quando o motor é feito sob medida para **uma** arquitetura? É
  sustentável, ou cada modelo novo vai precisar do seu Strata?
- O ganho de 6–10× veio de reorganizar **onde** cada especialista mora (VRAM, RAM ou SSD) e de ter a CPU
  trabalhando em paralelo. É o mesmo movimento que tornou viáveis os bancos de dados em memória. Qual é o
  próximo gargalo: banda de RAM (DDR4 contra DDR5) ou PCIe?
- Vale investir numa segunda GPU, ou esperar as próximas versões desses motores?
