# main.py
import sys, os
import time as _startup_clock


_STARTUP_T0 = _startup_clock.perf_counter()


def _startup_elapsed_ms() -> int:
    return int((_startup_clock.perf_counter() - _STARTUP_T0) * 1000)


def _is_startup_debug_enabled() -> bool:
    raw = os.environ.get("ZAPRET_STARTUP_DEBUG")
    if raw is not None and str(raw).strip() != "":
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    for arg in sys.argv[1:]:
        if str(arg).strip().lower() in {"--startup-debug", "--verbose-log"}:
            return True

    return False


def _is_cpu_diagnostic_enabled() -> bool:
    raw = os.environ.get("ZAPRET_CPU_DIAGNOSTIC")
    if raw is not None and str(raw).strip() != "":
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    for arg in sys.argv[1:]:
        if str(arg).strip().lower() in {"--cpu-diagnostic", "--cpu-debug"}:
            return True

    return False

# ──────────────────────────────────────────────────────────────
# Делаем рабочей директорией папку, где лежит exe/скрипт
# Нужно выполнить до любых других импортов!
# ──────────────────────────────────────────────────────────────
def _set_workdir_to_app():
    """Устанавливает рабочую директорию"""
    try:
        if "__compiled__" in globals():
            # Nuitka
            app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        else:
            # PyInstaller
            app_dir = os.path.dirname(sys.executable)

        os.chdir(app_dir)
        
        # Отладочный startup файл нужен только при явном включении.
        if _is_startup_debug_enabled():
            debug_info = f"""
=== ZAPRET STARTUP DEBUG ===
Compiled mode: {'__compiled__' in globals()}
Frozen mode: {getattr(sys, 'frozen', False)}
sys.executable: {sys.executable}
sys.argv[0]: {sys.argv[0]}
Working directory: {app_dir}
Directory exists: {os.path.exists(app_dir)}
Directory contents: {os.listdir(app_dir) if os.path.exists(app_dir) else 'N/A'}
========================
"""

            with open("zapret_startup.log", "w", encoding="utf-8") as f:
                f.write(debug_info)
            
    except Exception as e:
        with open("zapret_startup_error.log", "w", encoding="utf-8") as f:
            f.write(f"Error setting workdir: {e}\n")
            import traceback
            f.write(traceback.format_exc())

_set_workdir_to_app()

# ──────────────────────────────────────────────────────────────
# Запрещаем запуск из исходников — только exe (PyInstaller/Nuitka)
# ──────────────────────────────────────────────────────────────
def _require_frozen():
    is_frozen = getattr(sys, "frozen", False) or ("__compiled__" in globals())
    if not is_frozen:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                "Запустите программу через Zapret.exe\n\nЗапуск напрямую из исходников не поддерживается.",
                "Zapret — Ошибка запуска",
                0x10,  # MB_ICONERROR | MB_OK
            )
        except Exception:
            print("ERROR: Запуск из исходников не поддерживается. Используйте Zapret.exe")
        sys.exit(1)

_require_frozen()

# ──────────────────────────────────────────────────────────────
# ✅ УБРАНО: Очистка _MEI* папок больше не нужна
# Приложение собирается в режиме --onedir (папка с файлами)
# вместо --onefile, поэтому временные папки не создаются
# ──────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────
# Устанавливаем глобальный обработчик крашей (ДО всех импортов!)
# ──────────────────────────────────────────────────────────────
from log.crash_handler import install_crash_handler
if os.environ.get("ZAPRET_DISABLE_CRASH_HANDLER") != "1":
    install_crash_handler()

# ──────────────────────────────────────────────────────────────
# Предзагрузка медленных модулей в фоне (ускоряет старт на ~300ms)
# НЕ включает qfluentwidgets/qtawesome — они создают Qt объекты
# и должны импортироваться только в главном потоке после QApplication.
# ──────────────────────────────────────────────────────────────
def _preload_slow_modules():
    """Загружает медленные модули в фоновом потоке.

    Когда основной код дойдёт до импорта этих модулей,
    они уже будут в sys.modules - импорт будет мгновенным.
    """
    import threading

    def _preload():
        try:
            import jinja2            # ~1ms
            import requests          # ~99ms
            import psutil            # ~10ms
            import json              # для config и API
            import winreg            # для реестра Windows
        except Exception:
            pass  # Ошибки при предзагрузке не критичны

    t = threading.Thread(target=_preload, daemon=True)
    t.start()

_preload_slow_modules()

# ──────────────────────────────────────────────────────────────
# QApplication MUST exist before importing qfluentwidgets
# (it creates Qt objects at import time: icons, theme singletons, etc.)
# ──────────────────────────────────────────────────────────────
import subprocess, time

from PyQt6.QtCore    import QTimer, QEvent, Qt, QCoreApplication, pyqtSlot, QMetaObject, Q_ARG
from PyQt6.QtWidgets import QMessageBox, QWidget, QApplication

os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
os.environ["QT_API"] = "pyqt6"  # Force qtpy/qtawesome to use PyQt6 (not PyQt5)

def _set_attr_if_exists(name: str, on: bool = True) -> None:
    """Безопасно включает атрибут, если он есть в текущей версии Qt."""
    attr = getattr(Qt.ApplicationAttribute, name, None)
    if attr is None:
        attr = getattr(Qt, name, None)
    if attr is not None:
        QCoreApplication.setAttribute(attr, on)

_set_attr_if_exists("AA_EnableHighDpiScaling")
_set_attr_if_exists("AA_UseHighDpiPixmaps")

# Create QApplication early — qfluentwidgets requires it at import time
_app = QApplication.instance() or QApplication(sys.argv)

from ui.combo_popup_guard import install_global_combo_popup_closer
install_global_combo_popup_closer(_app)

# ── Python 3.14 + PyQt6 6.10 compat ───────────────────────────────────────────
# В Python 3.14 изменился протокол дескрипторов для C-extension slot'ов.
# instance.method() больше не связывает self корректно для sip-wrapped Qt методов,
# из-за чего qfluentwidgets animation.start() / stop() / pause() дают:
#   TypeError: start(...): first argument of unbound method must have type 'QAbstractAnimation'
# Решение: заменяем C-слоты тонкими Python-обёртками, у которых __get__ работает правильно.
def _install_animation_py314_compat() -> None:
    if sys.version_info < (3, 14):
        return
    try:
        from PyQt6.QtCore import (
            QAbstractAnimation, QVariantAnimation, QPropertyAnimation,
            QSequentialAnimationGroup, QParallelAnimationGroup,
        )
    except ImportError:
        return
    try:
        _c_start  = QAbstractAnimation.start
        _c_stop   = QAbstractAnimation.stop
        _c_pause  = QAbstractAnimation.pause
        _c_resume = QAbstractAnimation.resume
    except AttributeError:
        return

    _DP = QAbstractAnimation.DeletionPolicy

    def _start(self, policy: _DP = _DP.KeepWhenStopped) -> None:  # noqa: E704
        _c_start(self, policy)

    def _stop(self) -> None:
        _c_stop(self)

    def _pause(self) -> None:
        _c_pause(self)

    def _resume(self) -> None:
        _c_resume(self)

    _patches = {'start': _start, 'stop': _stop, 'pause': _pause, 'resume': _resume}
    _classes = (
        QAbstractAnimation, QVariantAnimation, QPropertyAnimation,
        QSequentialAnimationGroup, QParallelAnimationGroup,
    )
    for cls in _classes:
        for attr, fn in _patches.items():
            try:
                if hasattr(cls, attr):
                    setattr(cls, attr, fn)
            except Exception:
                pass

_install_animation_py314_compat()


def _install_qfluent_label_ctor_compat() -> None:
    """Accept legacy (text, parent) for qfluent label classes.

    Newer qfluentwidgets builds expose label ctors as either `(text)` or `(parent)`.
    A lot of project code still passes `(text, parent)`, which crashes at runtime.
    """
    try:
        from qfluentwidgets import (
            SubtitleLabel,
            TitleLabel,
            BodyLabel,
            StrongBodyLabel,
            CaptionLabel,
        )
    except Exception:
        return

    classes = (SubtitleLabel, TitleLabel, BodyLabel, StrongBodyLabel, CaptionLabel)

    for cls in classes:
        try:
            if getattr(cls, "_zapret_ctor_compat", False):
                continue

            original_init = cls.__init__

            def _make_init(_orig):
                def _compat_init(self, *args, **kwargs):
                    if len(args) == 2 and not kwargs:
                        text, parent = args
                        try:
                            _orig(self, parent)
                            try:
                                self.setText(str(text))
                            except Exception:
                                pass
                            return
                        except Exception:
                            pass

                    _orig(self, *args, **kwargs)

                return _compat_init

            cls.__init__ = _make_init(original_init)
            cls._zapret_ctor_compat = True
        except Exception:
            pass


_install_qfluent_label_ctor_compat()
# ──────────────────────────────────────────────────────────────────────────────

from ui.main_window import MainWindowUI
from ui.fluent_app_window import ZapretFluentWindow
from ui.holiday_effects import HolidayEffectsManager


from startup.admin_check import is_admin

from config import WIDTH, HEIGHT, MIN_WIDTH
from config import APP_VERSION
from utils import run_hidden

from ui.theme_subscription_manager import ThemeSubscriptionManager
from ui.theme import install_qtawesome_icon_theme_patch

# DNS настройки теперь интегрированы в network_page
from log import log, is_verbose_logging_enabled, global_logger


def _log_startup_metric(marker: str, details: str = "") -> None:
    suffix = f" | {details}" if details else ""
    log(f"⏱ Startup {marker}: {_startup_elapsed_ms()}ms{suffix}", "⏱ STARTUP")

from ui.page_names import PageName

# Global icon policy (theme-aware + rgba() normalization for qtawesome).
install_qtawesome_icon_theme_patch()

# Connect qfluentwidgets accent signal → invalidate tokens cache so all pages
# recompute CSS with the new accent color when setThemeColor() is called.
from ui.theme import connect_qfluent_accent_signal
connect_qfluent_accent_signal()


# _set_attr_if_exists defined earlier (before QApplication creation)

def _handle_update_mode():
    """updater.py запускает: main.py --update <old_exe> <new_exe>"""
    import os, sys, time, shutil, subprocess
    
    if len(sys.argv) < 4:
        log("--update: недостаточно аргументов", "❌ ERROR")
        return

    old_exe, new_exe = sys.argv[2], sys.argv[3]

    # ждём, пока старый exe освободится
    for _ in range(10):  # 10 × 0.5 c = 5 сек
        if not os.path.exists(old_exe) or os.access(old_exe, os.W_OK):
            break
        time.sleep(0.5)

    try:
        shutil.copy2(new_exe, old_exe)
        run_hidden([old_exe])          # запускаем новую версию
        log("Файл обновления применён", "INFO")
    except Exception as e:
        log(f"Ошибка в режиме --update: {e}", "❌ ERROR")
    finally:
        try:
            os.remove(new_exe)
        except FileNotFoundError:
            pass

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from managers.ui_manager import UIManager
    from managers.dpi_manager import DPIManager
    from managers.process_monitor_manager import ProcessMonitorManager
    from managers.subscription_manager import SubscriptionManager
    from managers.initialization_manager import InitializationManager

