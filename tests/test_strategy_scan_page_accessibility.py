import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from qfluentwidgets import CaptionLabel

from blockcheck import public as blockcheck_public
from blockcheck.ui.strategy_scan_page import StrategyScanPage
from blockcheck.ui.strategy_scan_page_results_workflow import (
    apply_finished_scan,
    apply_phase_change,
    apply_strategy_started_progress,
)


class _BlockcheckFeatureStub:
    build_selection_state = staticmethod(blockcheck_public.build_selection_state)
    build_protocol_ui_plan = staticmethod(blockcheck_public.build_protocol_ui_plan)
    build_udp_scope_hint_plan = staticmethod(blockcheck_public.build_udp_scope_hint_plan)
    build_idle_interaction_plan = staticmethod(blockcheck_public.build_idle_interaction_plan)
    build_running_interaction_plan = staticmethod(blockcheck_public.build_running_interaction_plan)
    plan_scan_start = staticmethod(blockcheck_public.plan_scan_start)


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
        self.assertEqual(page._progress_bar.accessibleName(), "Ход подбора стратегии: не выполняется")
        self.assertEqual(
            page._progress_bar.property("screenReaderStateText"),
            "Ход подбора стратегии: не выполняется",
        )
        self.assertIn("Показывает", page._progress_bar.accessibleDescription())
        self.assertEqual(page._status_label.accessibleName(), "Статус подбора стратегии: Готово к сканированию")
        self.assertEqual(page._table.accessibleName(), "Результаты подбора стратегии: пока нет результатов")
        self.assertEqual(
            page._table.property("screenReaderStateText"),
            "Результаты подбора стратегии: пока нет результатов",
        )
        self.assertEqual(page._log_edit.accessibleName(), "Подробный лог подбора стратегии: пока нет записей")
        self.assertEqual(
            page._log_edit.property("screenReaderStateText"),
            "Подробный лог подбора стратегии: пока нет записей",
        )
        self.assertEqual(page._expand_log_btn.accessibleName(), "Развернуть лог подбора стратегии")
        self.assertEqual(page._prepare_support_btn.accessibleName(), "Подготовить обращение по подбору стратегии")

    def test_protocol_combo_menu_items_are_named_for_screen_reader(self) -> None:
        page = StrategyScanPage(
            blockcheck_feature=_BlockcheckFeatureStub(),
            create_strategy_scan_worker=lambda *_args, **_kwargs: None,
        )
        self.addCleanup(page.deleteLater)
        create_menu = getattr(page._protocol_combo, "_create_accessible_combo_menu", None)
        self.assertIsNotNone(create_menu)

        menu = create_menu()

        self.assertEqual(
            menu.view.item(0).data(Qt.ItemDataRole.AccessibleTextRole),
            "Протокол подбора стратегии: TCP/HTTPS, выбран",
        )
        self.assertEqual(
            menu.view.item(1).data(Qt.ItemDataRole.AccessibleTextRole),
            "Протокол подбора стратегии: STUN Voice (Discord/Telegram), не выбран",
        )

    def test_runtime_status_updates_state_text_for_screen_reader(self) -> None:
        label = CaptionLabel("Готово к сканированию")

        apply_phase_change(status_label=label, phase="Проверяется стратегия TLS fake")

        self.assertEqual(label.text(), "Проверяется стратегия TLS fake")
        self.assertEqual(
            label.property("screenReaderStateText"),
            "Статус подбора стратегии: Проверяется стратегия TLS fake",
        )

    def test_progress_bar_reads_runtime_state_for_screen_reader(self) -> None:
        progress_bar = _FakeProgressBar()
        status_label = CaptionLabel()

        apply_strategy_started_progress(
            blockcheck_feature=_ProgressFeatureStub(),
            strategy_name="TLS fake",
            index=1,
            total=3,
            result_rows=[],
            progress_bar=progress_bar,
            status_label=status_label,
            scan_cursor=1,
        )

        self.assertEqual(progress_bar.accessibleName(), "Ход подбора стратегии: выполняется")
        self.assertEqual(progress_bar.property("screenReaderStateText"), "Ход подбора стратегии: выполняется")

        apply_finished_scan(
            blockcheck_feature=_ProgressFeatureStub(),
            finish_plan=SimpleNamespace(
                total_available=3,
                total_count=3,
                status_text="Подбор завершён",
                support_status_code="ready_after_error",
                cancelled=False,
            ),
            reset_ui=lambda: None,
            scan_protocol="tcp",
            progress_bar=progress_bar,
            status_label=status_label,
            set_support_status=lambda _text: None,
            parent_widget=None,
        )

        self.assertEqual(progress_bar.accessibleName(), "Ход подбора стратегии: не выполняется")
        self.assertEqual(progress_bar.property("screenReaderStateText"), "Ход подбора стратегии: не выполняется")

    def test_run_start_restores_empty_result_and_log_screen_reader_states(self) -> None:
        from ui.accessibility import set_state_text

        page = StrategyScanPage(
            blockcheck_feature=_BlockcheckFeatureStub(),
            create_strategy_scan_worker=lambda *_args, **_kwargs: _WorkerStub(),
        )
        self.addCleanup(page.deleteLater)
        page._strategy_scan_run_runtime = _RunRuntimeStub()
        set_state_text(page._table, "Старая строка подбора стратегии")
        set_state_text(page._log_edit, "Старый лог подбора стратегии")

        page._on_start()

        self.assertEqual(page._table.rowCount(), 0)
        self.assertEqual(page._table.accessibleName(), "Результаты подбора стратегии: пока нет результатов")
        self.assertEqual(
            page._table.property("screenReaderStateText"),
            "Результаты подбора стратегии: пока нет результатов",
        )
        self.assertEqual(page._log_edit.accessibleName(), "Подробный лог подбора стратегии: пока нет записей")
        self.assertEqual(
            page._log_edit.property("screenReaderStateText"),
            "Подробный лог подбора стратегии: пока нет записей",
        )


