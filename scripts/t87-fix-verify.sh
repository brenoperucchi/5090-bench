#!/usr/bin/env bash
#
# t87-fix-verify.sh — faz o corretor usar o Python do labuser.
#
# RODE COMO ROOT no WSL do ryzen9:
#     sudo bash ~/t87-fix-verify.sh
#
# ============================== O PROBLEMA ==============================
#
# `sudo /opt/spec-wins/scripts/verify.sh t2_metrics` falha com
# ModuleNotFoundError: No module named 'flask'.
#
# Motivo: o corretor roda como root e usa o Python do root, que não tem flask.
# O flask vive no venv do labuser. O README manda invocar assim:
#
#     PYTHON=/home/labuser/venv/bin/python ./scripts/verify.sh t2_metrics
#
# Mas por sudo isso não funciona: `sudo PYTHON=... verify.sh` faz o comando
# efetivo ser outro, e a regra de sudoers — estreita de propósito — casa o
# caminho exato de verify.sh e recusa a variação. A recusa está CORRETA; foi ela
# que provou que a regra não é sudo geral disfarçado.
#
# ============================== A SOLUÇÃO ==============================
#
# Um wrapper de dono root que fixa o PYTHON e chama o verify.sh. Entra no
# sudoers no lugar do verify.sh cru.
#
# Por que wrapper e não a tag SETENV do sudoers: SETENV permitiria ao operador
# injetar QUALQUER variável de ambiente num processo root. O wrapper fixa uma
# variável, escolhida por quem escreveu a regra, e o operador não controla
# nenhuma. Mesma função, superfície muito menor — e autodocumentado, porque o
# arquivo diz qual Python usa e por quê.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "ERRO: rode como root — sudo bash $0" >&2
  exit 1
fi

SUITE="${SPEC_WINS:-/opt/spec-wins}"
U="${LAB_USER:-labuser}"
OPERADOR="${HARNESS_USER:-brenoperucchi}"
PY="/home/$U/venv/bin/python"
WRAPPER="$SUITE/scripts/verify-lab.sh"

[ -x "$SUITE/scripts/verify.sh" ] || { echo "ERRO: não achei $SUITE/scripts/verify.sh" >&2; exit 1; }
[ -x "$PY" ] || { echo "ERRO: não achei o python do venv em $PY" >&2; exit 1; }
"$PY" -c 'import flask, pytest' || { echo "ERRO: o venv do labuser não tem flask/pytest" >&2; exit 1; }

echo "== 1. wrapper =="
cat > "$WRAPPER" <<EOF
#!/usr/bin/env bash
# verify-lab.sh <tarefa> — chama o corretor oficial com o Python do venv do
# $U, que é onde flask e pytest vivem. Gerado por t87-fix-verify.sh.
set -euo pipefail
cd "$SUITE"
exec env PYTHON="$PY" "$SUITE/scripts/verify.sh" "\$@"
EOF
chown root:root "$WRAPPER"
chmod 700 "$WRAPPER"
echo "   $WRAPPER ($(stat -c '%A %U:%G' "$WRAPPER"))"

echo "== 2. sudoers =="
# O verify.sh cru SAI da regra: sem o PYTHON certo ele dá falso negativo no
# t2_metrics, e falso negativo silencioso é pior que comando recusado.
cat > /etc/sudoers.d/t87-lab <<EOF
$OPERADOR ALL=(root) NOPASSWD: $SUITE/scripts/reset-lab.sh, $WRAPPER
EOF
chmod 440 /etc/sudoers.d/t87-lab
if visudo -c >/dev/null 2>&1; then
  echo "   regra atualizada: reset-lab.sh + verify-lab.sh"
else
  echo "   SUDOERS INVÁLIDO — removendo" >&2
  rm -f /etc/sudoers.d/t87-lab
  exit 1
fi

echo
echo "== 3. verificação =="
# `|| true` em cada linha: as tarefas estão no estado defeituoso, então FALHA é
# o resultado esperado. Sem isto o set -e abortaria no primeiro acerto — foi o
# bug do script anterior, que se matava ao dar certo.
for t in t1_ratelimit t2_metrics t3_pipeline; do
  echo "--- $t ---"
  su - "$OPERADOR" -c "sudo -n $WRAPPER $t" 2>&1 | tail -3 || true
done
echo
echo "PRONTO. O t2_metrics NÃO deve mais dizer ModuleNotFoundError: flask."
echo "Falha nas checagens é esperada — as tarefas estão com os defeitos originais."
echo "O que não pode aparecer é erro de ambiente: módulo ausente, porta ocupada,"
echo "ou permissão negada. Esses são nossos; os outros são do agente."
