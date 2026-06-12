import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget
from PyQt6.QtWidgets import QListWidget
from qfluentwidgets import BodyLabel, CaptionLabel, ComboBox, LineEdit, PushButton, TransparentToolButton

from orchestra.ui.blocked_page import BlockedDomainRow, OrchestraBlockedPage
from orchestra.ui.locked_page import LockedDomainRow, OrchestraLockedPage
from orchestra.ui.page import OrchestraPage
from orchestra.ui.page_build import build_orchestra_log_card, build_orchestra_log_history_card, build_orchestra_status_card
from orchestra.ui.page_runtime_helpers import protocol_filter_items, set_protocol_filter_items
from orchestra.ui.ratings_page import OrchestraRatingsPage
from orchestra.ui.settings_page import OrchestraSettingsPage
from orchestra.ui.whitelist_page import OrchestraWhitelistPage, WhitelistDomainRow


class _OrchestraFeatureStub:
    ASKEY_ALL = ("tcp", "udp")


class _DialogButton:
    def __init__(self) -> None:
        self._accessible_name = ""
        self._accessible_description = ""

    def accessibleName(self) -> str:  # noqa: N802
        return self._accessible_name

    def setAccessibleName(self, text: str) -> None:  # noqa: N802
        self._accessible_name = str(text)

    def accessibleDescription(self) -> str:  # noqa: N802
        return self._accessible_description

    def setAccessibleDescription(self, text: str) -> None:  # noqa: N802
        self._accessible_description = str(text)


class _MessageBox:
    instances: list["_MessageBox"] = []

    def __init__(self, title: str, body: str, parent=None) -> None:
        self.title = title
        self.body = body
        self.parent = parent
        self.yesButton = _DialogButton()
        self.cancelButton = _DialogButton()
        self.exec_called = False
        _MessageBox.instances.append(self)

    def exec(self) -> bool:
        self.exec_called = True
        return False


class OrchestraAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        self.app.closeAllWindows()
        self.app.processEvents()

    def test_settings_tabs_items_read_name_and_selection_for_screen_reader(self) -> None:
        page = OrchestraSettingsPage(orchestra_feature=_OrchestraFeatureStub())
        self.addCleanup(page.deleteLater)

        self.assertEqual(
            page.pivot.items["locked"].accessibleName(),
            "Настройки Оркестратора: Залоченные, выбрано",
        )
        self.assertEqual(
            page.pivot.items["blocked"].accessibleName(),
            "Настройки Оркестратора: Заблокированные, не выбрано",
        )

        page.pivot.setCurrentItem("blocked")

        self.assertEqual(
            page.pivot.items["locked"].accessibleName(),
            "Настройки Оркестратора: Залоченные, не выбрано",
        )
        self.assertEqual(
            page.pivot.items["blocked"].accessibleName(),
            "Настройки Оркестратора: Заблокированные, выбрано",
        )

    def test_locked_page_main_controls_are_named_for_screen_reader(self) -> None:
        page = OrchestraLockedPage(orchestra_feature=_OrchestraFeatureStub())
        self.addCleanup(page.deleteLater)

        self.assertEqual(page.domain_input.accessibleName(), "Домен для залочки стратегии")
        self.assertIn("example.com", page.domain_input.accessibleDescription())
        self.assertEqual(page.proto_combo.accessibleName(), "Протокол залочки стратегии, выбрано: TCP")
        self.assertEqual(
            page.proto_combo.property("screenReaderStateText"),
            "Протокол залочки стратегии, выбрано: TCP",
        )
        self.assertIn("TCP или UDP", page.proto_combo.accessibleDescription())
        create_menu = getattr(page.proto_combo, "_create_accessible_combo_menu", None)
        self.assertIsNotNone(create_menu)
        menu = create_menu()
        self.addCleanup(menu.deleteLater)
        self.assertEqual(
            menu.view.item(0).data(Qt.ItemDataRole.AccessibleTextRole),
            "Протокол залочки стратегии: TCP, выбран",
        )
        self.assertEqual(
            menu.view.item(1).data(Qt.ItemDataRole.AccessibleTextRole),
            "Протокол залочки стратегии: UDP, не выбран",
        )
        self.assertEqual(page.strat_spin.accessibleName(), "Номер стратегии для залочки, выбрано: 1")
        self.assertEqual(
            page.strat_spin.property("screenReaderStateText"),
            "Номер стратегии для залочки, выбрано: 1",
        )
        self.assertEqual(page.lock_btn.accessibleName(), "Залочить стратегию для домена")
        self.assertEqual(page.lock_btn.property("screenReaderStateText"), "Залочить стратегию для домена")
        self.assertEqual(page.search_input.accessibleName(), "Поиск по залоченным доменам")
        self.assertEqual(page.search_input.property("screenReaderStateText"), "Поиск по залоченным доменам")
        self.assertIn("После ввода перейдите к списку клавишей Tab", page.search_input.accessibleDescription())
        self.assertIn("или нажмите Стрелка вниз", page.search_input.accessibleDescription())
        self.assertEqual(page.refresh_btn.accessibleName(), "Обновить список залоченных стратегий")
        self.assertEqual(
            page.refresh_btn.property("screenReaderStateText"),
            "Обновить список залоченных стратегий",
        )
        self.assertEqual(page.unlock_all_btn.accessibleName(), "Разлочить все стратегии")
        self.assertEqual(page.unlock_all_btn.property("screenReaderStateText"), "Разлочить все стратегии")

        page.proto_combo.setCurrentIndex(1)
        page.strat_spin.setValue(7)

        self.assertEqual(page.proto_combo.accessibleName(), "Протокол залочки стратегии, выбрано: UDP")
        self.assertEqual(
            page.proto_combo.property("screenReaderStateText"),
            "Протокол залочки стратегии, выбрано: UDP",
        )
        self.assertEqual(page.strat_spin.accessibleName(), "Номер стратегии для залочки, выбрано: 7")
        self.assertEqual(
            page.strat_spin.property("screenReaderStateText"),
            "Номер стратегии для залочки, выбрано: 7",
        )

    def test_locked_search_arrow_down_moves_focus_to_first_visible_row(self) -> None:
        page = OrchestraLockedPage(orchestra_feature=_OrchestraFeatureStub())
        self.addCleanup(page.deleteLater)
        row = LockedDomainRow("example.com", 3, "tcp", page.rows_container)
        page.rows_layout.addWidget(row)
        page._domain_rows["example.com:tcp"] = row
        page.show()
        self.app.processEvents()
        page.search_input.setFocus()
        self.app.processEvents()

        QTest.keyClick(page.search_input, Qt.Key.Key_Down)
        self.app.processEvents()

        self.assertIs(self.app.focusWidget(), row.strat_spin)

    def test_blocked_page_main_controls_are_named_for_screen_reader(self) -> None:
        page = OrchestraBlockedPage(orchestra_feature=_OrchestraFeatureStub())
        self.addCleanup(page.deleteLater)

        self.assertEqual(page.domain_input.accessibleName(), "Домен для блокировки стратегии")
        self.assertIn("example.com", page.domain_input.accessibleDescription())
        self.assertEqual(page.proto_combo.accessibleName(), "Протокол блокировки стратегии, выбрано: TCP")
        self.assertEqual(
            page.proto_combo.property("screenReaderStateText"),
            "Протокол блокировки стратегии, выбрано: TCP",
        )
        create_menu = getattr(page.proto_combo, "_create_accessible_combo_menu", None)
        self.assertIsNotNone(create_menu)
        menu = create_menu()
        self.addCleanup(menu.deleteLater)
        self.assertEqual(
            menu.view.item(0).data(Qt.ItemDataRole.AccessibleTextRole),
            "Протокол блокировки стратегии: TCP, выбран",
        )
        self.assertEqual(
            menu.view.item(1).data(Qt.ItemDataRole.AccessibleTextRole),
            "Протокол блокировки стратегии: UDP, не выбран",
        )
        self.assertEqual(page.strat_spin.accessibleName(), "Номер блокируемой стратегии, выбрано: 1")
        self.assertEqual(
            page.strat_spin.property("screenReaderStateText"),
            "Номер блокируемой стратегии, выбрано: 1",
        )
        self.assertEqual(page.block_btn.accessibleName(), "Заблокировать стратегию для домена")
        self.assertEqual(page.block_btn.property("screenReaderStateText"), "Заблокировать стратегию для домена")
        self.assertEqual(page.search_input.accessibleName(), "Поиск по заблокированным доменам")
        self.assertEqual(page.search_input.property("screenReaderStateText"), "Поиск по заблокированным доменам")
        self.assertIn(
            "После ввода перейдите к списку клавишей Tab",
            page.search_input.accessibleDescription(),
        )
        self.assertIn("или нажмите Стрелка вниз", page.search_input.accessibleDescription())
        self.assertEqual(page.refresh_btn.accessibleName(), "Обновить чёрный список стратегий")
        self.assertEqual(page.refresh_btn.property("screenReaderStateText"), "Обновить чёрный список стратегий")
        self.assertEqual(page.unblock_all_btn.accessibleName(), "Очистить пользовательские блокировки")
        self.assertEqual(
            page.unblock_all_btn.property("screenReaderStateText"),
            "Очистить пользовательские блокировки",
        )

        page.proto_combo.setCurrentIndex(1)
        page.strat_spin.setValue(9)

        self.assertEqual(page.proto_combo.accessibleName(), "Протокол блокировки стратегии, выбрано: UDP")
        self.assertEqual(
            page.proto_combo.property("screenReaderStateText"),
            "Протокол блокировки стратегии, выбрано: UDP",
        )
        self.assertEqual(page.strat_spin.accessibleName(), "Номер блокируемой стратегии, выбрано: 9")
        self.assertEqual(
            page.strat_spin.property("screenReaderStateText"),
            "Номер блокируемой стратегии, выбрано: 9",
        )

    def test_blocked_search_arrow_down_moves_focus_to_first_visible_user_row(self) -> None:
        page = OrchestraBlockedPage(orchestra_feature=_OrchestraFeatureStub())
        self.addCleanup(page.deleteLater)
        row = BlockedDomainRow("blocked.example", 5, "udp", is_default=False, parent=page.rows_container)
        page.rows_layout.addWidget(row)
        page._blocked_rows.append(row)
        page.show()
        self.app.processEvents()
        page.search_input.setFocus()
        self.app.processEvents()

        QTest.keyClick(page.search_input, Qt.Key.Key_Down)
        self.app.processEvents()

        self.assertIs(self.app.focusWidget(), row.strat_spin)

    def test_whitelist_page_main_controls_are_named_for_screen_reader(self) -> None:
        page = OrchestraWhitelistPage(orchestra_feature=_OrchestraFeatureStub())
        self.addCleanup(page.deleteLater)

        self.assertEqual(page.restart_warning.accessibleName(), "Предупреждение: изменения белого списка применятся после перезапуска оркестратора")
        self.assertEqual(
            page.restart_warning.property("screenReaderStateText"),
            "Предупреждение: изменения белого списка применятся после перезапуска оркестратора",
        )
        self.assertEqual(page.domain_input.accessibleName(), "Домен для белого списка")
        self.assertEqual(page.domain_input.property("screenReaderStateText"), "Домен для белого списка")
        self.assertEqual(page.add_btn.accessibleName(), "Добавить домен в белый список")
        self.assertEqual(page.add_btn.property("screenReaderStateText"), "Добавить домен в белый список")
        self.assertEqual(page.search_input.accessibleName(), "Поиск по белому списку")
        self.assertEqual(page.search_input.property("screenReaderStateText"), "Поиск по белому списку")
        self.assertIn("После ввода перейдите к списку клавишей Tab", page.search_input.accessibleDescription())
        self.assertIn("или нажмите Стрелка вниз", page.search_input.accessibleDescription())
        self.assertEqual(page.clear_user_btn.accessibleName(), "Очистить пользовательские домены белого списка")
        self.assertEqual(
            page.clear_user_btn.property("screenReaderStateText"),
            "Очистить пользовательские домены белого списка",
        )

    def test_whitelist_search_arrow_down_moves_focus_to_first_visible_user_row(self) -> None:
        page = OrchestraWhitelistPage(orchestra_feature=_OrchestraFeatureStub())
        self.addCleanup(page.deleteLater)
        row = WhitelistDomainRow("safe.example", is_default=False, parent=page.rows_container)
        page.rows_layout.addWidget(row)
        page._domain_rows.append(row)
        page.show()
        self.app.processEvents()
        page.search_input.setFocus()
        self.app.processEvents()

        QTest.keyClick(page.search_input, Qt.Key.Key_Down)
        self.app.processEvents()

        self.assertIs(self.app.focusWidget(), row._delete_btn)

    def test_locked_clear_confirmation_buttons_are_named_for_screen_reader(self) -> None:
        page = OrchestraLockedPage.__new__(OrchestraLockedPage)
        page._cleanup_in_progress = False
        page._orchestra = SimpleNamespace(runner=object(), count_locked_strategies=lambda: 3)
        page._request_managed_action = Mock()
        page._tr = lambda _key, default, **kwargs: default.format(**kwargs) if kwargs else default
        page.window = lambda: None
        _MessageBox.instances = []

        with patch("orchestra.ui.locked_page.MessageBox", _MessageBox):
            OrchestraLockedPage._unlock_all(page)

        dialog = _MessageBox.instances[0]
        self.assertEqual(dialog.yesButton.accessibleName(), "Разлочить все стратегии")
        self.assertIn("Разлочить все 3 стратегий", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить разлочку всех стратегий")
        self.assertTrue(dialog.exec_called)
        page._request_managed_action.assert_not_called()

    def test_blocked_clear_confirmation_buttons_are_named_for_screen_reader(self) -> None:
        page = OrchestraBlockedPage.__new__(OrchestraBlockedPage)
        page._cleanup_in_progress = False
        page._orchestra = SimpleNamespace(runner=object(), count_user_blocked_strategies=lambda: 4)
        page._request_managed_action = Mock()
        page._tr = lambda _key, default, **kwargs: default.format(**kwargs) if kwargs else default
        page.window = lambda: None
        _MessageBox.instances = []

        with patch("orchestra.ui.blocked_page.MessageBox", _MessageBox):
            OrchestraBlockedPage._unblock_all(page)

        dialog = _MessageBox.instances[0]
        self.assertEqual(dialog.yesButton.accessibleName(), "Очистить пользовательские блокировки")
        self.assertIn("пользовательский чёрный список", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить очистку пользовательских блокировок")
        self.assertTrue(dialog.exec_called)
        page._request_managed_action.assert_not_called()

    def test_whitelist_clear_confirmation_buttons_are_named_for_screen_reader(self) -> None:
        page = OrchestraWhitelistPage.__new__(OrchestraWhitelistPage)
        page._all_whitelist_data = (("user.example", False), ("system.example", True))
        page._request_whitelist_action = Mock()
        page._tr = lambda _key, default, **kwargs: default.format(**kwargs) if kwargs else default
        page.window = lambda: None
        _MessageBox.instances = []

        with patch("orchestra.ui.whitelist_page.MessageBox", _MessageBox):
            OrchestraWhitelistPage._clear_user_domains(page)

        dialog = _MessageBox.instances[0]
        self.assertEqual(dialog.yesButton.accessibleName(), "Очистить пользовательские домены белого списка")
        self.assertIn("Удалить все пользовательские домены", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить очистку пользовательских доменов")
        self.assertTrue(dialog.exec_called)
        page._request_whitelist_action.assert_not_called()

    def test_orchestra_list_counters_read_current_counts(self) -> None:
        whitelist_page = OrchestraWhitelistPage(orchestra_feature=_OrchestraFeatureStub())
        locked_page = OrchestraLockedPage(orchestra_feature=_OrchestraFeatureStub())
        blocked_page = OrchestraBlockedPage(orchestra_feature=_OrchestraFeatureStub())
        self.addCleanup(whitelist_page.deleteLater)
        self.addCleanup(locked_page.deleteLater)
        self.addCleanup(blocked_page.deleteLater)

        whitelist_page._apply_whitelist_entries((
            ("system.example", True),
            ("user.example", False),
        ))
        locked_page._orchestra = SimpleNamespace(
            current_locked_snapshot=lambda: SimpleNamespace(total_count=3, tcp_count=2, udp_count=1),
        )
        locked_page._update_count()
        blocked_page._orchestra = SimpleNamespace(
            current_blocked_snapshot=lambda: SimpleNamespace(total_count=4, user_count=3, default_count=1),
        )
        blocked_page._update_count()

        self.assertEqual(
            whitelist_page.count_label.property("screenReaderStateText"),
            "Счётчик белого списка Оркестратора: Всего: 2 (1 системных + 1 пользовательских)",
        )
        self.assertEqual(
            locked_page.count_label.property("screenReaderStateText"),
            "Счётчик залоченных стратегий Оркестратора: Всего залочено: 3 (TCP: 2, UDP: 1)",
        )
        self.assertEqual(
            blocked_page.count_label.property("screenReaderStateText"),
            "Счётчик заблокированных стратегий Оркестратора: Всего: 4 (3 пользовательских + 1 системных)",
        )

    def test_whitelist_group_headers_read_section_names(self) -> None:
        page = OrchestraWhitelistPage(orchestra_feature=_OrchestraFeatureStub())
        self.addCleanup(page.deleteLater)

        page._apply_whitelist_entries((
            ("system.example", True),
            ("user.example", False),
        ))

        sections = {}
        for index in range(page.rows_layout.count()):
            widget = page.rows_layout.itemAt(index).widget()
            if widget is not None and widget.property("whitelistSection"):
                sections[str(widget.property("whitelistSection"))] = widget

        self.assertEqual(
            sections["user"].property("screenReaderStateText"),
            "Раздел белого списка Оркестратора: Пользовательские, 1",
        )
        self.assertEqual(
            sections["system"].property("screenReaderStateText"),
            "Раздел белого списка Оркестратора: Системные, 1, нельзя удалить",
        )

    def test_ratings_page_main_controls_are_named_for_screen_reader(self) -> None:
        page = OrchestraRatingsPage(orchestra_feature=_OrchestraFeatureStub())
        self.addCleanup(page.deleteLater)

        self.assertEqual(page.filter_input.accessibleName(), "Фильтр рейтингов по домену")
        self.assertIn("После ввода перейдите к истории клавишей Tab", page.filter_input.accessibleDescription())
        self.assertIn("или нажмите Стрелка вниз", page.filter_input.accessibleDescription())
        self.assertEqual(page.refresh_btn.accessibleName(), "Обновить рейтинги стратегий")
        self.assertEqual(page.refresh_btn.property("screenReaderStateText"), "Обновить рейтинги стратегий")
        self.assertEqual(page.stats_label.accessibleName(), "Статистика рейтингов: Загрузка...")
        self.assertEqual(
            page.history_text.accessibleName(),
            "История рейтингов стратегий: история появится после обучения",
        )
        self.assertIn("результаты обучения", page.history_text.accessibleDescription())
        self.assertEqual(
            page.history_text.property("screenReaderStateText"),
            "История рейтингов стратегий: история появится после обучения",
        )

    def test_ratings_filter_arrow_down_moves_focus_to_history(self) -> None:
        page = OrchestraRatingsPage(orchestra_feature=_OrchestraFeatureStub())
        self.addCleanup(page.deleteLater)
        page.show()
        self.app.processEvents()
        page.filter_input.setFocus()
        self.app.processEvents()

        QTest.keyClick(page.filter_input, Qt.Key.Key_Down)
        self.app.processEvents()

        self.assertIs(self.app.focusWidget(), page.history_text)

    def test_orchestra_search_clear_buttons_do_not_take_tab_focus(self) -> None:
        pages_and_inputs = []
        for page in (
            OrchestraWhitelistPage(orchestra_feature=_OrchestraFeatureStub()),
            OrchestraLockedPage(orchestra_feature=_OrchestraFeatureStub()),
            OrchestraBlockedPage(orchestra_feature=_OrchestraFeatureStub()),
            OrchestraRatingsPage(orchestra_feature=_OrchestraFeatureStub()),
        ):
            self.addCleanup(page.deleteLater)
            pages_and_inputs.append(
                getattr(page, "filter_input", None) or getattr(page, "search_input", None)
            )

        for line_edit in pages_and_inputs:
            line_edit.setText("example")
            buttons = [
                child
                for child in line_edit.findChildren(object)
                if str(getattr(child, "objectName", lambda: "")() or "") == "lineEditButton"
                and hasattr(child, "setFocusPolicy")
            ]

            self.assertTrue(buttons)
            self.assertTrue(all(button.focusPolicy() == Qt.FocusPolicy.NoFocus for button in buttons))

    def test_status_card_exposes_status_as_screen_reader_state(self) -> None:
        def create_card(title: str):
            card = QWidget()
            layout = QVBoxLayout(card)
            title_label = BodyLabel(title, card)
            layout.addWidget(title_label)
            return card, layout, title_label

        widgets = build_orchestra_status_card(
            create_card=create_card,
            tr_fn=lambda _key, default, **_kwargs: default,
            body_label_cls=BodyLabel,
            caption_label_cls=CaptionLabel,
        )
        self.addCleanup(widgets.card.deleteLater)

        self.assertEqual(widgets.status_label.accessibleName(), "Статус обучения Оркестратора: Не запущен")
        self.assertEqual(
            widgets.status_label.property("screenReaderStateText"),
            "Статус обучения Оркестратора: Не запущен",
        )

    def test_status_update_exposes_status_as_screen_reader_state(self) -> None:
        page = OrchestraPage(
            orchestra_feature=_OrchestraFeatureStub(),
            is_runtime_running=lambda: False,
        )
        self.addCleanup(page.deleteLater)

        page._update_status(page.STATE_RUNNING)

        self.assertEqual(
            page.status_label.accessibleName(),
            "Статус обучения Оркестратора: RUNNING - работает на лучших стратегиях",
        )
        self.assertEqual(
            page.status_label.property("screenReaderStateText"),
            "Статус обучения Оркестратора: RUNNING - работает на лучших стратегиях",
        )

    def test_log_card_controls_are_named_for_screen_reader(self) -> None:
        def create_card(title: str):
            card = QWidget()
            layout = QVBoxLayout(card)
            title_label = BodyLabel(title, card)
            layout.addWidget(title_label)
            return card, layout, title_label

        widgets = build_orchestra_log_card(
            create_card=create_card,
            tr_fn=lambda _key, default, **_kwargs: default,
            line_edit_cls=LineEdit,
            combo_cls=ComboBox,
            body_label_cls=BodyLabel,
            caption_label_cls=CaptionLabel,
            transparent_tool_button_cls=TransparentToolButton,
            fluent_push_button_cls=PushButton,
            on_show_log_context_menu=lambda *_args: None,
            on_apply_log_filter=lambda *_args: None,
            on_clear_log_filter=lambda: None,
            on_clear_log=lambda: None,
            on_clear_learned_clicked=lambda: None,
        )
        self.addCleanup(widgets.card.deleteLater)

        self.assertEqual(widgets.log_text.accessibleName(), "Лог обучения Оркестратора: пока нет записей обучения")
        self.assertIn("строки обучения", widgets.log_text.accessibleDescription())
        self.assertEqual(
            widgets.log_text.property("screenReaderStateText"),
            "Лог обучения Оркестратора: пока нет записей обучения",
        )
        self.assertEqual(widgets.log_filter_input.accessibleName(), "Фильтр лога Оркестратора по домену")
        self.assertIn("example.com", widgets.log_filter_input.accessibleDescription())
        self.assertIn("После ввода перейдите к логу клавишей Tab", widgets.log_filter_input.accessibleDescription())
        self.assertIn("или нажмите Стрелка вниз", widgets.log_filter_input.accessibleDescription())
        widgets.card.show()
        self.app.processEvents()
        widgets.log_filter_input.setFocus()
        self.app.processEvents()

        QTest.keyClick(widgets.log_filter_input, Qt.Key.Key_Down)
        self.app.processEvents()

        self.assertIs(self.app.focusWidget(), widgets.log_text)
        self.assertEqual(widgets.clear_filter_btn.accessibleName(), "Сбросить фильтр лога Оркестратора")
        self.assertEqual(widgets.clear_log_btn.accessibleName(), "Очистить лог обучения Оркестратора")
        self.assertEqual(widgets.clear_learned_btn.accessibleName(), "Сбросить данные обучения Оркестратора")

        set_protocol_filter_items(
            combo=widgets.log_protocol_filter,
            items=protocol_filter_items(tr_fn=lambda _key, default, **_kwargs: default),
        )

        self.assertEqual(
            widgets.log_protocol_filter.accessibleName(),
            "Фильтр лога Оркестратора по протоколу, выбрано: Все",
        )
        self.assertEqual(
            widgets.log_protocol_filter.property("screenReaderStateText"),
            "Фильтр лога Оркестратора по протоколу, выбрано: Все",
        )
        create_menu = getattr(widgets.log_protocol_filter, "_create_accessible_combo_menu", None)
        self.assertIsNotNone(create_menu)
        menu = create_menu()
        self.assertEqual(
            menu.view.item(0).data(Qt.ItemDataRole.AccessibleTextRole),
            "Фильтр лога Оркестратора по протоколу: Все, выбран",
        )
        self.assertEqual(
            menu.view.item(1).data(Qt.ItemDataRole.AccessibleTextRole),
            "Фильтр лога Оркестратора по протоколу: TLS, не выбран",
        )

        widgets.log_protocol_filter.setCurrentIndex(2)

        self.assertEqual(
            widgets.log_protocol_filter.accessibleName(),
            "Фильтр лога Оркестратора по протоколу, выбрано: HTTP",
        )
        self.assertEqual(
            widgets.log_protocol_filter.property("screenReaderStateText"),
            "Фильтр лога Оркестратора по протоколу, выбрано: HTTP",
        )

    def test_log_history_controls_are_named_for_screen_reader(self) -> None:
        def create_card(title: str):
            card = QWidget()
            layout = QVBoxLayout(card)
            title_label = BodyLabel(title, card)
            layout.addWidget(title_label)
            return card, layout, title_label

        widgets = build_orchestra_log_history_card(
            create_card=create_card,
            tr_fn=lambda _key, default, **kwargs: default.format(**kwargs) if kwargs else default,
            max_logs=10,
            list_widget_cls=QListWidget,
            caption_label_cls=CaptionLabel,
            fluent_push_button_cls=PushButton,
            on_view_log_history=lambda *_args: None,
            on_delete_log_history=lambda *_args: None,
            on_clear_all_log_history=lambda: None,
        )
        self.addCleanup(widgets.card.deleteLater)

        self.assertEqual(widgets.desc_label.accessibleName(), "Описание истории логов Оркестратора")
        self.assertIn("каждый запуск", widgets.desc_label.accessibleDescription().lower())
        self.assertEqual(
            widgets.log_history_list.accessibleName(),
            "История логов Оркестратора: список пока не загружен",
        )
        self.assertIn("выберите лог", widgets.log_history_list.accessibleDescription().lower())
        self.assertEqual(
            widgets.log_history_list.property("screenReaderStateText"),
            "История логов Оркестратора: список пока не загружен",
        )
        self.assertEqual(widgets.view_log_btn.accessibleName(), "Просмотреть выбранный лог Оркестратора")
        self.assertEqual(widgets.delete_log_btn.accessibleName(), "Удалить выбранный лог Оркестратора")
        self.assertEqual(widgets.clear_all_logs_btn.accessibleName(), "Очистить всю историю логов Оркестратора")

    def test_log_history_items_expose_screen_reader_text(self) -> None:
        from orchestra.ui.page_runtime_helpers import update_log_history_view

        widget = QListWidget()
        self.addCleanup(widget.deleteLater)

        update_log_history_view(
            logs=[
                {
                    "id": "log-1",
                    "created": "2026-06-08 12:30",
                    "size_str": "14 KB",
                    "is_current": True,
                }
            ],
            tr_fn=lambda _key, default, **_kwargs: default,
            log_history_list=widget,
        )

        self.assertEqual(
            widget.item(0).data(Qt.ItemDataRole.AccessibleTextRole),
            "Лог Оркестратора: 2026-06-08 12:30, размер 14 KB, текущий",
        )

    def test_log_history_updates_screen_reader_text_when_current_log_changes(self) -> None:
        from orchestra.ui.page_runtime_helpers import update_log_history_view

        widget = QListWidget()
        self.addCleanup(widget.deleteLater)

        update_log_history_view(
            logs=[
                {
                    "id": "log-1",
                    "created": "2026-06-08 12:30",
                    "size_str": "14 KB",
                    "is_current": True,
                },
                {
                    "id": "log-2",
                    "created": "2026-06-08 13:00",
                    "size_str": "18 KB",
                    "is_current": False,
                },
            ],
            tr_fn=lambda _key, default, **_kwargs: default,
            log_history_list=widget,
        )

        widget.setCurrentRow(1)

        self.assertEqual(
            widget.property("screenReaderStateText"),
            "История логов Оркестратора: Лог Оркестратора: 2026-06-08 13:00, размер 18 KB",
        )

    def test_empty_log_history_item_exposes_screen_reader_text(self) -> None:
        from orchestra.ui.page_runtime_helpers import update_log_history_view

        widget = QListWidget()
        self.addCleanup(widget.deleteLater)

        update_log_history_view(
            logs=[],
            tr_fn=lambda _key, default, **_kwargs: default,
            log_history_list=widget,
        )

        self.assertEqual(
            widget.item(0).data(Qt.ItemDataRole.AccessibleTextRole),
            "История логов Оркестратора: Нет сохранённых логов",
        )

    def test_empty_log_history_updates_screen_reader_state_text(self) -> None:
        from orchestra.ui.page_runtime_helpers import update_log_history_view

        widget = QListWidget()
        self.addCleanup(widget.deleteLater)

        update_log_history_view(
            logs=[],
            tr_fn=lambda _key, default, **_kwargs: default,
            log_history_list=widget,
        )

        self.assertEqual(
            widget.property("screenReaderStateText"),
            "История логов Оркестратора: Нет сохранённых логов",
        )

    def test_row_controls_include_domain_protocol_and_strategy(self) -> None:
        locked_row = LockedDomainRow("example.com", 3, "tcp")
        blocked_row = BlockedDomainRow("blocked.example", 5, "udp", is_default=False)
        whitelist_row = WhitelistDomainRow("safe.example", is_default=False)
        self.addCleanup(locked_row.deleteLater)
        self.addCleanup(blocked_row.deleteLater)
        self.addCleanup(whitelist_row.deleteLater)

        self.assertEqual(locked_row.accessibleName(), "Залоченная стратегия: example.com, TCP, стратегия 3")
        self.assertEqual(
            locked_row.property("screenReaderStateText"),
            "Залоченная стратегия: example.com, TCP, стратегия 3",
        )
        self.assertEqual(locked_row.strat_spin.accessibleName(), "Стратегия для example.com TCP, выбрано: 3")
        self.assertEqual(
            locked_row.strat_spin.property("screenReaderStateText"),
            "Стратегия для example.com TCP, выбрано: 3",
        )
        self.assertEqual(locked_row._delete_btn.accessibleName(), "Разлочить example.com TCP")
        self.assertEqual(
            locked_row._delete_btn.property("screenReaderStateText"),
            "Разлочить example.com TCP",
        )
        locked_row.strat_spin.setValue(8)
        self.assertEqual(locked_row.strat_spin.accessibleName(), "Стратегия для example.com TCP, выбрано: 8")
        self.assertEqual(
            locked_row.strat_spin.property("screenReaderStateText"),
            "Стратегия для example.com TCP, выбрано: 8",
        )

        self.assertEqual(blocked_row.accessibleName(), "Заблокированная стратегия: blocked.example, UDP, стратегия 5")
        self.assertEqual(
            blocked_row.property("screenReaderStateText"),
            "Заблокированная стратегия: blocked.example, UDP, стратегия 5",
        )
        self.assertEqual(blocked_row.strat_spin.accessibleName(), "Заблокированная стратегия для blocked.example UDP, выбрано: 5")
        self.assertEqual(
            blocked_row.strat_spin.property("screenReaderStateText"),
            "Заблокированная стратегия для blocked.example UDP, выбрано: 5",
        )
        self.assertEqual(blocked_row._add_btn.accessibleName(), "Добавить ещё одну блокировку для blocked.example UDP")
        self.assertEqual(
            blocked_row._add_btn.property("screenReaderStateText"),
            "Добавить ещё одну блокировку для blocked.example UDP",
        )
        self.assertEqual(blocked_row._delete_btn.accessibleName(), "Разблокировать blocked.example UDP, стратегия 5")
        self.assertEqual(
            blocked_row._delete_btn.property("screenReaderStateText"),
            "Разблокировать blocked.example UDP, стратегия 5",
        )

        self.assertEqual(whitelist_row.accessibleName(), "Домен белого списка: safe.example")
        self.assertEqual(whitelist_row.property("screenReaderStateText"), "Домен белого списка: safe.example")
        self.assertEqual(whitelist_row._delete_btn.accessibleName(), "Удалить safe.example из белого списка")
        self.assertEqual(
            whitelist_row._delete_btn.property("screenReaderStateText"),
            "Удалить safe.example из белого списка",
        )


if __name__ == "__main__":
    unittest.main()
