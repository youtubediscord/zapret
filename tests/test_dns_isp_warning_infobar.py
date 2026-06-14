from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock


class _InfoBar:
    def __init__(self) -> None:
        self.added_widgets = []
        self.closed = False

    def addWidget(self, widget) -> None:
        self.added_widgets.append(widget)

    def close(self) -> None:
        self.closed = True


class _InfoBarFactory:
    def __init__(self) -> None:
        self.bar = _InfoBar()
        self.warning = Mock(return_value=self.bar)


class _PushButton:
    def __init__(self, text: str) -> None:
        self.text = text
        self.clicked = SimpleNamespace(connect=Mock())

    def setCursor(self, _cursor) -> None:
        pass


class DnsIspWarningInfoBarTests(unittest.TestCase):
    def test_isp_dns_warning_uses_top_right_infobar_for_ten_seconds(self) -> None:
        from dns.page_diagnostics_warning_workflow import show_isp_dns_warning

        plan = SimpleNamespace(
            should_show=True,
            title="DNS от провайдера",
            content="Провайдерский DNS может мешать обходу блокировок.",
            action_text="Применить Quad9",
            dismiss_text="Нет, спасибо",
        )
        info_bar = _InfoBarFactory()
        info_bar_position = SimpleNamespace(TOP_RIGHT="top-right")

        show_isp_dns_warning(
            cleanup_in_progress=False,
            plan=plan,
            qpush_button_cls=_PushButton,
            qt_namespace=SimpleNamespace(
                CursorShape=SimpleNamespace(PointingHandCursor="pointing")
            ),
            on_accept=Mock(),
            log_fn=Mock(),
            info_bar_cls=info_bar,
            info_bar_position_cls=info_bar_position,
            parent_window="window",
        )

        info_bar.warning.assert_called_once_with(
            title="DNS от провайдера",
            content="Провайдерский DNS может мешать обходу блокировок.",
            isClosable=True,
            position="top-right",
            duration=10000,
            parent="window",
        )
        self.assertEqual(len(info_bar.bar.added_widgets), 1)
        self.assertEqual(info_bar.bar.added_widgets[0].text, "Применить Quad9")


if __name__ == "__main__":
    unittest.main()
