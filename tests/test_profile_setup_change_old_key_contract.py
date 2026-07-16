from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


class ProfileSetupChangeOldKeyContractTests(unittest.TestCase):
    """AC10: пара old→new persistent_key доезжает от profile_setup_page до
    `_refresh_profile_item_locally` через payload команды
    `profile_setup_changed` (поле `old_profile_key`, обратно-совместимое)."""

    def test_page_command_payload_contains_old_profile_key(self) -> None:
        from main.window_page_presenters import apply_profile_setup_change_for_method

        with patch("main.window_page_presenters.send_page_command", return_value=True) as send_command:
            apply_profile_setup_change_for_method(
                object(),
                "zapret2_mode",
                "name:Новое имя",
                "settings",
                profile_item=None,
                old_profile_key="name:Старое имя",
            )

        payload = send_command.call_args_list[0].args[3]
        self.assertEqual(payload["profile_key"], "name:Новое имя")
        self.assertEqual(payload["old_profile_key"], "name:Старое имя")

    def test_page_command_payload_defaults_old_key_to_profile_key(self) -> None:
        from main.window_page_presenters import apply_profile_setup_change_for_method

        with patch("main.window_page_presenters.send_page_command", return_value=True) as send_command:
            apply_profile_setup_change_for_method(
                object(),
                "zapret2_mode",
                "name:Профиль",
                "settings",
            )

        payload = send_command.call_args_list[0].args[3]
        self.assertEqual(payload["old_profile_key"], "name:Профиль")

    def test_apply_profile_setup_change_passes_old_and_new_keys(self) -> None:
        from profile.ui.preset_setup_page import PresetSetupPageBase

        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._replace_profile_item_locally = Mock(return_value=False)
        page._refresh_profile_item_locally = Mock()

        PresetSetupPageBase.handle_page_command(
            page,
            "profile_setup_changed",
            {
                "profile_key": "name:Новое имя",
                "change_kind": "settings",
                "old_profile_key": "name:Старое имя",
            },
        )

        page._refresh_profile_item_locally.assert_called_once_with("name:Старое имя", "name:Новое имя")

    def test_apply_profile_setup_change_replaces_item_by_old_key(self) -> None:
        from profile.ui.preset_setup_page import PresetSetupPageBase

        item = SimpleNamespace(key="name:Новое имя")
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._replace_profile_item_locally = Mock(return_value=True)
        page._clear_deferred_profile_payload_apply = Mock()
        page._refresh_profile_item_locally = Mock()

        PresetSetupPageBase.apply_profile_setup_change(
            page,
            "name:Новое имя",
            "settings",
            item,
            "name:Старое имя",
        )

        page._replace_profile_item_locally.assert_called_once_with("name:Старое имя", item)
        page._refresh_profile_item_locally.assert_not_called()

    def test_payload_without_old_key_behaves_as_before(self) -> None:
        from profile.ui.preset_setup_page import PresetSetupPageBase

        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._replace_profile_item_locally = Mock(return_value=False)
        page._refresh_profile_item_locally = Mock()

        PresetSetupPageBase.handle_page_command(
            page,
            "profile_setup_changed",
            {"profile_key": "name:Профиль", "change_kind": "settings"},
        )

        page._refresh_profile_item_locally.assert_called_once_with("name:Профиль", "name:Профиль")

    def test_emit_profile_changed_passes_old_key_kwarg_when_key_changed(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase

        callback = Mock()
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._on_profile_changed_callback = callback
        item = SimpleNamespace(key="name:Новое имя")

        ProfileSetupPageBase._emit_profile_changed(
            page,
            "name:Новое имя",
            "settings",
            item,
            old_profile_key="name:Старое имя",
        )

        callback.assert_called_once_with(
            "name:Новое имя",
            "settings",
            item,
            old_profile_key="name:Старое имя",
        )

    def test_emit_profile_changed_keeps_legacy_call_when_key_unchanged(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase

        callback = Mock()
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._on_profile_changed_callback = callback
        item = SimpleNamespace(key="name:Профиль")

        ProfileSetupPageBase._emit_profile_changed(
            page,
            "name:Профиль",
            "settings",
            item,
            old_profile_key="name:Профиль",
        )

        callback.assert_called_once_with("name:Профиль", "settings", item)


if __name__ == "__main__":
    unittest.main()