class _ProgressFeatureStub:
    def build_progress_plan(self, **_kwargs):
        return SimpleNamespace(total=3, status_text="Проверяется стратегия TLS fake")


class _SignalStub:
    def connect(self, _callback) -> None:
        pass


class _WorkerStub:
    def __init__(self) -> None:
        self.run_log_started = _SignalStub()
        self.strategy_started = _SignalStub()
        self.strategy_result = _SignalStub()
        self.scan_log = _SignalStub()
        self.phase_changed = _SignalStub()
        self.scan_finished = _SignalStub()


class _RunRuntimeStub:
    worker = None

    def is_running(self) -> bool:
        return False

    def start_qobject_worker(self, *, parent, worker_factory) -> None:
        self.worker = worker_factory(1)


class _FakeProgressBar:
    def __init__(self) -> None:
        self.properties = {}
        self.accessible_name = ""
        self.accessible_description = ""
        self._value = 0
        self._maximum = 100

    def setRange(self, _minimum: int, maximum: int) -> None:  # noqa: N802
        self._maximum = int(maximum)

    def value(self) -> int:
        return self._value

    def setValue(self, value: int) -> None:  # noqa: N802
        self._value = int(value)

    def maximum(self) -> int:
        return self._maximum

    def accessibleName(self) -> str:  # noqa: N802
        return self.accessible_name

    def setAccessibleName(self, text: str) -> None:  # noqa: N802
        self.accessible_name = str(text)

    def accessibleDescription(self) -> str:  # noqa: N802
        return self.accessible_description

    def setAccessibleDescription(self, text: str) -> None:  # noqa: N802
        self.accessible_description = str(text)

    def property(self, name: str) -> object:
        return self.properties.get(name)

    def setProperty(self, name: str, value: object) -> None:  # noqa: N802
        self.properties[name] = value


if __name__ == "__main__":
    unittest.main()
