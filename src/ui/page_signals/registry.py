from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from ui.page_names import PageName

from .common import connect_common_page_signals
from .direct import connect_direct_page_signals
from .helpers import connect_signal_once


def connect_lazy_page_signals(window, page_name: PageName, page: QWidget) -> None:
    connect_common_page_signals(window, page_name, page)
    connect_direct_page_signals(window, page_name, page)


__all__ = ["connect_lazy_page_signals", "connect_signal_once"]
