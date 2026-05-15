from typing import Optional

from PyQt6.QtCore import QThread, QObject
from donater.state import premium_state_from_activation_info
from donater.subscription_ui import (
    apply_subscription_progress_to_ui,
    apply_premium_state_to_ui,
    apply_subscription_init_failed_to_ui,
    apply_subscription_ready_to_ui,
    apply_subscription_starting_to_ui,
    SubscriptionUiActions,
)
from donater.subscription_worker import SubscriptionInitWorker
from log.log import log



class SubscriptionManager:
    """Запускает PremiumService в фоне и передаёт результат в UI-слой."""

    def __init__(self, *, thread_parent, ui_actions: SubscriptionUiActions):
        self.thread_parent = thread_parent
        self.ui_actions = ui_actions
        self._subscription_thread: Optional[QThread] = None
        self._subscription_worker: Optional[QObject] = None
        self._cleanup_in_progress = False

    @staticmethod
    def _shutdown_thread(thread: Optional[QThread], *, wait_timeout_ms: int = 2000) -> Optional[QThread]:
        if thread is None:
            return None
        try:
            if thread.isRunning():
                thread.quit()
                if not thread.wait(wait_timeout_ms):
                    log("⚠ Поток подписки не завершился, принудительно завершаем", "WARNING")
                    thread.terminate()
                    thread.wait(500)
        except RuntimeError:
            return None
        except Exception as e:
            log(f"Ошибка остановки потока подписки: {e}", "DEBUG")
        return None

    def initialize_async(self):
        """Асинхронно запускает первичную проверку подписки."""
        self._cleanup_in_progress = False
        if self._subscription_thread is not None:
            try:
                if self._subscription_thread.isRunning():
                    log("Инициализация подписки уже выполняется, повторный запуск пропущен", "DEBUG")
                    return
            except RuntimeError:
                self._subscription_thread = None
                self._subscription_worker = None

        apply_subscription_starting_to_ui(set_status=self.ui_actions.set_status)

        self._subscription_thread = QThread(self.thread_parent)
        self._subscription_worker = SubscriptionInitWorker()
        self._subscription_worker.moveToThread(self._subscription_thread)

        def _cleanup_subscription_objects():
            self._subscription_worker = None
            self._subscription_thread = None

        self._subscription_thread.started.connect(self._subscription_worker.run)
        self._subscription_worker.progress.connect(
            lambda message, actions=self.ui_actions: apply_subscription_progress_to_ui(
                set_status=actions.set_status,
                message=message,
            )
        )
        self._subscription_worker.finished.connect(self._on_subscription_ready)
        self._subscription_worker.finished.connect(self._subscription_thread.quit)
        self._subscription_worker.finished.connect(self._subscription_worker.deleteLater)
        self._subscription_thread.finished.connect(self._subscription_thread.deleteLater)
        self._subscription_thread.finished.connect(_cleanup_subscription_objects)

        self._subscription_thread.start()

    def _on_subscription_ready(self, activation_info, success):
        """Обрабатывает результат фоновой проверки подписки."""
        if self._cleanup_in_progress:
            return
        if not success:
            log("PremiumService не инициализирован", "⚠ WARNING")
            apply_subscription_init_failed_to_ui(
                update_title_badge=self.ui_actions.update_title_badge,
                set_status=self.ui_actions.set_status,
                mark_startup_ready=self.ui_actions.mark_startup_ready,
            )
            return

        state = premium_state_from_activation_info(activation_info)
        log(
            f"Информация о подписке получена: premium={state.is_premium}, "
            f"days={state.days_remaining}, source={state.source}, "
            f"level={state.subscription_level}",
            "DEBUG",
        )

        apply_premium_state_to_ui(
            ui_state_store=self.ui_actions.ui_state_store,
            update_title_badge=self.ui_actions.update_title_badge,
            state=state,
        )
        apply_subscription_ready_to_ui(
            init_holiday_effects=self.ui_actions.init_holiday_effects,
            effects_allowed=state.is_premium,
            set_status=self.ui_actions.set_status,
            mark_startup_ready=self.ui_actions.mark_startup_ready,
        )

        log(
            f"Подписка готова: {'Premium' if state.is_premium else 'Free'} "
            f"(уровень: {state.subscription_level})",
            "INFO",
        )

    def cleanup(self) -> None:
        """Останавливает фоновые потоки менеджера подписки при закрытии приложения."""
        self._cleanup_in_progress = True
        self._subscription_thread = self._shutdown_thread(self._subscription_thread)
        self._subscription_worker = None
