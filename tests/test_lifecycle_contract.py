import unittest

from tools.lifecycle_contract import (
    build_lifecycle_packet,
    detect_orphans,
    evaluate_restoration,
    validate_lifecycle_evidence,
    validate_lifecycle_packet,
)


HASH = "a" * 64


def process(pid, *, start_time="2026-09-15T12:00:00Z", executable="ollama"):
    return {
        "pid": pid,
        "start_time": start_time,
        "executable": executable,
        "executable_sha256": HASH,
    }


def evidence(*, final_processes=None, initial_residency="healthy", final_residency="healthy", initial_health="healthy", final_health="healthy"):
    return {
        "schema_version": "lifecycle-evidence-v1",
        "initial": {
            "processes": [process(100)],
            "endpoint_health": initial_health,
            "residency": initial_residency,
        },
        "auxiliary": {
            "processes": [process(200, executable="ollama-test")],
            "endpoint_health": "healthy",
            "residency": "healthy",
        },
        "final": {
            "processes": [process(100)] if final_processes is None else final_processes,
            "endpoint_health": final_health,
            "residency": final_residency,
        },
    }


class LifecycleContractTests(unittest.TestCase):
    def test_packet_is_explicitly_non_executable(self):
        packet = build_lifecycle_packet(
            campaign_id="campaign-test",
            production_endpoint="http://prod.example",
            auxiliary_endpoint="http://aux.example",
        )
        self.assertFalse(packet["can_execute"])
        self.assertEqual(validate_lifecycle_packet(packet), [])
        self.assertEqual([step["id"] for step in packet["steps"]], [1, 2, 3, 4, 5, 6])

    def test_packet_rejects_same_endpoint_or_bad_timeout(self):
        with self.assertRaisesRegex(ValueError, "endpoints must differ"):
            build_lifecycle_packet(
                campaign_id="campaign-test",
                production_endpoint="http://same.example",
                auxiliary_endpoint="http://same.example",
            )
        packet = build_lifecycle_packet(
            campaign_id="campaign-test",
            production_endpoint="http://prod.example",
            auxiliary_endpoint="http://aux.example",
        )
        packet["can_execute"] = True
        self.assertEqual(validate_lifecycle_packet(packet), ["packet_must_be_non_executable"])

    def test_evidence_requires_all_phases_and_process_identity(self):
        self.assertEqual(validate_lifecycle_evidence(evidence()), [])
        incomplete = evidence()
        del incomplete["final"]
        self.assertEqual(validate_lifecycle_evidence(incomplete), ["final_missing"])
        invalid = evidence()
        invalid["initial"]["processes"][0]["pid"] = True
        self.assertEqual(validate_lifecycle_evidence(invalid), ["initial_process_identity_invalid"])

    def test_orphans_are_reported_without_touching_processes(self):
        self.assertEqual(
            detect_orphans([process(100)], [process(100)], [process(200)]),
            [],
        )
        self.assertEqual(
            detect_orphans([process(100)], [process(100), process(201)], [process(200)]),
            [201],
        )
        self.assertEqual(
            detect_orphans([process(100)], [process(100), process(200)], [process(200)]),
            [200],
        )

    def test_restoration_is_verified_only_with_matching_state(self):
        self.assertEqual(evaluate_restoration(evidence()), {"status": "restored", "reasons": []})
        self.assertEqual(
            evaluate_restoration(evidence(final_processes=[process(100), process(201)]))["status"],
            "failed",
        )
        self.assertEqual(
            evaluate_restoration(evidence(final_residency="unknown")),
            {"status": "unknown", "reasons": ["residency_unknown"]},
        )
        self.assertEqual(
            evaluate_restoration(evidence(final_health="unhealthy")),
            {"status": "failed", "reasons": ["endpoint_unhealthy"]},
        )

    def test_invalid_or_unknown_evidence_never_reports_restored(self):
        self.assertEqual(
            evaluate_restoration(evidence(initial_residency="unhealthy")),
            {"status": "failed", "reasons": ["residency_not_restored"]},
        )
        malformed = evidence()
        malformed["initial"]["processes"][0]["executable_sha256"] = "bad"
        result = evaluate_restoration(malformed)
        self.assertEqual(result["status"], "invalid")


if __name__ == "__main__":
    unittest.main()
