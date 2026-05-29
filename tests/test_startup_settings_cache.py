from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class StartupSettingsCacheTests(unittest.TestCase):
    def test_repeated_settings_getters_reuse_one_file_read(self) -> None:
        from settings import store as settings_store

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                settings_store.reset_settings()

                with patch.object(
                    settings_store,
                    "_read_settings_file_locked",
                    wraps=settings_store._read_settings_file_locked,
                ) as read_file:
                    self.assertEqual(settings_store.get_display_mode(), "dark")
                    self.assertEqual(settings_store.get_strategy_launch_method(), "zapret2_mode")
                    self.assertEqual(settings_store.get_window_opacity(), 100)

                self.assertLessEqual(read_file.call_count, 1)

    def test_settings_write_updates_cached_reads(self) -> None:
        from settings import store as settings_store

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                settings_store.reset_settings()
                self.assertEqual(settings_store.get_display_mode(), "dark")

                settings_store.set_display_mode("light")

                with patch.object(
                    settings_store,
                    "_read_settings_file_locked",
                    wraps=settings_store._read_settings_file_locked,
                ) as read_file:
                    self.assertEqual(settings_store.get_display_mode(), "light")

                self.assertEqual(read_file.call_count, 0)


if __name__ == "__main__":
    unittest.main()
