from __future__ import annotations

import json
import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from tools.watcher_smoke_harness import (
    EvidenceFile,
    HarnessError,
    RoundInput,
    b5_projection,
    build_prompt,
    compare_passes,
    decoding_record,
    request_body,
    request_sha256,
    validate_output,
    validate_output_with_evidence,
    validate_request,
    _has_later_round,
    _slot_status,
)


def _item(tmp_path: Path) -> RoundInput:
    return RoundInput(
        round_id="ask/fixture-1",
        mode="ask",
        regime="dual-complete",
        round_dir=tmp_path,
        later_round_exists=True,
        evidence=(
            EvidenceFile(
                str(tmp_path / "metrics.json"),
                '{"dispatch": true, "reset_error": null}',
            ),
            EvidenceFile(
                str(tmp_path / "answer.md"),
                "**APROVE.**\nTudo certo.",
            ),
        ),
        label={"suggested_state": "normal"},
        slot_status=(
            {
                "reviewer": "fixture-rev",
                "dispatched": True,
                "declared_status": "done",
                "artifact_present": True,
            },
        ),
    )


def _output(item: RoundInput, *, state: str | None = "normal") -> dict:
    return {
        "state": state,
        "abstain": state is None,
        "summary": "leitura observacional",
        "tier": "heuristic",
        "action": "none",
        "priority": 1,
        "evidence": [
            {"path": item.evidence[0].path, "line_start": 1, "line_end": 1},
        ],
    }


def test_request_is_temperature_zero_and_has_no_tools_or_unsupported_knobs(tmp_path: Path) -> None:
    body = request_body(_item(tmp_path))
    validate_request(body)
    assert body["temperature"] == 0.0
    assert "tools" not in body
    assert "tool_choice" not in body
    assert "seed" not in body
    assert "top_p" not in body
    assert "top_k" not in body
    assert decoding_record()["num_ctx_declared"] == 32768


def test_request_hash_is_stable_for_both_passes(tmp_path: Path) -> None:
    item = _item(tmp_path)
    assert request_sha256(item) == request_sha256(item)


def test_prompt_contains_packet_but_not_label_sidecar(tmp_path: Path) -> None:
    item = _item(tmp_path)
    prompt = build_prompt(item)
    assert item.evidence[0].path in prompt
    assert "dispatch" in prompt
    assert "slot_status" in prompt
    assert "single-lens" in prompt
    assert "suggested_state" not in prompt
    assert "gold_state" not in prompt


def test_b3_accepts_path_and_in_bounds_coordinates_and_hashes_extracted_text(tmp_path: Path) -> None:
    item = _item(tmp_path)
    value, refs = validate_output_with_evidence(_output(item), item.evidence)
    assert value["tier"] == "heuristic"
    assert refs[0]["path"] == item.evidence[0].path
    assert refs[0]["line_start"] == 1
    assert refs[0]["line_end"] == 1
    assert refs[0]["extracted_sha256"] == hashlib.sha256(
        item.evidence[0].content.encode("utf-8")
    ).hexdigest()


@pytest.mark.parametrize(
    "mutator, message",
    [
        (lambda value: value["evidence"].__setitem__(0, {"path": "/inventado", "line_start": 1, "line_end": 1}), "B3"),
        (lambda value: value["evidence"].__setitem__(0, {"path": value["evidence"][0]["path"], "line_start": 0, "line_end": 1}), "B3"),
        (lambda value: value["evidence"].__setitem__(0, {"path": value["evidence"][0]["path"], "line_start": 1, "line_end": 2}), "B3"),
        (lambda value: value.__setitem__("tier", "verified"), "B4"),
        (lambda value: value.__setitem__("action", "interrupt"), "B1"),
        (lambda value: value.__setitem__("summary", "pare o processo"), "B1"),
    ],
)
def test_output_validation_fails_closed(tmp_path: Path, mutator, message: str) -> None:
    item = _item(tmp_path)
    value = _output(item)
    mutator(value)
    with pytest.raises(HarnessError, match=message):
        validate_output(value, item.evidence)


def test_b5_ignores_summary_but_compares_state_and_abstention(tmp_path: Path) -> None:
    item = _item(tmp_path)
    left = _output(item)
    right = _output(item)
    right["summary"] = "texto diferente, mesma decisão"
    records = [
        {"round_id": item.round_id, "pass": 1, "output": left},
        {"round_id": item.round_id, "pass": 2, "output": right},
    ]
    assert b5_projection(left) == b5_projection(right)
    assert compare_passes(records)["comparisons"][0]["agree"] is True


def test_b5_detects_state_or_abstention_change(tmp_path: Path) -> None:
    item = _item(tmp_path)
    left = _output(item, state="normal")
    right = _output(item, state=None)
    records = [
        {"round_id": item.round_id, "pass": 1, "output": left},
        {"round_id": item.round_id, "pass": 2, "output": right},
    ]
    assert compare_passes(records)["comparisons"][0]["agree"] is False


def test_fixture_output_is_json_serializable(tmp_path: Path) -> None:
    item = _item(tmp_path)
    json.dumps(_output(item), ensure_ascii=False)


def test_single_lens_prompt_requires_explicit_abstention(tmp_path: Path) -> None:
    prompt = build_prompt(replace(_item(tmp_path), regime="single-lens"))
    assert "state=null" in prompt
    assert "abstain=true" in prompt


def test_slot_status_materializes_absent_artifact(tmp_path: Path) -> None:
    metrics = {
        "reviewers": {
            "fixture-rev": {"dispatched": True, "status": "done"},
            "missing-rev": {"dispatched": True, "status": "stalled"},
        }
    }
    (tmp_path / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    (tmp_path / "fixture-rev").mkdir()
    (tmp_path / "fixture-rev" / "verdict.md").write_text("ok\n", encoding="utf-8")
    (tmp_path / "missing-rev").mkdir()
    slots = _slot_status(tmp_path, "review")
    assert slots == (
        {
            "reviewer": "fixture-rev",
            "dispatched": True,
            "declared_status": "done",
            "artifact_present": True,
        },
        {
            "reviewer": "missing-rev",
            "dispatched": True,
            "declared_status": "stalled",
            "artifact_present": False,
        },
    )


def test_later_round_exists_uses_same_mode_and_numeric_suffix() -> None:
    entries = [
        {"id": "ask/claude-bridge-1", "mode": {"value": "ask", "origin": "derived"}},
        {"id": "ask/claude-bridge-10", "mode": {"value": "ask", "origin": "derived"}},
        {"id": "ask/claude-bridge-2", "mode": {"value": "ask", "origin": "derived"}},
        {"id": "review/claude-bridge-1", "mode": {"value": "review", "origin": "derived"}},
    ]
    assert _has_later_round("ask/claude-bridge-1", "ask", entries) is True
    assert _has_later_round("ask/claude-bridge-2", "ask", entries) is True
    assert _has_later_round("ask/claude-bridge-10", "ask", entries) is False
    assert _has_later_round("review/claude-bridge-1", "review", entries) is False
