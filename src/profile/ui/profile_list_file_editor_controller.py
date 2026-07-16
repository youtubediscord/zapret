"""Контроллер редактора файла списка (hostlist/ipset) страницы profile.

Вынесено из profile_setup_page.py (этап 4, фаза B, чанк M2): подсистемы
загрузки (C4), валидации (C5) и сохранения (C6) list-file одним блоком —
они разделяют снапшоты редактора.

Контроллер не владеет состоянием: state-объекты, рантаймы, счётчики
request_id, снапшоты и QTimer'ы живут на странице — поведенческие тесты
создают страницу через `__new__` и присваивают эти атрибуты напрямую.
Вызовы методов, которые тесты подменяют на экземпляре страницы, идут через
атрибут страницы (диспетчеризация через instance-словарь сохранена).
"""

from __future__ import annotations

from ui.latest_value_worker_state import LatestValueWorkerState


def _page_module():
    """Модуль страницы через ленивый импорт.

    Разрывает циклический импорт со страницей и сохраняет monkeypatch-цели
    `profile.ui.profile_setup_page.*`: module-функции и `log` патчатся
    тестами по пути модуля страницы и резолвятся здесь в момент вызова."""
    from profile.ui import profile_setup_page

    return profile_setup_page


class ProfileListFileEditorController:
    """Stateless-оркестратор list-file подсистемы со ссылкой на страницу."""

    def __init__(self, page) -> None:
        self._page = page

    def _request_list_file_editor_state(self) -> None:
        page = self._page
        if not page._editor_tab_built or not page._profile_key:
            return
        runtime = page._worker_runtime("_list_file_load_runtime")
        state = page._list_file_load_state_obj()
        if state.is_busy():
            state.pending = True
            return
        if page._list_file_status_label is not None:
            _page_module().set_profile_list_status_text(page._list_file_status_label, "Загрузка файла списка...")
        page._list_file_load_request_id = int(page.__dict__.get("_list_file_load_request_id", 0) or 0) + 1
        request_id = page._list_file_load_request_id
        # Пара фильтра, под которую загружается редактор. Автосохранение пишет
        # ТОЛЬКО в этот файл: текущее значение поля могло уже указывать на
        # другой файл, и сохранение по нему пересадило бы текст в чужой список.
        page._list_file_editor_filter = (page._current_filter_kind(), page._current_filter_value())
        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: page.create_profile_list_file_load_worker(
                request_id,
                page._profile_key,
                filter_kind=page._list_file_editor_filter[0],
                filter_value=page._list_file_editor_filter[1],
                parent=page,
            ),
            on_loaded=page._on_list_file_editor_state_loaded,
            on_failed=page._on_list_file_editor_state_failed,
            on_finished=page._on_list_file_worker_finished,
        )

    def _on_list_file_editor_state_loaded(self, request_id: int, result) -> None:
        page = self._page
        if request_id != page._list_file_load_request_id:
            return
        if page._list_file_load_state_obj().has_pending():
            return
        if not page._list_file_load_result_is_current(result):
            return
        state = getattr(result, "state", None)
        if state is None:
            # Профиль не разрешился (удалён/переименован во время загрузки):
            # молчание оставляло бы «Загрузка файла списка...» навсегда.
            if page._list_file_status_label is not None:
                _page_module().set_profile_list_status_text(
                    page._list_file_status_label,
                    "Ошибка загрузки файла списка: profile не найден.",
                )
            return
        page._list_file_dirty = False
        page._schedule_list_file_editor_state_apply(state)

    def _list_file_load_result_is_current(self, result) -> bool:
        # Результат — эхо ПОСЛЕДНЕГО запроса (контекст редактирования меняется
        # только через _request_list_file_editor_state: каждая мутация комбо,
        # поля значения и payload планирует перезагрузку). Сверять его с
        # текущими виджетами по именам файлов нельзя: сервис легитимно ремапит
        # пару при kind-switch превью (netrogat.txt → ipset-ru/dns/exclude),
        # и сравнение имён не сходилось бы никогда — вечная «Загрузка...».
        page = self._page
        result_profile_key = str(getattr(result, "profile_key", "") or "").strip()
        if result_profile_key != str(page.__dict__.get("_profile_key", "") or "").strip():
            return False
        captured_kind, captured_value = page._list_file_target_filter()
        result_filter_kind = str(getattr(result, "filter_kind", "") or "").strip().lower()
        result_filter_value = str(getattr(result, "filter_value", "") or "").strip()
        return (
            result_filter_kind == str(captured_kind or "").strip().lower()
            and result_filter_value == str(captured_value or "").strip()
        )

    def _schedule_list_file_editor_state_apply(self, state) -> None:
        page = self._page
        page._pending_list_file_state_apply = state
        if page.__dict__.get("_list_file_state_apply_scheduled", False):
            return
        page._list_file_state_apply_scheduled = True
        try:
            _page_module().QTimer.singleShot(0, page._run_scheduled_list_file_editor_state_apply)
        except Exception:
            page._run_scheduled_list_file_editor_state_apply()

    def _run_scheduled_list_file_editor_state_apply(self) -> None:
        page = self._page
        state = page.__dict__.get("_pending_list_file_state_apply")
        page._pending_list_file_state_apply = None
        page._list_file_state_apply_scheduled = False
        if state is None or page.__dict__.get("_cleanup_in_progress"):
            return
        if (
            page._list_file_load_state_obj().has_pending()
            or page._list_file_load_state_obj().start_scheduled
        ):
            return
        page._apply_list_file_editor_state(state)

    def _on_list_file_editor_state_failed(self, request_id: int, error: str) -> None:
        page = self._page
        if request_id != page._list_file_load_request_id:
            return
        if (
            page._list_file_load_state_obj().has_pending()
            or page._list_file_load_state_obj().start_scheduled
        ):
            return
        if page._list_file_status_label is not None:
            _page_module().set_profile_list_status_text(
                page._list_file_status_label,
                f"Ошибка загрузки файла списка: {error}",
            )

    def _schedule_pending_list_file_load_start(self) -> None:
        page = self._page
        state = page._list_file_load_state_obj()
        state.pending = True

        def _single_shot(delay: int, callback) -> None:
            try:
                _page_module().QTimer.singleShot(delay, callback)
            except Exception:
                callback()

        state.schedule_start(
            _single_shot,
            page._run_scheduled_list_file_load_start,
            pending_when_already_scheduled=True,
        )

    def _run_scheduled_list_file_load_start(self) -> None:
        page = self._page
        pending = page._list_file_load_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=page.__dict__.get("_cleanup_in_progress", False),
        )
        if not pending:
            return
        page._request_list_file_editor_state()

    def _list_file_load_state_obj(self) -> LatestValueWorkerState:
        page = self._page
        state = page.__dict__.get("_list_file_load_state")
        runtime = page.__dict__.get("_list_file_load_runtime")
        if state is None:
            pending = bool(page.__dict__.pop("_pending_list_file_load", False))
            start_scheduled = bool(page.__dict__.pop("_list_file_load_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=False,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            page.__dict__["_list_file_load_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    def _run_scheduled_list_file_validation(self) -> None:
        page = self._page
        if page._loading or page._list_file_text is None:
            return
        page._request_list_file_validation({
            "kind": page._list_file_kind,
            "text": None,
        })

    def _request_list_file_validation(self, request: dict) -> None:
        page = self._page
        state = page._list_file_validation_state_obj()
        if state.is_busy():
            state.pending = dict(request)
            return
        page._start_list_file_validation_worker(request)

    def _resolve_list_file_validation_request(self, request: dict) -> dict[str, str]:
        page = self._page
        request = dict(request or {})
        raw_text = request.get("text")
        if raw_text is None:
            text = page._current_list_file_text()
        else:
            text = str(raw_text or "")
        return {
            "kind": str(request.get("kind") or ""),
            "text": text,
        }

    def _start_list_file_validation_worker(self, request: dict) -> None:
        page = self._page
        request = page._resolve_list_file_validation_request(request)
        runtime = page._worker_runtime("_list_file_validation_runtime")
        page._list_file_validation_request_id = int(getattr(page, "_list_file_validation_request_id", 0) or 0) + 1
        request_id = page._list_file_validation_request_id
        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: page.create_profile_list_file_validation_worker(
                request_id,
                kind=str(request.get("kind") or ""),
                text=str(request.get("text") or ""),
                parent=page,
            ),
            on_loaded=page._on_list_file_validation_finished,
            on_failed=page._on_list_file_validation_failed,
            on_finished=page._on_list_file_validation_worker_finished,
            loaded_signal_name="validated",
        )

    def _on_list_file_validation_finished(
        self,
        request_id: int,
        kind: str,
        text: str,
        invalid_lines,
    ) -> None:
        page = self._page
        if request_id != int(getattr(page, "_list_file_validation_request_id", 0) or 0):
            return
        if page._list_file_validation_state_obj().has_pending():
            return
        if str(kind or "").strip() != str(getattr(page, "_list_file_kind", "") or "").strip():
            return
        # Поздний результат по устаревшему тексту отбрасывается: пока воркер
        # работал, пользователь мог успеть напечатать новое — сравниваем с
        # живым текстом редактора, а не с моментом запуска валидации.
        if str(text or "") != page._current_list_file_text():
            return
        validation_result = invalid_lines
        if isinstance(validation_result, dict):
            invalid_lines = tuple(validation_result.get("invalid_lines") or ())
            try:
                page._list_file_user_entries_count = int(validation_result.get("entries_count") or 0)
            except (TypeError, ValueError):
                page._list_file_user_entries_count = 0
        else:
            invalid_lines = tuple(validation_result or ())
        # Флаг означает «ТЕКСТ невалиден» и выставляется только валидацией.
        # Ошибка ЗАПИСИ его не трогает: валидные правки при неудавшемся
        # сохранении обязаны уйти на диск при следующем флаше.
        page._list_file_validation_has_error = bool(invalid_lines)
        page._render_list_file_validation(tuple(invalid_lines or ()))
        if page._list_file_save_button is not None:
            editable = page._list_file_text is not None and not page._list_file_text.isReadOnly()
            _page_module().set_widget_enabled_if_changed(page._list_file_save_button, not invalid_lines and editable)
        if page._list_file_status_label is not None:
            if invalid_lines:
                _page_module().set_profile_list_status_text(
                    page._list_file_status_label,
                    "Исправьте ошибки перед сохранением.",
                )
            else:
                user_count = int(page.__dict__.get("_list_file_user_entries_count", 0) or 0)
                base_count = int(page.__dict__.get("_list_file_base_entries_count", 0) or 0)
                _page_module().set_profile_list_status_text(
                    page._list_file_status_label,
                    f"Записей всего: {base_count + user_count} • ваших: {user_count} • есть несохранённые изменения",
                )
        if not invalid_lines:
            page._maybe_autosave_list_file()

    def _unsaved_list_file_text(self) -> str | None:
        """Текст редактора, ещё не подтверждённый сервером, либо None.

        Пока серверный текст неизвестен (None), сохранять нечего: снапшот
        может относиться к ещё не загруженному файлу."""
        page = self._page
        editor = page.__dict__.get("_list_file_text")
        if editor is None or editor.isReadOnly():
            return None
        server_snapshot = page.__dict__.get("_list_file_server_text_snapshot")
        if not isinstance(server_snapshot, str):
            return None
        snapshot = page._current_list_file_text()
        return None if snapshot == server_snapshot else snapshot

    def _list_file_target_filter(self) -> tuple[str, str]:
        """Пара (kind, value), под которую загружен текущий текст редактора."""
        page = self._page
        pair = page.__dict__.get("_list_file_editor_filter")
        if isinstance(pair, tuple) and len(pair) == 2:
            return str(pair[0] or ""), str(pair[1] or "")
        return page._current_filter_kind(), page._current_filter_value()

    def _maybe_autosave_list_file(self) -> None:
        """Автосохранение вместо кнопки: валидный текст с несохранёнными
        правками уходит на диск сам. «Несохранённость» — производная от
        server_text_snapshot, поэтому цикл сохранений не возникает: после
        успешной записи снапшоты совпадают и повторный вызов — no-op."""
        page = self._page
        if bool(page.__dict__.get("_loading", False)) or not str(page.__dict__.get("_profile_key", "") or ""):
            return
        snapshot = page._unsaved_list_file_text()
        if snapshot is None:
            return
        target_kind, target_value = page._list_file_target_filter()
        page._request_list_file_save(
            page._profile_key,
            snapshot,
            filter_kind=target_kind,
            filter_value=target_value,
        )

    def _flush_list_file_autosave_before_switch(self, previous_key: str) -> None:
        """Уход с профиля не должен терять валидные несохранённые домены:
        отправляем их на запись по СТАРОЙ ссылке до сброса снапшотов.
        Результат к редактору нового профиля не применится — его отсечёт
        guard по _list_file_save_profile_key."""
        page = self._page
        previous = str(previous_key or "").strip()
        if not previous or bool(page.__dict__.get("_list_file_validation_has_error", False)):
            return
        snapshot = page._unsaved_list_file_text()
        if snapshot is None:
            return
        target_kind, target_value = page._list_file_target_filter()
        page._request_list_file_save(
            previous,
            snapshot,
            filter_kind=target_kind,
            filter_value=target_value,
        )

    def _on_list_file_validation_failed(self, request_id: int, error: str) -> None:
        page = self._page
        if request_id != int(getattr(page, "_list_file_validation_request_id", 0) or 0):
            return
        if page._list_file_validation_state_obj().has_pending():
            return
        _page_module().log(f"{page.__class__.__name__}: не удалось проверить файл списка profile: {error}", "ERROR")
        # Валидность неизвестна — консервативно блокируем автосейв/флаш.
        page._list_file_validation_has_error = True
        page._render_list_file_validation((), fallback_error=str(error))
        if page._list_file_save_button is not None:
            _page_module().set_widget_enabled_if_changed(page._list_file_save_button, False)
        if page._list_file_status_label is not None:
            _page_module().set_profile_list_status_text(page._list_file_status_label, "Ошибка проверки списка.")

    def _schedule_pending_list_file_validation_start(self) -> None:
        page = self._page
        state = page._list_file_validation_state_obj()

        def _single_shot(delay: int, callback) -> None:
            try:
                _page_module().QTimer.singleShot(delay, callback)
            except Exception:
                callback()

        state.schedule_start(_single_shot, page._run_scheduled_list_file_validation_start)

    def _run_scheduled_list_file_validation_start(self) -> None:
        page = self._page
        pending = page._list_file_validation_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=page.__dict__.get("_cleanup_in_progress", False),
        )
        if not pending:
            return
        page._start_list_file_validation_worker(dict(pending or {}))

    def _list_file_validation_state_obj(self) -> LatestValueWorkerState:
        page = self._page
        state = page.__dict__.get("_list_file_validation_state")
        runtime = page.__dict__.get("_list_file_validation_runtime")
        if state is None:
            pending = page.__dict__.pop("_pending_list_file_validation", None)
            start_scheduled = bool(page.__dict__.pop("_list_file_validation_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=None,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            page.__dict__["_list_file_validation_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    def _request_list_file_save(
        self,
        profile_key: str,
        text: str,
        *,
        filter_kind: str = "",
        filter_value: str = "",
    ) -> None:
        page = self._page
        request = _page_module()._list_file_save_request(
            profile_key,
            text,
            filter_kind=filter_kind,
            filter_value=filter_value,
        )
        if not request["profile_key"]:
            return
        if page._profile_setup_write_is_running():
            state = page._list_file_save_state_obj()
            if not (state.start_scheduled and state.has_pending()):
                state.pending = request
            page._queue_profile_setup_write_operation(
                {"kind": "list_file_save", **request}
            )
            return
        page._start_list_file_save_worker(
            request["profile_key"],
            request["text"],
            filter_kind=request["filter_kind"],
            filter_value=request["filter_value"],
        )

    def _start_list_file_save_worker(
        self,
        profile_key: str,
        text: str,
        *,
        filter_kind: str = "",
        filter_value: str = "",
    ) -> None:
        page = self._page
        runtime = page._worker_runtime("_list_file_save_runtime")
        page._list_file_save_request_id += 1
        request_id = page._list_file_save_request_id
        page._list_file_save_profile_key = str(profile_key or "").strip()
        page._list_file_save_filter = (str(filter_kind or "").strip(), str(filter_value or "").strip())
        if page._list_file_status_label is not None:
            _page_module().set_profile_list_status_text(page._list_file_status_label, "Сохранение списка...")
        if page._list_file_save_button is not None:
            _page_module().set_widget_enabled_if_changed(page._list_file_save_button, False)
        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: page.create_profile_list_file_save_worker(
                request_id,
                profile_key,
                str(text or ""),
                filter_kind=filter_kind,
                filter_value=filter_value,
                parent=page,
            ),
            on_loaded=page._on_list_file_save_finished,
            on_failed=page._on_list_file_save_failed,
            on_finished=page._on_list_file_save_worker_finished,
            loaded_signal_name="saved",
        )

    def _on_list_file_save_finished(self, request_id: int, state, payload=None) -> None:
        page = self._page
        if request_id != page._list_file_save_request_id:
            return
        if page._list_file_save_state_obj().has_pending():
            return
        saved_for = str(page.__dict__.get("_list_file_save_profile_key", "") or "")
        if saved_for and saved_for != str(page.__dict__.get("_profile_key", "") or ""):
            # Флаш при переключении профиля: запись на диск состоялась, но её
            # state нельзя применять к редактору другого профиля. Остальные
            # страницы всё же должны узнать об изменении файла.
            page._on_profile_changed_callback(saved_for, "list_file")
            return
        saved_filter = page.__dict__.get("_list_file_save_filter")
        if isinstance(saved_filter, tuple) and saved_filter != page._list_file_target_filter():
            # Флаш при смене фильтра: state старого файла не должен откатывать
            # редактор, уже показывающий другой файл.
            page._on_profile_changed_callback(page._profile_key, "list_file")
            return
        payload, apply_signature = _page_module()._profile_setup_payload_and_apply_signature(payload)
        if state is not None:
            page._apply_list_file_editor_state(state)
        if page._list_file_status_label is not None:
            _page_module().set_profile_list_status_text(page._list_file_status_label, "Список сохранён.")
        if payload is None:
            page.reload_current_profile()
            page._on_profile_changed_callback(page._profile_key, "list_file")
        elif page.__dict__.get("_payload") is payload:
            pass
        else:
            page._payload = payload
            page._schedule_profile_setup_payload_apply(payload, apply_signature=apply_signature)
            page._on_profile_changed_callback(page._profile_key, "list_file", getattr(payload, "item", None))
        _page_module().InfoBar.success(
            title="Список сохранён",
            content="Файл списка обновлён.",
            parent=page.window(),
        )

    def _on_list_file_save_failed(self, request_id: int, error: str) -> None:
        page = self._page
        if request_id != page._list_file_save_request_id:
            return
        if page._list_file_save_state_obj().has_pending():
            return
        _page_module().log(f"{page.__class__.__name__}: не удалось сохранить файл списка profile: {error}", "ERROR")
        page._render_list_file_validation((), fallback_error=str(error))
        if page._list_file_save_button is not None:
            _page_module().set_widget_enabled_if_changed(page._list_file_save_button, True)
        _page_module().InfoBar.error(title="Ошибка", content=str(error), parent=page.window())

    def _on_list_file_save_worker_finished(self, worker) -> None:
        page = self._page
        accepted, scheduled = page._schedule_next_profile_setup_write_operation_after_finish(
            "_list_file_save_request_id",
            worker,
        )
        if not accepted:
            return
        if scheduled:
            return
        if page._list_file_save_state_obj().has_pending():
            page._schedule_pending_list_file_save_start()

    def _schedule_pending_list_file_save_start(
        self,
        profile_key: str | None = None,
        text: str | None = None,
        *,
        filter_kind: str | None = None,
        filter_value: str | None = None,
    ) -> None:
        page = self._page
        state = page._list_file_save_state_obj()
        if profile_key is not None or text is not None or filter_kind is not None or filter_value is not None:
            state.pending = _page_module()._list_file_save_request(
                str(profile_key or ""),
                str(text or ""),
                filter_kind=str(filter_kind or ""),
                filter_value=str(filter_value or ""),
            )

        def _single_shot(delay: int, callback) -> None:
            try:
                _page_module().QTimer.singleShot(delay, callback)
            except Exception:
                callback()

        state.schedule_start(_single_shot, page._run_scheduled_list_file_save_start)

    def _run_scheduled_list_file_save_start(self) -> None:
        page = self._page
        pending = page._list_file_save_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=page.__dict__.get("_cleanup_in_progress", False),
        )
        if not pending:
            return
        request = _page_module()._normalized_list_file_save_request(pending)
        profile_key = request["profile_key"]
        if not profile_key:
            return
        if page._profile_setup_write_is_running():
            page._list_file_save_state_obj().pending = request
            page._queue_profile_setup_write_operation(
                {
                    "kind": "list_file_save",
                    **request,
                }
            )
            return
        page._start_list_file_save_worker(
            profile_key,
            request["text"],
            filter_kind=request["filter_kind"],
            filter_value=request["filter_value"],
        )

    def _list_file_save_state_obj(self) -> LatestValueWorkerState:
        page = self._page
        state = page.__dict__.get("_list_file_save_state")
        runtime = page.__dict__.get("_list_file_save_runtime")
        if state is None:
            pending = page.__dict__.pop("_pending_list_file_save", None)
            scheduled = page.__dict__.pop("_scheduled_list_file_save", None)
            start_scheduled = bool(page.__dict__.pop("_list_file_save_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=None,
                pending=scheduled if scheduled is not None else pending,
                start_scheduled=start_scheduled,
            )
            page.__dict__["_list_file_save_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state
