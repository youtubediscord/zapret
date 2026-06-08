import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget
from PyQt6.QtWidgets import QListWidget
from qfluentwidgets import BodyLabel, CaptionLabel, ComboBox, LineEdit, PushButton, TransparentToolButton

from orchestra.ui.blocked_page import BlockedDomainRow, OrchestraBlockedPage
from orchestra.ui.locked_page import LockedDomainRow, OrchestraLockedPage
from orchestra.ui.page_build import build_orchestra_log_card, build_orchestra_log_history_card
from orchestra.ui.page_runtime_helpers import protocol_filter_items, set_protocol_filter_items
from orchestra.ui.ratings_page import OrchestraRatingsPage
from orchestra.ui.whitelist_page import OrchestraWhitelistPage, WhitelistDomainRow


class _OrchestraFeatureStub:
    ASKEY_ALL = ("tcp", "udp")


class OrchestraAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_locked_page_main_controls_are_named_for_screen_reader(self) -> None:
        page = OrchestraLockedPage(orchestra_feature=_OrchestraFeatureStub())
        self.addCleanup(page.deleteLater)

        self.assertEqual(page.domain_input.accessibleName(), "Домен для залочки стратегии")
        self.assertIn("example.com", page.domain_input.accessibleDescription())
        self.assertEqual(page.proto_combo.accessibleName(), "Протокол залочки стратегии, выбрано: TCP")
        self.assertIn("TCP или UDP", page.proto_combo.accessibleDescription())
        self.assertEqual(page.strat_spin.accessibleName(), "Номер стратегии для залочки, выбрано: 1")
        self.assertEqual(page.lock_btn.accessibleName(), "Залочить стратегию для домена")
        self.assertEqual(page.search_input.accessibleName(), "Поиск по залоченным доменам")
        self.assertEqual(page.refresh_btn.accessibleName(), "Обновить список залоченных стратегий")
        self.assertEqual(page.unlock_all_btn.accessibleName(), "Разлочить все стратегии")

        page.proto_combo.setCurrentIndex(1)
        page.strat_spin.setValue(7)

        self.assertEqual(page.proto_combo.accessibleName(), "Протокол залочки стратегии, выбрано: UDP")
        self.assertEqual(page.strat_spin.accessibleName(), "Номер стратегии для залочки, выбрано: 7")

    def test_blocked_page_main_controls_are_named_for_screen_reader(self) -> None:
        page = OrchestraBlockedPage(orchestra_feature=_OrchestraFeatureStub())
        self.addCleanup(page.deleteLater)

        self.assertEqual(page.domain_input.accessibleName(), "Домен для блокировки стратегии")
        self.assertIn("example.com", page.domain_input.accessibleDescription())
        self.assertEqual(page.proto_combo.accessibleName(), "Протокол блокировки стратегии, выбрано: TCP")
        self.assertEqual(page.strat_spin.accessibleName(), "Номер блокируемой стратегии, выбрано: 1")
        self.assertEqual(page.block_btn.accessibleName(), "Заблокировать стратегию для домена")
        self.assertEqual(page.search_input.accessibleName(), "Поиск по заблокированным доменам")
        self.assertEqual(page.refresh_btn.accessibleName(), "Обновить чёрный список стратегий")
        self.assertEqual(page.unblock_all_btn.accessibleName(), "Очистить пользовательские блокировки")

        page.proto_combo.setCurrentIndex(1)
        page.strat_spin.setValue(9)

        self.assertEqual(page.proto_combo.accessibleName(), "Протокол блокировки стратегии, выбрано: UDP")
        self.assertEqual(page.strat_spin.accessibleName(), "Номер блокируемой стратегии, выбрано: 9")

    def test_whitelist_page_main_controls_are_named_for_screen_reader(self) -> None:
        page = OrchestraWhitelistPage(orchestra_feature=_OrchestraFeatureStub())
        self.addCleanup(page.deleteLater)

        self.assertEqual(page.restart_warning.accessibleName(), "Предупреждение: изменения белого списка применятся после перезапуска оркестратора")
        self.assertEqual(page.domain_input.accessibleName(), "Домен для белого списка")
        self.assertEqual(page.add_btn.accessibleName(), "Добавить домен в белый список")
        self.assertEqual(page.search_input.accessibleName(), "Поиск по белому списку")
        self.assertEqual(page.clear_user_btn.accessibleName(), "Очистить пользовательские домены белого списка")

    def test_ratings_page_main_controls_are_named_for_screen_reader(self) -> None:
        page = OrchestraRatingsPage(orchestra_feature=_OrchestraFeatureStub())
        self.addCleanup(page.deleteLater)

        self.assertEqual(page.filter_input.accessibleName(), "Фильтр рейтингов по домену")
        self.assertEqual(page.refresh_btn.accessibleName(), "Обновить рейтинги стратегий")
        self.assertEqual(page.stats_label.accessibleName(), "Статистика рейтингов: Загрузка...")
        self.assertEqual(page.history_text.accessibleName(), "История рейтингов стратегий")
        self.assertIn("результаты обучения", page.history_text.accessibleDescription())

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

        self.assertEqual(widgets.log_text.accessibleName(), "Лог обучения Оркестратора")
        self.assertIn("строки обучения", widgets.log_text.accessibleDescription())
        self.assertEqual(widgets.log_filter_input.accessibleName(), "Фильтр лога Оркестратора по домену")
        self.assertIn("example.com", widgets.log_filter_input.accessibleDescription())
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

        widgets.log_protocol_filter.setCurrentIndex(2)

        self.assertEqual(
            widgets.log_protocol_filter.accessibleName(),
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
        self.assertEqual(widgets.log_history_list.accessibleName(), "История логов Оркестратора")
        self.assertIn("выберите лог", widgets.log_history_list.accessibleDescription().lower())
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

    def test_row_controls_include_domain_protocol_and_strategy(self) -> None:
        locked_row = LockedDomainRow("example.com", 3, "tcp")
        blocked_row = BlockedDomainRow("blocked.example", 5, "udp", is_default=False)
        whitelist_row = WhitelistDomainRow("safe.example", is_default=False)
        self.addCleanup(locked_row.deleteLater)
        self.addCleanup(blocked_row.deleteLater)
        self.addCleanup(whitelist_row.deleteLater)

        self.assertEqual(locked_row.accessibleName(), "Залоченная стратегия: example.com, TCP, стратегия 3")
        self.assertEqual(locked_row.strat_spin.accessibleName(), "Стратегия для example.com TCP, выбрано: 3")
        self.assertEqual(locked_row._delete_btn.accessibleName(), "Разлочить example.com TCP")
        locked_row.strat_spin.setValue(8)
        self.assertEqual(locked_row.strat_spin.accessibleName(), "Стратегия для example.com TCP, выбрано: 8")

        self.assertEqual(blocked_row.accessibleName(), "Заблокированная стратегия: blocked.example, UDP, стратегия 5")
        self.assertEqual(blocked_row.strat_spin.accessibleName(), "Заблокированная стратегия для blocked.example UDP, выбрано: 5")
        self.assertEqual(blocked_row._add_btn.accessibleName(), "Добавить ещё одну блокировку для blocked.example UDP")
        self.assertEqual(blocked_row._delete_btn.accessibleName(), "Разблокировать blocked.example UDP, стратегия 5")

        self.assertEqual(whitelist_row.accessibleName(), "Домен белого списка: safe.example")
        self.assertEqual(whitelist_row._delete_btn.accessibleName(), "Удалить safe.example из белого списка")


if __name__ == "__main__":
    unittest.main()
