import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QTableWidget, QWidget
from qfluentwidgets import PushButton

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
        self.assertEqual(
            page._tabs_pivot.items[page.TAB_BLOCKCHECK].accessibleName(),
            "Раздел BlockCheck: BlockCheck, выбрано",
        )
        self.assertEqual(
            page._tabs_pivot.items[page.TAB_STRATEGY_SCAN].accessibleName(),
            "Раздел BlockCheck: Подбор стратегии, не выбрано",
        )
        page._tabs_pivot.setCurrentItem(page.TAB_STRATEGY_SCAN)
        self.assertEqual(page._tabs_pivot.accessibleName(), "Раздел BlockCheck, выбрано: Подбор стратегии")
        self.assertEqual(
            page._tabs_pivot.property("screenReaderStateText"),
            "Раздел BlockCheck, выбрано: Подбор стратегии",
        )
        self.assertEqual(
            page._tabs_pivot.items[page.TAB_BLOCKCHECK].accessibleName(),
            "Раздел BlockCheck: BlockCheck, не выбрано",
        )
        self.assertEqual(
            page._tabs_pivot.items[page.TAB_STRATEGY_SCAN].accessibleName(),
            "Раздел BlockCheck: Подбор стратегии, выбрано",
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
        self.assertEqual(page._start_btn.property("screenReaderStateText"), "Запустить BlockCheck")
        self.assertEqual(page._stop_btn.accessibleName(), "Остановить BlockCheck")
        self.assertIn("Остановить текущую проверку", page._stop_btn.accessibleDescription())
        self.assertEqual(page._stop_btn.property("screenReaderStateText"), "Остановить BlockCheck")
        self.assertEqual(page._domain_input.accessibleName(), "Пользовательский домен для BlockCheck")
        self.assertEqual(
            page._domain_input.property("screenReaderStateText"),
            "Пользовательский домен для BlockCheck",
        )
        self.assertEqual(page._add_domain_btn.accessibleName(), "Добавить домен в BlockCheck")
        self.assertEqual(
            page._add_domain_btn.property("screenReaderStateText"),
            "Добавить домен в BlockCheck",
        )
        self.assertEqual(page._progress_bar.accessibleName(), "Ход BlockCheck: не выполняется")
        self.assertEqual(
            page._progress_bar.property("screenReaderStateText"),
            "Ход BlockCheck: не выполняется",
        )
        self.assertIn("Показывает", page._progress_bar.accessibleDescription())
        self.assertEqual(page._status_label.accessibleName(), "Статус BlockCheck: Готово")
        page._ensure_run_output_ui()
        self.assertEqual(page._log_edit.accessibleName(), "Подробный лог BlockCheck: пока нет записей")
        self.assertEqual(
            page._log_edit.property("screenReaderStateText"),
            "Подробный лог BlockCheck: пока нет записей",
        )
        self.assertEqual(page._expand_log_btn.accessibleName(), "Развернуть лог BlockCheck")
        self.assertEqual(page._prepare_support_btn.accessibleName(), "Подготовить обращение по BlockCheck")
        self.assertEqual(
            page._support_status_label.property("screenReaderStateText"),
            "Статус обращения BlockCheck: нет статуса",
        )

    def test_blockcheck_section_labels_have_screen_reader_state(self) -> None:
        from blockcheck.ui.sections_build import build_actions_section, build_results_section

        actions = build_actions_section(
            tr_fn=lambda _key, default: default,
            strong_body_label_cls=QLabel,
            quick_actions_bar_cls=_ActionBarStub,
            content_parent=QWidget(),
            push_button_cls=PushButton,
            qta_module=None,
            on_start=lambda: None,
            on_stop=lambda: None,
        )
        results = build_results_section(
            tr_fn=lambda _key, default: default,
            settings_card_cls=_SettingsCardStub,
            strong_body_label_cls=QLabel,
            table_widget_cls=QTableWidget,
        )

        self.assertEqual(
            actions.title_label.property("screenReaderStateText"),
            "Раздел BlockCheck: Действия",
        )
        self.assertEqual(
            results.domains_section_label.property("screenReaderStateText"),
            "Раздел результатов BlockCheck: Часть 1: Проверка доменов (TLS + HTTP injection)",
        )
        self.assertEqual(
            results.tcp_section_label.property("screenReaderStateText"),
            "Раздел результатов BlockCheck: Часть 2: Проверка TCP 16-20KB",
        )

    def test_first_open_does_not_build_run_output_until_needed(self) -> None:
        with patch.object(BlockcheckPage, "_request_page_initial_state_load", lambda self: None):
            page = BlockcheckPage(
                blockcheck_feature=_FeatureStub(),
                diagnostics_feature=_FeatureStub(),
                dns_feature=_FeatureStub(),
                create_strategy_scan_worker=lambda *_args, **_kwargs: None,
            )
        self.addCleanup(page.deleteLater)

        self.assertIsNone(page._results_card)
        self.assertIsNone(page._dpi_card)
        self.assertIsNone(page._log_card)
        self.assertIsNone(page._table)
        self.assertIsNone(page._log_edit)

        page._ensure_run_output_ui()

        self.assertIsNotNone(page._results_card)
        self.assertIsNotNone(page._dpi_card)
        self.assertIsNotNone(page._log_card)
        self.assertIsNotNone(page._table)
        self.assertIsNotNone(page._log_edit)

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

    def test_run_start_restores_empty_result_table_screen_reader_states(self) -> None:
        results_table = _AccessibleTableStub()
        tcp_table = _AccessibleTableStub()

        start_blockcheck_page_run(
            blockcheck_feature=_RunFeatureStub(),
            mode="full",
            extra_domains=[],
            skip_preflight_failed=False,
            parent=None,
            run_runtime=_RunRuntimeStub(),
            table=results_table,
            tcp_table=tcp_table,
            tcp_section_label=_WidgetStub(),
            dpi_card=_WidgetStub(),
            log_edit=_LogEditStub(),
            start_button=_ButtonStub(),
            stop_button=_ButtonStub(),
            mode_combo=_ButtonStub(),
            skip_failed_checkbox=_ButtonStub(),
            progress_bar=_FakeProgressBar(),
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

        self.assertEqual(results_table.row_count, 0)
        self.assertEqual(results_table.accessibleName(), "Результаты BlockCheck по доменам: пока нет результатов")
        self.assertEqual(
            results_table.property("screenReaderStateText"),
            "Результаты BlockCheck по доменам: пока нет результатов",
        )
        self.assertEqual(tcp_table.row_count, 0)
        self.assertFalse(tcp_table.visible)
        self.assertEqual(tcp_table.accessibleName(), "Результаты TCP 16-20KB: пока нет результатов")
        self.assertEqual(
            tcp_table.property("screenReaderStateText"),
            "Результаты TCP 16-20KB: пока нет результатов",
        )


class _SignalStub:
    def connect(self, _callback) -> None:
        pass


class _ActionBarStub:
    def __init__(self, *_args, **_kwargs) -> None:
        self.buttons = []

    def add_button(self, button) -> None:
        self.buttons.append(button)


class _SettingsCardStub:
    def __init__(self, title: str) -> None:
        self.title = str(title)
        self.widgets = []

    def add_widget(self, widget) -> None:
        self.widgets.append(widget)


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


class _AccessibleTableStub:
    def __init__(self) -> None:
        self.row_count = -1
        self.visible = True
        self.properties = {}
        self.accessible_name = ""
        self.accessible_description = ""

    def setRowCount(self, count: int) -> None:  # noqa: N802
        self.row_count = int(count)

    def setVisible(self, visible: bool) -> None:  # noqa: N802
        self.visible = bool(visible)

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
