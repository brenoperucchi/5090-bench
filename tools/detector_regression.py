"""Pure, versioned regression evaluator for sanitized detector fixtures.

This is deliberately separate from ``run_chat.py`` and never assigns an
aggregate score.  Its expected outcomes define a regression contract, not an
independently labelled model-quality holdout.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


RULESET_ID = "detector-regression-v1"
_OUTCOMES = {"pass", "fail", "indeterminate", "not_applicable"}
_DETECTORS = {"language", "escalation", "promise", "reasoning", "citation", "tool"}
_LANGUAGES = {"pt", "en"}
_PROMISE_STATES = {"delivered", "not_delivered", "unknown"}


def ruleset_hash() -> str:
    """Return the SHA-256 of this ruleset's source bytes."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def fixture_hash(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_fixture(payload: Mapping[str, Any]) -> None:
    """Validate the deliberately small fixture schema before evaluation."""
    if not isinstance(payload, Mapping):
        raise ValueError("fixture must be an object")
    if payload.get("ruleset_id") != RULESET_ID:
        raise ValueError("fixture ruleset_id does not match evaluator")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("fixture cases must be a non-empty list")
    identifiers: set[str] = set()
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError("every fixture case must be an object")
        case_id, inputs, expected = case.get("case_id"), case.get("input"), case.get("expected")
        if not isinstance(case_id, str) or not case_id or case_id in identifiers:
            raise ValueError("case_id must be unique and non-empty")
        identifiers.add(case_id)
        if not isinstance(inputs, Mapping) or not isinstance(expected, Mapping) or not expected:
            raise ValueError(f"{case_id}: input and expected are required objects")
        for detector, result in expected.items():
            if detector not in _DETECTORS:
                raise ValueError(f"{case_id}: unknown detector {detector}")
            if not isinstance(result, Mapping) or set(result) != {"outcome", "reason"} or result.get("outcome") not in _OUTCOMES:
                raise ValueError(f"{case_id}: expected {detector} needs a named outcome")
            if not isinstance(result.get("reason"), str) or not result["reason"]:
                raise ValueError(f"{case_id}: expected {detector} needs a reason")
        _validate_case_inputs(case_id, inputs, expected)


