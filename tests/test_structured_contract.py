import json
import unittest

from tools.structured_contract import MAX_JSON_DEPTH, StructuredValidation, validate_contract, validate_structured_response


class StructuredContractTests(unittest.TestCase):
    json_contract = {
        "format": "json",
        "allowed_finish_reasons": ["stop"],
        "response_schema": {
            "type": "object",
            "required": ["answer"],
            "properties": {"answer": {"type": "string", "minLength": 1}},
            "additionalProperties": False,
        },
    }

    def test_json_schema_and_finish_reason_pass_without_score(self):
        result = validate_structured_response(
            {"stream_status": "complete", "finish_reason": "stop", "content": '{"answer":"ok"}'},
            self.json_contract,
        )
        self.assertIsInstance(result, StructuredValidation)
        self.assertTrue(result.valid)
        self.assertEqual(result.value, {"answer": "ok"})
        self.assertFalse(hasattr(result, "score"))

    def test_invalid_json_and_schema_are_named_failures(self):
        result = validate_structured_response(
            {"stream_status": "complete", "finish_reason": "stop", "content": '{"wrong": 1}'},
            self.json_contract,
        )
        self.assertFalse(result.valid)
        self.assertIn("$.answer:required", result.reasons)
        malformed = validate_structured_response(
            {"stream_status": "complete", "finish_reason": "stop", "content": "not json"},
            self.json_contract,
        )
        self.assertIn("invalid_json", malformed.reasons)

    def test_incomplete_and_finish_reason_mismatch_fail_closed(self):
        result = validate_structured_response(
            {"stream_status": "incomplete", "finish_reason": "length", "content": '{"answer":"ok"}'},
            self.json_contract,
        )
        self.assertFalse(result.valid)
        self.assertIn("stream_not_complete", result.reasons)
        self.assertIn("finish_reason_not_allowed", result.reasons)

    def test_tool_only_stream_requires_explicit_contract_and_checks_arguments(self):
        contract = {
            "format": "text",
            "allow_tool_only": True,
            "tool_finish_reason": "tool_calls",
            "allowed_finish_reasons": ["tool_calls"],
            "allowed_tools": ["lookup"],
            "required_tool_arguments": {"lookup": ["invoice_id"]},
        }
        result = validate_structured_response(
            {
                "stream_status": "complete",
                "finish_reason": "tool_calls",
                "content": None,
                "tool_calls": [{"name": "lookup", "arguments": {"invoice_id": "demo-001"}}],
            },
            contract,
        )
        self.assertTrue(result.valid)
        bad = validate_structured_response(
            {
                "stream_status": "complete",
                "finish_reason": "tool_calls",
                "content": None,
                "tool_calls": [{"name": "delete_all", "arguments": {}}],
            },
            contract,
        )
        self.assertIn("tool_not_allowed", bad.reasons)
        missing = validate_structured_response(
            {
                "stream_status": "complete",
                "finish_reason": "tool_calls",
                "content": None,
                "tool_calls": [{"name": "lookup", "arguments": {}}],
            },
            contract,
        )
        self.assertIn("tool_required_argument_missing", missing.reasons)

    def test_reasoning_bearing_stream_is_typed_and_explicit(self):
        contract = {"format": "text", "allow_reasoning": True, "allowed_finish_reasons": ["stop"]}
        result = validate_structured_response(
            {"stream_status": "complete", "finish_reason": "stop", "content": "answer", "reasoning": "internal"},
            contract,
        )
        self.assertTrue(result.valid)
        forbidden = validate_structured_response(
            {"stream_status": "complete", "finish_reason": "stop", "content": "answer", "reasoning": "internal"},
            {"format": "text", "allowed_finish_reasons": ["stop"]},
        )
        self.assertIn("reasoning_not_allowed", forbidden.reasons)
        malformed = validate_structured_response(
            {"stream_status": "complete", "finish_reason": "stop", "content": "answer", "reasoning": []},
            contract,
        )
        self.assertIn("reasoning_not_text", malformed.reasons)

    def test_required_provenance_is_checked(self):
        contract = {
            "format": "text",
            "provenance": {"required": True, "required_fields": ["source_id", "quote_hash"]},
        }
        missing = validate_structured_response(
            {"stream_status": "complete", "finish_reason": "stop", "content": "answer"}, contract
        )
        self.assertIn("provenance_missing", missing.reasons)
        empty = validate_structured_response(
            {"stream_status": "complete", "finish_reason": "stop", "content": "answer", "provenance": []}, contract
        )
        self.assertIn("provenance_missing", empty.reasons)
        valid = validate_structured_response(
            {
                "stream_status": "complete",
                "finish_reason": "stop",
                "content": "answer",
                "provenance": [{"source_id": "source-a", "quote_hash": "abc"}],
            },
            contract,
        )
        self.assertTrue(valid.valid)

    def test_tool_only_json_contract_can_skip_content_when_explicitly_allowed(self):
        contract = {
            "format": "json",
            "allow_tool_only": True,
            "allowed_finish_reasons": ["tool_calls"],
            "allowed_tools": ["lookup"],
            "required_tool_arguments": {"lookup": ["invoice_id"]},
        }
        result = validate_structured_response(
            {
                "stream_status": "complete",
                "finish_reason": "tool_calls",
                "content": None,
                "tool_calls": [{"name": "lookup", "arguments": {"invoice_id": "demo-001"}}],
            },
            contract,
        )
        self.assertTrue(result.valid)

    def test_malformed_contract_is_rejected_before_response_evaluation(self):
        with self.assertRaises(ValueError):
            validate_contract({"format": "xml"})
        with self.assertRaises(ValueError):
            validate_contract({"format": "json", "response_schema": {"type": "object", "oneOf": []}})
        with self.assertRaises(ValueError):
            validate_contract({"allowed_tools": ["lookup"], "required_tool_arguments": {"lookup": ["id", "id"]}})

    def test_untyped_response_fields_fail_without_raising(self):
        result = validate_structured_response(
            {"stream_status": [], "finish_reason": {}, "content": "answer"},
            {"format": "text", "allowed_finish_reasons": ["stop"]},
        )
        self.assertFalse(result.valid)
        self.assertIn("stream_status_unknown", result.reasons)
        self.assertIn("finish_reason_missing", result.reasons)

    def test_json_enum_distinguishes_booleans_from_numbers_recursively(self):
        for content, schema in (
            ("true", {"type": "boolean", "enum": [1]}),
            ("false", {"type": "boolean", "enum": [0]}),
            ('{"decision":true}', {"type": "object", "properties": {"decision": {"enum": [1]}}}),
        ):
            result = validate_structured_response(
                {"stream_status": "complete", "finish_reason": "stop", "content": content},
                {"format": "json", "allowed_finish_reasons": ["stop"], "response_schema": schema},
            )
            with self.subTest(content=content):
                self.assertIn("$:enum" if content != '{"decision":true}' else "$.decision:enum", result.reasons)
        numeric = validate_structured_response(
            {"stream_status": "complete", "finish_reason": "stop", "content": "1"},
            {"format": "json", "allowed_finish_reasons": ["stop"], "response_schema": {"type": "number", "enum": [1.0]}},
        )
        self.assertTrue(numeric.valid)

    def test_non_standard_json_constants_and_nonfinite_exponents_fail(self):
        contract = {"format": "json", "allowed_finish_reasons": ["stop"], "response_schema": {"type": "number"}}
        for content in ("NaN", "Infinity", "-Infinity", "1e999"):
            with self.subTest(content=content):
                result = validate_structured_response(
                    {"stream_status": "complete", "finish_reason": "stop", "content": content}, contract
                )
                self.assertIn("invalid_json", result.reasons)

    def test_nonfinite_exponents_are_rejected_without_schema_and_when_nested(self):
        contract = {"format": "json", "allowed_finish_reasons": ["stop"]}
        for content in ("1e999", '{"outer":{"value":1e999}}', "[1e999]"):
            with self.subTest(content=content):
                result = validate_structured_response(
                    {"stream_status": "complete", "finish_reason": "stop", "content": content}, contract
                )
                self.assertFalse(result.valid)
                self.assertIn("invalid_json", result.reasons)

    def test_finite_underflow_remains_valid_json(self):
        result = validate_structured_response(
            {"stream_status": "complete", "finish_reason": "stop", "content": "1e-999"},
            {"format": "json", "allowed_finish_reasons": ["stop"], "response_schema": {"type": "number"}},
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.value, 0.0)

    def test_decoded_surrogates_are_rejected_without_leaking_value(self):
        result = validate_structured_response(
            {"stream_status": "complete", "finish_reason": "stop", "content": '{"answer":"\\ud800"}'},
            {"format": "json", "allowed_finish_reasons": ["stop"]},
        )
        self.assertFalse(result.valid)
        self.assertIn("json_not_json", result.reasons)
        self.assertIsNone(result.value)

    def test_deep_json_and_schema_fail_with_named_or_value_error(self):
        nested = "leaf"
        for _ in range(MAX_JSON_DEPTH + 1):
            nested = {"x": nested}
        content = json.dumps(nested)
        result = validate_structured_response(
            {"stream_status": "complete", "finish_reason": "stop", "content": content},
            {"format": "json", "allowed_finish_reasons": ["stop"]},
        )
        self.assertFalse(result.valid)
        self.assertIn("json_not_json", result.reasons)

        schema = {"type": "object"}
        for _ in range(MAX_JSON_DEPTH + 1):
            schema = {"type": "object", "properties": {"x": schema}}
        with self.assertRaises(ValueError):
            validate_contract({"format": "json", "response_schema": schema})


if __name__ == "__main__":
    unittest.main()
