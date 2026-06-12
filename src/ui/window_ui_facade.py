# ui/window_ui_facade.py
"""
Главное окно приложения — навигация через qfluentwidgets FluentWindow.

Все страницы добавляются через addSubInterface() вместо ручного SideNavBar + QStackedWidget.
Бизнес-логика (сигналы, обработчики) сохранена без изменений.
"""
_SIDEBAR_SEARCH_NAV_WIDGET_CLS = None


def _get_nav_icons():
    from ui.navigation.icons import build_nav_icons

    return build_nav_icons()


def _get_nav_labels():
    from app.page_names import PageName

    return {
        PageName.NETWORK: "Настройка DNS",
        PageName.HOSTS: "Редактор hosts",
        PageName.BLOCKCHECK: "BlockCheck",
        PageName.APPEARANCE: "Оформление",
        PageName.PREMIUM: "Донат",
        PageName.LOGS: "Логи",
        PageName.ABOUT: "О программе",
        PageName.DPI_SETTINGS: "Сменить режим DPI",
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


def _default_nav_icon():
    from ui.navigation.icons import default_nav_icon

    return default_nav_icon()


def _nav_scroll_position():
    from qfluentwidgets import NavigationItemPosition

    return NavigationItemPosition.SCROLL


def _get_sidebar_search_nav_widget_cls():
    global _SIDEBAR_SEARCH_NAV_WIDGET_CLS
    if _SIDEBAR_SEARCH_NAV_WIDGET_CLS is not None:
        return _SIDEBAR_SEARCH_NAV_WIDGET_CLS

    from PyQt6.QtCore import QEvent, QTimer, Qt, pyqtSignal
    from PyQt6.QtWidgets import QWidget, QHBoxLayout
    from app.ui_texts import tr as tr_catalog
    from ui.accessibility import remove_line_edit_buttons_from_tab_order, set_control_accessibility, set_state_text
    from qfluentwidgets import SearchLineEdit

    class _SidebarSearchNavWidget(QWidget):
        textChanged = pyqtSignal(str)
        completionNavigationRequested = pyqtSignal(int)
        completionActivationRequested = pyqtSignal()

        def __init__(self, parent: QWidget | None = None):
            super().__init__(parent)
            self._search = SearchLineEdit(self)
            self._completion_timer = QTimer(self)
            self._completion_timer.setSingleShot(True)
            self._completion_timer.timeout.connect(self._show_completions_deferred)
            self._search.setPlaceholderText(tr_catalog("sidebar.search.placeholder"))
            search_description = (
                "Ищет страницу, preset или profile. Введите текст, выберите результат стрелками. "
                "Enter открывает выбранный результат."
            )
            set_control_accessibility(
                self,
                name="Глобальный поиск по ZapretGUI",
                description=search_description,
            )
            set_state_text(self, "Глобальный поиск по ZapretGUI")
            set_control_accessibility(
                self._search,
                name="Глобальный поиск по ZapretGUI",
                description=search_description,
            )
            set_state_text(self._search, "Глобальный поиск по ZapretGUI")
            try:
                self._search.setClearButtonEnabled(True)
            except Exception:
                pass
            remove_line_edit_buttons_from_tab_order(self._search)
            self._search.textChanged.connect(self.textChanged.emit)
            self._search.installEventFilter(self)

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

        def set_completer(self, completer) -> None:
            self._search.setCompleter(completer)

        def set_keyboard_result_text(self, text: str) -> None:
            value = str(text or "").strip() or "Глобальный поиск по ZapretGUI"
            set_state_text(self, value)
            set_state_text(self._search, value)

        def eventFilter(self, watched, event):  # noqa: N802
            if watched is self._search and event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Down:
                    self.completionNavigationRequested.emit(1)
                    event.accept()
                    return True
                if event.key() == Qt.Key.Key_Up:
                    self.completionNavigationRequested.emit(-1)
                    event.accept()
                    return True
                if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self.completionActivationRequested.emit()
                    event.accept()
                    return True
            return super().eventFilter(watched, event)

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

    _SidebarSearchNavWidget.__name__ = "_SidebarSearchNavWidget"
    _SIDEBAR_SEARCH_NAV_WIDGET_CLS = _SidebarSearchNavWidget
    return _SIDEBAR_SEARCH_NAV_WIDGET_CLS


def __getattr__(name: str):
    if name == "_SidebarSearchNavWidget":
        return _get_sidebar_search_nav_widget_cls()
    raise AttributeError(name)


class MainWindowUI:
    """
    Mixin: creates pages and registers them with FluentWindow navigation.
    """

    def _get_ui_root(self):
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
            nav_icons=_get_nav_icons(),
            nav_labels=_get_nav_labels(),
            default_nav_icon=_default_nav_icon(),
            nav_scroll_position=_nav_scroll_position(),
            sidebar_search_widget_cls=_get_sidebar_search_nav_widget_cls(),
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
