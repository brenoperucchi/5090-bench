import copy
import hashlib
import json
import unittest
from collections import UserDict

from tools.tool_mode_comparison import (
    ARM_MODES,
    MAX_JSON_DEPTH,
    build_comparison_packet,
    canonical_json,
    validate_packet,
    validate_tool_transcript,
)


def native_transcript():
    return {
        "arm": "native",
        "stream_status": "complete",
        "finish_reason": "stop",
        "turns": [
            {"role": "system", "content": "fixed"},
            {"role": "user", "content": "lookup"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": "call-1", "name": "lookup_invoice", "arguments": {"invoice_id": "demo-001"}}],
            },
            {"role": "tool", "tool_call_id": "call-1", "name": "lookup_invoice", "content": '{"status":"paid"}'},
            {"role": "assistant", "content": "Invoice is paid.", "used_tool_call_ids": ["call-1"]},
        ],
    }


class ToolModeComparisonTests(unittest.TestCase):
    def setUp(self):
        self.packet = build_comparison_packet()
        self.arms = {arm["mode"]: arm for arm in self.packet["arms"]}

    def test_packet_has_three_deterministic_nonexecuting_arms(self):
        self.assertEqual(tuple(arm["mode"] for arm in self.packet["arms"]), ARM_MODES)
        self.assertFalse(self.packet["can_execute"])
        self.assertEqual(validate_packet(self.packet), [])
        self.assertEqual(self.packet, build_comparison_packet())
        self.assertEqual(self.arms["native"]["request"]["tools"][0]["name"], "lookup_invoice")
        self.assertEqual(self.arms["json"]["request"]["format"], "json")
        self.assertEqual(self.arms["control"]["request"]["tools"], [])

    def test_json_arm_carries_the_same_custom_tool_definition(self):
        custom_tool = {
            "name": "find_invoice",
            "description": "Find an invoice.",
            "parameters": {
                "type": "object",
                "required": ["invoice_id"],
                "properties": {"invoice_id": {"type": "string", "maxLength": 12}},
                "additionalProperties": False,
            },
        }
        packet = build_comparison_packet(tool=custom_tool)
        json_system = packet["arms"][1]["request"]["messages"][0]["content"]
        self.assertIn('"name":"find_invoice"', json_system)
        self.assertIn('"maxLength":12', json_system)
        self.assertEqual(validate_packet(packet), [])

    def test_packet_detects_hash_and_rendered_input_tampering(self):
        packet = copy.deepcopy(self.packet)
        packet["arms"][0]["request"]["options"]["temperature"] = 1
        packet["arms"][1]["rendered_input"] = "captured text"
        self.assertIn("native:request_hash_mismatch", validate_packet(packet))
        self.assertIn("json:rendered_input_must_be_null", validate_packet(packet))

    def test_packet_rejects_rehashed_invariant_changes_and_bad_types(self):
        packet = copy.deepcopy(self.packet)
        packet["prompt"] = None
        packet["arms"][0]["rendered_input_status"] = []
        self.assertIn("prompt_invalid", validate_packet(packet))
        self.assertIn("native:rendered_input_status_invalid", validate_packet(packet))

        packet = copy.deepcopy(self.packet)
        packet["arms"][0]["request"]["model"] = "different-model"
        packet["arms"][0]["contract"]["require_result_use"] = False
        packet["arms"][0]["serialized_request_sha256"] = hashlib.sha256(canonical_json(packet["arms"][0]["request"])).hexdigest()
        unsigned = dict(packet)
        unsigned.pop("packet_sha256")
        packet["packet_sha256"] = hashlib.sha256(canonical_json(unsigned)).hexdigest()
        reasons = validate_packet(packet)
        self.assertIn("native:request_invariant_mismatch", reasons)
        self.assertIn("native:contract_invariant_mismatch", reasons)

        packet = copy.deepcopy(self.packet)
        packet["arms"][0]["request"]["stream"] = 1
        packet["arms"][0]["contract"]["require_result_use"] = 1
        packet["arms"][0]["contract"]["max_tool_rounds"] = 2.0
        packet["arms"][0]["serialized_request_sha256"] = hashlib.sha256(canonical_json(packet["arms"][0]["request"])).hexdigest()
        unsigned = dict(packet)
        unsigned.pop("packet_sha256")
        packet["packet_sha256"] = hashlib.sha256(canonical_json(unsigned)).hexdigest()
        reasons = validate_packet(packet)
        self.assertIn("native:request_invariant_mismatch", reasons)
        self.assertIn("native:contract_invariant_mismatch", reasons)

        packet = copy.deepcopy(self.packet)
        packet["arms"][0]["request"]["unserializable"] = {1, 2}
        self.assertIn("packet_not_json_serializable", validate_packet(packet))

    def test_default_tool_is_not_aliased_between_packets_or_arms(self):
        first = build_comparison_packet()
        second = build_comparison_packet()
        self.assertIsNot(first["tool"]["parameters"], second["tool"]["parameters"])
        self.assertIsNot(first["tool"]["parameters"], first["arms"][0]["contract"]["tool_schema"])
        first["tool"]["parameters"]["properties"]["invoice_id"]["minLength"] = 999
        self.assertEqual(second["tool"]["parameters"]["properties"]["invoice_id"]["minLength"], 1)

    def test_native_multiturn_contract_passes(self):
        result = validate_tool_transcript(native_transcript(), self.arms["native"])
        self.assertTrue(result.valid)
        self.assertEqual(result.reasons, ())

    def test_json_envelope_multiturn_contract_passes(self):
        observation = {
            "arm": "json",
            "stream_status": "complete",
            "finish_reason": "stop",
            "turns": [
                {"role": "user", "content": "lookup"},
                {
                    "role": "assistant",
                    "content": '{"tool_calls":[{"id":"call-1","name":"lookup_invoice","arguments":{"invoice_id":"demo-001"}}]}',
                },
                {"role": "tool", "tool_call_id": "call-1", "name": "lookup_invoice", "content": "paid"},
                {"role": "assistant", "content": '{"answer":"Invoice is paid.","used_tool_call_ids":["call-1"]}'},
            ],
        }
        self.assertTrue(validate_tool_transcript(observation, self.arms["json"]).valid)

    def test_control_and_json_wire_misuse_are_rejected(self):
        control = native_transcript()
        control["arm"] = "control"
        result = validate_tool_transcript(control, self.arms["control"])
        self.assertIn("tool_calls_not_allowed", result.reasons)
        json_observation = native_transcript()
        json_observation["arm"] = "json"
        result = validate_tool_transcript(json_observation, self.arms["json"])
        self.assertTrue(any("native_field_in_json_arm" in reason for reason in result.reasons))

    def test_malformed_call_unknown_argument_and_missing_result_fail_closed(self):
        observation = native_transcript()
        observation["turns"][2]["tool_calls"][0]["arguments"] = {"wrong": 1}
        observation["turns"].pop(3)
        result = validate_tool_transcript(observation, self.arms["native"])
        self.assertTrue(any("tool_required_argument_missing" in reason for reason in result.reasons))
        self.assertTrue(any("tool_argument_unknown" in reason for reason in result.reasons))
        self.assertIn("tool_result_missing", result.reasons)

    def test_result_use_and_loop_limits_are_explicit(self):
        observation = native_transcript()
        observation["turns"][-1]["used_tool_call_ids"] = []
        result = validate_tool_transcript(observation, self.arms["native"])
        self.assertIn("tool_result_unused", result.reasons)

        loop = native_transcript()
        loop["turns"].insert(4, {"role": "assistant", "content": None, "tool_calls": [{"id": "call-2", "name": "lookup_invoice", "arguments": {"invoice_id": "demo-001"}}]})
        loop["turns"].insert(5, {"role": "tool", "tool_call_id": "call-2", "name": "lookup_invoice", "content": "paid"})
        loop["turns"].insert(6, {"role": "assistant", "content": None, "tool_calls": [{"id": "call-3", "name": "lookup_invoice", "arguments": {"invoice_id": "demo-001"}}]})
        loop["turns"].insert(7, {"role": "tool", "tool_call_id": "call-3", "name": "lookup_invoice", "content": "paid"})
        loop["turns"][-1]["used_tool_call_ids"] = ["call-1", "call-2", "call-3"]
        self.assertIn("tool_loop_exceeded", validate_tool_transcript(loop, self.arms["native"]).reasons)

        direct_arm = copy.deepcopy(self.arms["native"])
        direct_arm["contract"]["max_tool_rounds"] = 3
        self.assertIn("contract_max_tool_rounds_invalid", validate_tool_transcript(loop, direct_arm).reasons)

    def test_native_arguments_share_the_json_finite_value_domain(self):
        custom_tool = copy.deepcopy(self.packet["tool"])
        custom_tool["parameters"]["properties"]["payload"] = {"type": "object"}
        packet = build_comparison_packet(tool=custom_tool)
        arm = {item["mode"]: item for item in packet["arms"]}["native"]
        observation = {
            "arm": "native",
            "stream_status": "complete",
            "finish_reason": "stop",
            "turns": [
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "name": "lookup_invoice",
                            "arguments": {"invoice_id": "demo-001", "payload": {"n": float("nan")}},
                        }
                    ],
                },
                {"role": "tool", "tool_call_id": "call-1", "name": "lookup_invoice", "content": "found"},
                {"role": "assistant", "content": "done", "used_tool_call_ids": ["call-1"]},
            ],
        }
        self.assertIn("observation_not_json", validate_tool_transcript(observation, arm).reasons)

        valid = copy.deepcopy(observation)
        valid["turns"][0]["tool_calls"][0]["arguments"]["payload"] = {"n": 1, "s": "x"}
        self.assertTrue(validate_tool_transcript(valid, arm).valid)

    def test_previous_answer_and_interruption_cannot_close_a_later_tool_round(self):
        observation = native_transcript()
        observation["turns"].insert(2, {"role": "assistant", "content": "Sure, let me check."})
        observation["turns"].pop()
        result = validate_tool_transcript(observation, self.arms["native"])
        self.assertIn("final_response_missing", result.reasons)
        self.assertIn("tool_result_unused", result.reasons)

        interrupted = native_transcript()
        interrupted["turns"].insert(3, {"role": "user", "content": "Are you there?"})
        result = validate_tool_transcript(interrupted, self.arms["native"])
        self.assertTrue(any("tool_result_interrupted" in reason for reason in result.reasons))

    def test_bad_json_and_duplicate_tool_result_are_rejected(self):
        observation = {
            "arm": "json",
            "stream_status": "complete",
            "finish_reason": "stop",
            "turns": [
                {"role": "assistant", "content": '{"tool_calls":[{"id":"call-1","name":"lookup_invoice","arguments":{"invoice_id":"demo-001"}}]}'},
                {"role": "tool", "tool_call_id": "call-1", "name": "lookup_invoice", "content": "paid"},
                {"role": "tool", "tool_call_id": "call-1", "name": "lookup_invoice", "content": "paid"},
                {"role": "assistant", "content": "not json"},
            ],
        }
        result = validate_tool_transcript(observation, self.arms["json"])
        self.assertTrue(any("tool_result_duplicate" in reason for reason in result.reasons))
        self.assertTrue(any("invalid_json" in reason for reason in result.reasons))

    def test_non_object_tool_call_and_missing_json_answer_are_rejected(self):
        native = native_transcript()
        native["turns"][2]["tool_calls"] = ["malformed"]
        result = validate_tool_transcript(native, self.arms["native"])
        self.assertTrue(any("tool_call_not_object" in reason for reason in result.reasons))

        json_observation = {
            "arm": "json",
            "stream_status": "complete",
            "finish_reason": "stop",
            "turns": [{"role": "assistant", "content": '{"used_tool_call_ids":[]}'}],
        }
        result = validate_tool_transcript(json_observation, self.arms["json"])
        self.assertTrue(any("json_final_field_missing" in reason for reason in result.reasons))

    def test_argument_schema_restrictions_are_recursive_and_fail_closed(self):
        custom_tool = {
            "name": "find_invoice",
            "description": "Find an invoice.",
            "parameters": {
                "type": "object",
                "required": ["invoice_id", "meta", "tags"],
                "properties": {
                    "invoice_id": {"type": "string", "enum": ["demo-001"], "maxLength": 8},
                    "meta": {
                        "type": "object",
                        "required": ["region"],
                        "properties": {"region": {"type": "string", "minLength": 2}},
                        "additionalProperties": False,
                    },
                    "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 2},
                },
                "additionalProperties": False,
            },
        }
        packet = build_comparison_packet(tool=custom_tool)
        arm = {item["mode"]: item for item in packet["arms"]}["native"]
        observation = {
            "arm": "native",
            "stream_status": "complete",
            "finish_reason": "stop",
            "turns": [
                {"role": "assistant", "tool_calls": [{"id": "call-1", "name": "find_invoice", "arguments": {"invoice_id": "other", "meta": {"region": "x"}, "tags": ["a", "b", "c"]}}]},
                {"role": "tool", "tool_call_id": "call-1", "name": "find_invoice", "content": "found"},
                {"role": "assistant", "content": "done", "used_tool_call_ids": ["call-1"]},
            ],
        }
        result = validate_tool_transcript(observation, arm)
        self.assertTrue(any("tool_argument_enum_invalid" in reason for reason in result.reasons))
        self.assertTrue(any("tool_argument_length_invalid" in reason for reason in result.reasons))

        invalid_tool = copy.deepcopy(custom_tool)
        invalid_tool["parameters"]["properties"]["invoice_id"]["minLength"] = "bad"
        with self.assertRaises(ValueError):
            build_comparison_packet(tool=invalid_tool)

    def test_non_json_enum_values_are_rejected_without_validator_exceptions(self):
        invalid_tool = copy.deepcopy(self.packet["tool"])
        invalid_tool["parameters"]["properties"]["invoice_id"]["enum"] = [{1, 2}]
        with self.assertRaises(ValueError):
            build_comparison_packet(tool=invalid_tool)

        packet = copy.deepcopy(self.packet)
        packet["tool"]["parameters"]["properties"]["invoice_id"]["enum"] = [{1, 2}]
        reasons = validate_packet(packet)
        self.assertIn("packet_not_json_serializable", reasons)

        packet = build_comparison_packet()
        packet["tool"]["parameters"]["properties"]["invoice_id"]["enum"] = [UserDict({"invoice_id": "demo-001"})]
        self.assertIsInstance(validate_packet(packet), list)

        packet = build_comparison_packet()
        packet["tool"]["parameters"]["properties"]["invoice_id"]["enum"] = [10**5000]
        self.assertIn("packet_not_json_serializable", validate_packet(packet))

        packet = build_comparison_packet()
        packet["prompt"] = "bad\ud800"
        self.assertIn("packet_not_json_serializable", validate_packet(packet))

    def test_cycles_are_rejected_at_public_boundaries_but_shared_nodes_are_allowed(self):
        packet = build_comparison_packet()
        cycle = []
        cycle.append(cycle)
        packet["tool"]["parameters"]["properties"]["invoice_id"]["enum"] = [cycle]
        self.assertIn("packet_not_json_serializable", validate_packet(packet))

        arm = copy.deepcopy(self.arms["native"])
        schema = arm["contract"]["tool_schema"]
        schema["properties"]["self"] = schema
        self.assertEqual(validate_tool_transcript(native_transcript(), arm).reasons, ("arm_not_json",))

        shared = {"type": "string"}
        tool = copy.deepcopy(self.packet["tool"])
        tool["parameters"]["required"] = []
        tool["parameters"]["properties"] = {"a": shared, "b": shared}
        self.assertEqual(validate_packet(build_comparison_packet(tool=tool)), [])

    def test_malformed_roles_and_contracts_return_reasons_without_exceptions(self):
        observation = native_transcript()
        observation["turns"][0]["role"] = []
        result = validate_tool_transcript(observation, self.arms["native"])
        self.assertTrue(any("role_invalid" in reason for reason in result.reasons))
        arm = copy.deepcopy(self.arms["native"])
        arm["contract"]["tool_schema"]["properties"]["invoice_id"]["minLength"] = "bad"
        result = validate_tool_transcript(native_transcript(), arm)
        self.assertIn("contract_tool_schema_invalid", result.reasons)

    def test_deep_json_values_fail_closed_before_recursive_consumers(self):
        nested = "leaf"
        for _ in range(MAX_JSON_DEPTH + 1):
            nested = {"x": nested}

        packet = copy.deepcopy(self.packet)
        packet["tool"]["parameters"]["properties"]["invoice_id"]["enum"] = [nested]
        self.assertEqual(validate_packet(packet), ["packet_not_json_serializable"])

        arm = copy.deepcopy(self.arms["native"])
        arm["contract"]["tool_schema"]["properties"]["invoice_id"]["enum"] = [nested]
        self.assertEqual(validate_tool_transcript(native_transcript(), arm).reasons, ("arm_not_json",))

    def test_builder_rejects_packet_depth_added_by_its_envelope(self):
        nested = "leaf"
        for _ in range(MAX_JSON_DEPTH - 8):
            nested = [nested]
        tool = {
            "name": "lookup_invoice",
            "description": "Look up one invoice.",
            "parameters": {
                "type": "object",
                "properties": {"payload": {"type": "array", "enum": [nested]}},
            },
        }
        with self.assertRaises(ValueError):
            build_comparison_packet(tool=tool)

    def test_json_envelope_normalizes_decoded_surrogates(self):
        native = native_transcript()
        native["turns"][2]["tool_calls"] = [
            {"id": "call-1", "name": "lookup_invoice", "arguments": {"invoice_id": "demo-001"}}
        ]
        observation = copy.deepcopy(native)
        observation["arm"] = "json"
        calls = observation["turns"][2].pop("tool_calls")
        observation["turns"][2]["content"] = json.dumps({"tool_calls": calls})
        observation["turns"][-1].pop("used_tool_call_ids")
        observation["turns"][-1]["content"] = (
            '{"answer":"\\ud800","used_tool_call_ids":["call-1"]}'
        )

        result = validate_tool_transcript(observation, self.arms["json"])
        self.assertFalse(result.valid)
        self.assertIn("turn[4]:json_not_json", result.reasons)


if __name__ == "__main__":
    unittest.main()
