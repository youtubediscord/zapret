from __future__ import annotations

from PyQt6.QtCore import QTimer

from log.log import log
from ui.queued_worker_state import QueuedWorkerState


class ProfileFolderController:
    """Очередь folder actions списка профилей (rename/move/collapse и т.п.).

    Контроллер не владеет состоянием: QueuedWorkerState, runtime и счётчик
    request_id живут на странице — поведенческие тесты создают страницу через
    `__new__` и присваивают эти атрибуты напрямую. Контроллер — оркестратор:
    читает состояние через stub-устойчивые аксессоры страницы и вызывает её
    UI-колбэки. Finish применяет `folder_state` точечно
    (`_apply_profile_folder_state_locally`), полная перезагрузка — только
    fallback при неуспехе. Вызовы методов, которые тесты подменяют на
    экземпляре страницы (`_show_folder_menu_with_state`,
    `_schedule_profile_folder_action_start` и т.п.), идут через атрибут
    страницы, чтобы сохранить диспетчеризацию через instance-словарь.
    """

    def __init__(self, page) -> None:
        self._page = page

    def _profile_folder_action_state_obj(self) -> QueuedWorkerState[dict[str, object]]:
        # Состояние создаётся эагерно в __init__ страницы; ленивая ветка нужна
        # только duck-typed стабам из тестов (__new__ без __init__).
        page = self._page
        state = page.__dict__.get("_profile_folder_action_state")
        runtime = page.__dict__.get("_profile_folder_action_runtime")
        if state is None:
            state = QueuedWorkerState(runtime)
            page.__dict__["_profile_folder_action_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    def _request_profile_folder_action(
        self,
        action: str,
        *,
        folder_key: str = "",
        name: str = "",
        direction: int = 0,
        collapsed: bool = False,
        collapsed_by_key: dict[str, bool] | None = None,
        refresh: bool = True,
        context_extra: dict | None = None,
    ) -> None:
        page = self._page
        runtime = page._worker_runtime("_profile_folder_action_runtime")
        payload = {
            "action": str(action or ""),
            "folder_key": str(folder_key or ""),
            "name": str(name or ""),
            "direction": int(direction or 0),
            "collapsed": bool(collapsed),
            "refresh": bool(refresh),
            "context_extra": dict(context_extra or {}),
        }
        collapsed_map = {
            str(key or "").strip(): bool(value)
            for key, value in dict(collapsed_by_key or {}).items()
            if str(key or "").strip()
        }
        if collapsed_map:
            payload["collapsed_by_key"] = collapsed_map
        if page._profile_folder_action_state_obj().is_busy():
            self._queue_profile_folder_action(payload)
            return
        page._profile_folder_action_request_id = int(
            page.__dict__.get("_profile_folder_action_request_id", 0) or 0
        ) + 1
        request_id = page._profile_folder_action_request_id
        page._profile_folder_action_refresh_map()[request_id] = bool(refresh)

        def _bind_worker(worker) -> None:
            worker.completed.connect(self._on_profile_folder_action_finished)
            worker.failed.connect(page._on_profile_folder_action_failed)

        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: page._create_profile_folder_action_worker(
                request_id,
                action=str(action or ""),
                folder_key=str(folder_key or ""),
                name=str(name or ""),
                direction=int(direction or 0),
                collapsed=bool(collapsed),
                collapsed_by_key={
                    str(key or "").strip(): bool(value)
                    for key, value in dict(collapsed_by_key or {}).items()
                    if str(key or "").strip()
                },
                context_extra=dict(context_extra or {}),
            ),
            bind_worker=_bind_worker,
            on_finished=page._on_profile_folder_action_worker_finished,
        )

    def _queue_profile_folder_action(self, payload: dict[str, object]) -> None:
        """Постановка в очередь с дедупом: повторный collapse той же папки и
        массовый collapse схлопывают устаревшие записи."""
        page = self._page
        queued = dict(payload or {})
        action = str(queued.get("action") or "")
        folder_key = str(queued.get("folder_key") or "")
        pending = page._profile_folder_action_state_obj().pending
        if action == "move" and queued in pending:
            return
        if action == "set_collapsed" and folder_key:
            pending[:] = [
                item
                for item in pending
                if not (
                    str(item.get("action") or "") == "set_collapsed"
                    and str(item.get("folder_key") or "") == folder_key
                )
            ]
        if action == "set_collapsed_many":
            collapsed_by_key = dict(queued.get("collapsed_by_key") or {})
            changed_keys = {
                str(key or "").strip()
                for key in collapsed_by_key.keys()
                if str(key or "").strip()
            }
            pending[:] = [
                item
                for item in pending
                if not (
                    str(item.get("action") or "") == "set_collapsed_many"
                    or (
                        str(item.get("action") or "") == "set_collapsed"
                        and str(item.get("folder_key") or "") in changed_keys
                    )
                )
            ]
        pending.append(queued)

    def _on_profile_folder_action_finished(self, request_id: int, action: str, result, context) -> None:
        page = self._page
        if request_id != int(getattr(page, "_profile_folder_action_request_id", 0) or 0):
            return
        if page._profile_folder_action_state_obj().has_pending():
            page._profile_folder_action_refresh_map().pop(request_id, None)
            return
        context = dict(context or {})
        folder_state = result if isinstance(result, dict) else context.get("folder_state")
        should_refresh = bool(
            page._profile_folder_action_refresh_map().pop(request_id, True)
        )
        if str(action or "") == "load_state" and bool(context.get("show_menu")):
            page._show_folder_menu_with_state(
                str(context.get("folder_key") or ""),
                context.get("global_pos"),
                result if isinstance(result, dict) else {},
            )
            return
        if bool(result) and should_refresh:
            if isinstance(folder_state, dict) and page._apply_profile_folder_state_locally(folder_state):
                return
            page._fallback_full_reload()

    def _on_profile_folder_action_failed(self, request_id: int, action: str, error: str, _context) -> None:
        page = self._page
        if request_id != int(getattr(page, "_profile_folder_action_request_id", 0) or 0):
            return
        if page._profile_folder_action_state_obj().has_pending():
            page._profile_folder_action_refresh_map().pop(request_id, None)
            return
        page._profile_folder_action_refresh_map().pop(request_id, None)
        log(f"{page.__class__.__name__}: не удалось выполнить действие папки profile ({action}): {error}", "ERROR")

    def _on_profile_folder_action_worker_finished(self, worker) -> None:
        page = self._page
        if not page._accept_current_preset_setup_worker_finished("_profile_folder_action_request_id", worker):
            return
        if not page._is_cleanup_in_progress():
            pending = page._profile_folder_action_state_obj().pop_next()
        else:
            pending = None
        if pending:
            page._schedule_profile_folder_action_start(pending)

    def _schedule_profile_folder_action_start(self, pending: dict[str, object]) -> None:
        page = self._page
        queued = dict(pending or {})
        state = page._profile_folder_action_state_obj()

        def _single_shot(delay: int, callback) -> None:
            try:
                QTimer.singleShot(delay, callback)
            except Exception:
                callback()

        state.schedule_start(
            queued,
            _single_shot,
            self._run_scheduled_profile_folder_action_start,
            queue_item=self._queue_profile_folder_action,
            is_cleanup_in_progress=lambda: bool(page._is_cleanup_in_progress()),
        )

    def _run_scheduled_profile_folder_action_start(self, pending: dict[str, object]) -> None:
        page = self._page
        page._profile_folder_action_state_obj().start_scheduled = False
        if page._is_cleanup_in_progress():
            return
        page._request_profile_folder_action(
            str(pending.get("action") or ""),
            folder_key=str(pending.get("folder_key") or ""),
            name=str(pending.get("name") or ""),
            direction=int(pending.get("direction") or 0),
            collapsed=bool(pending.get("collapsed")),
            collapsed_by_key=(
                dict(pending.get("collapsed_by_key") or {})
                if "collapsed_by_key" in pending
                else None
            ),
            refresh=bool(pending.get("refresh", True)),
            context_extra=dict(pending.get("context_extra") or {}),
        )
