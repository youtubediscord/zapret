import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from blockcheck.page_run_workflow import reset_blockcheck_running_ui, start_blockcheck_page_run
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
        self.assertEqual(
            page._mode_combo.property("screenReaderStateText"),
            "Режим BlockCheck, выбрано: Полная",
        )
        self.assertIn("Выберите глубину проверки", page._mode_combo.accessibleDescription())
        self.assertEqual(page._skip_failed_cb.accessibleName(), "Пропускать проблемные домены, выключено")
        self.assertEqual(
            page._skip_failed_cb.property("screenReaderStateText"),
            "Пропускать проблемные домены, выключено",
        )
        self.assertIn("DNS-заглушкой", page._skip_failed_cb.accessibleDescription())
        self.assertEqual(page._start_btn.accessibleName(), "Запустить BlockCheck")
        self.assertIn("анализ блокировок", page._start_btn.accessibleDescription())
        self.assertEqual(page._stop_btn.accessibleName(), "Остановить BlockCheck")
        self.assertIn("Остановить текущую проверку", page._stop_btn.accessibleDescription())
        self.assertEqual(page._domain_input.accessibleName(), "Пользовательский домен для BlockCheck")
        self.assertEqual(page._add_domain_btn.accessibleName(), "Добавить домен в BlockCheck")
        self.assertEqual(page._progress_bar.accessibleName(), "Ход BlockCheck: не выполняется")
        self.assertEqual(
            page._progress_bar.property("screenReaderStateText"),
            "Ход BlockCheck: не выполняется",
        )
        self.assertIn("Показывает", page._progress_bar.accessibleDescription())
        self.assertEqual(page._status_label.accessibleName(), "Статус BlockCheck: Готово")
        self.assertEqual(page._log_edit.accessibleName(), "Подробный лог BlockCheck")
        self.assertEqual(page._expand_log_btn.accessibleName(), "Развернуть лог BlockCheck")
        self.assertEqual(page._prepare_support_btn.accessibleName(), "Подготовить обращение по BlockCheck")

    def test_mode_combo_menu_items_are_named_for_screen_reader(self) -> None:
        with patch.object(BlockcheckPage, "_request_page_initial_state_load", lambda self: None):
            page = BlockcheckPage(
                blockcheck_feature=_FeatureStub(),
                diagnostics_feature=_FeatureStub(),
                dns_feature=_FeatureStub(),
                create_strategy_scan_worker=lambda *_args, **_kwargs: None,
            )
        self.addCleanup(page.deleteLater)
        create_menu = getattr(page._mode_combo, "_create_accessible_combo_menu", None)
        self.assertIsNotNone(create_menu)

        menu = create_menu()

        self.assertEqual(
            menu.view.item(0).data(Qt.ItemDataRole.AccessibleTextRole),
            "Режим BlockCheck: Быстрая, не выбран",
        )
        self.assertEqual(
            menu.view.item(1).data(Qt.ItemDataRole.AccessibleTextRole),
            "Режим BlockCheck: Полная, выбран",
        )

    def test_run_progress_bar_reads_running_state_for_screen_reader(self) -> None:
        progress_bar = _FakeProgressBar()

        start_blockcheck_page_run(
            blockcheck_feature=_RunFeatureStub(),
            mode="full",
            extra_domains=[],
            skip_preflight_failed=False,
            parent=None,
            run_runtime=_RunRuntimeStub(),
            table=_TableStub(),
            tcp_table=None,
            tcp_section_label=None,
            dpi_card=_WidgetStub(),
            log_edit=_LogEditStub(),
            start_button=_ButtonStub(),
            stop_button=_ButtonStub(),
            mode_combo=_ButtonStub(),
            skip_failed_checkbox=_ButtonStub(),
            progress_bar=progress_bar,
            status_label=_TextStub(),
            runtime_warnings_seen=set(),
            set_support_status=lambda _text: None,
            tr_fn=lambda _key, default: default,
            on_phase_changed=lambda *_args: None,
            on_test_result=lambda *_args: None,
            on_target_complete=lambda *_args: None,
            on_log=lambda *_args: None,
            on_run_log_started=lambda *_args: None,
            on_finished=lambda *_args: None,
        )

        self.assertEqual(progress_bar.accessibleName(), "Ход BlockCheck: выполняется")
        self.assertEqual(progress_bar.property("screenReaderStateText"), "Ход BlockCheck: выполняется")

        reset_blockcheck_running_ui(
            start_button=_ButtonStub(),
            stop_button=_ButtonStub(),
            mode_combo=_ButtonStub(),
            skip_failed_checkbox=_ButtonStub(),
            progress_bar=progress_bar,
        )

        self.assertEqual(progress_bar.accessibleName(), "Ход BlockCheck: не выполняется")
        self.assertEqual(progress_bar.property("screenReaderStateText"), "Ход BlockCheck: не выполняется")


class _SignalStub:
    def connect(self, _callback) -> None:
        pass


class _WorkerStub:
    def __init__(self) -> None:
        self.phase_changed = _SignalStub()
        self.test_result = _SignalStub()
        self.target_complete = _SignalStub()
        self.log_message = _SignalStub()
        self.run_log_started = _SignalStub()
        self.finished = _SignalStub()


class _RunFeatureStub:
    def create_blockcheck_worker(self, **_kwargs):
        return _WorkerStub()


class _RunRuntimeStub:
    def start_qobject_worker(self, *, parent, worker_factory) -> None:
        worker_factory(1)


class _TableStub:
    def setRowCount(self, _count: int) -> None:  # noqa: N802
        pass


class _WidgetStub:
    def setVisible(self, _visible: bool) -> None:  # noqa: N802
        pass


class _LogEditStub:
    def clear(self) -> None:
        pass


class _ButtonStub:
    def setEnabled(self, _enabled: bool) -> None:  # noqa: N802
        pass


class _TextStub:
    def setText(self, text: str) -> None:  # noqa: N802
        self.text = text


class _FakeProgressBar:
    def __init__(self) -> None:
        self.properties = {}
        self.accessible_name = ""
        self.accessible_description = ""

    def setVisible(self, _visible: bool) -> None:  # noqa: N802
        pass

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

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
