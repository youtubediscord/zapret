from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QTimer

from log.log import log
from ui.latest_value_worker_state import LatestValueWorkerState


PROFILE_PAYLOAD_PRESET_SWITCH_RELOAD_DELAY_MS = 180


@dataclass
class ProfilePayloadLoadState:
    """Состояние машины загрузки payload списка профилей.

    Один объект вместо россыпи булевых флагов и двух независимых счётчиков:
    `request_id` — монотонный счётчик выдачи id (единственная точка
    инкремента — `_request_profiles_payload`), `runtime_request_id` — снимок
    id запущенного воркера. Тестозависимые имена страницы остаются
    thin-property поверх этого объекта.
    """

    request_id: int = 0
    runtime_request_id: int = 0
    loaded_once: bool = False
    dirty: bool = True
    load_failed: bool = False
    request_scheduled: bool = False
    request_force: bool = False
    reload_after_preset_switch_scheduled: bool = False
    apply_scheduled: bool = False
    pending_apply: object | None = None
    deferred_apply: object | None = None
    show_scheduled: bool = False
    last_apply_signature: object | None = None

    def invalidate_in_flight(self) -> None:
        """Результат уже запущенного воркера перестаёт быть текущим:
        его request_id больше не совпадает с текущим счётчиком."""
        self.request_id += 1


