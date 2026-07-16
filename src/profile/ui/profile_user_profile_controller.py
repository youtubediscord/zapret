"""Контроллер записи пользовательского profile (update/delete).

Вынесено из profile_setup_page.py (этап 4, фаза B, чанк M5): одна очередь
`_user_profile_write_state` (QueuedWorkerState) сериализует update/delete
операции; конвертеры dict<->operation; рестарт по finish (намерение I5).
Клик-хендлеры (в т.ч. с MessageBox) остаются методами страницы (D8).

Контроллер не владеет состоянием: state-объект, рантаймы и счётчики
request_id живут на странице — поведенческие тесты создают страницу через
`__new__` и присваивают эти атрибуты напрямую. Вызовы методов, которые
тесты подменяют на экземпляре страницы, идут через атрибут страницы.
"""

from __future__ import annotations

from ui.queued_worker_state import QueuedWorkerState


def _page_module():
    """Модуль страницы через ленивый импорт.

    Разрывает циклический импорт со страницей и сохраняет monkeypatch-цели
    `profile.ui.profile_setup_page.*`: module-функции, `log`, `QTimer` и
    `InfoBar` патчатся тестами по пути модуля страницы и резолвятся здесь
    в момент вызова."""
    from profile.ui import profile_setup_page

    return profile_setup_page


