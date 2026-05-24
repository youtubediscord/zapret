# ui/window_ui_facade.py
"""
Главное окно приложения — навигация через qfluentwidgets FluentWindow.

Все страницы добавляются через addSubInterface() вместо ручного SideNavBar + QStackedWidget.
Бизнес-логика (сигналы, обработчики) сохранена без изменений.
"""
from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QCompleter
from qfluentwidgets import FluentIcon, NavigationItemPosition, SearchLineEdit

from app.page_names import PageName
from app.text_catalog import tr as tr_catalog
from ui.ui_root import WindowUiRoot

# ---------------------------------------------------------------------------
# Navigation icon mapping (PageName -> FluentIcon)
# ---------------------------------------------------------------------------
_NAV_ICONS = {
    PageName.ZAPRET2_MODE_CONTROL: FluentIcon.GAME,
    PageName.AUTOSTART: FluentIcon.POWER_BUTTON,
    PageName.NETWORK: FluentIcon.WIFI,
    PageName.HOSTS: FluentIcon.GLOBE,
    PageName.BLOCKCHECK: FluentIcon.CODE,
    PageName.APPEARANCE: FluentIcon.PALETTE,
    PageName.PREMIUM: FluentIcon.HEART,
    PageName.LOGS: FluentIcon.HISTORY,
    PageName.ABOUT: FluentIcon.INFO,
    PageName.DPI_SETTINGS: FluentIcon.SETTING,
    PageName.BLOBS: FluentIcon.CLOUD,
    PageName.ZAPRET2_USER_PRESETS: FluentIcon.FOLDER,
    PageName.SERVERS: FluentIcon.UPDATE,
    PageName.SUPPORT: FluentIcon.CHAT,
    PageName.ORCHESTRA: FluentIcon.MUSIC,
    PageName.ORCHESTRA_SETTINGS: FluentIcon.SETTING,
    PageName.ZAPRET2_PRESET_SETUP: FluentIcon.PLAY,
    PageName.ZAPRET1_MODE_CONTROL: FluentIcon.GAME,
    PageName.ZAPRET1_PRESET_SETUP: FluentIcon.PLAY,
    PageName.ZAPRET1_USER_PRESETS: FluentIcon.FOLDER,
    PageName.TELEGRAM_PROXY: FluentIcon.SEND,
}

# Russian labels for navigation
_NAV_LABELS = {
    PageName.AUTOSTART: "Автозапуск",
    PageName.NETWORK: "Сеть",
    PageName.HOSTS: "Редактор файла hosts",
    PageName.BLOCKCHECK: "BlockCheck",
    PageName.APPEARANCE: "Оформление",
    PageName.PREMIUM: "Донат",
    PageName.LOGS: "Логи",
    PageName.ABOUT: "О программе",
    PageName.DPI_SETTINGS: "Сменить режим DPI",
    PageName.BLOBS: "Блобы",
    PageName.SERVERS: "Обновления",
    PageName.SUPPORT: "Поддержка",

    PageName.ORCHESTRA: "Оркестратор",
    PageName.ORCHESTRA_SETTINGS: "Настройки оркестратора",

    PageName.ZAPRET2_MODE_CONTROL: "Управление Zapret 2",
    PageName.ZAPRET2_PRESET_SETUP: "Настройка preset-а",
    PageName.ZAPRET2_USER_PRESETS: "Мои пресеты",

    PageName.ZAPRET1_MODE_CONTROL: "Управление Zapret 1",
    PageName.ZAPRET1_PRESET_SETUP: "Настройка preset-а",
    PageName.ZAPRET1_USER_PRESETS: "Мои пресеты",

    PageName.TELEGRAM_PROXY: "Telegram Proxy",
}


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
            raise RuntimeError("WindowUiRoot не подключён. Сначала выполните attach_app_runtime_to_window().")
        return ui_root

    def build_ui(self, width: int, height: int):
        """Build UI: create pages and populate FluentWindow navigation sidebar.

        Note: window geometry (size/position) is restored in __init__ via the
        dedicated window geometry runtime before this is called - do NOT
        resize here, that would overwrite the saved geometry.
        """
        self._get_ui_root().build(
            width=width,
            height=height,
            nav_icons=_NAV_ICONS,
            nav_labels=_NAV_LABELS,
            default_nav_icon=FluentIcon.APPLICATION,
            nav_scroll_position=NavigationItemPosition.SCROLL,
            sidebar_search_widget_cls=_SidebarSearchNavWidget,
        )

    def finish_ui_bootstrap(self) -> None:
        """Дозавершает тяжёлые связи главного окна после первого показа UI.

        На старте нам важно как можно быстрее показать рабочее окно и первую
        страницу. Общие подписки окна на preset-store и watcher активного
        preset-а подключаются во второй фазе старта, не блокируя первый
        визуальный отклик.
        """
        self._get_ui_root().finish_bootstrap()

    def get_launch_method(self) -> str:
        from settings.mode import DEFAULT_LAUNCH_METHOD
        from ui.workflows.common import get_current_launch_method

        method = get_current_launch_method(default="")
        return method or DEFAULT_LAUNCH_METHOD

    # Window-facing API intentionally kept minimal. Page opening and routing go
    # through window_adapter/page_host/workflow layers, not through this mixin.
