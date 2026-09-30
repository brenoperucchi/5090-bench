import json
import tempfile
import unittest
from pathlib import Path

from tools.ollama_stream_recorder import (
    TransportResponse,
    create_jsonl_writer,
    record_stream,
)


class OllamaStreamRecorderTests(unittest.TestCase):
    endpoint = "http://127.0.0.1:19999/api/chat"

    def response(self, lines, status_code=200):
        return lambda endpoint, request: TransportResponse(status_code, iter(lines))

    def record(self, lines, status_code=200, **kwargs):
        return record_stream(
            endpoint=self.endpoint,
            request_fields={"model": "fixture", "messages": [{"content": "secret"}]},
            transport=self.response(lines, status_code),
            run_id="run-7",
            campaign_id="campaign-a",
            **kwargs,
        )

    def test_complete_records_private_raw_data_and_redacts_public_data(self):
        event = {"message": {"content": "answer"}, "done": True, "eval_count": 2}
        result = self.record([json.dumps(event)])

        self.assertEqual(result.public["status"], "complete")
        self.assertEqual(result.public["http_status"], 200)
        self.assertNotIn("run-7", json.dumps(result.public))
        self.assertEqual(result.private["request_fields"]["messages"][0]["content"], "secret")
        self.assertEqual(result.private["parsed_stream"]["raw_events"], [event])
        self.assertNotIn(self.endpoint, json.dumps(result.public))
        self.assertIn("endpoint_sha256", result.public)
        for forbidden in ('"request_fields":', "raw_events", "raw_lines", "command", "answer"):
            self.assertNotIn(forbidden, json.dumps(result.public))

    def test_partial_eof_is_persisted_as_incomplete(self):
        result = self.record([json.dumps({"done": False})])
        self.assertEqual(result.public["status"], "incomplete")
        self.assertEqual(result.public["parsed_stream"]["status"], "incomplete")

    def test_deep_malformed_json_is_not_mislabeled_as_transport_error(self):
        result = self.record(["[" * 100000 + "]" * 100000])
        self.assertEqual(result.public["status"], "invalid_stream")
        self.assertEqual(result.private["parsed_stream"]["status"], "invalid_stream")
        self.assertNotIn("transport_error", result.public)

    def test_api_error_is_persisted(self):
        result = self.record([json.dumps({"error": "private model unavailable"})], status_code=503)
        self.assertEqual(result.public["status"], "http_error")
        self.assertEqual(result.public["http_status"], 503)
        self.assertEqual(result.public["parsed_stream"]["status"], "api_error")
        self.assertNotIn("private model unavailable", json.dumps(result.public))
        self.assertEqual(result.private["parsed_stream"]["error"], "private model unavailable")

    def test_iterator_error_is_recorded_without_claiming_a_complete_stream(self):
        def broken():
            yield b'{"done": false}\n'
            raise OSError("socket closed")

        result = record_stream(
            endpoint=self.endpoint,
            request_fields={"model": "fixture", "prompt": "secret"},
            transport=lambda endpoint, request: TransportResponse(200, broken()),
            run_id="run-7",
            campaign_id="campaign-a",
        )
        self.assertEqual(result.public["status"], "transport_error")
        self.assertIsNone(result.public["parsed_stream"])
        self.assertEqual(result.public["transport_error"], {"type": "OSError"})
        self.assertNotIn("socket closed", json.dumps(result.public))
        self.assertEqual(result.private["transport_error"]["type"], "OSError")
        self.assertEqual(result.private["observed_raw_lines"], [b'{"done": false}\n'])

    def test_endpoint_is_required_and_has_no_implicit_default(self):
        with self.assertRaisesRegex(ValueError, "endpoint"):
            record_stream(
                endpoint="",
                request_fields={},
                transport=self.response([]),
                run_id="run-7",
                campaign_id="campaign-a",
            )

    def test_jsonl_paths_are_collision_safe_and_writer_is_incremental(self):
        with tempfile.TemporaryDirectory() as directory:
            first = create_jsonl_writer(directory, "public")
            second = create_jsonl_writer(directory, "public")
            self.assertNotEqual(first.path, second.path)
            first.write({"sequence": 1})
            first.write({"sequence": 2})
            first.close()
            second.close()
            self.assertEqual(
                [json.loads(line)["sequence"] for line in first.path.read_text().splitlines()],
                [1, 2],
            )

    def test_writers_keep_private_and_public_records_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            private = create_jsonl_writer(directory, "private")
            public = create_jsonl_writer(directory, "public")
            result = self.record([json.dumps({"done": True})], private_writer=private, public_writer=public)
            private.close()
            public.close()
            public_text = public.path.read_text()
            private_text = private.path.read_text()
            self.assertIn(result.public["record_id"], public_text)
            self.assertIn("secret", private_text)
            self.assertNotIn("secret", public_text)
            self.assertNotIn("raw_events", public_text)

    def test_non_success_http_status_cannot_be_complete(self):
        result = self.record([json.dumps({"done": True})], status_code=500)
        self.assertEqual(result.public["status"], "http_error")
        self.assertEqual(result.public["http_status"], 500)
        self.assertEqual(result.private["parsed_stream"]["status"], "complete")

    def test_invalid_http_status_is_private_and_public_status_is_null(self):
        for invalid in ("CANARY_PRIVATE_HTTP_STATUS", {"secret": "CANARY_PRIVATE_HTTP_STATUS"}, True, False):
            with self.subTest(invalid=invalid):
                result = self.record([json.dumps({"done": True})], status_code=invalid)
                self.assertEqual(result.public["status"], "http_error")
                self.assertIsNone(result.public["http_status"])
                self.assertEqual(result.private["http_status"], invalid)
                self.assertNotIn("CANARY_PRIVATE_HTTP_STATUS", json.dumps(result.public))

    def test_invalid_http_status_stays_private_in_persisted_public_jsonl(self):
        with tempfile.TemporaryDirectory() as directory:
            private = create_jsonl_writer(directory, "private")
            public = create_jsonl_writer(directory, "public")
            result = self.record(
                [json.dumps({"done": True})],
                status_code={"secret": "CANARY_PRIVATE_HTTP_STATUS"},
                private_writer=private,
                public_writer=public,
            )
            private.close()
            public.close()
            public_text = public.path.read_text()
            private_text = private.path.read_text()
            self.assertNotIn("CANARY_PRIVATE_HTTP_STATUS", public_text)
            self.assertIn("CANARY_PRIVATE_HTTP_STATUS", private_text)
            self.assertIsNone(result.public["http_status"])

    def test_invalid_http_status_and_iterator_error_preserve_transport_precedence(self):
        def broken():
            yield b'{"done": false}\n'
            raise OSError("socket closed")

        result = record_stream(
            endpoint=self.endpoint,
            request_fields={"model": "fixture"},
            transport=lambda endpoint, request: TransportResponse("CANARY_PRIVATE_HTTP_STATUS", broken()),
            run_id="run-7",
            campaign_id="campaign-a",
        )
        self.assertEqual(result.public["status"], "transport_error")
        self.assertIsNone(result.public["http_status"])
        self.assertEqual(result.private["http_status"], "CANARY_PRIVATE_HTTP_STATUS")
        self.assertEqual(result.public["transport_error"], {"type": "OSError"})

    def test_public_done_reason_is_an_allowlist(self):
        result = self.record([json.dumps({"done": True, "done_reason": "Bearer PRIVATE"})])
        self.assertEqual(result.public["parsed_stream"]["done_reason"], "other")
        self.assertNotIn("PRIVATE", json.dumps(result.public))

    def test_invalid_metric_value_is_not_public(self):
        result = self.record([json.dumps({"done": True, "eval_count": "PRIVATE_METRIC_CONTENT"})])
        self.assertEqual(result.public["parsed_stream"]["metrics"]["eval_count"], None)
        self.assertNotIn("PRIVATE_METRIC_CONTENT", json.dumps(result.public))
        self.assertEqual(result.private["parsed_stream"]["metrics"]["eval_count"], "PRIVATE_METRIC_CONTENT")

    def test_unhashable_done_reason_still_persists_result(self):
        with tempfile.TemporaryDirectory() as directory:
            private = create_jsonl_writer(directory, "private")
            public = create_jsonl_writer(directory, "public")
            result = self.record([json.dumps({"done": True, "done_reason": []})], private_writer=private, public_writer=public)
            private.close()
            public.close()
            self.assertEqual(result.public["parsed_stream"]["done_reason"], "other")
            self.assertIn('"record_type":"result"', public.path.read_text())
            self.assertEqual(result.private["parsed_stream"]["done_reason"], [])

    def test_transport_mutation_does_not_change_private_request_snapshot(self):
        def mutate(endpoint, request):
            request["messages"][0]["content"] = "changed"
            return TransportResponse(200, iter([json.dumps({"done": True})]))

        result = record_stream(
            endpoint=self.endpoint,
            request_fields={"messages": [{"content": "secret"}]},
            transport=mutate,
            run_id="run-7",
            campaign_id="campaign-a",
        )
        self.assertEqual(result.private["request_fields"]["messages"][0]["content"], "secret")


if __name__ == "__main__":
    unittest.main()
