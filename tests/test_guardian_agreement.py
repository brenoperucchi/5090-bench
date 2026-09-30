"""Specs for the inter-rater agreement tool.

The cases that matter are the degenerate ones: a criterion both raters always
answer the same way has no kappa, and reporting 1.0 there would turn "nobody
had to judge anything" into "perfect agreement".
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("agree", ROOT / "tools" / "guardian_agreement.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


agree = _load()


def test_perfect_agreement_on_a_varying_criterion_is_one() -> None:
    k, _ = agree.cohen_kappa(["sim", "nao", "sim", "nao"], ["sim", "nao", "sim", "nao"])
    assert k == 1.0


def test_constant_answers_have_no_kappa() -> None:
    k, note = agree.cohen_kappa(["nao"] * 8, ["nao"] * 8)
    assert k is None and "indefinido" in note


def test_total_disagreement_is_negative() -> None:
    k, _ = agree.cohen_kappa(["sim", "nao", "sim", "nao"], ["nao", "sim", "nao", "sim"])
    assert k is not None and k < 0


def test_chance_level_agreement_is_near_zero() -> None:
    a = ["sim", "sim", "nao", "nao"]
    b = ["sim", "nao", "sim", "nao"]
    k, _ = agree.cohen_kappa(a, b)
    assert k is not None and abs(k) < 1e-9


def test_parse_reads_ticked_and_blank_boxes(tmp_path: Path) -> None:
    form = tmp_path / "r1.md"
    form.write_text(
        "# Checklist\n"
        "- [x] A1: inverteu polaridade?\n  trecho: xyz\n"
        "- [ ] C1: decisão no primeiro bloco?\n"
        "- [x] C2: cobre as pendências?\n    forte\n"
        "## Resposta avaliada\n```\n- [x] isto não é um critério\n```\n",
        encoding="utf-8",
    )
    got = agree.parse_form(form)
    assert got["A1"] == "sim"
    assert got["C1"] == "nao"
    assert got["C2"] == "forte"
    assert "isto" not in got, "o corpo da resposta não pode virar critério"


def test_parse_marks_na_instead_of_counting_it_as_no(tmp_path: Path) -> None:
    form = tmp_path / "r2.md"
    form.write_text("- [ ] B2: declarou indistinção?\n  n/a — recorte de assunto único\n"
                    "## Resposta avaliada\n```\n```\n", encoding="utf-8")
    assert agree.parse_form(form)["B2"] == "n/a"


RULES = {"gate_por_criterio": {"piso_n": 7, "limiar": 0.6}, "prevalencia_extrema": {"limiar": 0.8}}


def test_small_n_is_not_evaluable() -> None:
    r = agree.gate_criterion(["sim", "nao", "nao"], ["nao", "nao", "nao"], RULES)
    assert r["gate_result"] == "NOT_EVALUABLE"


def test_extreme_prevalence_is_decided_by_ac1_but_kappa_is_still_reported() -> None:
    """6/7 agreement with a dominant 'nao': κ collapses to ~0, AC1 does not."""
    a = ["nao"] * 7
    b = ["nao"] * 6 + ["sim"]
    r = agree.gate_criterion(a, b, RULES)
    assert r["prevalencia_extrema"] and r["medida_que_decidiu"] == "ac1"
    assert r["kappa"] is not None and r["kappa"] < 0.6
    assert r["ac1"] > 0.6 and r["gate_result"] == "PASS"


def test_balanced_criterion_is_decided_by_kappa() -> None:
    a = ["sim", "nao"] * 5
    r = agree.gate_criterion(a, list(a), RULES)
    assert r["medida_que_decidiu"] == "kappa" and r["gate_result"] == "PASS"


def test_count_is_binned_into_frozen_ranges(tmp_path) -> None:
    f = tmp_path / "x.md"
    f.write_text("- [x] A2: contagem: 4\n## Resposta avaliada\n", encoding="utf-8")
    assert agree.parse_form(f)["A2"] == "3-5"
