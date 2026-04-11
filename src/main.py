# main.py
import sys, os
import time as _startup_clock
from ui.page_names import PageName


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

from PyQt6.QtCore    import QTimer, QEvent, Qt, QCoreApplication, pyqtSignal
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
from ui.window_close_controller import WindowCloseController
from ui.holiday_effects import HolidayEffectsManager
from ui.window_geometry_controller import WindowGeometryController
from ui.window_notification_controller import WindowNotificationController
from ui.main_window_state import AppUiState
from app_context import AppContext, build_app_context
from core.services import install_app_context


from startup.admin_check import is_admin

from config import WIDTH, HEIGHT, MIN_WIDTH
from config import APP_VERSION
from utils import run_hidden

from app_notifications import advisory_notification
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

    deferred_init_requested = pyqtSignal()
    continue_startup_requested = pyqtSignal()
    finalize_ui_bootstrap_requested = pyqtSignal()
    startup_interactive_ready = pyqtSignal(str)
    startup_post_init_ready = pyqtSignal(str)
    runner_runtime_state_requested = pyqtSignal(object)
    active_preset_content_changed_requested = pyqtSignal(str)

    from ui.theme import ThemeHandler
    # ✅ ДОБАВЛЯЕМ TYPE HINTS для менеджеров
    ui_manager: 'UIManager'
    dpi_manager: 'DPIManager'
    process_monitor_manager: 'ProcessMonitorManager'
    subscription_manager: 'SubscriptionManager'
    initialization_manager: 'InitializationManager'
    theme_handler: 'ThemeHandler'

    def log_startup_metric(self, marker: str, details: str = "") -> None:
        _log_startup_metric(marker, details)

    @staticmethod
    def _build_initial_ui_state() -> AppUiState:
        """Честное стартовое состояние UI до реальной проверки и автозапуска."""
        try:
            from config import get_dpi_autostart, get_winws_exe_for_method
            from strategy_menu import get_strategy_launch_method

            autostart_enabled = bool(get_dpi_autostart())
            launch_method = str(get_strategy_launch_method() or "").strip().lower()
            expected_process = ""
            if launch_method and launch_method != "orchestra":
                expected_process = os.path.basename(get_winws_exe_for_method(launch_method)).strip().lower()

            autostart_pending_methods = {
                "direct_zapret2",
                "direct_zapret1",
                "direct_zapret2_orchestra",
                "orchestra",
            }

            if autostart_enabled and launch_method in autostart_pending_methods:
                return AppUiState(
                    dpi_phase="autostart_pending",
                    dpi_running=False,
                    dpi_expected_process=expected_process,
                    autostart_enabled=autostart_enabled,
                )

            return AppUiState(
                dpi_phase="stopped",
                dpi_running=False,
                dpi_expected_process=expected_process,
                autostart_enabled=autostart_enabled,
            )
        except Exception:
            return AppUiState()

    def closeEvent(self, event):
        """Обрабатывает событие закрытия окна"""
        close_controller = getattr(self, "window_close_controller", None)
        if close_controller is not None:
            if not close_controller.should_continue_final_close(event):
                return

        self._is_exiting = True

        try:
            if hasattr(global_logger, "set_ui_error_notifier"):
                global_logger.set_ui_error_notifier(None)
        except Exception:
            pass
        
        # ✅ Гарантированно сохраняем геометрию/состояние окна при выходе
        try:
            geometry_controller = getattr(self, "window_geometry_controller", None)
            if geometry_controller is not None:
                geometry_controller.persist_now(force=True)
        except Exception as e:
            log(f"Ошибка сохранения геометрии окна при закрытии: {e}", "❌ ERROR")
        
        self._cleanup_support_managers_for_close()
        self._cleanup_threaded_pages_for_close()

        self._cleanup_visual_and_proxy_resources_for_close()
        self._cleanup_runtime_threads_for_close()

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

        self._cleanup_tray_for_close()

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
            geometry_controller = getattr(self, "window_geometry_controller", None)
            if geometry_controller is not None:
                geometry_controller.persist_now(force=True)
        except Exception as e:
            log(f"Ошибка сохранения геометрии окна при request_exit: {e}", "DEBUG")

        # Скрываем иконку трея (если есть) — пользователь выбрал полный выход.
        try:
            if hasattr(self, "tray_manager") and self.tray_manager:
                self.tray_manager.hide_icon()
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

    def ensure_tray_manager(self):
        """Возвращает tray manager, создавая его только как аварийный fallback."""
        tray_manager = getattr(self, "tray_manager", None)
        if tray_manager is not None:
            return tray_manager

        try:
            initialization_manager = getattr(self, "initialization_manager", None)
            if initialization_manager is not None:
                return initialization_manager.ensure_tray_initialized()
        except Exception as e:
            log(f"Не удалось инициализировать системный трей по требованию: {e}", "WARNING")

        return None

    def minimize_to_tray(self) -> bool:
        """Скрывает окно в трей (без выхода из GUI)."""
        try:
            tray_manager = self.ensure_tray_manager()
            if tray_manager is not None:
                return bool(tray_manager.hide_to_tray(show_hint=True))
        except Exception as e:
            log(f"Ошибка сценария сворачивания в трей: {e}", "WARNING")

        return False

    def set_status(self, text: str) -> None:
        """Sets the status text."""
        status_type = "neutral"
        lower_text = text.lower()
        if "работает" in lower_text or "запущен" in lower_text or "успешно" in lower_text:
            status_type = "running"
        elif "останов" in lower_text or "ошибка" in lower_text or "выключен" in lower_text:
            status_type = "stopped"
        elif "внимание" in lower_text or "предупреждение" in lower_text:
            status_type = "warning"

        store = getattr(self, "ui_state_store", None)
        if store is not None:
            store.set_status_message(text, status_type)


    def delayed_dpi_start(self) -> None:
        """Выполняет отложенный запуск DPI с проверкой наличия автозапуска"""
        if hasattr(self, 'dpi_manager'):
            self.dpi_manager.delayed_dpi_start()

    def on_strategy_selected_from_dialog(self, strategy_id: str, strategy_name: str) -> None:
        """Обрабатывает выбор стратегии из диалога."""
        try:
            log(f"Выбрана стратегия: {strategy_name} (ID: {strategy_id})", level="INFO")
            
            # ДЛЯ DIRECT РЕЖИМА ИСПОЛЬЗУЕМ ПРОСТОЕ НАЗВАНИЕ
            from strategy_menu import get_strategy_launch_method
            launch_method = get_strategy_launch_method()
            
            if launch_method == "direct_zapret2":
                # direct_zapret2 is preset-based; do not show a phantom single-strategy name.
                try:
                    preset = self.app_context.direct_flow_coordinator.get_selected_source_manifest("direct_zapret2")
                    preset_name = str(getattr(preset, "name", "") or "")
                    display_name = f"Пресет: {preset_name}"
                except Exception:
                    display_name = "Пресет"
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
                        preset = self.app_context.direct_flow_coordinator.get_selected_source_manifest("direct_zapret1")
                        preset_name = str(getattr(preset, "name", "") or "")
                        display_name = f"Пресет: {preset_name}"
                    except Exception:
                        display_name = "Пресет"
                else:
                    display_name = "Пресет"
                strategy_name = display_name
                log(f"Установлено простое название для режима {launch_method}: {display_name}", "DEBUG")

            # Обновляем новые страницы интерфейса
            if hasattr(self, 'update_current_strategy_display'):
                self.update_current_strategy_display(strategy_name)

            # Direct launch methods now go through one canonical controller path.
            if launch_method in ("direct_zapret2", "direct_zapret2_orchestra", "direct_zapret1"):
                log(
                    f"Запуск {launch_method} передан в единый DPI controller pipeline",
                    "INFO",
                )
                self.dpi_controller.start_dpi_async(selected_mode=None, launch_method=launch_method)
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

    def __init__(self, start_in_tray: bool = False, *, app_context: AppContext):
        # ZapretFluentWindow.__init__ handles: titlebar, icon, dark theme, min size
        super().__init__()

        from strategy_menu import get_strategy_launch_method
        current_method = get_strategy_launch_method()
        log(f"Метод запуска стратегий: {current_method}", "INFO")

        self.start_in_tray = start_in_tray
        self.app_context = app_context
        self.ui_state_store = app_context.ui_state_store
        self.app_runtime_state = app_context.app_runtime_state
        self.dpi_runtime_service = app_context.dpi_runtime_service

        # Flags
        self._dpi_autostart_initiated = False
        self._is_exiting = False
        self._stop_dpi_on_exit = False
        self._closing_completely = False
        self._deferred_init_started = False
        self._startup_post_init_ready = False
        self._startup_subscription_ready = False
        self._startup_background_init_started = False
        self._tray_launch_notification_pending = bool(self.start_in_tray)

        # FluentWindow handles: frameless, titlebar, acrylic, resize, drag
        # We only need to set title and restore geometry
        self.setWindowTitle(f"Zapret2 v{APP_VERSION}")
        self.setMinimumSize(MIN_WIDTH, 400)
        self.window_close_controller = WindowCloseController(self)
        self.window_geometry_controller = WindowGeometryController(
            self,
            min_width=MIN_WIDTH,
            min_height=400,
            default_width=WIDTH,
            default_height=HEIGHT,
        )
        self.window_notification_controller = WindowNotificationController(self)
        self.window_notification_controller.register_global_error_notifier()
        self.window_geometry_controller.restore_geometry()

        self._holiday_effects = HolidayEffectsManager(self)
        self._startup_ttff_logged = False
        self._startup_ttff_ms = None
        self._startup_interactive_logged = False
        self._startup_interactive_ms = None
        self._startup_managers_ready_logged = False
        self._startup_managers_ready_ms = None
        self._startup_post_init_done_logged = False
        self._startup_post_init_done_ms = None
        self._last_active_preset_content_path = ""
        self._last_active_preset_content_ms = 0
        self.deferred_init_requested.connect(self._deferred_init, Qt.ConnectionType.QueuedConnection)
        self.continue_startup_requested.connect(self._continue_deferred_init, Qt.ConnectionType.QueuedConnection)
        self.finalize_ui_bootstrap_requested.connect(self._finalize_ui_bootstrap, Qt.ConnectionType.QueuedConnection)
        self.runner_runtime_state_requested.connect(self._apply_runner_runtime_state_update, Qt.ConnectionType.QueuedConnection)
        self.active_preset_content_changed_requested.connect(self._apply_active_preset_content_changed, Qt.ConnectionType.QueuedConnection)

        # Show window right away (FluentWindow handles rendering)
        if not self.start_in_tray and not self.isVisible():
            self.show()
            log("Основное окно показано (FluentWindow, init в фоне)", "DEBUG")

        self.deferred_init_requested.emit()

    def _mark_startup_subscription_ready(self, source: str = "subscription_ready") -> None:
        self._startup_subscription_ready = True

    def _start_background_init(self) -> None:
        if self._startup_background_init_started:
            return
        self._startup_background_init_started = True

        try:
            subscription_manager = getattr(self, "subscription_manager", None)
            if subscription_manager is not None:
                subscription_manager.initialize_async()
        except Exception:
            pass

        notification_controller = getattr(self, "window_notification_controller", None)
        if notification_controller is not None:
            notification_controller.schedule_startup_notification_queue(0)

    def _deferred_init(self) -> None:
        """Heavy initialization — runs after first frame is shown."""
        if self._deferred_init_started:
            return
        self._deferred_init_started = True

        import time as _time
        _t_total = _time.perf_counter()
        log("⏱ Startup: deferred init started", "DEBUG")

        # Build UI: create the first visible pages and minimum navigation shell.
        # Всё, что не нужно для первого кадра и первого клика, переносим дальше.
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
            return
        log(f"⏱ Startup: build_ui {(_time.perf_counter() - _t_build) * 1000:.0f}ms", "DEBUG")
        log(f"⏱ Startup: deferred init total {( _time.perf_counter() - _t_total ) * 1000:.0f}ms", "DEBUG")
        self.continue_startup_requested.emit()

    def _continue_deferred_init(self) -> None:
        """Продолжает старт уже после показа базового UI.

        Этот этап не должен мешать первому визуальному отклику окна: сначала
        пользователь видит страницу и может начать взаимодействовать, а потом
        приложение спокойно поднимает менеджеры и фоновую инфраструктуру.
        """
        import time as _time
        _t_total = _time.perf_counter()

        _t_mgr = _time.perf_counter()
        _manager_bootstrap(self)
        log(f"⏱ Startup: managers init {( _time.perf_counter() - _t_mgr ) * 1000:.0f}ms", "DEBUG")

        self.update_title_with_subscription_status(False, None, 0, source="init")

        # Стартовый порядок теперь управляется самим initialization_manager.
        self.initialization_manager.run_async_init()
        log(f"⏱ Startup: continue init total {( _time.perf_counter() - _t_total ) * 1000:.0f}ms", "DEBUG")

        # Тяжёлые глобальные связи окна дозаводим ещё одним отдельным проходом,
        # чтобы не склеивать их с первым построением интерфейса.
        self.finalize_ui_bootstrap_requested.emit()

    def _finalize_ui_bootstrap(self) -> None:
        """Завершает не критичную для первого кадра сборку главного окна."""
        try:
            self.finish_ui_bootstrap()
        except Exception as e:
            log(f"Startup: finish_ui_bootstrap failed: {e}", "DEBUG")

    def _apply_runner_runtime_state_update(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return

        runtime_service = getattr(self, "dpi_runtime_service", None)
        if runtime_service is None:
            return

        launch_method = str(payload.get("launch_method") or "").strip().lower()
        if launch_method not in {"direct_zapret1", "direct_zapret2"}:
            return

        snapshot = runtime_service.snapshot()
        current_method = str(snapshot.launch_method or "").strip().lower()
        if current_method and current_method != launch_method and snapshot.phase in {"starting", "running", "autostart_pending"}:
            return

        try:
            from config import get_winws_exe_for_method

            expected_process = os.path.basename(get_winws_exe_for_method(launch_method)).strip().lower()
        except Exception:
            expected_process = snapshot.expected_process

        preset_path = str(payload.get("preset_path") or "").strip()
        pid = payload.get("pid")
        error_text = str(payload.get("error") or "").strip()
        phase = str(payload.get("phase") or "").strip().lower()

        if phase == "starting":
            runtime_service.begin_start(
                launch_method=launch_method,
                expected_process=expected_process,
                expected_preset_path=preset_path,
            )
            return

        if phase == "running":
            runtime_service.mark_running(
                pid=pid if isinstance(pid, int) else None,
                expected_process=expected_process,
                expected_preset_path=preset_path or snapshot.expected_preset_path,
            )
            return

        if phase == "failed":
            runtime_service.mark_start_failed(
                error_text or "Запуск завершился ошибкой",
            )

    def _apply_active_preset_content_changed(self, path: str) -> None:
        normalized_path = os.path.normcase(str(path or "").strip())
        if not normalized_path:
            return

        now_ms = _startup_elapsed_ms()
        if (
            normalized_path == str(getattr(self, "_last_active_preset_content_path", "") or "")
            and max(0, now_ms - int(getattr(self, "_last_active_preset_content_ms", 0) or 0)) < 500
        ):
            return

        self._last_active_preset_content_path = normalized_path
        self._last_active_preset_content_ms = now_ms

        store = getattr(self, "ui_state_store", None)
        if store is None:
            return
        try:
            store.bump_preset_content_revision()
        except Exception:
            pass

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
        try:
            self.startup_interactive_ready.emit(str(source or "interactive"))
        except Exception:
            pass

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

        _log_startup_metric("CoreStartupReady", details)

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
            details = f"{source}, +{delta_ms}ms after CoreStartupReady"
        elif isinstance(self._startup_interactive_ms, int):
            delta_ms = max(0, post_init_ms - self._startup_interactive_ms)
            details = f"{source}, +{delta_ms}ms after Interactive"

        _log_startup_metric("PostInitDispatched", details)
        self._startup_post_init_ready = True
        try:
            self.startup_post_init_ready.emit(str(source or "post_init"))
        except Exception:
            pass
        self._start_background_init()
        notification_controller = getattr(self, "window_notification_controller", None)
        if notification_controller is not None:
            notification_controller.schedule_startup_notification_queue(0)

    def setWindowTitle(self, title: str):
        """Override to update FluentWindow's built-in titlebar."""
        super().setWindowTitle(title)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange:
            try:
                if not self.isActiveWindow():
                    self._release_input_interaction_states()
            except Exception:
                pass

        if event.type() == QEvent.Type.WindowStateChange:
            geometry_controller = getattr(self, "window_geometry_controller", None)
            if geometry_controller is not None:
                geometry_controller.on_window_state_change()

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
        geometry_controller = getattr(self, "window_geometry_controller", None)
        if geometry_controller is not None:
            geometry_controller.on_geometry_changed()
    
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

    def _cleanup_loaded_page(self, page_name: PageName) -> None:
        page = self.get_loaded_page(page_name)
        if page is None or not hasattr(page, "cleanup"):
            return
        try:
            page.cleanup()
        except Exception as e:
            log(f"Ошибка при очистке страницы {page_name}: {e}", "DEBUG")

    def _cleanup_threaded_pages_for_close(self) -> None:
        try:
            for page_name in (
                PageName.LOGS,
                PageName.SERVERS,
                PageName.BLOCKCHECK,
                PageName.HOSTS,
            ):
                self._cleanup_loaded_page(page_name)
        except Exception as e:
            log(f"Ошибка при очистке страниц: {e}", "DEBUG")

    def _cleanup_support_managers_for_close(self) -> None:
        try:
            process_monitor_manager = getattr(self, "process_monitor_manager", None)
            if process_monitor_manager is not None:
                process_monitor_manager.stop_monitoring()
        except Exception as e:
            log(f"Ошибка остановки process_monitor_manager: {e}", "DEBUG")

        try:
            dns_ui_manager = getattr(self, "dns_ui_manager", None)
            if dns_ui_manager is not None:
                dns_ui_manager.cleanup()
        except Exception as e:
            log(f"Ошибка при очистке dns_ui_manager: {e}", "DEBUG")

        try:
            theme_handler = getattr(self, "theme_handler", None)
            theme_manager = getattr(theme_handler, "theme_manager", None) if theme_handler is not None else None
            if theme_manager is not None:
                theme_manager.cleanup()
        except Exception as e:
            log(f"Ошибка при очистке theme_manager: {e}", "DEBUG")


    def _cleanup_visual_and_proxy_resources_for_close(self) -> None:
        try:
            from ui.pages.telegram_proxy_page import _get_proxy_manager

            _get_proxy_manager().cleanup()
        except Exception:
            pass

        try:
            effects = getattr(self, "_holiday_effects", None)
            if effects is not None:
                effects.cleanup()
                self._holiday_effects = None
        except Exception as e:
            log(f"Ошибка очистки праздничных эффектов: {e}", "DEBUG")

    def _cleanup_runtime_threads_for_close(self) -> None:
        try:
            dpi_controller = getattr(self, "dpi_controller", None)
            if dpi_controller is not None:
                dpi_controller.cleanup_threads()
        except Exception as e:
            log(f"Ошибка очистки DPI controller threads: {e}", "DEBUG")

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

    def _cleanup_tray_for_close(self) -> None:
        try:
            tray_manager = getattr(self, "tray_manager", None)
            if tray_manager is not None:
                tray_manager.cleanup()
                self.tray_manager = None
        except Exception as e:
            log(f"Ошибка очистки системного трея: {e}", "DEBUG")
    
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
                self._route_search_result(PageName.BLOCKCHECK, "diagnostics")
                self._call_loaded_page_method(
                    PageName.BLOCKCHECK,
                    "request_diagnostics_start_focus",
                )
                log("Открыта вкладка диагностики в BlockCheck", "INFO")
        except Exception as e:
            log(f"Ошибка при открытии вкладки тестирования: {e}", "❌ ERROR")
            self.set_status(f"Ошибка: {e}")

    def set_garland_enabled(self, enabled: bool) -> None:
        """Enable/disable top garland overlay in FluentWindow shell."""
        try:
            store = getattr(self, "ui_state_store", None)
            if store is not None:
                snapshot = store.snapshot()
                store.set_holiday_overlays(bool(enabled), snapshot.snowflakes_enabled)

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
            store = getattr(self, "ui_state_store", None)
            if store is not None:
                snapshot = store.snapshot()
                store.set_holiday_overlays(snapshot.garland_enabled, bool(enabled))

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
            store = getattr(self, "ui_state_store", None)
            if store is not None:
                store.set_window_opacity_value(value)

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
        geometry_controller = getattr(self, "window_geometry_controller", None)
        if geometry_controller is not None:
            geometry_controller.on_geometry_changed()
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
        geometry_controller = getattr(self, "window_geometry_controller", None)
        if geometry_controller is not None:
            geometry_controller.apply_saved_maximized_state_if_needed()
        # Включаем автосохранение геометрии (после первого show + небольшой паузы)
        if geometry_controller is not None:
            QTimer.singleShot(350, geometry_controller.enable_persistence)

        try:
            effects = getattr(self, "_holiday_effects", None)
            if effects is not None:
                effects.sync_geometry()
                QTimer.singleShot(0, effects.sync_geometry)
        except Exception:
            pass

        notification_controller = getattr(self, "window_notification_controller", None)
        if notification_controller is not None:
            notification_controller.schedule_startup_notification_queue(0)

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
            self.set_garland_enabled(should_enable_garland)
            
            # Снежинки
            should_enable_snowflakes = is_premium and snowflakes_saved
            self.set_snowflakes_enabled(should_enable_snowflakes)

            # Прозрачность окна (не зависит от премиума)
            from config.reg import get_window_opacity
            opacity_saved = get_window_opacity()
            log(f"🔮 Инициализация: opacity={opacity_saved}%", "DEBUG")
            self.set_window_opacity(opacity_saved)

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
            return True
        else:
            log(f"Ошибка при выполнении команды: {result.stderr}", level="❌ ERROR")
            return False
            
    except Exception as e:
        log(f"Произошла ошибка: {e}", level="❌ ERROR")
        return False

def _shell_bootstrap() -> bool:
    import atexit
    import ctypes
    import sys

    if "--version" in sys.argv:
        ctypes.windll.user32.MessageBoxW(None, APP_VERSION, "Zapret – версия", 0x40)
        sys.exit(0)

    if "--update" in sys.argv and len(sys.argv) > 3:
        _handle_update_mode()
        sys.exit(0)

    start_in_tray = "--tray" in sys.argv

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

    from startup.single_instance import create_mutex, release_mutex
    from startup.ipc_manager import IPCManager

    mutex_handle, already_running = create_mutex("ZapretSingleInstance")
    if already_running:
        ipc = IPCManager()
        if ipc.send_show_command():
            log("Отправлена команда показать окно запущенному экземпляру", "INFO")
        else:
            ctypes.windll.user32.MessageBoxW(
                None,
                "Экземпляр Zapret уже запущен, но не удалось показать окно!",
                "Zapret",
                0x40,
            )
        sys.exit(0)

    atexit.register(lambda: release_mutex(mutex_handle))
    return bool(start_in_tray)


def _application_bootstrap():
    import ctypes

    app = QApplication.instance()
    try:
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

        from log.crash_handler import install_qt_crash_handler
        install_qt_crash_handler(app)

    except Exception as e:
        ctypes.windll.user32.MessageBoxW(None, f"Ошибка инициализации Qt: {e}", "Zapret", 0x10)

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

    try:
        from config.reg import (
            get_follow_windows_accent,
            get_windows_system_accent,
            get_accent_color,
            set_accent_color,
        )
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

    return app


def _window_bootstrap(*, start_in_tray: bool) -> tuple[AppContext, "LupiDPIApp"]:
    app_context = build_app_context(initial_ui_state=LupiDPIApp._build_initial_ui_state())
    install_app_context(app_context)
    window = LupiDPIApp(start_in_tray=start_in_tray, app_context=app_context)
    return app_context, window


def _manager_bootstrap(window: "LupiDPIApp") -> None:
    from managers.initialization_manager import InitializationManager
    from managers.subscription_manager import SubscriptionManager
    from managers.process_monitor_manager import ProcessMonitorManager
    from managers.ui_manager import UIManager

    window.initialization_manager = InitializationManager(window)
    window.subscription_manager = SubscriptionManager(window)
    window.process_monitor_manager = ProcessMonitorManager(window)
    window.ui_manager = UIManager(window)


def main():
    import sys, ctypes, os, atexit
    from startup.ipc_manager import IPCManager
    log("=== ЗАПУСК ПРИЛОЖЕНИЯ ===", "🔹 main")
    log(APP_VERSION, "🔹 main")

    start_in_tray = _shell_bootstrap()
    app = _application_bootstrap()
    _app_context, window = _window_bootstrap(start_in_tray=start_in_tray)

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

    # ✅ НЕКРИТИЧЕСКИЕ ПРОВЕРКИ ПОСЛЕ ПОКАЗА ОКНА
    # Важно: тяжёлые проверки должны выполняться НЕ в GUI-потоке, иначе окно "замирает".
    from PyQt6.QtCore import QObject, pyqtSignal

    class _StartupChecksBridge(QObject):
        finished = pyqtSignal(dict)

    _startup_bridge = _StartupChecksBridge()

    class _DeferredMaintenanceBridge(QObject):
        finished = pyqtSignal(dict)

    _deferred_maintenance_bridge = _DeferredMaintenanceBridge()

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
            controller = getattr(window, "window_notification_controller", None)
            blocking_notification = payload.get("blocking_notification")
            notifications = payload.get("notifications") or []
            duration_ms = int(payload.get("duration_ms") or 0)

            if duration_ms > 0:
                window.log_startup_metric("StartupChecksFinished", f"{duration_ms}ms")

            if blocking_notification:
                if controller is not None:
                    controller.notify(blocking_notification)
                else:
                    title = str(blocking_notification.get("title") or "Ошибка")
                    content = str(blocking_notification.get("content") or "")
                    try:
                        QMessageBox.critical(window, title, content)
                    except Exception:
                        _native_message_safe(title, content, 0x10)
                QApplication.quit()
                return

            if controller is not None:
                controller.notify_many([item for item in notifications if isinstance(item, dict)])

            log("✅ Все проверки пройдены", "🔹 main")
        except Exception as e:
            log(f"Ошибка при обработке результатов проверок: {e}", "❌ ERROR")

    _startup_bridge.finished.connect(_on_startup_checks_finished)

    def _on_deferred_maintenance_finished(payload: dict) -> None:
        try:
            controller = getattr(window, "window_notification_controller", None)
            duration_ms = int(payload.get("duration_ms") or 0)
            if duration_ms > 0:
                window.log_startup_metric("DeferredMaintenanceFinished", f"{duration_ms}ms")

            if bool(payload.get("association_ok")):
                log("Ассоциация успешно установлена", level="INFO")

            if controller is not None:
                controller.notify_many(payload.get("notifications") or [])
        except Exception as e:
            log(f"Ошибка поздней служебной проверки: {e}", "❌ ERROR")

    _deferred_maintenance_bridge.finished.connect(_on_deferred_maintenance_finished)

    def _bind_startup_gate(signal, callback, *, gate_name: str, is_ready) -> None:
        """Привязывает startup-задачу к честному событию вместо polling по флагу."""
        started = False

        def _run(*_args) -> None:
            nonlocal started
            if started:
                return
            started = True
            callback()

        try:
            signal.connect(_run)
        except Exception:
            QTimer.singleShot(0, _run)
            return

        try:
            if bool(is_ready()):
                QTimer.singleShot(0, _run)
        except Exception:
            QTimer.singleShot(0, _run)

    def _startup_checks_worker():
        started_at = time.perf_counter()
        try:
            from startup.bfe_util import preload_service_status, ensure_bfe_running, cleanup as bfe_cleanup
            from startup.check_start import collect_startup_notifications, check_goodbyedpi, check_mitmproxy
            notifications: list[dict] = []
            blocking_notification: dict | None = None

            preload_service_status("BFE")

            bfe_ok, bfe_notification = ensure_bfe_running()
            if bfe_notification is not None:
                notifications.append(bfe_notification)
            if not bfe_ok:
                log("BFE не запущен, продолжаем работу после предупреждения", "⚠ WARNING")

            startup_notifications, blocking_notification = collect_startup_notifications()
            notifications.extend(startup_notifications or [])
            log(
                "Startup notifications collected: "
                f"count={len(startup_notifications or [])}, "
                f"blocking={'yes' if blocking_notification else 'no'}",
                "⏱ STARTUP",
            )

            # Нефатальные, но потенциально долгие проверки — только в фоне после показа окна.
            has_gdpi, gdpi_msg = check_goodbyedpi()
            if has_gdpi and gdpi_msg:
                notifications.append(
                    advisory_notification(
                        level="warning",
                        title="Проверка при запуске",
                        content=gdpi_msg,
                        source="startup.goodbyedpi",
                        queue="startup",
                        duration=15000,
                        dedupe_key="startup.goodbyedpi",
                    )
                )

            has_mitmproxy, mitmproxy_msg = check_mitmproxy()
            if has_mitmproxy and mitmproxy_msg:
                notifications.append(
                    advisory_notification(
                        level="warning",
                        title="Проверка при запуске",
                        content=mitmproxy_msg,
                        source="startup.mitmproxy",
                        queue="startup",
                        duration=15000,
                        dedupe_key="startup.mitmproxy",
                    )
                )

            try:
                from startup.kaspersky import _check_kaspersky_antivirus, build_kaspersky_notification

                kaspersky_detected = bool(_check_kaspersky_antivirus())
                log(
                    f"Kaspersky startup check: detected={'yes' if kaspersky_detected else 'no'}",
                    "⏱ STARTUP",
                )
                if kaspersky_detected:
                    kaspersky_notification = build_kaspersky_notification()
                    if kaspersky_notification is not None:
                        log("Обнаружен антивирус Kaspersky", "⚠️ KASPERSKY")
                        notifications.append(kaspersky_notification)
            except Exception:
                pass

            if is_verbose_logging_enabled():
                from startup.admin_check_debug import debug_admin_status
                debug_admin_status()

            try:
                atexit.register(bfe_cleanup)
            except Exception:
                pass

            _startup_bridge.finished.emit(
                {
                    "notifications": notifications,
                    "blocking_notification": blocking_notification,
                    "duration_ms": int((time.perf_counter() - started_at) * 1000),
                }
            )
        except Exception as e:
            log(f"Ошибка при асинхронных проверках: {e}", "❌ ERROR")
            if hasattr(window, 'set_status'):
                try:
                    window.set_status(f"Ошибка проверок: {e}")
                except Exception:
                    pass
            _startup_bridge.finished.emit(
                {
                    "notifications": [],
                    "blocking_notification": None,
                    "duration_ms": int((time.perf_counter() - started_at) * 1000),
                }
            )

    # Запускаем проверки только после interactive-фазы,
    # чтобы не конкурировать с heavy build_ui на старте.
    def _start_startup_checks():
        import threading
        window.log_startup_metric("StartupChecksStarted", "startup_checks_worker")
        threading.Thread(target=_startup_checks_worker, daemon=True).start()

    _bind_startup_gate(
        window.startup_interactive_ready,
        _start_startup_checks,
        gate_name="startup_checks",
        is_ready=lambda: bool(getattr(window, "_startup_interactive_logged", False)),
    )

    def _deferred_maintenance_worker():
        started_at = time.perf_counter()
        telega_found_path = None
        association_ok = False
        notifications: list[dict] = []
        try:
            try:
                from startup.telega_check import _check_telega_installed, build_telega_notification
                telega_found_path = _check_telega_installed()
                log(
                    "Telega deferred check: "
                    f"found={'yes' if bool(telega_found_path) else 'no'}"
                    + (f", value={telega_found_path}" if telega_found_path else ""),
                    "⏱ STARTUP",
                )
                if telega_found_path:
                    log(f"Обнаружена Telega Desktop: {telega_found_path}", "🚨 TELEGA")
                    telega_notification = build_telega_notification(found_path=str(telega_found_path))
                    if telega_notification is not None:
                        notifications.append(telega_notification)
            except Exception:
                telega_found_path = None

            try:
                association_ok = bool(set_batfile_association())
            except Exception as association_error:
                log(f"Ошибка установки ассоциации batfile: {association_error}", "DEBUG")
        except Exception as e:
            log(f"Ошибка поздних служебных проверок: {e}", "❌ ERROR")
        finally:
            try:
                log(
                    f"Deferred maintenance notifications collected: count={len(notifications)}",
                    "⏱ STARTUP",
                )
            except Exception:
                pass
            _deferred_maintenance_bridge.finished.emit(
                {
                    "association_ok": association_ok,
                    "notifications": notifications,
                    "telega_found_path": telega_found_path,
                    "duration_ms": int((time.perf_counter() - started_at) * 1000),
                }
            )

    def _start_deferred_maintenance():
        import threading
        window.log_startup_metric("DeferredMaintenanceStarted", "telega_association_worker")
        threading.Thread(target=_deferred_maintenance_worker, daemon=True).start()

    def _schedule_deferred_maintenance() -> None:
        delay_ms = 6000
        log(
            f"Проверка Telega Desktop и служебные действия отложены на {delay_ms}ms после post-init",
            "DEBUG",
        )
        QTimer.singleShot(delay_ms, _start_deferred_maintenance)

    _bind_startup_gate(
        window.startup_post_init_ready,
        _schedule_deferred_maintenance,
        gate_name="deferred_maintenance",
        is_ready=lambda: bool(getattr(window, "_startup_post_init_ready", False)),
    )

    # ─── Автопроверка обновлений при запуске ───────────────────────────────────

    class _UpdateCheckBridge(QObject):
        update_found = pyqtSignal(str, str)   # version, release_notes
        no_update    = pyqtSignal(str)        # current_version
        check_error  = pyqtSignal(str)        # error_message

    _update_bridge = _UpdateCheckBridge()

    def _on_update_found(version: str, release_notes: str) -> None:
        try:
            try:
                window.set_status(f"Доступно обновление v{version}")
            except Exception:
                pass
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
                sp.present_startup_update(
                    version,
                    release_notes,
                    install_after_show=True,
                )
        except Exception as e:
            log(f"Ошибка при показе диалога обновления: {e}", "❌ ERROR")

    def _on_no_update(current_version: str) -> None:
        try:
            try:
                window.set_status(f"Обновлений нет, установлена версия {current_version}")
            except Exception:
                pass
            controller = getattr(window, "window_notification_controller", None)
            if controller is not None:
                controller.notify(
                    advisory_notification(
                        level="success",
                        title="Обновлений нет",
                        content=f"Установлена актуальная версия {current_version}",
                        source="startup.update_check",
                        presentation="infobar",
                        queue="immediate",
                        duration=4000,
                        dedupe_key=f"startup.update_check:{current_version}",
                    )
                )
        except Exception as e:
            log(f"Ошибка при показе InfoBar: {e}", "❌ ERROR")

    def _on_update_check_error(error: str) -> None:
        try:
            window.set_status("Не удалось проверить обновления")
        except Exception:
            pass
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
        try:
            window.set_status("Проверка обновлений...")
        except Exception:
            pass
        import threading
        threading.Thread(target=_startup_update_worker, daemon=True).start()

    def _schedule_startup_update_check_deferred() -> None:
        delay_ms = 12000
        log(f"Автопроверка обновлений отложена на {delay_ms}ms после готовности UI", "DEBUG")
        QTimer.singleShot(delay_ms, _schedule_startup_update_check)

    _bind_startup_gate(
        window.startup_post_init_ready,
        _schedule_startup_update_check_deferred,
        gate_name="startup_update_check",
        is_ready=lambda: bool(getattr(window, "_startup_post_init_ready", False)),
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
