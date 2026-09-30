import tempfile
import unittest
from pathlib import Path

from tools.public_artifact_scan import scan_paths


class PublicArtifactScanTests(unittest.TestCase):
    def test_safe_utf8_artifact_has_no_finding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "summary.json"
            path.write_text('{"status":"complete","event_count":1}', encoding="utf-8")
            self.assertEqual(scan_paths([path]), [])

    def test_canary_and_credentials_block_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unsafe.json"
            path.write_text("CANARY_PRIVATE_TOKEN\nauthorization: Bearer example\n", encoding="utf-8")
            self.assertEqual([item.rule for item in scan_paths([path])], ["test_canary", "authorization"])

    def test_json_credential_keys_block_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unsafe.jsonl"
            path.write_text('{"api_key":"example-secret-value"}\n{"password": "example-secret-value"}\n{"Authorization":"Basic ZXhhbXBsZQ=="}', encoding="utf-8")
            rules = [item.rule for item in scan_paths([path])]
            self.assertEqual(rules.count("credential_assignment"), 2)
            self.assertEqual(rules.count("authorization"), 1)

    def test_binary_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raw.bin"
            path.write_bytes(b"\xff")
            self.assertEqual(scan_paths([path])[0].rule, "unreadable_or_non_utf8:UnicodeDecodeError")


if __name__ == "__main__":
    unittest.main()
