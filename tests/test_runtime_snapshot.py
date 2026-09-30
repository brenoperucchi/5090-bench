import unittest

from tools.runtime_snapshot import MAX_JSON_DEPTH, SCHEMA_VERSION, normalize_snapshot, unknown_snapshot, validate_snapshot


class RuntimeSnapshotTests(unittest.TestCase):
    def test_missing_fields_are_explicit_unknown(self):
        self.assertEqual(normalize_snapshot(None)["status"], "unknown")
        snapshot = normalize_snapshot({})
        self.assertEqual(snapshot["schema_version"], SCHEMA_VERSION)
        self.assertEqual(snapshot["status"], "unknown")
        self.assertIsNone(snapshot["model"]["digest"])
        self.assertEqual(validate_snapshot(snapshot), [])

    def test_observed_fields_do_not_fill_unobserved_fields(self):
        snapshot = normalize_snapshot({"process": {"pid": 42}, "gpu": {"residency": "unknown"}})
        self.assertEqual(snapshot["status"], "known")
        self.assertEqual(snapshot["process"]["pid"], 42)
        self.assertIsNone(snapshot["process"]["listener"])

    def test_invalid_numeric_evidence_is_rejected(self):
        self.assertTrue(validate_snapshot({"process": {"pid": -1}}))
        with self.assertRaisesRegex(ValueError, "^snapshot_schema$"):
            normalize_snapshot({"process": {"pid": -1}})
        self.assertEqual(validate_snapshot(unknown_snapshot()), [])

    def test_runtime_sections_cover_process_server_model_gpu_evidence(self):
        snapshot = normalize_snapshot(
            {
                "captured_at": "2026-09-14T22:00:00Z",
                "process": {"pid": 42, "listener": {"address": "127.0.0.1", "port": 11434}, "binary_sha256": "a" * 64},
                "server": {"version": "fixture", "endpoint": "fixture-endpoint", "settings": {"num_parallel": 2}, "logs": ["fixture-log"]},
                "model": {"name": "fixture", "digest": "sha256:fixture", "layers": 32},
                "gpu": {"memory_used_bytes": 1, "memory_free_bytes": 2, "residency": "full", "spill": False},
            }
        )
        self.assertEqual(snapshot["status"], "known")
        self.assertEqual(validate_snapshot(snapshot), [])
        self.assertIsNone(snapshot["server"]["log_path"])

    def test_malformed_top_level_and_section_types_are_rejected(self):
        self.assertTrue(validate_snapshot({"schema_version": "runtime-snapshot-v0"}))
        self.assertTrue(validate_snapshot({"status": []}))
        self.assertTrue(validate_snapshot({"server": {"settings": 7}}))
        self.assertTrue(validate_snapshot({"gpu": {"memory_free_bytes": True}}))

    def test_schema_version_and_root_errors_are_stable(self):
        self.assertEqual(validate_snapshot([]), ["snapshot_not_object"])
        self.assertEqual(validate_snapshot(None), ["snapshot_not_object"])
        self.assertEqual(
            validate_snapshot({"schema_version": "runtime-snapshot-v0"}),
            ["snapshot_schema_version"],
        )
        with self.assertRaisesRegex(ValueError, "^snapshot_schema_version$"):
            normalize_snapshot({"schema_version": "runtime-snapshot-v0"})

    def test_normalizer_rejects_semantically_invalid_sections(self):
        with self.assertRaisesRegex(ValueError, "^snapshot_schema$"):
            normalize_snapshot({"process": {"pid": -1}})
        with self.assertRaisesRegex(ValueError, "^snapshot_schema$"):
            normalize_snapshot({"process": []})

    def test_unknown_schema_keys_are_rejected(self):
        cases = (
            {"procss": {"pid": 42}},
            {"process": {"pd": 42}},
        )
        for value in cases:
            with self.subTest(value=value):
                self.assertEqual(validate_snapshot(value), ["snapshot_schema"])
                with self.assertRaisesRegex(ValueError, "^snapshot_schema$"):
                    normalize_snapshot(value)

    def test_empty_capture_timestamp_is_rejected(self):
        value = {"captured_at": ""}
        self.assertEqual(validate_snapshot(value), ["snapshot_schema"])
        with self.assertRaisesRegex(ValueError, "^snapshot_schema$"):
            normalize_snapshot(value)

    def test_deep_and_cyclic_flexible_values_fail_closed(self):
        nested = "leaf"
        for _ in range(MAX_JSON_DEPTH + 1):
            nested = {"x": nested}
        self.assertEqual(validate_snapshot({"server": {"settings": nested}}), ["snapshot_not_json"])
        with self.assertRaisesRegex(ValueError, "^snapshot_not_json$"):
            normalize_snapshot({"server": {"settings": nested}})

        cycle = {}
        cycle["self"] = cycle
        self.assertEqual(validate_snapshot({"server": {"settings": cycle}}), ["snapshot_not_json"])
        with self.assertRaisesRegex(ValueError, "^snapshot_not_json$"):
            normalize_snapshot({"server": {"settings": cycle}})

    def test_invalid_root_is_not_absence(self):
        with self.assertRaisesRegex(ValueError, "^snapshot_not_object$"):
            normalize_snapshot([])

    def test_arbitrary_root_is_not_silently_unknown(self):
        with self.assertRaisesRegex(ValueError, "^snapshot_not_json$"):
            normalize_snapshot(object())


if __name__ == "__main__":
    unittest.main()
