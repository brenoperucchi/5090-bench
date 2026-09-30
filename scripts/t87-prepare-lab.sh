#!/usr/bin/env bash
#
# t87-prepare-lab.sh — preparação do laboratório spec-wins no WSL do ryzen9.
#
# RODE UMA VEZ, COMO ROOT, no WSL do ryzen9:
#     sudo bash t87-prepare-lab.sh
#
# Depois disto, NADA MAIS precisa de root: o reset entre corridas passa a rodar
# como o próprio labuser, que é dono de tudo o que o reset apaga.
#
# O que este script faz, e nada além:
#   1. cria o usuário `labuser` sem sudo, sem docker, sem acesso a /root;
#   2. cria o venv dele e instala pytest + flask;
#   3. CONGELA as versões instaladas num requirements.lock — o script original da
#      suíte instala sem pin, e sem pin duas instalações em datas diferentes
#      produzem ambientes diferentes: a variância medida passaria a incluir
#      variância do PyPI;
#   4. instala a chave pública do operador do arnês;
#   5. instala um reset SEM ROOT em ~labuser/reset-lab.sh, equivalente ao
#      scripts/reset-lab.sh da suíte mas sem o `chown` — desnecessário porque o
#      labuser já é dono;
#   6. verifica e imprime o que ficou, para o resultado ser conferível.
#
# O que este script NÃO faz: não dá sudo ao labuser, não instala docker, não
# toca no llama-server, não apaga nada fora de ~labuser, e não mexe no checkout
# do spec-wins.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "ERRO: rode como root — sudo bash $0" >&2
  exit 1
fi

U="${LAB_USER:-labuser}"
SUITE="${SPEC_WINS:-/home/brenoperucchi/t87-runtime/spec-wins}"
# Chave pública dedicada, gerada em .secrets/labuser_key no host do arnês.
# Não é a chave pessoal do Breno: serve só para o agente entrar no laboratório.
OPERATOR_KEY='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEnLrp7O7m7GDtoMSZ3Upbv4K2UxnqV/YCGnpjFtHJFr t87-labuser@llm-bench'

if [ ! -d "$SUITE/tasks" ]; then
  echo "ERRO: não achei $SUITE/tasks — ajuste SPEC_WINS=" >&2
  exit 1
fi

echo "== 1. usuário =="
if id "$U" >/dev/null 2>&1; then
  echo "   $U já existe, mantendo"
else
  useradd -m -s /bin/bash "$U"
  echo "   $U criado"
fi
H="$(eval echo "~$U")"

echo "== 2. venv + dependências =="
if [ ! -x "$H/venv/bin/python" ]; then
  python3 -m venv "$H/venv"
fi
"$H/venv/bin/pip" install -q --upgrade pip
# As tarefas exigem: pytest (t1_ratelimit), flask (t2_metrics). A t3_pipeline usa
# só biblioteca padrão. O requirements.txt de tasks/t1_ratelimit é ARMADILHA
# deliberada da suíte e não deve ser usado como fonte de verdade.
"$H/venv/bin/pip" install -q pytest flask

echo "== 3. congelando versões =="
"$H/venv/bin/pip" freeze > "$H/requirements.lock"
chmod 644 "$H/requirements.lock"
echo "   $H/requirements.lock ($(wc -l < "$H/requirements.lock") pacotes)"

echo "== 4. PATH e chave =="
# O export precisa ficar ACIMA do retorno antecipado do .bashrc para sessão
# não interativa: ssh sem tty não passa daquele ponto, e o `python` desapareceria.
touch "$H/.bashrc"
if ! grep -q 'venv/bin' "$H/.bashrc"; then
  printf 'export PATH="$HOME/venv/bin:$PATH"\n' | cat - "$H/.bashrc" > "$H/.bashrc.new"
  mv "$H/.bashrc.new" "$H/.bashrc"
fi
mkdir -p "$H/.ssh" "$H/lab"
# Idempotente de propósito: o script da suíte usa `>>` e duplica a chave a cada
# execução. Aqui a chave entra uma vez só.
touch "$H/.ssh/authorized_keys"
if ! grep -qF "$OPERATOR_KEY" "$H/.ssh/authorized_keys"; then
  printf '%s\n' "$OPERATOR_KEY" >> "$H/.ssh/authorized_keys"
  echo "   chave do operador instalada"
else
  echo "   chave do operador já presente"
fi
chmod 700 "$H/.ssh"; chmod 600 "$H/.ssh/authorized_keys"

echo "== 5. reset sem root =="
cat > "$H/reset-lab.sh" <<'RESET'
#!/usr/bin/env bash
# reset-lab.sh [tarefa] — restaura o laboratório ANTES de cada corrida.
# Roda como labuser, sem root: o labuser é dono de tudo o que isto apaga.
#
# Por que existe: scripts de reprodução que um modelo deixa em /tmp viram DICA
# para o modelo da corrida seguinte, e cache de contexto do servidor carrega
# estado entre corridas. Sem reset, as cinco corridas não são independentes e a
# "variância entre seeds" fica misturada com herança de estado.
set -euo pipefail
SUITE="${SPEC_WINS:-/home/brenoperucchi/t87-runtime/spec-wins}"
H="$HOME"
for t in ${1:-t1_ratelimit t2_metrics t3_pipeline}; do
  pkill -f "^$H/venv/bin/python.* app.py" 2>/dev/null || true
  rm -rf "$H/lab/$t"
  mkdir -p "$H/lab"
  cp -R "$SUITE/tasks/$t" "$H/lab/$t"
  echo "lab/$t: limpo"
done
find /tmp -maxdepth 1 -user "$(id -un)" -exec rm -rf {} + 2>/dev/null || true
echo "sobras em /tmp removidas"
if [ -n "${LLAMA_SERVER:-}" ]; then
  for s in 0 1 2 3; do
    curl -s -X POST "$LLAMA_SERVER/slots/$s?action=erase" >/dev/null 2>&1 || true
  done
  echo "contexto do modelo apagado ($LLAMA_SERVER)"
else
  echo "AVISO: LLAMA_SERVER não definido — cache de contexto NÃO foi apagado"
fi
RESET
chmod 755 "$H/reset-lab.sh"
echo "   $H/reset-lab.sh instalado"

chown -R "$U:$U" "$H"
chmod 700 /root 2>/dev/null || true

echo
echo "== 6. verificação =="
echo "home         : $H"
echo "python       : $H/venv/bin/python"
su - "$U" -c 'python -c "import pytest, flask, sys; print(\"python\", sys.version.split()[0], \"| pytest\", pytest.__version__, \"| flask\", flask.__version__)"'
echo "lock         : $(grep -cE '^[A-Za-z]' "$H/requirements.lock") pacotes congelados"
echo "sudo do $U   : $(su - "$U" -c 'sudo -n true 2>&1 | head -1' || echo 'sem sudo (esperado)')"
echo
echo "PRONTO. Reporte ao claude-bridge-exec a saída acima — as versões entram na"
echo "chave de série, e sem elas as corridas não são reproduzíveis."
