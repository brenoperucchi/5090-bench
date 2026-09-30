import hashlib
import json
import unittest
from pathlib import Path

from tools.detector_regression import (
    RULESET_ID,
    evaluate_case,
    fixture_hash,
    ruleset_hash,
    validate_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/detector-regression-v1.json"
REPORT = ROOT / "docs/en/evaluations/detector-regression-v1.md"


class DetectorRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_fixture_schema_and_cases_are_valid(self):
        validate_fixture(self.payload)
        self.assertEqual(self.payload["ruleset_id"], RULESET_ID)
        self.assertEqual(len(self.payload["cases"]), len({case["case_id"] for case in self.payload["cases"]}))

    def test_every_fixture_case_has_the_versioned_expected_named_outcome(self):
        for case in self.payload["cases"]:
            with self.subTest(case=case["case_id"]):
                result = evaluate_case(case)
                self.assertNotIn("auto_score", result)
                self.assertEqual(set(result["outcomes"]), set(case["expected"]))
                for name, expected in case["expected"].items():
                    self.assertEqual(result["outcomes"][name], expected)

    def test_tie_is_never_a_language_pass(self):
        case = next(case for case in self.payload["cases"] if case["case_id"] == "language-marker-poor-tie-is-indeterminate")
        self.assertNotEqual(evaluate_case(case)["outcomes"]["language"]["outcome"], "pass")

    def test_report_pins_current_fixture_and_ruleset_hashes(self):
        report = REPORT.read_text(encoding="utf-8")
        self.assertIn(RULESET_ID, report)
        self.assertIn(ruleset_hash(), report)
        self.assertIn(fixture_hash(FIXTURE), report)

    def test_fixture_is_sanitized(self):
        text = FIXTURE.read_text(encoding="utf-8").lower()
        for forbidden in ("@", "authorization", "bearer ", "sk-", "http://", "https://"):
            self.assertNotIn(forbidden, text)

    def test_detector_specific_schema_rejects_wrong_types(self):
        case = {"case_id": "bad-language", "input": {"expected_language": "pt", "response_text": []}, "expected": {"language": {"outcome": "indeterminate", "reason": "x"}}}
        with self.assertRaises(ValueError):
            validate_fixture({"ruleset_id": RULESET_ID, "cases": [case]})

    def test_promise_schema_rejects_unhashable_delivery_state_and_evaluator_fails_closed(self):
        for state in ([], {}):
            case = {
                "case_id": "bad-promise-state",
                "input": {
                    "promise": True,
                    "response_text": "ok",
                    "promise_contract": {"required_wording": "ok", "external_delivery_state": state},
                },
                "expected": {"promise": {"outcome": "indeterminate", "reason": "external_delivery_unknown"}},
            }
            with self.subTest(state=state):
                with self.assertRaises(ValueError):
                    validate_fixture({"ruleset_id": RULESET_ID, "cases": [case]})
                self.assertEqual(evaluate_case(case)["outcomes"]["promise"]["reason"], "external_delivery_unknown")

    def test_missing_promise_delivery_state_remains_unknown(self):
        case = {
            "case_id": "missing-promise-state",
            "input": {"promise": True, "response_text": "ok", "promise_contract": {"required_wording": "ok"}},
            "expected": {"promise": {"outcome": "indeterminate", "reason": "external_delivery_unknown"}},
        }
        validate_fixture({"ruleset_id": RULESET_ID, "cases": [case]})
        self.assertEqual(evaluate_case(case)["outcomes"]["promise"], case["expected"]["promise"])

    def test_escalation_unknown_is_indeterminate(self):
        case = {
            "case_id": "unknown-escalation",
            "input": {"expect_escalation": True, "observed_escalation": None},
            "expected": {"escalation": {"outcome": "indeterminate", "reason": "escalation_not_observed"}},
        }
        validate_fixture({"ruleset_id": RULESET_ID, "cases": [case]})
        self.assertEqual(evaluate_case(case)["outcomes"]["escalation"], case["expected"]["escalation"])

    def test_required_source_coverage_rejects_duplicate_requirements(self):
        case = {
            "case_id": "duplicate-required-source",
            "input": {
                "citation_contract": {"required": True, "required_count": 2, "required_source_ids": ["a", "a"], "sources": [{"source_id": "a", "literal_quote": "A", "finding_id": "F"}]},
                "citations": [{"source_id": "a", "quote": "A", "quote_hash": "559aead08264d5795d3909718cdd05abd49572e84fe55590eef31a88a08fdffd", "finding_id": "F"}] * 2,
            },
            "expected": {"citation": {"outcome": "fail", "reason": "required_source_ids_duplicate"}},
        }
        with self.assertRaises(ValueError):
            validate_fixture({"ruleset_id": RULESET_ID, "cases": [case]})
        self.assertEqual(evaluate_case(case)["outcomes"]["citation"]["reason"], "required_source_ids_duplicate")

    def test_nested_citation_schema_rejects_unusable_source(self):
        case = {"case_id": "bad-source", "input": {"citation_contract": {"required": True, "required_count": 1, "sources": [{"source_id": [], "literal_quote": "A", "finding_id": "F"}]}, "citations": []}, "expected": {"citation": {"outcome": "indeterminate", "reason": "citation_contract_unreadable"}}}
        with self.assertRaises(ValueError):
            validate_fixture({"ruleset_id": RULESET_ID, "cases": [case]})

    def test_citation_contract_rejects_unknown_required_source_and_duplicate_observation_fails(self):
        unknown_required = {
            "case_id": "unknown-required-source",
            "input": {
                "citation_contract": {"required": True, "required_count": 1, "required_source_ids": ["missing"], "sources": [{"source_id": "source-a", "literal_quote": "A", "finding_id": "F"}]},
                "citations": [],
            },
            "expected": {"citation": {"outcome": "indeterminate", "reason": "citation_contract_unreadable"}},
        }
        with self.assertRaises(ValueError):
            validate_fixture({"ruleset_id": RULESET_ID, "cases": [unknown_required]})
        duplicate = {
            "case_id": "duplicate-observed-source",
            "input": {
                "citation_contract": {"required": True, "required_count": 2, "required_source_ids": ["source-a", "source-b"], "sources": [{"source_id": "source-a", "literal_quote": "A", "finding_id": "F1"}, {"source_id": "source-b", "literal_quote": "B", "finding_id": "F2"}]},
                "citations": [
                    {"source_id": "source-a", "quote": "A", "quote_hash": hashlib.sha256(b"A").hexdigest(), "finding_id": "F1"},
                    {"source_id": "source-a", "quote": "A", "quote_hash": hashlib.sha256(b"A").hexdigest(), "finding_id": "F1"},
                ],
            },
            "expected": {"citation": {"outcome": "fail", "reason": "duplicate_citation_source_id"}},
        }
        validate_fixture({"ruleset_id": RULESET_ID, "cases": [duplicate]})
        self.assertEqual(evaluate_case(duplicate)["outcomes"]["citation"], duplicate["expected"]["citation"])

    def test_tool_contract_rejects_duplicate_arguments_and_unknown_expected_tool(self):
        duplicate_args = {
            "case_id": "duplicate-tool-args",
            "input": {"tool_contract": {"supported_tools": ["lookup"], "expected_calls": [{"name": "lookup", "required_arguments": ["id", "id"]}]}, "tool_calls": []},
            "expected": {"tool": {"outcome": "indeterminate", "reason": "tool_contract_unreadable"}},
        }
        with self.assertRaises(ValueError):
            validate_fixture({"ruleset_id": RULESET_ID, "cases": [duplicate_args]})
        unknown_tool = {
            "case_id": "unknown-expected-tool",
            "input": {"tool_contract": {"supported_tools": ["lookup"], "expected_calls": [{"name": "delete", "required_arguments": []}]}, "tool_calls": []},
            "expected": {"tool": {"outcome": "indeterminate", "reason": "tool_contract_unreadable"}},
        }
        with self.assertRaises(ValueError):
            validate_fixture({"ruleset_id": RULESET_ID, "cases": [unknown_tool]})


if __name__ == "__main__":
    unittest.main()
