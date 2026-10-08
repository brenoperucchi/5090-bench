#!/usr/bin/env python3
"""Rodada única de benchmark do Strata na RTX 5090 (decisão do Breno, 04/10/2026).

Para cada config da rodada (a padrão do setup e cada customização), na mesma passada e com os mesmos prompts:
  1. sobe o servidor no host Windows (adaptador privado: SSH + PowerShell);
  2. velocidade + sondas pelo núcleo público strata-bench (ou pelo run_bench.py/probes.py legados até a tag core-v0);
  3. compreensão MFC e mesa Guardian (adaptador privado, dados que nunca saem desta máquina);
  4. grava manifest.json com a identidade de cada config (motor, config, config_origin) e para o servidor.
Não fala com agentes nem espera o servidor ficar ocioso: avisar consumidores e abrir/fechar a janela é do agente.
Se derrubou o servidor, sempre religa a produção no fim e confere com um teste de fumaça (2 tentativas).

Uso:
  python3 tools/rodada/rodada.py tools/rodada/planos/0139.json [--testes velocidade,mfc,guardian]
  Resultados em results/rodadas/<versao>/; o que já está completo não roda de novo.

plano.json:
  {"versao": "0.1.39",
   "configs": [{"origin": "setup-default", "label": "0139-swift-default", "cfg": "E:\\\\strata-0139\\\\bench\\\\strata-swift-default.json"},
               {"origin": "custom-1", "label": "0139-swift-prod", "cfg": "E:\\\\strata-0139\\\\bench\\\\strata-prod-ctx32768.json"}],
   "producao": "E:\\\\strata-0138\\\\strata-swift-iq3_xxs.json"}
"""
import argparse
import re
import base64
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PS = Path(__file__).resolve().parent / "ps"
HOST = "192.168.0.125"
BASE = "http://127.0.0.1:18199"                     # túnel local até o Strata do host
CORE = Path("/home/brenoperucchi/Devs/strata-bench")          # núcleo público (tag core-v0.x)
LEGACY = Path("/home/brenoperucchi/Devs/strata-space/bench")  # run_bench.py/probes.py (protocol legacy-433)
MFC = Path("/home/brenoperucchi/Devs/miqueias/MFC/data/v04/handoff_llm_bench")
KEYFILE = Path("/home/brenoperucchi/.config/strata/prod-lan.key")
ENV = {**__import__("os").environ, "MFC_TARGET": "strata",
       **({"STRATA_API_KEY": KEYFILE.read_text().strip()} if KEYFILE.exists() else {})}
TESTES = ("velocidade", "velocidade-historica", "mfc", "guardian")       # padrão de toda config
EXTRAS = ("guardian-raciocinio", "deterministico", "gprobe")                    # só nas configs que pedem
BANCOS = ROOT / "results/rodadas/_bancos"                             # subconjuntos e referências privadas
def ps(script, *args, timeout=600):
    """Roda um .ps1 do adaptador no host via -EncodedCommand (sem problemas de aspas)."""
    body = Path(script).read_text(encoding="utf-8")
    call = "& {\n" + body + "\n} " + " ".join("'" + a.replace("'", "''") + "'" for a in args)
    enc = base64.b64encode(call.encode("utf-16-le")).decode()
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", HOST, f"powershell -NoProfile -NonInteractive -EncodedCommand {enc}"],
                       capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    return "\n".join(l for l in r.stdout.splitlines() if not l.startswith(("#< CLIXML", "<Objs")))


def props():
    k = ENV.get("STRATA_API_KEY", "")                 # 0.1.40+: /props também exige a chave quando há api_key
    req = urllib.request.Request(BASE + "/props", headers={"Authorization": f"Bearer {k}"} if k else {})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def velocidade(c, out, sizes="probe,medium,long,xlong,gprobe"):
    """Núcleo público strata-bench (tag core-v0.x): velocidade (medium/long/xlong) + sondas na mesma linha.
    A config do servidor é copiada do host SEM a api_key; a chave vai por $STRATA_API_KEY (nunca gravada)."""
    if not (CORE / "strata_bench").exists():
        return {"erro": "núcleo strata-bench ausente"}
    ident = out / f"{c['label']}.identity.json"          # só chaves do schema público (strata_bench/schema.py IDENTITY)
    ident.write_text(json.dumps({
        "machine": {"os": "Windows 11", "cpu": "AMD Ryzen 9 5950X", "cpu_isa": "AVX2", "cores": 16,
                    "ram_gb": 96, "ram_type": "DDR4", "ram_speed_mts": 3200},
        "engine": {"version": c["props"].get("build_info", "").split()[-1], "binary_sha256": c["identidade"]["engine_sha256"]},
    }), encoding="utf-8")
    cfg_local = out / f"{c['label']}.config.json"
    subprocess.run(["scp", "-q", f"{HOST}:{c['cfg'].replace(chr(92), '/')}", str(cfg_local)], stdin=subprocess.DEVNULL)
    cfg = json.loads(cfg_local.read_text(encoding="utf-8-sig")); cfg.pop("api_key", None)
    cfg_local.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    r = subprocess.run([sys.executable, "-m", "strata_bench", "run", "--base", BASE, "--config", str(cfg_local),
                        "--origin", c["origin"], "--sizes", sizes,
                        "--label", c["label"], "--identity", str(ident), "--out", str(out / "nucleo")], cwd=CORE, env=ENV)
    return {"nucleo": "strata-bench", "exit": r.returncode}


