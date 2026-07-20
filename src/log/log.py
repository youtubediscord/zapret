import os
import sys
import traceback
import time
from datetime import datetime
import glob

# NO Qt imports at module level!
# This file is imported very early (via log/__init__.py → crash_handler)
# BEFORE QApplication exists.

from config.config import LOGS_FOLDER, MAX_LOG_FILES, MAX_DEBUG_LOG_FILES


MAX_BLOCKCHECK_LOG_FILES = 200


_VERBOSE_LOG_ENV = "ZAPRET_GUI_VERBOSE_LOGS"
_VERBOSE_LOG_FLAGS = {"--verbose-log", "--debug-log", "--diag-log"}


def _is_truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _is_verbose_logging_enabled() -> bool:
    """Returns True when DEBUG/DIAG logs should be persisted."""
    env_value = os.environ.get(_VERBOSE_LOG_ENV)
    if env_value is not None and str(env_value).strip() != "":
        return _is_truthy(env_value)

    for arg in sys.argv[1:]:
        if str(arg).strip().lower() in _VERBOSE_LOG_FLAGS:
            return True

    return False

def get_current_log_filename():
    """Генерирует имя файла лога с текущей датой и временем"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"zapret_log_{timestamp}.txt"


def _cleanup_files_by_pattern(logs_folder: str, pattern: str, max_files: int) -> tuple:
    """
    Удаляет старые файлы по паттерну, оставляя только последние max_files.

    Returns:
        (deleted_count, errors, total_found)
    """
    deleted_count = 0
    errors = []
    total_found = 0

    try:
        files = glob.glob(os.path.join(logs_folder, pattern))
        total_found = len(files)

        if total_found > max_files:
            # Сортируем по времени модификации (старые первые)
            files.sort(key=os.path.getmtime)
            files_to_delete = files[:total_found - max_files]

            for old_file in files_to_delete:
                try:
                    os.remove(old_file)
                    deleted_count += 1
                except Exception as e:
                    errors.append(f"{os.path.basename(old_file)}: {e}")
    except Exception as e:
        errors.append(f"Glob error ({pattern}): {e}")

    return deleted_count, errors, total_found


def cleanup_old_logs(logs_folder, max_files=MAX_LOG_FILES):
    """
    Удаляет старые лог файлы с раздельными лимитами для каждого типа:
    - zapret_log_*.txt: max_files (по умолчанию 50)
    - zapret_winws2_debug_*.log: MAX_DEBUG_LOG_FILES (20)
    - zapret_[0-9]*.log: старый формат, включается в общий лимит
    - blockcheck_run_*.log: отдельная история запусков BlockCheck
    """
    total_deleted = 0
    all_errors = []
    total_found = 0

    # 1. Основные логи приложения (zapret_log_*.txt) - макс 50
    d, e, t = _cleanup_files_by_pattern(logs_folder, "zapret_log_*.txt", max_files)
    total_deleted += d
    all_errors.extend(e)
    total_found += t

    # 2. Debug логи winws2 (zapret_winws2_debug_*.log) - макс 20
    d, e, t = _cleanup_files_by_pattern(logs_folder, "zapret_winws2_debug_*.log", MAX_DEBUG_LOG_FILES)
    total_deleted += d
    all_errors.extend(e)
    total_found += t

    # 3. Старый формат логов (zapret_[0-9]*.log) - удаляем все старые
    d, e, t = _cleanup_files_by_pattern(logs_folder, "zapret_[0-9]*.log", 10)
    total_deleted += d
    all_errors.extend(e)
    total_found += t

    # 4. История запусков BlockCheck
    d, e, t = _cleanup_files_by_pattern(logs_folder, "blockcheck_run_*.log", MAX_BLOCKCHECK_LOG_FILES)
    total_deleted += d
    all_errors.extend(e)
    total_found += t

    return total_deleted, all_errors, total_found

# Создаем уникальное имя для текущей сессии
CURRENT_LOG_FILENAME = get_current_log_filename()
LOG_FILE = os.path.join(LOGS_FOLDER, CURRENT_LOG_FILENAME)

class Logger:
    """Simple logging system that captures console output and errors to a file"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, log_file_path=None):
        if self._initialized:
            return
        self._initialized = True

        self.verbose_logging = _is_verbose_logging_enabled()

        from config.config import LOGS_FOLDER


        # Используем глобальную переменную LOG_FILE если не передан путь
        self.log_file = log_file_path or LOG_FILE

        # Создаем папку для логов если её нет
        log_dir = os.path.dirname(self.log_file)
        os.makedirs(log_dir, exist_ok=True)

        # Очищаем старые логи
        cleanup_old_logs(log_dir, MAX_LOG_FILES)

        # Создаем новый лог файл для текущей сессии
        with open(self.log_file, "w", encoding="utf-8-sig") as f:
            f.write(f"=== Zapret 2 GUI Log - Started {datetime.now():%Y-%m-%d %H:%M:%S} ===\n")
            f.write(f"Log file: {os.path.basename(self.log_file)}\n")
            f.write(f"Total log files in folder: {len(glob.glob(os.path.join(log_dir, 'zapret_log_*.txt')))}\n")
            f.write("="*60 + "\n\n")

        self.orig_stdout = sys.stdout
        self.orig_stderr = sys.stderr
        self._ui_error_notifier = None
        self._ui_error_last_signature = ""
        self._ui_error_last_ts = 0.0
        self._stream_line_buffer = ""
        self._traceback_capture = False
        self._traceback_lines = []
        if os.environ.get("ZAPRET_DISABLE_STDIO_REDIRECT") != "1":
            sys.stdout = sys.stderr = self

    # --- redirect interface ---------------------------------------------------
    def write(self, message: str):
        if self.orig_stdout:
            try:
                self.orig_stdout.write(message)
            except UnicodeEncodeError:
                enc = getattr(self.orig_stdout, "encoding", None) or "utf-8"
                try:
                    safe = message.encode(enc, errors="replace").decode(enc, errors="replace")
                except Exception:
                    safe = message.encode("ascii", errors="replace").decode("ascii", errors="replace")
                try:
                    self.orig_stdout.write(safe)
                except Exception:
                    pass
        with open(self.log_file, "a", encoding="utf-8-sig") as f:
            f.write(f"[{datetime.now():%H:%M:%S}] {message}")

        self._scan_stream_for_unhandled_exception(message)

    def flush(self):
        if self.orig_stdout:
            self.orig_stdout.flush()

    # --- helper API -----------------------------------------------------------
    def is_verbose_logging_enabled(self) -> bool:
        return bool(getattr(self, "verbose_logging", False))

    def _should_emit_level(self, level: str) -> bool:
        if self.is_verbose_logging_enabled():
            return True
        normalized = str(level).strip().upper()
        return normalized not in {"DEBUG", "🔍 DIAG"}

    def _should_notify_ui_error(self, level: str) -> bool:
        normalized = str(level or "").strip().upper()
        if not normalized:
            return False
        return (
            "ERROR" in normalized
            or "CRITICAL" in normalized
            or "ОШИБ" in normalized
            or "КРИТ" in normalized
        )

    def set_ui_error_notifier(self, callback) -> None:
        """Registers callback used to show top UI error notifications."""
        self._ui_error_notifier = callback if callable(callback) else None

    def _notify_ui_error(self, message: str, level: str) -> None:
        notifier = self._ui_error_notifier
        if not notifier:
            return

        text = str(message or "").strip()
        if not text:
            return

        signature = " ".join(text.split()).lower()
        now_ts = time.time()
        if signature and signature == self._ui_error_last_signature and (now_ts - self._ui_error_last_ts) < 2.0:
            return

        self._ui_error_last_signature = signature
        self._ui_error_last_ts = now_ts

        level_text = str(level or "").strip()
        payload = f"[{level_text}] {text}" if level_text else text

        try:
            notifier(payload)
        except Exception:
            pass

    def _is_exception_summary_line(self, line: str) -> bool:
        text = str(line or "").strip()
        if not text or ":" not in text:
            return False

        head = text.split(":", 1)[0].strip().lower()
        if not head:
            return False

        return (
            head.endswith("error")
            or head.endswith("exception")
            or head.endswith("interrupt")
            or head in {"systemexit", "keyboardinterrupt"}
        )

    def _flush_captured_traceback(self, summary_line: str = "") -> None:
        summary = str(summary_line or "").strip()
        if not summary and self._traceback_lines:
            for line in reversed(self._traceback_lines):
                if self._is_exception_summary_line(line):
                    summary = line.strip()
                    break

        if summary:
            self._notify_ui_error(f"Необработанное исключение: {summary}", "ERROR")

        self._traceback_capture = False
        self._traceback_lines = []

    def _process_stream_line(self, line: str) -> None:
        text = str(line or "").rstrip("\r")
        stripped = text.strip()

        if not stripped:
            return

        if stripped.startswith("Traceback (most recent call last):"):
            self._traceback_capture = True
            self._traceback_lines = [stripped]
            return

        if self._traceback_capture:
            self._traceback_lines.append(stripped)
            if self._is_exception_summary_line(stripped):
                self._flush_captured_traceback(stripped)
                return

            if len(self._traceback_lines) >= 100:
                self._flush_captured_traceback()
                return

        lower = stripped.lower()
        if lower.startswith("fatal python error:"):
            self._notify_ui_error(stripped, "CRITICAL")

    def _scan_stream_for_unhandled_exception(self, message: str) -> None:
        # Нужен только когда есть UI notifier.
        if not self._ui_error_notifier:
            return

        chunk = str(message or "")
        if not chunk:
            return

        self._stream_line_buffer += chunk
        if len(self._stream_line_buffer) > 65536:
            self._stream_line_buffer = self._stream_line_buffer[-32768:]

        while "\n" in self._stream_line_buffer:
            line, self._stream_line_buffer = self._stream_line_buffer.split("\n", 1)
            self._process_stream_line(line)

    def log(self, message, level="INFO", component=None):
        if not self._should_emit_level(level):
            return
        prefix = f"[{component}][{level}]" if component else f"[{level}]"
        self.write(f"{prefix} {message}\n")
        if self._should_notify_ui_error(level):
            self._notify_ui_error(str(message), str(level))

    def log_exception(self, e, context=""):
        """Log an exception with its traceback"""
        try:
            tb = traceback.format_exc()
            msg = f"Exception in {context}: {str(e)}" if context else str(e)
            self.write(f"[ERROR] {msg}\n{tb}\n")
            self._notify_ui_error(msg, "ERROR")
        except Exception:
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    f.write(f"[{timestamp}] [ERROR] Exception in {context}: {str(e)}\n")
                    f.write(f"[{timestamp}] {traceback.format_exc()}\n")
                self._notify_ui_error(str(e), "ERROR")
            except Exception:
                pass

    def get_log_content(self) -> str:
        try:
            with open(self.log_file, "r", encoding="utf-8-sig") as f:
                return f.read()
        except Exception as e:
            return f"Error reading log: {e}"

# ───────────────────────────────────────────────────────────────
# 3.  GLOBAL LOGGER + HELPERS
# ───────────────────────────────────────────────────────────────
try:
    global_logger = Logger()
except Exception:
    class _FallbackLogger:
        def log(self, *_a, **_kw): pass
        def log_exception(self, *_a, **_kw): pass
        def set_ui_error_notifier(self, *_a, **_kw): pass
        def is_verbose_logging_enabled(self): return False
        def get_log_content(self): return "Logging system initialization failed."
    global_logger = _FallbackLogger()

def log(msg, level="INFO", component=None):
    global_logger.log(msg, level, component)


def is_verbose_logging_enabled() -> bool:
    try:
        return bool(global_logger.is_verbose_logging_enabled())
    except Exception:
        return _is_verbose_logging_enabled()


def log_exception(e, context=""):
    global_logger.log_exception(e, context)

def get_log_content():
    return global_logger.get_log_content()
