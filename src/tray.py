# tray.py

import os
import sys

from PyQt6.QtWidgets import QMenu, QApplication, QStyle, QSystemTrayIcon
from PyQt6.QtGui     import QAction, QIcon
from PyQt6.QtCore    import QEvent, Qt

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False

try:
    from qfluentwidgets import SystemTrayMenu, RoundMenu
    HAS_FLUENT_TRAY_MENU = True
except ImportError:
    SystemTrayMenu = None
    RoundMenu = None
    HAS_FLUENT_TRAY_MENU = False

# ----------------------------------------------------------------------
#   SystemTrayManager
# ----------------------------------------------------------------------
class SystemTrayManager:
    """Управление иконкой в системном трее и соответствующим функционалом"""

    def __init__(self, parent, icon_path, app_version):
        """
        Args:
            parent       – главное окно приложения
            icon_path    – png/ico иконка
            app_version  – строка версии (для tooltip-а)
        """
        self.parent        = parent
        self.tray_icon     = QSystemTrayIcon(parent)
        self.app_version   = app_version

        # иконка + меню + сигналы
        self.set_icon(icon_path)
        self.setup_menu()                     # ← создаём меню
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

        # перехватываем события окна
        self.install_event_handlers()

    # ------------------------------------------------------------------
    #  ВСПЛЫВАЮЩИЕ СООБЩЕНИЯ
    # ------------------------------------------------------------------
    def show_notification(self, title, message, msec=5000):
        self.tray_icon.showMessage(
            title, message,
            QSystemTrayIcon.MessageIcon.Information, msec
        )

    # ------------------------------------------------------------------
    #  НАСТРОЙКА ИКОНКИ
    # ------------------------------------------------------------------
    def set_icon(self, icon_path):
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            self.tray_icon.setIcon(
                QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
            )
            print(f"ОШИБКА: Файл иконки {icon_path} не найден")

        # tooltip с версией
        self.tray_icon.setToolTip(f"Zapret2 v{self.app_version}")

    # ------------------------------------------------------------------
    #  КОНТЕКСТНОЕ МЕНЮ
    # ------------------------------------------------------------------
    def setup_menu(self):
        using_fluent_menu = HAS_FLUENT_TRAY_MENU and SystemTrayMenu is not None
        menu = SystemTrayMenu(parent=self.parent) if using_fluent_menu else QMenu()
        self.menu = menu

        # Диагностика: помогает понять, "появляется ли" меню и не закрывается ли сразу.
        try:
            from log import log

            menu.aboutToShow.connect(lambda: (log("Tray menu: aboutToShow", "DEBUG"), self._update_tg_proxy_tray_status()))  # type: ignore[attr-defined]
            menu.aboutToHide.connect(lambda: log("Tray menu: aboutToHide", "DEBUG"))  # type: ignore[attr-defined]
            log(f"Tray menu initialized (hasContextMenu=True)", "DEBUG")
        except Exception:
            pass

        # Применяем стиль только для обычного QMenu.
        if not using_fluent_menu:
            self._apply_menu_style(menu)

        # показать окно
        show_act = QAction("Показать", self.parent)
        if HAS_QTAWESOME:
            show_act.setIcon(qta.icon('fa5s.window-restore', color='#60cdff'))
        show_act.triggered.connect(self.show_window)
        menu.addAction(show_act)

        # Прозрачность/акрил окна (быстрые пресеты + способ восстановить видимость)
        is_win11_plus = sys.platform == "win32" and sys.getwindowsversion().build >= 22000
        opacity_menu_title = "Эффект акрилика окна" if is_win11_plus else "Прозрачность окна"
        if using_fluent_menu and RoundMenu is not None:
            opacity_menu = RoundMenu(opacity_menu_title, menu)
            if HAS_QTAWESOME:
                opacity_menu.setIcon(qta.icon('fa5s.adjust', color='#60cdff'))
            menu.addMenu(opacity_menu)
        else:
            opacity_menu = menu.addMenu(opacity_menu_title)
            if HAS_QTAWESOME:
                opacity_menu.setIcon(qta.icon('fa5s.adjust', color='#60cdff'))

        def set_opacity(value: int):
            try:
                from config.reg import set_window_opacity as _set_window_opacity
                _set_window_opacity(value)
            except Exception:
                pass

            try:
                if hasattr(self.parent, "set_window_opacity"):
                    self.parent.set_window_opacity(value)
                if hasattr(self.parent, "appearance_page") and self.parent.appearance_page:
                    self.parent.appearance_page.set_opacity_value(value)
            except Exception:
                pass

        if is_win11_plus:
            presets = [
                (100, "100% (максимальный эффект)"),
                (75, "75%"),
                (50, "50%"),
                (25, "25%"),
                (0, "0% (минимальный эффект)"),
            ]
        else:
            presets = [
                (100, "100% (непрозрачное)"),
                (75, "75%"),
                (50, "50%"),
                (25, "25%"),
                (0, "0% (прозрачный фон)"),
            ]
        for value, title in presets:
            act = QAction(title, self.parent)
            act.triggered.connect(lambda checked=False, v=value: set_opacity(v))
            opacity_menu.addAction(act)

        menu.addSeparator()

        # Telegram Proxy toggle
        self._tg_proxy_act = QAction("Telegram Proxy: выкл", self.parent)
        if HAS_QTAWESOME:
            self._tg_proxy_act.setIcon(qta.icon('fa5s.paper-plane', color='#60cdff'))
        self._tg_proxy_act.triggered.connect(self._toggle_tg_proxy)
        menu.addAction(self._tg_proxy_act)

        menu.addSeparator()

        # консоль
        console_act = QAction("Консоль", self.parent)
        if HAS_QTAWESOME:
            console_act.setIcon(qta.icon('fa5s.terminal', color='#888888'))
        console_act.triggered.connect(self.show_console)
        menu.addAction(console_act)

        menu.addSeparator()

        # ─── ДВА ОТДЕЛЬНЫХ ВЫХОДА ──────────────────────────
        exit_only_act = QAction("Выход", self.parent)
        if HAS_QTAWESOME:
            exit_only_act.setIcon(qta.icon('fa5s.sign-out-alt', color='#aaaaaa'))
        exit_only_act.triggered.connect(self.exit_only)
        menu.addAction(exit_only_act)

        exit_stop_act = QAction("Выход и остановить DPI", self.parent)
        if HAS_QTAWESOME:
            exit_stop_act.setIcon(qta.icon('fa5s.power-off', color='#e81123'))
        exit_stop_act.triggered.connect(self.exit_and_stop)
        menu.addAction(exit_stop_act)
        # ───────────────────────────────────────────────────

        self.tray_icon.setContextMenu(menu)

    def _toggle_tg_proxy(self):
        """Toggle Telegram proxy from tray menu."""
        try:
            from ui.pages.telegram_proxy_page import _get_proxy_manager
            mgr = _get_proxy_manager()
            if mgr.is_running:
                mgr.stop_proxy()
                self._tg_proxy_act.setText("Telegram Proxy: выкл")
                try:
                    from config.reg import set_tg_proxy_enabled
                    set_tg_proxy_enabled(False)
                except Exception:
                    pass
            else:
                from config.reg import (get_tg_proxy_port, get_tg_proxy_host,
                                         get_tg_proxy_upstream_enabled, get_tg_proxy_upstream_host,
                                         get_tg_proxy_upstream_port, get_tg_proxy_upstream_mode,
                                         get_tg_proxy_upstream_user, get_tg_proxy_upstream_pass)
                port = get_tg_proxy_port()
                host = get_tg_proxy_host()
                upstream_config = None
                try:
                    if get_tg_proxy_upstream_enabled():
                        up_host = get_tg_proxy_upstream_host()
                        up_port = get_tg_proxy_upstream_port()
                        if up_host and up_port > 0:
                            from telegram_proxy.wss_proxy import UpstreamProxyConfig
                            upstream_config = UpstreamProxyConfig(
                                enabled=True, host=up_host, port=up_port,
                                mode=get_tg_proxy_upstream_mode(),
                                username=get_tg_proxy_upstream_user(),
                                password=get_tg_proxy_upstream_pass(),
                            )
                except Exception:
                    pass
                mgr.start_proxy(port=port, mode="socks5", host=host,
                                upstream_config=upstream_config)
                self._tg_proxy_act.setText(f"Telegram Proxy: вкл ({port})")
                try:
                    from config.reg import set_tg_proxy_enabled
                    set_tg_proxy_enabled(True)
                except Exception:
                    pass
        except Exception as e:
            try:
                from log import log
                log(f"Tray TG proxy toggle error: {e}", "WARNING")
            except Exception:
                pass

    def _update_tg_proxy_tray_status(self):
        """Update tray menu text to reflect proxy state."""
        try:
            from ui.pages.telegram_proxy_page import _get_proxy_manager
            mgr = _get_proxy_manager()
            if mgr.is_running:
                self._tg_proxy_act.setText(f"Telegram Proxy: вкл ({mgr.port})")
            else:
                self._tg_proxy_act.setText("Telegram Proxy: выкл")
        except Exception:
            pass

    def _apply_menu_style(self, menu: QMenu):
        """Применяет стиль к меню трея"""
        # Get current theme colors
        try:
            from qfluentwidgets import isDarkTheme
            is_light = not isDarkTheme()
            theme_bg = '243, 243, 243' if is_light else '30, 30, 30'
        except Exception:
            theme_bg = '30, 30, 30'
            is_light = False

        # Цвета в зависимости от темы
        if is_light:
            bg_color = f"rgb({theme_bg})"
            text_color = "#000000"
            hover_bg = "rgba(0, 0, 0, 0.1)"
            border_color = "rgba(0, 0, 0, 0.2)"
            separator_color = "rgba(0, 0, 0, 0.15)"
        else:
            bg_color = f"rgb({theme_bg})"
            text_color = "#ffffff"
            hover_bg = "rgba(255, 255, 255, 0.1)"
            border_color = "rgba(255, 255, 255, 0.15)"
            separator_color = "rgba(255, 255, 255, 0.1)"

        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 2px 0px;
            }}
            QMenu::item {{
                background-color: transparent;
                color: {text_color};
                padding: 3px 16px 3px 8px;
                margin: 0px 3px;
                border-radius: 3px;
                font-size: 11px;
            }}
            QMenu::item:selected {{
                background-color: {hover_bg};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {separator_color};
                margin: 2px 6px;
            }}
            QMenu::icon {{
                padding-left: 4px;
            }}
        """)

    # ------------------------------------------------------------------
    #  ВСПОМОГАТЕЛЬНЫЙ МЕТОД ДЛЯ СОХРАНЕНИЯ ГЕОМЕТРИИ
    # ------------------------------------------------------------------
    def _save_window_geometry(self):
        """Сохраняет текущую позицию и размер окна"""
        try:
            # Предпочтительно: единый persistence-слой главного окна.
            if hasattr(self.parent, "_persist_window_geometry_now"):
                self.parent._persist_window_geometry_now(force=True)
                return

            # Fallback для окон без современного persistence.
            from config import set_window_position, set_window_size, set_window_maximized
            from log import log

            if not self.parent.isVisible():
                return

            try:
                state = self.parent.windowState()
                is_zoomed = bool(
                    self.parent.isMaximized()
                    or self.parent.isFullScreen()
                    or (state & Qt.WindowState.WindowMaximized)
                    or (state & Qt.WindowState.WindowFullScreen)
                )
            except Exception:
                is_zoomed = bool(self.parent.isMaximized())

            if is_zoomed:
                geo = self.parent.normalGeometry()
            else:
                geo = self.parent.geometry()

            set_window_position(geo.x(), geo.y())
            set_window_size(geo.width(), geo.height())
            set_window_maximized(bool(is_zoomed))

            log(
                f"Геометрия окна сохранена: ({geo.x()}, {geo.y()}), {geo.width()}x{geo.height()}, maximized={bool(is_zoomed)}",
                "DEBUG",
            )
        except Exception as e:
            from log import log
            log(f"Ошибка сохранения геометрии окна: {e}", "❌ ERROR")

    def _cleanup_transient_overlays(self) -> None:
        """Закрывает плавающие tooltip/preview окна перед hide/show."""
        try:
            from ui.widgets.strategies_tooltip import strategies_tooltip_manager
            strategies_tooltip_manager.hide_immediately()
        except Exception:
            pass

        try:
            from strategy_menu.hover_tooltip import tooltip_manager
            tooltip_manager.hide_immediately()
        except Exception:
            pass

        try:
            from strategy_menu.args_preview_dialog import preview_manager
            preview_manager.cleanup()
        except Exception:
            pass

        try:
            if hasattr(self.parent, "strategy_detail_page"):
                self.parent.strategy_detail_page._close_preview_dialog(force=True)
        except Exception:
            pass

    def hide_to_tray(self, show_hint: bool = True) -> None:
        """Скрывает окно в трей (без выхода из GUI)."""
        try:
            self._cleanup_transient_overlays()
        except Exception:
            pass

        try:
            # ✅ СОХРАНЯЕМ ПОЗИЦИЮ ПЕРЕД СКРЫТИЕМ
            self._save_window_geometry()
        except Exception:
            pass

        try:
            self.parent.hide()
        except Exception:
            return

        if not show_hint:
            return

        # ✅ ПОКАЗЫВАЕМ УВЕДОМЛЕНИЕ ТОЛЬКО ОДИН РАЗ ЗА ВСЁ ВРЕМЯ
        try:
            from config import get_tray_hint_shown, set_tray_hint_shown
            if not get_tray_hint_shown():
                self.show_notification(
                    "Zapret продолжает работать",
                    "Свернуто в трей. Кликните по иконке, чтобы открыть окно."
                )
                set_tray_hint_shown(True)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 1) ПРОСТО закрыть GUI, winws.exe оставить жить
    # ------------------------------------------------------------------
    def exit_only(self):
        """Закрывает GUI, процесс winws.exe остаётся запущенным."""
        # Единая точка выхода: DPI не трогаем.
        if hasattr(self.parent, "request_exit"):
            self.parent.request_exit(stop_dpi=False)
            return

        # Fallback для старой архитектуры
        from log import log
        log("Выход без остановки DPI (fallback, только GUI)", level="INFO")
        self.tray_icon.hide()
        QApplication.quit()

    # ------------------------------------------------------------------
    # 2) СТАРОЕ ПОВЕДЕНИЕ – остановить DPI и выйти
    # ------------------------------------------------------------------
    def exit_and_stop(self):
        """Останавливает winws.exe, затем закрывает GUI."""
        # Единая точка выхода: остановить DPI и выйти (учитывает все режимы).
        if hasattr(self.parent, "request_exit"):
            self.parent.request_exit(stop_dpi=True)
            return

        # Fallback для старой архитектуры
        from dpi.stop import stop_dpi
        from log import log
        log("Выход + остановка DPI (fallback)", level="INFO")
        if hasattr(self.parent, 'dpi_starter'):
            stop_dpi(self.parent)
        self.tray_icon.hide()
        QApplication.quit()

    # ------------------------------------------------------------------
    #  РЕАКЦИЯ НА КЛИКИ ПО ИКОНКЕ
    # ------------------------------------------------------------------
    def on_tray_icon_activated(self, reason):
        # Диагностика: 1=Trigger (LMB), 2=DoubleClick, 3=MiddleClick, 4=Context (RMB)
        try:
            from log import log

            def _enum_to_int(v):
                try:
                    return int(v)
                except Exception:
                    try:
                        return int(v.value)
                    except Exception:
                        return str(v)

            log(
                f"Tray activated: reason={_enum_to_int(reason)} visible={self.parent.isVisible()}",
                "DEBUG",
            )
        except Exception:
            pass

        if reason == QSystemTrayIcon.ActivationReason.Trigger:          # левая кнопка
            if self.parent.isVisible():
                self.hide_to_tray(show_hint=False)
            else:
                self.show_window()

    # ------------------------------------------------------------------
    #  КОНСОЛЬ
    # ------------------------------------------------------------------
    def show_console(self):
        from PyQt6.QtWidgets import QInputDialog, QLineEdit
        from discord.discord_restart import toggle_discord_restart
        from github_api_toggle import toggle_github_api_removal

        cmd, ok = QInputDialog.getText(
            self.parent, "Консоль", "Введите команду:",
            QLineEdit.EchoMode.Normal, ""
        )
        if ok and cmd:
            if cmd.lower() == "ркн":
                toggle_discord_restart(
                    self.parent,
                    status_callback=lambda m: self.show_notification("Консоль", m)
                )
            elif cmd.lower() == "апигитхаб":
                toggle_github_api_removal(
                    self.parent,
                    status_callback=lambda m: self.show_notification("Консоль", m)
                )

    # ------------------------------------------------------------------
    #  ПРОЧИЕ ДЕЙСТВИЯ
    # ------------------------------------------------------------------
    def show_window(self):
        """Показывает окно и восстанавливает его на прежнем месте"""
        try:
            self._cleanup_transient_overlays()
        except Exception:
            pass

        was_maximized = False
        runtime_state_detected = False
        try:
            if hasattr(self.parent, "_is_window_zoomed"):
                was_maximized = bool(self.parent._is_window_zoomed())
            else:
                state = self.parent.windowState()
                was_maximized = bool(
                    self.parent.isMaximized()
                    or self.parent.isFullScreen()
                    or (state & Qt.WindowState.WindowMaximized)
                    or (state & Qt.WindowState.WindowFullScreen)
                    or getattr(self.parent, "_was_maximized", False)
                )
            runtime_state_detected = True
        except Exception:
            pass

        if not runtime_state_detected:
            try:
                from config import get_window_maximized
                was_maximized = bool(get_window_maximized())
            except Exception:
                pass

        if hasattr(self.parent, "_request_window_zoom_state"):
            try:
                self.parent._request_window_zoom_state(bool(was_maximized))
            except Exception:
                if was_maximized:
                    self.parent.showMaximized()
                else:
                    self.parent.showNormal()
        else:
            if was_maximized:
                self.parent.showMaximized()
            else:
                self.parent.showNormal()

        self.parent.activateWindow()
        self.parent.raise_()

    # ------------------------------------------------------------------
    #  ВСПОМОГАТЕЛЬНЫЕ
    # ------------------------------------------------------------------
    def install_event_handlers(self):
        self._orig_close  = self.parent.closeEvent
        self._orig_change = self.parent.changeEvent
        self.parent.closeEvent  = self._close_event
        self.parent.changeEvent = self._change_event

    def _close_event(self, ev):
        # ✅ ПРОВЕРЯЕМ флаг полного закрытия программы
        if hasattr(self.parent, '_closing_completely') and self.parent._closing_completely:
            # Программа полностью закрывается - вызываем оригинальный closeEvent
            # (который сохранит позицию)
            self._orig_close(ev)
            return

        # Обычное закрытие окна (Alt+F4, системное закрытие и т.д.)
        # Диалог показываем только когда DPI запущен.
        ev.ignore()
        try:
            from ui.close_dialog import ask_close_action

            result = ask_close_action(parent=self.parent)
            if result is None:
                # Пользователь отменил
                return

            if result == "tray":
                self.hide_to_tray(show_hint=True)
                return

            # result: False = только GUI, True = GUI + остановить DPI
            self.parent.request_exit(stop_dpi=result)
        except Exception:
            # Fallback: закрыть только GUI
            self.exit_only()

    def _change_event(self, ev):
        self._orig_change(ev)
