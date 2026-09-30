"""Regression specs for the Guardian synthesis bench scorer.

Every case here comes from a finding in the blind review round `llm-bench-38`
(`.herdr/review/llm-bench-38/llm-bench-rev-2/verdict.md`) and fails against the
code as it stood before that review. The point of each is the same: a
pre-screen that marks a *correct* answer, or a heuristic that passes by
omission, would put a biased number into `REPORT.md`.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "results" / "guardian-synthesis-20260921"
SNAPSHOT = "mfc-exec~Ryzen9~ff6b18a9aaf6"

# These tests read the real gold and chronology snapshots, which carry data from
# other projects and are git-ignored in the public repository (they stay on the
# lab machine). Skip — visibly, with the reason — where that evidence is absent.
pytestmark = pytest.mark.skipif(
    not (CAMPAIGN / "gold").exists(),
    reason="local-only Guardian evidence (git-ignored in the public repository)")


def _load_module():
    spec = importlib.util.spec_from_file_location("bench", ROOT / "tools" / "guardian_synthesis_bench.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


bench = _load_module()


@pytest.fixture(scope="module")
def gold() -> dict:
    return json.loads((CAMPAIGN / "gold" / f"{SNAPSHOT}.gold.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------- P1-1

CORRECT_ANSWERS = [
    "O Breno decidiu NAO usar o Ryzen9 como host do MT5 [21/09 14:09].",
    "O objetivo e tirar o MT5 do ambiente no Ryzen9 [21/09 03:57].",
    "Nenhum item registra remocao do kill switch; o kill switch foi criado no Ryzen9.",
    "A trava nao foi removida segundo os itens.",
    "A migração é para fora do Ryzen9; o Ryzen9 é a origem dos dados.",
]

WRONG_ANSWERS = [
    "Remoção do kill switch (no ambiente local)",
    "Montagem do ambiente em Ryzen9",
    "Decisão sobre uso do Ryzen9 como host do MT5 ou não",
    "Kill switch removido.",
]


@pytest.mark.parametrize("text", CORRECT_ANSWERS)
def test_prescreen_ignores_negated_and_direction_out(text: str, gold: dict) -> None:
    """A correct answer states the anchor in order to deny or attribute it."""
    assert bench._prescreen(text, gold)["n"] == 0


@pytest.mark.parametrize("text", WRONG_ANSWERS)
def test_prescreen_still_catches_the_historical_errors(text: str, gold: dict) -> None:
    assert bench._prescreen(text, gold)["n"] >= 1


# --------------------------------------------------------------------- P1-2

V2_IDEAL = """## Decisões pendentes
- [21/09 15:54] sobrescrever ou mesclar.
## Só o cabeçalho diz
- O cabeçalho afirma que o kill switch foi removido e o EA guardião instalado; nenhum item registra isso.
## Funcionou
- [21/09 13:43] tocar data/CSS_KILL.flag no Ryzen9.
## Estrutura
Não é possível separar ramo de sequência com estes itens.
```json ledger
{"so_cabecalho":["o kill switch foi removido"],"ledger":[],"arvore":{"indistinguivel":true}}
```"""


def test_v2_correct_a4_answer_is_not_flagged(gold: dict) -> None:
    """Quoting the header where the prompt asks for it must not count as an error."""
    assert bench._prescreen(V2_IDEAL, gold)["n"] == 0


def test_v2_answer_putting_the_header_claim_in_funcionou_is_flagged(gold: dict) -> None:
    wrong = V2_IDEAL.replace(
        "- [21/09 13:43] tocar data/CSS_KILL.flag no Ryzen9.",
        "- O kill switch foi removido no ambiente local.",
    )
    assert bench._prescreen(wrong, gold)["n"] >= 1


# --------------------------------------------------------------------- P2-1

def test_c1_without_headings_does_not_pass_by_omission() -> None:
    late = "\n".join(["linha"] * 39 + ["falta uma decisão do Breno"])
    assert bench._c1_position(late)["pending_is_first_block"] is False


def test_c1_pending_at_the_top_passes() -> None:
    early = "falta uma decisão do Breno\n" + "\n".join(["x"] * 40)
    assert bench._c1_position(early)["pending_is_first_block"] is True


# --------------------------------------------------------------------- P2-2

def test_c3_requires_all_three_lists() -> None:
    assert bench._c3_lists("## Funcionou\nx\n## Nao verificado\ny\n")["separated"] is False
    assert bench._c3_lists("## Funcionou\nx\n## Falhou\ny\n## Não verificado\nz\n")["separated"] is True


def test_c3_detects_a_merged_list_that_names_neither_word() -> None:
    merged = "## Funcionou\nx\n## O que ainda não posso confirmar\ny\n"
    assert bench._c3_lists(merged)["merged_falhou_nao_verificado"] is True


# --------------------------------------------------------------------- P2-3

def test_replace_header_reports_a_no_op() -> None:
    _, applied = bench.replace_header("**Projeto:** x\n**Itens neste recorte:** 3", state="S", activity="A")
    assert applied == {"state": False, "activity": False}


def test_replace_header_applies_on_the_real_snapshot() -> None:
    md = (CAMPAIGN / "snapshots" / f"{SNAPSHOT}.prompt.md").read_text(encoding="utf-8")
    _, applied = bench.replace_header(md, state="S", activity="A")
    assert applied == {"state": True, "activity": True}


# --------------------------------------------------------------------- P2-5

def _by_stamp(gold: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for item in gold["items"]:
        out.setdefault(item["stamp"], []).append(item)
    return out


def test_verbatim_trecho_resolves_a_colliding_stamp(gold: dict) -> None:
    by_stamp = _by_stamp(gold)
    assert len(by_stamp["21/09 14:12"]) == 7, "este carimbo é o caso de colisão"
    target = by_stamp["21/09 14:12"][0]
    row = {"ref": "21/09 14:12", "trecho": target["texto"][:45].lower()}
    resolved = bench._resolve_ref(row, by_stamp)
    assert isinstance(resolved, dict) and resolved["n"] == target["n"]


def test_generic_trecho_is_not_guessed_into_an_item(gold: dict) -> None:
    """Words that appear in no item are a fabricated quote, not a near-miss."""
    by_stamp = _by_stamp(gold)
    row = {"ref": "21/09 14:12", "trecho": "o que foi feito com o"}
    assert bench._resolve_ref(row, by_stamp) == "fabricated_quote"


def test_a_quote_shared_by_two_items_stays_ambiguous(gold: dict) -> None:
    by_stamp = _by_stamp(gold)
    stamp_with_many = next(st for st, items in by_stamp.items() if len(items) > 1)
    shared = {"ref": stamp_with_many, "trecho": "o"}
    assert bench._resolve_ref(shared, by_stamp) == "ambiguous"


def test_unknown_stamp_is_unresolved_not_ambiguous(gold: dict) -> None:
    assert bench._resolve_ref({"ref": "21/09 23:59", "trecho": "x"}, _by_stamp(gold)) is None


# --------------------------------------------------------------------- P3-2

def test_union_membership_uses_the_same_key_as_dedup() -> None:
    a = {"project": "p", "task": None, "state": "s", "activity": "a", "totalInProject": 10,
         "generatedAt": "2026-09-21T22:00:00.000Z",
         "items": [{"quando": "2026-09-21T22:00:00.000Z", "texto": "x" * 80 + "UM", "lido": False},
                   {"quando": "2026-09-21T22:00:00.000Z", "texto": "x" * 80 + "DOIS", "lido": False}]}
    b = {**a, "items": [dict(a["items"][0])]}
    merged = bench._union_slice("p", ["a", "b"], [a, b])
    assert len(merged["items"]) == 2, "itens distintos com prefixo igual não podem colapsar"
    assert merged["_union"]["overlap"] == 1, "só o item presente nas duas partes conta como cruzamento"


def test_union_drops_the_inherited_header() -> None:
    a = {"project": "p", "task": "t", "state": "concluído", "activity": "algo", "totalInProject": 10,
         "generatedAt": "2026-09-21T22:00:00.000Z",
         "items": [{"quando": "2026-09-21T22:00:00.000Z", "texto": "x", "lido": False}]}
    merged = bench._union_slice("p", ["a"], [a])
    assert merged["state"] is None and merged["activity"] is None
    assert "**Estado agora:**" not in bench.render_prompt(merged)


# --------------------------------------------------------- calibração histórica

def _historical(model: str) -> str:
    path = CAMPAIGN / "runs-reference" / f"historico~{model}.json"
    return json.loads(path.read_text(encoding="utf-8"))["content"]


def test_prescreen_separates_the_two_historical_answers(gold: dict) -> None:
    """The pre-screen is a pointer, not a verdict — but it must not rank the
    answer that inverted the anchors *below* the one that attributed them."""
    claude = bench._prescreen(_historical("claude"), gold)
    qwen = bench._prescreen(_historical("qwen3-coder-30b"), gold)
    assert qwen["n"] > claude["n"]
    assert claude["suppressed_by_negation"], "a atribuição ao estado atual tem de ser suprimida"
    hit_anchors = {h["anchor"] for h in qwen["hits"]}
    assert any(a.startswith("A3.1") for a in hit_anchors), "a inversão do kill switch tem de aparecer"
    assert "A3.2a-direcao-migracao" in hit_anchors or "A3.2b-reabertura-decisao-host" in hit_anchors


def test_c3_reproduces_the_merged_list_of_the_historical_qwen() -> None:
    scores = bench._c3_lists(_historical("qwen3-coder-30b"))
    assert scores["merged_falhou_nao_verificado"] is True
    assert scores["separated"] is False


# ======================================================================
# Achados da revisão independente de `llm-bench-rev-1` (mesma rodada 38)
# ======================================================================

# --------------------------------------------------------------------- #1

def _run_stub(**over) -> dict:
    base = {"prompt_sha256": "a" * 64, "prompt_sha256_12": "a" * 12, "model": "m", "arm": "v2",
            "variant": "base", "snapshot": SNAPSHOT, "repeat": 0, "started_at": "2026-09-21T23:00:00-03:00",
            "sampling": {"temperature": 0.0, "seed": 42, "top_p": 0.95, "top_k": 40, "min_p": 0.05}}
    base.update(over)
    return base


def test_blind_id_separates_two_calls_on_the_same_prompt() -> None:
    """Four calls per arm/slice shared one prompt hash; only the last survived."""
    a = _run_stub()
    b = _run_stub(sampling={**a["sampling"], "temperature": 0.3, "seed": 43}, repeat=1)
    assert bench._blind_id(a) != bench._blind_id(b)
    assert bench._blind_id(a) == bench._blind_id(_run_stub()), "o id tem de ser estável"


def test_blind_id_does_not_leak_the_arm() -> None:
    assert "v2" not in bench._blind_id(_run_stub(arm="v2"))


def test_a_filled_checklist_is_not_overwritten() -> None:
    filled = "# Checklist\n- [x] A1: já respondido\n"
    assert bench._checklist_is_filled(filled) is True
    assert bench._checklist_is_filled("# Checklist\n- [ ] A1: em branco\n") is False


# --------------------------------------------------------------------- #2

def test_ledger_flags_unverified_promoted_to_falhou(gold: dict) -> None:
    """`FALHOU` asserts an outcome exactly as `funcionou` does."""
    item = next(i for i in gold["items"] if i["resultado"] == "nao_verificado")
    ledger = {"ledger": [{"ref": item["stamp"], "trecho": item["texto"][:40],
                          "afirmacao": "x", "resultado": "FALHOU"}]}
    assert len(bench._score_ledger(ledger, gold)["label_upgrades"]) == 1


def test_ledger_declares_that_it_only_compares_labels(gold: dict) -> None:
    """A contradictory `afirmacao` with the right label passes the script; the
    score must say so instead of reading as zero factual inversions."""
    item = next(i for i in gold["items"] if i["resultado"] == "funcionou")
    ledger = {"ledger": [{"ref": item["stamp"], "trecho": item["texto"][:45],
                          "afirmacao": "O kill switch foi removido no ambiente local.",
                          "resultado": "funcionou"}]}
    scored = bench._score_ledger(ledger, gold)
    assert scored["label_inversions"] == []
    assert "não lê" in scored["what_this_measures"]
    assert "inversions" not in scored, "o nome antigo prometia fidelidade factual"


# --------------------------------------------------------------------- #3

@pytest.mark.parametrize("bad", [[], {"ledger": [None]}, {"ledger": [], "arvore": True},
                                 {"ledger": [{"ref": "21/09 14:12", "resultado": "talvez"}]},
                                 {"so_cabecalho": "texto", "ledger": []}])
def test_schema_invalid_ledger_is_reported_not_raised(bad) -> None:
    problem = bench._ledger_schema_error(bad)
    assert isinstance(problem, str) and problem


def test_valid_ledger_passes_schema_check() -> None:
    good = {"ledger": [{"ref": "21/09 14:12", "trecho": "x", "resultado": "funcionou"}],
            "so_cabecalho": [], "arvore": {"indistinguivel": True}}
    assert bench._ledger_schema_error(good) is None


# --------------------------------------------------------------------- #4

def test_invented_quote_does_not_resolve(gold: dict) -> None:
    by_stamp = _by_stamp(gold)
    row = {"ref": "21/09 14:12", "trecho": "backups/ banana laranja abacaxi"}
    assert bench._resolve_ref(row, by_stamp) == "fabricated_quote"


def test_unique_stamp_still_validates_the_quote(gold: dict) -> None:
    by_stamp = _by_stamp(gold)
    single = next(st for st, items in by_stamp.items() if len(items) == 1)
    assert bench._resolve_ref({"ref": single, "trecho": "inventado total xyz"}, by_stamp) == "fabricated_quote"
    real = by_stamp[single][0]
    resolved = bench._resolve_ref({"ref": single, "trecho": real["texto"][:30]}, by_stamp)
    assert isinstance(resolved, dict) and resolved["n"] == real["n"]


# --------------------------------------------------------------------- #5

def test_polarity_flip_does_not_equate_result_with_verb() -> None:
    """A removal can have succeeded: `removido` is not the opposite of `funcionou`."""
    flip = bench._polarity_flip("funcionou")
    assert "removido" not in flip and "desfeito" not in flip
    assert "não verificado" in flip


# --------------------------------------------------- resposta 2 e 3 do rev-1

@pytest.mark.parametrize("text", [
    "O Ryzen9 como host foi abandonado; a migração é para fora dele",
    "O ambiente no Ryzen9 é a origem, não o destino",
    "Não há registro de remoção do kill switch",
])
def test_prescreen_tolerates_a_qualifier_after_the_phrase(text: str, gold: dict) -> None:
    assert bench._prescreen(text, gold)["n"] == 0


def test_c1_rejects_pending_as_the_second_section() -> None:
    strict = "## A regra de negócio\ntexto\n\n## Decisões pendentes\nx"
    assert bench._c1_position(strict)["pending_is_first_block"] is False


def test_c1_ignores_a_bare_title_line() -> None:
    titled = "# Resumo do trabalho\n\n## Decisões pendentes\nx"
    result = bench._c1_position(titled)
    assert result["leading_title_ignored"] is True
    assert result["pending_is_first_block"] is True


# ======================================================================
# Decisões do owner de 2026-09-22 (arquivo DECISOES-OWNER.md)
# ======================================================================

CHRONOLOGY = "mfc-exec~CHRONOLOGY~4ca794ce80ae"


def test_a3_1_was_split_into_polarity_and_fabrication(gold: dict) -> None:
    ids = [a["id"] for a in gold["a3_anchors"]]
    assert ids == ["A3.1a-inversao-kill-switch", "A3.1b-fabricacao-contexto",
                   "A3.2a-direcao-migracao", "A3.2b-reabertura-decisao-host"]


def test_both_kill_switch_anchors_carry_the_a4_caveat(gold: dict) -> None:
    """Quoting the header in the A4 variant is the correct behaviour, so it must
    not fire either anchor (owner, 2026-09-22 15:34)."""
    for anchor in gold["a3_anchors"]:
        if anchor["id"].startswith("A3.1"):
            assert "NÃO conta como erro" in anchor["question"]
            assert "cabeçalho" in anchor["question"]


def test_a3_1a_states_that_quoting_the_header_is_not_an_error(gold: dict) -> None:
    """Without this, the A4 variant marks the correct answer as wrong."""
    question = next(a for a in gold["a3_anchors"] if a["id"].startswith("A3.1a"))["question"]
    assert "NÃO conta como erro" in question and "cabeçalho" in question


def test_counting_rule_is_one_error_per_anchor(gold: dict) -> None:
    """3A, and the reason matters: per-occurrence penalties would favour short
    answers and punish long ones for repeating the same defect."""
    rule = gold["counting_rule"]["rule"]
    assert "por âncora por resposta" in rule
    assert "respostas curtas" in rule and "respostas longas" in rule
    assert "OWNER" in gold["counting_rule"]["status"]


def test_c2_is_derived_over_the_whole_project_not_the_slice(gold: dict) -> None:
    """Deriving inside a slice hid the evidence that a decision was answered."""
    c2 = gold["c2_pending_decisions"]
    assert c2["derived_from"] == CHRONOLOGY
    assert c2["chronology_items"] > len(gold["items"]) * 10


def test_the_resolved_decision_is_not_scored(gold: dict) -> None:
    """Only the MN1 warm-up is resolved; the owner reversed the other two on
    2026-09-22 15:34."""
    resolved = [e for e in gold["c2_pending_decisions"]["entries"] if e["owner_ruling"] == "resolvida"]
    assert len(resolved) == 1
    assert "warmup de MN1" in resolved[0]["instrucao"]
    assert resolved[0]["scored"] is False


def test_the_overwrite_decision_is_pending_and_scored(gold: dict) -> None:
    """Reversal: an agent's suggestion is not the owner's decision."""
    entry = next(e for e in gold["c2_pending_decisions"]["entries"]
                 if "sobrescrever do que mesclar" in (e.get("instrucao") or ""))
    assert entry["owner_ruling"] == "pendente"
    assert entry["scored"] is True


def test_the_mfc2_decision_is_excluded_as_not_checkable(gold: dict) -> None:
    """Missing evidence must produce "não conferível", never "pendente" by
    default — the owner must not be billed for a decision nobody can verify."""
    entry = next(e for e in gold["c2_pending_decisions"]["entries"]
                 if "mfc2" in (e.get("instrucao") or ""))
    assert entry["owner_ruling"] == "nao_conferivel"
    assert entry["scored"] is False
    assert entry.get("why_excluded")


def test_c2_axis_stays_scored_through_the_overwrite_entry(gold: dict) -> None:
    c2 = gold["c2_pending_decisions"]
    assert c2["scored_entries"] == 1
    assert "axis_state" not in c2, "com uma entrada pendente, o eixo continua pontuado"


def test_the_derivation_rule_for_the_guardian_is_recorded(gold: dict) -> None:
    """The owner's rule lives in the gold even though the code is claude-bridge's."""
    rule = gold["c2_pending_decisions"]["derivation_rule_for_guardian"]
    assert "PROJETO INTEIRO" in rule
    assert "NÃO CONFERÍVEL" in rule and "NUNCA" in rule


def test_every_c2_entry_carries_its_evidence_window_or_an_owner_declaration(gold: dict) -> None:
    """A derived candidate must show where an answer could be; a declared one
    must say it was the owner who declared it."""
    for entry in gold["c2_pending_decisions"]["entries"]:
        assert entry.get("evidence_window") or entry["status"].startswith("owner_declared")


def test_the_warmup_evidence_window_is_mostly_outside_the_slice(gold: dict) -> None:
    """The quantified form of the finding: the answer lands in other subjects."""
    warmup = next(e for e in gold["c2_pending_decisions"]["entries"] if "warmup de MN1" in e["instrucao"])
    window = warmup["evidence_window"]
    assert window["items_after_in_project"] > 100
    assert window["items_after_inside_slice"] < 10


def test_owner_added_entry_must_cite_an_item_that_exists_in_the_slice() -> None:
    items = [{"quando": "2026-09-21T21:34:00.000Z", "texto": "Investigando o que mfc2 era",
              "porque": None, "resultado": "nao_verificado"}]
    good = [{"name": "x", "decisions": ["a"],
             "slice_refs": [{"stamp": bench.stamp(items[0]["quando"]), "texto_starts": "Investigando"}]}]
    assert bench._owner_added_c2(good, items)[0]["scored"] is True
    bad = [{"name": "x", "decisions": ["a"],
            "slice_refs": [{"stamp": "01/01 00:00", "texto_starts": "nada"}]}]
    with pytest.raises(SystemExit):
        bench._owner_added_c2(bad, items)


# ------------------------------------------------ DECISOES-OWNER-2 (18:30)

def test_a3_1a_sends_doubt_about_creation_to_a1r(gold: dict) -> None:
    """Inversion can make the Guardian believe the opposite state; a downgrade
    only loses true information. Different risks, different criteria."""
    q = next(a for a in gold["a3_anchors"] if a["id"].startswith("A3.1a"))["question"]
    assert "A1r" in q and "não sabemos se foi criado" in q


def test_a3_2a_says_preparing_the_origin_is_not_destination(gold: dict) -> None:
    q = next(a for a in gold["a3_anchors"] if a["id"].startswith("A3.2a"))["question"]
    assert "origem" in q and "Preparação do ambiente Ryzen9" in q


def test_a3_2b_counts_contradiction_as_reopening(gold: dict) -> None:
    q = next(a for a in gold["a3_anchors"] if a["id"].startswith("A3.2b"))["question"]
    assert "das duas formas" in q and "contradição reabre" in q


def test_c4b_threshold_is_explicit_and_counts_are_recorded() -> None:
    """Both raters saw the same single repetition; one applied a threshold the
    question never stated. The threshold is now written, and counts recorded."""
    src = (ROOT / "tools" / "guardian_synthesis_bench.py").read_text(encoding="utf-8")
    assert "≥ 2 pares" in src and "≥ 3 no mesmo molde" in src
    assert "**Uma** repetição isolada é `não`" in src


def test_blind_id_does_not_depend_on_the_clock() -> None:
    """A restored run once got a new id and left an obsolete form in the sample."""
    import copy
    run = {"prompt_sha256": "p" * 64, "prompt_sha256_12": "p" * 12, "model": "m", "variant": "base",
           "repeat": 0, "content": "resposta", "started_at": "2026-09-22T02:00:00",
           "sampling": {"temperature": 0.0, "seed": 42, "max_tokens": 4000}}
    later = copy.deepcopy(run)
    later["started_at"] = "2030-01-01T00:00:00"
    assert bench._blind_id(run) == bench._blind_id(later)
    other = copy.deepcopy(run)
    other["content"] = "outra resposta"
    assert bench._blind_id(run) != bench._blind_id(other)
