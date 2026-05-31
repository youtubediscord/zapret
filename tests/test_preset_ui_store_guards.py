from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PyQt6.QtWidgets import QApplication

from presets.ui_store import PresetUiStore
from settings.mode import ENGINE_WINWS2


class PresetUiStoreGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_duplicate_content_change_signal_is_not_emitted_for_same_file_state(self) -> None:
        with TemporaryDirectory() as temp_dir:
            preset_path = Path(temp_dir) / "Default v5.txt"
            preset_path.write_text("--new\n--filter-tcp=443\n", encoding="utf-8")

            class _PresetFileStore:
                def get_source_path(self, _engine, _file_name):
                    return preset_path

                def list_manifests(self, _engine):
                    return []

            store = PresetUiStore(
                ENGINE_WINWS2,
                _PresetFileStore(),
                selection_service=object(),
            )
            emitted: list[str] = []
            store.preset_content_changed.connect(lambda file_name: emitted.append(file_name))

            store.notify_preset_content_changed("Default v5.txt")
            store.notify_preset_content_changed("Default v5.txt")
            preset_path.write_text("--new\n--filter-tcp=80\n", encoding="utf-8")
            store.notify_preset_content_changed("Default v5.txt")

        self.assertEqual(emitted, ["Default v5.txt", "Default v5.txt"])


if __name__ == "__main__":
    unittest.main()
