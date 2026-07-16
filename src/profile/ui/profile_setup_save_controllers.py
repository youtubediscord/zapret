"""Контроллеры записи страницы profile: write-очередь и save-подсистемы.

Вынесено из profile_setup_page.py (этап 4, фаза B, чанк M3) одним модулем:
write-serialization очередь (C1) и все её клиенты-стартеры — settings
autosave (C11), raw save (C3), enabled save (C12) — разделяют
`_settings_save_runtime` и мультиплексируются одной очередью
QueuedWorkerState (намерение I4).

Контроллер не владеет состоянием: state-объекты, рантаймы, счётчики
request_id и QTimer'ы живут на странице — поведенческие тесты создают
страницу через `__new__` и присваивают эти атрибуты напрямую. Вызовы
методов, которые тесты подменяют на экземпляре страницы, идут через
атрибут страницы (диспетчеризация через instance-словарь сохранена).
"""

from __future__ import annotations

from profile.profile_setup_loader import profile_save_result_keys
from profile.ui.profile_setup_controls import range_expression_from_controls
from settings.mode import is_preset_launch_method
from ui.latest_value_worker_state import LatestValueWorkerState
from ui.queued_worker_state import QueuedWorkerState


def _page_module():
    """Модуль страницы через ленивый импорт.

    Разрывает циклический импорт со страницей и сохраняет monkeypatch-цели
    `profile.ui.profile_setup_page.*`: module-функции, `log`, `QTimer` и
    `InfoBar` патчатся тестами по пути модуля страницы и резолвятся здесь
    в момент вызова."""
    from profile.ui import profile_setup_page

    return profile_setup_page


