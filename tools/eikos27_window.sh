#!/bin/bash
# Eikos-27B-INT4 test window, v2 (24/09 11:22). Fixes from the aborted v1:
# - stop a server by the pid on its port, killing its whole process GROUP (vLLM's
#   EngineCore has no port), and wait until VRAM is actually free (kill -9 after 20 s);
# - vLLM with --enforce-eager (v1 hung capturing CUDA graphs: 0/51 for 7.5 min);
# - no pgrep/pkill -f anywhere (it matched its own command line in v1).
# Production is ALWAYS restored (trap), with the exact line and n_ctx 32768.
H=192.168.0.125
M=/mnt/e/llm-bench-t87-runtimes/models/eikos-27b-int4
cd /home/brenoperucchi/Devs/llm-bench
log(){ echo "[$(date +%H:%M:%S)] $*"; }
# remote helper: stop_port <port> <max_used_mib> — kill the process group on the port, wait for VRAM
cat > /tmp/claude-1000/stop_port.sh <<'SH'
#!/bin/bash
port=$1; limit=$2
pid=$(ss -tlnp | grep ":$port " | grep -oP "pid=\K[0-9]+" | head -1)
if [ -n "$pid" ]; then
  pg=$(ps -o pgid= -p "$pid" | tr -d " ")
  kill -TERM -- "-$pg" 2>/dev/null || kill "$pid"
  for i in $(seq 1 20); do ps -p "$pid" >/dev/null || break; sleep 1; done
  ps -p "$pid" >/dev/null && { kill -9 -- "-$pg" 2>/dev/null || kill -9 "$pid"; sleep 3; }
fi
for i in $(seq 1 30); do
  used=$(/usr/lib/wsl/lib/nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr -d " ")
  [ "$used" -le "$limit" ] && { echo "porta $port livre; VRAM em uso ${used} MiB"; exit 0; }
  sleep 1
done
echo "porta $port: VRAM NÃO liberou (${used} MiB)"; exit 1
SH
scp -q /tmp/claude-1000/stop_port.sh $H:/tmp/stop_port.sh && ssh -n $H chmod +x /tmp/stop_port.sh
restore(){
  log "limpando: túnel, servidor Eikos, vLLM"
  for p in $(ss -tlnp 2>/dev/null | grep "127.0.0.1:18198 " | grep -oP "pid=\K[0-9]+"); do kill $p; done
  ssh -n $H '/tmp/stop_port.sh 18198 32000; /tmp/stop_port.sh 8001 2000'
  ssh -n $H 'ss -tlnp | grep -q ":18194 " && echo "18194 já no ar" || { setsid nohup /home/brenoperucchi/llama.cpp/build/bin/llama-server --model /mnt/e/ollama/models/blobs/sha256-1194192cf2a187eb02722edcc3f77b11d21f537048ce04b67ccf8ba78863006a --alias qwen3-coder-30b --host 0.0.0.0 --port 18194 -ngl 99 --ctx-size 32768 --jinja --temp 0 --parallel 1 < /dev/null > /tmp/llama-18194.log 2>&1 & echo relancada; }'
  timeout 300 bash -c 'until curl -sf localhost:18194/health >/dev/null; do sleep 3; done' && \
    log "PRODUÇÃO DE VOLTA $(curl -s localhost:18194/props | python3 -c 'import json,sys;p=json.load(sys.stdin);print(p["total_slots"],p["default_generation_settings"]["n_ctx"],p["model_path"][-12:])')" || log "PRODUÇÃO NÃO VOLTOU — VERIFICAR"
  log "JANELA_FIM"
}
trap restore EXIT
log "JANELA_INICIO — derrubando 18194"
ssh -n $H '/tmp/stop_port.sh 18194 2000' || { log "VRAM não liberou — abortando"; exit 1; }
log "subindo vLLM (enforce-eager)"
ssh -n $H "source /home/brenoperucchi/eikos-vllm-venv/bin/activate && setsid nohup vllm serve $M --host 127.0.0.1 --port 8001 --served-model-name decider --dtype bfloat16 --gpu-memory-utilization 0.85 --max-model-len 16384 --enable-prefix-caching --mamba-cache-mode all --logprobs-mode processed_logprobs --max-logprobs 32 --enforce-eager < /dev/null > /tmp/eikos27-vllm.log 2>&1 & echo ok"
if ! ssh -n $H 'timeout 900 bash -c "until curl -sf localhost:8001/health >/dev/null; do sleep 5; grep -qE \"Traceback|ERROR\" /tmp/eikos27-vllm.log && exit 1; done"'; then
  log "vLLM NÃO SUBIU:"; ssh -n $H 'grep -E "Error|ERROR" /tmp/eikos27-vllm.log | tail -6 | cut -c1-200'; exit 1
fi
log "vLLM pronto; subindo servidor Eikos"
ssh -n $H "cd /mnt/e/llm-bench-t87-runtimes/eikos-src && source /home/brenoperucchi/eikos-vllm-venv/bin/activate && setsid nohup python eikos/serve.py --model $M --calib $M/calib.json --vllm-url http://127.0.0.1:8001 --host 127.0.0.1 --port 18198 < /dev/null > /tmp/eikos27-serve.log 2>&1 & echo ok"
ssh -n $H 'timeout 300 bash -c "until grep -q \"ready at\" /tmp/eikos27-serve.log; do sleep 3; grep -q Traceback /tmp/eikos27-serve.log && exit 1; done"' || { log "SERVIDOR EIKOS NÃO SUBIU"; ssh -n $H 'tail -6 /tmp/eikos27-serve.log'; exit 1; }
ssh -f -N -o ExitOnForwardFailure=yes -L 18198:127.0.0.1:18198 $H && log "túnel ok"
log "teste: $(curl -s -m 120 -X POST http://127.0.0.1:18198/v1/systemone -H 'Content-Type: application/json' -d '{"state":"O pedido foi aprovado ontem pelo gerente.","questions":{"q":{"type":"noul","instructions":"O pedido foi aprovado?","criteria":{"true":"sim","false":"não"}}}}' | head -c 300)"
log "tipificação 22/09"
SYSTEMONE_URL=http://127.0.0.1:18198/v1/systemone python3 tools/typification_eval.py --arm trivial --arm jev --out results/tipificacao-eikos27b-int4-20260924.json 2>&1 | sed -n '/=== jev/,$p'
log "experimento 1"
JEV_HYB_OUT=results/jev-hibrido-a2-20260924/eikos-27b-int4 SYSTEMONE_URL=http://127.0.0.1:18198/v1/systemone python3 tools/jev_hybrid_a2.py 2>&1 | tail -2
log "baterias concluídas"
