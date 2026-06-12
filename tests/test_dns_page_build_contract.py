from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, IndeterminateProgressBar, LineEdit, PushButton

from dns.ui.page_build import build_network_page_shell
from dns.ui.page_runtime_helpers import build_dns_choices_ui
from ui.fluent_widgets import SettingsCard


class DnsPageBuildContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_network_shell_transient_containers_are_parented_immediately(self) -> None:
        content_parent = QWidget()

        shell = build_network_page_shell(
            parent=content_parent,
            content_parent=content_parent,
            tr_fn=lambda _key, default: default,
            add_section_title_fn=lambda **_kwargs: None,
            body_label_cls=BodyLabel,
            settings_card_cls=SettingsCard,
            qvbox_layout_cls=QVBoxLayout,
            qhbox_layout_cls=QHBoxLayout,
            qframe_cls=QFrame,
            line_edit_cls=LineEdit,
            action_button_cls=PushButton,
            indeterminate_progress_bar_cls=IndeterminateProgressBar,
            setting_card_group_cls=SettingsCard,
            quick_actions_bar_cls=lambda: QWidget(),
            insert_widget_into_setting_card_group_fn=lambda *_args, **_kwargs: None,
            build_custom_dns_ui_fn=lambda **_kwargs: SimpleNamespace(
                card=SettingsCard(parent=content_parent),
                indicator=QFrame(content_parent),
                title_label=BodyLabel(""),
                primary_input=LineEdit(content_parent),
                secondary_input=LineEdit(content_parent),
                apply_button=PushButton("OK", content_parent),
            ),
            build_tools_card_ui_fn=lambda **_kwargs: SimpleNamespace(
                section_label=None,
                card=SettingsCard(parent=content_parent),
                actions_bar=QWidget(content_parent),
                test_button=PushButton("test", content_parent),
                flush_button=PushButton("flush", content_parent),
            ),
            on_apply_custom_dns=lambda: None,
            on_test_connection=lambda: None,
            on_flush_dns_cache=lambda: None,
            set_tooltip_fn=lambda *_args, **_kwargs: None,
            dns_provider_card_cls=SimpleNamespace(indicator_off=lambda: ""),
        )

        self.assertIs(shell.dns_cards_container.parent(), content_parent)
        self.assertIs(shell.adapters_container.parent(), content_parent)

    def test_network_shell_uses_compact_adapter_choice_list(self) -> None:
        from dns.ui.adapter_list import AdapterChoiceListWidget

        content_parent = QWidget()

        shell = build_network_page_shell(
            parent=content_parent,
            content_parent=content_parent,
            tr_fn=lambda _key, default: default,
            add_section_title_fn=lambda **_kwargs: None,
            body_label_cls=BodyLabel,
            settings_card_cls=SettingsCard,
            qvbox_layout_cls=QVBoxLayout,
            qhbox_layout_cls=QHBoxLayout,
            qframe_cls=QFrame,
            line_edit_cls=LineEdit,
            action_button_cls=PushButton,
            indeterminate_progress_bar_cls=IndeterminateProgressBar,
            setting_card_group_cls=SettingsCard,
            quick_actions_bar_cls=lambda: QWidget(),
            insert_widget_into_setting_card_group_fn=lambda *_args, **_kwargs: None,
            build_custom_dns_ui_fn=lambda **_kwargs: SimpleNamespace(
                card=SettingsCard(parent=content_parent),
                indicator=QFrame(content_parent),
                title_label=BodyLabel(""),
                primary_input=LineEdit(content_parent),
                secondary_input=LineEdit(content_parent),
                apply_button=PushButton("OK", content_parent),
            ),
            build_tools_card_ui_fn=lambda **_kwargs: SimpleNamespace(
                section_label=None,
                card=SettingsCard(parent=content_parent),
                actions_bar=QWidget(content_parent),
                test_button=PushButton("test", content_parent),
                flush_button=PushButton("flush", content_parent),
            ),
            on_apply_custom_dns=lambda: None,
            on_test_connection=lambda: None,
            on_flush_dns_cache=lambda: None,
            set_tooltip_fn=lambda *_args, **_kwargs: None,
            dns_provider_card_cls=SimpleNamespace(indicator_off=lambda: ""),
        )

        self.assertIsInstance(shell.adapters_container, AdapterChoiceListWidget)
        self.assertIs(shell.adapters_layout, shell.adapters_container)

    def test_network_page_does_not_place_inline_custom_dns_row_in_choices_list(self) -> None:
        from dns.ui.cards import DNSProviderCard
        from dns.ui.choice_list import DnsChoiceListWidget
        from dns.ui.page import NetworkPage

        dns_feature = SimpleNamespace(
            normalize_adapter_alias=lambda value: str(value),
            consume_warmed_page_data=lambda: None,
            create_page_load_worker=lambda request_id, parent=None: None,
        )

        with patch("dns.ui.page.get_custom_dns_servers", return_value=[]):
            page = NetworkPage(deps=SimpleNamespace(dns_feature=dns_feature))

        self.assertIsInstance(page.dns_cards_container, DnsChoiceListWidget)
        self.assertIsNone(page.dns_cards_container.custom_item())
        self.assertFalse(page.custom_card.isVisible())
        self.assertEqual(len(page.dns_cards_container.findChildren(DNSProviderCard)), 0)
        self.assertGreater(page.dns_cards_container.count(), len(page.dns_cards))

    def test_network_page_refresh_adds_saved_custom_dns_to_choice_list(self) -> None:
        from dns.ui.page import NetworkPage

        dns_feature = SimpleNamespace(
            normalize_adapter_alias=lambda value: str(value),
            consume_warmed_page_data=lambda: None,
            create_page_load_worker=lambda request_id, parent=None: None,
        )

        with patch("dns.ui.page.get_custom_dns_servers", return_value=[]):
            page = NetworkPage(deps=SimpleNamespace(dns_feature=dns_feature))

        page._custom_dns_servers = [
            {
                "id": "my-dns",
                "name": "Мой DNS",
                "ipv4": ["8.8.8.8"],
                "ipv6": [],
            }
        ]
        page._refresh_custom_dns_providers()

        self.assertIn("Мой DNS", page.dns_cards)

    def test_custom_dns_row_is_not_inserted_or_shown_by_choices_builder(self) -> None:
        class _ChoiceList:
            def __init__(self):
                self.auto_selected = _Signal()
                self.custom_was_inserted = False

            def show(self):
                pass

            def add_auto_choice(self, _title):
                return object()

            def set_custom_choice(self, custom_card):
                self.custom_was_inserted = True
                custom_card.set_parented()

        class _CustomCard:
            def __init__(self):
                self.was_shown_without_parent = False
                self.parented = False

            def show(self):
                if not self.parented:
                    self.was_shown_without_parent = True

            def set_parented(self):
                self.parented = True

        custom_card = _CustomCard()

        choice_list = _ChoiceList()

        build_dns_choices_ui(
            cleanup_in_progress=False,
            dns_choices_built=False,
            tr_fn=lambda _key, default: default,
            settings_card_cls=object,
            qhbox_layout_cls=object,
            qframe_cls=object,
            strong_body_label_cls=object,
            caption_label_cls=object,
            qlabel_cls=object,
            qta_module=None,
            get_theme_tokens_fn=lambda: SimpleNamespace(fg_faint="#888888"),
            build_auto_dns_ui_fn=lambda **_kwargs: None,
            build_provider_cards_fn=lambda **_kwargs: SimpleNamespace(dns_cards={}, category_labels=[]),
            providers={},
            dns_cards_layout=choice_list,
            on_auto_selected=lambda: None,
            on_provider_selected=lambda _name, _data: None,
            ipv6_available=True,
            dns_cards_container=SimpleNamespace(show=lambda: None),
            custom_card=custom_card,
            dns_provider_card_cls=SimpleNamespace(indicator_off=lambda: ""),
            apply_inline_theme_styles_fn=lambda _tokens: None,
        )

        self.assertFalse(choice_list.custom_was_inserted)
        self.assertFalse(custom_card.was_shown_without_parent)


class _Signal:
    def connect(self, _callback):
        pass


if __name__ == "__main__":
    unittest.main()
