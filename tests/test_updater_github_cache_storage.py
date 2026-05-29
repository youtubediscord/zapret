from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class UpdaterGithubCacheStorageTests(unittest.TestCase):
    def test_normalize_settings_drops_legacy_github_cache_payload(self) -> None:
        from settings.normalize import normalize_settings
        from settings.schema import build_default_settings

        settings = build_default_settings()
        settings["updater"]["github_cache"] = {
            "https://api.github.test/releases": {
                "timestamp": 123,
                "content": [{"body": "x" * 10_000}],
            }
        }

        normalized = normalize_settings(settings)

        self.assertEqual(normalized["updater"]["github_cache"], {})

    def test_github_cache_is_saved_outside_settings_json(self) -> None:
        from settings import store as settings_store
        from updater import github_cache_storage

        cache_payload = {
            "https://api.github.test/releases": {
                "timestamp": 123.0,
                "content": [{"tag_name": "v1"}],
            }
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with (
                patch("settings.store.MAIN_DIRECTORY", str(root)),
                patch("updater.github_cache_storage.MAIN_DIRECTORY", str(root)),
            ):
                settings_store.reset_settings()
                github_cache_storage.save_github_cache(cache_payload)

                settings_data = json.loads((root / "settings" / "settings.json").read_text(encoding="utf-8"))
                self.assertEqual(settings_data["updater"]["github_cache"], {})
                self.assertEqual(github_cache_storage.load_github_cache(), cache_payload)


if __name__ == "__main__":
    unittest.main()
