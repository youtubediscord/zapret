"""Stacked/tab helper'ы для страницы Листы."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QStackedWidget


class CurrentPanelStackedWidget(QStackedWidget):
    """QStackedWidget, который берёт высоту у текущей вкладки."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.currentChanged.connect(self._refresh_geometry)

    def sizeHint(self) -> QSize:  # noqa: N802
        current = self.currentWidget()
        if current is not None:
            try:
                hint = current.sizeHint()
                if hint.isValid():
                    return hint
            except Exception:
                pass
        return super().sizeHint()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        current = self.currentWidget()
        if current is not None:
            try:
                hint = current.minimumSizeHint()
                if hint.isValid():
                    return hint
            except Exception:
                pass
        return super().minimumSizeHint()

    def _refresh_geometry(self, _index: int) -> None:
        self.updateGeometry()


@dataclass(slots=True)
class HostlistTabSwitchResult:
    domains_loaded: bool
    ips_loaded: bool
    excl_loaded: bool


def switch_hostlist_tab(
    *,
    index: int,
    stacked,
    pivot,
    refresh_geometry_fn,
    request_folder_info_fn,
    domains_loaded: bool,
    ips_loaded: bool,
    excl_loaded: bool,
    schedule_fn,
    load_domains_fn,
    load_ips_fn,
    load_exclusions_fn,
) -> HostlistTabSwitchResult:
    stacked.setCurrentIndex(index)
    keys = ["hostlist", "ipset", "domains", "ips", "exclusions"]
    if 0 <= index < len(keys):
        pivot.setCurrentItem(keys[index])
    refresh_geometry_fn()

    if index == 0:
        request_folder_info_fn("hostlist")
    elif index == 1:
        request_folder_info_fn("ipset")

    next_domains_loaded = bool(domains_loaded)
    next_ips_loaded = bool(ips_loaded)
    next_excl_loaded = bool(excl_loaded)

    if index == 2 and not next_domains_loaded:
        next_domains_loaded = True
        schedule_fn(0, load_domains_fn)
    elif index == 3 and not next_ips_loaded:
        next_ips_loaded = True
        schedule_fn(0, load_ips_fn)
    elif index == 4 and not next_excl_loaded:
        next_excl_loaded = True
        schedule_fn(0, load_exclusions_fn)

    return HostlistTabSwitchResult(
        domains_loaded=next_domains_loaded,
        ips_loaded=next_ips_loaded,
        excl_loaded=next_excl_loaded,
    )
