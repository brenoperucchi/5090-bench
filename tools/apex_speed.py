#!/usr/bin/env python3
"""APEX 35B-A3B speed: without/with the separate MTP draft head, WSL and Windows.

Reuses the optimization campaign plumbing and its adopted flags; production is
always restored at the end.
"""
import json
import optimization_campaign as oc

D = "/mnt/e/llm-bench-t87-runtimes/models/qwen38-35b-apex"
W = r"E:\llm-bench-t87-runtimes\models\qwen38-35b-apex"
oc.MODELS["apex"] = {"wsl": f"{D}/Qwen3.8-35B-A3B-Distill.APEX-I-MiniPlus-V2.1.gguf",
                     "win": W + r"\Qwen3.8-35B-A3B-Distill.APEX-I-MiniPlus-V2.1.gguf",
                     "frag": "APEX-I-MiniPlus-V2.1.gguf", "mtp": True}
COMMON = "-ub 1024 -b 4096"
MTP = {"wsl": f"-md {D}/mtp-Qwen3.8-35B-A3B-Distill-Q8_0.gguf --spec-type draft-mtp --spec-draft-n-max 2",
       "win": f"-md '{W}\\mtp-Qwen3.8-35B-A3B-Distill-Q8_0.gguf' --spec-type draft-mtp --spec-draft-n-max 2"}

res = {}
try:
    for os_ in ("wsl", "win"):
        res[f"apex-{os_}"] = oc.run(f"apex-{os_}", os_, "apex", COMMON)
        res[f"apex-{os_}-mtp"] = oc.run(f"apex-{os_}-mtp", os_, "apex", f"{COMMON} {MTP[os_]}")
finally:
    oc.stop_all()
    oc.ssh(f"setsid nohup {oc.WSL_BIN} --model {oc.PROD} < /dev/null > /tmp/llama-18194.log 2>&1 &")
    back = oc.wait_health("http://127.0.0.1:18194")
    oc.log(f"PRODUÇÃO {'DE VOLTA' if back else 'NÃO VOLTOU — VERIFICAR'}")
    (oc.OUT / "APEX-RESULTADO.json").write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n")
