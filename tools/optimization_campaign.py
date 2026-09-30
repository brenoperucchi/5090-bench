#!/usr/bin/env python3
"""llama-server optimization campaign: isolated A/B, then 3 models × Windows × WSL.

Rules are read from results/otimizacao-20260922/REGRAS.json, frozen BEFORE this
script runs. Phase 1 measures each tweak in isolation and applies those rules
mechanically; phase 2 measures the three models on both operating systems with
the adopted set. Production is ALWAYS restored at the end, even on failure.

Windows is driven through WSL interop (the .exe runs natively on Windows).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/otimizacao-20260922"
HOST = "192.168.0.125"
WSL_BIN = "/home/brenoperucchi/llama.cpp/build/bin/llama-server"
WIN_EXE = "/mnt/e/llama-win-b11053/llama-server.exe"
BASE_FLAGS = "-ngl 99 --ctx-size 16384 --jinja --temp 0 --parallel 1"
PROD = ("/mnt/e/ollama/models/blobs/sha256-1194192cf2a187eb02722edcc3f77b11d21f537048ce04b67ccf8ba78863006a "
        "--alias qwen3-coder-30b --host 0.0.0.0 --port 18194 -ngl 99 --ctx-size 16384 --jinja --temp 0 --parallel 1")

MODELS = {
    "q4": {"wsl": "/mnt/e/ollama/models/blobs/sha256-f5f1dd8920d417aac2718b0bda3403da274301efdd6760b4f0f4b864ff2ad57d",
           "win": r"E:\ollama\models\blobs\sha256-f5f1dd8920d417aac2718b0bda3403da274301efdd6760b4f0f4b864ff2ad57d",
           "frag": "f5f1dd8920d417aa", "mtp": False},
    "nvfp4": {"wsl": "/mnt/e/llm-bench-t87-runtimes/models/qwen38-nvfp4/Qwen3.8-27B-iMatrix-NVFP4-MTP.gguf",
              "win": r"E:\llm-bench-t87-runtimes\models\qwen38-nvfp4\Qwen3.8-27B-iMatrix-NVFP4-MTP.gguf",
              "frag": "NVFP4-MTP.gguf", "mtp": True},
    "hemmingway": {"wsl": "/mnt/e/llm-bench-t87-runtimes/models/hemmingway/Altworld_Hemmingway-1-Q4_K_M.gguf",
                   "win": r"E:\llm-bench-t87-runtimes\models\hemmingway\Altworld_Hemmingway-1-Q4_K_M.gguf",
                   "frag": "Hemmingway-1-Q4_K_M.gguf", "mtp": False},
}


def ssh(cmd: str, timeout: int = 300) -> str:
    p = subprocess.run(["ssh", "-o", "BatchMode=yes", HOST, cmd], capture_output=True, text=True, timeout=timeout)
    return (p.stdout + p.stderr).strip()


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def wait_health(url: str, limit: int = 300) -> bool:
    t0 = time.time()
    while time.time() - t0 < limit:
        try:
            with urllib.request.urlopen(url + "/health", timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:  # noqa: BLE001 — still loading
            pass
        time.sleep(4)
    return False


def stop_all() -> None:
    ssh("for p in $(ss -tlnp | grep -E ':1819[4-6] ' | grep -oP 'pid=\\K[0-9]+'); do kill $p; done; "
        "/mnt/c/Windows/System32/taskkill.exe /IM llama-server.exe /F >/dev/null 2>&1; sleep 5; true")


def start(os_: str, model: str, extra: str) -> str:
    m = MODELS[model]
    if os_ == "wsl":
        ssh(f"setsid nohup {WSL_BIN} --model {m['wsl']} --alias {model}-wsl --host 127.0.0.1 --port 18196 "
            f"{BASE_FLAGS} {extra} < /dev/null > /tmp/opt-{model}-wsl.log 2>&1 &")
        ok = wait_health("http://127.0.0.1:18196")
        return "http://127.0.0.1:18196" if ok else ""
    # interop keeps the ssh channel open while the .exe lives: fire and don't wait
    subprocess.Popen(["ssh", "-o", "BatchMode=yes", "-n", HOST, f"cd /mnt/e/llama-win-b11053 && setsid nohup {WIN_EXE} --model '{m['win']}' --alias {model}-win "
        f"--host 0.0.0.0 --port 18197 {BASE_FLAGS} {extra} < /dev/null > /tmp/opt-{model}-win.log 2>&1 &"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok = wait_health(f"http://{HOST}:18197")
    return f"http://{HOST}:18197" if ok else ""


def bench(label: str, base: str, model: str) -> dict | None:
    out = OUT / f"{label}.json"
    if not out.exists():
        subprocess.run([sys.executable, str(ROOT / "tools/os_runtime_ab.py"), "--label", label, "--base", base,
                        "--expect-path", MODELS[model]["frag"], "--out", str(out)],
                       capture_output=True, text=True, timeout=1200)
    return json.loads(out.read_text()) if out.exists() else None


def summary(d: dict) -> dict:
    ag = d["derivados"]
    tg = (ag["medio"]["tg_tps_mediana"] + ag["longo"]["tg_tps_mediana"]) / 2
    drafted = sum((c["timings"] or {}).get("draft_n", 0) or 0 for c in d["chamadas"])
    accepted = sum((c["timings"] or {}).get("draft_n_accepted", 0) or 0 for c in d["chamadas"])
    return {"tg": round(tg, 2), "pp_longo": round(ag["longo"]["pp_tps_mediana"], 1),
            "aceitacao_mtp": round(accepted / drafted, 3) if drafted else None,
            "textos": {f"{c['tamanho']}-{c['repeticao']}": c["content_sha256"][:12] for c in d["chamadas"]}}


def run(label: str, os_: str, model: str, extra: str) -> dict | None:
    if (OUT / f"{label}.json").exists():  # resume: already measured
        s = summary(json.loads((OUT / f"{label}.json").read_text())) | {"extra": extra, "retomado": True}
        log(f"{label}: já medido — geração {s['tg']} · prefill longo {s['pp_longo']}")
        return s
    stop_all()
    log(f"{label}: subindo {model} em {os_} [{extra or 'base'}]")
    base = start(os_, model, extra)
    if not base:
        log(f"{label}: NÃO SUBIU — {ssh(f'tail -3 /tmp/opt-{model}-{os_}.log')[-300:]}")
        return None
    fa = ssh(f"grep -iE 'flash.?attn|fattn' /tmp/opt-{model}-{os_}.log | tail -2")
    d = bench(label, base, model)
    if not d:
        log(f"{label}: bench falhou")
        return None
    s = summary(d) | {"extra": extra, "log_fa": fa[-200:]}
    log(f"{label}: geração {s['tg']} tok/s · prefill longo {s['pp_longo']} · aceitação MTP {s['aceitacao_mtp']}")
    return s


def same_text(a: dict, b: dict) -> bool:
    return a["textos"] == b["textos"]


def main() -> int:
    rules = json.loads((OUT / "REGRAS.json").read_text())
    res: dict[str, dict | None] = {}
    decision: dict[str, object] = {"regras_sha": __import__("hashlib").sha256(
        (OUT / "REGRAS.json").read_bytes()).hexdigest()}
    try:
        # ---------------- fase 1: isolados (WSL) — base de comparação medida de novo, mesma sessão
        res["f1-q4-base"] = run("f1-q4-base", "wsl", "q4", "")
        res["f1-q4-fa"] = run("f1-q4-fa", "wsl", "q4", "-fa on")
        res["f1-q4-ub"] = run("f1-q4-ub", "wsl", "q4", "-ub 1024 -b 4096")
        res["f1-q4-kvq8"] = run("f1-q4-kvq8", "wsl", "q4", "-ctk q8_0 -ctv q8_0")
        res["f1-nvfp4-base"] = run("f1-nvfp4-base", "wsl", "nvfp4", "")
        res["f1-nvfp4-mtp2"] = run("f1-nvfp4-mtp2", "wsl", "nvfp4", "--spec-type draft-mtp --spec-draft-n-max 2")
        res["f1-nvfp4-mtp3"] = run("f1-nvfp4-mtp3", "wsl", "nvfp4", "--spec-type draft-mtp --spec-draft-n-max 3")

        b = res["f1-q4-base"]
        adopted = []
        if b and (fa := res["f1-q4-fa"]):
            ok = fa["tg"] >= b["tg"] * 0.98 and fa["pp_longo"] >= b["pp_longo"] * 0.98 and same_text(fa, b)
            decision["-fa on"] = {"adotado": ok, "tg": [b["tg"], fa["tg"]], "pp": [b["pp_longo"], fa["pp_longo"]],
                                  "texto_identico": same_text(fa, b)}
            if ok:
                adopted.append("-fa on")
        if b and (ub := res["f1-q4-ub"]):
            ok = ub["pp_longo"] >= b["pp_longo"] * 1.03 and ub["tg"] >= b["tg"] * 0.98
            decision["-ub 1024 -b 4096"] = {"adotado": ok, "tg": [b["tg"], ub["tg"]], "pp": [b["pp_longo"], ub["pp_longo"]]}
            if ok:
                adopted.append("-ub 1024 -b 4096")
        if b and (kv := res["f1-q4-kvq8"]):
            decision["KV q8_0"] = {"adotado": False, "motivo": "regra congelada: medido, nunca adotado",
                                   "tg": [b["tg"], kv["tg"]], "pp": [b["pp_longo"], kv["pp_longo"]],
                                   "texto_identico": same_text(kv, b)}
        mtp = ""
        nb = res["f1-nvfp4-base"]
        cands = [(k, v) for k, v in (("2", res["f1-nvfp4-mtp2"]), ("3", res["f1-nvfp4-mtp3"])) if v]
        if nb and cands:
            k, v = max(cands, key=lambda kv: kv[1]["tg"])
            ok = v["tg"] >= nb["tg"] * 1.05
            decision["MTP"] = {"adotado": ok, "n_max": k, "tg_base": nb["tg"],
                               "tg": {kk: vv["tg"] for kk, vv in cands},
                               "aceitacao": {kk: vv["aceitacao_mtp"] for kk, vv in cands},
                               "texto_identico_ao_sem_mtp": {kk: same_text(vv, nb) for kk, vv in cands}}
            if ok:
                mtp = f"--spec-type draft-mtp --spec-draft-n-max {k}"
        common = " ".join(adopted)
        decision["conjunto_adotado"] = {"todos": common or "(nenhum)", "so_nvfp4": mtp or "(nenhum)"}
        log(f"ADOTADO: comum=[{common}] nvfp4=[{mtp}]")

        # ---------------- fase 2: 3 modelos × 2 SOs com o conjunto adotado
        for model in ("q4", "nvfp4", "hemmingway"):
            extra = (common + (" " + mtp if MODELS[model]["mtp"] and mtp else "")).strip()
            for os_ in ("wsl", "win"):
                res[f"f2-{model}-{os_}"] = run(f"f2-{model}-{os_}", os_, model, extra)
    finally:
        stop_all()
        ssh(f"setsid nohup {WSL_BIN} --model {PROD} < /dev/null > /tmp/llama-18194.log 2>&1 &")
        back = wait_health(f"http://{HOST}:18194") or wait_health("http://127.0.0.1:18194")
        log(f"PRODUÇÃO {'DE VOLTA' if back else 'NÃO VOLTOU — VERIFICAR'}")
        (OUT / "RESULTADO.json").write_text(json.dumps({"decisao": decision, "resultados": res},
                                                       ensure_ascii=False, indent=2) + "\n")
        log("CAMPANHA CONCLUÍDA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
