# ui/window_ui_facade.py
"""
Главное окно приложения — навигация через qfluentwidgets FluentWindow.

Все страницы добавляются через addSubInterface() вместо ручного SideNavBar + QStackedWidget.
Бизнес-логика (сигналы, обработчики) сохранена без изменений.
"""
from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QCompleter
from typing import Any, cast


try:
    from qfluentwidgets import (
        NavigationItemPosition, FluentIcon,
    )
    try:
        from qfluentwidgets import SearchLineEdit
    except ImportError:
        SearchLineEdit = QLineEdit
    HAS_FLUENT = True
except ImportError:
    HAS_FLUENT = False
    NavigationItemPosition = cast(Any, None)
    FluentIcon = cast(Any, None)
    SearchLineEdit = QLineEdit

from ui.page_names import PageName
from ui.text_catalog import tr as tr_catalog
from ui.navigation.navigation_controller import ensure_navigation_controller
from ui.window_display_state import get_direct_strategy_summary
from ui.ui_root import WindowUiRoot

# ---------------------------------------------------------------------------
# Navigation icon mapping (SectionName/PageName -> FluentIcon)
# ---------------------------------------------------------------------------
_NAV_ICONS = {
    PageName.CONTROL: FluentIcon.COMMAND_PROMPT if HAS_FLUENT else None,
    PageName.ZAPRET2_DIRECT_CONTROL: FluentIcon.GAME if HAS_FLUENT else None,
    PageName.AUTOSTART: FluentIcon.POWER_BUTTON if HAS_FLUENT else None,
    PageName.NETWORK: FluentIcon.WIFI if HAS_FLUENT else None,
    PageName.HOSTS: FluentIcon.GLOBE if HAS_FLUENT else None,
    PageName.BLOCKCHECK: FluentIcon.CODE if HAS_FLUENT else None,
    PageName.APPEARANCE: FluentIcon.PALETTE if HAS_FLUENT else None,
    PageName.PREMIUM: FluentIcon.HEART if HAS_FLUENT else None,
    PageName.LOGS: FluentIcon.HISTORY if HAS_FLUENT else None,
    PageName.ABOUT: FluentIcon.INFO if HAS_FLUENT else None,
    PageName.DPI_SETTINGS: FluentIcon.SETTING if HAS_FLUENT else None,
    PageName.HOSTLIST: FluentIcon.BOOK_SHELF if HAS_FLUENT else None,
    PageName.BLOBS: FluentIcon.CLOUD if HAS_FLUENT else None,
    PageName.NETROGAT: FluentIcon.REMOVE_FROM if HAS_FLUENT else None,
    PageName.CUSTOM_DOMAINS: FluentIcon.ADD if HAS_FLUENT else None,
    PageName.CUSTOM_IPSET: FluentIcon.ADD if HAS_FLUENT else None,
    PageName.ZAPRET2_USER_PRESETS: FluentIcon.FOLDER if HAS_FLUENT else None,
    PageName.SERVERS: FluentIcon.UPDATE if HAS_FLUENT else None,
    PageName.SUPPORT: FluentIcon.CHAT if HAS_FLUENT else None,
    PageName.ORCHESTRA: FluentIcon.MUSIC if HAS_FLUENT else None,
    PageName.ORCHESTRA_SETTINGS: FluentIcon.SETTING if HAS_FLUENT else None,
    PageName.ZAPRET2_DIRECT: FluentIcon.PLAY if HAS_FLUENT else None,
    PageName.ZAPRET1_DIRECT_CONTROL: FluentIcon.GAME if HAS_FLUENT else None,
    PageName.ZAPRET1_DIRECT: FluentIcon.PLAY if HAS_FLUENT else None,
    PageName.ZAPRET1_USER_PRESETS: FluentIcon.FOLDER if HAS_FLUENT else None,
    PageName.TELEGRAM_PROXY: FluentIcon.SEND if HAS_FLUENT else None,
}