def gprobe(c, out):
    """Só a sonda formato Guardian (core-v0.1.1+), para completar rodadas feitas antes dela. Grava
    nucleo/<label>-gprobe.result.json; o gerador junta na linha de velocidade da mesma config."""
    c2 = dict(c, label=c["label"] + "-gprobe")
    r = velocidade(c2, out, sizes="gprobe")
    return r


def velocidade_historica(c, out):
    """Adaptador privado: mesma série das versões antigas (os_runtime_ab.py, prompts de 27/2.671/5.952 tokens, os dois
    maiores são snapshots do Guardian), para a aba GPU comparar a versão nova com as anteriores no MESMO tamanho."""
    r = subprocess.run([sys.executable, "tools/os_runtime_ab.py", "--label", c["label"], "--base", BASE,
                        "--expect-path", c["props"]["model_path"], "--repeats", "5", "--out", str(out / "privado" / f"{c['label']}.historico.json")],
                       cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, env=ENV)
    if r.returncode:                                   # guarda o motivo (sem segredos: a chave não sai do ENV)
        (out / "privado" / f"{c['label']}.historico.erro.log").write_text(r.stderr[-4000:], encoding="utf-8")
    return {"exit": r.returncode}


def deterministico(c, out, versao, referencia):
    """Igualdade de respostas: sobe a variante determinística da config (--pcie-frac 0 --prompt-cache 0
    --adapt-swaps 0, MT_MIN=1), roda 2 passadas nos casos sensíveis do MFC (nd e conflito) e compara byte a byte
    com a referência (outra versão). Grava as saídas desta versão como nova referência. Roda por último na config."""
    import hashlib
    cfg_det = ps(PS / "det.ps1", c["cfg"]).strip().splitlines()[-1]
    ps(PS / "parar.ps1")
    if "pronto" not in ps(PS / "subir.ps1", cfg_det, cfg_det.replace(".json", ".rodada.log"), timeout=300):
        return {"erro": "variante determinística não subiu"}
    res = {"referencia": referencia, "casos": 0, "identicos": 0, "estaveis": 0}
    for banco in ("nd2", "conf"):
        saida = BANCOS / f"ref-det-{versao}-{banco}.jsonl"
        if saida.exists(): saida.rename(saida.with_suffix(".anterior.jsonl"))
        subprocess.run([sys.executable, "tools/mfc_bench_gateway_adapter.py", "--script", str(MFC / "v04_compreensao_autonomo.py"), "rodar", "--banco", str(BANCOS / f"banco-{banco}.jsonl"),
                        "--saida", str(saida), "--url", BASE + "/v1/chat/completions", "--modelo", c["props"].get("model_alias") or "strata",
                        "--props", BASE + "/props", "--caminho-pesos", c["props"]["model_path"], "--repeticoes", "2"], stdout=subprocess.DEVNULL, cwd=ROOT, env=ENV)
        def h(f):
            d = {}
            for x in map(json.loads, open(f)): d.setdefault(x["caso"], set()).add(hashlib.sha256(x["texto"].encode()).hexdigest())
            return d
        novo = h(saida); ref = h(BANCOS / f"ref-det-{referencia}-{banco}.jsonl") if referencia else {}
        res["casos"] += len(novo)
        res["estaveis"] += sum(len(v) == 1 for v in novo.values())
        res["identicos"] += sum(1 for k, v in novo.items() if ref.get(k) == v)
    (out / "privado" / f"det-{c['label']}.json").write_text(json.dumps(res), encoding="utf-8")
    return res


