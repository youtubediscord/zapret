from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QThread


class OneShotWorkerRuntime:
    """Общий запуск одноразового фонового worker-а.

    Worker здесь — фоновый загрузчик. Он делает тяжёлую работу вне UI-потока,
    а страница принимает только свежий результат по request_id.
    """

    def __init__(self) -> None:
        self.request_id = 0
        self.worker = None
        self.thread = None

    def next_request_id(self) -> int:
        self.request_id += 1
        return self.request_id

    def is_current(self, request_id: int, *, cleanup_in_progress: bool = False) -> bool:
        return (not cleanup_in_progress) and int(request_id) == int(self.request_id)

    def is_running(self) -> bool:
        target = self.thread or self.worker
        if target is None:
            return False
        try:
            if hasattr(target, "is_running"):
                running_state = getattr(target, "is_running")
                return bool(running_state() if callable(running_state) else running_state)
            return bool(target.isRunning())
        except (AttributeError, RuntimeError):
            self.worker = None
            self.thread = None
            return False

    def start_qobject_worker(
        self,
        *,
        parent,
        worker_factory: Callable[[int], object],
        on_loaded: Callable | None = None,
        on_failed: Callable | None = None,
        on_finished: Callable | None = None,
        bind_worker: Callable[[object], None] | None = None,
        run_method_name: str = "run",
    ) -> tuple[int, object, QThread]:
        request_id = self.next_request_id()
        thread = QThread(parent)
        worker = worker_factory(request_id)
        worker.moveToThread(thread)

        run_method = getattr(worker, run_method_name)
        thread.started.connect(run_method)
        if on_loaded is not None and hasattr(worker, "loaded"):
            worker.loaded.connect(lambda *args, req=request_id: on_loaded(req, *args))
        if on_failed is not None and hasattr(worker, "failed"):
            worker.failed.connect(lambda *args, req=request_id: on_failed(req, *args))
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda req=request_id, th=thread: self._finish_qobject_worker(req, th, on_finished))
        thread.finished.connect(thread.deleteLater)
        if bind_worker is not None:
            bind_worker(worker)

        self.worker = worker
        self.thread = thread
        thread.start()
        return request_id, worker, thread

    def start_qthread_worker(
        self,
        *,
        worker_factory: Callable[[int], object],
        on_loaded: Callable | None = None,
        on_failed: Callable | None = None,
        on_finished: Callable | None = None,
        bind_worker: Callable[[object], None] | None = None,
        signal_includes_request_id: bool = True,
        loaded_signal_name: str = "loaded",
        failed_signal_name: str = "failed",
    ) -> tuple[int, object]:
        request_id = self.next_request_id()
        worker = worker_factory(request_id)

        loaded_signal = getattr(worker, loaded_signal_name, None)
        if on_loaded is not None and loaded_signal is not None:
            if signal_includes_request_id:
                loaded_signal.connect(on_loaded)
            else:
                loaded_signal.connect(lambda *args, req=request_id: on_loaded(req, *args))
        failed_signal = getattr(worker, failed_signal_name, None)
        if on_failed is not None and failed_signal is not None:
            if signal_includes_request_id:
                failed_signal.connect(on_failed)
            else:
                failed_signal.connect(lambda *args, req=request_id: on_failed(req, *args))
        worker.finished.connect(lambda *_args, w=worker: self._finish_qthread_worker(w, on_finished))
        worker.finished.connect(worker.deleteLater)
        if bind_worker is not None:
            bind_worker(worker)

        self.worker = worker
        self.thread = None
        worker.start()
        return request_id, worker

    def stop(
        self,
        *,
        blocking: bool = False,
        wait_timeout_ms: int = 2000,
        terminate_wait_ms: int = 500,
        log_fn: Callable[[str, str], None] | None = None,
        warning_prefix: str = "Worker",
    ) -> None:
        worker = self.worker
        thread = self.thread

        if worker is not None:
            stop = getattr(worker, "stop", None)
            if callable(stop):
                try:
                    stop()
                except RuntimeError:
                    worker = None
                    self.worker = None
                except Exception as exc:
                    if log_fn is not None:
                        log_fn(f"Ошибка остановки {warning_prefix}: {exc}", "DEBUG")

        target = thread or worker
        if target is None:
            return
        try:
            if hasattr(target, "is_running"):
                running_state = getattr(target, "is_running")
                running = bool(running_state() if callable(running_state) else running_state)
            else:
                running = bool(target.isRunning())
        except (AttributeError, RuntimeError):
            self.worker = None
            self.thread = None
            return
        if not running:
            if self.worker is worker:
                self.worker = None
            if self.thread is thread:
                self.thread = None
            return

        quit_fn = getattr(target, "quit", None)
        if callable(quit_fn):
            quit_fn()
        if blocking and hasattr(target, "wait") and not target.wait(wait_timeout_ms):
            if log_fn is not None:
                log_fn(f"⚠ {warning_prefix} не завершился, принудительно завершаем", "WARNING")
            terminate = getattr(target, "terminate", None)
            if callable(terminate):
                try:
                    terminate()
                    target.wait(terminate_wait_ms)
                except Exception:
                    pass

    def cancel(self) -> None:
        self.request_id += 1
        self.worker = None
        self.thread = None

    def _finish_qobject_worker(self, request_id: int, thread, on_finished: Callable | None) -> None:
        if self.thread is thread:
            self.thread = None
            self.worker = None
        if on_finished is not None:
            on_finished(request_id, thread)

    def _finish_qthread_worker(self, worker, on_finished: Callable | None) -> None:
        if self.worker is worker:
            self.worker = None
        if on_finished is not None:
            on_finished(worker)


__all__ = ["OneShotWorkerRuntime"]
