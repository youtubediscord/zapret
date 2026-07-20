import os
import sys
import traceback
import time
import logging
import threading
import atexit
from datetime import datetime
import glob
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

# NO Qt imports at module level!
# This file is imported very early (via log/__init__.py → crash_handler)
# BEFORE QApplication exists.

from config.config import MAX_LOG_FILES, MAX_DEBUG_LOG_FILES
from config.runtime_layout import APPLICATION_PATHS


LOGS_FOLDER = str(APPLICATION_PATHS.logs_dir)


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


@dataclass(frozen=True, slots=True)
class LiveLogSnapshot:
    """Согласованный снимок уже записанной части текущего журнала."""

    text: str
    last_sequence: int
    reset_required: bool


@dataclass(frozen=True, slots=True)
class _QueuedLogRecord:
    sequence: int
    text: str


class _AsyncLogStore:
    """Единственный владелец записи основного журнала и его живого снимка.

    Вызывающие потоки только кладут готовый текст в ограниченную очередь.
    Один фоновый поток держит файл открытым, объединяет всплески сообщений и
    после успешной записи публикует их подписчикам в том же порядке.
    """

    def __init__(
        self,
        log_file: str,
        header: str,
        *,
        max_pending_records: int = 8192,
        max_pending_chars: int = 8 * 1024 * 1024,
        max_history_chars: int = 2 * 1024 * 1024,
        batch_delay_seconds: float = 0.015,
    ) -> None:
        self.log_file = str(log_file)
        self._max_pending_records = max(64, int(max_pending_records))
        self._max_pending_chars = max(64 * 1024, int(max_pending_chars))
        self._max_history_chars = max(64 * 1024, int(max_history_chars))
        self._batch_delay_seconds = max(0.0, float(batch_delay_seconds))

        self._condition = threading.Condition()
        self._pending: deque[_QueuedLogRecord] = deque()
        self._pending_chars = 0
        self._history: deque[_QueuedLogRecord] = deque()
        self._history_chars = 0
        self._subscribers: dict[int, Callable[[int, str], None]] = {}
        self._next_subscriber_id = 1
        self._next_sequence = 1
        self._last_persisted_sequence = 0
        self._dropped_records = 0
        self._last_dropped_sequence = 0
        self._write_in_progress = False
        self._stopping = False
        self._stopped = False
        self._writer_error = ""

        # Заголовок создаётся синхронно: даже при очень раннем падении у нас
        # остаётся валидный файл текущей сессии. Обычные записи дальше асинхронны.
        with open(self.log_file, "w", encoding="utf-8-sig", newline="") as handle:
            handle.write(header)
            handle.flush()
        self._append_history_locked(_QueuedLogRecord(0, header))

        self._writer_thread = threading.Thread(
            target=self._writer_loop,
            name="app-log-writer",
            daemon=True,
        )
        self._writer_thread.start()

    def publish(self, text: str) -> int:
        payload = str(text or "")
        if not payload:
            return self._last_persisted_sequence

        if len(payload) > self._max_pending_chars:
            marker = "[... слишком большая запись сокращена ...]\n"
            payload = marker + payload[-(self._max_pending_chars - len(marker)) :]

        with self._condition:
            if self._stopping or self._stopped:
                return self._last_persisted_sequence

            sequence = self._next_sequence
            self._next_sequence += 1

            while self._pending and (
                len(self._pending) >= self._max_pending_records
                or self._pending_chars + len(payload) > self._max_pending_chars
            ):
                dropped = self._pending.popleft()
                self._pending_chars -= len(dropped.text)
                self._dropped_records += 1
                self._last_dropped_sequence = dropped.sequence

            self._pending.append(_QueuedLogRecord(sequence, payload))
            self._pending_chars += len(payload)
            self._condition.notify()
            return sequence

    def open_subscription(
        self,
        callback: Callable[[int, str], None],
        *,
        after_sequence: int | None,
        max_chars: int = 1024 * 1024,
    ) -> tuple[int, LiveLogSnapshot]:
        if not callable(callback):
            raise TypeError("callback must be callable")

        with self._condition:
            token = self._next_subscriber_id
            self._next_subscriber_id += 1
            self._subscribers[token] = callback
            snapshot = self._build_snapshot_locked(after_sequence, max_chars=max_chars)
            return token, snapshot

    def close_subscription(self, token: int | None) -> None:
        if token is None:
            return
        with self._condition:
            self._subscribers.pop(int(token), None)

    def snapshot(
        self,
        *,
        after_sequence: int | None = None,
        max_chars: int = 1024 * 1024,
    ) -> LiveLogSnapshot:
        with self._condition:
            return self._build_snapshot_locked(after_sequence, max_chars=max_chars)

    def flush_pending(self, timeout: float = 2.0) -> bool:
        deadline = time.monotonic() + max(0.0, float(timeout))
        with self._condition:
            self._condition.notify()
            while self._pending or self._write_in_progress:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(timeout=min(0.1, remaining))
            return not bool(self._writer_error)

    def shutdown(self, timeout: float = 3.0) -> None:
        with self._condition:
            if self._stopped:
                return
            self._stopping = True
            self._condition.notify_all()

        thread = self._writer_thread
        if thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=max(0.0, float(timeout)))

        with self._condition:
            self._stopped = not thread.is_alive()
            self._subscribers.clear()

    @property
    def pending_record_count(self) -> int:
        with self._condition:
            return len(self._pending)

    @property
    def history_char_count(self) -> int:
        with self._condition:
            return self._history_chars

    @property
    def writer_thread_alive(self) -> bool:
        return self._writer_thread.is_alive()

    def _build_snapshot_locked(self, after_sequence: int | None, *, max_chars: int) -> LiveLogSnapshot:
        records = list(self._history)
        last_sequence = self._last_persisted_sequence
        earliest_sequence = records[0].sequence if records else last_sequence
        requested_sequence = None if after_sequence is None else int(after_sequence)
        reset_required = (
            requested_sequence is None
            or requested_sequence > last_sequence
            or requested_sequence < earliest_sequence - 1
        )

        if reset_required:
            selected = records
        else:
            selected = [record for record in records if record.sequence > requested_sequence]

        char_limit = max(1024, int(max_chars))
        selected_chars = sum(len(record.text) for record in selected)
        if selected_chars > char_limit:
            reset_required = True
            kept: deque[_QueuedLogRecord] = deque()
            kept_chars = 0
            for record in reversed(records):
                if not kept and len(record.text) > char_limit:
                    marker = "[... начало снимка удалено ...]\n"
                    kept.appendleft(
                        _QueuedLogRecord(
                            record.sequence,
                            marker + record.text[-(char_limit - len(marker)) :],
                        )
                    )
                    kept_chars = char_limit
                    break
                if kept and kept_chars + len(record.text) > char_limit:
                    break
                kept.appendleft(record)
                kept_chars += len(record.text)
            selected = list(kept)

        return LiveLogSnapshot(
            text="".join(record.text for record in selected),
            last_sequence=last_sequence,
            reset_required=reset_required,
        )

    def _append_history_locked(self, record: _QueuedLogRecord) -> None:
        if len(record.text) > self._max_history_chars:
            marker = "[... начало большой записи удалено из памяти ...]\n"
            record = _QueuedLogRecord(
                record.sequence,
                marker + record.text[-(self._max_history_chars - len(marker)) :],
            )
        self._history.append(record)
        self._history_chars += len(record.text)
        while len(self._history) > 1 and self._history_chars > self._max_history_chars:
            removed = self._history.popleft()
            self._history_chars -= len(removed.text)
        self._last_persisted_sequence = max(self._last_persisted_sequence, record.sequence)

    def _take_batch(self) -> tuple[list[_QueuedLogRecord], int, int]:
        with self._condition:
            while not self._pending and not self._stopping:
                self._condition.wait()
            if not self._pending and self._stopping:
                return [], 0, 0

            if not self._stopping and self._batch_delay_seconds:
                self._condition.wait(timeout=self._batch_delay_seconds)

            batch = list(self._pending)
            self._pending.clear()
            self._pending_chars = 0
            dropped_count = self._dropped_records
            dropped_sequence = self._last_dropped_sequence
            self._dropped_records = 0
            self._last_dropped_sequence = 0
            self._write_in_progress = True
            return batch, dropped_count, dropped_sequence

    def _writer_loop(self) -> None:
        try:
            # Файл уже содержит BOM и заголовок. Здесь нужен обычный utf-8,
            # иначе повторное открытие utf-8-sig может вставлять BOM в середину.
            with open(self.log_file, "a", encoding="utf-8", buffering=256 * 1024, newline="") as handle:
                while True:
                    batch, dropped_count, dropped_sequence = self._take_batch()
                    if not batch:
                        with self._condition:
                            self._write_in_progress = False
                            self._condition.notify_all()
                        if self._stopping:
                            break
                        continue

                    persisted: list[_QueuedLogRecord] = []
                    if dropped_count:
                        marker = _QueuedLogRecord(
                            dropped_sequence,
                            f"[{datetime.now():%H:%M:%S}] [WARNING] "
                            f"Пропущено сообщений из-за переполнения очереди: {dropped_count}\n",
                        )
                        persisted.append(marker)
                    persisted.extend(batch)

                    handle.write("".join(record.text for record in persisted))
                    handle.flush()

                    with self._condition:
                        for record in persisted:
                            self._append_history_locked(record)
                        subscribers = list(self._subscribers.items())
                        self._write_in_progress = False
                        self._condition.notify_all()

                    failed_tokens: set[int] = set()
                    published_text = "".join(record.text for record in persisted)
                    published_sequence = persisted[-1].sequence
                    for token, callback in subscribers:
                        try:
                            callback(published_sequence, published_text)
                        except Exception:
                            failed_tokens.add(token)
                    if failed_tokens:
                        with self._condition:
                            for token in failed_tokens:
                                self._subscribers.pop(token, None)
        except Exception as exc:
            with self._condition:
                self._writer_error = str(exc)
                self._pending.clear()
                self._pending_chars = 0
                self._write_in_progress = False
                self._stopped = True
                self._condition.notify_all()
        finally:
            with self._condition:
                self._write_in_progress = False
                self._stopped = True
                self._condition.notify_all()