def mfc(c, out):
    """Adaptador privado: compreensão MFC (60 casos × 3, protocolo do MFC). Respostas ficam fora do git."""
    saida = out / "privado" / f"mfc-{c['label']}.jsonl"
    saida.parent.mkdir(parents=True, exist_ok=True)
    rodar = subprocess.run([sys.executable, "tools/mfc_bench_gateway_adapter.py", "--script", str(MFC / "v04_compreensao_autonomo.py"), "rodar", "--banco",
                            str(MFC / "compreensao_banco_dev.jsonl"), "--saida", str(saida), "--url", BASE + "/v1/chat/completions",
                            "--modelo", c["props"].get("model_alias") or "strata", "--props", BASE + "/props",
                            "--caminho-pesos", c["props"]["model_path"], "--repeticoes", "3"], stdout=subprocess.DEVNULL, cwd=ROOT, env=ENV)
    corr = subprocess.run([sys.executable, str(MFC / "v04_compreensao_autonomo.py"), "corrigir", "--banco",
                           str(MFC / "compreensao_banco_dev.jsonl"), "--saida", str(saida), "--repeticoes", "3"],
                          capture_output=True, text=True)
    (out / "privado" / f"mfc-{c['label']}.correcao.json").write_text(corr.stdout, encoding="utf-8")
    return {"exit": max(rodar.returncode, corr.returncode)}


def guardian(c, out, raciocinio=False):
    """Adaptador privado: mesa Guardian v3-compact (12 respostas) e nota A2. Com raciocinio=True a mesa pede
    enable_thinking=true; o teto de raciocínio vem da config (reasoning_budget_tokens) e max_tokens é 12000."""
    tag = f"rodada-{c['label']}"
    ps(PS / "mesa.ps1", tag, "true" if raciocinio else "false", c["cfg"], timeout=5400)
    runs = ROOT / "results/guardian-synthesis-20260921/runs"
    subprocess.run(["scp", "-q", f"{HOST}:E:/strata-bench/results/guardian-synthesis-20260921/runs/v3-compact~{tag}~*", str(runs)],
                   stdin=subprocess.DEVNULL)
    nota = subprocess.run([sys.executable, "tools/desk_test_by_model.py", tag], cwd=ROOT, capture_output=True, text=True,
                          env={**__import__("os").environ, "ARM": "v3-compact"})
    (out / "privado" / f"mesa-{c['label']}.txt").write_text(nota.stdout, encoding="utf-8")
    return {"tag": tag}


def preparar_servidor(c, existente):
    """(pronto, derrubou). existente=True: NÃO para nem sobe nada (o dono do runtime já subiu a config do plano);
    só confere que o processo no ar é o desta config (exe sha256 e caminho da config) antes de medir."""
    if existente:
        rt = json.loads(ps(PS / "runtime.ps1").strip().splitlines()[-1])
        ident = json.loads(ps(PS / "identidade.ps1", c["cfg"]).strip().splitlines()[-1])
        ok = (rt.get("config_path") or "").lower() == c["cfg"].lower() and rt.get("engine_sha256") == ident.get("engine_sha256")
        return ok, False
    ps(PS / "parar.ps1")
    return "pronto" in ps(PS / "subir.ps1", c["cfg"], c["cfg"].replace(".json", ".rodada.log"), timeout=300), True


def sem_teste_que_mexe_no_servidor(testes, existente):
    """--servidor-existente promete não parar/subir nada. 'deterministico' sobe uma variante própria (det.ps1) e para o servidor:
    nesse modo ele NÃO roda (regressão 08/10/2026: derrubou a candidata do llm-exec e deixou a variante det no ar)."""
    if not existente: return list(testes)
    return [t for t in testes if t != "deterministico"]


