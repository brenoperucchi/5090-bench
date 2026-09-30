#!/usr/bin/env python3
"""Guardian synthesis bench: snapshot, gold, run, score, report.

The bench measures whether a model, given a Guardian slice (a flat chronology of
screen-derived facts), produces a synthesis that is faithful to what the items
*state*.  It never measures truth about the world: an item marked
``nao_verificado`` is gold for "must not be asserted as fact", not for "false".

Design constraints carried from the campaign plan (``PLANO.md``):

* the slice sent to every arm is byte-identical; only the instruction differs;
* every call records endpoint, model, prompt hash, snapshot hash, sampling
  parameters, usage, finish reason and latency;
* ``run`` refuses to call the model unless ``--confirm-inference`` is given, so
  building snapshots and gold never triggers inference by accident;
* nothing in this file writes outside the campaign directory in ``llm-bench``.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAMPAIGN = ROOT / "results" / "guardian-synthesis-20260921"
DEFAULT_GUARDIAN = "http://127.0.0.1:7717"
DEFAULT_ENDPOINT = "http://127.0.0.1:18194/v1/chat/completions"
DEFAULT_MODEL = "qwen3-coder-30b"
PROMPTS_DIR = ROOT / "prompts"
# Read-only source for the full timeline. The subject API only serves slices, and
# deriving C2 inside a slice hides the evidence that a decision was already
# answered — the answer routinely lands in another subject (owner, 2026-09-22).
NARRATIVAS_DIR = Path("/home/brenoperucchi/Devs/claude-bridge/.herdr/guardian/narrativas")

RESULT_LABEL = {"funcionou": "funcionou", "falhou": "FALHOU", "nao_verificado": "não verificado"}


# --------------------------------------------------------------------------- utils

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def http_get(url: str, timeout: float = 30) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url), timeout=timeout) as r:
        return r.read()


def http_post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[int, dict[str, Any] | None, str]:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers={"content-type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8")
            return r.status, json.loads(body), body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        return e.code, None, body


def stamp(iso: str) -> str:
    """Port of ``slice.ts::stamp`` — local wall-clock ``dd/mm hh:mm``."""
    d = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
    return f"{d.day:02d}/{d.month:02d} {d.hour:02d}:{d.minute:02d}"


# --------------------------------------------------------------------------- render (port of slice.ts::toPrompt)

def render_prompt(s: dict[str, Any]) -> str:
    """Byte-faithful port of ``guardian/web/slice.ts::toPrompt``.

    Kept in sync by ``verify-render``, which regenerates the markdown from the
    JSON snapshot and diffs it against what the API returned.
    """
    l: list[str] = []
    l.append("# Contexto para análise")
    l.append("")
    l.append("Abaixo está a cronologia de um trabalho em andamento, montada por um observador")
    l.append("que lê a tela do executor e interpreta o que vê — ele nunca leu a tarefa original.")
    l.append("")
    l.append("Explique para o Breno, em linguagem de negócio e sem jargão, o que está acontecendo:")
    l.append("o que foi feito, o que funcionou, o que falhou, e o que espera uma decisão dele.")
    l.append("Diga explicitamente o que NÃO dá para saber a partir destes itens — não preencha")
    l.append("lacuna com suposição plausível.")
    l.append("")
    l.append(f"**Projeto:** {s['project']}")
    if s.get("task"):
        l.append(f"**Tarefa:** {s['task']}")
    if s.get("subject"):
        l.append(f"**Recorte:** {s['subject']}")
    if s.get("state"):
        l.append(f"**Estado agora:** {s['state']}")
    if s.get("activity"):
        l.append(f"**Atividade agora:** {s['activity']}")
    l.append(
        f"**Itens neste recorte:** {len(s['items'])} de {s['totalInProject']} do projeto · "
        f"{s['unread']} ainda não lidos pelo Breno"
    )
    l.append("")
    l.append("---")
    l.append("")
    l.append("## Cronologia (mais recente primeiro)")
    l.append("")
    for i in s["items"]:
        l.append(f"### {stamp(i['quando'])}{'' if i.get('lido') else ' **[novo]**'}")
        l.append("")
        l.append(i["texto"])
        if i.get("porque"):
            l.append(f"\n- **Por quê:** {i['porque']}")
        if i.get("resultado"):
            l.append(f"- **Resultado:** {RESULT_LABEL.get(i['resultado'], 'não verificado')}")
        if i.get("aposInstrucao") and i.get("instrucao"):
            l.append(f"- **Veio depois desta instrução do Breno:** \"{i['instrucao']}\"")
        l.append(f"- _hora {'registrada pelo terminal' if i.get('fonte') == 'tela' else 'em que o observador leu'}_")
        l.append("")
    if s.get("related"):
        l.append("---")
        l.append("")
        l.append("## Adendo: outros assuntos interligados a este")
        l.append("")
        l.append("Estes assuntos NÃO estão no corpo acima, mas compartilham itens com ele —")
        l.append("são o mesmo trabalho visto de outro ângulo. Use-os como periferia: se algo")
        l.append("no foco só fizer sentido com um deles, diga qual você precisaria ver, em vez")
        l.append("de supor o que ele contém.")
        l.append("")
        l.append("| Assunto | Itens | Em comum com o foco | Exemplo |")
        l.append("|---|---:|---:|---|")
        for r in s["related"]:
            ex = (r.get("sample") or "")[:90].replace("|", "/")
            l.append(f"| {r['subject']} | {r['items']} | {r['overlap']} | {ex} |")
        l.append("")
    l.append("---")
    l.append("")
    l.append(f"_Recorte gerado em {stamp(s['generatedAt'])}._")
    return "\n".join(l)


def replace_header(markdown: str, *, state: str | None, activity: str | None) -> tuple[str, dict[str, bool]]:
    """Swap only the ``Estado agora``/``Atividade agora`` lines. Items are untouched.

    This is how the A4 variant is built: the chronology stays byte-identical and
    only the perception-derived header changes. Returns which fields were
    actually replaced — ``render_prompt`` omits those lines when the slice has no
    ``state``/``activity``, and a silent no-op would record ``variant="a4"`` on a
    prompt with no header conflict at all (rev-2 P2-3).
    """
    applied = {"state": False, "activity": False}
    out: list[str] = []
    for line in markdown.split("\n"):
        if line.startswith("**Estado agora:**") and state is not None:
            out.append(f"**Estado agora:** {state}")
            applied["state"] = True
        elif line.startswith("**Atividade agora:**") and activity is not None:
            out.append(f"**Atividade agora:** {activity}")
            applied["activity"] = True
        else:
            out.append(line)
    return "\n".join(out), applied


# --------------------------------------------------------------------------- snapshot

def snapshot_id(project: str, subject: str, sha: str) -> str:
    return f"{project}~{subject}~{sha[:12]}"


def cmd_snapshot(a: argparse.Namespace) -> int:
    camp = Path(a.campaign)
    snaps = camp / "snapshots"
    snaps.mkdir(parents=True, exist_ok=True)
    index_path = snaps / "index.json"
    index: dict[str, Any] = read_json(index_path) if index_path.exists() else {"snapshots": {}}

    fetched: dict[str, dict[str, Any]] = {}
    for subject in a.subject:
        base = f"{a.guardian}/api/v1/project/{a.project}/subject/{urllib.request.quote(subject)}"
        raw_json = http_get(base)
        raw_md = http_get(base + "?format=prompt")
        data = json.loads(raw_json)
        sha = sha256_bytes(raw_json)
        sid = snapshot_id(a.project, subject, sha)
        (snaps / f"{sid}.json").write_bytes(raw_json)
        (snaps / f"{sid}.prompt.md").write_bytes(raw_md)
        entry = {
            "id": sid,
            "project": a.project,
            "subject": subject,
            "kind": "api",
            "source_url": base,
            "json_sha256": sha,
            "prompt_md_sha256": sha256_bytes(raw_md),
            "prompt_md_bytes": len(raw_md),
            "items": len(data["items"]),
            "resultado": _count(data["items"], "resultado"),
            "generatedAt": data["generatedAt"],
            "totalInProject": data["totalInProject"],
            "fetched_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        index["snapshots"][sid] = entry
        fetched[subject] = data
        print(f"snapshot {sid}: {entry['items']} itens, {entry['resultado']}, prompt {entry['prompt_md_bytes']} B")

    for union in a.union or []:
        parts = union.split("+")
        part_ids: list[str] = []
        for part in parts:
            if part not in fetched:
                # Reuse the most recent API snapshot of that subject instead of
                # re-fetching a live, changing slice.
                prior = [e for e in index["snapshots"].values() if e.get("subject") == part and e.get("kind") == "api"]
                if not prior:
                    print(f"union {union}: sem snapshot de {part}; busque-o com --subject", file=sys.stderr)
                    return 2
                prior.sort(key=lambda e: e["fetched_at"])
                fetched[part] = read_json(snaps / f"{prior[-1]['id']}.json")
                part_ids.append(prior[-1]["id"])
            else:
                part_ids.append(next(e["id"] for e in index["snapshots"].values()
                                     if e.get("subject") == part and e.get("kind") == "api"
                                     and e["generatedAt"] == fetched[part]["generatedAt"]))
        merged = _union_slice(a.project, parts, [fetched[p] for p in parts])
        raw_json = (json.dumps(merged, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        md = render_prompt(merged)
        sha = sha256_bytes(raw_json)
        sid = snapshot_id(a.project, union, sha)
        (snaps / f"{sid}.json").write_bytes(raw_json)
        (snaps / f"{sid}.prompt.md").write_text(md, encoding="utf-8")
        entry = {
            "id": sid,
            "project": a.project,
            "subject": union,
            "kind": "union-rendered-locally",
            "parts": parts,
            "part_snapshots": part_ids,
            "json_sha256": sha,
            "prompt_md_sha256": sha256_text(md),
            "prompt_md_bytes": len(md.encode("utf-8")),
            "items": len(merged["items"]),
            "overlap_items": merged["_union"]["overlap"],
            "resultado": _count(merged["items"], "resultado"),
            "generatedAt": merged["generatedAt"],
            "totalInProject": merged["totalInProject"],
            "fetched_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "note": "Rendered by render_prompt (Python port of slice.ts::toPrompt); related[] deliberately empty.",
        }
        index["snapshots"][sid] = entry
        print(f"snapshot {sid}: {entry['items']} itens ({entry['overlap_items']} em cruzamento), prompt {entry['prompt_md_bytes']} B")

    write_json(index_path, index)
    return 0


def _count(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for i in items:
        v = str(i.get(key))
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items()))


def _union_slice(project: str, parts: list[str], slices: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge subject slices, identifying an item by (``quando``, ``texto``).

    ``slice.ts::relatedTo`` measures overlap by ``quando`` alone. Several distinct
    items share one ``quando`` (one screen read yields many facts), so that key
    collapses different items; the first union attempt lost 14 of 55 items this
    way. Identity here is the pair, and the overlap reported to the Guardian side
    notes the discrepancy instead of adopting it.
    """
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    membership: dict[tuple[str, str], set[str]] = {}
    for name, s in zip(parts, slices):
        for i in s["items"]:
            key = (i["quando"], i["texto"])
            # Same key as ``seen``, and a set: a truncated key merged distinct
            # items, and a list inflated overlap when a part repeated an item
            # (rev-2 P3-2).
            membership.setdefault(key, set()).add(name)
            seen.setdefault(key, i)
    items = sorted(seen.values(), key=lambda i: i["quando"], reverse=True)
    first = slices[0]
    return {
        "project": project,
        "task": first.get("task"),
        # No real header corresponds to a union of subjects, and the header is
        # precisely what triggers A4 / "só o cabeçalho diz"; inheriting parts[0]'s
        # would plant an unintended conflict in the B1 slice (rev-2 P3-1).
        "state": None,
        "activity": None,
        "totalInProject": first["totalInProject"],
        "generatedAt": max(s["generatedAt"] for s in slices),
        "subject": "+".join(parts),
        "items": items,
        "unread": sum(1 for i in items if not i.get("lido")),
        "related": [],
        "_union": {
            "parts": parts,
            "header": "omitido de propósito: nenhum Estado/Atividade real corresponde à união",
            "task_from": parts[0],
            "overlap": sum(1 for v in membership.values() if len(v) > 1),
            "membership": {f"{q}|{t[:60]}": sorted(v) for (q, t), v in membership.items()},
        },
    }


