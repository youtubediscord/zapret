# UI module exports
from .page_names import (
    PageName,
    SectionName,
    SECTION_TO_PAGE,
    COLLAPSIBLE_SECTIONS,
    SECTION_CHILDREN,
    ORCHESTRA_ONLY_SECTIONS,
    STRATEGY_PAGES,
)

__all__ = [
    'MainWindowUI',
    'PageName',
    'SectionName',
    'SECTION_TO_PAGE',
    'COLLAPSIBLE_SECTIONS',
    'SECTION_CHILDREN',
    'ORCHESTRA_ONLY_SECTIONS',
    'STRATEGY_PAGES',
]


def __getattr__(name):
    if name == 'MainWindowUI':
        from .window_ui_facade import MainWindowUI

        return MainWindowUI
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