class ProfileUserProfileController:
    """Stateless-оркестратор очереди записи user profile со ссылкой на страницу."""

    def __init__(self, page) -> None:
        self._page = page

    def _request_user_profile_update(self, profile_id: str, *, name: str, protocol: str, ports: str) -> None:
        page = self._page
        profile_id = str(profile_id or "").strip()
        if not profile_id:
            return
        if page._user_profile_write_operation_running():
            page._queue_user_profile_write_operation(
                "update",
                profile_id=profile_id,
                name=name,
                protocol=protocol,
                ports=ports,
            )
            return
        page._start_user_profile_update_worker(
            profile_id,
            name=name,
            protocol=protocol,
            ports=ports,
        )

    def _user_profile_write_operation_running(self) -> bool:
        page = self._page
        if page._user_profile_write_state_obj().start_scheduled:
            return True
        return page._worker_runtime("_user_profile_update_runtime").is_running() or page._worker_runtime(
            "_user_profile_delete_runtime"
        ).is_running()

    def _queue_user_profile_write_operation(
        self,
        action: str,
        *,
        profile_id: str,
        name: str = "",
        protocol: str = "",
        ports: str = "",
    ) -> None:
        page = self._page
        operation = {
            "action": str(action or ""),
            "profile_id": str(profile_id or ""),
            "name": str(name or ""),
            "protocol": str(protocol or ""),
            "ports": str(ports or ""),
        }
        state = page._user_profile_write_state_obj()
        if operation["action"] == "update":
            profile_id_to_replace = str(operation["profile_id"] or "")
            pending_operations = state.pending
            pending_operations[:] = [
                pending
                for pending in pending_operations
                if not (
                    str(pending.get("action") or "") == "update"
                    and str(pending.get("profile_id") or "") == profile_id_to_replace
                )
            ]
        state.append(operation)

    def _pop_next_pending_user_profile_write_operation(self) -> dict[str, str] | None:
        page = self._page
        state = page._user_profile_write_state_obj()
        pending = state.pop_next()
        if pending:
            return dict(pending)
        return None

    def _has_pending_user_profile_write_operation(self) -> bool:
        page = self._page
        return page._user_profile_write_state_obj().has_pending()

    def _schedule_next_pending_user_profile_write_operation_start(self) -> bool:
        page = self._page
        if page._user_profile_write_operation_running():
            return True
        if not page._has_pending_user_profile_write_operation():
            return False
        state = page._user_profile_write_state_obj()
        if state.start_scheduled:
            return True
        state.start_scheduled = True
        try:
            _page_module().QTimer.singleShot(0, page._run_scheduled_user_profile_write_operation_start)
        except Exception:
            page._run_scheduled_user_profile_write_operation_start()
        return True

    def _run_scheduled_user_profile_write_operation_start(self) -> None:
        page = self._page
        page._user_profile_write_state_obj().start_scheduled = False
        page._start_next_pending_user_profile_write_operation()

    def _user_profile_write_state_obj(self) -> QueuedWorkerState[dict[str, str]]:
        page = self._page
        state = page.__dict__.get("_user_profile_write_state")
        runtime = page.__dict__.get("_user_profile_update_runtime")
        if state is None:
            pending = [
                page._user_profile_write_operation_from_pending_operation(operation)
                for operation in list(page.__dict__.pop("_pending_user_profile_operations", []) or [])
            ]
            if not pending:
                pending.extend(
                    page._user_profile_write_operation_from_update(update)
                    for update in list(page.__dict__.pop("_pending_user_profile_updates", []) or [])
                )
                pending.extend(
                    page._user_profile_write_operation_from_delete(profile_id)
                    for profile_id in list(page.__dict__.pop("_pending_user_profile_deletes", []) or [])
                )
            else:
                page.__dict__.pop("_pending_user_profile_updates", None)
                page.__dict__.pop("_pending_user_profile_deletes", None)
            start_scheduled = bool(page.__dict__.pop("_user_profile_write_operation_start_scheduled", False))
            state = QueuedWorkerState(
                runtime,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            page.__dict__["_user_profile_write_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @staticmethod
    def _user_profile_write_operation_from_pending_operation(operation) -> dict[str, str]:
        pending = dict(operation or {})
        action = str(pending.get("action") or "")
        if action == "delete":
            return ProfileUserProfileController._user_profile_write_operation_from_delete(pending.get("profile_id"))
        return {
            "action": action,
            "profile_id": str(pending.get("profile_id") or ""),
            "name": str(pending.get("name") or ""),
            "protocol": str(pending.get("protocol") or ""),
            "ports": str(pending.get("ports") or ""),
        }

    @staticmethod
    def _user_profile_write_operation_from_update(update) -> dict[str, str]:
        pending = dict(update or {})
        return {
            "action": "update",
            "profile_id": str(pending.get("profile_id") or ""),
            "name": str(pending.get("name") or ""),
            "protocol": str(pending.get("protocol") or ""),
            "ports": str(pending.get("ports") or ""),
        }

    @staticmethod
    def _user_profile_write_operation_from_delete(profile_id) -> dict[str, str]:
        return {
            "action": "delete",
            "profile_id": str(profile_id or ""),
            "name": "",
            "protocol": "",
            "ports": "",
        }

    def _start_next_pending_user_profile_write_operation(self) -> bool:
        page = self._page
        if page._user_profile_write_operation_running():
            return True
        pending = page._pop_next_pending_user_profile_write_operation()
        if not pending:
            return False
        return page._run_user_profile_write_operation(pending)

    def _run_user_profile_write_operation(self, pending: dict[str, str] | None) -> bool:
        page = self._page
        pending = page._user_profile_write_operation_from_pending_operation(pending or {})
        if page.__dict__.get("_cleanup_in_progress", False):
            return False
        if page._user_profile_write_operation_running():
            page._queue_user_profile_write_operation_from_dict(pending)
            return False
        if pending.get("action") == "update":
            page._start_user_profile_update_worker(
                str(pending.get("profile_id") or ""),
                name=str(pending.get("name") or ""),
                protocol=str(pending.get("protocol") or ""),
                ports=str(pending.get("ports") or ""),
            )
            return True
        if pending.get("action") == "delete":
            page._start_user_profile_delete_worker(str(pending.get("profile_id") or ""))
            return True
        return page._start_next_pending_user_profile_write_operation()

    def _queue_user_profile_write_operation_from_dict(self, operation: dict[str, str]) -> bool:
        page = self._page
        pending = page._user_profile_write_operation_from_pending_operation(operation)
        page._queue_user_profile_write_operation(
            str(pending.get("action") or ""),
            profile_id=str(pending.get("profile_id") or ""),
            name=str(pending.get("name") or ""),
            protocol=str(pending.get("protocol") or ""),
            ports=str(pending.get("ports") or ""),
        )
        return True

    def _schedule_next_user_profile_write_operation_after_finish(
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

        operation = page._user_profile_write_state_obj().schedule_next_after_finish(
            worker,
            is_current_worker_finish=_is_current_worker_finish,
            single_shot=_single_shot,
            start=page._run_user_profile_write_operation,
            queue_item=page._queue_user_profile_write_operation_from_dict,
            is_cleanup_in_progress=lambda: bool(page.__dict__.get("_cleanup_in_progress", False)),
        )
        return accepted, operation is not None

    def _start_user_profile_update_worker(self, profile_id: str, *, name: str, protocol: str, ports: str) -> None:
        page = self._page
        runtime = page._worker_runtime("_user_profile_update_runtime")
        page._user_profile_update_request_id = int(getattr(page, "_user_profile_update_request_id", 0) or 0) + 1
        request_id = page._user_profile_update_request_id
        page._set_user_profile_buttons_enabled(False)
        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: page.create_profile_user_update_worker(
                request_id,
                profile_id=profile_id,
                name=name,
                protocol=protocol,
                ports=ports,
                parent=page,
            ),
            on_loaded=page._on_user_profile_update_finished,
            on_failed=page._on_user_profile_update_failed,
            on_finished=page._on_user_profile_update_worker_finished,
            loaded_signal_name="updated",
        )

    def _on_user_profile_update_finished(
        self,
        request_id: int,
        profile_id: str,
        changed: int,
        _profile_items=(),
    ) -> None:
        page = self._page
        if request_id != int(getattr(page, "_user_profile_update_request_id", 0) or 0):
            return
        if page._has_pending_user_profile_write_operation():
            return
        if str(profile_id or "").strip() != page._current_user_profile_id():
            return
        _page_module().InfoBar.success(
            title="Profile изменён",
            content=f"Обновлено profile-ов в preset-ах: {int(changed or 0)}.",
            parent=page.window(),
        )
        updated_item = _page_module()._updated_user_profile_item(profile_id, page._profile_key, _profile_items)
        if updated_item is not None:
            current_item = getattr(page.__dict__.get("_payload"), "item", None)
            if current_item == updated_item:
                return
            if not page._apply_user_profile_update_locally(updated_item):
                page.reload_current_profile()
                page._on_profile_changed_callback(page._profile_key, "user_profile_updated")
                return
            page._on_profile_changed_callback(page._profile_key, "user_profile_updated", updated_item)
            return
        page.reload_current_profile()
        page._on_profile_changed_callback(page._profile_key, "user_profile_updated")

    def _on_user_profile_update_failed(self, request_id: int, error: str) -> None:
        page = self._page
        if request_id != int(getattr(page, "_user_profile_update_request_id", 0) or 0):
            return
        if not page._has_pending_user_profile_write_operation():
            page._set_user_profile_buttons_enabled(True)
        _page_module().log(f"{page.__class__.__name__}: не удалось изменить пользовательский profile: {error}", "ERROR")
        _page_module().InfoBar.error(
            title="Ошибка",
            content=str(error),
            parent=page.window(),
        )

    def _on_user_profile_update_worker_finished(self, _worker) -> None:
        page = self._page
        accepted, scheduled = page._schedule_next_user_profile_write_operation_after_finish(
            "_user_profile_update_request_id",
            _worker,
        )
        if not accepted:
            return
        if scheduled:
            return
        page._set_user_profile_buttons_enabled(True)

    def _request_user_profile_delete(self, profile_id: str) -> None:
        page = self._page
        profile_id = str(profile_id or "").strip()
        if not profile_id:
            return
        runtime = page._worker_runtime("_user_profile_delete_runtime")
        if page._user_profile_write_operation_running():
            page._queue_user_profile_write_operation("delete", profile_id=profile_id)
            return
        page._start_user_profile_delete_worker(profile_id)

    def _start_user_profile_delete_worker(self, profile_id: str) -> None:
        page = self._page
        runtime = page._worker_runtime("_user_profile_delete_runtime")
        page._user_profile_delete_request_id = int(getattr(page, "_user_profile_delete_request_id", 0) or 0) + 1
        request_id = page._user_profile_delete_request_id
        page._set_user_profile_buttons_enabled(False)
        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: page.create_profile_user_delete_worker(
                request_id,
                profile_id=profile_id,
                parent=page,
            ),
            on_loaded=page._on_user_profile_delete_finished,
            on_failed=page._on_user_profile_delete_failed,
            on_finished=page._on_user_profile_delete_worker_finished,
            loaded_signal_name="deleted",
        )

    def _on_user_profile_delete_finished(self, request_id: int, profile_id: str, changed: int) -> None:
        page = self._page
        if request_id != int(getattr(page, "_user_profile_delete_request_id", 0) or 0):
            return
        if page._has_pending_user_profile_write_operation():
            return
        if str(profile_id or "").strip() != page._current_user_profile_id():
            return
        _page_module().InfoBar.success(
            title="Profile удалён",
            content=f"Удалено profile-ов из preset-ов: {int(changed or 0)}.",
            parent=page.window(),
        )
        page._on_profile_changed_callback(page._profile_key, "user_profile_deleted")
        page._open_profiles()

    def _on_user_profile_delete_failed(self, request_id: int, error: str) -> None:
        page = self._page
        if request_id != int(getattr(page, "_user_profile_delete_request_id", 0) or 0):
            return
        if not page._has_pending_user_profile_write_operation():
            page._set_user_profile_buttons_enabled(True)
        _page_module().log(f"{page.__class__.__name__}: не удалось удалить пользовательский profile: {error}", "ERROR")
        _page_module().InfoBar.error(
            title="Ошибка",
            content=str(error),
            parent=page.window(),
        )

    def _on_user_profile_delete_worker_finished(self, _worker) -> None:
        page = self._page
        accepted, scheduled = page._schedule_next_user_profile_write_operation_after_finish(
            "_user_profile_delete_request_id",
            _worker,
        )
        if not accepted:
            return
        if scheduled:
            return
        page._set_user_profile_buttons_enabled(True)
