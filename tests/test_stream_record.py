import json
import unittest

from tools.stream_record import parse_stream


class StreamRecordTests(unittest.TestCase):
    def parse(self, *events):
        return parse_stream(json.dumps(event) for event in events)

    def test_empty_is_incomplete(self):
        self.assertEqual(parse_stream([])["status"], "incomplete")

    def test_partial_eof_is_incomplete(self):
        result = self.parse({"message": {"content": "partial"}, "done": False})
        self.assertEqual(result["status"], "incomplete")
        self.assertIsNone(result["task_success"])

    def test_api_error_payload_is_not_success(self):
        result = self.parse({"error": "model failed"})
        self.assertEqual(result["status"], "api_error")
        self.assertEqual(result["error"], "model failed")

    def test_null_error_is_conservatively_terminal(self):
        event = {"error": None}
        result = self.parse(event)
        self.assertEqual(result["status"], "api_error")
        self.assertEqual(result["raw_events"], [event])
        self.assertIsNone(result["task_success"])

    def test_empty_error_followed_by_done_retains_diagnostics(self):
        for error in (None, ""):
            with self.subTest(error=error):
                events = [{"error": error}, {"done": True}]
                result = self.parse(*events)
                self.assertEqual(result["status"], "invalid_stream")
                self.assertTrue(result["error"])
                self.assertIn("data after terminal event", result["error"])
                self.assertEqual(result["raw_events"], events)

    def test_iterator_exception_propagates(self):
        def broken_reader():
            yield '{"done":true}'
            raise OSError("reader failed")

        with self.assertRaisesRegex(OSError, "reader failed"):
            parse_stream(broken_reader())

    def test_malformed_json(self):
        result = parse_stream(['{"done":'])
        self.assertEqual(result["status"], "invalid_stream")
        self.assertEqual(result["raw_lines"], ['{"done":'])

    def test_deep_json_is_named_invalid_stream(self):
        result = parse_stream(["[" * 100000 + "]" * 100000])
        self.assertEqual(result["status"], "invalid_stream")
        self.assertIn("line 1: malformed JSON", result["validation_errors"])

    def test_nonobject(self):
        self.assertEqual(parse_stream(['[]'])["status"], "invalid_stream")

    def test_complete_preserves_events_and_metrics(self):
        events = [{"message": {"thinking": "reason", "content": "answer"}, "done": False},
                  {"done": True, "done_reason": "stop", "eval_count": 7}]
        result = self.parse(*events)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["raw_events"], events)
        self.assertEqual(result["metrics"]["eval_count"], 7)
        self.assertIsNone(result["task_success"])

    def test_tool_only_is_complete(self):
        event = {"message": {"tool_calls": [{"function": {"name": "lookup"}}]}, "done": True}
        result = self.parse(event)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["raw_events"], [event])

    def test_missing_metrics_are_none(self):
        result = self.parse({"done": True})
        self.assertTrue(all(value is None for value in result["metrics"].values()))
        self.assertIsNone(result["metrics_valid"])

    def test_malformed_metrics_invalidate_stream(self):
        result = self.parse({"done": True, "prompt_eval_count": "about 25k", "eval_duration": -1})
        self.assertEqual(result["status"], "invalid_stream")
        self.assertFalse(result["metrics_valid"])

    def test_error_and_done_is_api_error(self):
        self.assertEqual(self.parse({"done": True, "error": "failed"})["status"], "api_error")

    def test_events_after_terminal_are_invalid(self):
        for tail in ({"message": {"content": "late"}}, {"done": True}):
            with self.subTest(tail=tail):
                self.assertEqual(self.parse({"done": True}, tail)["status"], "invalid_stream")

    def test_done_requires_boolean(self):
        for value in (1, "true", None):
            with self.subTest(value=value):
                self.assertEqual(self.parse({"done": value})["status"], "invalid_stream")

    def test_length_is_transport_complete_only(self):
        result = self.parse({"done": True, "done_reason": "length"})
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["done_reason"], "length")
        self.assertIsNone(result["task_success"])

    def test_bytes_and_blank_lines(self):
        self.assertEqual(parse_stream([b"\n", b'{"done":true}\n'])["status"], "complete")

    def test_invalid_utf8(self):
        self.assertEqual(parse_stream([b"\xff"])["status"], "invalid_stream")


if __name__ == "__main__":
    unittest.main()
