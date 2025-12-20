import os
import sys
import traceback
from datetime import datetime
import glob

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import QThread
from PyQt6.QtCore import Qt

from log_tail import LogTailWorker

from config import LOGS_FOLDER, MAX_LOG_FILES, MAX_DEBUG_LOG_FILES

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

        base_dir = os.path.dirname(
            os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)
        )
        from config import LOGS_FOLDER
        
        # Используем глобальную переменную LOG_FILE если не передан путь
        self.log_file = log_file_path or LOG_FILE
        
        # Создаем папку для логов если её нет
        log_dir = os.path.dirname(self.log_file)
        os.makedirs(log_dir, exist_ok=True)
        
        # Очищаем старые логи
        cleanup_old_logs(log_dir, MAX_LOG_FILES)  # Результат игнорируется при инициализации
        
        # Создаем новый лог файл для текущей сессии
        with open(self.log_file, "w", encoding="utf-8-sig") as f:
            f.write(f"=== Zapret 2 GUI Log - Started {datetime.now():%Y-%m-%d %H:%M:%S} ===\n")
            f.write(f"Log file: {os.path.basename(self.log_file)}\n")
            f.write(f"Total log files in folder: {len(glob.glob(os.path.join(log_dir, 'zapret_log_*.txt')))}\n")
            f.write("="*60 + "\n\n")

        self.orig_stdout = sys.stdout
        self.orig_stderr = sys.stderr
        sys.stdout = sys.stderr = self           # перенаправляем
    
    # --- redirect interface ---------------------------------------------------
    def write(self, message: str):
        if self.orig_stdout:
            self.orig_stdout.write(message)
        with open(self.log_file, "a", encoding="utf-8-sig") as f:
            f.write(f"[{datetime.now():%H:%M:%S}] {message}")

    def flush(self):                              # нужен для print(...)
        if self.orig_stdout:
            self.orig_stdout.flush()
    
    # --- helper API -----------------------------------------------------------
    def log(self, message, level="INFO", component=None):
        prefix = f"[{component}][{level}]" if component else f"[{level}]"
        self.write(f"{prefix} {message}\n")

    def log_exception(self, e, context=""):
        tb = traceback.format_exc()
        self.write(f"[ERROR] Exception in {context}: {e}\n{tb}\n")

    def get_log_content(self) -> str:
        try:
            with open(self.log_file, "r", encoding="utf-8-sig") as f:
                return f.read()
        except Exception as e:
            return f"Error reading log: {e}"
    
    def log_exception(self, e, context=""):
        """Log an exception with its traceback"""
        try:
            tb = traceback.format_exc()
            self.write(f"[ERROR] Exception in {context}: {str(e)}\n{tb}\n")
        except Exception:
            # Last resort - direct write
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    f.write(f"[{timestamp}] [ERROR] Exception in {context}: {str(e)}\n")
                    f.write(f"[{timestamp}] {traceback.format_exc()}\n")
            except Exception:
                pass
    
    def get_log_content(self):
        """Return the content of the log file"""
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading log: {str(e)}"
    
    def get_all_logs(self):
        """Возвращает список всех лог файлов с информацией"""
        try:
            log_dir = os.path.dirname(self.log_file)
            log_pattern = os.path.join(log_dir, "zapret_log_*.txt")
            log_files = glob.glob(log_pattern)
            
            logs_info = []
            for log_path in log_files:
                stat = os.stat(log_path)
                logs_info.append({
                    'path': log_path,
                    'name': os.path.basename(log_path),
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime),
                    'is_current': log_path == self.log_file
                })
            
            # Сортируем по дате модификации (новые первые)
            logs_info.sort(key=lambda x: x['modified'], reverse=True)
            return logs_info
            
        except Exception as e:
            print(f"Ошибка при получении списка логов: {e}")
            return []

