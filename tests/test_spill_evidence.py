import unittest

from tools.spill_evidence import classify_spill_evidence, validate_spill_evidence


def role(
    *,
    layers_expected=40,
    layers_on_gpu=40,
    kv_location="gpu",
    attributed_memory_bytes=10_000,
    sources=None,
    model="fixture-model",
):
    return {
        "model": model,
        "layers_expected": layers_expected,
        "layers_on_gpu": layers_on_gpu,
        "kv_location": kv_location,
        "attributed_memory_bytes": attributed_memory_bytes,
        "sources": ["startup_log"] if sources is None else sources,
    }


def evidence(**target_overrides):
    target = role(**target_overrides)
    return {
        "schema_version": "spill-evidence-v1",
        "roles": {"target": target},
        "global_memory": {"used_bytes": 20_000, "free_bytes": 10_000},
    }


class SpillEvidenceTests(unittest.TestCase):
    def test_complete_target_proof_is_no_spill(self):
        value = evidence()
        self.assertEqual(validate_spill_evidence(value), [])
        self.assertEqual(
            classify_spill_evidence(value),
            {"status": "verified_no_spill", "reasons": []},
        )

    def test_draft_can_be_required_without_inference(self):
        value = evidence()
        value["roles"]["draft"] = role(model="fixture-draft", layers_expected=8, layers_on_gpu=8)
        self.assertEqual(validate_spill_evidence(value, required_roles=("target", "draft")), [])
        self.assertEqual(
            classify_spill_evidence(value, required_roles=("target", "draft"))["status"],
            "verified_no_spill",
        )

    def test_offloaded_layers_or_kv_are_spill(self):
        self.assertEqual(
            classify_spill_evidence(evidence(layers_on_gpu=39)),
            {"status": "spill_detected", "reasons": ["target_layers_offloaded"]},
        )
        self.assertEqual(
            classify_spill_evidence(evidence(kv_location="mixed")),
            {"status": "spill_detected", "reasons": ["target_kv_offloaded"]},
        )

    def test_missing_attribution_or_runner_source_is_unknown(self):
        value = evidence(attributed_memory_bytes=None, sources=["api_ps"])
        result = classify_spill_evidence(value)
        self.assertEqual(result["status"], "residency_unknown")
        self.assertEqual(
            result["reasons"],
            ["target_attributed_memory_unknown", "target_residency_source_unknown"],
        )
        self.assertEqual(
            classify_spill_evidence(evidence(kv_location="unknown"))["status"],
            "residency_unknown",
        )

    def test_global_memory_alone_cannot_prove_no_spill(self):
        value = evidence(attributed_memory_bytes=None, sources=["gpu_sample"])
        value["global_memory"] = {"used_bytes": 1, "free_bytes": 99_999_999}
        self.assertNotEqual(classify_spill_evidence(value)["status"], "verified_no_spill")

    def test_invalid_evidence_fails_closed(self):
        value = evidence()
        value["roles"]["target"]["layers_on_gpu"] = True
        self.assertEqual(
            validate_spill_evidence(value),
            ["target_layers_on_gpu_invalid"],
        )
        self.assertEqual(classify_spill_evidence(value)["status"], "invalid")

    def test_unknown_roles_and_missing_draft_are_rejected(self):
        value = evidence()
        value["roles"]["other"] = role()
        self.assertEqual(validate_spill_evidence(value), ["unknown_role"])
        self.assertEqual(
            validate_spill_evidence(value, required_roles=("target", "draft")),
            ["unknown_role"],
        )
        del value["roles"]["other"]
        self.assertEqual(
            validate_spill_evidence(value, required_roles=("target", "draft")),
            ["draft_missing"],
        )


if __name__ == "__main__":
    unittest.main()