def feito(teste, c, out):
    """O resultado deste teste para esta config já existe e está completo? (então não roda de novo)"""
    L = c["label"]
    if teste == "velocidade":
        return ((out / f"{L}.json").exists() and (out / f"{L}-probes.json").exists()) or \
               (out / "nucleo" / f"{L}.result.json").exists()
    if teste == "mfc":
        f = out / "privado" / f"mfc-{L}.correcao.json"
        try: return json.loads(f.read_text(encoding="utf-8")).get("tentativas_faltando") == 0
        except (OSError, ValueError): return False
    if teste == "velocidade-historica":
        return (out / "privado" / f"{L}.historico.json").exists()
    if teste == "gprobe":
        r = out / "nucleo" / f"{L}-gprobe.result.json"
        principal = out / "nucleo" / f"{L}.result.json"
        try:
            if "gprobe150" in json.loads(principal.read_text(encoding="utf-8")).get("sizes", {}): return True
        except (OSError, ValueError):
            pass
        return r.exists()
    if teste == "deterministico":
        return (out / "privado" / f"det-{L}.json").exists()
    if teste in ("guardian", "guardian-raciocinio"):
        f = out / "privado" / f"mesa-{L}.txt"
        return f.exists() and re.search(rf"rodada-{re.escape(L)}\s+12\s", f.read_text(encoding="utf-8")) is not None
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plano")
    ap.add_argument("--testes", default=",".join(TESTES + EXTRAS))
    ap.add_argument("--verificar", action="store_true", help="só lista o que falta; nunca toca no servidor")
    ap.add_argument("--servidor-existente", action="store_true",
                    help="não para nem sobe nada: mede o servidor que o dono do runtime já subiu com a config do plano")
    a = ap.parse_args()
    plano = json.loads(Path(a.plano).read_text(encoding="utf-8"))
    testes = [t for t in a.testes.split(",") if t]
    out = (ROOT / "results/rodadas" / plano["versao"]).resolve()     # uma pasta por versão; retoma o que faltou
    out.mkdir(parents=True, exist_ok=True)
    (out / "privado").mkdir(exist_ok=True)               # plano curto (sem MFC/mesa) também grava aqui
    (out / "nucleo").mkdir(exist_ok=True)
    mpath = out / "manifest.json"
    manifest = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {"versao": plano["versao"], "configs": []}
    feitos = {x["label"]: x for x in manifest["configs"] if not x.get("erro")}
    # --testes filtra também os testes próprios de cada config (ex.: guardian-raciocinio só roda se pedido)
    falta = {c["label"]: [t for t in (c.get("testes") or TESTES) if t in testes and not feito(t, c, out)]
             for c in plano["configs"]}
    for k in falta: falta[k] = sem_teste_que_mexe_no_servidor(falta[k], a.servidor_existente)
    print("falta:", {k: v for k, v in falta.items() if v} or "nada", flush=True)
    if a.verificar: return
    if not any(falta.values()):
        subprocess.run([sys.executable, "tools/build_benchmarks_json.py"], cwd=ROOT)
        print("nada a rodar; servidor não foi tocado"); return
    testes_ok = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tools/rodada/testes", "-q"], cwd=ROOT)
    if testes_ok.returncode != 0:
        sys.exit("testes unitários/regressão falharam: rodada NÃO iniciada, servidor não foi tocado")
    derrubou = False
    try:
        for c in plano["configs"]:
            if not falta[c["label"]]: continue
            print(f"=== {c['label']} ({c['origin']}) {falta[c['label']]} {time.strftime('%H:%M:%S')}", flush=True)
            pronto, d = preparar_servidor(c, a.servidor_existente); derrubou = derrubou or d
            if not pronto:
                print("  servidor não está no ar com esta config (exe/config); NÃO medido; segue", flush=True); continue
            c["identidade"] = json.loads(ps(PS / "identidade.ps1", c["cfg"]).strip().splitlines()[-1])
            c["config"] = {"args": c["identidade"]["args"], "env": c["identidade"]["env"]}
            c["props"] = props()
            vista = c["props"].get("build_info", "").split()[-1]       # o motor diz "0.1.40" na release 0.1.40.1
            if vista != plano["versao"] and vista != ".".join(plano["versao"].split(".")[:3]):
                print(f"  versão no ar {c['props'].get('build_info')} != {plano['versao']}; segue", flush=True); continue
            res = (feitos.get(c["label"]) or {}).get("resultados", {})
            for t in sorted(falta[c["label"]], key=lambda t: t == "deterministico"):   # determinístico por último
                res[t] = {"velocidade": velocidade, "velocidade-historica": velocidade_historica, "mfc": mfc,
                          "guardian": guardian, "guardian-raciocinio": lambda c, o: guardian(c, o, raciocinio=True),
                          "deterministico": lambda c, o: deterministico(c, o, plano["versao"], plano.get("referencia_det")),
                          "gprobe": gprobe}[t](c, out)
            feitos[c["label"]] = {k: c[k] for k in ("label", "origin", "cfg", "identidade", "config")} | {"papel": c.get("papel", "unknown")} | \
                                 {"build": c["props"].get("build_info"), "resultados": res}
            manifest["configs"] = list(feitos.values())
            mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    finally:
        if derrubou:
            ps(PS / "parar.ps1")                           # nunca deixa servidor temporário de teste no ar
        if derrubou and plano.get("producao"):          # derrubou -> volta a produção do plano (se houver) e confere
            for tentativa in (1, 2):
                print("religando produção:", ps(PS / "subir.ps1", plano["producao"], plano["producao"].replace(".json", "-serve-rodada.log"), timeout=300), flush=True)
                fumaca = ps(PS / "fumaca.ps1").strip().splitlines()[-1]
                print("fumaça:", fumaca, flush=True)
                if fumaca.startswith("OK"): break
                ps(PS / "parar.ps1")
            manifest["producao_religada"] = fumaca
        manifest["atualizado"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    subprocess.run([sys.executable, "tools/build_benchmarks_json.py"], cwd=ROOT)   # publica no painel (validado)
    print("rodada concluída:", mpath)


if __name__ == "__main__":
    main()