# Russian labels for navigation
_NAV_LABELS = {
    PageName.CONTROL: "Управление",
    PageName.ZAPRET2_DIRECT_CONTROL: "Управление Zapret 2",
    PageName.AUTOSTART: "Автозапуск",
    PageName.NETWORK: "Сеть",
    PageName.HOSTS: "Редактор файла hosts",
    PageName.BLOCKCHECK: "BlockCheck",
    PageName.APPEARANCE: "Оформление",
    PageName.PREMIUM: "Донат",
    PageName.LOGS: "Логи",
    PageName.ABOUT: "О программе",
    PageName.DPI_SETTINGS: "Сменить режим DPI",
    PageName.HOSTLIST: "Листы",
    PageName.BLOBS: "Блобы",
    PageName.NETROGAT: "Исключения",
    PageName.CUSTOM_DOMAINS: "Мои hostlist",
    PageName.CUSTOM_IPSET: "Мои ipset",
    PageName.ZAPRET2_USER_PRESETS: "Мои пресеты",
    PageName.SERVERS: "Обновления",
    PageName.SUPPORT: "Поддержка",
    PageName.ORCHESTRA: "Оркестратор",
    PageName.ORCHESTRA_SETTINGS: "Настройки оркестратора",
    PageName.ZAPRET2_DIRECT: "Прямой запуск",
    PageName.ZAPRET1_DIRECT_CONTROL: "Управление Zapret 1",
    PageName.ZAPRET1_DIRECT: "Стратегии Z1",
    PageName.ZAPRET1_USER_PRESETS: "Мои пресеты Z1",
    PageName.TELEGRAM_PROXY: "Telegram Proxy",
}


if HAS_FLUENT:
    class _SidebarSearchNavWidget(QWidget):
        textChanged = pyqtSignal(str)

        def __init__(self, parent: QWidget | None = None):
            super().__init__(parent)
            self._search = SearchLineEdit(self)
            self._completion_timer = QTimer(self)
            self._completion_timer.setSingleShot(True)
            self._completion_timer.timeout.connect(self._show_completions_deferred)
            self._search.setPlaceholderText(tr_catalog("sidebar.search.placeholder"))
            try:
                self._search.setClearButtonEnabled(True)
            except Exception:
                pass
            self._search.textChanged.connect(self.textChanged.emit)

            layout = QHBoxLayout(self)
            layout.setContentsMargins(0, 4, 0, 4)
            layout.setSpacing(0)
            layout.addWidget(self._search)

            self.setFixedHeight(40)

        def clear(self) -> None:
            self._search.clear()

        def text(self) -> str:
            return self._search.text()

        def set_placeholder_text(self, text: str) -> None:
            self._search.setPlaceholderText(text or "")

        def set_completer(self, completer: QCompleter) -> None:
            self._search.setCompleter(completer)

        def show_completions(self) -> None:
            # Defer popup interaction to avoid re-entrant completer/model updates
            # from textChanged handlers, which can crash native Qt on Windows.
            if not self.isVisible() or not self._search.isVisible() or not self._search.hasFocus():
                return
            self._completion_timer.start(0)

        def _show_completions_deferred(self) -> None:
            completer = self._search.completer()
            if completer is None:
                return
            if not self._search.text().strip():
                return

            try:
                completion_model = completer.completionModel()
                if completion_model is not None and completion_model.rowCount() <= 0:
                    return
            except Exception:
                pass

            completer.setCompletionPrefix(self._search.text())
            # Avoid direct popup forcing here: on some Windows/Qt stacks it can
            # crash natively during re-entrant completer/model updates.


class MainWindowUI:
    """
    Mixin: creates pages and registers them with FluentWindow navigation.
    """

    def _get_ui_root(self) -> WindowUiRoot:
        ui_root = getattr(self, "_ui_root", None)
        if ui_root is None:
            ui_root = WindowUiRoot(self)
            self._ui_root = ui_root
        return ui_root

    def build_ui(self, width: int, height: int):
        """Build UI: create pages and populate FluentWindow navigation sidebar.

        Note: window geometry (size/position) is restored in __init__ via the
        dedicated window geometry controller before this is called — do NOT
        resize here, that would overwrite the saved geometry.
        """
        self._get_ui_root().build(
            width=width,
            height=height,
            nav_icons=_NAV_ICONS,
            nav_labels=_NAV_LABELS,
            has_fluent=HAS_FLUENT,
            default_nav_icon=FluentIcon.APPLICATION if HAS_FLUENT else None,
            nav_scroll_position=NavigationItemPosition.SCROLL if HAS_FLUENT else None,
            sidebar_search_widget_cls=_SidebarSearchNavWidget if HAS_FLUENT else None,
        )

    def finish_ui_bootstrap(self) -> None:
        """Дозавершает тяжёлые связи главного окна после первого показа UI.

        На старте нам важно как можно быстрее показать рабочее окно и первую
        страницу. Общие подписки окна на preset-store, file watcher активного
        пресета и часть сервисных связей можно подключить позже, отдельным
        шагом, не блокируя первый визуальный отклик.
        """
        self._get_ui_root().finish_bootstrap()

    def _get_launch_method(self) -> str:
        try:
            from settings.dpi.strategy_settings import get_strategy_launch_method

            method = (get_strategy_launch_method() or "").strip().lower()
        except Exception:
            method = ""
        return method or "direct_zapret2"

    # Window-facing API intentionally kept minimal. Page opening and routing go
    # through window_adapter/page_host/workflow layers, not through this mixin.
