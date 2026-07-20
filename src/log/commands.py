from __future__ import annotations

import glob
import os
import subprocess
import threading
import time
from dataclasses import dataclass

from config.config import MAX_DEBUG_LOG_FILES, MAX_LOG_FILES
from config.runtime_layout import APPLICATION_PATHS
from log.log import LOG_FILE, cleanup_old_logs, global_logger, log
from app.performance_metrics import log_ui_timing_since

from support_request_bundle import prepare_support_request


LOGS_FOLDER = str(APPLICATION_PATHS.logs_dir)


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
class LogsPageDataState:
    logs_state: LogsListState
    stats_state: LogsStatsState


@dataclass(slots=True)
class LogsTailStartPlan:
    should_start: bool
    info_text: str
    file_path: str
    should_clear_view: bool = True
    initial_max_bytes: int | None = 1024 * 1024
    file_signature: tuple[str, int, int] | None = None


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


_warmed_page_data_lock = threading.Lock()
_warmed_page_data_cache: LogsPageDataState | None = None


def store_warmed_page_data(state: LogsPageDataState) -> None:
    global _warmed_page_data_cache
    with _warmed_page_data_lock:
        _warmed_page_data_cache = state


def clear_warmed_page_data_cache() -> None:
    global _warmed_page_data_cache
    with _warmed_page_data_lock:
        _warmed_page_data_cache = None


def consume_warmed_page_data() -> LogsPageDataState | None:
    global _warmed_page_data_cache
    with _warmed_page_data_lock:
        state = _warmed_page_data_cache
        _warmed_page_data_cache = None
        return state


def get_current_log_file() -> str:
    return getattr(global_logger, "log_file", LOG_FILE)

def list_logs(*, run_cleanup: bool) -> LogsListState:
    total_started_at = time.perf_counter()
    cleanup_deleted = 0
    cleanup_errors: list[str] = []
    cleanup_total = 0

    if run_cleanup:
        cleanup_started_at = time.perf_counter()
        cleanup_deleted, cleanup_errors, cleanup_total = cleanup_old_logs(LOGS_FOLDER, MAX_LOG_FILES)
        _log_timing("logs_feature.list_logs.cleanup", cleanup_started_at)

    glob_started_at = time.perf_counter()
    log_files: list[str] = []
    log_files.extend(glob.glob(os.path.join(LOGS_FOLDER, "zapret_log_*.txt")))
    log_files.extend(glob.glob(os.path.join(LOGS_FOLDER, "zapret_[0-9]*.log")))
    log_files.extend(glob.glob(os.path.join(LOGS_FOLDER, "blockcheck_run_*.log")))
    _log_timing("logs_feature.list_logs.glob", glob_started_at)

    sort_started_at = time.perf_counter()
    log_files.sort(key=os.path.getmtime, reverse=True)
    _log_timing("logs_feature.list_logs.sort", sort_started_at)

    current_log = get_current_log_file()
    entries: list[dict] = []
    entries_started_at = time.perf_counter()
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
    _log_timing("logs_feature.list_logs.entries.build", entries_started_at)
    _log_timing("logs_feature.list_logs.total", total_started_at)

    return LogsListState(
        entries=entries,
        current_log_file=current_log,
        cleanup_deleted=cleanup_deleted,
        cleanup_errors=cleanup_errors,
        cleanup_total=cleanup_total,
    )

def build_stats() -> LogsStatsState:
    total_started_at = time.perf_counter()
    glob_started_at = time.perf_counter()
    app_logs = glob.glob(os.path.join(LOGS_FOLDER, "zapret_log_*.txt"))
    app_logs.extend(glob.glob(os.path.join(LOGS_FOLDER, "zapret_[0-9]*.log")))
    app_logs.extend(glob.glob(os.path.join(LOGS_FOLDER, "blockcheck_run_*.log")))
    debug_logs = glob.glob(os.path.join(LOGS_FOLDER, "zapret_winws2_debug_*.log"))
    all_files = app_logs + debug_logs
    _log_timing("logs_feature.build_stats.glob", glob_started_at)
    size_started_at = time.perf_counter()
    total_size = sum(os.path.getsize(path) for path in all_files) / 1024 / 1024
    _log_timing("logs_feature.build_stats.size", size_started_at)
    _log_timing("logs_feature.build_stats.total", total_started_at)
    return LogsStatsState(
        app_logs=len(app_logs),
        debug_logs=len(debug_logs),
        total_size_mb=total_size,
        max_logs=MAX_LOG_FILES,
        max_debug_logs=MAX_DEBUG_LOG_FILES,
    )


