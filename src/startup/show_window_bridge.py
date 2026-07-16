# startup/show_window_bridge.py

from __future__ import annotations

from log.log import log

from PyQt6.QtCore import QObject, pyqtSignal

from startup.single_instance import start_show_event_watcher


class ShowWindowBridge(QObject):
    """Доставляет сигнал «показать окно» от второго экземпляра в главный поток Qt.

    Поток-наблюдатель ждёт named event (см. startup/single_instance.py) и
    эмитит show_requested; queued connection переносит вызов в главный поток.
    """

    show_requested = pyqtSignal()

    def __init__(self, window):
        super().__init__()
        self.window = window
        self._watcher_thread = None

    def start(self) -> bool:
        """Подключает обработчик и запускает наблюдатель события.

        False — событие не было создано (не Windows или CreateEventW не прошёл).
        """
        self.show_requested.connect(self._handle_show_window)
        self._watcher_thread = start_show_event_watcher(self.show_requested.emit)
        if self._watcher_thread is None:
            log("Наблюдатель события показа окна не запущен", "WARNING")
            return False
        return True

    def _handle_show_window(self):
        """Обработчик сигнала показа окна (выполняется в главном потоке)"""
        if self.window:
            tray_manager = getattr(getattr(self.window, "visual_state", None), "tray_manager", None)
            if tray_manager is not None:
                tray_manager.show_window()
            else:
                from ui.window_adapter import show_window

                show_window(self.window)
            log("Окно показано по запросу от другого экземпляра", "INFO")
