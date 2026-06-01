"""Workflow запуска и остановки BlockCheck page."""

from dataclasses import dataclass
from collections.abc import Callable

from PyQt6.QtCore import QTimer


@dataclass(frozen=True)
class BlockcheckRunStartResult:
    worker: object
    run_log_file: str | None


def start_blockcheck_page_run(
    *,
    blockcheck_feature,
    mode: str,
    extra_domains: list[str],
    skip_preflight_failed: bool,
    parent,
    run_runtime,
    table,
    tcp_table,
    tcp_section_label,
    dpi_card,
    log_edit,
    start_button,
    stop_button,
    mode_combo,
    skip_failed_checkbox,
    progress_bar,
    status_label,
    runtime_warnings_seen: set[str],
    set_support_status: Callable[[str], None],
    tr_fn: Callable[..., str],
    on_phase_changed,
    on_test_result,
    on_target_complete,
    on_log,
    on_run_log_started,
    on_finished,
) -> BlockcheckRunStartResult:
    """Готовит экран и запускает фоновую проверку BlockCheck."""
    table.setRowCount(0)
    if tcp_table is not None:
        tcp_table.setRowCount(0)
        tcp_table.setVisible(False)
    if tcp_section_label is not None:
        tcp_section_label.setVisible(False)
    dpi_card.setVisible(False)
    log_edit.clear()
    runtime_warnings_seen.clear()
    set_support_status("")

    start_button.setEnabled(False)
    stop_button.setEnabled(True)
    mode_combo.setEnabled(False)
    skip_failed_checkbox.setEnabled(False)
    progress_bar.setVisible(True)
    if hasattr(progress_bar, "start"):
        progress_bar.start()
    status_label.setText(
        tr_fn("page.blockcheck.running", default="Запуск тестов...")
    )

    worker = blockcheck_feature.create_blockcheck_worker(
        mode=mode,
        extra_domains=extra_domains or None,
        skip_preflight_failed=skip_preflight_failed,
        parent=None,
    )
    worker.phase_changed.connect(on_phase_changed)
    worker.test_result.connect(on_test_result)
    worker.target_complete.connect(on_target_complete)
    worker.log_message.connect(on_log)
    worker.run_log_started.connect(on_run_log_started)
    worker.finished.connect(on_finished)
    run_runtime.start_qobject_worker(
        parent=parent,
        worker_factory=lambda _request_id: worker,
    )

    return BlockcheckRunStartResult(
        worker=worker,
        run_log_file=None,
    )


def request_blockcheck_stop(
    *,
    worker,
    stop_button,
    status_label,
    force_stop: Callable[[object], None],
    tr_fn: Callable[..., str],
) -> None:
    """Запрашивает остановку текущего BlockCheck worker."""
    expected_worker = None
    if worker is not None:
        worker.stop()
        expected_worker = worker

    stop_button.setEnabled(False)
    status_label.setText(
        tr_fn("page.blockcheck.stopping", default="Остановка...")
    )
    QTimer.singleShot(5000, lambda worker=expected_worker: force_stop(worker))


def reset_blockcheck_running_ui(
    *,
    start_button,
    stop_button,
    mode_combo,
    skip_failed_checkbox,
    progress_bar,
) -> None:
    """Возвращает основные элементы управления BlockCheck в idle-состояние."""
    start_button.setEnabled(True)
    stop_button.setEnabled(False)
    mode_combo.setEnabled(True)
    skip_failed_checkbox.setEnabled(True)
    progress_bar.setVisible(False)
    if hasattr(progress_bar, "stop"):
        progress_bar.stop()


def cleanup_blockcheck_worker(worker):
    """Останавливает или удаляет worker при закрытии страницы."""
    if worker is None:
        return None
    if getattr(worker, "is_running", False):
        try:
            worker.stop()
        except Exception:
            pass
        return worker

    try:
        worker.deleteLater()
    except Exception:
        pass
    return None