def cmd_chronology(a: argparse.Namespace) -> int:
    """Freeze the project's full timeline, hash-addressed. Read-only."""
    src = Path(a.narrativas) / f"{a.project}.json"
    raw = src.read_bytes()
    data = json.loads(raw)
    items = data["linha"]
    payload = {
        "schema": "guardian-chronology-v1",
        "project": a.project,
        "source": str(src),
        "source_sha256": sha256_bytes(raw),
        "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "atualizadoEm": data.get("atualizadoEm"),
        "items": sorted(items, key=lambda i: i["quando"], reverse=True),
    }
    body = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    sid = f"{a.project}~CHRONOLOGY~{sha256_bytes(body)[:12]}"
    camp = Path(a.campaign) / "snapshots"
    camp.mkdir(parents=True, exist_ok=True)
    (camp / f"{sid}.json").write_bytes(body)
    index_path = camp / "index.json"
    index = read_json(index_path) if index_path.exists() else {"snapshots": {}}
    index["snapshots"][sid] = {
        "id": sid, "project": a.project, "kind": "chronology",
        "items": len(items), "resultado": _count(items, "resultado"),
        "source": str(src), "source_sha256": payload["source_sha256"],
        "captured_at": payload["captured_at"],
        "note": "cronologia COMPLETA do projeto; serve para derivar C2 sem cortar a evidência de resolução",
    }
    write_json(index_path, index)
    print(f"chronology {sid}: {len(items)} itens, {payload['source_sha256'][:12]}…")
    return 0


def cmd_verify_render(a: argparse.Namespace) -> int:
    """Regenerate the markdown from the JSON snapshot and diff against the API's."""
    camp = Path(a.campaign)
    ok = True
    for sid in a.snapshot:
        data = read_json(camp / "snapshots" / f"{sid}.json")
        api_md = (camp / "snapshots" / f"{sid}.prompt.md").read_text(encoding="utf-8")
        mine = render_prompt(data)
        if mine == api_md:
            print(f"{sid}: render idêntico ({len(api_md.encode())} B)")
            continue
        ok = False
        print(f"{sid}: DIVERGE")
        for line in difflib.unified_diff(api_md.split("\n"), mine.split("\n"), "api", "port", lineterm="", n=1):
            print("  " + line)
    return 0 if ok else 1


# --------------------------------------------------------------------------- gold

def cmd_gold(a: argparse.Namespace) -> int:
    camp = Path(a.campaign)
    data = read_json(camp / "snapshots" / f"{a.snapshot}.json")
    items = data["items"]
    chronology = None
    if a.chronology:
        chronology = read_json(camp / "snapshots" / f"{a.chronology}.json")
    gold: dict[str, Any] = {
        "schema": "guardian-synthesis-gold-v1",
        "snapshot": a.snapshot,
        "snapshot_json_sha256": sha256_file(camp / "snapshots" / f"{a.snapshot}.json"),
        "principle": (
            "Mede fidelidade ao que a cronologia AFIRMA, não verdade no mundo. "
            "Um item nao_verificado é gold para 'não pode ser afirmado como fato', não para 'falso'."
        ),
        "items": [],
        "a1_explicit_results": [],
        "a2_unverified": [],
        "a3_anchors": [],
        "a4_header_conflict": None,
        "b2_indistinction": None,
        "c2_pending_decisions": {
            "rule_status": "regra 'instrucao com ?' aprovada pelo owner em 2026-09-21 19:49; entradas por extensão da regra têm status próprio",
            "entries": [],
        },
        "counts": _count(items, "resultado"),
    }
    union = data.get("_union")
    if union:
        gold["b1_membership"] = union.get("membership")
        gold["b1_note"] = ("Agrupamento por assunto do próprio Guardian — proxy declarado, "
                           "não gold do owner. Avaliação de B1 é manual, no checklist.")
    for n, i in enumerate(items):
        ref = {"n": n, "stamp": stamp(i["quando"]), "quando": i["quando"], "texto": i["texto"],
               # `porque` carries the substance of some pending decisions ("precisa
               # de duas decisões"); dropping it hid what C2 is about (rev-1 #6).
               "porque": i.get("porque"), "resultado": i["resultado"]}
        gold["items"].append(ref)
        if i["resultado"] in ("funcionou", "falhou"):
            gold["a1_explicit_results"].append({**ref, "status": "source_derived", "must_not": _polarity_flip(i["resultado"])})
        else:
            gold["a2_unverified"].append({**ref, "status": "source_derived",
                                          "must_not": "afirmado como desfecho confirmado (nem funcionou, nem FALHOU)"})
        if chronology is not None:
            continue  # C2 comes from the whole project below, not from the slice
        instr = (i.get("instrucao") or "").strip()
        if i.get("aposInstrucao") and _looks_like_question(instr):
            # One owner question usually precedes several items; group them so the
            # gold counts decisions, not items.
            entry = next((e for e in gold["c2_pending_decisions"]["entries"] if e.get("instrucao") == instr), None)
            if entry is None:
                # The owner approved (2026-09-21 19:49) the rule "instrucao com ?".
                # A question recognised only by its opener (the mark was truncated)
                # is an extension of that rule and keeps its own status.
                literal = "?" in instr
                gold["c2_pending_decisions"]["entries"].append({
                    "instrucao": instr,
                    "origin": "instrucao com ?" if literal else "instrucao em forma de pergunta (sem ?, truncada)",
                    "status": "owner_approved_2026-09-21" if literal else "source_derived_pending_owner",
                    "refs": [ref],
                })
            else:
                entry["refs"].append(ref)
        elif re.search(r"\bdecis(ão|ões)\b", (i["texto"] + " " + (i.get("porque") or "")), re.I):
            gold["c2_pending_decisions"]["entries"].append({
                "origin": "texto/porque menciona decisão", "status": "source_derived_pending_owner", "refs": [ref],
            })

    if chronology is not None:
        gold["c2_pending_decisions"] = _derive_c2(chronology, items, camp, a.chronology)

    if a.anchors:
        manual = read_json(Path(a.anchors))
        for key in ("a3_anchors", "a4_header_conflict", "b2_indistinction", "counting_rule"):
            if key in manual:
                gold[key] = manual[key]
        if "c2_pending_decisions" in manual:
            override = dict(manual["c2_pending_decisions"])
            rulings = override.pop("rulings", None)
            added = override.pop("owner_added", None)
            gold["c2_pending_decisions"] = {**gold["c2_pending_decisions"], **override}
            if added:
                gold["c2_pending_decisions"]["entries"] = (
                    list(gold["c2_pending_decisions"]["entries"]) + _owner_added_c2(added, items)
                )
            if rulings:
                _apply_c2_rulings(gold["c2_pending_decisions"], rulings)
        gold["anchors_file"] = str(Path(a.anchors).resolve().relative_to(ROOT))
        gold["anchors_sha256"] = sha256_file(Path(a.anchors))
        _check_anchor_refs(gold)

    out = camp / "gold" / f"{a.snapshot}.gold.json"
    write_json(out, gold)
    print(
        f"gold {out.relative_to(ROOT)}: A1={len(gold['a1_explicit_results'])} A2={len(gold['a2_unverified'])} "
        f"A3={len(gold['a3_anchors'])} C2={len(gold['c2_pending_decisions']['entries'])} "
        f"A4={'sim' if gold['a4_header_conflict'] else 'não'} B2={'sim' if gold['b2_indistinction'] else 'não'}"
    )
    return 0


