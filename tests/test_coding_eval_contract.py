import unittest

from tools.coding_eval_contract import (
    build_coding_packet,
    classify_coding_result,
    validate_coding_packet,
    validate_coding_result,
    validate_coding_task,
)


HASH = "b" * 64


def task(task_id="task-1"):
    return {
        "task_id": task_id,
        "family": "functional",
        "language": "python",
        "prompt": "Write a function that adds two integers.",
        "expected": {"mode": "stdout", "value": "5\\n"},
        "sandbox": {
            "network": False,
            "filesystem": "ephemeral",
            "timeout_s": 10,
            "memory_limit_mb": 256,
        },
    }


def result(**overrides):
    value = {
        "schema_version": "coding-result-v1",
        "task_id": "task-1",
        "status": "pass",
        "candidate_sha256": HASH,
        "stdout_sha256": HASH,
        "stderr_sha256": None,
        "exit_code": 0,
        "duration_ms": 12,
        "sandbox_proof": {
            "network_blocked": True,
            "filesystem_ephemeral": True,
            "timeout_enforced": True,
            "memory_enforced": True,
        },
    }
    value.update(overrides)
    return value


class CodingEvalContractTests(unittest.TestCase):
    def test_task_and_packet_are_valid_but_non_executable(self):
        self.assertEqual(validate_coding_task(task()), [])
        packet = build_coding_packet(suite_id="suite-1", tasks=[task()])
        self.assertFalse(packet["can_execute"])
        self.assertEqual(validate_coding_packet(packet), [])

    def test_task_requires_safe_sandbox(self):
        unsafe = task()
        unsafe["sandbox"]["network"] = True
        self.assertEqual(validate_coding_task(unsafe), ["sandbox_network_must_be_disabled"])
        unsafe = task()
        unsafe["sandbox"]["filesystem"] = "workspace"
        self.assertEqual(validate_coding_task(unsafe), ["sandbox_filesystem_must_be_ephemeral"])

    def test_packet_rejects_duplicate_or_invalid_tasks(self):
        with self.assertRaisesRegex(ValueError, "duplicate_task_id"):
            build_coding_packet(suite_id="suite-1", tasks=[task(), task()])
        with self.assertRaisesRegex(ValueError, "tasks_must_not_be_empty"):
            build_coding_packet(suite_id="suite-1", tasks=[])
        self.assertEqual(
            validate_coding_packet({"schema_version": "coding-eval-packet-v1", "can_execute": True}),
            ["coding_packet_must_be_non_executable"],
        )

    def test_result_requires_complete_sandbox_proof(self):
        value = result()
        self.assertEqual(validate_coding_result(value), [])
        self.assertEqual(classify_coding_result(value), {"status": "usable", "reasons": []})
        value = result(sandbox_proof={
            "network_blocked": False,
            "filesystem_ephemeral": True,
            "timeout_enforced": True,
            "memory_enforced": True,
        })
        self.assertEqual(
            classify_coding_result(value),
            {"status": "sandbox_failed", "reasons": ["network_not_blocked"]},
        )

    def test_result_unknown_safety_is_not_usable(self):
        value = result(sandbox_proof={
            "network_blocked": True,
            "filesystem_ephemeral": True,
            "timeout_enforced": False,
            "memory_enforced": True,
        })
        self.assertEqual(
            classify_coding_result(value),
            {"status": "sandbox_unproven", "reasons": ["timeout_not_enforced"]},
        )
        self.assertEqual(
            classify_coding_result(result(status="inconclusive")),
            {"status": "inconclusive", "reasons": ["inconclusive"]},
        )

    def test_result_schema_and_hashes_fail_closed(self):
        value = result(candidate_sha256="bad")
        self.assertEqual(validate_coding_result(value), ["candidate_sha256_invalid"])
        value = result()
        value["sandbox_proof"]["extra"] = False
        self.assertEqual(validate_coding_result(value), ["sandbox_proof_invalid"])


if __name__ == "__main__":
    unittest.main()
