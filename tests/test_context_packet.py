import hashlib
import unittest

from tools.context_packet import (
    CONTEXT,
    KEEP,
    TARGET_EFFECTIVE_INPUT,
    build_arm,
    canonical_json,
    predicted_limits,
    serialized_request_sha256,
    wire_payload,
)


class ContextPacketTests(unittest.TestCase):
    def test_preregistered_predictions(self):
        self.assertEqual(predicted_limits(parallel=2), {"law_a_limit": 16384, "law_b_limit": 16386})
        self.assertEqual(predicted_limits(parallel=1), {"law_a_limit": 32768, "law_b_limit": 16386})

    def test_arms_hold_wire_payload_constant_except_parallel_metadata(self):
        one, two = build_arm(parallel=1), build_arm(parallel=2)
        self.assertEqual(wire_payload(one), wire_payload(two))
        self.assertEqual(one["messages"], two["messages"])
        self.assertEqual(one["options"], two["options"])
        self.assertEqual(one["packet"]["process_num_parallel"], 1)
        self.assertIsNone(one["packet"]["effective_input_tokens"])
        self.assertFalse(one["packet"]["can_execute"])
        self.assertNotEqual(canonical_json(one), canonical_json(two))

    def test_payload_and_prompt_hashes_are_deterministic(self):
        arm = build_arm(parallel=1)
        self.assertEqual(arm["options"], {"num_ctx": CONTEXT, "num_predict": 1, "num_keep": KEEP, "temperature": 0})
        self.assertEqual(arm["think"], False)
        self.assertEqual(arm["packet"]["sentinels"]["count"], TARGET_EFFECTIVE_INPUT)
        self.assertEqual(arm["packet"]["sentinels"]["first"], "CTX_SENTINEL_000000")
        self.assertEqual(arm["packet"]["sentinels"]["last"], "CTX_SENTINEL_039999")
        self.assertEqual(arm["packet"]["serialized_request_sha256"], serialized_request_sha256(arm))
        self.assertEqual(
            arm["packet"]["serialized_request_sha256"],
            hashlib.sha256(canonical_json(wire_payload(arm))).hexdigest(),
        )

    def test_packet_declares_unknown_runtime_counters_and_validity_checks(self):
        packet = build_arm(parallel=2)["packet"]
        self.assertIsNone(packet["counters"]["server_prompt_eval_count"])
        self.assertIsNone(packet["counters"]["truncated"])
        self.assertIn("gpu_residency_before", packet["validity_checks"])
        self.assertIn("restoration_verified", packet["validity_checks"])

    def test_invalid_parallel_and_token_units_are_rejected(self):
        with self.assertRaises(ValueError):
            predicted_limits(parallel=True)
        with self.assertRaises(ValueError):
            predicted_limits(parallel=1, context=True)


if __name__ == "__main__":
    unittest.main()
