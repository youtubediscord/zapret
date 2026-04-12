from __future__ import annotations

import glob
import os
import subprocess
from dataclasses import dataclass

from config import LOGS_FOLDER, MAX_DEBUG_LOG_FILES, MAX_LOG_FILES, get_winws_exe_for_method
from launcher_common import get_current_runner
from log import LOG_FILE, cleanup_old_logs, global_logger, log
from support_request_bundle import prepare_support_request


@dataclass(slots=True)
class LogsListState:
    entries: list[dict]
    current_log_file: str
    cleanup_deleted: int
    cleanup_errors: list[str]
    cleanup_total: int


@dataclass(slots=True)
class LogsStatsState:
    app_logs: int
    debug_logs: int
    total_size_mb: float
    max_logs: int
    max_debug_logs: int


@dataclass(slots=True)
class LogsThreadStopPlan:
    should_stop_worker: bool
    should_quit_thread: bool
    should_wait: bool
    wait_timeout_ms: int
    should_terminate: bool
    terminate_wait_ms: int


@dataclass(slots=True)
class LogsWinwsOutputPlan:
    action: str
    status_kind: str
    status_text: str
    process: object | None


@dataclass(slots=True)
class LogsTailStartPlan:
    should_start: bool
    info_text: str
    file_path: str


@dataclass(slots=True)
class LogsSupportFeedbackPlan:
    ok: bool
    status_text: str
    status_tone: str
    infobar_title: str
    infobar_content: str


@dataclass(slots=True)
class LogsStatsTextPlan:
    text: str


