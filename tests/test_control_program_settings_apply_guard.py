from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch


class ControlProgramSettingsApplyGuardTests(unittest.TestCase):
    def test_zapret1_marks_program_settings_snapshot_apply_in_progress(self) -> None:
        from presets.ui.control.zapret1 import page as zapret1_page

        page = SimpleNamespace(
            _cleanup_in_progress=False,
            auto_dpi_toggle=object(),
            gui_autostart_toggle=object(),
            hide_to_tray_toggle=object(),
            defender_toggle=object(),
            max_block_toggle=object(),
        )
        states: list[bool] = []

        def record_apply(*_args, **_kwargs) -> None:
            states.append(bool(getattr(page, "_program_settings_snapshot_apply_in_progress", False)))

        with patch.object(zapret1_page, "apply_program_settings_snapshot", side_effect=record_apply):
            zapret1_page.Zapret1ModeControlPage._apply_program_settings_snapshot(page, SimpleNamespace())

        self.assertEqual(states, [True])
        self.assertFalse(getattr(page, "_program_settings_snapshot_apply_in_progress", False))

    def test_zapret2_marks_program_settings_snapshot_apply_in_progress(self) -> None:
        from presets.ui.control.zapret2 import page as zapret2_page

        page = SimpleNamespace(
            _cleanup_in_progress=False,
            auto_dpi_toggle=object(),
            gui_autostart_toggle=object(),
            hide_to_tray_toggle=object(),
            defender_toggle=object(),
            max_block_toggle=object(),
        )
        states: list[bool] = []

        def record_apply(*_args, **_kwargs) -> None:
            states.append(bool(getattr(page, "_program_settings_snapshot_apply_in_progress", False)))

        with patch.object(zapret2_page, "apply_program_settings_snapshot", side_effect=record_apply):
            zapret2_page.Zapret2ModeControlPage._apply_program_settings_snapshot(page, SimpleNamespace())

        self.assertEqual(states, [True])
        self.assertFalse(getattr(page, "_program_settings_snapshot_apply_in_progress", False))


if __name__ == "__main__":
    unittest.main()
