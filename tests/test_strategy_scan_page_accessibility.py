import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from blockcheck import public as blockcheck_public
from blockcheck.ui.strategy_scan_page import StrategyScanPage


class _BlockcheckFeatureStub:
    build_selection_state = staticmethod(blockcheck_public.build_selection_state)
    build_protocol_ui_plan = staticmethod(blockcheck_public.build_protocol_ui_plan)
    build_udp_scope_hint_plan = staticmethod(blockcheck_public.build_udp_scope_hint_plan)
    build_idle_interaction_plan = staticmethod(blockcheck_public.build_idle_interaction_plan)


class StrategyScanPageAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_main_controls_are_named_for_screen_reader(self) -> None:
        page = StrategyScanPage(
            blockcheck_feature=_BlockcheckFeatureStub(),
            create_strategy_scan_worker=lambda *_args, **_kwargs: None,
        )
        self.addCleanup(page.deleteLater)

        self.assertEqual(page._protocol_combo.accessibleName(), "Протокол подбора стратегии, выбрано: TCP/HTTPS")
        self.assertEqual(
            page._protocol_combo.property("screenReaderStateText"),
            "Протокол подбора стратегии, выбрано: TCP/HTTPS",
        )
        self.assertIn("тип соединения", page._protocol_combo.accessibleDescription())
        self.assertEqual(page._games_scope_combo.accessibleName(), "Охват UDP, выбрано: Все ipset (по умолчанию)")
        self.assertEqual(
            page._games_scope_combo.property("screenReaderStateText"),
            "Охват UDP, выбрано: Все ipset (по умолчанию)",
        )
        self.assertIn("UDP Games", page._games_scope_combo.accessibleDescription())
        self.assertEqual(page._mode_combo.accessibleName(), "Режим подбора стратегии, выбрано: Быстрый (30)")
        self.assertEqual(
            page._mode_combo.property("screenReaderStateText"),
            "Режим подбора стратегии, выбрано: Быстрый (30)",
        )
        self.assertIn("сколько стратегий", page._mode_combo.accessibleDescription())
        self.assertEqual(page._target_input.accessibleName(), "Цель подбора стратегии")
        self.assertIn("домен или STUN-цель", page._target_input.accessibleDescription())
        self.assertEqual(page._quick_domain_btn.accessibleName(), "Быстрый выбор цели")
        self.assertEqual(page._start_btn.accessibleName(), "Начать подбор стратегии")
        self.assertEqual(page._stop_btn.accessibleName(), "Остановить подбор стратегии")
        self.assertEqual(page._status_label.accessibleName(), "Статус подбора стратегии: Готово к сканированию")
        self.assertEqual(page._table.accessibleName(), "Результаты подбора стратегии")
        self.assertEqual(page._log_edit.accessibleName(), "Подробный лог подбора стратегии")
        self.assertEqual(page._expand_log_btn.accessibleName(), "Развернуть лог подбора стратегии")
        self.assertEqual(page._prepare_support_btn.accessibleName(), "Подготовить обращение по подбору стратегии")


if __name__ == "__main__":
    unittest.main()
