"""Контроллер загрузки payload страницы настройки profile.

Вынесено из profile_setup_page.py (этап 4, фаза B, чанк M6): машина загрузки
C9 (request/start/loaded/failed/deferred-apply/scheduled-start).
Применение payload (`_apply_payload`, C10 fan-out) остаётся методом страницы.

Контроллер не владеет состоянием: state-объект, runtime и счётчики
request_id живут на странице — поведенческие тесты создают страницу через
`__new__` и присваивают эти атрибуты напрямую. Вызовы методов, которые
тесты подменяют на экземпляре страницы, идут через атрибут страницы.
"""

from __future__ import annotations

from ui.latest_value_worker_state import LatestValueWorkerState


def _page_module():
    """Модуль страницы через ленивый импорт.

    Разрывает циклический импорт со страницей и сохраняет monkeypatch-цели
    `profile.ui.profile_setup_page.*`: module-функции, `log`, `QTimer` и
    `InfoBar` патчатся тестами по пути модуля страницы и резолвятся здесь
    в момент вызова."""
    from profile.ui import profile_setup_page

    return profile_setup_page


class ProfileSetupPayloadController:
    """Stateless-оркестратор загрузки payload со ссылкой на страницу."""

    def __init__(self, page) -> None:
        self._page = page

    def _request_profile_setup_payload(self) -> None:
        page = self._page
        if not page._profile_key:
            return
        if page._setup_load_state_obj().is_busy():
            page._setup_load_request_id += 1
            page._setup_load_state_obj().pending = True
            return

        page._start_profile_setup_load_worker()

    def _start_profile_setup_load_worker(self) -> None:
        page = self._page
        if not page._profile_key:
            return
        page._setup_load_request_id += 1
        request_id = page._setup_load_request_id
        _page_module().set_widget_text_if_changed(page._summary, "Загрузка profile...")
        _page_module().set_widget_enabled_if_changed(page._enabled_checkbox, False)
        runtime = page._worker_runtime("_setup_load_runtime")
        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: page.create_profile_setup_load_worker(
                request_id,
                page._profile_key,
                page,
            ),
            on_loaded=page._on_profile_setup_payload_loaded,
            on_failed=page._on_profile_setup_payload_failed,
            on_finished=page._on_profile_setup_worker_finished,
        )
        page._setup_load_runtime_request_id = request_id

    def _on_profile_setup_payload_loaded(self, request_id: int, payload) -> None:
        page = self._page
        if request_id != page._setup_load_request_id:
            return
        if page._setup_load_state_obj().has_pending():
            return
        payload, apply_signature = _page_module()._profile_setup_payload_and_apply_signature(payload)
        if payload is None:
            _page_module().set_widget_text_if_changed(
                page._summary,
                "Профиль не найден. Вернитесь к списку и выберите profile заново.",
            )
            _page_module().set_widget_enabled_if_changed(page._enabled_checkbox, False)
            return
        if (
            apply_signature is not None
            and page.__dict__.get("_last_profile_setup_payload_apply_signature") == apply_signature
        ):
            page._restore_loaded_payload_header(payload)
            return
        if payload == page.__dict__.get("_payload"):
            page._restore_loaded_payload_header(payload)
            return
        page._payload = payload
        page._profile_key = page._profile_result_reference(
            payload,
            str(page.__dict__.get("_profile_key", "") or ""),
        )
        page._schedule_profile_setup_payload_apply(payload, apply_signature=apply_signature)

    def _schedule_profile_setup_payload_apply(self, payload, *, apply_signature=None) -> None:
        page = self._page
        page._pending_profile_setup_payload_apply = (
            payload,
            tuple(apply_signature) if apply_signature is not None else None,
        )
        if page.__dict__.get("_profile_setup_payload_apply_scheduled", False):
            return
        page._profile_setup_payload_apply_scheduled = True
        try:
            _page_module().QTimer.singleShot(0, page._run_scheduled_profile_setup_payload_apply)
        except Exception:
            page._run_scheduled_profile_setup_payload_apply()

    def _run_scheduled_profile_setup_payload_apply(self) -> None:
        page = self._page
        pending = page.__dict__.get("_pending_profile_setup_payload_apply")
        page._pending_profile_setup_payload_apply = None
        page._profile_setup_payload_apply_scheduled = False
        if isinstance(pending, tuple) and len(pending) == 2:
            payload, apply_signature = pending
        else:
            payload = pending
            apply_signature = None
        if payload is None or page.__dict__.get("_cleanup_in_progress"):
            return
        if (
            page._setup_load_state_obj().has_pending()
            or page._setup_load_state_obj().start_scheduled
        ):
            return
        if (
            apply_signature is not None
            and page.__dict__.get("_last_profile_setup_payload_apply_signature") == apply_signature
        ):
            page._restore_loaded_payload_header(payload)
            return
        page._apply_payload(payload)
        if apply_signature is not None:
            page._last_profile_setup_payload_apply_signature = apply_signature

    def _on_profile_setup_payload_failed(self, request_id: int, error: str) -> None:
        page = self._page
        if request_id != page._setup_load_request_id:
            return
        if (
            page._setup_load_state_obj().has_pending()
            or page._setup_load_state_obj().start_scheduled
        ):
            return
        _page_module().log(f"{page.__class__.__name__}: не удалось прочитать профиль {page._profile_key}: {error}", "ERROR")
        _page_module().set_widget_text_if_changed(
            page._summary,
            "Профиль не найден. Вернитесь к списку и выберите profile заново.",
        )
        _page_module().set_widget_enabled_if_changed(page._enabled_checkbox, False)

    def _accept_current_profile_setup_load_worker_finished(self, worker) -> bool:
        page = self._page
        request_id = getattr(worker, "_request_id", None)
        if request_id is None:
            return False
        try:
            current_request_id = int(page.__dict__.get("_setup_load_runtime_request_id", 0) or 0)
            if int(request_id) != current_request_id:
                return False
        except (TypeError, ValueError):
            return False
        page._setup_load_runtime_request_id = 0
        return True

    def _schedule_profile_setup_load_start(self) -> None:
        page = self._page
        state = page._setup_load_state_obj()
        state.pending = True

        def _single_shot(delay: int, callback) -> None:
            try:
                _page_module().QTimer.singleShot(delay, callback)
            except Exception:
                callback()

        state.schedule_start(
            _single_shot,
            page._run_scheduled_profile_setup_load_start,
            pending_when_already_scheduled=True,
        )

    def _run_scheduled_profile_setup_load_start(self) -> None:
        page = self._page
        pending = page._setup_load_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=page.__dict__.get("_cleanup_in_progress", False),
        )
        if not pending:
            return
        page._request_profile_setup_payload()

    def _setup_load_state_obj(self) -> LatestValueWorkerState:
        page = self._page
        state = page.__dict__.get("_setup_load_state")
        runtime = page.__dict__.get("_setup_load_runtime")
        if state is None:
            pending = bool(page.__dict__.pop("_setup_load_dirty", False))
            start_scheduled = bool(page.__dict__.pop("_setup_load_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=False,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            page.__dict__["_setup_load_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state