QUESTION_OPENERS = re.compile(r"^(quer que|n[ãa]o seria|posso|devo|qual|como|o que|será que|prefere|vale)\b", re.I)


def _looks_like_question(instr: str) -> bool:
    """``instrucao`` is truncated by the perception layer, so a trailing ``?`` is
    not reliable (the MN1 warm-up question was cut before its mark)."""
    return "?" in instr or bool(QUESTION_OPENERS.match(instr))


def _derive_c2(chronology: dict[str, Any], slice_items: list[dict[str, Any]],
               camp: Path, chronology_id: str) -> dict[str, Any]:
    """Derive C2 over the WHOLE project, then keep what touches this slice.

    ⚠️ Deriving inside a slice was wrong, and the owner proved it on real data
    (2026-09-22): the MN1 warm-up question was asked at 21/09 17:14 inside the
    Ryzen9 slice and answered at 17:29 by items the grouping filed under other
    subjects. A rule that only looks at one slice bills the owner for decisions
    he already made — and penalises the answer that correctly left them out.

    Resolution is never decided here. Each candidate carries the later items that
    might answer it; the owner rules, and the ruling lands in the anchors file.
    """
    full = chronology["items"]
    in_slice = {(i["quando"], i["texto"]) for i in slice_items}
    questions: dict[str, dict[str, Any]] = {}
    for i in full:
        instr = (i.get("instrucao") or "").strip()
        if not (i.get("aposInstrucao") and _looks_like_question(instr)):
            continue
        entry = questions.setdefault(instr, {
            "instrucao": instr,
            "origin": "instrucao com ?" if "?" in instr else "instrucao em forma de pergunta (sem ?, truncada)",
            "status": ("owner_approved_2026-09-21" if "?" in instr else "source_derived_pending_owner"),
            "refs": [], "refs_outside_slice": 0,
        })
        ref = {"stamp": stamp(i["quando"]), "quando": i["quando"], "texto": i["texto"],
               "porque": i.get("porque"), "resultado": i["resultado"]}
        if (i["quando"], i["texto"]) in in_slice:
            entry["refs"].append(ref)
        else:
            entry["refs_outside_slice"] += 1
        entry["last_seen"] = max(entry.get("last_seen", ""), i["quando"])
    kept = [e for e in questions.values() if e["refs"]]
    for e in kept:
        # Everything the project recorded after the question stopped being echoed:
        # this is where an answer would be, in or out of the slice.
        later = [i for i in full if i["quando"] > e["last_seen"]]
        e["evidence_window"] = {
            "items_after_in_project": len(later),
            "items_after_inside_slice": sum(1 for i in later if (i["quando"], i["texto"]) in in_slice),
            "note": "a resolução costuma estar fora do recorte; conferir aqui antes de tratar como pendente",
        }
    kept.sort(key=lambda e: e["last_seen"], reverse=True)
    return {
        "rule_status": ("regra 'instrucao com ?' aprovada pelo owner em 2026-09-21 19:49; "
                        "derivada sobre a cronologia COMPLETA desde 2026-09-22"),
        "derived_from": chronology_id,
        "chronology_source_sha256": chronology["source_sha256"],
        "chronology_items": len(full),
        "limitation": ("O derivador não decide resolução — não há como saber por script se um item "
                       "posterior responde à pergunta. Cada candidato traz a janela de evidência; "
                       "o veredito por entrada vem do owner, no arquivo de âncoras."),
        "entries": kept,
    }


def _polarity_flip(resultado: str) -> str:
    """What the answer must not say about this item's *result*.

    Only the result label, never the verb: a removal can have succeeded, so
    "removido" is not the opposite of "funcionou" (rev-1 #5). Inverting the
    action itself is a separate defect, checked by A3 and by the evaluator.
    """
    return ("dito como falhou ou não verificado" if resultado == "funcionou"
            else "dito como funcionou ou não verificado")


