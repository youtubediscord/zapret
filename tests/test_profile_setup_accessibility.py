import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from profile.ui.profile_setup_page import ProfileSetupPageBase


def _worker_stub(*_args, **_kwargs):
    return None


class ProfileSetupAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _make_page(self) -> ProfileSetupPageBase:
        return ProfileSetupPageBase(
            create_profile_setup_load_worker=_worker_stub,
            create_profile_list_file_load_worker=_worker_stub,
            create_profile_list_file_save_worker=_worker_stub,
            create_profile_list_file_validation_worker=_worker_stub,
            create_profile_settings_save_worker=_worker_stub,
            create_profile_raw_text_save_worker=_worker_stub,
            create_profile_enabled_save_worker=_worker_stub,
            create_profile_user_update_worker=_worker_stub,
            create_profile_user_delete_worker=_worker_stub,
            create_profile_strategy_apply_worker=_worker_stub,
            create_profile_strategy_feedback_save_worker=_worker_stub,
            open_profiles=lambda: None,
            open_root=lambda: None,
            on_profile_changed=lambda: None,
        )

    def test_main_controls_are_named_for_screen_reader(self) -> None:
        page = self._make_page()
        self.addCleanup(page.deleteLater)
        page._ensure_editor_tab_built()
        page._ensure_match_tab_built()

        self.assertEqual(page._enabled_checkbox.accessibleName(), "Profile, выключено")
        self.assertEqual(page._enabled_checkbox.property("screenReaderStateText"), "Profile, выключено")
        self.assertIn("Включает или отключает", page._enabled_checkbox.accessibleDescription())
        self.assertEqual(page._filter_combo.accessibleName(), "Тип списка profile, выбрано: Hostlist")
        self.assertEqual(page._filter_value.accessibleName(), "Файл списка profile")
        self.assertEqual(page._in_range_mode.accessibleName(), "Режим in-range, выбрано: a — всегда")
        self.assertEqual(page._out_range_mode.accessibleName(), "Режим out-range, выбрано: a — всегда")
        self.assertEqual(page._strategy_branch_combo.accessibleName(), "Ветка готовой стратегии, не выбрано")
        self.assertEqual(page._list_file_base_text.accessibleName(), "Базовая часть списка profile")
        self.assertEqual(page._list_file_text.accessibleName(), "Ваши записи списка profile")
        self.assertEqual(page._list_file_save_button.accessibleName(), "Сохранить список profile")
        self.assertEqual(page._match_text.accessibleName(), "Условия применения profile")
        self.assertEqual(page._raw_profile_text.accessibleName(), "Текст profile в текущем preset")
        self.assertEqual(page._raw_profile_save_button.accessibleName(), "Сохранить текст profile")
        self.assertEqual(page._work_button.accessibleName(), "Отметить стратегию как рабочую")
        self.assertEqual(page._notwork_button.accessibleName(), "Отметить стратегию как нерабочую")
        self.assertEqual(page._favorite_button.accessibleName(), "Добавить стратегию в избранное")
        self.assertEqual(page._clear_feedback_button.accessibleName(), "Убрать оценку стратегии")


if __name__ == "__main__":
    unittest.main()
