#!/usr/bin/env python3
"""Build results/painel/benchmarks.json: every benchmark comparison measured on this bench, for the gateway's
/benchmarks page. Reads only local result files; the output stays out of git (private MFC/Guardian numbers)."""
import glob, hashlib, json, re, statistics, subprocess, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1          # contract: llm-gateway docs/CONTRATO-benchmarks-v1.md


def src(path):
    """Relative source label + sha256 of the artifact (no absolute paths in the output)."""
    path = Path(path)
    rel = (f"llm-bench/{path.relative_to(ROOT)}" if path.is_relative_to(ROOT)
           else f"strata-space/{path.relative_to(SPACE.parents[1])}" if path.is_relative_to(SPACE.parents[1]) else path.name)
    return {"fonte": rel, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
OUT = ROOT / "results/painel/benchmarks.json"
STRATA = ROOT / "results/strata-20260930"
SPACE = Path("/home/brenoperucchi/Devs/strata-space/bench/results")
MFC = ROOT / "results/mfc-compreensao-20261001"

GPU = {"id": "rtx5090", "nome": "RTX 5090 32 GB", "host": "Ryzen 9 5950X (AVX2), Windows 11",
       "ram": "96 GB DDR4-3200 desde 01/10/2026 (antes 64 GB a 2400)"}

# label of a speed JSON -> (engine, version, model, variant, ram)
def describe(label):
    l = label.lower()
    m = re.search(r"strata-?0?1?(\d{2,3})", l)
    ver = None
    if "strata-iq2xs" in l and "01" not in l: ver = "0.1.27"
    m = re.search(r"strata-?(0\d{3})", l) or re.search(r"strata(0\d{3})", l)
    if m: d = m.group(1); ver = f"0.1.{int(d[2:])}"
    model = ("Swift 1.5 IQ3_XXS" if "swift-iq3xxs" in l else "Swift 1.5 IQ2_XS" if "swift-iq2xs" in l else
             "Flash-Next IQ3_XXS" if "iq3xxs" in l else "Flash-Next IQ3_S" if "iq3s" in l else
             "Coder IQ1_M" if "coder" in l else "Flash-Next IQ2_XS" if "iq2xs" in l else label)
    variant = []
    for k, v in (("auto32kstager", "auto:32768 + stager"), ("auto32k", "auto:32768"), ("stager", "stager antigo"),
                 ("fused", "PF_FUSED"), ("recal", "recalibrado"), ("posbios", "pós-BIOS"), ("cal", "calibrado")):
        if k in l and not any(k in x for x in []): variant.append(v); l = l.replace(k, "")
    ram = "96 GB" if "96gb" in label.lower() or (ver and ver >= "0.1.32") else "64 GB"
    return ver, model, ", ".join(variant) or "padrão", ram

def speed():
    out = []
    for f in sorted(STRATA.glob("*.json")):
        try: d = json.load(open(f))
        except Exception: continue
        if "chamadas" not in d: continue
        row = {**src(f), "label": d.get("label"), "build": (d.get("props") or {}).get("build_info")}
        row["versao"], row["modelo"], row["variante"], row["ram"] = describe(d.get("label", f.stem))
        if row["build"] and row["build"].startswith("Strata "): row["versao"] = row["build"].split()[1]
        for t in ("curto", "medio", "longo"):
            c = [x["timings"] for x in d["chamadas"] if x.get("tamanho") == t and x.get("repeticao", 2) > 1] or \
                [x["timings"] for x in d["chamadas"] if x.get("tamanho") == t]
            if c:
                row[f"geracao_{t}"] = round(statistics.median(x["predicted_per_second"] for x in c), 1)
                row[f"leitura_{t}"] = round(statistics.median(x["prompt_per_second"] for x in c))
        if any(r["label"] == row["label"] for r in out): continue   # same run copied twice
        if row["versao"] and row["versao"] >= "0.1.34" and row["modelo"] == "Swift 1.5 IQ3_XXS" and row["variante"] == "padrão" and row["versao"] != "0.1.34":
            row["variante"] = "config de produção (auto:32768)"
        out.append(row)
    return out

def longos():
    out = []
    for f in sorted(STRATA.glob("*longos*.json")):
        d = json.load(open(f)); row = {**src(f), "label": d.get("label"), "build": d.get("build_info")}
        for size, s in d.get("sizes", {}).items():
            if s.get("prompt_tps"): row[f"leitura_{size}"] = round(s["prompt_tps"]["median"])
            if s.get("decode_tps"): row[f"geracao_{size}"] = round(s["decode_tps"]["median"], 1)
        out.append(row)
    return out

def rodadas():
    """label -> {versao, modelo} das rodadas únicas, tirados do manifest (build observado no /props e config real)."""
    out = {}
    for m in sorted((ROOT / "results/rodadas").glob("*/manifest.json")):
        for c in json.load(open(m)).get("configs", []):
            if c.get("erro") or not c.get("build"): continue
            args = " ".join((c.get("config") or {}).get("args") or []).lower()
            modelo = ("Swift 1.5 IQ3_XXS" if "swift" in args and "iq3_xxs" in args else
                      "Flash-Next IQ3_S" if "iq3_s" in args else None)
            out[c["label"]] = {"versao": c["build"].split()[-1], "modelo": modelo, "papel": c.get("papel")}
    return out


def versao_de(build):
    """Versão a partir do build_info observado ('Strata 0.1.39'); nunca do nome do arquivo."""
    return build.split()[-1] if isinstance(build, str) and build.startswith("Strata ") else None


def producao_atual():
    """Produção lida do próprio Strata (/v1/status: versão e subida); se ele estiver fora do ar, a última conhecida."""
    cache = ROOT / "results/painel/producao.json"
    try:
        import urllib.request, datetime
        with urllib.request.urlopen("http://127.0.0.1:18199/v1/status", timeout=3) as r:
            st = json.load(r)
        modelo = "Swift 1.5 IQ3_XXS" if "swift" in str(st.get("model")) and "iq3_xxs" in str(st.get("model")) else st.get("model")
        p = {"gpu": "rtx5090", "motor": f"Strata {st['engine']}", "modelo": modelo,
             "desde": datetime.datetime.fromtimestamp(st["started"]).astimezone().isoformat(timespec="minutes")}
        cache.write_text(json.dumps(p), encoding="utf-8")
        return p
    except Exception:
        return json.loads(cache.read_text(encoding="utf-8"))


def strata_space():
    """Benchmarks of the strata space (public prompts of the Strata community benchmark: short/medium/long/xlong)."""
    out = []
    for f in sorted(list(SPACE.glob("*.json")) + list(SPACE.glob("r01*/*.json")) + list((ROOT / "results/rodadas").glob("*/*.json")) + list((ROOT / "results/rodadas").glob("*/nucleo/*.result.json"))):
        try: d = json.load(open(f))
        except Exception: continue
        if "sizes" not in d and "summary" in d and "prompt_ms_median" in d["summary"]:   # probes.py format
            sm = d["summary"]; base = f.with_name(f.name.replace("-probes", ""))
            if not base.exists(): continue          # no sibling run: model/context unknown, skip instead of guessing
            bd = json.load(open(base)); bmp = (bd.get("model_path") or "").lower()
            if not bd.get("n_ctx") or "swift" not in bmp: continue
            out.append({**src(f), "label": sm.get("label"), "build": bd.get("build_info"), "modelo": "Swift 1.5 IQ3_XXS"
                        if "iq3_xxs" in bmp else bd.get("model_path"), "n_ctx": bd.get("n_ctx"), "sonda": True,
                        "leitura_ms_probe": round(sm["prompt_ms_median"])})
            continue
        if "sizes" not in d: continue
        mp = (d.get("model_path") or "").lower()
        modelo = ("Unsloth UD-Q4_K_XL" if "ud-q4" in mp or "unsloth" in mp else "Swift 1.5 IQ3_XXS" if "swift" in mp and "iq3_xxs" in mp
                  else "Flash-Next IQ3_S" if "iq3_s" in mp else "Flash-Next IQ2_XS" if "iq2_xs" in mp else d.get("model_path"))
        row = {**src(f), "label": d.get("label"), "build": d.get("build_info"), "modelo": modelo,
               "n_ctx": d.get("n_ctx"), "sonda": ("probe" in d["sizes"]) if d.get("schema") == "strata-bench/v1" else ("probe" in f.name)}
        for size, v in d["sizes"].items():
            if v.get("prompt_tps"): row[f"leitura_{size}"] = round(v["prompt_tps"]["median"])
            if v.get("decode_tps"): row[f"geracao_{size}"] = round(v["decode_tps"]["median"], 1)
            if v.get("prompt_ms"): row[f"leitura_ms_{size}"] = round(v["prompt_ms"]["median"])
        out.append(row)
    return out

RUN_LOGS = {"openrouter-qwen38-max-0902-reasoning-minimal-rep1": "rodar_openrouter_max.log"}

def mfc():
    out = []
    for f in sorted(list(MFC.glob("correcao_*.json")) + list((ROOT / "results/rodadas").glob("*/privado/mfc-*.correcao.json"))):
        try: d = json.JSONDecoder().raw_decode(open(f).read())[0]
        except Exception: continue
        name = f.stem.replace("correcao_", "").replace(".correcao", "")
        resp = (f.parent / f"{name}.jsonl") if f.name.endswith(".correcao.json") else MFC / f"resp_{name.replace('-rep1','')}.jsonl"
        lat = None
        if resp.exists():
            ls = [json.loads(l).get("latencia_s") for l in open(resp)]
            ls = [x for x in ls if x is not None]
            if ls: lat = statistics.median(ls)
        elif (MFC / RUN_LOGS.get(name, "-")).exists():   # responses gone: latency from the run log (last column)
            ls = [float(l.split()[-1]) for l in open(MFC / RUN_LOGS[name]) if l.split() and re.match(r"^[\d.]+$", l.split()[-1])]
            if ls: lat = statistics.median(ls)
        row = {"config": name, "repeticoes": d.get("repeticoes"), "invalidas": d.get("invalidas"),
               "taxas": {k: round(v["taxa"] * 100, 1) for k, v in d["por_categoria"].items()},
               "criticos_100": d.get("criticos_100pct"), "demais_95": d.get("demais_95pct"), **src(f)}
        if lat is not None: row["latencia_mediana_s"] = lat     # omitted = not measured (contract v1)
        out.append(row)
    return out

def mesa():
    p = subprocess.run(["python3", "tools/desk_test_by_model.py"], cwd=ROOT, env={**os.environ, "ARM": "v3-compact"},
                       capture_output=True, text=True).stdout
    out = []
    for l in p.splitlines():
        m = re.match(r"(\S+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)", l)
        if m: out.append({"modelo_tag": m.group(1), "n": int(m.group(2)), "a2_media": float(m.group(4)), "a2_mediana": float(m.group(5))})
    return out

HIST = [
    {"data": "2026-09-09", "motor": "Ollama (Windows)", "modelo": "qwen3:14b", "geracao": 135, "nota": "produção anterior (DECISAO-producao-2026-09-09.md)"},
    {"data": "2026-09-09", "motor": "Ollama (Windows)", "modelo": "qwen3.5:9b", "geracao": 183, "nota": "segundo residente"},
    {"data": "2026-09-09", "motor": "Ollama (Windows)", "modelo": "qwen3.8:27b", "geracao": 126, "nota": "finalista não escolhido"},
    {"data": "2026-09-19", "motor": "llama.cpp (fork Codacus, WSL)", "modelo": "Qwen3.8-Flash-Next 177B UD-IQ3_XXS (~82 GB, especialistas na CPU)", "geracao": 26.7, "nota": "aquecido; 15,5 no aquecimento (flash-next-context-probe-2026-09-19.md)"},
    {"data": "2026-09-30", "motor": "llama.cpp (WSL)", "modelo": "qwen3-coder-30b", "geracao": 239, "nota": "produção anterior ao Strata; síntese do Guardian"},
    {"data": "2026-09-30", "motor": "Strata 0.1.27", "modelo": "Flash-Next IQ2_XS", "geracao": 171.3, "nota": "primeira medição Strata"},
]

data = {"schema_version": SCHEMA_VERSION, "classificacao": "private_aggregate", "gerado_em": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
        "gpus": [GPU], "producao": producao_atual(),
        "abas": ["GPU / Benchmarks", "Benchmark Guardian", "Benchmark Strata"], "historico": HIST, "velocidade": speed(), "prompts_longos": longos(), "compreensao_mfc": mfc(),
        "mesa_guardian": mesa(), "strata_space": strata_space(),
        "notas": ["Velocidade: tok/s do próprio servidor, mediana de 5 repetições (os_runtime_ab.py); prompts curto 27, médio 2.671, longo 5.952 tokens.",
                  "Compreensão MFC e mesa Guardian são privadas: uso local, nunca publicar.",
                  "A2: menor é melhor; indicador com ρ≈0,7 com avaliação humana; ruído grande com 12 respostas (4,58–7,75 no mesmo modelo)."]}
_r = rodadas()
# Série histórica da rodada (os_runtime_ab, MESMOS tamanhos 27/2.671/5.952 da série antiga) entra em "velocidade".
for m in sorted((ROOT / "results/rodadas").glob("*/manifest.json")):
    for c in json.load(open(m)).get("configs", []):
        f = m.parent / "privado" / f"{c.get('label')}.historico.json"
        if not f.exists(): continue
        d = json.load(open(f)); info = _r.get(c["label"], {})
        row = {**src(f), "label": c["label"] + " · rodada llm-bench", "build": (d.get("props") or {}).get("build_info"),
               "versao": info.get("versao"), "modelo": info.get("modelo") or "?", "ram": "96 GB",
               "variante": "config padrão do setup" if c.get("origin") == "setup-default" else f"config de produção ({c.get('origin')})"}
        ok = True
        for t in ("curto", "medio", "longo"):
            cs = [x["timings"] for x in d.get("chamadas", []) if x.get("tamanho") == t and x.get("repeticao", 2) > 1]
            if not cs: ok = False; break
            row[f"geracao_{t}"] = round(statistics.median(x["predicted_per_second"] for x in cs), 1)
            row[f"leitura_{t}"] = round(statistics.median(x["prompt_per_second"] for x in cs))
        if ok and row["versao"]: data["velocidade"].append(row)

# A rodada única NÃO entra em "velocidade": essa série usa prompts de 27/2.671/5.952 tokens (instrumento antigo) e
# os tamanhos públicos (2,7K/14,7K/28,9K) não se encaixam nas mesmas colunas — a página calcularia Δ entre
# tamanhos diferentes (erro de 04/10, +1.361% falso). A velocidade da rodada fica em strata_space.

# Sonda na MESMA linha da velocidade (como o núcleo strata-bench/v1): junta "<label>-probes" na linha "<label>" da
# mesma pasta e some com a linha só de sonda. O rótulo diz de onde veio a medição (rodada do llm-bench ou strata-exec).
_ss = data["strata_space"]
_por_chave = {(Path(r["fonte"]).parent, r["label"]): r for r in _ss}
for r in list(_ss):
    if r.get("sonda") and r["label"].endswith("-probes"):
        irma = _por_chave.get((Path(r["fonte"]).parent, r["label"][: -len("-probes")]))
        if irma is not None and "leitura_ms_probe" in r:
            irma["leitura_ms_probe"] = r["leitura_ms_probe"]; irma["sonda"] = True
            _ss.remove(r)
for r in _ss:
    origem = "rodada llm-bench" if r["fonte"].startswith("llm-bench/") else "strata-exec"
    r["label"] = f"{r['label']} · {origem}"

# versão/modelo explícitos (contrato v1: campos opcionais); só de fonte observada, nunca inferidos do nome
_r = rodadas()
for row in data["strata_space"]:
    if versao_de(row.get("build")): row["versao"] = versao_de(row["build"])
# config_origin (contrato v1, extensão aprovada): só para linhas cuja config veio do plano da rodada (campo "papel");
# nunca deduzido do nome. Ausente = desconhecido.
for row in data["strata_space"]:
    lab = row["label"].split(" · ")[0].removesuffix("-probes")
    if row["fonte"].startswith("llm-bench/results/rodadas/") and (_r.get(lab) or {}).get("papel"):
        row["config_origin"] = _r[lab]["papel"]
for row in data["compreensao_mfc"]:
    info = _r.get(row["config"].removeprefix("mfc-"))
    if info and info.get("papel"): row["config_origin"] = info["papel"]
    if info: row["versao"] = info["versao"]; row["modelo"] = info["modelo"] or row.get("modelo")
for row in data["mesa_guardian"]:
    info = _r.get(row["modelo_tag"].removeprefix("rodada-"))
    if info and info.get("papel"): row["config_origin"] = info["papel"]
    if info: row["versao"] = info["versao"]; row["modelo"] = info["modelo"] or row.get("modelo")
for lst in ("compreensao_mfc", "mesa_guardian"):
    for row in data[lst]:
        if row.get("modelo") is None: row.pop("modelo", None)
# v1 has no gpu_id per row: every measurement belongs to the single GPU of the envelope
if len(data["gpus"]) != 1:
    raise SystemExit("v1 só admite uma GPU; outra GPU exige o contrato v2 com gpu_id por linha")
SCHEMA = Path("/home/brenoperucchi/Devs/llm-gateway/docs/schema-benchmarks-v1.json")
VALIDATOR = Path("/home/brenoperucchi/Devs/llm-gateway/.venv/bin/python")   # has jsonschema; this repo stays stdlib-only
CHECK = ("import json,sys,jsonschema;s=json.load(open(sys.argv[1]));d=json.load(sys.stdin);"
         "e=sorted(jsonschema.Draft202012Validator(s).iter_errors(d),key=str);"
         "[print('/'.join(map(str,x.absolute_path)),x.message[:200]) for x in e[:20]];sys.exit(1 if e else 0)")
r = subprocess.run([str(VALIDATOR), "-c", CHECK, str(SCHEMA)], input=json.dumps(data), capture_output=True, text=True)
if r.returncode != 0:
    raise SystemExit("contrato benchmarks-v1 violado; arquivo NÃO gravado:\n" + (r.stdout or r.stderr))
OUT.parent.mkdir(parents=True, exist_ok=True)
tmp = OUT.with_suffix(".json.tmp")
json.dump(data, open(tmp, "w"), ensure_ascii=False, indent=1)
tmp.replace(OUT)                       # atomic: the gateway never reads a half-written file

# Página estática (http-server 8088, /benchmarks/): mesmos dados + catálogo de comparação com os MESMOS IDs do gateway
# (llm_gateway.benchmarks_dashboard.comparison_items: sha256 do JSON canônico de {categoria, gpu_id, medicao}).
COMPARISON_SECTIONS = ("velocidade", "prompts_longos", "compreensao_mfc", "mesa_guardian", "strata_space", "historico")


def comparison_items(document):
    items = {}
    for section in COMPARISON_SECTIONS:
        for row in document[section]:
            content = {"categoria": section, "gpu_id": document["gpus"][0]["id"], "medicao": row}
            canonical = json.dumps(content, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
            identity = "v1-" + hashlib.sha256(canonical.encode("ascii")).hexdigest()
            items[identity] = {"id": identity, **content}
    return list(items.values())


WEB = ROOT / "web/data"
WEB.mkdir(parents=True, exist_ok=True)
for nome, conteudo in (("benchmarks.json", data), ("catalog.json", {"document": data, "items": comparison_items(data)})):
    t = WEB / (nome + ".tmp")
    t.write_text(json.dumps(conteudo, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    t.replace(WEB / nome)
print(OUT, {k: len(v) for k, v in data.items() if isinstance(v, list)})
