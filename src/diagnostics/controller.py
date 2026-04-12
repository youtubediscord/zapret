from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class ConnectionTestStartPlan:
    test_type: str
    start_lines: tuple[str, ...]
    status_text: str
    status_tone: str
    status_badge_text: str
    progress_badge_text: str
    start_enabled: bool
    stop_enabled: bool
    combo_enabled: bool
    send_log_enabled: bool
    progress_visible: bool


@dataclass(slots=True)
class ConnectionTestFinishPlan:
    status_text: str
    status_tone: str
    status_badge_text: str
    progress_badge_text: str
    finish_lines: tuple[str, ...]
    start_enabled: bool
    stop_enabled: bool
    combo_enabled: bool
    send_log_enabled: bool
    progress_visible: bool


@dataclass(slots=True)
class ConnectionTestStopPlan:
    append_lines: tuple[str, ...]
    status_text: str
    status_tone: str
    poll_interval_ms: int
    max_attempts: int
    finalize_delay_ms: int


@dataclass(slots=True)
class ConnectionStopPollPlan:
    action: str
    append_line: str
    finalize_delay_ms: int


@dataclass(slots=True)
class ConnectionCleanupPlan:
    should_request_stop: bool
    should_quit_thread: bool
    wait_timeout_ms: int
    should_terminate: bool
    terminate_wait_ms: int


@dataclass(slots=True)
class ConnectionSupportPlan:
    log_lines: tuple[str, ...]
    status_text: str
    status_tone: str


class ConnectionPageController:
    @staticmethod
    def normalize_test_type(test_type: str) -> str:
        normalized = str(test_type or "").strip().lower()
        if normalized in {"discord", "youtube", "all"}:
            return normalized
        return "all"

    @staticmethod
    def build_start_plan(*, selection: str, test_type: str) -> ConnectionTestStartPlan:
        return ConnectionTestStartPlan(
            test_type=ConnectionPageController.normalize_test_type(test_type),
            start_lines=(
                f"🚀 Запуск тестирования: {selection}",
                "=" * 50,
            ),
            status_text="🔄 Тестирование в процессе...",
            status_tone="info",
            status_badge_text="Тест выполняется",
            progress_badge_text="Идёт проверка",
            start_enabled=False,
            stop_enabled=True,
            combo_enabled=False,
            send_log_enabled=False,
            progress_visible=True,
        )

    @staticmethod
    def build_worker_update_lines(message: str) -> tuple[str, ...]:
        if "DNS" in message and "подмен" in message:
            return (
                message,
                "💡 Совет: откройте вкладку «DNS подмена» для детального анализа",
            )
        return (message,)

    @staticmethod
    def build_finish_plan() -> ConnectionTestFinishPlan:
        return ConnectionTestFinishPlan(
            status_text="✅ Тестирование завершено",
            status_tone="success",
            status_badge_text="Тест завершён",
            progress_badge_text="Готово к обращению",
            finish_lines=(
                "\n" + "=" * 50,
                "🎉 Тестирование завершено! Теперь можно одной кнопкой подготовить обращение в поддержку.",
            ),
            start_enabled=True,
            stop_enabled=False,
            combo_enabled=True,
            send_log_enabled=True,
            progress_visible=False,
        )

    @staticmethod
    def build_stopped_finish_plan() -> ConnectionTestFinishPlan:
        return ConnectionTestFinishPlan(
            status_text="⏹️ Тест остановлен",
            status_tone="warning",
            status_badge_text="Тест остановлен",
            progress_badge_text="Остановлено",
            finish_lines=(
                "\n" + "=" * 50,
                "⏹️ Тест остановлен пользователем. Можно запустить его снова или подготовить обращение по уже собранным логам.",
            ),
            start_enabled=True,
            stop_enabled=False,
            combo_enabled=True,
            send_log_enabled=True,
            progress_visible=False,
        )

    @staticmethod
    def build_stop_plan() -> ConnectionTestStopPlan:
        return ConnectionTestStopPlan(
            append_lines=("\n⚠️ Остановка теста...",),
            status_text="⏹️ Останавливаем...",
            status_tone="warning",
            poll_interval_ms=100,
            max_attempts=50,
            finalize_delay_ms=800,
        )

    @staticmethod
    def build_stop_poll_plan(
        *,
        attempt_count: int,
        thread_running: bool,
        max_attempts: int,
        finalize_delay_ms: int,
    ) -> ConnectionStopPollPlan:
        if not thread_running:
            return ConnectionStopPollPlan(
                action="finish",
                append_line="",
                finalize_delay_ms=0,
            )
        if int(attempt_count) >= int(max_attempts):
            return ConnectionStopPollPlan(
                action="force_terminate",
                append_line="⚠️ Принудительная остановка...",
                finalize_delay_ms=finalize_delay_ms,
            )
        return ConnectionStopPollPlan(
            action="continue",
            append_line="",
            finalize_delay_ms=0,
        )

    @staticmethod
    def build_cleanup_plan(*, has_worker: bool, thread_running: bool) -> ConnectionCleanupPlan:
        return ConnectionCleanupPlan(
            should_request_stop=bool(has_worker and thread_running),
            should_quit_thread=bool(thread_running),
            wait_timeout_ms=2000,
            should_terminate=bool(thread_running),
            terminate_wait_ms=500,
        )

    @staticmethod
    def prepare_support_request_for_connection(*, selection: str) -> ConnectionSupportPlan:
        from config import LOGS_FOLDER
        from log import global_logger, LOG_FILE
        from support_request_bundle import prepare_support_request

        temp_log_path = os.path.join(LOGS_FOLDER, "connection_test_temp.log")
        try:
            result = prepare_support_request(
                bundle_prefix="connection_support",
                context_label=f"Диагностика соединения: {selection}",
                candidate_paths=[
                    temp_log_path,
                    getattr(global_logger, "log_file", LOG_FILE),
                ],
                recent_patterns=("blockcheck_run_*.log",),
                extra_note="В архив добавлен лог connection_test_temp.log, если он сохранился после теста.",
            )

            lines: list[str] = []
            if result.zip_path:
                lines.append(f"📦 Подготовлен архив: {result.zip_path}")
            else:
                lines.append("⚠️ Архив не был создан, потому что подходящие файлы логов не найдены.")

            if result.copied_to_clipboard:
                lines.append("📋 Шаблон обращения скопирован в буфер обмена.")
            else:
                lines.append("⚠️ Не удалось скопировать шаблон обращения в буфер обмена.")

            if result.discussions_opened:
                lines.append("🌐 GitHub Discussions открыты.")
            else:
                lines.append("⚠️ GitHub Discussions не удалось открыть автоматически.")

            if result.bundle_folder_opened:
                lines.append("📁 Папка с готовым архивом открыта.")

            return ConnectionSupportPlan(
                log_lines=tuple(lines),
                status_text="✅ Обращение подготовлено",
                status_tone="success",
            )
        except Exception as exc:
            return ConnectionSupportPlan(
                log_lines=(f"❌ Не удалось подготовить обращение: {exc}",),
                status_text="Ошибка подготовки обращения",
                status_tone="error",
            )