class LupiDPIApp(ZapretFluentWindow, MainWindowUI, ThemeSubscriptionManager):
    """Главное окно приложения — FluentWindow + навигация + подписки."""

    from ui.theme import ThemeHandler
    # ✅ ДОБАВЛЯЕМ TYPE HINTS для менеджеров
    ui_manager: 'UIManager'
    dpi_manager: 'DPIManager'
    process_monitor_manager: 'ProcessMonitorManager'
    subscription_manager: 'SubscriptionManager'
    initialization_manager: 'InitializationManager'
    theme_handler: 'ThemeHandler'

    def closeEvent(self, event):
        """Обрабатывает событие закрытия окна"""
        self._is_exiting = True

        try:
            if hasattr(global_logger, "set_ui_error_notifier"):
                global_logger.set_ui_error_notifier(None)
        except Exception:
            pass
        
        # ✅ Гарантированно сохраняем геометрию/состояние окна при выходе
        try:
            self._persist_window_geometry_now(force=True)
        except Exception as e:
            log(f"Ошибка сохранения геометрии окна при закрытии: {e}", "❌ ERROR")
        
        # ✅ Очищаем менеджеры через их методы
        if hasattr(self, 'process_monitor_manager'):
            self.process_monitor_manager.stop_monitoring()
        
        # ✅ Очищаем DNS UI Manager
        if hasattr(self, 'dns_ui_manager'):
            self.dns_ui_manager.cleanup()
        
        # ✅ Очищаем Theme Manager
        if hasattr(self, 'theme_handler') and hasattr(self.theme_handler, 'theme_manager'):
            try:
                self.theme_handler.theme_manager.cleanup()
            except Exception as e:
                log(f"Ошибка при очистке theme_manager: {e}", "DEBUG")
        
        # ✅ Очищаем страницы с потоками
        try:
            if hasattr(self, 'logs_page') and hasattr(self.logs_page, 'cleanup'):
                self.logs_page.cleanup()
            if hasattr(self, 'servers_page') and hasattr(self.servers_page, 'cleanup'):
                self.servers_page.cleanup()
            if hasattr(self, 'blockcheck_page') and hasattr(self.blockcheck_page, 'cleanup'):
                self.blockcheck_page.cleanup()
            if hasattr(self, 'connection_page') and hasattr(self.connection_page, 'cleanup'):
                self.connection_page.cleanup()
            if hasattr(self, 'dns_check_page') and hasattr(self.dns_check_page, 'cleanup'):
                self.dns_check_page.cleanup()
            if hasattr(self, 'hosts_page') and hasattr(self.hosts_page, 'cleanup'):
                self.hosts_page.cleanup()
        except Exception as e:
            log(f"Ошибка при очистке страниц: {e}", "DEBUG")

        # Cleanup Telegram proxy
        try:
            from ui.pages.telegram_proxy_page import _get_proxy_manager
            _get_proxy_manager().cleanup()
        except Exception:
            pass

        # Очищаем праздничные оверлеи
        try:
            effects = getattr(self, "_holiday_effects", None)
            if effects is not None:
                effects.cleanup()
                self._holiday_effects = None
        except Exception as e:
            log(f"Ошибка очистки праздничных эффектов: {e}", "DEBUG")
        
        # ✅ Очищаем потоки через контроллер
        if hasattr(self, 'dpi_controller'):
            self.dpi_controller.cleanup_threads()

        # ✅ ВАЖНО: winws/winws2 не должны останавливаться при "Выход" из трея/меню.
        # Останавливаем процессы только если явно запрошен "Выход и остановить DPI".
        if getattr(self, "_stop_dpi_on_exit", False):
            try:
                from utils.process_killer import kill_winws_force
                kill_winws_force()
                log("Процессы winws завершены при закрытии приложения (stop_dpi_on_exit=True)", "DEBUG")
            except Exception as e:
                log(f"Ошибка остановки winws при закрытии: {e}", "DEBUG")
        else:
            log("Выход без остановки DPI: winws не трогаем", "DEBUG")

        # Останавливаем все асинхронные операции без уведомлений
        try:
            if hasattr(self, '_dpi_start_thread') and self._dpi_start_thread:
                try:
                    if self._dpi_start_thread.isRunning():
                        self._dpi_start_thread.quit()
                        self._dpi_start_thread.wait(1000)
                except RuntimeError:
                    pass
            
            if hasattr(self, '_dpi_stop_thread') and self._dpi_stop_thread:
                try:
                    if self._dpi_stop_thread.isRunning():
                        self._dpi_stop_thread.quit()
                        self._dpi_stop_thread.wait(1000)
                except RuntimeError:
                    pass
        except Exception as e:
            log(f"Ошибка при очистке потоков: {e}", "❌ ERROR")

        super().closeEvent(event)

    def _release_input_interaction_states(self) -> None:
        """Сбрасывает drag/resize состояния при скрытии/потере фокуса окна."""
        try:
            if bool(getattr(self, "_is_resizing", False)) and hasattr(self, "_end_resize"):
                self._end_resize()
            else:
                self._is_resizing = False
                self._resize_edge = None
                self._resize_start_pos = None
                self._resize_start_geometry = None
                self.unsetCursor()
        except Exception:
            pass

        try:
            self._is_dragging = False
            self._drag_start_pos = None
            self._drag_window_pos = None
        except Exception:
            pass

        try:
            tb = getattr(self, "title_bar", None)
            if tb is not None:
                tb._is_moving = False
                tb._is_system_moving = False
                tb._drag_pos = None
                tb._window_pos = None
        except Exception:
            pass

    def request_exit(self, stop_dpi: bool) -> None:
        """Единая точка выхода из приложения.

        - stop_dpi=False: закрыть GUI, DPI оставить работать.
        - stop_dpi=True: остановить DPI и выйти (учитывает текущий launch_method).
        """
        from PyQt6.QtWidgets import QApplication

        self._stop_dpi_on_exit = bool(stop_dpi)

        self._closing_completely = True

        # Сохраняем геометрию/состояние окна сразу (без debounce).
        try:
            self._persist_window_geometry_now(force=True)
        except Exception as e:
            log(f"Ошибка сохранения геометрии окна при request_exit: {e}", "DEBUG")

        # Скрываем иконку трея (если есть) — пользователь выбрал полный выход.
        try:
            if hasattr(self, "tray_manager") and self.tray_manager:
                self.tray_manager.tray_icon.hide()
        except Exception:
            pass

        if stop_dpi:
            log("Запрошен выход: остановить DPI и выйти", "INFO")

            # Предпочтительно: асинхронная остановка + выход.
            try:
                if hasattr(self, "dpi_controller") and self.dpi_controller:
                    self.dpi_controller.stop_and_exit_async()
                    return
            except Exception as e:
                log(f"stop_and_exit_async не удалось: {e}", "WARNING")

            # Fallback: синхронная остановка.
            try:
                from dpi.stop import stop_dpi
                stop_dpi(self)
            except Exception as e:
                log(f"Ошибка остановки DPI перед выходом: {e}", "WARNING")

        else:
            log("Запрошен выход: выйти без остановки DPI", "INFO")

        # Закрываем все окна — это вызовет closeEvent с полной очисткой
        # потоков, страниц и менеджеров (т.к. _closing_completely=True).
        # Без этого closeEvent не вызывается и cleanup не происходит → краш.
        QApplication.closeAllWindows()
        QApplication.processEvents()
        QApplication.quit()

    def minimize_to_tray(self) -> None:
        """Скрывает окно в трей (без выхода из GUI)."""
        try:
            if hasattr(self, "tray_manager") and self.tray_manager:
                self.tray_manager.hide_to_tray(show_hint=True)
                return
        except Exception:
            pass

        try:
            self.hide()
        except Exception:
            pass

    def restore_window_geometry(self):
        """Восстанавливает сохраненную позицию и размер окна"""
        self._geometry_restore_in_progress = True
        try:
            from config import get_window_position, get_window_size, get_window_maximized, WIDTH, HEIGHT

            min_width = MIN_WIDTH
            min_height = 400

            # Сначала читаем maximize-флаг: он нужен для валидации legacy-геометрии.
            saved_maximized = bool(get_window_maximized())

            screen_geometry = QApplication.primaryScreen().availableGeometry()
            screens = QApplication.screens()

            def _looks_like_legacy_maximized_geometry(width: int, height: int) -> bool:
                """Определяет старую некорректную normal-геометрию (сохранена как fullscreen)."""
                if not saved_maximized:
                    return False
                for screen in screens:
                    rect = screen.availableGeometry()
                    if width >= (rect.width() - 4) and height >= (rect.height() - 4):
                        return True
                return False

            # Размер
            saved_size = get_window_size()
            if saved_size:
                width, height = saved_size
                if _looks_like_legacy_maximized_geometry(width, height):
                    log(
                        "Обнаружена legacy normal-геометрия (размер почти как fullscreen); используем размер по умолчанию",
                        "WARNING",
                    )
                    width, height = WIDTH, HEIGHT

                if width >= min_width and height >= min_height:
                    self.resize(width, height)
                    log(f"Восстановлен размер окна: {width}x{height}", "DEBUG")
                else:
                    log(f"Сохраненный размер слишком мал ({width}x{height}), используем по умолчанию", "DEBUG")
                    self.resize(WIDTH, HEIGHT)
            else:
                self.resize(WIDTH, HEIGHT)

            # Позиция
            saved_pos = get_window_position()

            if saved_pos:
                x, y = saved_pos

                is_visible = False
                for screen in screens:
                    screen_rect = screen.availableGeometry()
                    # Окно считается видимым если хотя бы 100x100 пикселей на экране
                    if (x + 100 > screen_rect.left() and
                        x < screen_rect.right() and
                        y + 100 > screen_rect.top() and
                        y < screen_rect.bottom()):
                        is_visible = True
                        break

                if is_visible:
                    self.move(x, y)
                    log(f"Восстановлена позиция окна: ({x}, {y})", "DEBUG")
                else:
                    self.move(
                        screen_geometry.center().x() - self.width() // 2,
                        screen_geometry.center().y() - self.height() // 2
                    )
                    log("Сохраненная позиция за пределами экранов, окно отцентрировано", "WARNING")
            else:
                self.move(
                    screen_geometry.center().x() - self.width() // 2,
                    screen_geometry.center().y() - self.height() // 2
                )
                log("Позиция не сохранена, окно отцентрировано", "DEBUG")

            # Сохраняем нормальную геометрию (для корректного закрытия из maximized)
            self._last_normal_geometry = (int(self.x()), int(self.y()), int(self.width()), int(self.height()))
            self._last_non_minimized_zoomed = saved_maximized

            # Maximized будем применять при первом showEvent (особенно важно для start_in_tray/splash)
            self._pending_restore_maximized = saved_maximized

        except Exception as e:
            log(f"Ошибка восстановления геометрии окна: {e}", "❌ ERROR")
            from config import WIDTH, HEIGHT
            self.resize(WIDTH, HEIGHT)
        finally:
            self._geometry_restore_in_progress = False

    def set_status(self, text: str) -> None:
        """Sets the status text."""
        # Обновляем статус на главной странице
        if hasattr(self, 'home_page'):
            # Определяем тип статуса по тексту
            status_type = "neutral"
            if "работает" in text.lower() or "запущен" in text.lower() or "успешно" in text.lower():
                status_type = "running"
            elif "останов" in text.lower() or "ошибка" in text.lower() or "выключен" in text.lower():
                status_type = "stopped"
            elif "внимание" in text.lower() or "предупреждение" in text.lower():
                status_type = "warning"
            self.home_page.set_status(text, status_type)

    def _register_global_error_notifier(self) -> None:
        """Подключает глобальные ERROR/CRITICAL логи к верхнему InfoBar."""
        try:
            if hasattr(global_logger, "set_ui_error_notifier"):
                global_logger.set_ui_error_notifier(self._enqueue_global_error_infobar)
        except Exception as e:
            log(f"Ошибка подключения глобального error-notifier: {e}", "DEBUG")

    def _enqueue_global_error_infobar(self, message: str) -> None:
        """Thread-safe показ ошибки в верхнем InfoBar."""
        text = str(message or "").strip()
        if not text:
            return

        try:
            QMetaObject.invokeMethod(
                self,
                "show_dpi_launch_error",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, text),
            )
        except Exception:
            try:
                self.show_dpi_launch_error(text)
            except Exception:
                pass

    @pyqtSlot(str)
    def show_dpi_launch_error(self, message: str) -> None:
        """Показывает ошибку сверху окна через InfoBar.

        If the message starts with ``[AUTOFIX:<action>]``, a "Fix" button is
        added and the InfoBar stays visible until manually closed.
        """
        import re as _re

        text = str(message or "").strip()
        if not text:
            text = "Не удалось запустить DPI"

        # Extract optional auto-fix action from prefix
        auto_fix_action: str | None = None
        m = _re.match(r"^\[AUTOFIX:(\w+)]", text)
        if m:
            auto_fix_action = m.group(1)
            text = text[m.end():]

        # Дедупликация одинаковых ошибок, прилетевших подряд.
        try:
            now = time.time()
            last_msg = str(getattr(self, "_last_dpi_launch_error_message", "") or "")
            last_ts = float(getattr(self, "_last_dpi_launch_error_ts", 0.0) or 0.0)
            if text == last_msg and (now - last_ts) < 1.5:
                return
            self._last_dpi_launch_error_message = text
            self._last_dpi_launch_error_ts = now
        except Exception:
            pass

        try:
            from qfluentwidgets import InfoBar as _InfoBar, InfoBarPosition as _IBPos

            # Critical/auto-fixable errors stay until manually closed
            duration = -1 if auto_fix_action else 10000

            bar = _InfoBar.error(
                title="Ошибка",
                content=text,
                orient=Qt.Orientation.Vertical if len(text) > 90 else Qt.Orientation.Horizontal,
                isClosable=True,
                position=_IBPos.TOP,
                duration=duration,
                parent=self,
            )

            if auto_fix_action and bar is not None:
                self._add_autofix_button(bar, auto_fix_action)
        except Exception as e:
            log(f"Ошибка показа InfoBar запуска DPI: {e}", "DEBUG")

    def _add_autofix_button(self, bar, action: str) -> None:
        """Add a 'Fix' button to an InfoBar that runs the auto-fix action."""
        try:
            from qfluentwidgets import PushButton, InfoBar as _InfoBar, InfoBarPosition as _IBPos

            btn = PushButton("Исправить")
            btn.setFixedWidth(100)

            def on_fix():
                btn.setEnabled(False)
                btn.setText("...")
                try:
                    from dpi.process_health_check import execute_windivert_auto_fix
                    ok, msg = execute_windivert_auto_fix(action)
                    bar.close()
                    if ok:
                        _InfoBar.success(
                            title="Готово",
                            content=msg,
                            isClosable=True,
                            position=_IBPos.TOP,
                            duration=5000,
                            parent=self,
                        )
                    else:
                        _InfoBar.warning(
                            title="Не удалось",
                            content=msg,
                            isClosable=True,
                            position=_IBPos.TOP,
                            duration=8000,
                            parent=self,
                        )
                except Exception as e:
                    log(f"Auto-fix error: {e}", "ERROR")
                    btn.setEnabled(True)
                    btn.setText("Исправить")

            btn.clicked.connect(on_fix)
            bar.addWidget(btn)
        except Exception as e:
            log(f"Error adding auto-fix button: {e}", "DEBUG")

    def update_ui(self, running: bool) -> None:
        """Обновляет состояние кнопок в зависимости от статуса запуска"""
        if hasattr(self, 'ui_manager'):
            self.ui_manager.update_ui_state(running)

    def delayed_dpi_start(self) -> None:
        """Выполняет отложенный запуск DPI с проверкой наличия автозапуска"""
        if hasattr(self, 'dpi_manager'):
            self.dpi_manager.delayed_dpi_start()

    def update_autostart_ui(self, service_running: bool) -> None:
        """Обновляет интерфейс при включении/выключении автозапуска"""
        if hasattr(self, 'ui_manager'):
            self.ui_manager.update_autostart_ui(service_running)

    def on_strategy_selected_from_dialog(self, strategy_id: str, strategy_name: str) -> None:
        """Обрабатывает выбор стратегии из диалога."""
        try:
            log(f"Выбрана стратегия: {strategy_name} (ID: {strategy_id})", level="INFO")
            
            # Сохраняем ID и имя выбранной стратегии в атрибутах класса
            self.current_strategy_id = strategy_id
            self.current_strategy_name = strategy_name
            
            # ДЛЯ DIRECT РЕЖИМА ИСПОЛЬЗУЕМ ПРОСТОЕ НАЗВАНИЕ
            from strategy_menu import get_strategy_launch_method
            launch_method = get_strategy_launch_method()
            
            if launch_method == "direct_zapret2":
                # direct_zapret2 is preset-based; do not show a phantom single-strategy name.
                try:
                    from core.services import get_direct_flow_coordinator

                    preset_name = get_direct_flow_coordinator().get_selected_preset_name("direct_zapret2")
                    display_name = f"Пресет: {preset_name}"
                except Exception:
                    display_name = "Пресет"
                self.current_strategy_name = display_name
                strategy_name = display_name
                log(f"Установлено имя пресета для direct_zapret2: {display_name}", "DEBUG")
            elif strategy_id == "DIRECT_MODE" or launch_method in ("direct_zapret2_orchestra", "direct_zapret1"):
                if launch_method == "direct_zapret2_orchestra":
                    try:
                        from preset_orchestra_zapret2 import get_active_preset_name
                        preset_name = get_active_preset_name() or "Default"
                        display_name = f"Пресет оркестра: {preset_name}"
                    except Exception:
                        display_name = "Оркестратор Z2"
                elif launch_method == "direct_zapret1":
                    try:
                        from core.services import get_direct_flow_coordinator

                        preset_name = get_direct_flow_coordinator().get_selected_preset_name("direct_zapret1")
                        display_name = f"Пресет: {preset_name}"
                    except Exception:
                        display_name = "Пресет"
                else:
                    display_name = "Пресет"
                self.current_strategy_name = display_name
                strategy_name = display_name
                log(f"Установлено простое название для режима {launch_method}: {display_name}", "DEBUG")

            # Обновляем новые страницы интерфейса
            if hasattr(self, 'update_current_strategy_display'):
                self.update_current_strategy_display(strategy_name)

            # ✅ ИСПРАВЛЕННАЯ ЛОГИКА для обработки Direct режимов
            if launch_method in ("direct_zapret2", "direct_zapret2_orchestra", "direct_zapret1"):
                if strategy_id == "DIRECT_MODE" or strategy_id == "combined":
                    
                    # ✅ ДЛЯ direct_zapret2 - используем runtime config выбранного пресета
                    if launch_method == "direct_zapret2":
                        try:
                            from core.services import get_direct_flow_coordinator

                            coordinator = get_direct_flow_coordinator()
                            profile = coordinator.ensure_launch_profile("direct_zapret2", require_filters=True)
                            combined_data = profile.to_selected_mode()
                        except Exception as e:
                            log(f"Не удалось подготовить запуск direct_zapret2: {e}", "ERROR")
                            self.set_status(str(e))
                            return

                        log(f"Запуск direct_zapret2 из generated launch config: {profile.launch_config_path}", "INFO")
                        self.dpi_controller.start_dpi_async(selected_mode=combined_data, launch_method=launch_method)
                    
                    # ✅ ДЛЯ direct_zapret1 - используем runtime config выбранного пресета
                    elif launch_method == "direct_zapret1":
                        try:
                            from core.services import get_direct_flow_coordinator

                            coordinator = get_direct_flow_coordinator()
                            profile = coordinator.ensure_launch_profile("direct_zapret1", require_filters=True)
                            combined_data = profile.to_selected_mode()
                        except Exception as e:
                            log(f"Не удалось подготовить запуск direct_zapret1: {e}", "ERROR")
                            self.set_status(str(e))
                            return

                        log(f"Запуск Zapret1 из generated launch config: {profile.launch_config_path}", "INFO")
                        self.dpi_controller.start_dpi_async(selected_mode=combined_data, launch_method=launch_method)

                    # ✅ ДЛЯ direct_zapret2_orchestra - используем preset-zapret2-orchestra.txt
                    elif launch_method == "direct_zapret2_orchestra":
                        from preset_orchestra_zapret2 import (
                            get_active_preset_path,
                            get_active_preset_name,
                            ensure_default_preset_exists,
                        )

                        if not ensure_default_preset_exists():
                            log(
                                "Не удалось создать preset-zapret2-orchestra.txt: отсутствует шаблон Default",
                                "ERROR",
                            )
                            self.set_status("Ошибка: отсутствует шаблон Default для оркестра")
                            return

                        preset_path = get_active_preset_path()
                        preset_name = get_active_preset_name() or "Default"

                        if not preset_path.exists():
                            log(f"preset-zapret2-orchestra.txt не найден: {preset_path}", "ERROR")
                            self.set_status("Выберите стратегию в разделе Оркестратор Z2")
                            return

                        try:
                            content = preset_path.read_text(encoding='utf-8').strip()
                            has_filters = any(f in content for f in ['--wf-tcp-out', '--wf-udp-out', '--wf-raw-part'])
                            if not has_filters:
                                log("Orchestra preset файл не содержит активных фильтров", "WARNING")
                                self.set_status("Выберите хотя бы одну категорию для запуска")
                                return
                        except Exception as e:
                            log(f"Ошибка чтения orchestra preset файла: {e}", "ERROR")
                            self.set_status(f"Ошибка чтения preset: {e}")
                            return

                        combined_data = {
                            'is_preset_file': True,
                            'name': f"Пресет оркестра: {preset_name}",
                            'preset_path': str(preset_path)
                        }

                        log(f"Запуск direct_zapret2_orchestra из preset файла: {preset_path}", "INFO")
                        self.dpi_controller.start_dpi_async(selected_mode=combined_data, launch_method=launch_method)

                    # ✅ ДЛЯ ДРУГИХ РЕЖИМОВ - используем combine_strategies
                    else:
                        from launcher_common import combine_strategies
                        from strategy_menu import get_direct_strategy_selections, get_default_selections

                        try:
                            category_selections = get_direct_strategy_selections()
                        except:
                            category_selections = get_default_selections()

                        combined_strategy = combine_strategies(**category_selections)
                        combined_args = combined_strategy['args']

                        combined_data = {
                            'id': strategy_id,
                            'name': strategy_name,
                            'is_combined': True,
                            'args': combined_args,
                            'selections': category_selections
                        }

                        log(f"Комбинированная стратегия: {len(combined_args)} символов", "DEBUG")

                        self.dpi_controller.start_dpi_async(selected_mode=combined_data, launch_method=launch_method)
                        
                else:
                    self.dpi_controller.start_dpi_async(selected_mode=(strategy_id, strategy_name), launch_method=launch_method)
            else:
                # BAT режим
                try:
                    strategies = self.strategy_manager.get_strategies_list()
                    strategy_info = strategies.get(strategy_id, {})
                    
                    if not strategy_info:
                        strategy_info = {
                            'name': strategy_name,
                            'file_path': f"{strategy_id}.bat"
                        }
                        log(f"Не удалось найти информацию о стратегии {strategy_id}, используем базовую", "⚠ WARNING")
                    
                    self.dpi_controller.start_dpi_async(selected_mode=strategy_info, launch_method=launch_method)
                    
                except Exception as strategy_error:
                    log(f"Ошибка при получении информации о стратегии: {strategy_error}", "❌ ERROR")
                    self.dpi_controller.start_dpi_async(selected_mode=strategy_name, launch_method=launch_method)
                
        except Exception as e:
            log(f"Ошибка при установке выбранной стратегии: {str(e)}", level="❌ ERROR")
            import traceback
            log(f"Traceback: {traceback.format_exc()}", "DEBUG")
            self.set_status(f"Ошибка при установке стратегии: {str(e)}")

    def __init__(self, start_in_tray=False):
        # ZapretFluentWindow.__init__ handles: titlebar, icon, dark theme, min size
        super().__init__()

        from strategy_menu import get_strategy_launch_method
        current_method = get_strategy_launch_method()
        log(f"Метод запуска стратегий: {current_method}", "INFO")

        self.start_in_tray = start_in_tray
        self._register_global_error_notifier()

        # Flags
        self._dpi_autostart_initiated = False
        self._is_exiting = False
        self._stop_dpi_on_exit = False
        self._closing_completely = False
        self._deferred_init_started = False
        self._startup_splash = None
        self._startup_splash_shown_at = None
        self._startup_splash_finish_pending = False
        self._startup_splash_min_visible_ms = 2200
        self._startup_post_init_ready = False
        self._startup_subscription_ready = False

        # Window geometry persistence (debounce)
        self._geometry_restore_in_progress = False
        self._geometry_persistence_enabled = False
        self._pending_restore_maximized = False
        self._applied_saved_maximize_state = False
        self._last_normal_geometry = None
        self._last_persisted_geometry = None
        self._last_persisted_maximized = None
        self._pending_window_maximized_state = None

        self._window_fsm_active = False
        self._window_fsm_target_mode = None
        self._window_fsm_retry_count = 0
        self._last_non_minimized_zoomed = False
        self._window_zoom_visual_state = None

        self._geometry_save_timer = QTimer(self)
        self._geometry_save_timer.setSingleShot(True)
        self._geometry_save_timer.setInterval(450)
        self._geometry_save_timer.timeout.connect(self._persist_window_geometry_now)

        self._window_state_settle_timer = QTimer(self)
        self._window_state_settle_timer.setSingleShot(True)
        self._window_state_settle_timer.setInterval(180)
        self._window_state_settle_timer.timeout.connect(self._on_window_state_settle_timeout)

        self._window_maximized_persist_timer = QTimer(self)
        self._window_maximized_persist_timer.setSingleShot(True)
        self._window_maximized_persist_timer.setInterval(140)
        self._window_maximized_persist_timer.timeout.connect(self._persist_window_maximized_state_now)

        # FluentWindow handles: frameless, titlebar, acrylic, resize, drag
        # We only need to set title and restore geometry
        self.setWindowTitle(f"Zapret2 v{APP_VERSION}")
        self.setMinimumSize(MIN_WIDTH, 400)
        self.restore_window_geometry()

        self.current_strategy_id = None
        self.current_strategy_name = None
        self._holiday_effects = HolidayEffectsManager(self)
        self._startup_ttff_logged = False
        self._startup_ttff_ms = None
        self._startup_interactive_logged = False
        self._startup_interactive_ms = None
        self._startup_managers_ready_logged = False
        self._startup_managers_ready_ms = None
        self._startup_post_init_done_logged = False
        self._startup_post_init_done_ms = None

        # Show window right away (FluentWindow handles rendering)
        if not self.start_in_tray and not self.isVisible():
            self._show_startup_splash()
            self.show()
            log("Основное окно показано (FluentWindow, init в фоне)", "DEBUG")

        deferred_init_delay_ms = 0 if self.start_in_tray else 60
        QTimer.singleShot(deferred_init_delay_ms, self._deferred_init)

    def _show_startup_splash(self) -> None:
        if self.start_in_tray or getattr(self, "_startup_splash", None) is not None:
            return
        try:
            from PyQt6.QtCore import QSize
            from qfluentwidgets import SplashScreen

            try:
                from qframelesswindow import StandardTitleBar
            except Exception:
                StandardTitleBar = None

            class _StartupSplashScreen(SplashScreen):
                def __init__(self, icon, parent=None):
                    super().__init__(icon, parent)
                    self._pulse_timer = QTimer(self)
                    self._pulse_timer.setInterval(40)  # ~25 FPS
                    self._pulse_timer.timeout.connect(self._pulse_tick)
                    self._pulse_phase = 0.0
                    self._base_icon_size = QSize(self.iconSize())

                def start_pulse(self) -> None:
                    self._base_icon_size = QSize(self.iconSize())
                    self._pulse_phase = 0.0
                    self._pulse_timer.start()

                def stop_pulse(self) -> None:
                    try:
                        self._pulse_timer.stop()
                    except Exception:
                        pass
                    try:
                        self.setIconSize(self._base_icon_size)
                        self._center_icon_widget()
                    except Exception:
                        pass

                def _center_icon_widget(self) -> None:
                    try:
                        iw = int(self.iconSize().width())
                        ih = int(self.iconSize().height())
                        self.iconWidget.move(self.width() // 2 - iw // 2, self.height() // 2 - ih // 2)
                    except Exception:
                        pass

                def _pulse_tick(self) -> None:
                    try:
                        import math

                        self._pulse_phase += 0.22
                        if self._pulse_phase >= 6.283185307179586:
                            self._pulse_phase -= 6.283185307179586

                        t = (math.sin(self._pulse_phase) + 1.0) * 0.5
                        scale = 0.94 + (0.12 * t)  # 0.94..1.06
                        w = max(64, int(self._base_icon_size.width() * scale))
                        h = max(64, int(self._base_icon_size.height() * scale))

                        cur = self.iconSize()
                        if int(cur.width()) == w and int(cur.height()) == h:
                            return

                        self.setIconSize(QSize(w, h))
                        self._center_icon_widget()
                    except Exception:
                        pass

                def resizeEvent(self, e):
                    super().resizeEvent(e)
                    self._center_icon_widget()

            splash = _StartupSplashScreen(self.windowIcon(), self)
            splash.setGeometry(self.rect())

            splash.setIconSize(QSize(104, 104))
            splash.start_pulse()

            # Stock title bar from qframelesswindow (as in qfluent docs).
            if StandardTitleBar is not None:
                title_bar = StandardTitleBar(splash)
                title_bar.setIcon(self.windowIcon())
                title_bar.setTitle(self.windowTitle())
                splash.setTitleBar(title_bar)

            splash.raise_()
            splash.show()
            self._startup_splash = splash
            self._startup_splash_shown_at = _startup_clock.perf_counter()
            self._startup_splash_finish_pending = False

            # Safety: never keep splash forever if post-init callback is skipped.
            QTimer.singleShot(20000, self._finish_startup_splash)
        except Exception as e:
            log(f"Startup splash create failed: {e}", "DEBUG")

    def _request_finish_startup_splash(self, *, force: bool = False, reason: str = "") -> None:
        if getattr(self, "_startup_splash", None) is None:
            return

        if force:
            self._finish_startup_splash()
            return

        shown_at = getattr(self, "_startup_splash_shown_at", None)
        if shown_at is None:
            self._finish_startup_splash()
            return

        elapsed_ms = int((_startup_clock.perf_counter() - shown_at) * 1000)
        delay_ms = max(0, int(self._startup_splash_min_visible_ms) - elapsed_ms)
        if delay_ms <= 0:
            self._finish_startup_splash()
            return

        if self._startup_splash_finish_pending:
            return

        self._startup_splash_finish_pending = True
        log(f"Startup splash finish scheduled in {delay_ms}ms ({reason or 'no-reason'})", "DEBUG")
        QTimer.singleShot(delay_ms, self._finish_startup_splash)

    def _try_finish_startup_splash(self, reason: str = "") -> None:
        if getattr(self, "_startup_splash", None) is None:
            return

        if not self._startup_post_init_ready:
            return
        if not self._startup_subscription_ready:
            return

        self._request_finish_startup_splash(reason=reason or "all-startup-phases-ready")

    def _mark_startup_subscription_ready(self, source: str = "subscription_ready") -> None:
        self._startup_subscription_ready = True
        self._try_finish_startup_splash(source)

    def _finish_startup_splash(self) -> None:
        self._startup_splash_finish_pending = False
        splash = getattr(self, "_startup_splash", None)
        if splash is None:
            return
        self._startup_splash = None
        self._startup_splash_shown_at = None

        try:
            stop_pulse = getattr(splash, "stop_pulse", None)
            if callable(stop_pulse):
                stop_pulse()
        except Exception:
            pass

        try:
            splash.finish()
        except Exception:
            try:
                splash.close()
            except Exception:
                pass

    def _deferred_init(self) -> None:
        """Heavy initialization — runs after first frame is shown."""
        if self._deferred_init_started:
            return
        self._deferred_init_started = True

        import time as _time
        _t_total = _time.perf_counter()
        log("⏱ Startup: deferred init started", "DEBUG")

        # Build UI: create pages & register with FluentWindow navigation
        _t_build = _time.perf_counter()
        try:
            self.build_ui(WIDTH, HEIGHT)
        except Exception as e:
            log(f"Startup: build_ui failed: {e}", "ERROR")
            try:
                import traceback
                log(traceback.format_exc(), "DEBUG")
            except Exception:
                pass
            self._request_finish_startup_splash(force=True, reason="build_ui_failed")
            return
        log(f"⏱ Startup: build_ui {(_time.perf_counter() - _t_build) * 1000:.0f}ms", "DEBUG")

        # Create managers
        _t_mgr = _time.perf_counter()
        from managers.initialization_manager import InitializationManager
        from managers.subscription_manager import SubscriptionManager
        from managers.process_monitor_manager import ProcessMonitorManager
        from managers.ui_manager import UIManager

        self.initialization_manager = InitializationManager(self)
        self.subscription_manager = SubscriptionManager(self)
        self.process_monitor_manager = ProcessMonitorManager(self)
        self.ui_manager = UIManager(self)
        log(f"⏱ Startup: managers init {( _time.perf_counter() - _t_mgr ) * 1000:.0f}ms", "DEBUG")

        # Инициализируем donate checker
        self._init_real_donate_checker()  # Упрощенная версия
        self.update_title_with_subscription_status(False, None, 0, source="init")

        # Запускаем асинхронную инициализацию через менеджер
        QTimer.singleShot(50, self.initialization_manager.run_async_init)
        QTimer.singleShot(1000, self.subscription_manager.initialize_async)
        # Гирлянда инициализируется автоматически в subscription_manager после проверки подписки
        log(f"⏱ Startup: deferred init total {( _time.perf_counter() - _t_total ) * 1000:.0f}ms", "DEBUG")

    def _mark_startup_interactive(self, source: str = "ui_signals_connected") -> None:
        if self._startup_interactive_logged:
            return

        self._startup_interactive_logged = True
        interactive_ms = _startup_elapsed_ms()
        self._startup_interactive_ms = interactive_ms

        ttff_ms = self._startup_ttff_ms
        if isinstance(ttff_ms, int):
            delta_ms = max(0, interactive_ms - ttff_ms)
            _log_startup_metric("Interactive", f"{source}, +{delta_ms}ms after TTFF")
        else:
            _log_startup_metric("Interactive", source)

    def _mark_startup_managers_ready(self, source: str = "managers_init_done") -> None:
        if self._startup_managers_ready_logged:
            return

        self._startup_managers_ready_logged = True
        managers_ready_ms = _startup_elapsed_ms()
        self._startup_managers_ready_ms = managers_ready_ms

        details = source
        interactive_ms = self._startup_interactive_ms
        if isinstance(interactive_ms, int):
            delta_ms = max(0, managers_ready_ms - interactive_ms)
            details = f"{source}, +{delta_ms}ms after Interactive"
        elif isinstance(self._startup_ttff_ms, int):
            delta_ms = max(0, managers_ready_ms - self._startup_ttff_ms)
            details = f"{source}, +{delta_ms}ms after TTFF"

        _log_startup_metric("ManagersReady", details)

    def _mark_startup_post_init_done(self, source: str = "post_init_tasks") -> None:
        if self._startup_post_init_done_logged:
            return

        self._startup_post_init_done_logged = True
        post_init_ms = _startup_elapsed_ms()
        self._startup_post_init_done_ms = post_init_ms

        details = source
        managers_ready_ms = self._startup_managers_ready_ms
        if isinstance(managers_ready_ms, int):
            delta_ms = max(0, post_init_ms - managers_ready_ms)
            details = f"{source}, +{delta_ms}ms after ManagersReady"
        elif isinstance(self._startup_interactive_ms, int):
            delta_ms = max(0, post_init_ms - self._startup_interactive_ms)
            details = f"{source}, +{delta_ms}ms after Interactive"

        _log_startup_metric("PostInitDone", details)
        self._startup_post_init_ready = True
        self._try_finish_startup_splash("post_init_done")

    def setWindowTitle(self, title: str):
        """Override to update FluentWindow's built-in titlebar."""
        super().setWindowTitle(title)

    def _enable_geometry_persistence(self) -> None:
        if getattr(self, "_geometry_persistence_enabled", False):
            return
        self._geometry_persistence_enabled = True

    def _is_window_zoomed(self) -> bool:
        """Возвращает True, если окно в maximized/fullscreen состоянии."""
        state = None
        try:
            state = self.windowState()
        except Exception:
            state = None

        try:
            if self.isMaximized() or self.isFullScreen():
                return True
        except Exception:
            pass

        if state is not None:
            try:
                if state & Qt.WindowState.WindowMaximized:
                    return True
                if state & Qt.WindowState.WindowFullScreen:
                    return True
            except Exception:
                pass

        if state is None:
            return bool(getattr(self, "_was_maximized", False))

        return False

    def _apply_window_zoom_visual_state(self, is_zoomed: bool) -> None:
        """Применяет визуальное состояние окна для maximized/fullscreen."""
        zoomed = bool(is_zoomed)
        if self._window_zoom_visual_state is zoomed:
            return

        self._window_zoom_visual_state = zoomed

        if hasattr(self, "_was_maximized"):
            self._was_maximized = zoomed

        if hasattr(self, "_update_border_radius"):
            self._update_border_radius(not zoomed)

        if hasattr(self, "_set_handles_visible"):
            self._set_handles_visible(not zoomed)

        # FluentWindow handles maximize button state automatically

    def _schedule_window_maximized_persist(self, is_zoomed: bool) -> None:
        """Debounce сохранения maximize-флага, чтобы убрать дребезг True/False/True."""
        self._pending_window_maximized_state = bool(is_zoomed)
        try:
            if hasattr(self, "_window_maximized_persist_timer") and self._window_maximized_persist_timer is not None:
                self._window_maximized_persist_timer.start()
            else:
                self._persist_window_maximized_state_now()
        except Exception:
            pass

    def _persist_window_maximized_state_now(self) -> None:
        state = self._pending_window_maximized_state
        if state is None:
            return

        self._pending_window_maximized_state = None

        try:
            from config import set_window_maximized
            state_bool = bool(state)
            if self._last_persisted_maximized != state_bool:
                set_window_maximized(state_bool)
                self._last_persisted_maximized = state_bool
        except Exception:
            pass

    def _detect_window_mode(self) -> str:
        """Возвращает актуальный режим окна: normal/maximized/minimized."""
        if self._is_window_minimized_state():
            return "minimized"
        if self._is_window_zoomed():
            return "maximized"
        return "normal"

    def _apply_window_mode_command(self, mode: str) -> bool:
        """Низкоуровнево применяет режим окна."""
        mode_str = str(mode)

        try:
            if mode_str == "maximized":
                self.showMaximized()
            elif mode_str == "normal":
                self.showNormal()
            elif mode_str == "minimized":
                self.showMinimized()
            else:
                return False
            return True
        except Exception:
            pass

        try:
            state = self.windowState()
        except Exception:
            state = Qt.WindowState.WindowNoState

        try:
            if mode_str == "maximized":
                state = state & ~Qt.WindowState.WindowMinimized
                state = state & ~Qt.WindowState.WindowFullScreen
                state = state | Qt.WindowState.WindowMaximized
            elif mode_str == "normal":
                state = state & ~Qt.WindowState.WindowMinimized
                state = state & ~Qt.WindowState.WindowMaximized
                state = state & ~Qt.WindowState.WindowFullScreen
            elif mode_str == "minimized":
                state = state & ~Qt.WindowState.WindowFullScreen
                state = state | Qt.WindowState.WindowMinimized
            else:
                return False

            self.setWindowState(state)
            return True
        except Exception:
            return False

    def _start_window_fsm_transition(self, target_mode: str) -> None:
        self._window_fsm_active = True
        self._window_fsm_target_mode = str(target_mode)
        self._window_fsm_retry_count = 0

        if self._window_fsm_target_mode != "minimized":
            self._apply_window_zoom_visual_state(self._window_fsm_target_mode == "maximized")

        self._apply_window_mode_command(self._window_fsm_target_mode)

        try:
            if hasattr(self, "_window_state_settle_timer") and self._window_state_settle_timer is not None:
                self._window_state_settle_timer.start()
        except Exception:
            pass

    def _finish_window_fsm_transition(self, actual_mode=None) -> None:
        mode = str(actual_mode) if actual_mode is not None else str(self._detect_window_mode())

        self._window_fsm_active = False
        self._window_fsm_target_mode = None
        self._window_fsm_retry_count = 0

        try:
            if hasattr(self, "_window_state_settle_timer") and self._window_state_settle_timer is not None:
                self._window_state_settle_timer.stop()
        except Exception:
            pass

        if mode == "minimized":
            return

        zoomed = (mode == "maximized")
        self._last_non_minimized_zoomed = zoomed
        self._apply_window_zoom_visual_state(zoomed)
        self._schedule_window_maximized_persist(zoomed)

    def _on_window_state_settle_timeout(self) -> None:
        """Дожимает целевое состояние, если WM не применил его с первого раза."""
        if not self._window_fsm_active:
            return

        target_mode = self._window_fsm_target_mode
        if target_mode is None:
            return

        actual_mode = self._detect_window_mode()
        if actual_mode == target_mode:
            self._finish_window_fsm_transition(actual_mode)
            return

        if self._window_fsm_retry_count < 2:
            self._window_fsm_retry_count += 1
            self._apply_window_mode_command(target_mode)
            try:
                if hasattr(self, "_window_state_settle_timer") and self._window_state_settle_timer is not None:
                    self._window_state_settle_timer.start()
            except Exception:
                pass
            return

        self._finish_window_fsm_transition(actual_mode)

    def _request_window_mode(self, target_mode: str) -> str:
        """Единый вход FSM для normal/maximized/minimized."""
        mode = str(target_mode)
        if mode not in ("normal", "maximized", "minimized"):
            return self._detect_window_mode()

        if self._window_fsm_active and self._window_fsm_target_mode == mode:
            return mode

        current_mode = self._detect_window_mode()
        if not self._window_fsm_active and current_mode == mode:
            try:
                if not self.isVisible():
                    self._apply_window_mode_command(mode)
            except Exception:
                pass
            self._finish_window_fsm_transition(current_mode)
            return current_mode

        self._start_window_fsm_transition(mode)
        return mode

    def _request_window_zoom_state(self, maximize: bool) -> bool:
        target_mode = "maximized" if bool(maximize) else "normal"
        resulting_mode = self._request_window_mode(target_mode)
        if resulting_mode == "minimized":
            return bool(self._last_non_minimized_zoomed)
        return bool(resulting_mode == "maximized")

    def request_window_minimize(self) -> bool:
        """Сворачивает окно через общий FSM."""
        resulting_mode = self._request_window_mode("minimized")
        return bool(resulting_mode == "minimized" or self._is_window_minimized_state())

    def restore_window_from_zoom_for_drag(self) -> bool:
        """Выводит окно из maximized/fullscreen перед drag и возвращает факт изменения."""
        current_mode = self._detect_window_mode()
        current_zoomed = (current_mode == "maximized")

        if not current_zoomed:
            if not (self._window_fsm_active and self._window_fsm_target_mode == "maximized"):
                return False

        self._request_window_zoom_state(False)

        # Для drag важно сразу выйти в normal; если WM не успел — дожимаем 1 раз.
        if self._is_window_zoomed():
            if not self._apply_window_mode_command("normal"):
                return False

        actual_mode = self._detect_window_mode()
        if actual_mode != "maximized":
            self._finish_window_fsm_transition(actual_mode)

        return bool(actual_mode != "maximized")

    def toggle_window_maximize_restore(self) -> bool:
        """Переключает окно между maximized/fullscreen и normal. Возвращает целевое zoomed-состояние."""
        if self._window_fsm_active and self._window_fsm_target_mode in ("normal", "maximized"):
            current_zoomed = bool(self._window_fsm_target_mode == "maximized")
        else:
            current_mode = self._detect_window_mode()
            if current_mode == "minimized":
                current_zoomed = bool(self._last_non_minimized_zoomed)
            else:
                current_zoomed = bool(current_mode == "maximized")

        should_maximize = not current_zoomed
        return bool(self._request_window_zoom_state(should_maximize))

    def _is_window_minimized_state(self) -> bool:
        try:
            if self.isMinimized():
                return True
        except Exception:
            pass

        try:
            return bool(self.windowState() & Qt.WindowState.WindowMinimized)
        except Exception:
            return False

    def _schedule_window_geometry_save(self) -> None:
        if not getattr(self, "_geometry_persistence_enabled", False):
            return
        if getattr(self, "_geometry_restore_in_progress", False):
            return
        if getattr(self, "_is_exiting", False):
            return

        try:
            if self.isMinimized():
                return
        except Exception:
            return

        try:
            if hasattr(self, "_geometry_save_timer") and self._geometry_save_timer is not None:
                self._geometry_save_timer.start()
        except Exception:
            pass

    def _on_window_geometry_changed(self) -> None:
        if getattr(self, "_geometry_restore_in_progress", False):
            return

        try:
            if self.isMinimized() or self._is_window_zoomed():
                return
        except Exception:
            return

        self._last_normal_geometry = (int(self.x()), int(self.y()), int(self.width()), int(self.height()))
        self._schedule_window_geometry_save()

    def _get_normal_geometry_to_save(self, is_maximized: bool):
        if not is_maximized:
            return (int(self.x()), int(self.y()), int(self.width()), int(self.height()))

        # Если окно maximized — сохраняем "normal" геометрию, чтобы корректно восстановить при следующем запуске.
        try:
            normal_geo = self.normalGeometry()
            w = int(normal_geo.width())
            h = int(normal_geo.height())
            if w > 0 and h > 0:
                return (int(normal_geo.x()), int(normal_geo.y()), w, h)
        except Exception:
            pass

        if self._last_normal_geometry:
            return self._last_normal_geometry

        return None

    def _persist_window_geometry_now(self, force: bool = False) -> None:
        if not force:
            if not getattr(self, "_geometry_persistence_enabled", False):
                return
            if getattr(self, "_geometry_restore_in_progress", False):
                return
            if getattr(self, "_is_exiting", False):
                return

        try:
            if self.isMinimized():
                return
        except Exception:
            pass

        try:
            from config import set_window_position, set_window_size, set_window_maximized

            is_maximized = bool(self._is_window_zoomed())

            if force or self._last_persisted_maximized != is_maximized:
                set_window_maximized(is_maximized)
                self._last_persisted_maximized = is_maximized
                self._pending_window_maximized_state = is_maximized
                try:
                    if hasattr(self, "_window_maximized_persist_timer") and self._window_maximized_persist_timer is not None:
                        self._window_maximized_persist_timer.stop()
                except Exception:
                    pass

            geometry = self._get_normal_geometry_to_save(is_maximized)
            if geometry is None:
                return

            x, y, w, h = geometry
            w = max(int(w), MIN_WIDTH)
            h = max(int(h), 400)
            geometry = (int(x), int(y), int(w), int(h))

            if force or self._last_persisted_geometry != geometry:
                set_window_position(geometry[0], geometry[1])
                set_window_size(geometry[2], geometry[3])
                self._last_persisted_geometry = geometry

        except Exception as e:
            log(f"Ошибка сохранения геометрии окна: {e}", "DEBUG")

    def _apply_saved_maximized_state_if_needed(self) -> None:
        if getattr(self, "_applied_saved_maximize_state", False):
            return

        self._applied_saved_maximize_state = True

        if getattr(self, "_pending_restore_maximized", False):
            try:
                if not self._is_window_zoomed():
                    self._geometry_restore_in_progress = True
                    self._request_window_zoom_state(True)
            except Exception:
                pass
            finally:
                self._geometry_restore_in_progress = False

    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange:
            try:
                if not self.isActiveWindow():
                    self._release_input_interaction_states()
            except Exception:
                pass

        if event.type() == QEvent.Type.WindowStateChange:
            current_mode = self._detect_window_mode()

            if self._window_fsm_active and self._window_fsm_target_mode is not None:
                target_mode = str(self._window_fsm_target_mode)
                if current_mode == target_mode:
                    self._finish_window_fsm_transition(current_mode)
                elif target_mode != "minimized":
                    # Держим визуал в целевом состоянии до завершения transition.
                    self._apply_window_zoom_visual_state(target_mode == "maximized")
            elif current_mode != "minimized":
                zoomed = bool(current_mode == "maximized")
                self._last_non_minimized_zoomed = zoomed
                self._apply_window_zoom_visual_state(zoomed)
                self._schedule_window_maximized_persist(zoomed)

            try:
                effects = getattr(self, "_holiday_effects", None)
                if effects is not None:
                    QTimer.singleShot(0, effects.sync_geometry)
            except Exception:
                pass

        super().changeEvent(event)

    def hideEvent(self, event):
        try:
            self._release_input_interaction_states()
        except Exception:
            pass
        super().hideEvent(event)

    def moveEvent(self, event):
        super().moveEvent(event)
        self._on_window_geometry_changed()
    
    def _force_style_refresh(self) -> None:
        """Принудительно обновляет стили всех виджетов после показа окна
        
        Необходимо потому что CSS применяется к QApplication ДО создания/показа виджетов.
        unpolish/polish заставляет Qt пересчитать стили для каждого виджета.
        """
        try:
            # unpolish/polish принудительно пересчитывает стили виджета
            for widget in self.findChildren(QWidget):
                widget.style().unpolish(widget)
                widget.style().polish(widget)
            
            log("🎨 Принудительное обновление стилей выполнено после показа окна", "DEBUG")
        except Exception as e:
            log(f"Ошибка обновления стилей: {e}", "DEBUG")
    
    def _init_real_donate_checker(self) -> None:
        """Создает базовый DonateChecker (полная инициализация в SubscriptionManager)"""
        try:
            from donater import DonateChecker
            self.donate_checker = DonateChecker()
            log("Базовый DonateChecker создан", "DEBUG")
        except Exception as e:
            log(f"Ошибка создания DonateChecker: {e}", "❌ ERROR")

    def show_subscription_dialog(self) -> None:
        """Переключается на страницу Premium."""
        try:
            self.show_page(PageName.PREMIUM)
        except Exception as e:
            log(f"Ошибка при переходе на страницу Premium: {e}", level="❌ ERROR")
            
    def open_folder(self) -> None:
        """Opens the DPI folder."""
        try:
            run_hidden('explorer.exe .', shell=True)
        except Exception as e:
            self.set_status(f"Ошибка при открытии папки: {str(e)}")

    def open_connection_test(self) -> None:
        """Переключает на вкладку диагностики соединений."""
        try:
            if self.show_page(PageName.BLOCKCHECK):
                try:
                    blockcheck_page = getattr(self, "blockcheck_page", None)
                    if blockcheck_page is not None:
                        switch_tab = getattr(blockcheck_page, "switch_to_tab", None)
                        if callable(switch_tab):
                            switch_tab("diagnostics")

                        self.connection_page = getattr(blockcheck_page, "connection_page", getattr(self, "connection_page", None))
                        self.dns_check_page = getattr(blockcheck_page, "dns_check_page", getattr(self, "dns_check_page", None))
                except Exception:
                    pass

                try:
                    if getattr(self, "connection_page", None) is not None:
                        self.connection_page.start_btn.setFocus()
                except Exception:
                    pass
                log("Открыта вкладка диагностики в BlockCheck", "INFO")
        except Exception as e:
            log(f"Ошибка при открытии вкладки тестирования: {e}", "❌ ERROR")
            self.set_status(f"Ошибка: {e}")

    def set_garland_enabled(self, enabled: bool) -> None:
        """Enable/disable top garland overlay in FluentWindow shell."""
        try:
            effects = getattr(self, "_holiday_effects", None)
            if effects is None:
                effects = HolidayEffectsManager(self)
                self._holiday_effects = effects
            effects.set_garland_enabled(bool(enabled))
        except Exception as e:
            log(f"❌ Ошибка переключения гирлянды: {e}", "ERROR")

    def set_snowflakes_enabled(self, enabled: bool) -> None:
        """Enable/disable snow overlay in FluentWindow shell."""
        try:
            effects = getattr(self, "_holiday_effects", None)
            if effects is None:
                effects = HolidayEffectsManager(self)
                self._holiday_effects = effects
            effects.set_snowflakes_enabled(bool(enabled))
        except Exception as e:
            log(f"❌ Ошибка переключения снежинок: {e}", "ERROR")

    def set_window_opacity(self, value: int) -> None:
        """Устанавливает прозрачность фона окна (0–100%).

        Win11: обновляет тинт-оверлей поверх Mica (apply_aero_effect fast path).
        Win10: применяет setWindowOpacity через apply_aero_effect.
        """
        try:
            # Эффект применяется только для standard пресета
            from config.reg import get_background_preset
            if get_background_preset() != "standard":
                log(f"Transparent effect проигнорирован (не standard пресет)", "DEBUG")
                return

            from ui.theme import apply_aero_effect
            apply_aero_effect(self, value)
            log(f"Прозрачность обновлена: {value}%", "DEBUG")
        except Exception as e:
            log(f"❌ Ошибка при установке прозрачности окна: {e}", "ERROR")

    def resizeEvent(self, event):
        """Обновляем геометрию при изменении размера окна"""
        super().resizeEvent(event)
        try:
            self._update_titlebar_search_width()
        except Exception:
            pass
        self._on_window_geometry_changed()
        try:
            effects = getattr(self, "_holiday_effects", None)
            if effects is not None:
                effects.sync_geometry()
        except Exception:
            pass
    
    def showEvent(self, event):
        """Первый показ окна"""
        super().showEvent(event)

        if not self._startup_ttff_logged:
            self._startup_ttff_logged = True
            self._startup_ttff_ms = _startup_elapsed_ms()
            _log_startup_metric("TTFF", "first showEvent")

        # Применяем сохранённое maximized состояние при первом показе
        self._apply_saved_maximized_state_if_needed()

        # Включаем автосохранение геометрии (после первого show + небольшой паузы)
        QTimer.singleShot(350, self._enable_geometry_persistence)

        try:
            effects = getattr(self, "_holiday_effects", None)
            if effects is not None:
                effects.sync_geometry()
                QTimer.singleShot(0, effects.sync_geometry)
        except Exception:
            pass

    def _init_garland_from_registry(self) -> None:
        """Загружает состояние гирлянды и снежинок из реестра при старте"""
        try:
            from config.reg import get_garland_enabled, get_snowflakes_enabled
            
            garland_saved = get_garland_enabled()
            snowflakes_saved = get_snowflakes_enabled()
            log(f"🎄 Инициализация: гирлянда={garland_saved}, снежинки={snowflakes_saved}", "DEBUG")
            
            # Проверяем премиум статус
            is_premium = False
            if hasattr(self, 'donate_checker') and self.donate_checker:
                try:
                    is_premium, _, _ = self.donate_checker.check_subscription_status(use_cache=True)
                    log(f"🎄 Премиум статус: {is_premium}", "DEBUG")
                except Exception as e:
                    log(f"🎄 Ошибка проверки премиума: {e}", "DEBUG")
            
            # Гирлянда
            should_enable_garland = is_premium and garland_saved
            if should_enable_garland:
                self.set_garland_enabled(True)
            if hasattr(self, 'appearance_page'):
                self.appearance_page.set_garland_state(should_enable_garland)
            
            # Снежинки
            should_enable_snowflakes = is_premium and snowflakes_saved
            if should_enable_snowflakes:
                self.set_snowflakes_enabled(True)
            if hasattr(self, 'appearance_page'):
                self.appearance_page.set_snowflakes_state(should_enable_snowflakes)

            # Прозрачность окна (не зависит от премиума)
            from config.reg import get_window_opacity
            opacity_saved = get_window_opacity()
            log(f"🔮 Инициализация: opacity={opacity_saved}%", "DEBUG")
            self.set_window_opacity(opacity_saved)
            if hasattr(self, 'appearance_page'):
                self.appearance_page.set_opacity_value(opacity_saved)

            # Анимации интерфейса
            from config.reg import get_animations_enabled
            if not get_animations_enabled() and hasattr(self, '_on_animations_changed'):
                self._on_animations_changed(False)

        except Exception as e:
            log(f"❌ Ошибка загрузки состояния декораций: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")


def set_batfile_association() -> bool:
    """
    Устанавливает ассоциацию типа файла для .bat файлов
    """
    try:
        # Используем максимально скрытый режим
        command = r'ftype batfile="%SystemRoot%\System32\cmd.exe" /c "%1" %*'

        result = subprocess.run(command, shell=True, check=True, 
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode == 0:
            log("Ассоциация успешно установлена", level="INFO")
            return True
        else:
            log(f"Ошибка при выполнении команды: {result.stderr}", level="❌ ERROR")
            return False
            
    except Exception as e:
        log(f"Произошла ошибка: {e}", level="❌ ERROR")
        return False

def main():
    import sys, ctypes, os, atexit
    log("=== ЗАПУСК ПРИЛОЖЕНИЯ ===", "🔹 main")
    log(APP_VERSION, "🔹 main")

    # ---------------- Быстрая обработка специальных аргументов ----------------
    if "--version" in sys.argv:
        ctypes.windll.user32.MessageBoxW(None, APP_VERSION, "Zapret – версия", 0x40)
        sys.exit(0)

    if "--update" in sys.argv and len(sys.argv) > 3:
        _handle_update_mode()
        sys.exit(0)
    
    start_in_tray = "--tray" in sys.argv
    
    # ---------------- Проверка прав администратора ----------------
    if not is_admin():
        params = subprocess.list2cmdline(list(sys.argv[1:]))

        shell_exec_result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            params,
            None,
            1,
        )
        if int(shell_exec_result) <= 32:
            ctypes.windll.user32.MessageBoxW(
                None,
                "Не удалось запросить права администратора.",
                "Zapret",
                0x10,
            )
        sys.exit(0)
    
    # ---------------- Проверка single instance ----------------
    from startup.single_instance import create_mutex, release_mutex
    from startup.ipc_manager import IPCManager
    
    mutex_handle, already_running = create_mutex("ZapretSingleInstance")
    if already_running:
        ipc = IPCManager()
        if ipc.send_show_command():
            log("Отправлена команда показать окно запущенному экземпляру", "INFO")
        else:
            ctypes.windll.user32.MessageBoxW(None, 
                "Экземпляр Zapret уже запущен, но не удалось показать окно!", "Zapret", 0x40)
        sys.exit(0)
    
    atexit.register(lambda: release_mutex(mutex_handle))

    # ---------------- QApplication (уже создан на уровне модуля) ----------------
    app = QApplication.instance()
    try:
        # На Windows принудительно отключаем "transient/overlay" скроллбары
        # (иначе они могут не отображаться/быть практически невидимыми).
        try:
            import platform
            if platform.system() == "Windows":
                from PyQt6.QtWidgets import QProxyStyle, QStyle

                class _NoTransientScrollbarsStyle(QProxyStyle):
                    def styleHint(self, hint, option=None, widget=None, returnData=None):
                        if hint == QStyle.StyleHint.SH_ScrollBar_Transient:
                            return 0
                        return super().styleHint(hint, option, widget, returnData)

                app.setStyle(_NoTransientScrollbarsStyle(app.style()))
        except Exception:
            pass

        app.setQuitOnLastWindowClosed(False)

        # Устанавливаем Qt crash handler
        from log.crash_handler import install_qt_crash_handler
        install_qt_crash_handler(app)

    except Exception as e:
        ctypes.windll.user32.MessageBoxW(None,
            f"Ошибка инициализации Qt: {e}", "Zapret", 0x10)

    # Apply display mode and accent color via native qfluentwidgets API.
    from qfluentwidgets import setTheme, Theme
    from qfluentwidgets.common.config import qconfig
    from PyQt6.QtGui import QColor as _QColor

    try:
        from config.reg import get_display_mode
        _display_mode = get_display_mode()
    except Exception:
        _display_mode = "dark"

    if _display_mode == "light":
        setTheme(Theme.LIGHT)
    elif _display_mode == "system":
        setTheme(Theme.AUTO)
    else:
        setTheme(Theme.DARK)

    # Accent color: Windows system accent takes priority, then saved custom, then default.
    try:
        from config.reg import (get_follow_windows_accent, get_windows_system_accent,
                                 get_accent_color, set_accent_color)
        if get_follow_windows_accent():
            _hex = get_windows_system_accent()
        else:
            _hex = get_accent_color()
        if _hex:
            _c = _QColor(_hex)
            if _c.isValid():
                qconfig.set(qconfig.themeColor, _c)
                if get_follow_windows_accent():
                    set_accent_color(_hex)
    except Exception:
        pass

    # СОЗДАЁМ ОКНО
    window = LupiDPIApp(start_in_tray=start_in_tray)

    # ✅ ПРИМЕНЯЕМ ПРЕСЕТ ФОНА + MICA (amoled / rkn_chan / standard)
    try:
        from config.reg import get_background_preset
        from ui.theme import apply_window_background
        _bg_preset = get_background_preset()
        apply_window_background(window, preset=_bg_preset)
    except Exception:
        pass

    # Re-apply window background when AUTO mode follows OS theme changes.
    try:
        from ui.theme import apply_window_background
        qconfig.themeChanged.connect(lambda _: apply_window_background(window))
    except Exception:
        pass

    # ✅ ПРИМЕНЯЕМ СОХРАНЁННУЮ ПРОЗРАЧНОСТЬ ОКНА
    try:
        from config.reg import get_window_opacity
        _opacity = get_window_opacity()
        if _opacity != 100:
            window.set_window_opacity(_opacity)
    except Exception:
        pass

    # ✅ ЗАПУСКАЕМ IPC СЕРВЕР
    ipc_manager = IPCManager()
    ipc_manager.start_server(window)
    atexit.register(ipc_manager.stop)

    if start_in_tray:
        log("Запуск приложения скрыто в трее", "TRAY")
        if hasattr(window, 'tray_manager'):
            window.tray_manager.show_notification(
                "Zapret работает в трее", 
                "Приложение запущено в фоновом режиме"
            )

    # ✅ НЕКРИТИЧЕСКИЕ ПРОВЕРКИ ПОСЛЕ ПОКАЗА ОКНА
    # Важно: тяжёлые проверки должны выполняться НЕ в GUI-потоке, иначе окно "замирает".
    from PyQt6.QtCore import QObject, pyqtSignal

    class _StartupChecksBridge(QObject):
        finished = pyqtSignal(dict)

    _startup_bridge = _StartupChecksBridge()

    def _native_message_safe(title: str, message: str, flags: int) -> int:
        try:
            from startup.check_start import _native_message
            return int(_native_message(title, message, flags))
        except Exception:
            try:
                return int(ctypes.windll.user32.MessageBoxW(None, str(message), str(title), int(flags)))
            except Exception:
                return 0

    def _on_startup_checks_finished(payload: dict) -> None:
        try:
            fatal_error = payload.get("fatal_error")
            warnings = payload.get("warnings") or []
            ok = bool(payload.get("ok", True))
            kaspersky_detected = bool(payload.get("kaspersky_detected", False))

            if fatal_error:
                try:
                    QMessageBox.critical(window, "Ошибка", str(fatal_error))
                except Exception:
                    _native_message_safe("Ошибка", str(fatal_error), 0x10)
                QApplication.quit()
                return

            if warnings:
                full_message = "\n\n".join([str(w) for w in warnings if w]) + "\n\nПродолжить работу?"
                try:
                    result = QMessageBox.warning(
                        window,
                        "Предупреждение",
                        full_message,
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    ok = (result == QMessageBox.StandardButton.Yes)
                except Exception:
                    btn = _native_message_safe("Предупреждение", full_message, 0x34)  # MB_ICONWARNING | MB_YESNO
                    ok = (btn == 6)  # IDYES

            if kaspersky_detected:
                log("Обнаружен антивирус Kaspersky", "⚠️ KASPERSKY")
                try:
                    from startup.kaspersky import show_kaspersky_warning
                    show_kaspersky_warning(window)
                except Exception as e:
                    log(f"Не удалось показать предупреждение Kaspersky: {e}", "⚠️ KASPERSKY")

            telega_found_path = payload.get("telega_found_path")
            if telega_found_path:
                log(f"Обнаружена Telega Desktop: {telega_found_path}", "🚨 TELEGA")
                try:
                    from startup.telega_check import show_telega_warning
                    show_telega_warning(window, found_path=str(telega_found_path))
                except Exception as e:
                    log(f"Не удалось показать предупреждение Telega: {e}", "🚨 TELEGA")

            if not ok and not start_in_tray:
                log("Некритические проверки не пройдены, продолжаем работу после предупреждения", "⚠ WARNING")

            log("✅ Все проверки пройдены", "🔹 main")
        except Exception as e:
            log(f"Ошибка при обработке результатов проверок: {e}", "❌ ERROR")

    _startup_bridge.finished.connect(_on_startup_checks_finished)

    def _run_after_startup_flag(
        flag_attr: str,
        callback,
        *,
        gate_name: str,
        check_every_ms: int = 250,
        timeout_ms: int = 20000,
    ) -> None:
        """Run callback when a startup flag becomes True (or after timeout)."""
        started_at = time.perf_counter()

        def _try_start() -> None:
            try:
                ready = bool(getattr(window, flag_attr, False))
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)

                if ready or elapsed_ms >= int(timeout_ms):
                    if not ready:
                        log(
                            f"Startup gate timeout: {gate_name} ({flag_attr}) after {elapsed_ms}ms",
                            "DEBUG",
                        )
                    callback()
                    return

                QTimer.singleShot(max(50, int(check_every_ms)), _try_start)
            except Exception:
                callback()

        QTimer.singleShot(0, _try_start)

    def _startup_checks_worker():
        try:
            from startup.bfe_util import preload_service_status, ensure_bfe_running, cleanup as bfe_cleanup
            from startup.check_start import collect_startup_warnings, check_goodbyedpi, check_mitmproxy

            preload_service_status("BFE")

            if not ensure_bfe_running(show_ui=True):
                log("BFE не запущен, продолжаем работу после предупреждения", "⚠ WARNING")

            can_continue, warnings, fatal_error = collect_startup_warnings()
            warnings = list(warnings or [])

            # Нефатальные, но потенциально долгие проверки — только в фоне после показа окна.
            has_gdpi, gdpi_msg = check_goodbyedpi()
            if has_gdpi and gdpi_msg:
                warnings.append(gdpi_msg)

            has_mitmproxy, mitmproxy_msg = check_mitmproxy()
            if has_mitmproxy and mitmproxy_msg:
                warnings.append(mitmproxy_msg)

            kaspersky_detected = False
            try:
                from startup.kaspersky import _check_kaspersky_antivirus
                kaspersky_detected = bool(_check_kaspersky_antivirus(None))
            except Exception:
                kaspersky_detected = False

            telega_found_path = None
            try:
                from startup.telega_check import _check_telega_installed
                telega_found_path = _check_telega_installed()
            except Exception:
                telega_found_path = None

            if is_verbose_logging_enabled():
                from startup.admin_check_debug import debug_admin_status
                debug_admin_status()
            set_batfile_association()

            try:
                atexit.register(bfe_cleanup)
            except Exception:
                pass

            _startup_bridge.finished.emit(
                {
                    "ok": bool(can_continue),
                    "warnings": warnings,
                    "fatal_error": fatal_error,
                    "kaspersky_detected": kaspersky_detected,
                    "telega_found_path": telega_found_path,
                }
            )
        except Exception as e:
            log(f"Ошибка при асинхронных проверках: {e}", "❌ ERROR")
            if hasattr(window, 'set_status'):
                try:
                    window.set_status(f"Ошибка проверок: {e}")
                except Exception:
                    pass
            _startup_bridge.finished.emit({"ok": True, "warnings": [], "fatal_error": None})

    # Запускаем проверки только после interactive-фазы,
    # чтобы не конкурировать с heavy build_ui на старте.
    def _start_startup_checks():
        import threading
        threading.Thread(target=_startup_checks_worker, daemon=True).start()

    _run_after_startup_flag(
        "_startup_interactive_logged",
        _start_startup_checks,
        gate_name="startup_checks",
        check_every_ms=250,
        timeout_ms=20000,
    )

    # ─── Автопроверка обновлений при запуске ───────────────────────────────────

    class _UpdateCheckBridge(QObject):
        update_found = pyqtSignal(str, str)   # version, release_notes
        no_update    = pyqtSignal(str)        # current_version
        check_error  = pyqtSignal(str)        # error_message

    _update_bridge = _UpdateCheckBridge()

    def _on_update_found(version: str, release_notes: str) -> None:
        try:
            from qfluentwidgets import MessageBox as _MsgBox
            box = _MsgBox(
                "Доступно обновление",
                f"Выпущена версия {version}. Скачать и установить сейчас?",
                window,
            )
            box.yesButton.setText("Скачать и установить")
            box.cancelButton.setText("Позже")
            if not box.exec():
                return
            # Переходим на страницу обновлений и запускаем скачивание
            from ui.page_names import PageName as _PageName
            window.show_page(_PageName.SERVERS)
            sp = window.pages.get(_PageName.SERVERS)
            if sp is not None:
                if sp._update_in_progress or sp.changelog_card._is_downloading:
                    log("Обновление уже загружается, пропускаем startup-триггер", "🔄 UPDATE")
                    return
                sp._remote_version = version
                sp._release_notes = release_notes
                sp._found_update = True
                try:
                    sp.changelog_card.show_update(version, release_notes)
                except Exception:
                    pass
                QTimer.singleShot(300, sp._install_update)
        except Exception as e:
            log(f"Ошибка при показе диалога обновления: {e}", "❌ ERROR")

    def _on_no_update(current_version: str) -> None:
        try:
            from qfluentwidgets import InfoBar as _InfoBar, InfoBarPosition as _IBPos
            _InfoBar.success(
                title="Обновлений нет",
                content=f"Установлена актуальная версия {current_version}",
                parent=window,
                duration=4000,
                position=_IBPos.TOP_RIGHT,
            )
        except Exception as e:
            log(f"Ошибка при показе InfoBar: {e}", "❌ ERROR")

    def _on_update_check_error(error: str) -> None:
        log(f"Не удалось проверить обновления при запуске: {error}", "⚠️ UPDATE")

    _update_bridge.update_found.connect(_on_update_found)
    _update_bridge.no_update.connect(_on_no_update)
    _update_bridge.check_error.connect(_on_update_check_error)

    def _startup_update_worker():
        try:
            from updater.startup_update_check import check_for_update_sync
            result = check_for_update_sync()
            if result.get('error'):
                _update_bridge.check_error.emit(result['error'])
            elif result.get('has_update'):
                _update_bridge.update_found.emit(
                    result.get('version') or '',
                    result.get('release_notes') or '',
                )
            else:
                _update_bridge.no_update.emit(result.get('version') or '')
        except Exception as e:
            log(f"Ошибка воркера проверки обновлений: {e}", "❌ ERROR")

    def _schedule_startup_update_check():
        try:
            from config import get_auto_update_enabled
            if not get_auto_update_enabled():
                log("Автопроверка обновлений при запуске отключена", "🔁 UPDATE")
                return
        except Exception:
            pass
        import threading
        threading.Thread(target=_startup_update_worker, daemon=True).start()

    def _schedule_startup_update_check_deferred() -> None:
        delay_ms = 12000
        log(f"Автопроверка обновлений отложена на {delay_ms}ms после готовности UI", "DEBUG")
        QTimer.singleShot(delay_ms, _schedule_startup_update_check)

    _run_after_startup_flag(
        "_startup_post_init_ready",
        _schedule_startup_update_check_deferred,
        gate_name="startup_update_check",
        check_every_ms=350,
        timeout_ms=30000,
    )

    # ─── CPU Diagnostic ────────────────────────────────────────────────────────
    # Logs per-process CPU breakdown to identify the 20% CPU source.
    # Remove after the root cause is confirmed.
    def _cpu_diagnostic_worker():
        import threading as _t
        import traceback as _tb
        import sys as _sys
        import time as _time
        _time.sleep(15)  # wait for full app startup
        try:
            import psutil as _psutil

            this_proc = _psutil.Process()
            # psutil warmup — first call always returns 0
            this_proc.cpu_percent(interval=None)
            _time.sleep(1)

            log("=== CPU DIAGNOSTIC: начало ===", "INFO")
            log(f"Активных тредов Python: {_t.active_count()}", "INFO")

            # — Thread stack dump (one snapshot) — INFO level so it shows in logs
            frames = _sys._current_frames()
            for tid, frame in frames.items():
                th = next((x for x in _t.enumerate() if x.ident == tid), None)
                name = th.name if th else f"tid-{tid}"
                stack = "".join(_tb.format_stack(frame)).strip()
                log(f"[STACK '{name}']\n{stack[-1200:]}", "INFO")

            # — 5 CPU samples, 2 sec each —
            samples_gui = []
            for i in range(5):
                cpu_gui = this_proc.cpu_percent(interval=2.0)
                samples_gui.append(cpu_gui)
                # winws CPU
                winws_parts = []
                for p in _psutil.process_iter(['name', 'cpu_percent']):
                    try:
                        n = (p.info.get('name') or '').lower()
                        if n in ('winws.exe', 'winws2.exe'):
                            winws_parts.append(f"{n}={p.cpu_percent():.1f}%")
                    except Exception:
                        pass
                winws_str = ", ".join(winws_parts) if winws_parts else "не запущен"
                log(f"[CPU {i+1}/5] Python GUI: {cpu_gui:.1f}%  |  winws: {winws_str}", "INFO")

            avg = sum(samples_gui) / len(samples_gui) if samples_gui else 0
            log(f"=== CPU DIAGNOSTIC DONE: avg Python GUI = {avg:.1f}% ===", "INFO")

            # — Sampling profiler: снимаем стеки ВСЕХ тредов 50 раз за 5с —
            if avg > 20:
                try:
                    from collections import Counter as _Counter
                    sample_counts: dict = _Counter()
                    for _ in range(50):
                        _time.sleep(0.1)
                        frames2 = _sys._current_frames()
                        for tid2, frame2 in frames2.items():
                            th2 = next((x for x in _t.enumerate() if x.ident == tid2), None)
                            tname2 = th2.name if th2 else f"tid-{tid2}"
                            # Top 3 frames as key
                            import traceback as _tb2
                            stack2 = _tb2.extract_stack(frame2)
                            key = tname2 + " | " + " → ".join(
                                f"{f.filename.split('/')[-1].split(chr(92))[-1]}:{f.lineno}:{f.name}"
                                for f in stack2[-4:]
                            )
                            sample_counts[key] += 1
                    top = sample_counts.most_common(15)
                    report = "\n".join(f"  {cnt:3d}x  {key}" for key, cnt in top)
                    log(f"[SAMPLING top-15 hotspots (50 samples × 100ms)]\n{report}", "INFO")
                except Exception as _pe:
                    log(f"Sampling error: {_pe}", "WARNING")
        except Exception as _e:
            log(f"CPU diagnostic error: {_e}", "WARNING")

    if _is_cpu_diagnostic_enabled():
        import threading as _diag_t
        _diag_t.Thread(target=_cpu_diagnostic_worker, daemon=True, name="CPUDiagnostic").start()
        del _diag_t

    # Exception handler
    def global_exception_handler(exctype, value, tb_obj):
        import traceback as tb
        try:
            error_msg = ''.join(tb.format_exception(exctype, value, tb_obj))
        except Exception as format_error:
            try:
                base_error = ''.join(tb.format_exception_only(exctype, value)).strip()
            except Exception:
                base_error = f"{getattr(exctype, '__name__', exctype)}: {value!r}"
            error_msg = f"{base_error}\n[traceback formatting failed: {format_error!r}]"
        log(f"UNCAUGHT EXCEPTION: {error_msg}", level="❌ CRITICAL")

    sys.excepthook = global_exception_handler
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