class ProfileSetupSaveController:
    """Stateless-оркестратор write-очереди и save-подсистем страницы."""

    def __init__(self, page) -> None:
        self._page = page

    def _profile_setup_write_is_running(self) -> bool:
        page = self._page
        if page._profile_setup_write_state_obj().start_scheduled:
            return True
        for attr in (
            "_list_file_save_runtime",
            "_settings_save_runtime",
            "_raw_profile_save_runtime",
            "_enabled_save_runtime",
            "_strategy_apply_runtime",
        ):
            runtime = page.__dict__.get(attr)
            if runtime is not None and runtime.is_running():
                return True
        if page._enabled_save_state_obj().start_scheduled:
            return True
        if page._list_file_save_state_obj().start_scheduled:
            return True
        return False

    @staticmethod
    def _profile_setup_write_operations_collide(previous: dict, queued: dict) -> bool:
        """Замещать в очереди можно только операцию над ТЕМ ЖЕ объектом.

        list_file_save-операции с разными (profile_key, filter_kind,
        filter_value) пишут в разные файлы: замещение по одному только kind
        молча теряло флаш прежнего профиля/типа фильтра."""
        if previous.get("kind") != queued.get("kind"):
            return False
        if str(queued.get("kind") or "") != "list_file_save":
            return True
        return all(
            str(previous.get(field) or "") == str(queued.get(field) or "")
            for field in ("profile_key", "filter_kind", "filter_value")
        )

    def _queue_profile_setup_write_operation(self, operation: dict[str, object]) -> None:
        page = self._page
        queued = dict(operation)
        scheduled = page.__dict__.get("_scheduled_profile_setup_write_operation")
        if (
            page._profile_setup_write_state_obj().start_scheduled
            and isinstance(scheduled, dict)
            and page._profile_setup_write_operations_collide(scheduled, queued)
        ):
            page._scheduled_profile_setup_write_operation = queued
            return
        pending = page._profile_setup_write_state_obj().pending
        if pending and pending[-1] == queued:
            return
        if pending and page._profile_setup_write_operations_collide(pending[-1], queued):
            pending[-1] = queued
            return
        pending.append(queued)

    def _start_next_profile_setup_write_operation(self) -> bool:
        page = self._page
        if page.__dict__.get("_cleanup_in_progress"):
            return False
        if page._profile_setup_write_is_running():
            return False
        state = page._profile_setup_write_state_obj()
        operation = state.pop_next()
        if not operation:
            return False
        page._schedule_profile_setup_write_operation_start(dict(operation))
        return True

    def _schedule_next_profile_setup_write_operation_after_finish(
        self,
        request_attr: str,
        worker,
    ) -> tuple[bool, bool]:
        page = self._page
        accepted = False

        def _is_current_worker_finish(_runtime, finished_worker) -> bool:
            nonlocal accepted
            accepted = page._accept_current_profile_setup_worker_finished(request_attr, finished_worker)
            return accepted

        def _single_shot(delay: int, callback) -> None:
            try:
                _page_module().QTimer.singleShot(delay, callback)
            except Exception:
                callback()

        operation = page._profile_setup_write_state_obj().schedule_next_after_finish(
            worker,
            is_current_worker_finish=_is_current_worker_finish,
            single_shot=_single_shot,
            start=lambda pending: page._run_profile_setup_write_operation(dict(pending or {})),
            queue_item=page._queue_profile_setup_write_operation,
            is_cleanup_in_progress=lambda: bool(page.__dict__.get("_cleanup_in_progress", False)),
        )
        return accepted, operation is not None

    def _schedule_profile_setup_write_operation_start(self, operation: dict[str, object]) -> None:
        page = self._page
        queued = dict(operation or {})
        if page.__dict__.get("_cleanup_in_progress"):
            return
        state = page._profile_setup_write_state_obj()
        if state.start_scheduled:
            page._queue_profile_setup_write_operation(queued)
            return
        page._scheduled_profile_setup_write_operation = queued
        state.start_scheduled = True
        try:
            _page_module().QTimer.singleShot(0, page._run_profile_setup_write_operation)
        except Exception:
            page._run_profile_setup_write_operation()

    def _run_profile_setup_write_operation(self, operation: dict[str, object] | None = None) -> bool:
        page = self._page
        page._profile_setup_write_state_obj().start_scheduled = False
        if operation is None:
            operation = page.__dict__.get("_scheduled_profile_setup_write_operation")
        page._scheduled_profile_setup_write_operation = None
        operation = dict(operation or {})
        if page.__dict__.get("_cleanup_in_progress"):
            return False
        if page._profile_setup_write_is_running():
            page._queue_profile_setup_write_operation(operation)
            return False
        kind = str(operation.get("kind") or "")
        if kind == "list_file_save":
            page._pending_list_file_save = None
            request = _page_module()._normalized_list_file_save_request(operation)
            page._start_list_file_save_worker(
                request["profile_key"],
                request["text"],
                filter_kind=request["filter_kind"],
                filter_value=request["filter_value"],
            )
            return True
        if kind == "settings_save":
            page._pending_settings_save = None
            request = operation.get("request")
            page._start_settings_save_worker(dict(request if isinstance(request, dict) else {}))
            return True
        if kind == "raw_profile_save":
            page._pending_raw_profile_save = None
            page._start_raw_profile_save_worker(
                str(operation.get("profile_key") or ""),
                operation.get("text"),
            )
            return True
        if kind == "enabled_save":
            page._pending_enabled_save = None
            page._start_enabled_save_worker(bool(operation.get("enabled")))
            return True
        if kind == "strategy_apply":
            page._pending_strategy_apply = None
            page._start_strategy_apply_worker(
                str(operation.get("strategy_id") or ""),
                strategy_branch_id=str(operation.get("branch_id") or ""),
            )
            return True
        return False

    def _profile_setup_write_state_obj(self) -> QueuedWorkerState[dict[str, object]]:
        page = self._page
        state = page.__dict__.get("_profile_setup_write_state")
        runtime = page.__dict__.get("_settings_save_runtime")
        if state is None:
            pending = [
                dict(operation or {})
                for operation in list(page.__dict__.pop("_pending_profile_setup_write_operations", []) or [])
            ]
            start_scheduled = bool(page.__dict__.pop("_profile_setup_write_operation_start_scheduled", False))
            state = QueuedWorkerState(
                runtime,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            page.__dict__["_profile_setup_write_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    def _schedule_settings_autosave(self) -> None:
        page = self._page
        if page._loading or not page._profile_key or not is_preset_launch_method(page.launch_method):
            return
        if page._profile_is_only_template():
            return
        page._settings_save_timer.start()

    def _autosave_editable_settings(self) -> None:
        page = self._page
        if page._loading or not page._profile_key or not is_preset_launch_method(page.launch_method):
            return
        filter_value = page._filter_value.text().strip()
        filter_enabled = bool(getattr(page._payload, "editable_filter_enabled", True))
        if filter_enabled and not filter_value:
            return
        request = {
            "profile_key": page._profile_key,
            "filter_kind": page._current_filter_kind(),
            "filter_value": filter_value,
            "in_range": range_expression_from_controls(page._in_range_mode, page._in_range_value, default="x"),
            "out_range": range_expression_from_controls(page._out_range_mode, page._out_range_value, default="a"),
        }
        payload = page.__dict__.get("_payload")
        if payload is not None and (
            str(getattr(payload, "editable_filter_kind", "") or "hostlist") == request["filter_kind"]
            and str(getattr(payload, "editable_filter_value", "") or "") == request["filter_value"]
            and str(getattr(payload, "in_range", "") or "x") == request["in_range"]
            and str(getattr(payload, "out_range", "") or "a") == request["out_range"]
        ):
            return
        page._request_settings_save(request)

    def _request_settings_save(self, request: dict) -> None:
        page = self._page
        request = dict(request)
        if page._profile_setup_write_is_running():
            state = page._settings_save_state_obj()
            if state.pending == dict(request):
                return
            state.pending = request
            page._queue_profile_setup_write_operation({"kind": "settings_save", "request": request})
            return
        page._start_settings_save_worker(request)

    def _start_settings_save_worker(self, request: dict) -> None:
        page = self._page
        runtime = page._worker_runtime("_settings_save_runtime")
        page._settings_save_request_id += 1
        request_id = page._settings_save_request_id
        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: page.create_profile_settings_save_worker(
                request_id,
                profile_key=str(request.get("profile_key") or ""),
                filter_kind=str(request.get("filter_kind") or ""),
                filter_value=str(request.get("filter_value") or ""),
                in_range=str(request.get("in_range") or ""),
                out_range=str(request.get("out_range") or ""),
                parent=page,
            ),
            on_loaded=page._on_settings_save_finished,
            on_failed=page._on_settings_save_failed,
            on_finished=page._on_settings_save_worker_finished,
            loaded_signal_name="saved",
        )

    def _on_settings_save_finished(self, request_id: int, saved_keys, payload=None) -> None:
        page = self._page
        if request_id != page._settings_save_request_id:
            return
        if page._settings_save_state_obj().has_pending():
            return
        old_saved_key, new_saved_key = profile_save_result_keys(saved_keys)
        payload, apply_signature = _page_module()._profile_setup_payload_and_apply_signature(payload)
        new_key = page._profile_result_reference(payload, new_saved_key)
        previous_key = str(page._profile_key or "").strip()
        old_key = old_saved_key or previous_key
        if new_key:
            page._profile_key = new_key
        if payload is None:
            page.reload_current_profile()
            page._emit_profile_changed(page._profile_key, "settings", old_profile_key=old_key)
            return
        if page.__dict__.get("_payload") is payload and (not new_key or new_key == previous_key):
            return
        page._payload = payload
        page._schedule_profile_setup_payload_apply(payload, apply_signature=apply_signature)
        page._emit_profile_changed(
            page._profile_key,
            "settings",
            getattr(payload, "item", None),
            old_profile_key=old_key,
        )

    def _on_settings_save_failed(self, request_id: int, error: str) -> None:
        page = self._page
        if request_id != page._settings_save_request_id:
            return
        if page._settings_save_state_obj().has_pending():
            return
        _page_module().log(f"{page.__class__.__name__}: не удалось сохранить настройки профиля: {error}", "ERROR")

    def _on_settings_save_worker_finished(self, worker) -> None:
        page = self._page
        accepted, scheduled = page._schedule_next_profile_setup_write_operation_after_finish(
            "_settings_save_request_id",
            worker,
        )
        if not accepted:
            return
        if scheduled:
            return
        pending = page._settings_save_state_obj().pending
        page._settings_save_state_obj().pending = None
        if pending:
            page._schedule_profile_setup_write_operation_start(
                {"kind": "settings_save", "request": dict(pending)}
            )

    def _settings_save_state_obj(self) -> LatestValueWorkerState:
        page = self._page
        state = page.__dict__.get("_settings_save_state")
        runtime = page.__dict__.get("_settings_save_runtime")
        if state is None:
            pending = page.__dict__.pop("_pending_settings_save", None)
            state = LatestValueWorkerState(
                runtime,
                empty_value=None,
                pending=pending,
            )
            page.__dict__["_settings_save_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    def _resolve_raw_profile_save_text(self, raw_text) -> str:
        page = self._page
        if raw_text is not None:
            return str(raw_text or "")
        return page._current_raw_profile_text()

    def _request_raw_profile_save(self, profile_key: str, raw_text: str | None) -> None:
        page = self._page
        profile_key = str(profile_key or "").strip()
        if not profile_key:
            return
        if page._profile_setup_write_is_running():
            page._raw_profile_save_state_obj().pending = (profile_key, raw_text)
            page._queue_profile_setup_write_operation(
                {"kind": "raw_profile_save", "profile_key": profile_key, "text": raw_text}
            )
            return
        page._start_raw_profile_save_worker(profile_key, raw_text)

    def _start_raw_profile_save_worker(self, profile_key: str, raw_text: str | None) -> None:
        page = self._page
        runtime = page._worker_runtime("_raw_profile_save_runtime")
        page._raw_profile_save_request_id += 1
        request_id = page._raw_profile_save_request_id
        raw_text = page._resolve_raw_profile_save_text(raw_text)
        if page._raw_profile_save_button is not None:
            _page_module().set_widget_enabled_if_changed(page._raw_profile_save_button, False)
        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: page.create_profile_raw_text_save_worker(
                request_id,
                profile_key,
                str(raw_text or ""),
                parent=page,
            ),
            on_loaded=page._on_raw_profile_save_finished,
            on_failed=page._on_raw_profile_save_failed,
            on_finished=page._on_raw_profile_save_worker_finished,
            loaded_signal_name="saved",
        )

    def _on_raw_profile_save_finished(self, request_id: int, saved_keys, payload=None) -> None:
        page = self._page
        if request_id != page._raw_profile_save_request_id:
            return
        if page._raw_profile_save_state_obj().has_pending():
            return
        old_saved_key, new_saved_key = profile_save_result_keys(saved_keys)
        payload, apply_signature = _page_module()._profile_setup_payload_and_apply_signature(payload)
        previous_key = str(page._profile_key or "").strip()
        old_key = old_saved_key or previous_key
        new_key = page._profile_result_reference(payload, new_saved_key)
        if new_key:
            page._profile_key = new_key
        if payload is None:
            page.reload_current_profile()
            page._emit_profile_changed(page._profile_key, "raw_profile", old_profile_key=old_key)
        elif page.__dict__.get("_payload") is payload and (not new_key or new_key == previous_key):
            pass
        else:
            page._payload = payload
            page._schedule_profile_setup_payload_apply(payload, apply_signature=apply_signature)
            page._emit_profile_changed(
                page._profile_key,
                "raw_profile",
                getattr(payload, "item", None),
                old_profile_key=old_key,
            )
        _page_module().InfoBar.success(
            title="Profile сохранён",
            content="Текст profile обновлён только в текущем preset.",
            parent=page.window(),
        )

    def _on_raw_profile_save_failed(self, request_id: int, error: str) -> None:
        page = self._page
        if request_id != page._raw_profile_save_request_id:
            return
        if page._raw_profile_save_state_obj().has_pending():
            return
        if page._raw_profile_save_button is not None:
            _page_module().set_widget_enabled_if_changed(page._raw_profile_save_button, True)
        _page_module().log(f"{page.__class__.__name__}: не удалось сохранить сырой текст profile: {error}", "ERROR")
        _page_module().InfoBar.error(
            title="Ошибка",
            content=str(error),
            parent=page.window(),
        )

    def _on_raw_profile_save_worker_finished(self, worker) -> None:
        page = self._page
        accepted, scheduled = page._schedule_next_profile_setup_write_operation_after_finish(
            "_raw_profile_save_request_id",
            worker,
        )
        if not accepted:
            return
        if scheduled:
            return
        pending = page._raw_profile_save_state_obj().pending
        page._raw_profile_save_state_obj().pending = None
        if pending:
            profile_key, raw_text = pending
            page._schedule_profile_setup_write_operation_start(
                {
                    "kind": "raw_profile_save",
                    "profile_key": str(profile_key or ""),
                    "text": raw_text,
                }
            )

    def _raw_profile_save_state_obj(self) -> LatestValueWorkerState:
        page = self._page
        state = page.__dict__.get("_raw_profile_save_state")
        runtime = page.__dict__.get("_raw_profile_save_runtime")
        if state is None:
            pending = page.__dict__.pop("_pending_raw_profile_save", None)
            state = LatestValueWorkerState(
                runtime,
                empty_value=None,
                pending=pending,
            )
            page.__dict__["_raw_profile_save_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    def _start_enabled_save_worker(self, enabled: bool) -> None:
        page = self._page
        runtime = page._worker_runtime("_enabled_save_runtime")
        page._enabled_save_request_id += 1
        request_id = page._enabled_save_request_id
        if page._enabled_checkbox is not None:
            _page_module().set_widget_enabled_if_changed(page._enabled_checkbox, False)
        page._enabled_save_runtime_enabled = bool(enabled)
        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: page.create_profile_enabled_save_worker(
                request_id,
                profile_key=page._profile_key,
                enabled=enabled,
                filter_kind=page._current_filter_kind(),
                filter_value=page._current_filter_value(),
                parent=page,
            ),
            on_loaded=page._on_enabled_save_finished,
            on_failed=page._on_enabled_save_failed,
            on_finished=page._on_enabled_save_worker_finished,
            loaded_signal_name="saved",
        )

    def _on_enabled_save_finished(self, request_id: int, profile_key: str, enabled: bool, payload=None) -> None:
        page = self._page
        if request_id != page._enabled_save_request_id:
            return
        if page._enabled_save_state_obj().has_pending():
            return
        payload, apply_signature = _page_module()._profile_setup_payload_and_apply_signature(payload)
        old_key = str(page._profile_key or "").strip()
        new_key = page._profile_result_reference(payload, profile_key)
        if payload is not None:
            if page.__dict__.get("_payload") is payload and (not new_key or new_key == old_key):
                return
            if new_key:
                page._profile_key = new_key
            page._payload = payload
            page._schedule_profile_setup_payload_apply(payload, apply_signature=apply_signature)
            page._on_profile_changed_callback(
                page._profile_key,
                "enabled" if enabled else "disabled",
                getattr(payload, "item", None),
            )
            return
        if new_key and new_key != old_key:
            page._profile_key = new_key
            page.reload_current_profile()
            page._on_profile_changed_callback(page._profile_key, "enabled" if enabled else "disabled")
            return
        updated_item = page._apply_enabled_locally(enabled)
        if updated_item is None:
            page.reload_current_profile()
            page._on_profile_changed_callback(page._profile_key, "enabled" if enabled else "disabled")
            return
        page._on_profile_changed_callback(page._profile_key, "enabled" if enabled else "disabled", updated_item)

    def _on_enabled_save_failed(self, request_id: int, error: str) -> None:
        page = self._page
        if request_id != page._enabled_save_request_id:
            return
        if page._enabled_save_state_obj().has_pending():
            return
        if page._enabled_checkbox is not None:
            _page_module().set_widget_enabled_if_changed(page._enabled_checkbox, True)
        _page_module().log(f"{page.__class__.__name__}: не удалось изменить состояние профиля: {error}", "ERROR")

    def _on_enabled_save_worker_finished(self, worker) -> None:
        page = self._page
        accepted, scheduled = page._schedule_next_profile_setup_write_operation_after_finish(
            "_enabled_save_request_id",
            worker,
        )
        if not accepted:
            return
        page._enabled_save_runtime_enabled = None
        if scheduled:
            return
        pending = page._enabled_save_state_obj().pending
        page._enabled_save_state_obj().pending = None
        if pending is None:
            return
        item = getattr(page.__dict__.get("_payload"), "item", None)
        if item is not None and bool(getattr(item, "enabled", False)) == bool(pending):
            if page._enabled_checkbox is not None:
                _page_module().set_widget_enabled_if_changed(page._enabled_checkbox, True)
            return
        page._enabled_save_state_obj().pending = bool(pending)
        page._schedule_enabled_save_worker_start()

    def _schedule_enabled_save_worker_start(self) -> None:
        page = self._page
        state = page._enabled_save_state_obj()

        def _single_shot(delay: int, callback) -> None:
            try:
                _page_module().QTimer.singleShot(delay, callback)
            except Exception:
                callback()

        state.schedule_start(_single_shot, page._run_scheduled_enabled_save_worker_start)

    def _run_scheduled_enabled_save_worker_start(self) -> None:
        page = self._page
        pending = page._enabled_save_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=page.__dict__.get("_cleanup_in_progress", False),
        )
        if pending is None:
            return
        item = getattr(page.__dict__.get("_payload"), "item", None)
        if item is not None and bool(getattr(item, "enabled", False)) == bool(pending):
            if page._enabled_checkbox is not None:
                _page_module().set_widget_enabled_if_changed(page._enabled_checkbox, True)
            return
        enabled = bool(pending)
        page._start_enabled_save_worker(bool(enabled))

    def _enabled_save_state_obj(self) -> LatestValueWorkerState:
        page = self._page
        state = page.__dict__.get("_enabled_save_state")
        runtime = page.__dict__.get("_enabled_save_runtime")
        if state is None:
            pending = page.__dict__.pop("_pending_enabled_save", None)
            start_scheduled = bool(page.__dict__.pop("_enabled_save_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=None,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            page.__dict__["_enabled_save_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state
