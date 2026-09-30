import json
import tempfile
import unittest
from pathlib import Path

from tools.run_manifest import new_manifest, sha256_json, validate_manifest, write_manifest


class RunManifestTests(unittest.TestCase):
    def args(self):
        return dict(
            model="fixture",
            code_sha256="a" * 64,
            prompt_sha256="b" * 64,
            goldset_sha256="c" * 64,
            payload_sha256="d" * 64,
            options={"num_ctx": 32768},
            cache_state="cold",
        )

    def test_manifest_has_unique_ids_and_all_hashes(self):
        first, second = new_manifest(**self.args()), new_manifest(**self.args())
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertNotEqual(first["campaign_id"], second["campaign_id"])
        self.assertEqual(first["options_sha256"], sha256_json(self.args()["options"]))
        self.assertEqual(validate_manifest(first), [])

    def test_cache_state_is_enum(self):
        with self.assertRaises(ValueError):
            new_manifest(**{**self.args(), "cache_state": "maybe"})
        with self.assertRaises(ValueError):
            new_manifest(**{**self.args(), "cache_state": []})

    def test_hashes_and_ids_are_required(self):
        with self.assertRaises(ValueError):
            new_manifest(**{**self.args(), "code_sha256": "short"})
        with self.assertRaises(ValueError):
            new_manifest(**{**self.args(), "campaign_id": "same", "run_id": "same"})
        self.assertTrue(validate_manifest({"schema_version": "run-manifest-v1"}))

    def test_write_manifest_is_exclusive_and_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            manifest = new_manifest(**self.args())
            self.assertEqual(write_manifest(path, manifest), path)
            self.assertEqual(json.loads(path.read_text()), manifest)
            with self.assertRaises(FileExistsError):
                write_manifest(path, manifest)


if __name__ == "__main__":
    unittest.main()
