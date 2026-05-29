import time
from dataclasses import dataclass
from typing import Protocol

from PyQt6.QtCore import QThread, QTimer

from config.build_info import CHANNEL
from config.config import CHANNEL_DEV, CHANNEL_STABLE
from ui.one_shot_worker_runtime import OneShotWorkerRuntime

from log.log import log

from updater.rate_limiter import UpdateRateLimiter


@dataclass(slots=True)
class UpdateFoundState:
    is_available: bool = False
    version: str = ""
    release_notes: str = ""


@dataclass(slots=True)
class UpdateCheckState:
    is_active: bool = False
    last_check_time: float = 0.0
    has_cached_data: bool = False


@dataclass(slots=True)
class ServerCheckRecoveryState:
    enabled: bool = False
    attempted: bool = False
    retry_running: bool = False
    dpi_stopped: bool = False
    online_source_seen: bool = False


@dataclass(slots=True)
class UpdateDownloadState:
    is_installing: bool = False


@dataclass(slots=True)
class UpdateIdleViewDecision:
    action: str
    elapsed_seconds: float


@dataclass(slots=True)
class UpdateStartupPresentAction:
    version: str
    release_notes: str
    should_present_offer: bool
    should_schedule_install: bool


@dataclass(slots=True)
class UpdatePageInitPlan:
    should_apply_idle_view_state: bool
    view_action: str
    elapsed_seconds: float


@dataclass(frozen=True, slots=True)
class UpdateResponsibilityMap:
    state_and_view_methods: tuple[str, ...]
    state_and_worker_methods: tuple[str, ...]
    state_and_network_workflow_methods: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UpdateStatefulCoreDescription:
    required_state_fields: tuple[str, ...]
    worker_runtime_fields: tuple[str, ...]
    pure_helper_methods: tuple[str, ...]
    view_plan_candidates: tuple[str, ...]
    cleanup_extraction_candidates: tuple[str, ...]
    download_orchestration_candidates: tuple[str, ...]
    check_orchestration_candidates: tuple[str, ...]


class UpdatePageView(Protocol):
    def get_ui_language(self) -> str: ...
    def window(self): ...
    def is_update_download_in_progress(self) -> bool: ...
    def reset_server_rows(self) -> None: ...
    def upsert_server_status(self, server_name: str, status: dict) -> None: ...
    def start_checking(self) -> None: ...
    def finish_checking(self, found_update: bool, version: str) -> None: ...
    def show_found_update_source(self, version: str, source: str) -> None: ...
    def show_update_offer(self, version: str, release_notes: str) -> None: ...
    def hide_update_offer(self) -> None: ...
    def start_update_download(self, version: str) -> None: ...
    def update_download_progress(self, percent: int, done_bytes: int, total_bytes: int) -> None: ...
    def mark_update_download_complete(self) -> None: ...
    def mark_update_download_failed(self, error: str) -> None: ...
    def show_update_download_error(self) -> None: ...
    def show_update_deferred(self, version: str) -> None: ...
    def show_checked_ago(self, elapsed: float) -> None: ...
    def show_manual_hint(self) -> None: ...
    def show_auto_enabled_hint(self) -> None: ...
    def hide_update_status_card(self) -> None: ...
    def show_update_status_card(self) -> None: ...
    def set_update_check_enabled(self, enabled: bool) -> None: ...
    def set_auto_check_toggle_checked(self, enabled: bool) -> None: ...
    def show_update_channel_open_error(self, error: str) -> None: ...


