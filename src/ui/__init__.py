# UI module exports
from .page_names import (
    PageName,
)

__all__ = [
    'MainWindowUI',
    'PageName',
]


def __getattr__(name):
    if name == 'MainWindowUI':
        from .window_ui_facade import MainWindowUI

        return MainWindowUI
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