def _validate_case_inputs(case_id: str, inputs: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    expected_detectors = set(expected)
    if "expected_language" in inputs:
        if not isinstance(inputs["expected_language"], str) or inputs["expected_language"] not in _LANGUAGES or not isinstance(inputs.get("response_text"), str):
            raise ValueError(f"{case_id}: language requires expected_language pt/en and response_text")
    if "expect_escalation" in inputs:
        if type(inputs["expect_escalation"]) is not bool or ("observed_escalation" not in inputs or inputs["observed_escalation"] is not None and type(inputs["observed_escalation"]) is not bool):
            raise ValueError(f"{case_id}: escalation requires boolean expected and boolean/null observed values")
    if "promise" in inputs and type(inputs["promise"]) is not bool:
        raise ValueError(f"{case_id}: promise must be boolean")
    if inputs.get("promise") is True:
        contract = inputs.get("promise_contract")
        if not isinstance(contract, Mapping) or not isinstance(inputs.get("response_text"), str):
            raise ValueError(f"{case_id}: promise requires response_text and promise_contract")
        _validate_promise_contract(case_id, contract)
    if "check_reasoning" in inputs and type(inputs["check_reasoning"]) is not bool:
        raise ValueError(f"{case_id}: check_reasoning must be boolean")
    if inputs.get("check_reasoning") is True and not isinstance(inputs.get("response_text"), str):
        raise ValueError(f"{case_id}: reasoning requires response_text")
    if "visible_reasoning" in inputs and type(inputs["visible_reasoning"]) is not bool:
        raise ValueError(f"{case_id}: visible_reasoning must be boolean")
    if "citation_contract" in inputs and (not isinstance(inputs["citation_contract"], Mapping) or not isinstance(inputs.get("citations"), list)):
        raise ValueError(f"{case_id}: citation requires contract and citations list")
    if "citation_contract" in inputs:
        _validate_citation_contract(case_id, inputs["citation_contract"])
    if "tool_contract" in inputs and (not isinstance(inputs["tool_contract"], Mapping) or not isinstance(inputs.get("tool_calls"), list)):
        raise ValueError(f"{case_id}: tool requires contract and tool_calls list")
    if "tool_contract" in inputs:
        _validate_tool_contract(case_id, inputs["tool_contract"])
    active = set()
    if "expected_language" in inputs: active.add("language")
    if "expect_escalation" in inputs: active.add("escalation")
    if inputs.get("promise") is True: active.add("promise")
    if inputs.get("check_reasoning") is True: active.add("reasoning")
    if "citation_contract" in inputs: active.add("citation")
    if "tool_contract" in inputs: active.add("tool")
    if active != expected_detectors:
        raise ValueError(f"{case_id}: expected detectors must equal active detectors")


def _validate_promise_contract(case_id: str, contract: Mapping[str, Any]) -> None:
    required = contract.get("required_wording")
    if not isinstance(required, str) or not required:
        raise ValueError(f"{case_id}: promise required_wording must be a non-empty string")
    if "external_delivery_state" in contract:
        state = contract["external_delivery_state"]
        if not isinstance(state, str) or state not in _PROMISE_STATES:
            raise ValueError(f"{case_id}: external_delivery_state must be delivered, not_delivered, or unknown")


def _validate_citation_contract(case_id: str, contract: Mapping[str, Any]) -> None:
    if type(contract.get("required")) is not bool or type(contract.get("required_count")) is not int or isinstance(contract.get("required_count"), bool) or contract["required_count"] < 0:
        raise ValueError(f"{case_id}: citation required/required_count have invalid types")
    sources = contract.get("sources")
    if not isinstance(sources, list):
        raise ValueError(f"{case_id}: citation sources must be a list")
    source_ids: list[str] = []
    for source in sources:
        if not isinstance(source, Mapping) or any(not isinstance(source.get(field), str) or not source[field] for field in ("source_id", "literal_quote", "finding_id")):
            raise ValueError(f"{case_id}: citation source fields are invalid")
        source_ids.append(source["source_id"])
    if len(source_ids) != len(set(source_ids)):
        raise ValueError(f"{case_id}: citation source IDs must be unique")
    required = contract.get("required_source_ids")
    if required is not None and (not isinstance(required, list) or any(not isinstance(item, str) or not item for item in required) or len(required) != len(set(required))):
        raise ValueError(f"{case_id}: required source IDs must be unique strings")
    source_id_set = set(source_ids)
    if required is not None and (not set(required).issubset(source_id_set) or contract["required_count"] != len(required)):
        raise ValueError(f"{case_id}: required source IDs must belong to sources and match required_count")


def _validate_tool_contract(case_id: str, contract: Mapping[str, Any]) -> None:
    supported, expected = contract.get("supported_tools"), contract.get("expected_calls")
    if not isinstance(supported, list) or any(not isinstance(item, str) or not item for item in supported) or len(supported) != len(set(supported)):
        raise ValueError(f"{case_id}: supported tools must be unique strings")
    if not isinstance(expected, list):
        raise ValueError(f"{case_id}: expected tool calls must be a list")
    for call in expected:
        if not isinstance(call, Mapping) or not isinstance(call.get("name"), str) or not call["name"] or call["name"] not in supported or not isinstance(call.get("required_arguments", []), list) or any(not isinstance(item, str) or not item for item in call.get("required_arguments", [])) or len(call.get("required_arguments", [])) != len(set(call.get("required_arguments", []))):
            raise ValueError(f"{case_id}: expected tool call is invalid")
        if "citation_source_id" in call and (not isinstance(call["citation_source_id"], str) or not call["citation_source_id"]):
            raise ValueError(f"{case_id}: expected tool citation source must be a non-empty string")


def evaluate_case(case: Mapping[str, Any]) -> dict[str, Any]:
    """Return named detector outcomes only; there is intentionally no score."""
    case_id = case.get("case_id")
    inputs = case.get("input")
    if not isinstance(case_id, str) or not isinstance(inputs, Mapping):
        raise ValueError("case requires case_id and input")
    outcomes: dict[str, dict[str, str]] = {}
    if "expected_language" in inputs:
        outcomes["language"] = _language(inputs)
    if "expect_escalation" in inputs:
        outcomes["escalation"] = _escalation(inputs)
    if inputs.get("promise") is True:
        outcomes["promise"] = _promise(inputs)
    if inputs.get("check_reasoning") is True:
        outcomes["reasoning"] = _reasoning(inputs)
    if "citation_contract" in inputs:
        outcomes["citation"] = _citation(inputs)
    if "tool_contract" in inputs:
        outcomes["tool"] = _tool(inputs)
    return {"ruleset_id": RULESET_ID, "ruleset_sha256": ruleset_hash(), "case_id": case_id, "outcomes": outcomes}


def _outcome(outcome: str, reason: str) -> dict[str, str]:
    return {"outcome": outcome, "reason": reason}


def _language(inputs: Mapping[str, Any]) -> dict[str, str]:
    expected = inputs.get("expected_language")
    observed = _detect_language(inputs.get("response_text"))
    if observed == "tie":
        return _outcome("indeterminate", "marker_poor_tie")
    if observed == expected:
        return _outcome("pass", "language_matches")
    return _outcome("fail", "unexpected_language")


def _detect_language(value: Any) -> str:
    if not isinstance(value, str):
        return "tie"
    words = set(re.findall(r"[a-záàâãçéêíóôõúü]+", value.lower()))
    pt = len(words & {"a", "é", "para", "você", "uma", "com", "resposta", "vou", "chamado"})
    en = len(words & {"this", "is", "entirely", "in", "english", "response", "will", "the", "and"})
    if pt == en:
        return "tie"
    return "pt" if pt > en else "en"


def _escalation(inputs: Mapping[str, Any]) -> dict[str, str]:
    expected, observed = inputs.get("expect_escalation"), inputs.get("observed_escalation")
    if expected is True and observed is False:
        return _outcome("fail", "MISS")
    if expected is False and observed is True:
        return _outcome("fail", "LEAK")
    if type(observed) is bool:
        return _outcome("pass", "escalation_matches")
    return _outcome("indeterminate", "escalation_not_observed")


def _promise(inputs: Mapping[str, Any]) -> dict[str, str]:
    contract = inputs.get("promise_contract")
    if not isinstance(contract, Mapping):
        return _outcome("indeterminate", "external_delivery_unknown")
    state = contract.get("external_delivery_state")
    if not isinstance(state, str) or state not in _PROMISE_STATES or state == "unknown":
        return _outcome("indeterminate", "external_delivery_unknown")
    required = contract.get("required_wording")
    text = inputs.get("response_text")
    if not isinstance(required, str) or not required or not isinstance(text, str) or required not in text:
        return _outcome("fail", "required_wording_missing")
    if state != "delivered":
        return _outcome("fail", "external_delivery_not_confirmed")
    return _outcome("pass", "delivered_with_required_wording")


def _reasoning(inputs: Mapping[str, Any]) -> dict[str, str]:
    text = inputs.get("response_text", "")
    if not isinstance(text, str):
        return _outcome("indeterminate", "response_text_not_text")
    if any(marker in text.lower() for marker in ("<think", "</think", "<analysis", "</analysis")):
        return _outcome("fail", "tagged_reasoning")
    if inputs.get("visible_reasoning") is True or re.match(r"^(first i will|let me |primeiro vou )", text.lower()):
        return _outcome("fail", "visible_reasoning")
    return _outcome("pass", "no_visible_reasoning_signal")


def _citation(inputs: Mapping[str, Any]) -> dict[str, str]:
    contract = inputs.get("citation_contract")
    citations = inputs.get("citations", [])
    if not isinstance(contract, Mapping) or not isinstance(citations, list):
        return _outcome("indeterminate", "citation_contract_unreadable")
    required = contract.get("required") is True
    sources = contract.get("sources", [])
    if not isinstance(sources, list):
        return _outcome("indeterminate", "citation_contract_unreadable")
    if required and not sources:
        return _outcome("indeterminate", "required_source_unoffered_or_unread")
    if not required and not citations:
        return _outcome("pass", "citation_not_required")
    required_count = contract.get("required_count")
    if type(required_count) is not int or required_count < 0:
        return _outcome("indeterminate", "citation_contract_unreadable")
    if len(citations) != required_count:
        return _outcome("fail", "citation_count_mismatch")
    required_source_ids = contract.get("required_source_ids")
    if required_source_ids is not None and (not isinstance(required_source_ids, list) or any(not isinstance(item, str) for item in required_source_ids)):
        return _outcome("indeterminate", "citation_contract_unreadable")
    if required_source_ids is not None and len(required_source_ids) != len(set(required_source_ids)):
        return _outcome("fail", "required_source_ids_duplicate")
    if required_source_ids is not None and required_count != len(required_source_ids):
        return _outcome("fail", "required_source_coverage_mismatch")
    source_by_id = {source.get("source_id"): source for source in sources if isinstance(source, Mapping)}
    for citation in citations:
        if not isinstance(citation, Mapping):
            return _outcome("fail", "citation_not_object")
        for field in ("source_id", "quote", "quote_hash", "finding_id"):
            if not isinstance(citation.get(field), str) or not citation[field]:
                return _outcome("fail", "required_citation_field_missing")
        source = source_by_id.get(citation["source_id"])
        if source is None:
            return _outcome("fail", "source_id_outside_enum")
        quote = citation["quote"]
        if quote != source.get("literal_quote"):
            return _outcome("fail", "quote_not_literal")
        if _sha256(quote) != citation["quote_hash"]:
            return _outcome("fail", "quote_hash_mismatch")
        if citation["finding_id"] != source.get("finding_id"):
            return _outcome("fail", "finding_mismatch")
    observed_source_ids = [citation["source_id"] for citation in citations]
    if len(observed_source_ids) != len(set(observed_source_ids)):
        return _outcome("fail", "duplicate_citation_source_id")
    if required_source_ids is not None and set(observed_source_ids) != set(required_source_ids):
        return _outcome("fail", "required_source_coverage_mismatch")
    return _outcome("pass", "citation_contract_matches")


def _tool(inputs: Mapping[str, Any]) -> dict[str, str]:
    contract = inputs.get("tool_contract")
    calls = inputs.get("tool_calls", [])
    if not isinstance(contract, Mapping) or not isinstance(calls, list):
        return _outcome("indeterminate", "tool_contract_unreadable")
    expected_calls = contract.get("expected_calls", [])
    supported = contract.get("supported_tools", [])
    if not isinstance(expected_calls, list) or not isinstance(supported, list):
        return _outcome("indeterminate", "tool_contract_unreadable")
    if len(calls) != len(expected_calls):
        return _outcome("fail", "tool_call_count_mismatch")
    for call, expected in zip(calls, expected_calls):
        if not isinstance(call, Mapping) or not isinstance(expected, Mapping):
            return _outcome("fail", "tool_call_not_object")
        name = call.get("name")
        if name not in supported:
            return _outcome("fail", "unsupported_tool")
        if name != expected.get("name"):
            return _outcome("fail", "unexpected_tool")
        arguments = call.get("arguments")
        if not isinstance(arguments, Mapping):
            return _outcome("fail", "missing_required_argument")
        if any(argument not in arguments for argument in expected.get("required_arguments", [])):
            return _outcome("fail", "missing_required_argument")
        if "citation_source_id" in expected and call.get("citation_source_id") != expected["citation_source_id"]:
            return _outcome("fail", "tool_citation_mismatch")
    return _outcome("pass", "tool_contract_matches")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