class UpdatePageRuntime:
    """Сценарный слой страницы обновлений.

    Держит только действительно stateful-часть update workflow:
    фоновые воркеры, кэш найденного обновления, текущую проверку и загрузку.
    View остаётся экраном и получает уже готовые команды отображения.
    """

    def __init__(self, view: UpdatePageView, *, runtime_feature, updater_feature) -> None:
        self._view = view
        self._runtime_feature = runtime_feature
        self._updater_feature = updater_feature

        self._server_worker_runtime = OneShotWorkerRuntime()
        self._version_worker_runtime = OneShotWorkerRuntime()
        self._server_retry_without_dpi_runtime = OneShotWorkerRuntime()
        self._dpi_restart_runtime = OneShotWorkerRuntime()
        self._auto_check_load_runtime = OneShotWorkerRuntime()
        self._auto_check_save_runtime = OneShotWorkerRuntime()
        self._update_channel_open_runtime = OneShotWorkerRuntime()
        self._update_thread = None
        self._update_worker = None
        self._cleanup_in_progress = False
        self._auto_check_save_pending: bool | None = None
        self._auto_check_user_changed = False
        self._dpi_restart_after = ""

        self._found_state = UpdateFoundState()
        self._check_state = UpdateCheckState()
        self._server_check_recovery = ServerCheckRecoveryState()
        self._download_state = UpdateDownloadState()

        self._auto_check_enabled = False

    @property
    def auto_check_enabled(self) -> bool:
        return bool(self._auto_check_enabled)

    @staticmethod
    def build_responsibility_map() -> UpdateResponsibilityMap:
        return UpdateResponsibilityMap(
            state_and_view_methods=(
                "apply_idle_view_state",
                "present_startup_update",
                "request_manual_check",
                "install_update",
                "dismiss_update",
                "set_auto_check_enabled",
                "_offer_current_update",
                "_present_found_update_source",
                "_present_deferred_update",
                "_present_download_failure_ui",
                "_finish_checking_workflow",
                "_on_server_checked",
                "_on_versions_complete",
                "_on_download_failed",
                "_maybe_offer_update_from_server",
            ),
            state_and_worker_methods=(
                "start_checks",
                "install_update",
                "cleanup",
                "_start_server_check_workflow",
                "_request_server_retry_without_dpi",
                "_start_version_check_workflow",
                "_create_server_worker",
                "create_server_retry_without_dpi_worker",
                "_create_version_worker",
                "_create_update_worker_runtime",
                "_bind_server_worker_signals",
                "_bind_version_worker_signals",
                "_bind_update_worker_signals",
                "_handle_update_thread_finished",
                "_teardown_server_worker",
                "_teardown_server_retry_without_dpi_worker",
                "_teardown_version_worker",
                "_request_auto_check_load",
                "request_open_update_channel",
                "_teardown_update_runtime",
            ),
            state_and_network_workflow_methods=(
                "start_checks",
                "request_manual_check",
                "install_update",
                "_on_servers_complete",
                "_observe_server_check_status",
                "_maybe_retry_server_check_without_dpi",
                "_restart_dpi_after_server_check_retry",
                "_on_version_found",
                "_on_versions_complete",
                "_maybe_offer_update_from_server",
                "_get_candidate_version_and_notes",
                "_restart_dpi_after_update",
            ),
        )

    @staticmethod
    def build_stateful_core_description() -> UpdateStatefulCoreDescription:
        return UpdateStatefulCoreDescription(
            required_state_fields=(
                "_found_state",
                "_check_state",
                "_server_check_recovery",
                "_download_state",
                "_auto_check_enabled",
            ),
            worker_runtime_fields=(
                "_server_worker_runtime",
                "_version_worker_runtime",
                "_server_retry_without_dpi_runtime",
                "_dpi_restart_runtime",
                "_auto_check_load_runtime",
                "_update_channel_open_runtime",
                "_update_thread",
                "_update_worker",
            ),
            pure_helper_methods=(
                "_resolve_idle_view_decision",
                "_resolve_elapsed_since_last_check",
                "_resolve_startup_present_action",
                "_resolve_dismissed_update_version",
                "_can_present_idle_view_state",
                "_can_accept_startup_present",
                "_can_start_new_check",
                "_can_start_install",
                "_get_candidate_version_and_notes",
                "_app_version",
                "_is_dev_update_channel",
            ),
            view_plan_candidates=(
                "apply_idle_view_state",
                "_offer_current_update",
                "_present_found_update_source",
                "_present_deferred_update",
                "_present_download_failure_ui",
                "_finish_checking_workflow",
            ),
            cleanup_extraction_candidates=(
                "_teardown_server_worker",
                "_teardown_server_retry_without_dpi_worker",
                "_teardown_dpi_restart_worker",
                "_teardown_version_worker",
                "_teardown_auto_check_load_worker",
                "_teardown_update_channel_open_worker",
                "_teardown_update_runtime",
            ),
            download_orchestration_candidates=(
                "install_update",
                "_bind_update_worker_signals",
                "_handle_update_thread_finished",
                "_on_download_failed",
            ),
            check_orchestration_candidates=(
                "start_checks",
                "request_manual_check",
                "_start_server_check_workflow",
                "_start_version_check_workflow",
                "_on_servers_complete",
                "_observe_server_check_status",
                "_maybe_retry_server_check_without_dpi",
                "_restart_dpi_after_server_check_retry",
                "_on_version_found",
                "_on_versions_complete",
                "_maybe_offer_update_from_server",
            ),
        )

    def build_page_init_plan(self, *, runtime_initialized: bool) -> UpdatePageInitPlan:
        idle_decision = self._resolve_idle_view_decision()
        return UpdatePageInitPlan(
            should_apply_idle_view_state=not bool(runtime_initialized),
            view_action=idle_decision.action,
            elapsed_seconds=idle_decision.elapsed_seconds,
        )

    def apply_idle_view_state(self, *, view_action: str, elapsed_seconds: float) -> None:
        if self._cleanup_in_progress:
            return
        if not self._can_present_idle_view_state():
            return

        if view_action == "checked_ago":
            self._view.show_checked_ago(elapsed_seconds)
            return

        if view_action == "manual":
            self._view.show_manual_hint()
            return

        if view_action == "auto_on":
            self._view.show_auto_enabled_hint()

    def start_auto_check_load(self) -> None:
        self._request_auto_check_load()

    def _request_auto_check_load(self) -> None:
        if self._auto_check_load_runtime.is_running():
            return
        self._auto_check_load_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self._updater_feature.create_auto_check_load_worker(
                request_id,
                parent=self._view.window(),
            ),
            on_loaded=self._on_auto_check_load_finished,
            on_failed=self._on_auto_check_load_failed,
        )

    def _on_auto_check_load_finished(self, request_id: int, enabled: bool) -> None:
        if not self._auto_check_load_runtime.is_current(request_id, cleanup_in_progress=self._cleanup_in_progress):
            return
        if self._auto_check_user_changed:
            return
        self._auto_check_enabled = bool(enabled)
        self._view.set_auto_check_toggle_checked(bool(enabled))
        idle_decision = self._resolve_idle_view_decision()
        self.apply_idle_view_state(
            view_action=idle_decision.action,
            elapsed_seconds=idle_decision.elapsed_seconds,
        )

    def _on_auto_check_load_failed(self, request_id: int, error: str) -> None:
        if not self._auto_check_load_runtime.is_current(request_id, cleanup_in_progress=self._cleanup_in_progress):
            return
        log(f"Не удалось загрузить автопроверку обновлений: {error}", "WARNING")

    def present_startup_update(self, version: str, release_notes: str, *, install_after_show: bool = True) -> bool:
        if self._cleanup_in_progress:
            return False
        action = self._resolve_startup_present_action(
            version=version,
            release_notes=release_notes,
            install_after_show=install_after_show,
        )
        if not action.should_present_offer:
            log("Обновление уже загружается, пропускаем startup-триггер", "🔄 UPDATE")
            return False

        self._apply_startup_present_action(action)
        return True

    def start_checks(self, telegram_only: bool = False, skip_server_rate_limit: bool = False) -> None:
        self._cleanup_in_progress = False
        if self._check_state.is_active:
            return
        if not self._can_start_new_check():
            log("⏭️ Пропуск проверки - идёт скачивание обновления", "🔄 UPDATE")
            return

        keep_existing_rows = False

        if not telegram_only:
            if not skip_server_rate_limit:
                can_full, msg = UpdateRateLimiter.can_check_servers_full()
                if not can_full:
                    telegram_only = True
                    keep_existing_rows = True
                    log(f"⏱️ Полная проверка VPS заблокирована: {msg}. fallback=telegram-only", "🔄 UPDATE")

            if not telegram_only:
                UpdateRateLimiter.record_servers_full_check()
                self._check_state.last_check_time = time.time()

        self._reset_check_state(keep_cached_data=True)
        self._check_state.is_active = True
        self._server_check_recovery = ServerCheckRecoveryState(enabled=not telegram_only)
        self._reset_found_update_state()

        self._view.start_checking()
        if not keep_existing_rows:
            self._view.reset_server_rows()

        self._start_server_check_workflow(telegram_only=telegram_only)

    def request_manual_check(self) -> None:
        if not self._can_start_new_check():
            return

        self._view.hide_update_offer()
        self._reset_found_update_state()

        from updater import invalidate_cache

        invalidate_cache(CHANNEL)
        log("🔄 Полная проверка всех серверов (ручная)", "🔄 UPDATE")

        self.start_checks(telegram_only=False, skip_server_rate_limit=True)

    def install_update(self) -> None:
        self._cleanup_in_progress = False
        if not self._can_start_install():
            if self._download_state.is_installing:
                log("Загрузка уже выполняется, повторный запуск проигнорирован", "🔄 UPDATE")
            return

        self._download_state.is_installing = True
        log(f"Запуск установки обновления v{self._found_state.version}", "🔄 UPDATE")

        from updater import invalidate_cache

        invalidate_cache(CHANNEL)

        self._view.start_update_download(self._found_state.version)
        self._view.hide_update_status_card()
        self._view.set_update_check_enabled(False)

        try:
            update_thread, update_worker = self._create_update_worker_runtime()
            self._update_thread = update_thread
            self._update_worker = update_worker
            self._bind_update_worker_signals(update_thread, update_worker)
            update_thread.start()
        except Exception as e:
            log(f"Ошибка при запуске обновления: {e}", "❌ ERROR")
            self._teardown_update_runtime()
            self._view.mark_update_download_failed(str(e)[:50])

    def dismiss_update(self) -> None:
        version = self._resolve_dismissed_update_version()
        if not version:
            return
        log("Обновление отложено пользователем", "🔄 UPDATE")
        self._present_deferred_update(version)

    def set_auto_check_enabled(self, enabled: bool) -> None:
        self._auto_check_user_changed = True
        self._auto_check_enabled = bool(enabled)
        self._request_auto_check_save(bool(enabled))

        if enabled:
            self._view.show_auto_enabled_hint()
        else:
            self._view.show_manual_hint()

        log(f"Автопроверка при запуске: {'включена' if enabled else 'отключена'}", "🔄 UPDATE")

    def _request_auto_check_save(self, enabled: bool) -> None:
        if self._auto_check_save_runtime.is_running():
            self._auto_check_save_pending = bool(enabled)
            return
        self._start_auto_check_save_worker(bool(enabled))

    def _start_auto_check_save_worker(self, enabled: bool) -> None:
        self._auto_check_save_pending = None
        self._auto_check_save_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self._updater_feature.create_auto_check_save_worker(
                request_id,
                enabled=bool(enabled),
                parent=self._view.window(),
            ),
            on_failed=self._on_auto_check_save_failed,
            on_finished=lambda _worker: self._on_auto_check_save_finished(),
        )

    def _on_auto_check_save_failed(self, request_id: int, error: str) -> None:
        if not self._auto_check_save_runtime.is_current(request_id, cleanup_in_progress=self._cleanup_in_progress):
            return
        log(f"Не удалось сохранить автопроверку обновлений: {error}", "WARNING")

    def _on_auto_check_save_finished(self) -> None:
        if self._cleanup_in_progress:
            return
        pending = self._auto_check_save_pending
        if pending is None:
            return
        if bool(pending) == bool(self._auto_check_enabled):
            self._start_auto_check_save_worker(bool(pending))
        else:
            self._auto_check_save_pending = None

    def request_open_update_channel(self, channel: str) -> None:
        if self._update_channel_open_runtime.is_running():
            return
        self._update_channel_open_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self._updater_feature.create_update_channel_open_worker(
                request_id,
                channel=channel,
                parent=self._view.window(),
            ),
            on_loaded=self._on_update_channel_open_finished,
            on_failed=self._on_update_channel_open_failed,
        )

    def _on_update_channel_open_finished(self, request_id: int, result) -> None:
        if not self._update_channel_open_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if bool(getattr(result, "ok", False)):
            return
        self._view.show_update_channel_open_error(str(getattr(result, "message", "") or ""))

    def _on_update_channel_open_failed(self, request_id: int, error: str) -> None:
        if not self._update_channel_open_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        self._view.show_update_channel_open_error(str(error or ""))

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        self._teardown_server_worker()
        self._teardown_server_retry_without_dpi_worker()
        self._teardown_dpi_restart_worker()
        self._teardown_version_worker()
        self._teardown_auto_check_load_worker()
        self._teardown_auto_check_save_worker()
        self._teardown_update_channel_open_worker()
        self._teardown_update_runtime(wait_for_finish=True)

    def _resolve_idle_view_decision(self) -> UpdateIdleViewDecision:
        if not self._can_present_idle_view_state():
            return UpdateIdleViewDecision(action="none", elapsed_seconds=0.0)

        if self._found_state.is_available and self._found_state.version:
            return UpdateIdleViewDecision(action="none", elapsed_seconds=0.0)

        if self._check_state.has_cached_data:
            return UpdateIdleViewDecision(
                action="checked_ago",
                elapsed_seconds=self._resolve_elapsed_since_last_check(),
            )
        if self._auto_check_enabled:
            return UpdateIdleViewDecision(action="auto_on", elapsed_seconds=0.0)
        return UpdateIdleViewDecision(action="manual", elapsed_seconds=0.0)

    def _resolve_elapsed_since_last_check(self) -> float:
        return max(time.time() - self._check_state.last_check_time, 0.0)

    def _resolve_startup_present_action(
        self,
        *,
        version: str,
        release_notes: str,
        install_after_show: bool,
    ) -> UpdateStartupPresentAction:
        prepared_version = str(version or "")
        prepared_release_notes = str(release_notes or "")
        should_present_offer = bool(prepared_version) and self._can_accept_startup_present()
        return UpdateStartupPresentAction(
            version=prepared_version,
            release_notes=prepared_release_notes,
            should_present_offer=should_present_offer,
            should_schedule_install=bool(should_present_offer and install_after_show),
        )

    def _apply_startup_present_action(self, action: UpdateStartupPresentAction) -> None:
        self._set_found_update_state(action.version, action.release_notes)
        self._offer_current_update()
        if action.should_schedule_install:
            QTimer.singleShot(300, self.install_update)

    def _resolve_dismissed_update_version(self) -> str:
        return self._found_state.version

    def _can_present_idle_view_state(self) -> bool:
        return not (
            self._check_state.is_active
            or self._download_state.is_installing
            or self._is_download_in_progress()
        )

    def _can_accept_startup_present(self) -> bool:
        return not (
            self._download_state.is_installing
            or self._is_download_in_progress()
        )

    def _can_start_new_check(self) -> bool:
        return not (
            self._check_state.is_active
            or self._download_state.is_installing
            or self._is_download_in_progress()
        )

    def _can_start_install(self) -> bool:
        return bool(self._found_state.version) and not (
            self._download_state.is_installing
            or self._is_download_in_progress()
        )

    def _set_found_update_state(self, version: str, release_notes: str) -> None:
        self._found_state.is_available = bool(version)
        self._found_state.version = str(version or "")
        self._found_state.release_notes = str(release_notes or "")

    def _reset_found_update_state(self) -> None:
        self._found_state = UpdateFoundState()

    def _reset_check_state(self, *, keep_cached_data: bool = False) -> None:
        cached_data = self._check_state.has_cached_data if keep_cached_data else False
        last_check_time = self._check_state.last_check_time if keep_cached_data else 0.0
        self._check_state = UpdateCheckState(
            is_active=False,
            last_check_time=last_check_time,
            has_cached_data=cached_data,
        )

    def _reset_download_state(self) -> None:
        self._download_state = UpdateDownloadState()

    def _start_server_check_workflow(self, *, telegram_only: bool) -> None:
        self._teardown_server_worker()
        _request_id, server_worker = self._server_worker_runtime.start_qthread_worker(
            worker_factory=lambda _request_id: self._create_server_worker(telegram_only=telegram_only),
            bind_worker=self._bind_server_worker_signals,
            signal_includes_request_id=False,
        )
        _ = server_worker

    def _start_version_check_workflow(self) -> None:
        self._teardown_version_worker()
        _request_id, version_worker = self._version_worker_runtime.start_qthread_worker(
            worker_factory=lambda _request_id: self._create_version_worker(),
            bind_worker=self._bind_version_worker_signals,
            signal_includes_request_id=False,
        )
        _ = version_worker

    def _create_server_worker(self, *, telegram_only: bool):
        from updater.server_status_workers import ServerCheckWorker

        return ServerCheckWorker(
            update_pool_stats=False,
            telegram_only=telegram_only,
            language=self._view.get_ui_language(),
        )

    def create_server_retry_without_dpi_worker(self, request_id: int):
        from updater.retry_workers import UpdaterServerRetryWithoutDpiWorker

        return UpdaterServerRetryWithoutDpiWorker(
            request_id,
            is_any_running=self._runtime_feature.is_any_running,
            shutdown_sync=self._runtime_feature.shutdown_sync,
            parent=self._view.window(),
        )

    def create_dpi_restart_worker(self, request_id: int, *, context: str):
        from updater.retry_workers import UpdaterDpiRestartWorker

        return UpdaterDpiRestartWorker(
            request_id,
            is_available=self._runtime_feature.is_available,
            restart=self._runtime_feature.restart,
            context=context,
            parent=self._view.window(),
        )

    def _create_version_worker(self):
        from updater.server_status_workers import VersionCheckWorker

        return VersionCheckWorker()

    def _create_update_worker_runtime(self) -> tuple[QThread, object]:
        from updater.update import UpdateWorker

        parent_window = self._view.window()
        update_thread = QThread(parent_window)
        update_worker = UpdateWorker(
            parent_window,
            silent=True,
            skip_rate_limit=True,
            is_any_running=self._runtime_feature.is_any_running,
            shutdown_sync=self._runtime_feature.shutdown_sync,
        )
        update_worker.moveToThread(update_thread)
        return update_thread, update_worker

    def _bind_server_worker_signals(self, worker) -> None:
        worker.server_checked.connect(self._on_server_checked)
        worker.all_complete.connect(self._on_servers_complete)

    def _bind_version_worker_signals(self, worker) -> None:
        worker.version_found.connect(self._on_version_found)
        worker.complete.connect(self._on_versions_complete)

    def _bind_update_worker_signals(self, thread: QThread, worker) -> None:
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._handle_update_thread_finished)

        worker.progress_bytes.connect(
            lambda p, d, t: self._view.update_download_progress(p, d, t)
        )
        worker.download_complete.connect(self._view.mark_update_download_complete)
        worker.download_failed.connect(self._view.mark_update_download_failed)
        worker.download_failed.connect(self._on_download_failed)
        worker.dpi_restart_needed.connect(self._restart_dpi_after_update)
        worker.progress.connect(lambda message: log(f"{message}", "🔁 UPDATE"))

    def _handle_update_thread_finished(self) -> None:
        if self._cleanup_in_progress:
            return
        self._teardown_update_runtime()

    def _teardown_server_worker(self) -> None:
        self._server_worker_runtime.stop(
            blocking=True,
            log_fn=log,
            warning_prefix="server_worker",
        )
        self._server_worker_runtime.cancel()

    def _teardown_server_retry_without_dpi_worker(self) -> None:
        self._server_retry_without_dpi_runtime.stop(
            blocking=True,
            log_fn=log,
            warning_prefix="server_retry_without_dpi_worker",
        )
        self._server_retry_without_dpi_runtime.cancel()

    def _teardown_dpi_restart_worker(self) -> None:
        self._dpi_restart_after = ""
        self._dpi_restart_runtime.stop(
            blocking=True,
            log_fn=log,
            warning_prefix="dpi_restart_worker",
        )
        self._dpi_restart_runtime.cancel()

    def _teardown_version_worker(self) -> None:
        self._version_worker_runtime.stop(
            blocking=True,
            log_fn=log,
            warning_prefix="version_worker",
        )
        self._version_worker_runtime.cancel()

    def _teardown_auto_check_save_worker(self) -> None:
        self._auto_check_save_pending = None
        self._auto_check_save_runtime.stop(
            blocking=True,
            log_fn=log,
            warning_prefix="auto_check_save_worker",
        )
        self._auto_check_save_runtime.cancel()

    def _teardown_auto_check_load_worker(self) -> None:
        self._auto_check_load_runtime.stop(
            blocking=True,
            log_fn=log,
            warning_prefix="auto_check_load_worker",
        )
        self._auto_check_load_runtime.cancel()

    def _teardown_update_channel_open_worker(self) -> None:
        self._update_channel_open_runtime.stop(
            blocking=True,
            log_fn=log,
            warning_prefix="update_channel_open_worker",
        )
        self._update_channel_open_runtime.cancel()

    def _teardown_update_runtime(self, *, wait_for_finish: bool = False) -> None:
        thread = self._update_thread
        worker = self._update_worker
        try:
            if worker is not None:
                stop = getattr(worker, "stop", None)
                if callable(stop):
                    try:
                        stop()
                    except Exception as e:
                        log(f"Ошибка остановки update_worker: {e}", "DEBUG")
            if wait_for_finish and thread is not None and thread.isRunning():
                log("Останавливаем update_thread...", "DEBUG")
                thread.quit()
                if not thread.wait(2000):
                    log("⚠ update_thread не завершился, принудительно завершаем", "WARNING")
                    thread.terminate()
                    thread.wait(500)
        except Exception as e:
            log(f"Ошибка при очистке update runtime: {e}", "DEBUG")
        finally:
            self._update_thread = None
            self._update_worker = None
            self._reset_download_state()
            if not self._cleanup_in_progress:
                self._view.set_update_check_enabled(True)

    def _offer_current_update(self) -> None:
        if self._cleanup_in_progress:
            return
        if not self._found_state.is_available or not self._found_state.version:
            return
        self._view.show_update_offer(
            self._found_state.version,
            self._found_state.release_notes,
        )

    def _present_found_update_source(self, server_name: str) -> None:
        if self._cleanup_in_progress:
            return
        self._view.show_found_update_source(self._found_state.version, server_name)

    def _present_deferred_update(self, version: str) -> None:
        if self._cleanup_in_progress:
            return
        self._view.show_update_deferred(version)

    def _finish_checking_workflow(self) -> None:
        if self._cleanup_in_progress:
            return
        self._reset_check_state(keep_cached_data=True)
        self._check_state.has_cached_data = True
        self._view.finish_checking(self._found_state.is_available, self._found_state.version)

    def _on_server_checked(self, server_name: str, status: dict) -> None:
        if self._cleanup_in_progress:
            return
        self._observe_server_check_status(status)
        self._view.upsert_server_status(server_name, status)
        self._maybe_offer_update_from_server(server_name, status)

    def _on_servers_complete(self) -> None:
        if self._cleanup_in_progress:
            return
        if self._maybe_retry_server_check_without_dpi():
            return
        if self._restart_dpi_after_server_check_retry():
            return
        self._start_version_check_workflow()

    def _observe_server_check_status(self, status: dict) -> None:
        if not isinstance(status, dict):
            return
        if str(status.get("status") or "").lower() == "online":
            self._server_check_recovery.online_source_seen = True

    def _maybe_retry_server_check_without_dpi(self) -> bool:
        recovery = self._server_check_recovery
        if (
            not recovery.enabled
            or recovery.attempted
            or recovery.retry_running
            or recovery.online_source_seen
        ):
            return False

        self._request_server_retry_without_dpi()
        return True

    def _request_server_retry_without_dpi(self) -> None:
        recovery = self._server_check_recovery
        recovery.attempted = True
        recovery.retry_running = True
        recovery.online_source_seen = False
        self._server_retry_without_dpi_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_server_retry_without_dpi_worker(request_id),
            on_loaded=self._on_server_retry_without_dpi_finished,
            on_failed=self._on_server_retry_without_dpi_failed,
            on_finished=self._on_server_retry_without_dpi_worker_finished,
        )

    def _on_server_retry_without_dpi_finished(
        self,
        request_id: int,
        should_retry: bool,
        dpi_stopped: bool,
        _message: str,
    ) -> None:
        if not self._server_retry_without_dpi_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return

        recovery = self._server_check_recovery
        recovery.retry_running = False
        if should_retry:
            recovery.dpi_stopped = bool(dpi_stopped)
            self._start_server_check_workflow(telegram_only=False)
            return

        self._start_version_check_workflow()

    def _on_server_retry_without_dpi_failed(self, request_id: int, error: str) -> None:
        if not self._server_retry_without_dpi_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        log(f"Не удалось подготовить повторную проверку серверов без DPI: {error}", "❌ ERROR")
        self._server_check_recovery.retry_running = False
        self._start_version_check_workflow()

    def _on_server_retry_without_dpi_worker_finished(self, worker) -> None:
        if self._server_retry_without_dpi_runtime.worker is worker:
            self._server_retry_without_dpi_runtime.worker = None

    def _restart_dpi_after_server_check_retry(self) -> bool:
        recovery = self._server_check_recovery
        if not recovery.dpi_stopped:
            return False
        recovery.dpi_stopped = False
        recovery.retry_running = False
        self._restart_dpi_after_update(
            context="повторной проверки серверов",
            after_restart="version_check",
        )
        return True

    def _on_version_found(self, channel: str, version_info: dict) -> None:
        if self._cleanup_in_progress:
            return
        target_channel = CHANNEL_DEV if self._is_dev_update_channel() else CHANNEL_STABLE
        if channel not in {CHANNEL_STABLE, CHANNEL_DEV} or channel != target_channel or version_info.get("error"):
            return

        version = version_info.get("version", "")
        try:
            from updater.update import compare_versions

            if compare_versions(self._app_version(), version) < 0:
                self._set_found_update_state(
                    version,
                    version_info.get("release_notes", ""),
                )
        except Exception:
            pass

    def _on_versions_complete(self) -> None:
        if self._cleanup_in_progress:
            return
        self._finish_checking_workflow()

        if self._found_state.is_available and self._can_accept_startup_present():
            self._offer_current_update()

    def _on_download_failed(self, error: str) -> None:
        if self._cleanup_in_progress:
            return
        _ = error
        self._present_download_failure_ui()

    def _present_download_failure_ui(self) -> None:
        if self._cleanup_in_progress:
            return
        self._view.show_update_status_card()
        self._view.show_update_download_error()

    def _maybe_offer_update_from_server(self, server_name: str, status: dict) -> None:
        if not self._check_state.is_active:
            return

        if not self._found_state.is_available and not status.get("is_current"):
            return

        if not self._can_accept_startup_present():
            return

        candidate_version, candidate_notes = self._get_candidate_version_and_notes(status)
        if not candidate_version:
            return

        try:
            from updater.update import compare_versions

            if compare_versions(self._app_version(), candidate_version) >= 0:
                return

            if self._found_state.version and compare_versions(self._found_state.version, candidate_version) >= 0:
                return
        except Exception:
            return

        self._set_found_update_state(candidate_version, candidate_notes)
        self._offer_current_update()
        self._present_found_update_source(server_name)

    def _get_candidate_version_and_notes(self, status: dict) -> tuple[str | None, str]:
        if self._is_dev_update_channel():
            raw_version = status.get("dev_version")
            notes = status.get("dev_notes", "") or ""
        else:
            raw_version = status.get("stable_version")
            notes = status.get("stable_notes", "") or ""

        if not raw_version or raw_version == "—":
            return None, ""

        try:
            from updater.github_release import normalize_version

            return normalize_version(str(raw_version)), notes
        except Exception:
            return None, ""

    def _restart_dpi_after_update(
        self,
        *,
        context: str = "скачивания обновления",
        after_restart: str = "",
    ) -> None:
        if self._cleanup_in_progress:
            return
        self._request_dpi_restart(context=context, after_restart=after_restart)

    def _request_dpi_restart(self, *, context: str, after_restart: str = "") -> None:
        if self._dpi_restart_runtime.is_running():
            if after_restart:
                self._dpi_restart_after = str(after_restart or "")
            return
        self._dpi_restart_after = str(after_restart or "")
        self._dpi_restart_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_dpi_restart_worker(
                request_id,
                context=str(context or "скачивания обновления"),
            ),
            on_loaded=self._on_dpi_restart_finished,
            on_failed=self._on_dpi_restart_failed,
        )

    def _on_dpi_restart_finished(self, request_id: int, _restarted: bool) -> None:
        if not self._dpi_restart_runtime.is_current(request_id, cleanup_in_progress=self._cleanup_in_progress):
            return
        self._continue_after_dpi_restart()

    def _on_dpi_restart_failed(self, request_id: int, error: str) -> None:
        if not self._dpi_restart_runtime.is_current(request_id, cleanup_in_progress=self._cleanup_in_progress):
            return
        log(f"Не удалось перезапустить DPI: {error}", "❌ ERROR")
        self._continue_after_dpi_restart()

    def _continue_after_dpi_restart(self) -> None:
        after_restart = str(self._dpi_restart_after or "")
        self._dpi_restart_after = ""
        if after_restart == "version_check" and not self._cleanup_in_progress:
            self._start_version_check_workflow()

    def _is_download_in_progress(self) -> bool:
        try:
            return bool(self._view.is_update_download_in_progress())
        except Exception:
            return False

    @staticmethod
    def _app_version() -> str:
        from config.build_info import APP_VERSION


        return APP_VERSION

    @staticmethod
    def _is_dev_update_channel() -> bool:
        from updater.channel_utils import is_dev_update_channel

        return bool(is_dev_update_channel(CHANNEL))
