import unittest

from tools.input_integrity import classify_input_integrity


class InputIntegrityTests(unittest.TestCase):
    def test_missing_server_evidence_is_unknown(self):
        result = classify_input_integrity(request_sent=True, server_tokenized=None)
        self.assertEqual(result.status, "unknown")

    def test_server_tokenization_and_delivery_are_distinct(self):
        tokenized = classify_input_integrity(request_sent=True, server_tokenized=True, response_complete=False)
        delivered = classify_input_integrity(request_sent=True, server_tokenized=True, response_complete=True)
        self.assertEqual(tokenized.status, "server_tokenized")
        self.assertEqual(delivered.status, "server_tokenized")
        self.assertIsNone(delivered.truncated)
        self.assertEqual(
            classify_input_integrity(request_sent=True, server_tokenized=True, truncated=False, response_complete=True).status,
            "delivered",
        )

    def test_truncation_takes_precedence(self):
        result = classify_input_integrity(request_sent=True, server_tokenized=True, truncated=True, response_complete=True)
        self.assertEqual(result.status, "truncated")

    def test_invalid_counts_are_rejected(self):
        with self.assertRaises(ValueError):
            classify_input_integrity(request_sent=True, server_tokenized=True, input_tokens_server=-1)


if __name__ == "__main__":
    unittest.main()
