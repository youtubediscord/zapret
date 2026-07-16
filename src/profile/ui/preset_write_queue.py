from __future__ import annotations

from PyQt6.QtCore import QTimer

from qfluentwidgets import InfoBar

from log.log import log
from ui.queued_worker_state import QueuedWorkerState


class PresetWriteQueue:
    """Гетерогенная очередь записи пресета (context/move/user_profile).

    Одна очередь на все виды записи: один QueuedWorkerState, операции
    сериализованы, конвертеры kind↔operation, старт следующей операции —
    по finish предыдущей через single-shot.

    Очередь не владеет состоянием: QueuedWorkerState, рантаймы и счётчики
    request_id живут на странице — поведенческие тесты создают страницу через
    `__new__` и присваивают эти атрибуты напрямую. Очередь — оркестратор:
    читает состояние через stub-устойчивые аксессоры страницы и вызывает её
    UI-колбэки. Вызовы методов, которые тесты подменяют на экземпляре страницы
    (`_refresh_profile_item_locally`, `_set_user_profile_actions_enabled`,
    `_request_user_profile_*` и т.п.), идут через атрибут страницы, чтобы
    сохранить диспетчеризацию через instance-словарь.
    """

    def __init__(self, page) -> None:
        self._page = page

    def _profile_preset_write_state_obj(self) -> QueuedWorkerState[dict[str, object]]:
        # Состояние создаётся эагерно в __init__ страницы; ленивая ветка нужна
        # только duck-typed стабам из тестов (__new__ без __init__).
        page = self._page
        state = page.__dict__.get("_profile_preset_write_state")
        runtime = page.__dict__.get("_profile_context_action_runtime")
        if state is None:
            state = QueuedWorkerState(runtime)
            page.__dict__["_profile_preset_write_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    # --- постановка операций из UI ---

    def _request_profile_context_action(self, action: str, profile_key: str, *, enabled: bool | None = None) -> None:
        page = self._page
        # Ссылка вместо позиционного ключа: очередь записи не ремапит ключи,
        # и "profile:N", захваченный при клике, после предыдущей операции
        # указывал бы на чужой профиль.
        profile_key = page._profile_reference_for(profile_key)
        if not profile_key:
            return
        if self._profile_preset_write_operation_running():
            self._queue_profile_preset_write_operation(
                "context",
                action=str(action or ""),
                profile_key=profile_key,
                enabled=enabled,
            )
            return
        self._start_profile_context_action_worker(str(action or ""), profile_key, enabled=enabled)

    def _request_profile_move(
        self,
        action: str,
        source_profile_key: str,
        *,
        destination_profile_key: str = "",
        destination_group_key: str = "",
    ) -> None:
        page = self._page
        source_profile_key = str(source_profile_key or "").strip()
        if not source_profile_key:
            return
        if self._profile_preset_write_operation_running():
            self._queue_profile_preset_write_operation(
                "move",
                action=str(action or ""),
                source_profile_key=source_profile_key,
                destination_profile_key=str(destination_profile_key or ""),
                destination_group_key=str(destination_group_key or ""),
            )
            return
        self._start_profile_move_worker(
            str(action or ""),
            source_profile_key,
            destination_profile_key=destination_profile_key,
            destination_group_key=destination_group_key,
        )

    # --- механика очереди ---

    def _profile_preset_write_operation_running(self) -> bool:
        page = self._page
        if page._profile_preset_write_state_obj().start_scheduled:
            return True
        return (
            page._worker_runtime("_profile_context_action_runtime").is_running()
            or page._worker_runtime("_profile_move_runtime").is_running()
            or page._user_profile_operation_running()
        )

    def _user_profile_operation_running(self) -> bool:
        page = self._page
        for attr in (
            "_user_profile_create_runtime",
            "_user_profile_update_runtime",
            "_user_profile_delete_runtime",
        ):
            runtime = page.__dict__.get(attr)
            if runtime is None:
                continue
            try:
                if runtime.is_running():
                    return True
            except Exception:
                return True
        return False

    def _queue_profile_preset_write_operation(
        self,
        kind: str,
        *,
        action: str,
        profile_key: str = "",
        enabled: bool | None = None,
        source_profile_key: str = "",
        destination_profile_key: str = "",
        destination_group_key: str = "",
        profile_id: str = "",
        name: str = "",
        protocol: str = "",
        ports: str = "",
    ) -> None:
        page = self._page
        operation = {
            "kind": str(kind or ""),
            "action": str(action or ""),
            "profile_key": str(profile_key or source_profile_key or profile_id or ""),
            "enabled": enabled,
            "source_profile_key": str(source_profile_key or ""),
            "destination_profile_key": str(destination_profile_key or ""),
            "destination_group_key": str(destination_group_key or ""),
        }
        if operation["kind"] == "user_profile":
            operation.update(
                {
                    "profile_id": str(profile_id or ""),
                    "name": str(name or ""),
                    "protocol": str(protocol or ""),
                    "ports": str(ports or ""),
                }
            )
            if operation["action"] == "update":
                profile_id_to_replace = str(operation["profile_id"] or "")
                pending_operations = page._profile_preset_write_state_obj().pending
                pending_operations[:] = [
                    pending
                    for pending in pending_operations
                    if not (
                        str(pending.get("kind") or "") == "user_profile"
                        and str(pending.get("action") or "") == "update"
                        and str(pending.get("profile_id") or "") == profile_id_to_replace
                    )
                ]
        if operation["kind"] == "context" and operation["action"] == "set_enabled":
            profile_key_to_replace = str(operation["profile_key"] or "")
            pending_operations = page._profile_preset_write_state_obj().pending
            pending_operations[:] = [
                pending
                for pending in pending_operations
                if not (
                    str(pending.get("kind") or "") == "context"
                    and str(pending.get("action") or "") == "set_enabled"
                    and str(pending.get("profile_key") or "") == profile_key_to_replace
                )
            ]
        if operation["kind"] == "move":
            source_profile_key_to_replace = str(operation["source_profile_key"] or "")
            pending_operations = page._profile_preset_write_state_obj().pending
            pending_operations[:] = [
                pending
                for pending in pending_operations
                if not (
                    str(pending.get("kind") or "") == "move"
                    and str(pending.get("source_profile_key") or "") == source_profile_key_to_replace
                )
            ]
        page._profile_preset_write_state_obj().append(operation)

    def _pop_next_profile_preset_write_operation(self) -> dict[str, object] | None:
        pending_operations = self._page._profile_preset_write_state_obj().pending
        if pending_operations:
            return dict(pending_operations.pop(0))
        return None

    def _schedule_next_profile_preset_write_operation_start(self) -> bool:
        page = self._page
        if self._profile_preset_write_operation_running():
            return True
        if not page._has_pending_profile_preset_write_operation():
            return False
        if page._profile_preset_write_state_obj().start_scheduled:
            return True
        page._profile_preset_write_state_obj().start_scheduled = True
        try:
            QTimer.singleShot(0, self._run_scheduled_profile_preset_write_operation_start)
        except Exception:
            self._run_scheduled_profile_preset_write_operation_start()
        return True

    def _run_scheduled_profile_preset_write_operation_start(self) -> None:
        page = self._page
        page._profile_preset_write_state_obj().start_scheduled = False
        if page._is_cleanup_in_progress():
            return
        self._start_next_profile_preset_write_operation()

    def _queue_profile_preset_write_operation_from_dict(self, operation: dict[str, object]) -> bool:
        pending = dict(operation or {})
        self._queue_profile_preset_write_operation(
            str(pending.get("kind") or ""),
            action=str(pending.get("action") or ""),
            profile_key=str(pending.get("profile_key") or ""),
            enabled=pending.get("enabled"),
            source_profile_key=str(pending.get("source_profile_key") or ""),
            destination_profile_key=str(pending.get("destination_profile_key") or ""),
            destination_group_key=str(pending.get("destination_group_key") or ""),
            profile_id=str(pending.get("profile_id") or ""),
            name=str(pending.get("name") or ""),
            protocol=str(pending.get("protocol") or ""),
            ports=str(pending.get("ports") or ""),
        )
        return True

    def _schedule_next_profile_preset_write_operation_after_finish(
        self,
        request_attr: str,
        worker,
    ) -> tuple[bool, bool]:
        page = self._page
        accepted = False

        def _is_current_worker_finish(_runtime, finished_worker) -> bool:
            nonlocal accepted
            accepted = page._accept_current_preset_setup_worker_finished(request_attr, finished_worker)
            return accepted

        def _single_shot(delay: int, callback) -> None:
            try:
                QTimer.singleShot(delay, callback)
            except Exception:
                callback()

        operation = page._profile_preset_write_state_obj().schedule_next_after_finish(
            worker,
            is_current_worker_finish=_is_current_worker_finish,
            single_shot=_single_shot,
            start=lambda pending: self._run_profile_preset_write_operation(dict(pending or {})),
            queue_item=self._queue_profile_preset_write_operation_from_dict,
            is_cleanup_in_progress=lambda: bool(page._is_cleanup_in_progress()),
        )
        return accepted, operation is not None

    def _start_next_profile_preset_write_operation(self) -> bool:
        if self._profile_preset_write_operation_running():
            return True
        pending = self._pop_next_profile_preset_write_operation()
        if not pending:
            return False
        return self._run_profile_preset_write_operation(pending)

    def _run_profile_preset_write_operation(self, pending: dict[str, object] | None) -> bool:
        page = self._page
        pending = dict(pending or {})
        if page._is_cleanup_in_progress():
            return False
        if self._profile_preset_write_operation_running():
            self._queue_profile_preset_write_operation_from_dict(pending)
            return False
        if pending.get("kind") == "context":
            self._start_profile_context_action_worker(
                str(pending.get("action") or ""),
                str(pending.get("profile_key") or ""),
                enabled=pending.get("enabled"),
            )
            return True
        if pending.get("kind") == "move":
            self._start_profile_move_worker(
                str(pending.get("action") or ""),
                str(pending.get("source_profile_key") or ""),
                destination_profile_key=str(pending.get("destination_profile_key") or ""),
                destination_group_key=str(pending.get("destination_group_key") or ""),
            )
            return True
        if pending.get("kind") == "user_profile":
            action = str(pending.get("action") or "")
            if action == "create":
                page._request_user_profile_create(
                    name=str(pending.get("name") or ""),
                    protocol=str(pending.get("protocol") or ""),
                    ports=str(pending.get("ports") or ""),
                )
                return True
            if action == "update":
                page._request_user_profile_update(
                    str(pending.get("profile_id") or ""),
                    name=str(pending.get("name") or ""),
                    protocol=str(pending.get("protocol") or ""),
                    ports=str(pending.get("ports") or ""),
                )
                return True
            if action == "delete":
                page._request_user_profile_delete(str(pending.get("profile_id") or ""))
                return True
        return self._start_next_profile_preset_write_operation()

    # --- конвертеры kind↔operation ---

    @staticmethod
    def _profile_preset_write_operation_from_context_action(operation) -> dict[str, object]:
        pending = dict(operation or {})
        return {
            "kind": "context",
            "action": str(pending.get("action") or ""),
            "profile_key": str(pending.get("profile_key") or ""),
            "enabled": pending.get("enabled"),
            "source_profile_key": "",
            "destination_profile_key": "",
            "destination_group_key": "",
        }

    @staticmethod
    def _context_action_from_profile_preset_write_operation(operation) -> dict[str, object] | None:
        pending = dict(operation or {})
        if str(pending.get("kind") or "") != "context":
            return None
        return {
            "action": str(pending.get("action") or ""),
            "profile_key": str(pending.get("profile_key") or ""),
            "enabled": pending.get("enabled"),
        }

    @staticmethod
    def _profile_preset_write_operation_from_move_operation(operation) -> dict[str, object]:
        pending = dict(operation or {})
        source_profile_key = str(pending.get("source_profile_key") or "")
        return {
            "kind": "move",
            "action": str(pending.get("action") or ""),
            "profile_key": source_profile_key,
            "enabled": None,
            "source_profile_key": source_profile_key,
            "destination_profile_key": str(pending.get("destination_profile_key") or ""),
            "destination_group_key": str(pending.get("destination_group_key") or ""),
        }

    @staticmethod
    def _move_operation_from_profile_preset_write_operation(operation) -> dict[str, str] | None:
        pending = dict(operation or {})
        if str(pending.get("kind") or "") != "move":
            return None
        return {
            "action": str(pending.get("action") or ""),
            "source_profile_key": str(pending.get("source_profile_key") or pending.get("profile_key") or ""),
            "destination_profile_key": str(pending.get("destination_profile_key") or ""),
            "destination_group_key": str(pending.get("destination_group_key") or ""),
        }

    @staticmethod
    def _profile_preset_write_operation_from_user_profile_operation(operation) -> dict[str, object]:
        pending = dict(operation or {})
        profile_id = str(pending.get("profile_id") or "")
        return {
            "kind": "user_profile",
            "action": str(pending.get("action") or ""),
            "profile_key": profile_id,
            "enabled": None,
            "source_profile_key": "",
            "destination_profile_key": "",
            "destination_group_key": "",
            "profile_id": profile_id,
            "name": str(pending.get("name") or ""),
            "protocol": str(pending.get("protocol") or ""),
            "ports": str(pending.get("ports") or ""),
        }

    @staticmethod
    def _user_profile_operation_from_profile_preset_write_operation(operation) -> dict[str, str] | None:
        pending = dict(operation or {})
        if str(pending.get("kind") or "") != "user_profile":
            return None
        return {
            "action": str(pending.get("action") or ""),
            "profile_id": str(pending.get("profile_id") or pending.get("profile_key") or ""),
            "name": str(pending.get("name") or ""),
            "protocol": str(pending.get("protocol") or ""),
            "ports": str(pending.get("ports") or ""),
        }

    # --- context action: старт/финиш воркера ---

    def _start_profile_context_action_worker(
        self,
        action: str,
        profile_key: str,
        *,
        enabled: bool | None = None,
    ) -> None:
        page = self._page
        runtime = page._worker_runtime("_profile_context_action_runtime")
        page._profile_context_action_request_id = int(
            page.__dict__.get("_profile_context_action_request_id", 0) or 0
        ) + 1
        request_id = page._profile_context_action_request_id
        if str(action or "") == "set_enabled" and enabled is not None:
            page._profile_context_action_enabled_map()[request_id] = bool(enabled)

        def _bind_worker(worker) -> None:
            worker.finished_action.connect(page._on_profile_context_action_finished)
            worker.failed.connect(page._on_profile_context_action_failed)

        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: page._create_profile_context_action_worker(
                request_id,
                page.launch_method,
                action=str(action or ""),
                profile_key=profile_key,
                enabled=enabled,
                parent=page,
            ),
            bind_worker=_bind_worker,
            on_finished=page._on_profile_context_action_worker_finished,
        )

    def _on_profile_context_action_finished(self, request_id: int, action: str, profile_key: str, result) -> None:
        page = self._page
        if request_id != int(getattr(page, "_profile_context_action_request_id", 0) or 0):
            return
        applied_pending_result = False
        if action == "set_enabled":
            applied_pending_result = self._apply_profile_context_enabled_result(
                request_id,
                profile_key,
                result,
            )
        if page._has_pending_profile_preset_write_operation():
            return
        if action == "set_enabled":
            if not applied_pending_result:
                target_key = _profile_context_action_result_key(result) or str(profile_key or "").strip()
                page._refresh_profile_item_locally(profile_key, target_key)
            return
        if action == "duplicate":
            target_item = _profile_context_action_result_item(result)
            if target_item is not None and page._add_created_user_profile_locally(target_item):
                return
            page._add_profile_item_locally(profile_key, _profile_context_action_result_key(result))
            return
        if action == "delete" and bool(result):
            page._remove_profile_item_locally(profile_key)

    def _apply_profile_context_enabled_result(self, request_id: int, profile_key: str, result) -> bool:
        page = self._page
        target_key = _profile_context_action_result_key(result) or str(profile_key or "").strip()
        target_item = _profile_context_action_result_item(result)
        requested_enabled = bool(
            page._profile_context_action_enabled_map().pop(request_id, True)
        )
        held_item = (
            page._profiles_list.profile_item_for_key(profile_key)
            if page._profiles_list_widget() is not None
            else None
        )
        same_row = held_item is not None and str(getattr(held_item, "key", "") or "") == target_key
        if (target_key == str(profile_key or "") or same_row) and page._apply_profile_enabled_locally(
            profile_key, requested_enabled
        ):
            page._profile_payload_dirty = True
            return True
        if target_item is not None and page._add_created_user_profile_locally(target_item):
            return True
        return False

    def _on_profile_context_action_failed(self, request_id: int, error: str) -> None:
        page = self._page
        if request_id != int(getattr(page, "_profile_context_action_request_id", 0) or 0):
            return
        if page._has_pending_profile_preset_write_operation():
            page._profile_context_action_enabled_map().pop(request_id, None)
            return
        page._profile_context_action_enabled_map().pop(request_id, None)
        log(f"{page.__class__.__name__}: не удалось выполнить действие profile: {error}", "ERROR")
        InfoBar.error(title="Ошибка", content=str(error), parent=page.window())

    def _on_profile_context_action_worker_finished(self, worker) -> None:
        self._schedule_next_profile_preset_write_operation_after_finish(
            "_profile_context_action_request_id",
            worker,
        )

    # --- user profile: старт/финиш воркеров ---

    def _request_user_profile_create(self, *, name: str, protocol: str, ports: str) -> None:
        page = self._page
        if self._profile_preset_write_operation_running():
            self._queue_profile_preset_write_operation(
                "user_profile",
                action="create",
                name=name,
                protocol=protocol,
                ports=ports,
            )
            return
        page._user_profile_create_request_id = int(page.__dict__.get("_user_profile_create_request_id", 0) or 0) + 1
        request_id = page._user_profile_create_request_id
        page._set_user_profile_actions_enabled(False)
        runtime = page._worker_runtime("_user_profile_create_runtime")

        def _bind_worker(worker) -> None:
            worker.created.connect(page._on_user_profile_create_finished)
            worker.failed.connect(page._on_user_profile_create_failed)

        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: page._create_user_profile_create_worker(
                request_id,
                name=name,
                protocol=protocol,
                ports=ports,
            ),
            bind_worker=_bind_worker,
            on_finished=page._on_user_profile_create_worker_finished,
        )

    def _on_user_profile_create_finished(self, request_id: int, _profile_id: str, profile_item=None) -> None:
        page = self._page
        if request_id != int(getattr(page, "_user_profile_create_request_id", 0) or 0):
            return
        if page._has_pending_user_profile_operation():
            return
        InfoBar.success(
            title="Profile добавлен",
            content="Он появился в общем списке и пока выключен во всех preset-ах.",
            parent=page.window(),
        )
        if page._add_created_user_profile_locally(profile_item):
            return
        page._fallback_full_reload()

    def _on_user_profile_create_failed(self, request_id: int, error: str) -> None:
        page = self._page
        if request_id != int(getattr(page, "_user_profile_create_request_id", 0) or 0):
            return
        if page._has_pending_user_profile_operation():
            return
        log(f"{page.__class__.__name__}: не удалось создать пользовательский profile: {error}", "ERROR")
        InfoBar.error(title="Ошибка", content=str(error), parent=page.window())

    def _on_user_profile_create_worker_finished(self, worker) -> None:
        page = self._page
        accepted, scheduled = self._schedule_next_profile_preset_write_operation_after_finish(
            "_user_profile_create_request_id",
            worker,
        )
        if not accepted:
            return
        if scheduled:
            return
        if not page._user_profile_operation_running():
            page._set_user_profile_actions_enabled(True)

    def _request_user_profile_update(self, profile_id: str, *, name: str, protocol: str, ports: str) -> None:
        page = self._page
        profile_id = str(profile_id or "").strip()
        if not profile_id:
            return
        if self._profile_preset_write_operation_running():
            self._queue_profile_preset_write_operation(
                "user_profile",
                action="update",
                profile_id=profile_id,
                name=name,
                protocol=protocol,
                ports=ports,
            )
            return
        page._user_profile_update_request_id = int(page.__dict__.get("_user_profile_update_request_id", 0) or 0) + 1
        request_id = page._user_profile_update_request_id
        page._set_user_profile_actions_enabled(False)
        runtime = page._worker_runtime("_user_profile_update_runtime")

        def _bind_worker(worker) -> None:
            worker.updated.connect(page._on_user_profile_update_finished)
            worker.failed.connect(page._on_user_profile_update_failed)

        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: page._create_user_profile_update_worker(
                request_id,
                profile_id=profile_id,
                name=name,
                protocol=protocol,
                ports=ports,
            ),
            bind_worker=_bind_worker,
            on_finished=page._on_user_profile_update_worker_finished,
        )

    def _on_user_profile_update_finished(
        self,
        request_id: int,
        profile_id: str,
        changed: int,
        profile_items=(),
    ) -> None:
        page = self._page
        if request_id != int(getattr(page, "_user_profile_update_request_id", 0) or 0):
            return
        if page._has_pending_user_profile_operation():
            return
        InfoBar.success(
            title="Profile изменён",
            content=f"Обновлено profile-ов в preset-ах: {int(changed or 0)}.",
            parent=page.window(),
        )
        if page._replace_user_profile_items_locally(profile_id, profile_items):
            return
        page._fallback_full_reload()

    def _on_user_profile_update_failed(self, request_id: int, error: str) -> None:
        page = self._page
        if request_id != int(getattr(page, "_user_profile_update_request_id", 0) or 0):
            return
        if page._has_pending_user_profile_operation():
            return
        log(f"{page.__class__.__name__}: не удалось изменить пользовательский profile: {error}", "ERROR")
        InfoBar.error(title="Ошибка", content=str(error), parent=page.window())

    def _on_user_profile_update_worker_finished(self, worker) -> None:
        page = self._page
        accepted, scheduled = self._schedule_next_profile_preset_write_operation_after_finish(
            "_user_profile_update_request_id",
            worker,
        )
        if not accepted:
            return
        if scheduled:
            return
        if not page._user_profile_operation_running():
            page._set_user_profile_actions_enabled(True)

    def _request_user_profile_delete(self, profile_id: str) -> None:
        page = self._page
        profile_id = str(profile_id or "").strip()
        if not profile_id:
            return
        if self._profile_preset_write_operation_running():
            self._queue_profile_preset_write_operation(
                "user_profile",
                action="delete",
                profile_id=profile_id,
            )
            return
        page._user_profile_delete_request_id = int(page.__dict__.get("_user_profile_delete_request_id", 0) or 0) + 1
        request_id = page._user_profile_delete_request_id
        page._set_user_profile_actions_enabled(False)
        runtime = page._worker_runtime("_user_profile_delete_runtime")

        def _bind_worker(worker) -> None:
            worker.deleted.connect(page._on_user_profile_delete_finished)
            worker.failed.connect(page._on_user_profile_delete_failed)

        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: page._create_user_profile_delete_worker(
                request_id,
                profile_id=profile_id,
            ),
            bind_worker=_bind_worker,
            on_finished=page._on_user_profile_delete_worker_finished,
        )

    def _on_user_profile_delete_finished(self, request_id: int, _profile_id: str, changed: int) -> None:
        page = self._page
        if request_id != int(getattr(page, "_user_profile_delete_request_id", 0) or 0):
            return
        if page._has_pending_user_profile_operation():
            return
        InfoBar.success(
            title="Profile удалён",
            content=f"Удалено profile-ов из preset-ов: {int(changed or 0)}.",
            parent=page.window(),
        )
        if page._remove_user_profile_items_locally(_profile_id):
            return
        page._fallback_full_reload()

    def _on_user_profile_delete_failed(self, request_id: int, error: str) -> None:
        page = self._page
        if request_id != int(getattr(page, "_user_profile_delete_request_id", 0) or 0):
            return
        if page._has_pending_user_profile_operation():
            return
        log(f"{page.__class__.__name__}: не удалось удалить пользовательский profile: {error}", "ERROR")
        InfoBar.error(title="Ошибка", content=str(error), parent=page.window())

    def _on_user_profile_delete_worker_finished(self, worker) -> None:
        page = self._page
        accepted, scheduled = self._schedule_next_profile_preset_write_operation_after_finish(
            "_user_profile_delete_request_id",
            worker,
        )
        if not accepted:
            return
        if scheduled:
            return
        if not page._user_profile_operation_running():
            page._set_user_profile_actions_enabled(True)

    # --- move: старт/финиш воркера ---

    def _start_profile_move_worker(
        self,
        action: str,
        source_profile_key: str,
        *,
        destination_profile_key: str = "",
        destination_group_key: str = "",
    ) -> None:
        page = self._page
        runtime = page._worker_runtime("_profile_move_runtime")
        page._profile_move_request_id = int(page.__dict__.get("_profile_move_request_id", 0) or 0) + 1
        request_id = page._profile_move_request_id

        def _bind_worker(worker) -> None:
            worker.moved.connect(page._on_profile_move_finished)
            worker.failed.connect(page._on_profile_move_failed)

        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: page._create_profile_move_worker(
                request_id,
                page.launch_method,
                action=str(action or ""),
                source_profile_key=source_profile_key,
                destination_profile_key=destination_profile_key,
                destination_group_key=destination_group_key,
            ),
            bind_worker=_bind_worker,
            on_finished=page._on_profile_move_worker_finished,
        )

    def _on_profile_move_finished(
        self,
        request_id: int,
        action: str,
        source_profile_key: str,
        destination_profile_key: str,
        destination_group_key: str,
        result,
    ) -> None:
        page = self._page
        if request_id != int(getattr(page, "_profile_move_request_id", 0) or 0):
            return
        applied_locally = False
        if result:
            applied_locally = page._apply_profile_move_locally(
                action,
                source_profile_key,
                destination_profile_key=destination_profile_key,
                destination_group_key=destination_group_key,
            )
        if page._has_pending_profile_preset_write_operation():
            if applied_locally:
                page._profile_payload_dirty = True
            return
        if applied_locally:
            page._profile_payload_dirty = True
            return
        page.refresh_from_preset_switch()

    def _on_profile_move_failed(self, request_id: int, error: str) -> None:
        page = self._page
        if request_id != int(getattr(page, "_profile_move_request_id", 0) or 0):
            return
        if page._has_pending_profile_preset_write_operation():
            return
        log(f"{page.__class__.__name__}: не удалось переместить profile: {error}", "ERROR")
        page._fallback_full_reload()

    def _on_profile_move_worker_finished(self, worker) -> None:
        self._schedule_next_profile_preset_write_operation_after_finish(
            "_profile_move_request_id",
            worker,
        )


def _profile_context_action_result_key(result) -> str:
    if isinstance(result, dict):
        return str(result.get("profile_key") or "").strip()
    return str(result or "").strip()


def _profile_context_action_result_item(result):
    if isinstance(result, dict):
        return result.get("profile_item")
    return None