class LogsPageController:
    @staticmethod
    def get_current_log_file() -> str:
        return getattr(global_logger, "log_file", LOG_FILE)

    @staticmethod
    def list_logs(*, run_cleanup: bool) -> LogsListState:
        cleanup_deleted = 0
        cleanup_errors: list[str] = []
        cleanup_total = 0

        if run_cleanup:
            cleanup_deleted, cleanup_errors, cleanup_total = cleanup_old_logs(LOGS_FOLDER, MAX_LOG_FILES)

        log_files: list[str] = []
        log_files.extend(glob.glob(os.path.join(LOGS_FOLDER, "zapret_log_*.txt")))
        log_files.extend(glob.glob(os.path.join(LOGS_FOLDER, "zapret_[0-9]*.log")))
        log_files.extend(glob.glob(os.path.join(LOGS_FOLDER, "blockcheck_run_*.log")))
        log_files.sort(key=os.path.getmtime, reverse=True)

        current_log = LogsPageController.get_current_log_file()
        entries: list[dict] = []
        for index, log_path in enumerate(log_files):
            size_kb = os.path.getsize(log_path) / 1024
            is_current = log_path == current_log
            if is_current:
                display = f"📍 {os.path.basename(log_path)} ({size_kb:.1f} KB) - ТЕКУЩИЙ"
            else:
                display = f"{os.path.basename(log_path)} ({size_kb:.1f} KB)"
            entries.append(
                {
                    "index": index,
                    "path": log_path,
                    "size_kb": size_kb,
                    "display": display,
                    "is_current": is_current,
                }
            )

        return LogsListState(
            entries=entries,
            current_log_file=current_log,
            cleanup_deleted=cleanup_deleted,
            cleanup_errors=cleanup_errors,
            cleanup_total=cleanup_total,
        )

    @staticmethod
    def build_stats() -> LogsStatsState:
        app_logs = glob.glob(os.path.join(LOGS_FOLDER, "zapret_log_*.txt"))
        app_logs.extend(glob.glob(os.path.join(LOGS_FOLDER, "zapret_[0-9]*.log")))
        app_logs.extend(glob.glob(os.path.join(LOGS_FOLDER, "blockcheck_run_*.log")))
        debug_logs = glob.glob(os.path.join(LOGS_FOLDER, "zapret_winws2_debug_*.log"))
        all_files = app_logs + debug_logs
        total_size = sum(os.path.getsize(path) for path in all_files) / 1024 / 1024
        return LogsStatsState(
            app_logs=len(app_logs),
            debug_logs=len(debug_logs),
            total_size_mb=total_size,
            max_logs=MAX_LOG_FILES,
            max_debug_logs=MAX_DEBUG_LOG_FILES,
        )

    @staticmethod
    def resolve_winws_exe_name(launch_method: str) -> str:
        try:
            return os.path.basename(get_winws_exe_for_method(launch_method)) or "winws.exe"
        except Exception:
            return "winws.exe"

    @staticmethod
    def get_running_runner_source(launch_method: str, orchestra_runner):
        direct_runner = get_current_runner()

        orchestra_running = bool(orchestra_runner and orchestra_runner.is_running())
        direct_running = bool(direct_runner and direct_runner.is_running())

        if launch_method == "orchestra":
            if orchestra_running:
                return "orchestra", orchestra_runner
            if direct_running:
                return "direct", direct_runner
            return None, None

        if direct_running:
            return "direct", direct_runner
        if orchestra_running:
            return "orchestra", orchestra_runner
        return None, None

    @staticmethod
    def get_runner_pid(runner):
        if not runner:
            return "?"

        try:
            get_pid = getattr(runner, "get_pid", None)
            if callable(get_pid):
                pid = get_pid()
                if pid:
                    return pid
        except Exception:
            pass

        try:
            get_info = getattr(runner, "get_current_strategy_info", None)
            if callable(get_info):
                info = get_info()
                pid = info.get("pid") if isinstance(info, dict) else None
                if pid:
                    return pid
        except Exception:
            pass

        try:
            process = getattr(runner, "running_process", None)
            pid = getattr(process, "pid", None)
            if pid:
                return pid
        except Exception:
            pass

        return "?"

    @staticmethod
    def get_orchestra_log_path(orchestra_runner):
        try:
            if orchestra_runner:
                if orchestra_runner.current_log_id and orchestra_runner.debug_log_path:
                    if os.path.exists(orchestra_runner.debug_log_path):
                        return orchestra_runner.debug_log_path

                logs = orchestra_runner.get_log_history()
                if logs:
                    latest_log = logs[0]
                    log_path = os.path.join(LOGS_FOLDER, latest_log["filename"])
                    if os.path.exists(log_path):
                        return log_path
        except Exception as exc:
            log(f"Ошибка получения пути лога оркестратора: {exc}", "DEBUG")

        try:
            pattern = os.path.join(LOGS_FOLDER, "orchestra_*.log")
            files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
            if files:
                return files[0]
        except Exception as exc:
            log(f"Ошибка fallback поиска лога: {exc}", "DEBUG")

        log("Лог оркестратора не найден для отправки", "WARNING")
        return None

    @staticmethod
    def prepare_support_bundle(*, current_log_file: str, orchestra_runner):
        candidate_paths = [
            current_log_file,
            LogsPageController.get_current_log_file(),
            LogsPageController.get_orchestra_log_path(orchestra_runner),
        ]
        return prepare_support_request(
            bundle_prefix="support_logs",
            context_label="Логи приложения",
            candidate_paths=candidate_paths,
            recent_patterns=("zapret_winws2_debug_*.log", "blockcheck_run_*.log"),
            extra_note="Если проблема связана с оркестратором, в архив по возможности добавлен и его свежий лог.",
        )

    @staticmethod
    def open_logs_folder() -> None:
        subprocess.run(["explorer", LOGS_FOLDER], check=False)

    @staticmethod
    def create_log_tail_worker(file_path: str):
        from log_tail import LogTailWorker

        return LogTailWorker(
            file_path,
            poll_interval=0.6,
            initial_chunk_chars=65536,
            initial_max_bytes=1024 * 1024,
        )

    @staticmethod
    def create_winws_output_worker(process):
        from log.winws_output_worker import WinwsOutputWorker

        worker = WinwsOutputWorker()
        worker.set_process(process)
        return worker

    @staticmethod
    def build_thread_stop_plan(*, has_worker: bool, thread_running: bool, blocking: bool) -> LogsThreadStopPlan:
        return LogsThreadStopPlan(
            should_stop_worker=bool(has_worker),
            should_quit_thread=bool(thread_running),
            should_wait=bool(blocking and thread_running),
            wait_timeout_ms=2000,
            should_terminate=bool(blocking and thread_running),
            terminate_wait_ms=500,
        )

    @staticmethod
    def build_tail_start_plan(*, current_log_file: str) -> LogsTailStartPlan:
        file_path = str(current_log_file or "").strip()
        if not file_path or not os.path.exists(file_path):
            return LogsTailStartPlan(
                should_start=False,
                info_text="",
                file_path=file_path,
            )
        return LogsTailStartPlan(
            should_start=True,
            info_text=f"📄 {os.path.basename(file_path)}",
            file_path=file_path,
        )

    @staticmethod
    def build_support_feedback(result) -> LogsSupportFeedbackPlan:
        status_parts: list[str] = []
        if result.zip_path:
            status_parts.append("ZIP готов")
        if result.copied_to_clipboard:
            status_parts.append("шаблон скопирован")
        if result.discussions_opened:
            status_parts.append("GitHub открыт")
        if result.bundle_folder_opened:
            status_parts.append("папка открыта")

        archive_name = os.path.basename(result.zip_path) if result.zip_path else "архив не создан"
        content = f"Архив: {archive_name}\n"
        content += (
            "Шаблон обращения скопирован в буфер обмена."
            if result.copied_to_clipboard
            else "Шаблон не удалось скопировать в буфер обмена."
        )

        return LogsSupportFeedbackPlan(
            ok=True,
            status_text=" • ".join(status_parts) or "Подготовка завершена",
            status_tone="success",
            infobar_title="Поддержка подготовлена",
            infobar_content=content,
        )

    @staticmethod
    def build_support_error_feedback(error: str) -> LogsSupportFeedbackPlan:
        return LogsSupportFeedbackPlan(
            ok=False,
            status_text="Ошибка подготовки",
            status_tone="error",
            infobar_title="Ошибка",
            infobar_content=f"Не удалось подготовить обращение:\n{str(error or '')}",
        )

    @staticmethod
    def build_stats_text_plan(stats: LogsStatsState, *, language: str) -> LogsStatsTextPlan:
        from ui.text_catalog import tr as tr_catalog

        return LogsStatsTextPlan(
            text=tr_catalog(
                "page.logs.stats.template",
                language=language,
                default="📊 Логи: {logs} (макс {max_logs}) | 🔧 Debug: {debug} (макс {max_debug}) | 💾 Размер: {size:.2f} MB",
            ).format(
                logs=stats.app_logs,
                max_logs=stats.max_logs,
                debug=stats.debug_logs,
                max_debug=stats.max_debug_logs,
                size=stats.total_size_mb,
            )
        )

    @staticmethod
    def build_winws_output_plan(*, launch_method: str, orchestra_runner, language: str) -> LogsWinwsOutputPlan:
        source, runner = LogsPageController.get_running_runner_source(launch_method, orchestra_runner)

        if source == "orchestra" and runner:
            pid = LogsPageController.get_runner_pid(runner)
            return LogsWinwsOutputPlan(
                action="orchestra",
                status_kind="running",
                status_text=f"PID: {pid} | Оркестратор",
                process=None,
            )

        if source != "direct" or not runner:
            from ui.text_catalog import tr as tr_catalog

            return LogsWinwsOutputPlan(
                action="idle",
                status_kind="neutral",
                status_text=tr_catalog(
                    "page.logs.winws.status.not_running",
                    language=language,
                    default="Процесс не запущен",
                ),
                process=None,
            )

        process = runner.get_process()
        if not process:
            from ui.text_catalog import tr as tr_catalog

            return LogsWinwsOutputPlan(
                action="idle",
                status_kind="neutral",
                status_text=tr_catalog(
                    "page.logs.winws.status.not_running",
                    language=language,
                    default="Процесс не запущен",
                ),
                process=None,
            )

        strategy_info = {}
        try:
            get_info = getattr(runner, "get_current_strategy_info", None)
            if callable(get_info):
                info_value = get_info()
                if isinstance(info_value, dict):
                    strategy_info = info_value
        except Exception:
            pass

        strategy_name = strategy_info.get("name", "winws")
        if len(strategy_name) > 35:
            strategy_name = strategy_name[:32] + "..."
        pid = strategy_info.get("pid") or LogsPageController.get_runner_pid(runner)

        return LogsWinwsOutputPlan(
            action="start_worker",
            status_kind="running",
            status_text=f"PID: {pid} | {strategy_name}",
            process=process,
        )
