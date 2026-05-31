from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PyQt6.QtWidgets import QApplication

from presets.models import PresetManifest
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

    def test_duplicate_preset_switch_signal_is_not_emitted_for_same_file_name(self) -> None:
        store = PresetUiStore(
            ENGINE_WINWS2,
            preset_file_store=object(),
            selection_service=object(),
        )
        emitted: list[str] = []
        store.preset_switched.connect(lambda file_name: emitted.append(file_name))

        store.notify_preset_switched("Default v5.txt")
        store.notify_preset_switched("default V5.TXT")
        store.notify_preset_switched("Other.txt")

        self.assertEqual(emitted, ["Default v5.txt", "Other.txt"])

    def test_duplicate_identity_change_signal_is_not_emitted_for_same_file_state(self) -> None:
        with TemporaryDirectory() as temp_dir:
            preset_path = Path(temp_dir) / "Default v5.txt"
            preset_path.write_text("# Preset: Default v5\n--new\n", encoding="utf-8")

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
            store.preset_identity_changed.connect(lambda file_name: emitted.append(file_name))

            store.notify_preset_identity_changed("Default v5.txt")
            store.notify_preset_identity_changed("default V5.TXT")
            preset_path.write_text("# Preset: Renamed\n--new\n", encoding="utf-8")
            store.notify_preset_identity_changed("Default v5.txt")

        self.assertEqual(emitted, ["Default v5.txt", "Default v5.txt"])

    def test_refresh_does_not_emit_presets_changed_when_metadata_is_unchanged(self) -> None:
        manifests = [
            PresetManifest(
                file_name="Default v5.txt",
                name="Default v5",
                updated_at="1",
                kind="builtin",
            )
        ]

        class _PresetFileStore:
            def list_manifests(self, _engine):
                return list(manifests)

        class _SelectionService:
            def get_selected_file_name(self, _engine):
                return "Default v5.txt"

        store = PresetUiStore(
            ENGINE_WINWS2,
            _PresetFileStore(),
            selection_service=_SelectionService(),
        )
        emitted: list[str] = []
        store.presets_changed.connect(lambda: emitted.append("changed"))

        store.list_manifests()
        store.refresh()
        manifests.append(
            PresetManifest(
                file_name="Other.txt",
                name="Other",
                updated_at="1",
                kind="user",
            )
        )
        store.refresh()

        self.assertEqual(emitted, ["changed"])


if __name__ == "__main__":
    unittest.main()