def _owner_added_c2(added: list[dict[str, Any]], slice_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pending decisions the owner declares directly.

    The derivation only recognises a decision when it is phrased as a question in
    ``instrucao``. A real pending decision can be recorded some other way — the
    mfc2 one lives in an item's text, and what it is waiting for is named in a
    third item, in another subject. The owner names it; the script only checks
    that the cited slice items exist.
    """
    by_stamp: dict[str, list[dict[str, Any]]] = {}
    for i in slice_items:
        by_stamp.setdefault(stamp(i["quando"]), []).append(i)
    out: list[dict[str, Any]] = []
    for entry in added:
        refs = []
        for want in entry["slice_refs"]:
            cands = by_stamp.get(want["stamp"], [])
            match = next((c for c in cands if want["texto_starts"].lower() in c["texto"].lower()), None)
            if match is None:
                raise SystemExit(f"c2 owner_added cita item inexistente no recorte: {want}")
            refs.append({"stamp": want["stamp"], "quando": match["quando"], "texto": match["texto"],
                         "porque": match.get("porque"), "resultado": match["resultado"]})
        out.append({
            "instrucao": entry["name"],
            "origin": "declarada pelo owner (não derivável da regra: não é pergunta em `instrucao`)",
            "status": "owner_declared_2026-09-22",
            "why_excluded": entry.get("why_excluded"),
            "refs": refs,
            "decisions": entry["decisions"],
            "evidence": entry.get("evidence"),
            "scoring": entry.get("scoring"),
            "scored": entry.get("verdict", "pendente") == "pendente",
            "owner_ruling": entry.get("verdict", "pendente"),
        })
    return out


def _apply_c2_rulings(c2: dict[str, Any], rulings: list[dict[str, Any]]) -> None:
    """Attach the owner's per-entry verdict. Only a `pendente` entry is scored."""
    unmatched = [r for r in rulings]
    for entry in c2["entries"]:
        if entry.get("status") == "owner_declared_2026-09-22":
            continue
        for ruling in rulings:
            if ruling["matches_instrucao"].lower() in entry["instrucao"].lower():
                v = ruling["verdict"]
                entry["owner_ruling"] = v
                entry["owner_evidence"] = ruling.get("evidence")
                entry["decisions"] = ruling.get("decisions")
                entry["status"] = {
                    "pendente": "owner_ruled_pending",
                    "resolvida": "owner_ruled_resolved",
                    # Missing evidence must not default to "pending": a question
                    # nobody can check objectively is excluded from the gold, not
                    # billed to the owner (owner, 2026-09-22 15:34).
                    "nao_conferivel": "owner_ruled_not_checkable",
                }[v] + "_2026-09-22"
                entry["scored"] = v == "pendente"
                if ruling in unmatched:
                    unmatched.remove(ruling)
                break
        else:
            entry.setdefault("scored", False)
            entry.setdefault("owner_ruling", "nao_julgada")
    if unmatched:
        raise SystemExit("veredito do owner sem entrada correspondente: "
                         + ", ".join(r["matches_instrucao"][:50] for r in unmatched))
    scored = [e for e in c2["entries"] if e.get("scored")]
    c2["scored_entries"] = len(scored)
    if not scored:
        c2["axis_state"] = ("informativo — nenhuma pendência confirmada pelo owner neste recorte; "
                            "C2 não entra na soma da rubrica C")


def _check_anchor_refs(gold: dict[str, Any]) -> None:
    """Every manual anchor must cite item indices that exist and whose stamp matches."""
    by_n = {i["n"]: i for i in gold["items"]}
    for anchor in gold["a3_anchors"]:
        for ref in anchor.get("evidence", []):
            item = by_n.get(ref["n"])
            if item is None or item["stamp"] != ref["stamp"]:
                raise SystemExit(f"anchor {anchor['id']} cita item inexistente ou com carimbo errado: {ref}")
            ref["resultado"] = item["resultado"]
            ref["texto"] = item["texto"]


# --------------------------------------------------------------------------- run

def load_instruction(arm: str) -> tuple[str, Path]:
    path = PROMPTS_DIR / f"guardian-synthesis-{arm}.md"
    text = path.read_text(encoding="utf-8")
    # The file carries a provenance header above a marker; only what follows is sent.
    marker = "<!-- INSTRUCTION-BEGIN -->\n"
    if marker in text:
        text = text.split(marker, 1)[1]
    return text, path


def cmd_run(a: argparse.Namespace) -> int:
    if not a.confirm_inference:
        print("run chama o modelo. Repita com --confirm-inference.", file=sys.stderr)
        return 2
    camp = Path(a.campaign)
    instruction, ipath = load_instruction(a.arm)
    slice_md = (camp / "snapshots" / f"{a.snapshot}.prompt.md").read_text(encoding="utf-8")
    variant = "base"
    a4_applied: dict[str, bool] | None = None
    if a.a4:
        gold = read_json(camp / "gold" / f"{a.snapshot}.gold.json")
        spec = gold.get("a4_header_conflict")
        if not spec:
            print("gold não tem a4_header_conflict; nada a variar", file=sys.stderr)
            return 2
        slice_md, a4_applied = replace_header(slice_md, state=spec.get("state"), activity=spec.get("activity"))
        wanted = {k for k in ("state", "activity") if spec.get(k) is not None}
        missing = sorted(k for k in wanted if not a4_applied[k])
        if missing:
            print(f"--a4 pedido mas o recorte não tem a(s) linha(s) {missing}: o prompt não teria conflito "
                  f"de cabeçalho e seria gravado como a4 mesmo assim. Abortado.", file=sys.stderr)
            return 2
        variant = "a4"
    prompt = instruction + slice_md
    props = _server_props(a.endpoint)
    max_tokens = a.max_tokens
    budget: dict[str, Any] | None = None
    if a.max_tokens_auto:
        n_ctx = (props or {}).get("n_ctx")
        counted = _count_tokens(a.endpoint, prompt)
        if not isinstance(n_ctx, int) or counted is None:
            # A pre-flight failure used to leave no trace at all, so a dead
            # endpoint produced a silent gap in the campaign instead of a record
            # saying what was attempted and why it did not happen.
            write_json(runs_dir_for(camp) / _failed_name(a, variant), {
                "schema": "guardian-synthesis-run-v1", "state": "preflight_failed",
                "arm": a.arm, "snapshot": a.snapshot, "variant": variant,
                "endpoint": a.endpoint, "model": a.model,
                "error": "--max-tokens-auto precisa de n_ctx em /props e de /tokenize",
                "server_props": props, "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            })
            print("--max-tokens-auto precisa de n_ctx em /props e de /tokenize", file=sys.stderr)
            return 2
        max_tokens = n_ctx - counted - a.ctx_margin
        if max_tokens < 512:
            print(f"sobra de contexto insuficiente: n_ctx={n_ctx} entrada={counted}", file=sys.stderr)
            return 2
        budget = {"n_ctx": n_ctx, "prompt_tokens_counted": counted, "margin": a.ctx_margin,
                  "max_tokens_granted": max_tokens,
                  "note": "teto = todo o contexto restante; uma truncagem aqui é limite do n_ctx, não escolha"}
        print(f"  auto: n_ctx={n_ctx} entrada={counted} → max_tokens={max_tokens}")
    ctk = json.loads(a.chat_template_kwargs) if a.chat_template_kwargs else None
    runs_dir = runs_dir_for(camp)
    for k in range(a.repeats):
        payload: dict[str, Any] = {
            "model": a.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": a.temperature,
            "top_p": a.top_p,
            "top_k": a.top_k,
            "min_p": a.min_p,
            "seed": a.seed + k if a.seed is not None else None,
            "max_tokens": max_tokens,
            "chat_template_kwargs": ctk,
        }
        payload = {k2: v for k2, v in payload.items() if v is not None}
        t0 = time.monotonic()
        status, body, raw = http_post_json(a.endpoint, payload, timeout=a.timeout)
        latency = round(time.monotonic() - t0, 3)
        choice = (body or {}).get("choices", [{}])[0] if body else {}
        msg = choice.get("message", {}) if isinstance(choice, dict) else {}
        record = {
            "schema": "guardian-synthesis-run-v1",
            "campaign": str(camp.relative_to(ROOT)),
            "arm": a.arm,
            "variant": variant,
            "snapshot": a.snapshot,
            "a4_header_applied": a4_applied,
            "snapshot_prompt_md_sha256": sha256_text(slice_md),
            "instruction_file": str(ipath.relative_to(ROOT)),
            "instruction_sha256": sha256_text(instruction),
            "prompt_sha256": sha256_text(prompt),
            "prompt_sha256_12": sha256_text(prompt)[:12],
            "prompt_bytes": len(prompt.encode("utf-8")),
            "endpoint": a.endpoint,
            "model": a.model,
            "server_props": props,
            "sampling": {k2: payload.get(k2) for k2 in ("temperature", "top_p", "top_k", "min_p", "seed", "max_tokens")},
            "chat_template_kwargs": ctk,
            "context_budget": budget,
            "repeat": k,
            "http_status": status,
            "usage": (body or {}).get("usage"),
            "timings": (body or {}).get("timings"),
            "finish_reason": choice.get("finish_reason") if isinstance(choice, dict) else None,
            "latency_s": latency,
            "content": msg.get("content"),
            "reasoning_content": msg.get("reasoning_content"),
            "error": None if body else raw[:2000],
            "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        temp_tag = str(a.temperature).replace(".", "p")
        seed_tag = payload.get("seed", "noseed")
        # Everything that distinguishes one call from another belongs in the
        # name. max_tokens was added after a collision; the MODEL was added after
        # a Bonsai run silently overwrote a qwen run with the same parameters.
        model_tag = re.sub(r"[^A-Za-z0-9.-]+", "-", a.model)
        name = f"{a.arm}~{model_tag}~{a.snapshot}~{variant}~t{temp_tag}~s{seed_tag}~m{max_tokens}~r{k}.json"
        write_json(runs_dir / name, record)
        u = record["usage"] or {}
        print(
            f"{name}: http={status} finish={record['finish_reason']} in={u.get('prompt_tokens')} "
            f"out={u.get('completion_tokens')} {latency}s"
        )
    return 0


def _count_tokens(endpoint: str, text: str) -> int | None:
    base = endpoint.split("/v1/")[0]
    try:
        status, body, _ = http_post_json(base + "/tokenize", {"content": text}, timeout=30)
        return len(body["tokens"]) if status == 200 and body else None
    except Exception:  # noqa: BLE001 — falling back is the caller's decision
        return None


def runs_dir_for(camp: Path) -> Path:
    d = camp / "runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _failed_name(a: argparse.Namespace, variant: str) -> str:
    model_tag = re.sub(r"[^A-Za-z0-9.-]+", "-", a.model)
    return f"FAILED~{a.arm}~{model_tag}~{a.snapshot}~{variant}~{int(time.time())}.json"


def _server_props(endpoint: str) -> dict[str, Any] | None:
    base = endpoint.split("/v1/")[0]
    try:
        p = json.loads(http_get(base + "/props", timeout=10))
        gs = p.get("default_generation_settings", {})
        return {
            "n_ctx": gs.get("n_ctx"),
            "model_path": p.get("model_path"),
            "build_info": p.get("build_info"),
            "chat_format": gs.get("params", {}).get("chat_format"),
            "reasoning_format": gs.get("params", {}).get("reasoning_format"),
        }
    except Exception as e:  # noqa: BLE001 — provenance is best-effort, the run is not
        return {"error": str(e)}


# --------------------------------------------------------------------------- score

LEDGER_RE = re.compile(r"```json\s*ledger\s*\n(.*?)```", re.S)
LEDGER_OPEN_RE = re.compile(r"```json\s*ledger\s*\n", re.S)
NEG_WORDS = r"(removid[oa]|desativad[oa]|apagad[oa]|retirad[oa]|desfeit[oa]|falhou|não funcionou|nao funcionou)"


def cmd_score(a: argparse.Namespace) -> int:
    camp = Path(a.campaign)
    for run_path in a.run:
        run = read_json(Path(run_path))
        run["_path"] = str(Path(run_path).resolve())
        gold = read_json(camp / "gold" / f"{run['snapshot']}.gold.json")
        text = run.get("content") or ""
        score: dict[str, Any] = {
            "schema": "guardian-synthesis-score-v1",
            "run": str(Path(run_path).resolve().relative_to(ROOT)),
            "arm": run["arm"],
            "variant": run["variant"],
            "snapshot": run["snapshot"],
            "gold_sha256": sha256_file(camp / "gold" / f"{run['snapshot']}.gold.json"),
            "content_bytes": len(text.encode("utf-8")),
            "prescreen": _prescreen(text, gold),
            "c1_pending_first": _c1_position(text),
            "c3_three_lists": _c3_lists(text),
            "b2_indistinction_phrase": _b2_phrase(text),
            "a4_header_quarantined": _a4_quarantined(text) if run["variant"] == "a4" else None,
            "comprimento": {"completion_tokens": (run.get("usage") or {}).get("completion_tokens"),
                            "finish_reason": run.get("finish_reason")},
            "lacunas_posicao": gap_position(text, getattr(a, "tokenize_endpoint", None)),
            "ledger": None,
            "note": (
                "prescreen/c1/c3/b2 são heurísticas textuais declaradas como pré-triagem; "
                "o número que conta vem do checklist dos dois avaliadores cegos (checklists/)."
            ),
        }
        m = LEDGER_RE.search(text)
        if not m:
            # "Never started" and "started but cut off" are different facts: the
            # second says the model complied and ran out of output budget.
            started = LEDGER_OPEN_RE.search(text)
            truncated = run.get("finish_reason") == "length"
            if started:
                score["ledger"] = {"state": "truncado",
                                   "note": "bloco ```json ledger``` começou e não fechou",
                                   "finish_reason": run.get("finish_reason")}
            elif truncated:
                score["ledger"] = {"state": "cortado_antes_do_ledger",
                                   "note": "resposta truncada por max_tokens antes de abrir o ledger",
                                   "finish_reason": "length"}
            else:
                score["ledger"] = {"state": "ausente", "note": "a resposta não traz bloco ```json ledger```"}
        else:
            try:
                parsed = json.loads(m.group(1))
            except json.JSONDecodeError as e:
                score["ledger"] = {"state": "json_invalido", "error": str(e)}
            else:
                problem = _ledger_schema_error(parsed)
                if problem:
                    # A model can emit syntactically valid JSON with the wrong
                    # shape; that must not abort the batch (rev-1 #3).
                    score["ledger"] = {"state": "schema_invalido", "schema_error": problem}
                else:
                    score["ledger"] = {"state": "ok", **_score_ledger(parsed, gold)}
        out = camp / "scores" / (Path(run_path).stem + ".score.json")
        write_json(out, score)
        _write_checklist(camp, run, gold, text, score.get("ledger") if isinstance(score.get("ledger"), dict) else None)
        print(f"score {out.relative_to(ROOT)}: prescreen_hits={score['prescreen']['n']} "
              f"(suprimidos={len(score['prescreen']['suppressed_by_negation'])}) "
              f"c1={score['c1_pending_first'].get('pending_is_first_block')} "
              f"c3_separado={score['c3_three_lists']['separated']} b2={score['b2_indistinction_phrase']} "
              f"ledger={'sim' if m else 'não'}")
    return 0


# Negation/attribution can sit before the matched phrase ("nenhum item registra
# remoção do kill switch") or inside it ("a trava **não foi** removida"), so the
# window is the 60 characters before the match plus the match itself.
NEGATION_WINDOW = re.compile(
    r"n[ãa]o\s+\w+|nenhum|nenhuma|sem\s+registro|jamais|tampouco"
    r"|(o\s+)?(cabe[çc]alho|estado\s+(agora|atual)|atividade\s+(agora|atual))\s*(diz|afirma|informa|:)?"
    r"|\bagora\b\s*[·:|-]"
    # Direction-out phrasings for A3.2: "tirar o MT5 do ambiente no Ryzen9" is
    # the correct reading, not the inversion.
    r"|tirar\s+[^.\n]{0,40}\bd[oe]\b|sair\s+d|migra[çc][ãa]o\s+para\s+fora|fora\s+d[oe]\s+ryzen9"
    r"|origem|deixar\s+de\s+usar|abandonad|descartad|deixou\s+de\s+ser"
    r"|n[ãa]o\s+h[áa]\s+registro|sem\s+nenhum\s+item",
    re.I,
)
QUARANTINE_LEDGER = re.compile(r"```json\s*ledger\s*\n.*?```", re.S)
QUARANTINE_HEADER_SECTION = re.compile(
    r"^#{1,6}[^\n]*s[óo]\s+o\s+cabe[çc]alho[^\n]*$.*?(?=^#{1,6}\s|\Z)", re.I | re.M | re.S
)


def _quarantine(text: str) -> tuple[str, list[str]]:
    """Remove the regions where naming the header's claim is the *correct* answer.

    The v2 arm is told to quote the header in "Só o cabeçalho diz" and to repeat
    it in ``so_cabecalho``. Scanning those regions would flag a correct v2+a4
    answer by construction, biasing the arm comparison against v2 (rev-2 P1-2).
    """
    regions: list[str] = []

    def take(m: re.Match[str]) -> str:
        regions.append(m.group(0))
        return "\n"

    body = QUARANTINE_LEDGER.sub(take, text)
    body = QUARANTINE_HEADER_SECTION.sub(take, body)
    return body, regions


def _prescreen(text: str, gold: dict[str, Any]) -> dict[str, Any]:
    """Cheap regex hits for anchor polarity. **Not** the metric, and not an error
    count: a hit only says the anchor's wording appears outside the quarantined
    regions, unnegated. The number that counts comes from the blind checklist.
    """
    body, regions = _quarantine(text)
    low = body.lower()
    hits: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    for anchor in gold.get("a3_anchors", []):
        for pat in anchor.get("prescreen_patterns", []):
            for m in re.finditer(pat, low, re.I | re.S):
                # The qualifier can follow the phrase too ("o Ryzen9 como host
                # foi abandonado"), so the window runs to the end of the sentence
                # (rev-1, resposta 2).
                tail = re.split(r"[.\n;]", low[m.end():m.end() + 90], maxsplit=1)[0]
                window = low[max(0, m.start() - 60):m.end()] + tail
                entry = {
                    "anchor": anchor["id"],
                    "pattern": pat,
                    "excerpt": body[max(0, m.start() - 60):m.end() + 40].replace("\n", " ").strip(),
                }
                (suppressed if NEGATION_WINDOW.search(window) else hits).append(entry)
    return {
        "hits": hits,
        "n": len(hits),
        "suppressed_by_negation": suppressed,
        "quarantined_regions": len(regions),
        "meaning": "hit = a frase da âncora aparece afirmada fora das regiões de quarentena; pode marcar acerto, não é contagem de erro",
    }


def _c1_position(text: str) -> dict[str, Any]:
    """Report where the pending-decision block sits. The binary is the evaluator's.

    C1 is defined once, here and in the checklist: *the first content block of
    the answer — heading or bold section — is the pending-decisions one*. A
    section boundary is a markdown heading or a standalone bold line, because
    the ``atual`` arm may answer with no ``#`` at all; with no boundary of either
    kind the heuristic falls back to relative position and says so, instead of
    passing by default (rev-2 P2-1).
    """
    lines = text.split("\n")
    bounds = [i for i, l in enumerate(lines)
              if l.startswith("#") or re.match(r"^\*\*[^*]+\*\*:?\s*$", l.strip())]
    pend = next((i for i, l in enumerate(lines)
                 if re.search(r"decis(ão|ões)|espera (você|o breno)|pendente|aguarda", l, re.I)), None)
    if pend is None:
        return {"first_boundary_line": bounds[0] if bounds else None, "first_pending_line": None,
                "basis": "nenhuma menção a decisão encontrada", "pending_is_first_block": False}
    if bounds:
        before = [b for b in bounds if b < pend]
        # A leading H1 counts as the answer's title only when no prose sits
        # between it and the next boundary; otherwise it opens a real section.
        title_only = False
        if before and lines[before[0]].startswith("# "):
            nxt = next((b for b in bounds if b > before[0]), len(lines))
            title_only = not any(l.strip() for l in lines[before[0] + 1:nxt])
        allowed = 1 if title_only else 0
        return {"first_boundary_line": bounds[0], "first_pending_line": pend,
                "sections_before_pending": len(before), "leading_title_ignored": title_only,
                "basis": "primeiro bloco de conteúdo (título isolado não conta)",
                "pending_is_first_block": len(before) <= allowed}
    rel = pend / max(1, len(lines))
    return {"first_boundary_line": None, "first_pending_line": pend, "relative_position": round(rel, 3),
            "basis": "sem fronteiras — posição relativa, sinal mais fraco",
            "pending_is_first_block": rel <= 0.15}


def _c3_lists(text: str) -> dict[str, bool]:
    """Heuristic only. Calibrated on the historical qwen answer, whose heading
    'O que falhou ou não verificado' merges two lists — that is what
    ``merged_falhou_nao_verificado`` catches."""
    low = text.lower()
    headings = [l for l in low.split("\n") if l.startswith("#") or re.match(r"^\*\*[^*]+\*\*:?\s*$", l.strip())]
    merged = any(
        (re.search(r"falh", h) and re.search(r"verificad", h))
        # A merged list can also avoid both words: "o que ainda não posso confirmar".
        or re.search(r"(ainda )?n[ãa]o (posso |consigo )?(confirmar|comprovar)", h)
        for h in headings
    )
    funcionou = bool(re.search(r"^#{1,6}.*funcion|\*\*.*funcion.*\*\*", low, re.M))
    falhou = bool(re.search(r"^#{1,6}.*falh|\*\*.*falh.*\*\*", low, re.M))
    nv = bool(re.search(r"n[ãa]o[ -]verificad", low))
    return {
        "funcionou": funcionou,
        "falhou": falhou,
        "nao_verificado": nv,
        "merged_falhou_nao_verificado": merged,
        # C3 asks for three labelled lists, so all three must be present (rev-2 P2-2).
        "separated": funcionou and falhou and nv and not merged,
    }


def _a4_quarantined(text: str) -> dict[str, Any]:
    """Did the answer put the header's claim somewhere marked as the header's?

    Pre-screen with the same caveat as the others; the binary is the evaluator's
    (rev-2 P3-3).
    """
    section = bool(QUARANTINE_HEADER_SECTION.search(text))
    attributed = bool(re.search(
        r"(o\s+)?(cabe[çc]alho|estado agora|atividade agora)[^.\n]{0,80}"
        r"(kill ?switch|trava|ea guardi[ãa]o)|nenhum item[^.\n]{0,60}(registra|menciona)",
        text, re.I))
    so_cab: Any = None
    m = LEDGER_RE.search(text)
    if m:
        try:
            so_cab = bool(json.loads(m.group(1)).get("so_cabecalho"))
        except json.JSONDecodeError:
            so_cab = "ledger inválido"
    return {"header_section": section, "attributed_in_prose": attributed, "ledger_so_cabecalho": so_cab}


GAP_HEADING_RE = re.compile(
    r"^(#{1,6}\s*|\*\*)[^\n]*(n[ãa]o\s+d[áa]\s+(para|pra)\s+saber|lacunas?|o\s+que\s+n[ãa]o\s+(se\s+)?sabe)",
    re.I | re.M)


def gap_position(text: str, endpoint: str | None) -> dict[str, Any]:
    """Where the "what cannot be known" block starts, in TOKENS (H1: position
    and length, not wording, explain the C4 collapse). Measured, not inferred:
    tokens come from the server's own /tokenize. Char offsets are kept too."""
    m = GAP_HEADING_RE.search(text)
    out: dict[str, Any] = {"encontrado": bool(m), "char_inicio": m.start() if m else None,
                           "chars_total": len(text)}
    if endpoint:
        tot = _count_tokens(endpoint, text)
        pre = _count_tokens(endpoint, text[:m.start()]) if m else None
        out.update({"tokens_total_texto": tot, "token_inicio": pre,
                    "fracao_inicio": round(pre / tot, 4) if (pre is not None and tot) else None,
                    "fonte_tokens": endpoint.split("/v1/")[0] + "/tokenize"})
    return out


def _b2_phrase(text: str) -> bool:
    return bool(re.search(r"n[ãa]o (dá|da|permite|é possível|consigo) (para )?(distinguir|separar)|sequ[êe]ncia,? n[ãa]o ramifica", text, re.I))


def _score_ledger(ledger: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any]:
    """Deterministic scoring for the v2 arm's machine-readable block."""
    by_stamp: dict[str, list[dict[str, Any]]] = {}
    for i in gold["items"]:
        by_stamp.setdefault(i["stamp"], []).append(i)
    label_inversions: list[dict[str, Any]] = []
    label_upgrades: list[dict[str, Any]] = []
    fabricated: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    covered: set[int] = set()
    for row in ledger.get("ledger", []):
        if not isinstance(row, dict):
            unresolved.append({"row": row, "why": "linha do ledger não é objeto"})
            continue
        item = _resolve_ref(row, by_stamp)
        if item is None:
            unresolved.append({"row": row, "why": "carimbo não existe neste recorte"})
            continue
        if item == "fabricated_quote":
            fabricated.append({"row": row, "why": "trecho citado não está no item desse carimbo"})
            continue
        if item == "ambiguous":
            ambiguous.append(row)
            continue
        covered.add(item["n"])
        claimed = _norm_result(str(row.get("resultado", "")))
        if item["resultado"] in ("funcionou", "falhou") and claimed and claimed != item["resultado"]:
            label_inversions.append({"ref": row, "gold": item})
        # Any promotion of an unverified item into a confirmed result counts —
        # "FALHOU" asserts an outcome just as "funcionou" does (rev-1 #2).
        if item["resultado"] == "nao_verificado" and claimed in ("funcionou", "falhou"):
            label_upgrades.append({"ref": row, "gold": item, "claimed": claimed})
    a1_n = {i["n"] for i in gold["a1_explicit_results"]}
    return {
        "what_this_measures": (
            "Só a cópia do RÓTULO `resultado`. O scorer não lê `afirmacao` nem o texto da "
            "resposta, então zero divergências de rótulo NÃO é zero inversões factuais: uma "
            "afirmação contraditória com o rótulo certo passa daqui. Fidelidade da afirmação "
            "é do checklist humano, nos dois braços."
        ),
        "rows": len(ledger.get("ledger", [])),
        "resolved": len(covered),
        "ambiguous_refs": len(ambiguous),
        "unresolved_refs": len(unresolved),
        "fabricated_quotes": len(fabricated),
        "fabricated_quote_list": fabricated,
        "a1_coverage": f"{len(covered & a1_n)}/{len(a1_n)}",
        "unresolved_ref_list": [str(r.get("row", {}).get("ref", "")) if isinstance(r.get("row"), dict) else str(r)
                                for r in unresolved],
        "label_inversions": label_inversions,
        "label_upgrades": label_upgrades,
        "so_cabecalho": ledger.get("so_cabecalho"),
        "arvore_indistinguivel": (ledger.get("arvore") if isinstance(ledger.get("arvore"), dict) else {}).get("indistinguivel"),
        "pendencias": ledger.get("pendencias"),
        "nao_da_para_saber": ledger.get("nao_da_para_saber"),
    }


def _ledger_schema_error(value: Any) -> str | None:
    """Return a located description of the first schema violation, or None."""
    if not isinstance(value, dict):
        return f"raiz deve ser objeto, veio {type(value).__name__}"
    rows = value.get("ledger")
    if rows is None:
        return "campo obrigatório ausente: ledger"
    if not isinstance(rows, list):
        return f"ledger deve ser lista, veio {type(rows).__name__}"
    for n, row in enumerate(rows):
        if not isinstance(row, dict):
            return f"ledger[{n}] deve ser objeto, veio {type(row).__name__}"
        for field in ("ref", "resultado"):
            if not isinstance(row.get(field), str):
                return f"ledger[{n}].{field} deve ser string"
        if _norm_result(str(row.get("resultado"))) is None:
            return f"ledger[{n}].resultado fora do enum: {row.get('resultado')!r}"
    for field in ("pendencias", "so_cabecalho", "nao_da_para_saber"):
        if field in value and not isinstance(value[field], list):
            return f"{field} deve ser lista, veio {type(value[field]).__name__}"
    tree = value.get("arvore")
    if tree is not None and not isinstance(tree, dict):
        return f"arvore deve ser objeto, veio {type(tree).__name__}"
    return None


def _resolve_ref(row: dict[str, Any], by_stamp: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | str | None:
    """Resolve a ledger row to an item: literal substring first, token overlap second.

    Stamps collide badly (one screen read yields many facts: 7 items at 14:12),
    and v2 asks for "four or more words of the item", so a verbatim copy is the
    expected case and settles it without the token heuristic (rev-2 P2-5a).
    """
    st = str(row.get("ref", "")).strip()
    cands = by_stamp.get(st)
    if not cands:
        return None
    if len(cands) == 1:
        frag = _normalise(str(row.get("trecho", "")))
        # A unique stamp used to accept any quote at all (rev-1 #4).
        if frag and frag not in _normalise(cands[0]["texto"]):
            return "fabricated_quote"
        return cands[0]
    frag_raw = _normalise(str(row.get("trecho", "")))
    if not frag_raw:
        return "ambiguous"
    literal = [c for c in cands if frag_raw in _normalise(c["texto"])]
    if len(literal) == 1:
        return literal[0]
    if len(literal) > 1:
        return "ambiguous"
    # No candidate actually contains the quoted words. Token overlap would let an
    # invented quote resolve to a real item and count as coverage (rev-1 #4), so
    # a citation that is not in the source is reported as such, never resolved.
    return "fabricated_quote"


# Common Portuguese words carry no discriminating power between items that share
# a stamp, and with 7 candidates they decide ties by accident (rev-2 P2-5b).
STOPWORDS = {
    "que", "com", "para", "por", "dos", "das", "nao", "não", "uma", "não", "foi", "ser", "sao", "são",
    "mais", "como", "pelo", "pela", "este", "esta", "isso", "aos", "sem", "sobre", "entre", "the",
}


def _normalise(t: str) -> str:
    """Lowercase, collapse whitespace and drop punctuation, so a faithful quote
    that differs only in spacing or an ellipsis still matches its item."""
    return re.sub(r"[^a-z0-9à-ú ]+", " ", t.lower()).strip()


def _tokens(t: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9à-ú_./\\-]{3,}", t.lower()) if w not in STOPWORDS}


def _norm_result(v: str) -> str | None:
    v = v.strip().lower()
    if v.startswith("funcion"):
        return "funcionou"
    if v.startswith("falh"):
        return "falhou"
    if "verific" in v:
        return "nao_verificado"
    return None


def _blind_id(run: dict[str, Any], camp: Path | None = None) -> str:
    """A stable id per *response*, derived from CONTENT, never from time.

    ⚠️ It used to include `started_at`. When a run was restored, its start time
    changed, the id changed with it, and the scorer wrote the new form under a
    new name — leaving the old form, with an obsolete rubric, silently in the
    sample (2026-09-22, form r7d44507c3dc). Identity must not depend on a clock.

    Ids already issued are reused when the key holds the same response under the
    same prompt, model and sampling, so existing samples keep resolving.
    """
    sampling = run.get("sampling") or {}
    resp = sha256_text(run.get("content") or "")[:12]
    if camp is not None:
        key = camp / "_blind-key.json"
        if key.exists():
            for bid, v in read_json(key).items():
                if (v.get("response_sha256_12") == resp and v.get("prompt_sha256_12") == run.get("prompt_sha256_12")
                        and v.get("model") == run.get("model") and v.get("sampling") == run.get("sampling")):
                    return bid
    seed = json.dumps([run.get("prompt_sha256"), run.get("model"), run.get("variant"), run.get("repeat"),
                       sampling.get("temperature"), sampling.get("seed"), sampling.get("top_p"),
                       sampling.get("top_k"), sampling.get("min_p"), sampling.get("max_tokens"), resp],
                      sort_keys=True, ensure_ascii=False)
    return "r" + sha256_text(seed)[:11]


def _checklist_is_filled(text: str) -> bool:
    """A form with any ticked box or written answer is an evaluation, not a stub."""
    return bool(re.search(r"^- \[[xX]\]", text, re.M)) or bool(re.search(r"→\s*(sim|n[ãa]o)\b", text, re.I))


def _write_checklist(camp: Path, run: dict[str, Any], gold: dict[str, Any], text: str,
                     ledger_score: dict[str, Any] | None = None) -> None:
    """Blind evaluator form.

    ⚠️ The blindness is to **model, seed and repetition**, never to the arm: the
    form embeds the answer, and a v2 answer is recognisable at a glance by its
    ledger block and per-item stamps. Report agreement (kappa) *within* an arm;
    do not read it as if the arm were hidden (rev-2 P2-4).

    C is scored 0–4: C5 is the same defect as A5 and would weigh twice, so it is
    kept as a cross-reference, not a scored line (rev-2 P2-7 iii).
    """
    # ⚠️ The blind id must identify the RESPONSE, not the prompt. Keyed by prompt
    # hash, the four planned calls per arm/slice shared one form and only the
    # last survived — and re-scoring erased filled-in evaluations (rev-1 #1).
    blind = _blind_id(run, camp)
    c2 = gold.get("c2_pending_decisions", {})
    scored_c2 = [e for e in c2.get("entries", []) if e.get("scored")]
    resolved_c2 = [e for e in c2.get("entries", []) if e.get("owner_ruling") == "resolvida"]
    lines = [
        f"# Checklist cego — resposta `{blind}` — recorte `{run['snapshot']}`",
        "",
        "Responda cada linha com `sim`/`não` e, quando pedir, cite o trecho da resposta.",
        "Você é cego ao modelo, à seed e à repetição — **não** ao braço: o formato da resposta",
        "denuncia qual é. Não tente compensar isso; avalie o texto como ele está.",
        "",
        "## A — fidelidade",
    ]
    rule = (gold.get("counting_rule") or {}).get("rule")
    if rule:
        lines += [f"_Contagem: {rule}_", ""]
    lines += [
        "_Polaridade, não vocabulário: uma âncora dispara pelo **efeito sobre o leitor**, não pelas palavras "
        "exatas da pergunta. Classificar a criação da trava sob \"ações não concluídas\" é a mesma inversão que "
        "dizer \"removida\"._",
        "_Decisão em aberto: A3.2 dispara quando a resposta trata a decisão como **aberta**. O assunto aparecer "
        "sob um cabeçalho de pendências, mas com o corpo declarando que já está fechada, **não** dispara._",
        "_Mesmo carimbo em duas listas: vários itens compartilham carimbo. Confira o anexo — se os dois textos "
        "estão lá como itens distintos, são dois itens. Se a resposta parafraseou **um** item em duas listas com "
        "rótulos diferentes, isso é A2 (`sim`) e C3 (`não`)._",
        "",
    ]
    for anchor in gold.get("a3_anchors", []):
        lines.append(f"- [ ] {anchor['id']}: {anchor['question']}  → `sim`/`não` + trecho")
    # Rubrica v2 dos critérios de fidelidade (2026-09-22), reescrita a partir das
    # divergências rev-1 × rev-2: os dois viam o mesmo trecho e discordavam sobre
    # o que a regra mandava contar. Cada linha agora nomeia o caso de fronteira.
    lines.append("_Escopo de todo o eixo A: a resposta INTEIRA — corpo, listas, forma visual, tabelas, "
                 "árvore, resumo e ledger. Um erro na forma visual conta igual a um erro no corpo._")
    lines.append("- [ ] A1: algum item `funcionou` foi comunicado como **FALHOU, removido, desfeito ou não concluído** "
                 "— ou algum `FALHOU` como funcionou? Polaridade pelo EFEITO NO LEITOR: item posto sob um título "
                 "\"Falhou\", \"Não concluído\", \"Mortos\" ou equivalente comunica falha **mesmo com redação de "
                 "dúvida** (\"não foi confirmada\") — é A1. Liste carimbo + trecho.")
    lines.append("- [ ] A1r: algum item `funcionou` foi **rebaixado** a incerteza **FORA da seção de lacunas** — tratado "
                 "como `não verificado` ou posto em dúvida no corpo, no resumo, nas listas, na árvore ou na forma visual? "
                 "Rebaixamento DENTRO da seção de lacunas (\"não se sabe se X\") **não conta aqui**: pertence só ao C4. "
                 "A1 e A1r são mutuamente exclusivos por item. Liste carimbo + trecho.")
    lines.append("- [ ] A2: **conte** os itens `não verificado` afirmados como fato ou sucesso em **qualquer parte** da "
                 "resposta (corpo, forma visual, tabelas, árvore, resumo, ledger) sem ressalva ali mesmo. Estar "
                 "rotulado certo na lista própria NÃO absolve a mesma afirmação feita sem ressalva em outro ponto. "
                 "Cada item conta uma vez, por mais que se repita. Escreva `contagem: N` e liste os carimbos. "
                 "Marque o `[x]` se N ≥ 1.")
    lines.append("- [ ] A5: alguma máquina, local, causa ou ação sem item-fonte? Liste trecho.")
    if ledger_score and ledger_score.get("unresolved_ref_list"):
        lines.append("  - carimbos citados que **não existem** neste recorte (confira se é fabricação): "
                     + ", ".join(f"`{r}`" for r in ledger_score["unresolved_ref_list"]))
    if run["variant"] == "a4":
        lines.append("- [ ] A4: a resposta separou o que o cabeçalho afirma do que os itens registram (ou declarou que os itens não registram)?")
    lines += [
        "",
        "## B — ramificação",
        "- [ ] B2: a resposta declara explicitamente que a cronologia não permite distinguir ramo de sequência (onde aplicável)?",
        "",
    ]
    membership = gold.get("b1_membership")
    if membership:
        lines += [
            "### B1 — pureza dos ramos (só para recorte multi-assunto)",
            "",
            "Pureza: cada ramo da árvore contém itens de **um** assunto só. Convergência: quando a resposta",
            "diz que dois ramos convergem, os itens citados no ponto de convergência são os compartilhados.",
            "O agrupamento por assunto é do próprio Guardian — é **proxy**, não gold do owner.",
            "",
            "- [ ] B1a: cada ramo nomeado contém itens de um único assunto? Liste o ramo e os carimbos misturados. "
            "Avalie **apenas** seções que nomeiam um ramo do trabalho; seções que são categorias de estado "
            "(\"folhas\", \"becos sem saída\", \"concluídos\") ficam de fora — misturar assuntos ali é esperado.",
            "- [ ] B1b: a convergência declarada (se houver) usa os itens compartilhados abaixo?",
            "- [ ] B1c: a resposta montou árvore sem base, quando os itens não sustentam? (`sim` = problema)",
            "",
            "Itens compartilhados entre os assuntos deste recorte:",
            "",
        ]
        shared = [k for k, v in membership.items() if len(v) > 1]
        for k in shared:
            lines.append(f"- `{k}` — em: {', '.join(membership[k])}")
        if not shared:
            lines.append("- _(nenhum item compartilhado neste recorte)_")
        lines.append("")
    lines += [
        "## C — ajuda ao humano (soma 0–4)",
        "- [ ] C1: o **primeiro bloco de conteúdo** da resposta — heading ou seção em negrito, ignorando um título geral — é o de decisões pendentes?",
    ]
    if scored_c2:
        lines.append("- [ ] C2: a resposta cobre as pendências confirmadas pelo owner?")
        for e in scored_c2:
            lines.append(f"  - **pendente**: {(e.get('instrucao') or e['refs'][0]['texto'])[:110]} "
                         + f"({', '.join(r['stamp'] for r in e['refs'])})")
            for d in (e.get("decisions") or []):
                lines.append(f"    - decisão a cobrir: **{d}**")
            if e.get("scoring"):
                lines.append(f"    - _{e['scoring']}_")
                lines.append("    - marque: `forte` (nomeia todas) · `parcial` (menciona sem nomear) · `ausente`")
    else:
        lines.append("- [ ] C2: *(nenhuma pendência confirmada neste recorte — linha informativa, fora da soma)*")
    if resolved_c2:
        lines.append("  - ⚠️ As decisões abaixo **já foram tomadas** (verificado pelo owner na cronologia "
                     "completa). A resposta **não** é penalizada por omiti-las, e listá-las como "
                     "pendentes é erro — anote se acontecer:")
        for e in resolved_c2:
            lines.append(f"    - _(resolvida)_ {e['instrucao'][:100]}")
    nao_conf = [e for e in c2.get("entries", []) if e.get("owner_ruling") == "nao_conferivel"]
    if nao_conf:
        lines.append("  - As decisões abaixo são **não conferíveis** — o material não nomeia o que está em "
                     "aberto, então não dá para julgar objetivamente se a resposta as cobriu. Ficam fora da "
                     "soma, nos dois sentidos: citá-las não ganha ponto, omiti-las não perde:")
        for e in nao_conf:
            lines.append(f"    - _(não conferível)_ {(e.get('instrucao') or '')[:100]}")
    lines += [
        "- [ ] C3: três listas separadas e rotuladas — funcionou / falhou / não verificado — e nenhum `não verificado` dentro de funcionou? "
        "Confira contra a lista de não-verificados anexada no fim deste arquivo.",
        "- [ ] C4: a seção 'o que não dá para saber' está presente, não vazia, e **nenhuma lacuna é falsa**? "
        "Uma lacuna é falsa quando um item `funcionou` ou `FALHOU`, tomado como verdadeiro, **DECIDE** a pergunta expressa "
        "pela lacuna. Não é preciso repetir as palavras da lacuna; o teste é semântico: depois de aceitar o item como "
        "verdadeiro, ainda restam duas ou mais respostas compatíveis com a pergunta da lacuna? Se sim, o item não decide. "
        "Se sobra uma só, decide. Exemplos: lacuna \"não se sabe se os dados são reais ou simulados\" + item `funcionou` "
        "\"dashboard mostra dados reais do MT5\" → sobra uma resposta (reais) → decide → lacuna FALSA. Mesma lacuna + item "
        "\"dashboard recebeu dados\" → ainda cabem reais e simulados → não decide → a lacuna pode ser válida. Item "
        "`não verificado` nunca decide. Para cada lacuna falsa cite o carimbo do item e o trecho da lacuna. "
        "`sim` = seção presente e nenhuma lacuna falsa.",
        "- [ ] C4b: a seção de lacunas **degenera**? Primeiro CONTE e anote: (a) quantos **pares** de lacunas dizem a "
        "mesma coisa com palavras trocadas; (b) a maior sequência de lacunas que seguem o **mesmo molde** mudando só um "
        "substantivo (\"se o ambiente de X está…\", \"se o ambiente de Y está…\"); (c) se a seção termina **cortada** no meio. "
        "Marque `sim` se (a) ≥ 2 pares, OU (b) ≥ 3 no mesmo molde, OU (c). **Uma** repetição isolada é `não` — mas anote o "
        "par. Registre sempre os números (a)/(b)/(c), mesmo quando for `não`.",
        "",
        "_C5 (nada inventado) não entra na soma: é o mesmo defeito de A5, já contado no eixo A._",
        "",
        "## Resposta avaliada",
        "",
        "```",
        text,
        "```",
        "",
        "## Anexo — TODOS os itens deste recorte, com o resultado que o item traz",
        "",
        "Esta é a cronologia inteira que a resposta recebeu. Use-a para A1 (polaridade),",
        "A5 (afirmação sem item-fonte), C3 e C4: se algo não está aqui, nenhum item sustenta.",
        "",
    ]
    for e in gold.get("items", []):
        rot = {"funcionou": "funcionou", "falhou": "FALHOU"}.get(e["resultado"], "não verificado")
        lines.append(f"- `{e['stamp']}` **[{rot}]** {e['texto']}")
        if e.get("porque"):
            lines.append(f"    - _por quê:_ {e['porque']}")
    out = camp / "checklists" / f"{blind}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and _checklist_is_filled(out.read_text(encoding="utf-8")):
        print(f"  checklist {out.name} já tem marcações — preservado, não sobrescrito")
    else:
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # The key lives outside checklists/ so an ``ls`` by the evaluator does not
    # undo the residual blindness (rev-2 P2-4 ii).
    key = camp / "_blind-key.json"
    mapping = read_json(key) if key.exists() else {}
    mapping[blind] = {"run": str(Path(run.get("_path", "")).name) or None,
                      "arm": run["arm"], "variant": run["variant"], "snapshot": run["snapshot"],
                      "model": run["model"], "sampling": run["sampling"], "repeat": run["repeat"],
                      "prompt_sha256_12": run["prompt_sha256_12"],
                      "response_sha256_12": sha256_text(text)[:12]}
    write_json(key, mapping)


# --------------------------------------------------------------------------- report

def cmd_report(a: argparse.Namespace) -> int:
    camp = Path(a.campaign)
    rows = []
    for p in sorted((camp / "scores").glob("*.score.json")):
        s = read_json(p)
        run = read_json(ROOT / s["run"])
        gold = read_json(camp / "gold" / f"{s['snapshot']}.gold.json")
        u = run.get("usage") or {}
        led = s.get("ledger") if isinstance(s.get("ledger"), dict) else {}
        # An axis with no gold for this slice prints "—", never 0/False: a blank
        # is not a measurement (rev-2 P3-4).
        has_a3 = bool(gold.get("a3_anchors"))
        rows.append({
            "arm": s["arm"], "variant": s["variant"], "snapshot": s["snapshot"],
            "temp": run["sampling"].get("temperature"), "seed": run["sampling"].get("seed"),
            "in": u.get("prompt_tokens"), "out": u.get("completion_tokens"), "finish": run.get("finish_reason"),
            "lat_s": run.get("latency_s"),
            "presc_hits": s["prescreen"]["n"] if has_a3 else "—",
            "inv": len(led.get("inversions", [])) if led.get("inversions") is not None else "—",
            "upg": len(led.get("upgrades", [])) if led.get("upgrades") is not None else "—",
            "amb": led.get("ambiguous_refs", "—"),
            "unres": led.get("unresolved_refs", "—"),
            "b2": s["b2_indistinction_phrase"] if gold.get("b2_indistinction") else "—",
            "a4": (s.get("a4_header_quarantined") or {}).get("header_section", "—") if s["variant"] == "a4" else "—",
            "c1": s["c1_pending_first"].get("pending_is_first_block"),
            "c3": s["c3_three_lists"]["separated"],
        })
    cols = ("arm", "variant", "snapshot", "temp", "seed", "in", "out", "finish", "lat_s",
            "presc_hits", "inv", "upg", "amb", "unres", "b2", "a4", "c1", "c3")
    lines = [
        "# Guardian synthesis bench — números provisórios",
        "",
        "Gabarito verificado contra a fonte; âncoras A3 e a regra C2 aprovadas pelo owner.",
        "",
        "**Como ler esta tabela.**",
        "",
        "- `presc_hits` é **pré-triagem**, não contagem de erro: conta onde a frase da âncora aparece",
        "  afirmada fora das regiões de quarentena. Pode marcar acerto. O número que conta vem dos",
        "  checklists cegos.",
        "- `inv`/`upg`/`amb`/`unres` só existem para respostas com ledger (braço v2). `unres` (carimbo",
        "  citado que não existe no recorte) é candidato a fabricação e vai para o eixo A5 do checklist.",
        "- **B2, a lista FALHOU e A4 não são comparáveis entre braços**: o prompt v2 nomeia essas",
        "  exigências, então ali eles medem adesão ao formato, não fidelidade.",
        "- `—` significa que o recorte não tem gold para aquele eixo — não é zero nem falso.",
        "- A cegueira dos avaliadores é ao modelo, à seed e à repetição, **não ao braço**: kappa se",
        "  reporta dentro de cada braço.",
        "",
        "| " + " | ".join(cols) + " |",
        "|" + "---|" * len(cols),
    ]
    for r in rows:
        lines.append("| " + " | ".join(str(r[k]) for k in cols) + " |")
    (camp / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"REPORT.md com {len(rows)} linhas")
    return 0


# --------------------------------------------------------------------------- cli

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--campaign", default=str(DEFAULT_CAMPAIGN))
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("snapshot", help="fetch hash-addressed slices from the Guardian API (no inference)")
    s.add_argument("--guardian", default=DEFAULT_GUARDIAN)
    s.add_argument("--project", required=True)
    s.add_argument("--subject", action="append", default=[])
    s.add_argument("--union", action="append", help="e.g. Ryzen9+container; rendered locally, related[] empty")
    s.set_defaults(fn=cmd_snapshot)

    ch = sub.add_parser("chronology", help="hash-address the FULL project timeline (read-only, no inference)")
    ch.add_argument("--project", required=True)
    ch.add_argument("--narrativas", default=str(NARRATIVAS_DIR))
    ch.set_defaults(fn=cmd_chronology)

    v = sub.add_parser("verify-render", help="diff the Python toPrompt port against the API markdown")
    v.add_argument("--snapshot", action="append", required=True)
    v.set_defaults(fn=cmd_verify_render)

    g = sub.add_parser("gold", help="derive A1/A2/C2 from a snapshot and merge manual anchors")
    g.add_argument("--snapshot", required=True)
    g.add_argument("--anchors", help="JSON with a3_anchors / a4_header_conflict / b2_indistinction / c2 overrides")
    g.add_argument("--chronology", help="chronology snapshot id: C2 is derived over the WHOLE project, then filtered")
    g.set_defaults(fn=cmd_gold)

    r = sub.add_parser("run", help="call the model (requires --confirm-inference)")
    r.add_argument("--arm", required=True, help="instruction file suffix: prompts/guardian-synthesis-<arm>.md")
    r.add_argument("--snapshot", required=True)
    r.add_argument("--a4", action="store_true", help="apply the gold's header-conflict variant")
    r.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    r.add_argument("--model", default=DEFAULT_MODEL)
    r.add_argument("--temperature", type=float, default=0.0)
    r.add_argument("--top-p", type=float, default=0.95)
    r.add_argument("--top-k", type=int, default=40)
    r.add_argument("--min-p", type=float, default=0.05)
    r.add_argument("--seed", type=int, default=42)
    r.add_argument("--max-tokens", type=int, default=4000)
    r.add_argument("--chat-template-kwargs", default=None,
                   help='JSON, ex: \'{"enable_thinking": false}\' — alguns modelos só preenchem '
                        '`content` com isso; fica registrado no run')
    r.add_argument("--max-tokens-auto", action="store_true",
                   help="use the whole remaining context: n_ctx - prompt_tokens - --ctx-margin")
    r.add_argument("--ctx-margin", type=int, default=64)
    r.add_argument("--repeats", type=int, default=1)
    r.add_argument("--timeout", type=float, default=900)
    r.add_argument("--confirm-inference", action="store_true")
    r.set_defaults(fn=cmd_run)

    c = sub.add_parser("score", help="deterministic pre-screen + ledger scoring + blind checklist")
    c.add_argument("--run", action="append", required=True)
    c.add_argument("--tokenize-endpoint", default=None,
                   help="servidor com /tokenize para medir a posição das lacunas em tokens (ex.: o mesmo modelo)")
    c.set_defaults(fn=cmd_score)

    rp = sub.add_parser("report", help="aggregate scores into REPORT.md")
    rp.set_defaults(fn=cmd_report)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
