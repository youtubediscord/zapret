from __future__ import annotations

from .helpers import connect_signal_once
from .registry import connect_lazy_page_signals

__all__ = ["connect_lazy_page_signals", "connect_signal_once"]