class LogViewerDialog(QDialog):
    """
    Просмотр лог-файла в реальном времени
    (работает и если файл переписывается другим потоком).
    """

    def __init__(self, parent=None, log_file=None):
        super().__init__(parent)
        self.setWindowTitle("Zapret Logs (live)")
        self.setMinimumSize(800, 600)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        # Используем текущий лог файл если не передан другой
        self.current_log_file = log_file or getattr(global_logger, "log_file", LOG_FILE)

        # ---------- UI ----------
        layout = QVBoxLayout(self)

        # Информация о текущем лог файле
        from PyQt6.QtWidgets import QLabel
        self.log_info_label = QLabel(f"Текущий лог: {os.path.basename(self.current_log_file)}")
        layout.addWidget(self.log_info_label)

        self.log_text = QTextEdit(readOnly=True)
        self.log_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.log_text.setFont(QFont("Courier New", 9))
        layout.addWidget(self.log_text)

        btn_layout = QHBoxLayout()
        
        # Кнопки для работы с логами
        btn_copy   = QPushButton("Копировать", clicked=self.copy_all)
        btn_clear  = QPushButton("Очистить вид", clicked=self.log_text.clear)
        btn_open_folder = QPushButton("Открыть папку", clicked=self.open_logs_folder)
        btn_select_log = QPushButton("Выбрать лог", clicked=self.select_log_file)
        btn_close  = QPushButton("Закрыть", clicked=self.close)
        
        btn_layout.addWidget(btn_copy)
        btn_layout.addWidget(btn_clear)
        btn_layout.addWidget(btn_open_folder)
        btn_layout.addWidget(btn_select_log)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        # Добавляем статистику
        from PyQt6.QtWidgets import QLabel
        self.stats_label = QLabel()
        self.update_stats()
        layout.addWidget(self.stats_label)

        # ---------- Tail worker ----------
        self.start_tail_worker(self.current_log_file)

    def start_tail_worker(self, log_file):
        """Запускает или перезапускает worker для отслеживания лог файла"""
        # Останавливаем предыдущий worker если есть
        if hasattr(self, '_worker') and self._worker:
            self._worker.stop()
        if hasattr(self, '_thread') and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()
            
        # Очищаем текстовое поле
        self.log_text.clear()
        
        # Обновляем информацию
        self.log_info_label.setText(f"Текущий лог: {os.path.basename(log_file)}")
        self.current_log_file = log_file
        
        # Создаем новый worker
        self._thread = QThread(self)
        self._worker = LogTailWorker(log_file)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.new_lines.connect(self._append_text)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def update_stats(self):
        """Обновляет статистику по лог файлам"""
        try:
            if hasattr(global_logger, 'get_all_logs'):
                logs = global_logger.get_all_logs()
                total_size = sum(log['size'] for log in logs) / 1024 / 1024  # в MB
                self.stats_label.setText(
                    f"Всего логов: {len(logs)} | "
                    f"Общий размер: {total_size:.2f} MB | "
                    f"Максимум файлов: {MAX_LOG_FILES}"
                )
            else:
                self.stats_label.setText("Статистика недоступна")
        except Exception:
            self.stats_label.setText("Ошибка получения статистики")

    def select_log_file(self):
        """Открывает диалог выбора лог файла"""
        try:
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout, QLabel
            
            dialog = QDialog(self)
            dialog.setWindowTitle("Выбор лог файла")
            dialog.setMinimumSize(600, 400)
            
            layout = QVBoxLayout(dialog)
            
            # Список логов
            list_widget = QListWidget()
            
            if hasattr(global_logger, 'get_all_logs'):
                logs = global_logger.get_all_logs()
                for log in logs:
                    item_text = f"{log['name']} ({log['size'] // 1024} KB) - {log['modified'].strftime('%d.%m.%Y %H:%M')}"
                    if log['is_current']:
                        item_text += " [ТЕКУЩИЙ]"
                    list_widget.addItem(item_text)
                    # Сохраняем путь в data
                    list_widget.item(list_widget.count() - 1).setData(Qt.ItemDataRole.UserRole, log['path'])
            
            layout.addWidget(QLabel(f"Доступные лог файлы (всего: {list_widget.count()})"))
            layout.addWidget(list_widget)
            
            # Кнопки
            btn_layout = QHBoxLayout()
            btn_open = QPushButton("Открыть")
            btn_cancel = QPushButton("Отмена")
            
            btn_layout.addWidget(btn_open)
            btn_layout.addWidget(btn_cancel)
            layout.addLayout(btn_layout)
            
            def open_selected():
                current_item = list_widget.currentItem()
                if current_item:
                    log_path = current_item.data(Qt.ItemDataRole.UserRole)
                    self.start_tail_worker(log_path)
                    dialog.accept()
            
            btn_open.clicked.connect(open_selected)
            btn_cancel.clicked.connect(dialog.reject)
            list_widget.doubleClicked.connect(open_selected)
            
            dialog.exec()
            
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть диалог выбора: {e}")

    def open_logs_folder(self):
        """Открывает папку с логами в проводнике"""
        try:
            import subprocess
            log_dir = os.path.dirname(self.current_log_file)
            if os.path.exists(log_dir):
                subprocess.Popen(f'explorer "{log_dir}"')
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Ошибка", f"Не удалось открыть папку: {e}")

    # ----------- slots -----------
    def _append_text(self, text: str):
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def copy_all(self):
        self.log_text.selectAll()
        self.log_text.copy()
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)

    def closeEvent(self, event):
        """
        Останавливаем tail-воркер и дожидаемся завершения потока,
        чтобы не упасть на «Destroyed while thread is still running».
        """
        try:
            if hasattr(self, "_worker") and self._worker:
                self._worker.stop()           # просим воркер завершиться
            if hasattr(self, "_thread") and self._thread.isRunning():
                self._thread.quit()
                self._thread.wait(2_000)      # <= 2 сек
        finally:
            super().closeEvent(event)

# ───────────────────────────────────────────────────────────────
# 3.  GLOBAL LOGGER + HELPERS
# ───────────────────────────────────────────────────────────────
try:
    global_logger = Logger()
except Exception:
    class _FallbackLogger:
        def log(self, *_a, **_kw): pass
        def log_exception(self, *_a, **_kw): pass
        def get_log_content(self): return "Logging system initialization failed."
    global_logger = _FallbackLogger()

def log(msg, level="INFO", component=None):       # удобный helper
    global_logger.log(msg, level, component)

def log_exception(e, context=""):                 # helper для исключений
    global_logger.log_exception(e, context)

def get_log_content():
    return global_logger.get_log_content()