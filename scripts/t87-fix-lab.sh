#!/usr/bin/env bash
#
# t87-fix-lab.sh — conserta a preparação do laboratório spec-wins.
#
# RODE COMO ROOT no WSL do ryzen9:
#     sudo bash ~/t87-fix-lab.sh
#
# ============================ POR QUE ISTO EXISTE ============================
#
# A preparação anterior VIOLOU uma instrução explícita do README da suíte
# (linhas 46-47):
#
#   "labuser must not be able to read this repo (the graders and the answer key
#    live here). Keep the checkout under /root or /opt with mode 700; never put
#    hidden/, solutions/ or docs/answer-key.md anywhere the agent can list."
#
# O que foi feito: `chmod -R a+rX /opt/spec-wins`. Resultado verificado entrando
# como labuser — ele lia hidden/check_t3.py, solutions/ com as correções de nota
# máxima, e docs/answer-key.md. O agente medido tinha acesso ao gabarito, o que
# invalida a corrida v7 inteira: não importa se usou, não há como provar que não.
#
# A causa raiz foi um "conserto" que removeu o root do reset-lab.sh sem entender
# por que o root estava lá. O root existe JUSTAMENTE porque a suíte precisa ser
# ilegível ao labuser: o reset roda privilegiado, copia só tasks/ e faz chown.
# Remover o privilégio exigiu abrir a suíte — trocou uma inconveniência por uma
# falha de validade.
#
# Este script restaura o desenho da suíte e devolve o privilégio por uma porta
# estreita: uma regra de sudoers para DOIS scripts específicos, não sudo geral.
#
# ============================== O QUE ELE FAZ ===============================
#   1. fecha /opt/spec-wins em modo 700, root:root;
#   2. remove o reset sem-root que eu instalei e o lab contaminado;
#   3. instala sudoers permitindo ao operador do arnês rodar, sem senha,
#      SOMENTE reset-lab.sh e verify.sh — validado com visudo -c;
#   4. roda o reset oficial como root, que é o caminho da suíte;
#   5. verifica que o labuser NÃO lê a suíte e SIM lê as tarefas dele.
#
# O que NÃO faz: não dá sudo ao labuser, não apaga artefatos do llm-bench, não
# toca no llama-server nem no modelo.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "ERRO: rode como root — sudo bash $0" >&2
  exit 1
fi

SUITE="${SPEC_WINS:-/opt/spec-wins}"
U="${LAB_USER:-labuser}"
OPERADOR="${HARNESS_USER:-brenoperucchi}"
H="$(eval echo "~$U")"

[ -d "$SUITE/hidden" ] || { echo "ERRO: $SUITE não parece ser a suíte" >&2; exit 1; }

echo "== 1. fechando a suíte =="
chown -R root:root "$SUITE"
chmod 700 "$SUITE"
# Os três caminhos que o README nomeia explicitamente, por garantia: mesmo que
# alguém afrouxe a raiz depois, estes ficam inacessíveis.
for p in "$SUITE/hidden" "$SUITE/solutions" "$SUITE/docs/answer-key.md"; do
  [ -e "$p" ] && chmod -R go-rwx "$p"
done
echo "   $SUITE agora é $(stat -c '%A %U:%G' "$SUITE")"

echo "== 2. removendo o reset sem-root e o lab contaminado =="
rm -f "$H/reset-lab.sh"
rm -rf "$H"/lab/*
# O /tmp do labuser pode ter sobras da corrida inválida, que seriam dica para a
# próxima — é o mesmo motivo que o reset oficial limpa /tmp.
find /tmp -maxdepth 1 -user "$U" -exec rm -rf {} + 2>/dev/null || true
echo "   reset sem-root removido, lab e /tmp limpos"

echo "== 3. sudoers estreito para o arnês =="
# Dois scripts, caminho absoluto, sem argumentos livres de caminho. NÃO é sudo
# geral: o operador continua sem poder rodar qualquer outra coisa como root.
cat > /etc/sudoers.d/t87-lab <<EOF
$OPERADOR ALL=(root) NOPASSWD: $SUITE/scripts/reset-lab.sh, $SUITE/scripts/verify.sh
EOF
chmod 440 /etc/sudoers.d/t87-lab
if visudo -c >/dev/null 2>&1; then
  echo "   /etc/sudoers.d/t87-lab instalado e validado"
else
  echo "   CONFIG DE SUDOERS INVÁLIDA — removendo" >&2
  rm -f /etc/sudoers.d/t87-lab
  exit 1
fi

echo "== 4. reset oficial, como a suíte desenhou =="
cd "$SUITE"
LLAMA_SERVER="${LLAMA_SERVER:-http://192.168.0.125:18087}" ./scripts/reset-lab.sh

echo
echo "== 5. verificação — as duas propriedades que importam =="
echo -n "labuser LÊ a suíte? (esperado: Permission denied) ... "
su - "$U" -c "ls $SUITE" 2>&1 | head -1
echo -n "labuser lê o gabarito? (esperado: Permission denied) ... "
su - "$U" -c "head -1 $SUITE/docs/answer-key.md" 2>&1 | head -1
echo -n "labuser tem as tarefas dele? ... "
su - "$U" -c 'ls ~/lab' 2>&1 | tr '\n' ' '; echo
echo -n "operador roda o verify sem senha? ... "
su - "$OPERADOR" -c "sudo -n $SUITE/scripts/verify.sh --help >/dev/null 2>&1 && echo sim || echo 'checar manualmente'"
echo
echo "PRONTO. As duas primeiras linhas PRECISAM dizer Permission denied."
echo "Se alguma delas listar conteúdo, o agente medido vê o gabarito e nenhuma"
echo "corrida vale — reporte ao claude-bridge-exec antes de rodar qualquer coisa."
