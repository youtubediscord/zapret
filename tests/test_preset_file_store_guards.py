from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from core.paths import AppPaths
from presets.file_store import PresetFileStore
from settings.mode import ENGINE_WINWS2


class PresetFileStoreGuardTests(unittest.TestCase):
    def test_update_preset_skips_write_when_source_text_is_unchanged(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            user_dir = root / "presets" / "winws2"
            user_dir.mkdir(parents=True)
            preset_path = user_dir / "Default v5.txt"
            preset_path.write_text(
                "# Preset: Default v5\n--new\n--filter-tcp=443\n",
                encoding="utf-8",
            )
            store = PresetFileStore(AppPaths(user_root=root, local_root=root))

            with patch.object(
                store,
                "_write_source",
                side_effect=AssertionError("unchanged preset source must not be written"),
            ):
                manifest = store.update_preset(
                    ENGINE_WINWS2,
                    "Default v5.txt",
                    "# Preset: Default v5\r\n--new\r\n--filter-tcp=443\r\n",
                    None,
                )

        self.assertEqual(manifest.file_name, "Default v5.txt")


if __name__ == "__main__":
    unittest.main()
