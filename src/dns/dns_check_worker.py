from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal


class DNSCheckWorker(QObject):
    """Worker для выполнения DNS проверки в отдельном потоке."""

    update_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal(dict)

    def run(self):
        try:
            from dns_checker import DNSChecker

            checker = DNSChecker()
            results = checker.check_dns_poisoning(log_callback=self.update_signal.emit)
            self.finished_signal.emit(results)
        except Exception as e:
            self.update_signal.emit(f"❌ Ошибка: {str(e)}")
            self.finished_signal.emit({})