class ProfilePayloadController:
    """Машина загрузки/применения payload списка профилей.

    Контроллер не владеет состоянием: канон состояния (ProfilePayloadLoadState,
    OneShotWorkerRuntime, LatestValueWorkerState) живёт на странице —
    поведенческие тесты создают страницу через `__new__` и присваивают эти
    атрибуты напрямую. Контроллер — оркестратор: читает состояние через
    stub-устойчивые аксессоры страницы и вызывает её UI-колбэки.

    Вызовы методов, которые тесты подменяют на экземпляре страницы
    (`_apply_payload`, `_schedule_profile_payload_apply`,
    `_request_profiles_payload` и т.п.), идут через атрибут страницы,
    чтобы сохранить диспетчеризацию через instance-словарь.
    """

    def __init__(self, page) -> None:
        self._page = page

    def _profile_load_refresh_state_obj(self) -> LatestValueWorkerState:
        # Состояние создаётся эагерно в __init__ страницы; ленивая ветка нужна
        # только duck-typed стабам из тестов (__new__ без __init__).
        page = self._page
        state = page.__dict__.get("_profile_load_refresh_state")
        runtime = page.__dict__.get("_profile_load_runtime")
        if state is None:
            state = LatestValueWorkerState(runtime, empty_value=False)
            page.__dict__["_profile_load_refresh_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    def _profile_list_view_state_options(self) -> dict[str, object]:
        page = self._page
        profiles_list = page._profiles_list_widget()
        getter = getattr(profiles_list, "view_state_options", None)
        if callable(getter):
            try:
                return dict(getter() or {})
            except Exception:
                pass
        return {
            "active_profile_types": {"all"},
            "search_query": page._profile_search_query,
            "show_only_added": page._profile_show_only_added,
            "group_expanded": {},
        }

    # --- планирование и запрос payload ---

    def _schedule_profiles_payload_request(self, *, force: bool = False) -> None:
        page = self._page
        if bool(force) and page._profile_load_refresh_state_obj().has_pending():
            if page._worker_runtime_is_running("_profile_load_runtime"):
                page._deferred_profile_payload_apply = None
                page._pending_profile_payload_apply = None
                page._profile_payload_dirty = True
                return
        page._profile_payload_request_force = (
            bool(page._profile_payload_request_force) or bool(force)
        )
        if page._profile_payload_request_scheduled:
            return
        page._profile_payload_request_scheduled = True
        try:
            QTimer.singleShot(0, page._run_scheduled_profiles_payload_request)
        except Exception:
            page._run_scheduled_profiles_payload_request()

    def _run_scheduled_profiles_payload_request(self) -> None:
        page = self._page
        force = bool(page._profile_payload_request_force)
        page._profile_payload_request_scheduled = False
        page._profile_payload_request_force = False
        page._request_profiles_payload(force=force)

    def _schedule_profiles_payload_reload_after_preset_switch(self) -> None:
        page = self._page
        page._profile_payload_dirty = True
        if page._profile_payload_reload_after_preset_switch_scheduled:
            return
        page._profile_payload_reload_after_preset_switch_scheduled = True
        try:
            QTimer.singleShot(
                PROFILE_PAYLOAD_PRESET_SWITCH_RELOAD_DELAY_MS,
                self._run_scheduled_profiles_payload_reload_after_preset_switch,
            )
        except Exception:
            self._run_scheduled_profiles_payload_reload_after_preset_switch()

    def _run_scheduled_profiles_payload_reload_after_preset_switch(self) -> None:
        page = self._page
        page._profile_payload_reload_after_preset_switch_scheduled = False
        if page._is_cleanup_in_progress():
            return
        if not page._profile_payload_dirty:
            return
        page._schedule_profiles_payload_request(force=True)

    def _request_profiles_payload(self, *, force: bool = False) -> None:
        page = self._page
        if page._cleanup_in_progress:
            return
        if not force and page._profile_payload_loaded_once and not page._profile_payload_dirty:
            return
        if force:
            page._deferred_profile_payload_apply = None
            page._pending_profile_payload_apply = None
        page._profile_payload_dirty = True
        runtime = page._worker_runtime("_profile_load_runtime")
        refresh_state = page._profile_load_refresh_state_obj()
        if runtime.is_running() or refresh_state.start_scheduled:
            if force:
                page._profile_payload_dirty = True
                if not refresh_state.has_pending():
                    refresh_state.pending = True
                    if runtime.is_running():
                        page._profile_load_state_obj().invalidate_in_flight()
            return
        refresh_state.pending = False
        page._profile_load_request_id += 1
        request_id = page._profile_load_request_id
        if page._profiles_list_widget() is None:
            page._clear_dynamic_widgets()
        view_state_options = self._profile_list_view_state_options()

        def _bind_worker(worker) -> None:
            worker.loaded.connect(page._on_profile_payload_loaded)
            worker.failed.connect(page._on_profile_payload_failed)

        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: page._create_profile_list_load_worker(
                request_id,
                page.launch_method,
                page,
                view_state_options=view_state_options,
            ),
            bind_worker=_bind_worker,
            on_finished=page._on_profile_worker_finished,
        )
        page._profile_load_runtime_request_id = request_id

    # --- хендлеры воркера payload ---

    def _on_profile_payload_loaded(self, request_id: int, payload) -> None:
        page = self._page
        if request_id != page._profile_load_request_id or page._cleanup_in_progress:
            return
        if page._profile_load_refresh_state_obj().has_pending():
            return
        view_state = getattr(payload, "view_state", None)
        apply_signature_base = getattr(payload, "apply_signature_base", None)
        payload = getattr(payload, "payload", payload)
        page._profile_payload_loaded_once = True
        page._profile_payload_dirty = False
        page._schedule_profile_payload_apply(payload, view_state=view_state, apply_signature_base=apply_signature_base)

    def _schedule_profile_payload_apply(self, payload, *, view_state=None, apply_signature_base=None) -> None:
        page = self._page
        page._pending_profile_payload_apply = (payload, view_state, apply_signature_base)
        if page._profile_payload_apply_scheduled:
            return
        page._profile_payload_apply_scheduled = True
        try:
            QTimer.singleShot(0, page._run_scheduled_profile_payload_apply)
        except Exception:
            page._run_scheduled_profile_payload_apply()

    def _run_scheduled_profile_payload_apply(self) -> None:
        page = self._page
        pending = page._pending_profile_payload_apply
        page._pending_profile_payload_apply = None
        page._profile_payload_apply_scheduled = False
        if pending is None or page._cleanup_in_progress:
            return
        if (
            page._profile_load_refresh_state_obj().has_pending()
            or page._profile_payload_request_scheduled
        ):
            return
        is_page_hidden = False
        is_visible = getattr(page, "isVisible", None)
        if callable(is_visible):
            try:
                is_page_hidden = not bool(is_visible())
            except RuntimeError:
                is_page_hidden = False
        if is_page_hidden:
            page._deferred_profile_payload_apply = None
            payload, view_state, apply_signature_base = pending
            page._apply_payload(payload, view_state=view_state, apply_signature_base=apply_signature_base)
            page._profile_payload_dirty = False
            return
        page._deferred_profile_payload_apply = None
        payload, view_state, apply_signature_base = pending
        page._apply_payload(payload, view_state=view_state, apply_signature_base=apply_signature_base)
        page._schedule_profiles_list_show_after_page_switch()

    def _apply_deferred_profile_payload_after_show(self) -> bool:
        page = self._page
        pending = page._deferred_profile_payload_apply
        if pending is None or page._is_cleanup_in_progress():
            return False
        if page._profile_payload_refresh_is_blocked():
            return False
        page._deferred_profile_payload_apply = None
        payload, view_state, apply_signature_base = pending
        page._apply_payload(payload, view_state=view_state, apply_signature_base=apply_signature_base)
        page._profile_payload_loaded_once = True
        page._profile_payload_dirty = False
        return True

    def _profile_payload_refresh_is_blocked(self) -> bool:
        page = self._page
        refresh_state = page._profile_load_refresh_state_obj()
        return (
            refresh_state.is_busy()
            or refresh_state.has_pending()
            or page._profile_payload_request_scheduled
            or page._profile_payload_apply_scheduled
            or page._pending_profile_payload_apply is not None
        )

    def _on_profile_payload_failed(self, request_id: int, error: str) -> None:
        page = self._page
        if request_id != page._profile_load_request_id or page._cleanup_in_progress:
            return
        if (
            page._profile_load_refresh_state_obj().has_pending()
            or page._profile_payload_request_scheduled
        ):
            return
        page._profile_payload_dirty = True
        # Постоянная ошибка загрузки не должна перезапускаться из finish-обработчика:
        # без этого флага dirty превращается в pending и цикл load→fail крутится вечно.
        page._profile_payload_load_failed = True
        log(f"{page.__class__.__name__}: не удалось прочитать профили: {error}", "ERROR")
        page._show_empty_state(
            "Не удалось показать профили выбранного пресета. "
            "Файл мог быть удалён, очищен или повреждён. "
            "Выберите пресет заново в разделе «Мои пресеты»."
        )

    def _on_profile_worker_finished(self, worker) -> None:
        page = self._page
        state = page._profile_load_refresh_state_obj()
        load_failed = bool(page._profile_payload_load_failed)
        page._profile_payload_load_failed = False
        if page._profile_payload_dirty and not load_failed:
            state.pending = True
        state.schedule_pending_after_finish(
            worker,
            is_current_worker_finish=lambda _runtime, finished_worker: self._accept_current_profile_load_worker_finished(
                finished_worker
            ),
            single_shot=QTimer.singleShot,
            run_scheduled=self._run_scheduled_profile_load_refresh_start,
            cleanup_in_progress=bool(page._is_cleanup_in_progress()),
        )
        if state.has_pending() or state.start_scheduled:
            return
        is_visible = getattr(page, "isVisible", None)
        if callable(is_visible):
            try:
                if not bool(is_visible()):
                    return
            except RuntimeError:
                return
        if page._apply_deferred_profile_payload_after_show():
            page._schedule_profiles_list_show_after_page_switch()

    def _schedule_profile_load_refresh_start(self) -> None:
        page = self._page
        page._profile_load_refresh_state_obj().schedule_start(
            QTimer.singleShot,
            self._run_scheduled_profile_load_refresh_start,
            cleanup_in_progress=bool(page._is_cleanup_in_progress()),
            pending_when_already_scheduled=True,
        )

    def _run_scheduled_profile_load_refresh_start(self) -> None:
        page = self._page
        pending = page._profile_load_refresh_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=bool(page._is_cleanup_in_progress()),
        )
        if not pending:
            return
        page._schedule_profiles_payload_request(force=True)

    def _accept_current_profile_load_worker_finished(self, worker) -> bool:
        page = self._page
        request_id = getattr(worker, "_request_id", None)
        if request_id is None:
            return False
        try:
            current_request_id = int(page._profile_load_runtime_request_id or 0)
            if int(request_id) != current_request_id:
                return False
        except (TypeError, ValueError):
            return False
        page._profile_load_runtime_request_id = 0
        return True

    # --- машина точечного item refresh (путь B с fallback на полную перезагрузку) ---

    def _refresh_profile_item_locally(self, old_profile_key: str, profile_key: str) -> None:
        page = self._page
        old_key = str(old_profile_key or "").strip()
        clean_profile_key = str(profile_key or "").strip()
        page._profile_payload_dirty = True
        page._clear_deferred_profile_payload_apply()
        if page._is_cleanup_in_progress():
            return
        if not clean_profile_key:
            page._fallback_full_reload()
            return
        runtime = page._worker_runtime("_profile_item_refresh_runtime")

        def _bind_worker(worker) -> None:
            worker.refreshed.connect(page._on_profile_item_refreshed)
            worker.failed.connect(self._on_profile_item_refresh_failed)

        runtime.start_qthread_worker(
            worker_factory=lambda runtime_request_id: page._create_profile_item_refresh_worker(
                runtime_request_id,
                page.launch_method,
                old_profile_key=old_key or clean_profile_key,
                profile_key=clean_profile_key,
                parent=page,
            ),
            bind_worker=_bind_worker,
        )

    def _on_profile_item_refreshed(
        self,
        request_id: int,
        old_profile_key: str,
        profile_key: str,
        item,
    ) -> None:
        page = self._page
        if not self._profile_item_refresh_is_current(request_id):
            return
        if page._is_cleanup_in_progress():
            return
        if item is not None and page._replace_profile_item_locally(old_profile_key or profile_key, item):
            return
        page._fallback_full_reload()

    def _on_profile_item_refresh_failed(self, request_id: int, error: str) -> None:
        page = self._page
        if not self._profile_item_refresh_is_current(request_id):
            return
        if page._is_cleanup_in_progress():
            return
        log(f"{page.__class__.__name__}: не удалось обновить profile item: {error}", "DEBUG")
        page._fallback_full_reload()

    def _profile_item_refresh_is_current(self, request_id: int) -> bool:
        """Актуальность результата item-refresh решает примитив runtime
        (OneShotWorkerRuntime.is_current), без ручного счётчика страницы.
        Duck-typed стаб рантайма без is_current считается текущим."""
        runtime = self._page._worker_runtime("_profile_item_refresh_runtime")
        is_current = getattr(runtime, "is_current", None)
        if not callable(is_current):
            return True
        return bool(is_current(request_id))
