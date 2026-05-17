from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from core.paths import AppPaths
from presets.file_store import PresetFileStore
from presets.mode_coordinator import PresetModeCoordinator
from presets.selection_service import PresetSelectionService
from settings.mode import DEFAULT_PRESET_FILE_NAME_BY_ENGINE, ENGINE_WINWS2, ZAPRET2_MODE
from settings.schema import SETTINGS_DIR_NAME, SETTINGS_FILE_NAME


class PresetSelectionDefaultsTests(unittest.TestCase):
    def test_first_start_selects_configured_default_preset_not_first_sorted_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            builtin_dir = root / "presets" / "winws2_builtin"
            builtin_dir.mkdir(parents=True)
            (builtin_dir / "A first alphabetically.txt").write_text(
                "# Preset: A first alphabetically\n--wf-tcp-out=80\n",
                encoding="utf-8",
            )
            default_file_name = DEFAULT_PRESET_FILE_NAME_BY_ENGINE[ENGINE_WINWS2]
            (builtin_dir / default_file_name).write_text(
                "# Preset: Default v1 (game filter)\n--wf-tcp-out=80\n",
                encoding="utf-8",
            )

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                store = PresetFileStore(AppPaths(user_root=root, local_root=root))
                selection = PresetSelectionService(store)
                coordinator = PresetModeCoordinator(AppPaths(user_root=root, local_root=root), selection, store)

                manifest = coordinator.get_selected_source_manifest(ZAPRET2_MODE)

                settings_path = root / SETTINGS_DIR_NAME / SETTINGS_FILE_NAME
                settings = json.loads(settings_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest.file_name, default_file_name)
        self.assertEqual(
            settings["program"]["selected_source_preset_file_name_winws2"],
            default_file_name,
        )

    def test_missing_saved_selection_is_replaced_with_configured_default_preset(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            builtin_dir = root / "presets" / "winws2_builtin"
            settings_dir = root / SETTINGS_DIR_NAME
            builtin_dir.mkdir(parents=True)
            settings_dir.mkdir(parents=True)
            default_file_name = DEFAULT_PRESET_FILE_NAME_BY_ENGINE[ENGINE_WINWS2]
            (builtin_dir / default_file_name).write_text(
                "# Preset: Default v1 (game filter)\n--wf-tcp-out=80\n",
                encoding="utf-8",
            )
            (settings_dir / SETTINGS_FILE_NAME).write_text(
                json.dumps(
                    {
                        "version": 1,
                        "program": {
                            "strategy_launch_method": ZAPRET2_MODE,
                            "selected_source_preset_file_name_winws2": "missing.txt",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                store = PresetFileStore(AppPaths(user_root=root, local_root=root))
                selection = PresetSelectionService(store)
                coordinator = PresetModeCoordinator(AppPaths(user_root=root, local_root=root), selection, store)

                manifest = coordinator.get_selected_source_manifest(ZAPRET2_MODE)

                settings_path = root / SETTINGS_DIR_NAME / SETTINGS_FILE_NAME
                settings = json.loads(settings_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest.file_name, default_file_name)
        self.assertEqual(
            settings["program"]["selected_source_preset_file_name_winws2"],
            default_file_name,
        )


if __name__ == "__main__":
    unittest.main()
