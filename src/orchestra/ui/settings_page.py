# ui/pages/orchestra/orchestra_settings_page.py
"""Объединённая страница настроек оркестратора с вкладками.

Содержит:
  - Залоченные стратегии (OrchestraLockedPage)
  - Заблокированные стратегии (OrchestraBlockedPage)
  - Белый список (OrchestraWhitelistPage)
  - Рейтинги (OrchestraRatingsPage)
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget
from ui.text_catalog import normalize_language, tr as tr_catalog

try:
    from qfluentwidgets import SegmentedWidget
    _PIVOT_OK = True
except ImportError:
    SegmentedWidget = None
    _PIVOT_OK = False


class OrchestraSettingsPage(QWidget):
    """Контейнерная страница настроек оркестратора с вкладками."""

    TAB_KEYS   = ["locked", "blocked", "whitelist", "ratings"]
    TAB_LABEL_KEYS = [
        "tab.orchestra.locked",
        "tab.orchestra.blocked",
        "tab.orchestra.whitelist",
        "tab.orchestra.ratings",
    ]
    TAB_LABELS = ["Залоченные", "Заблокированные", "Белый список", "Рейтинги"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("OrchestraSettingsPage")
        self._ui_language = self._resolve_ui_language()

        self._app_parent = parent
        self.locked_page = None
        self.blocked_page = None
        self.whitelist_page = None
        self.ratings_page = None
        self._tab_pages: list[QWidget | None] = [None, None, None, None]

        # Stacked widget
        self.stacked = QStackedWidget(self)
        for _ in self.TAB_KEYS:
            self.stacked.addWidget(QWidget(self))

        # Pivot tab bar
        if _PIVOT_OK:
            pivot_cls = SegmentedWidget
            if pivot_cls is None:
                self.pivot = None
            else:
                self.pivot = pivot_cls(self)
        else:
            self.pivot = None

        if self.pivot is not None:
            for i, (key, label) in enumerate(zip(self.TAB_KEYS, self._get_tab_labels())):
                self.pivot.addItem(key, label, lambda *_, idx=i: self._switch_tab(idx))
            self.pivot.setCurrentItem("locked")
            self.pivot.setItemFontSize(13)

        # Layout: pivot bar with margins aligned with BasePage content
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        if self.pivot is not None:
            pivot_row = QWidget(self)
            pivot_row_layout = QHBoxLayout(pivot_row)
            pivot_row_layout.setContentsMargins(36, 8, 36, 0)
            pivot_row_layout.addWidget(self.pivot)
            main_layout.addWidget(pivot_row)

        main_layout.addWidget(self.stacked)

        self._switch_tab(0)

    def _ensure_tab_page(self, index: int) -> QWidget | None:
        if not (0 <= index < len(self.TAB_KEYS)):
            return None

        page = self._tab_pages[index]
        if page is not None:
            return page

        if index == 0:
            from orchestra.ui.locked_page import OrchestraLockedPage

            page = OrchestraLockedPage(self._app_parent)
            self.locked_page = page
        elif index == 1:
            from orchestra.ui.blocked_page import OrchestraBlockedPage

            page = OrchestraBlockedPage(self._app_parent)
            self.blocked_page = page
        elif index == 2:
            from orchestra.ui.whitelist_page import OrchestraWhitelistPage

            page = OrchestraWhitelistPage(self._app_parent)
            self.whitelist_page = page
        else:
            from orchestra.ui.ratings_page import OrchestraRatingsPage

            page = OrchestraRatingsPage(self._app_parent)
            self.ratings_page = page

        set_lang = getattr(page, "set_ui_language", None)
        if callable(set_lang):
            try:
                set_lang(self._ui_language)
            except Exception:
                pass

        old_widget = self.stacked.widget(index)
        if old_widget is not None:
            self.stacked.removeWidget(old_widget)
            old_widget.deleteLater()

        self.stacked.insertWidget(index, page)
        self._tab_pages[index] = page
        return page

    def _resolve_ui_language(self) -> str:
        try:
            from config.reg import get_ui_language

            return normalize_language(get_ui_language())
        except Exception:
            return normalize_language(None)

    def _get_tab_labels(self) -> list[str]:
        labels: list[str] = []
        for fallback, key in zip(self.TAB_LABELS, self.TAB_LABEL_KEYS):
            labels.append(tr_catalog(key, language=self._ui_language, default=fallback))
        return labels

    def set_ui_language(self, language: str) -> None:
        self._ui_language = normalize_language(language)
        if self.pivot is not None:
            try:
                for key, label in zip(self.TAB_KEYS, self._get_tab_labels()):
                    self.pivot.setItemText(key, label)
            except Exception:
                pass

        for page in self._tab_pages:
            if page is None:
                continue
            handler = getattr(page, "set_ui_language", None)
            if callable(handler):
                try:
                    handler(self._ui_language)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Tab switching
    # ------------------------------------------------------------------

    def _switch_tab(self, index: int) -> None:
        self._ensure_tab_page(index)
        self.stacked.setCurrentIndex(index)
        if self.pivot is not None and 0 <= index < len(self.TAB_KEYS):
            self.pivot.setCurrentItem(self.TAB_KEYS[index])

    def switch_to_tab(self, key: str) -> None:
        """External API: switch to the named tab."""
        if key in self.TAB_KEYS:
            self._switch_tab(self.TAB_KEYS.index(key))

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        for page in self._tab_pages:
            if page is None:
                continue
            cleanup_handler = getattr(page, "cleanup", None)
            if callable(cleanup_handler):
                try:
                    cleanup_handler()
                except Exception:
                    pass