class Logger:
    """Лёгкий фасад: форматирует сообщения и отдаёт их единому хранилищу."""

    def __init__(self, log_file_path=None, *, redirect_stdio: bool | None = None, run_cleanup: bool = True):

        self.verbose_logging = _is_verbose_logging_enabled()

        # Используем глобальную переменную LOG_FILE если не передан путь
        self.log_file = log_file_path or LOG_FILE

        # Создаем папку для логов если её нет
        log_dir = os.path.dirname(self.log_file)
        os.makedirs(log_dir, exist_ok=True)

        if run_cleanup:
            cleanup_old_logs(log_dir, MAX_LOG_FILES)

        header = (
            f"=== Zapret 2 GUI Log - Started {datetime.now():%Y-%m-%d %H:%M:%S} ===\n"
            f"Log file: {os.path.basename(self.log_file)}\n"
            f"Total log files in folder: {len(glob.glob(os.path.join(log_dir, 'zapret_log_*.txt')))}\n"
            f"{'=' * 60}\n\n"
        )
        self._store = _AsyncLogStore(self.log_file, header)

        self.orig_stdout = sys.stdout
        self.orig_stderr = sys.stderr
        self._ui_error_notifier = None
        self._ui_error_last_signature = ""
        self._ui_error_last_ts = 0.0
        self._stream_line_buffer = ""
        self._traceback_capture = False
        self._traceback_lines = []
        self._capture_lock = threading.Lock()
        self._capture_buffers: dict[int, str] = {}
        self._scan_lock = threading.Lock()
        if redirect_stdio is None:
            redirect_stdio = os.environ.get("ZAPRET_DISABLE_STDIO_REDIRECT") != "1"
        self._redirect_stdio = bool(redirect_stdio)
        if self._redirect_stdio:
            sys.stdout = sys.stderr = self

    # --- redirect interface ---------------------------------------------------
    def write(self, message: str):
        message = str(message or "")
        if not message:
            return 0
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
        with self._scan_lock:
            self._scan_stream_for_unhandled_exception(message)

        thread_id = threading.get_ident()
        with self._capture_lock:
            combined = self._capture_buffers.get(thread_id, "") + message
            parts = combined.splitlines(keepends=True)
            complete: list[str] = []
            remainder = ""
            for part in parts:
                if part.endswith(("\n", "\r")):
                    complete.append(part)
                else:
                    remainder += part
            if remainder:
                if len(remainder) > 65536:
                    complete.append(remainder + "\n")
                    self._capture_buffers.pop(thread_id, None)
                else:
                    if thread_id not in self._capture_buffers and len(self._capture_buffers) >= 128:
                        oldest_thread_id = next(iter(self._capture_buffers))
                        oldest_text = self._capture_buffers.pop(oldest_thread_id, "")
                        if oldest_text:
                            complete.append(oldest_text + "\n")
                    self._capture_buffers[thread_id] = remainder
            else:
                self._capture_buffers.pop(thread_id, None)

        if complete:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self._store.publish("".join(f"[{timestamp}] {part}" for part in complete))
        return len(message)

    def flush(self):
        thread_id = threading.get_ident()
        with self._capture_lock:
            pending_text = self._capture_buffers.pop(thread_id, "")
        if pending_text:
            self._store.publish(f"[{datetime.now():%H:%M:%S}] {pending_text}\n")
        if self.orig_stdout:
            try:
                self.orig_stdout.flush()
            except Exception:
                pass

    @property
    def encoding(self):
        return getattr(self.orig_stdout, "encoding", None) or "utf-8"

    @property
    def errors(self):
        return getattr(self.orig_stdout, "errors", None) or "replace"

    def isatty(self) -> bool:
        try:
            return bool(self.orig_stdout and self.orig_stdout.isatty())
        except Exception:
            return False

    def fileno(self):
        if self.orig_stdout and hasattr(self.orig_stdout, "fileno"):
            return self.orig_stdout.fileno()
        raise OSError("redirected log stream has no file descriptor")

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
        self._store.publish(f"[{datetime.now():%H:%M:%S}] {prefix} {message}\n")
        if self._should_notify_ui_error(level):
            self._notify_ui_error(str(message), str(level))

    def log_exception(self, e, context=""):
        """Log an exception with its traceback"""
        try:
            tb = traceback.format_exc()
            msg = f"Exception in {context}: {str(e)}" if context else str(e)
            self._store.publish(f"[{datetime.now():%H:%M:%S}] [ERROR] {msg}\n{tb}\n")
            self._notify_ui_error(msg, "ERROR")
        except Exception:
            self._notify_ui_error(str(e), "ERROR")

    def get_log_content(self) -> str:
        try:
            self.flush_pending()
            with open(self.log_file, "r", encoding="utf-8-sig") as f:
                return f.read()
        except Exception as e:
            return f"Error reading log: {e}"

    def open_live_subscription(
        self,
        callback: Callable[[int, str], None],
        *,
        after_sequence: int | None = None,
        max_chars: int = 1024 * 1024,
    ) -> tuple[int, LiveLogSnapshot]:
        return self._store.open_subscription(
            callback,
            after_sequence=after_sequence,
            max_chars=max_chars,
        )

    def close_live_subscription(self, token: int | None) -> None:
        self._store.close_subscription(token)

    def get_live_snapshot(
        self,
        *,
        after_sequence: int | None = None,
        max_chars: int = 1024 * 1024,
    ) -> LiveLogSnapshot:
        return self._store.snapshot(after_sequence=after_sequence, max_chars=max_chars)

    def flush_pending(self, timeout: float = 2.0) -> bool:
        return self._store.flush_pending(timeout=timeout)

    def shutdown(self, timeout: float = 3.0) -> None:
        # Дозаписываем незавершённый print() текущего потока перед остановкой.
        with self._capture_lock:
            pending_parts = list(self._capture_buffers.values())
            self._capture_buffers.clear()
        for pending_text in pending_parts:
            if pending_text:
                self._store.publish(f"[{datetime.now():%H:%M:%S}] {pending_text}\n")
        self._store.shutdown(timeout=timeout)
        if self._redirect_stdio:
            if sys.stdout is self:
                sys.stdout = self.orig_stdout
            if sys.stderr is self:
                sys.stderr = self.orig_stderr

    @property
    def pending_record_count(self) -> int:
        return self._store.pending_record_count

    @property
    def history_char_count(self) -> int:
        return self._store.history_char_count

    @property
    def writer_thread_alive(self) -> bool:
        return self._store.writer_thread_alive

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
        def open_live_subscription(self, *_a, **_kw):
            return None, LiveLogSnapshot("", 0, True)
        def close_live_subscription(self, *_a, **_kw): pass
        def get_live_snapshot(self, *_a, **_kw): return LiveLogSnapshot("", 0, True)
        def flush_pending(self, *_a, **_kw): return False
        def shutdown(self, *_a, **_kw): pass
    global_logger = _FallbackLogger()


class _ApplicationLoggingHandler(logging.Handler):
    """Направляет стандартный logging в тот же основной журнал."""

    _zapret_application_handler = True

    def emit(self, record: logging.LogRecord) -> None:
        try:
            global_logger.log(self.format(record), record.levelname, record.name)
        except Exception:
            pass


def _install_standard_logging_bridge() -> None:
    root = logging.getLogger()
    if any(getattr(handler, "_zapret_application_handler", False) for handler in root.handlers):
        return
    handler = _ApplicationLoggingHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(handler)
    # В обычном режиме не повышаем шум стандартных библиотек: раньше корневой
    # logging тоже пропускал только WARNING и выше. Подробности включаются явно.
    root.setLevel(logging.DEBUG if is_verbose_logging_enabled() else logging.WARNING)


def log(msg, level="INFO", component=None):
    global_logger.log(msg, level, component)


def is_verbose_logging_enabled() -> bool:
    try:
        return bool(global_logger.is_verbose_logging_enabled())
    except Exception:
        return _is_verbose_logging_enabled()


_install_standard_logging_bridge()
atexit.register(global_logger.shutdown)


def log_exception(e, context=""):
    global_logger.log_exception(e, context)

def get_log_content():
    return global_logger.get_log_content()
