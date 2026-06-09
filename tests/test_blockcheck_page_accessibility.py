import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from blockcheck.ui.page import BlockcheckPage


class _FeatureStub:
    pass


class BlockcheckPageAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_main_tab_controls_are_named_for_screen_reader(self) -> None:
        with patch.object(BlockcheckPage, "_request_page_initial_state_load", lambda self: None):
            page = BlockcheckPage(
                blockcheck_feature=_FeatureStub(),
                diagnostics_feature=_FeatureStub(),
                dns_feature=_FeatureStub(),
                create_strategy_scan_worker=lambda *_args, **_kwargs: None,
            )
        self.addCleanup(page.deleteLater)

        self.assertEqual(page._tabs_pivot.accessibleName(), "Раздел BlockCheck, выбрано: BlockCheck")
        self.assertIn("BlockCheck, Подбор стратегии, Диагностика или DNS подмена", page._tabs_pivot.accessibleDescription())
        page._tabs_pivot.setCurrentItem(page.TAB_STRATEGY_SCAN)
        self.assertEqual(page._tabs_pivot.accessibleName(), "Раздел BlockCheck, выбрано: Подбор стратегии")
        self.assertEqual(
            page._tabs_pivot.property("screenReaderStateText"),
            "Раздел BlockCheck, выбрано: Подбор стратегии",
        )

        self.assertEqual(page._mode_combo.accessibleName(), "Режим BlockCheck, выбрано: Полная")
        self.assertIn("Выберите глубину проверки", page._mode_combo.accessibleDescription())
        self.assertEqual(page._skip_failed_cb.accessibleName(), "Пропускать проблемные домены, выключено")
        self.assertIn("DNS-заглушкой", page._skip_failed_cb.accessibleDescription())
        self.assertEqual(page._start_btn.accessibleName(), "Запустить BlockCheck")
        self.assertIn("анализ блокировок", page._start_btn.accessibleDescription())
        self.assertEqual(page._stop_btn.accessibleName(), "Остановить BlockCheck")
        self.assertIn("Остановить текущую проверку", page._stop_btn.accessibleDescription())
        self.assertEqual(page._domain_input.accessibleName(), "Пользовательский домен для BlockCheck")
        self.assertEqual(page._add_domain_btn.accessibleName(), "Добавить домен в BlockCheck")
        self.assertEqual(page._status_label.accessibleName(), "Статус BlockCheck: Готово")
        self.assertEqual(page._log_edit.accessibleName(), "Подробный лог BlockCheck")
        self.assertEqual(page._expand_log_btn.accessibleName(), "Развернуть лог BlockCheck")
        self.assertEqual(page._prepare_support_btn.accessibleName(), "Подготовить обращение по BlockCheck")


if __name__ == "__main__":
    unittest.main()