def warm_page_data_cache(*, run_cleanup: bool = False) -> LogsPageDataState:
    state = LogsPageDataState(
        logs_state=list_logs(run_cleanup=run_cleanup),
        stats_state=build_stats(),
    )
    store_warmed_page_data(state)
    return state


def _log_timing(label: str, started_at: float) -> None:
    log_ui_timing_since("feature", "logs", label, started_at)

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

def prepare_support_bundle(*, current_log_file: str, orchestra_runner):
    candidate_paths = [
        current_log_file,
        get_current_log_file(),
        get_orchestra_log_path(orchestra_runner),
    ]
    return prepare_support_request(
        bundle_prefix="support_logs",
        context_label="Логи приложения",
        candidate_paths=candidate_paths,
        recent_patterns=("zapret_winws2_debug_*.log", "blockcheck_run_*.log"),
        extra_note="Если проблема связана с оркестратором, в архив по возможности добавлен и его свежий лог.",
    )

def open_logs_folder() -> None:
    subprocess.run(["explorer", LOGS_FOLDER], check=False)

def create_log_tail_worker(file_path: str, *, initial_max_bytes: int | None = 1024 * 1024):
    from log_tail import LogTailWorker

    return LogTailWorker(
        file_path,
        poll_interval=0.6,
        initial_chunk_chars=65536,
        initial_max_bytes=initial_max_bytes,
    )

def create_logs_overview_worker(*, run_cleanup: bool):
    from log.overview_worker import LogsOverviewWorker

    return LogsOverviewWorker(
        list_logs_fn=list_logs,
        build_stats_fn=build_stats,
        run_cleanup=run_cleanup,
    )

def _log_file_signature(file_path: str) -> tuple[str, int, int] | None:
    try:
        stat = os.stat(file_path)
        return (os.path.abspath(file_path), int(stat.st_size), int(stat.st_mtime_ns))
    except Exception:
        return None


def build_tail_start_plan(
    *,
    current_log_file: str,
    previous_signature: tuple[str, int, int] | None = None,
) -> LogsTailStartPlan:
    file_path = str(current_log_file or "").strip()
    if not file_path or not os.path.exists(file_path):
        return LogsTailStartPlan(
            should_start=False,
            info_text="",
            file_path=file_path,
            should_clear_view=False,
            initial_max_bytes=None,
            file_signature=None,
        )
    file_signature = _log_file_signature(file_path)
    is_same_file_content = bool(file_signature and file_signature == previous_signature)
    return LogsTailStartPlan(
        should_start=True,
        info_text=f"📄 {os.path.basename(file_path)}",
        file_path=file_path,
        should_clear_view=not is_same_file_content,
        initial_max_bytes=0 if is_same_file_content else 1024 * 1024,
        file_signature=file_signature,
    )

def build_support_feedback(result) -> LogsSupportFeedbackPlan:
    archive_paths = list(getattr(result, "archive_paths", None) or ([result.zip_path] if result.zip_path else []))
    status_parts: list[str] = []
    if archive_paths:
        status_parts.append("ZIP готовы" if len(archive_paths) > 1 else "ZIP готов")
    if result.copied_to_clipboard:
        status_parts.append("шаблон скопирован")
    if result.discussions_opened:
        status_parts.append("GitHub открыт")
    if result.bundle_folder_opened:
        status_parts.append("папка открыта")

    if archive_paths:
        archive_names = "\n".join(f"- {os.path.basename(path)}" for path in archive_paths)
        content = f"Архивы:\n{archive_names}\n"
    else:
        content = "Архив: архив не создан\n"
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

def build_support_error_feedback(error: str) -> LogsSupportFeedbackPlan:
    return LogsSupportFeedbackPlan(
        ok=False,
        status_text="Ошибка подготовки",
        status_tone="error",
        infobar_title="Ошибка",
        infobar_content=f"Не удалось подготовить обращение:\n{str(error or '')}",
    )

def build_stats_text_plan(stats: LogsStatsState, *, language: str) -> LogsStatsTextPlan:
    from app.ui_texts import tr as tr_catalog

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
