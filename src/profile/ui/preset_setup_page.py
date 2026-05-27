from __future__ import annotations

import time

from PyQt6.QtCore import QTimer

from log.log import log
from profile.folders import set_profile_folder_collapsed
from profile.match_filters import filter_values
from profile.ui.profile_context_menu import ProfileContextMenuActions, show_profile_context_menu
from profile.ui.profile_folder_menu import show_profile_folder_menu
from profile.profile_setup_loader import (
    ProfilePresetProfileActionWorker,
    ProfilePresetProfileMoveWorker,
    ProfileUserProfileCreateWorker,
    ProfileUserProfileDeleteWorker,
    ProfileUserProfileUpdateWorker,
)
from profile.ui.profiles_list import ProfilesList
from profile.ui.shell import build_profile_shell
from profile.ui.user_profile_dialog import CreateUserProfileDialog
from qfluentwidgets import BodyLabel, InfoBar, MessageBox
from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE
from ui.pages.base_page import BasePage
from app.ui_texts import tr as tr_catalog


def preset_setup_title_for_payload(payload, default_title: str = "Настройка пресета") -> str:
    preset_name = str(getattr(payload, "selected_preset_name", "") or "").strip()
    if not preset_name:
        preset_name = str(getattr(payload, "selected_preset_file_name", "") or "").strip()
    if not preset_name:
        return default_title
    return f"{default_title}: {preset_name}"


class PresetSetupPageBase(BasePage):
    profile_ui_mode_override: str | None = None
    launch_method = ZAPRET2_MODE
    engine_label = "Zapret 2"
    page_title = "Настройка пресета"
    title_key = "page.winws2_pages.title"
    control_key = "page.winws2_pages.back.control"
    toolbar_title_key = "page.winws2_pages.toolbar.title"
    request_button_key = "page.winws2_pages.request.button"
    request_hint_key = "page.winws2_pages.request.hint"
    loading_key = "page.winws2_pages.loading"

    def __init__(self, parent=None, *, profile_feature, open_profile_setup, open_profile_order, ui_state_store=None):
        super().__init__(
            title=self.page_title,
            parent=parent,
            title_key=self.title_key,
        )
        self._profile = profile_feature
        self._open_profile_setup = open_profile_setup
        self._open_profile_order_page = open_profile_order

        self._profiles_list: ProfilesList | None = None
        self._empty_state_label = None
        self._content_host_layout = None
        self._expand_btn = None
        self._collapse_btn = None
        self._request_btn = None
        self._info_btn = None
        self._add_profile_btn = None
        self._profile_search_input = None
        self._profile_search_query = ""
        self._toolbar_actions_bar = None
        self._profile_load_request_id = 0
        self._profile_load_worker = None
        self._profile_context_action_request_id = 0
        self._profile_context_action_worker = None
        self._profile_move_request_id = 0
        self._profile_move_worker = None
        self._user_profile_create_request_id = 0
        self._user_profile_create_worker = None
        self._user_profile_update_request_id = 0
        self._user_profile_update_worker = None
        self._user_profile_delete_request_id = 0
        self._user_profile_delete_worker = None
        self._profile_payload_loaded_once = False
        self._profile_payload_dirty = True
        self._cleanup_in_progress = False
        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._build_content()
        self.bind_ui_state_store(ui_state_store)

    def on_page_activated(self) -> None:
        self._schedule_profiles_payload_request()

    def _schedule_profiles_payload_request(self, *, force: bool = False) -> None:
        try:
            QTimer.singleShot(0, lambda: self._request_profiles_payload(force=force))
        except Exception:
            self._request_profiles_payload(force=force)

    def _build_content(self) -> None:
        shell = build_profile_shell(
            content_parent=self.content,
            content_layout=self.layout,
            add_section_title=self.add_section_title,
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            engine_label=self.engine_label,
            toolbar_title_key=self.toolbar_title_key,
            request_button_key=self.request_button_key,
            request_hint_key=self.request_hint_key,
            loading_key=self.loading_key,
            on_open_profile_request_form=self._show_profile_info,
            on_add_user_profile=self._on_add_user_profile_clicked,
            on_expand_all=self._expand_all,
            on_collapse_all=self._collapse_all,
            on_open_profile_order=self._open_profile_order,
            on_show_info_popup=self._show_profile_info,
            on_profile_search_text_changed=self._on_profile_search_text_changed,
        )
        self._toolbar_actions_bar = shell.toolbar_actions_bar
        self._add_profile_btn = shell.add_profile_btn
        self._request_btn = shell.request_btn
        self._expand_btn = shell.expand_btn
        self._collapse_btn = shell.collapse_btn
        self._info_btn = shell.info_btn
        self._profile_search_input = shell.profile_search_input
        self._content_host_layout = shell.content_host_layout

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refresh_toolbar_layout()

    def _refresh_toolbar_layout(self) -> None:
        toolbar = self._toolbar_actions_bar
        if toolbar is None:
            return
        try:
            toolbar.refresh_for_viewport(self.viewport().width(), self.layout.contentsMargins())
        except Exception:
            pass

    def refresh_from_preset_switch(self) -> None:
        self._request_profiles_payload(force=True)

    def bind_ui_state_store(self, store) -> None:
        if self._ui_state_store is store:
            return
        unsubscribe = self._ui_state_unsubscribe
        if callable(unsubscribe):
            try:
                unsubscribe()
            except Exception:
                pass
        self._ui_state_store = store
        self._ui_state_unsubscribe = None
        if store is None:
            return
        self._ui_state_unsubscribe = store.subscribe(
            self._on_ui_state_changed,
            fields={"active_preset_revision", "preset_content_revision"},
            emit_initial=False,
        )

    def _on_ui_state_changed(self, _state, changed: frozenset[str]) -> None:
        if self._cleanup_in_progress:
            return
        if not (changed & {"active_preset_revision", "preset_content_revision"}):
            return
        self._profile_payload_dirty = True
        if self.isVisible():
            self._request_profiles_payload(force=True)

    def _request_profiles_payload(self, *, force: bool = False) -> None:
        if self._cleanup_in_progress:
            return
        if not force and self._profile_payload_loaded_once and not self._profile_payload_dirty:
            return
        self._profile_payload_dirty = True
        cached_payload = self._profile.get_cached_profile_list(self.launch_method)
        if cached_payload is not None:
            self._apply_cached_profile_payload(cached_payload)
            return
        worker = self._profile_load_worker
        if worker is not None:
            try:
                if worker.isRunning():
                    if force:
                        self._profile_payload_dirty = True
                        self._profile_load_request_id += 1
                    return
            except Exception:
                return
        self._profile_load_request_id += 1
        request_id = self._profile_load_request_id
        if self._profiles_list is None:
            self._clear_dynamic_widgets()
        worker = self._profile.create_profile_list_load_worker(request_id, self.launch_method, self)
        self._profile_load_worker = worker
        worker.loaded.connect(self._on_profile_payload_loaded)
        worker.failed.connect(self._on_profile_payload_failed)
        worker.finished.connect(lambda w=worker: self._on_profile_worker_finished(w))
        worker.start()

    def _on_profile_payload_loaded(self, request_id: int, payload) -> None:
        if request_id != self._profile_load_request_id or self._cleanup_in_progress:
            return
        self._profile_payload_loaded_once = True
        self._profile_payload_dirty = False
        self._apply_payload(payload)

    def _apply_cached_profile_payload(self, payload) -> None:
        self._profile_payload_loaded_once = True
        self._profile_payload_dirty = False
        self._profile_load_request_id += 1
        self._apply_payload(payload)

    def _on_profile_payload_failed(self, request_id: int, error: str) -> None:
        if request_id != self._profile_load_request_id or self._cleanup_in_progress:
            return
        self._profile_payload_dirty = True
        log(f"{self.__class__.__name__}: не удалось прочитать профили: {error}", "ERROR")
        self._show_empty_state(
            "Не удалось показать профили выбранного пресета. "
            "Файл мог быть удалён, очищен или повреждён. "
            "Выберите пресет заново в разделе «Мои пресеты»."
        )

    def _on_profile_worker_finished(self, worker) -> None:
        if self._profile_load_worker is worker:
            self._profile_load_worker = None
        worker.deleteLater()
        if self._profile_payload_dirty and not self._cleanup_in_progress:
            self._schedule_profiles_payload_request(force=True)

    def _apply_payload(self, payload) -> None:
        if self._content_host_layout is None:
            return
        total_started_at = time.perf_counter()
        self._apply_selected_preset_title(payload)
        self._show_profile_normalization_info(payload)
        if not payload.items:
            self._show_empty_state(
                "В выбранном пресете нет профилей, которые можно показать на этой странице. "
                "Попробуйте другой пресет или добавьте нужный профиль."
            )
            self._log_ui_timing("profile_ui.apply_payload.total", total_started_at)
            return
        profiles_list = self._profiles_list
        if profiles_list is not None:
            started_at = time.perf_counter()
            profiles_list.update_profiles(tuple(payload.items))
            profiles_list.set_search_query(self._profile_search_query)
            self._log_ui_timing("profile_ui.profile_list.update", started_at, extra=f"{len(payload.items)} items")
            self._log_ui_timing("profile_ui.apply_payload.total", total_started_at)
            return

        self._clear_dynamic_widgets()
        create_started_at = time.perf_counter()
        profiles_list = ProfilesList(self)
        profiles_list.profile_selected.connect(self._on_profile_clicked)
        profiles_list.profile_context_requested.connect(self._on_profile_context_requested)
        profiles_list.profile_move_requested.connect(self._on_profile_move_requested)
        profiles_list.profile_move_after_requested.connect(self._on_profile_move_after_requested)
        profiles_list.profile_move_to_folder_requested.connect(self._on_profile_move_to_folder_requested)
        profiles_list.profile_move_to_end_requested.connect(self._on_profile_move_to_end_requested)
        profiles_list.folder_context_requested.connect(self._on_folder_context_requested)
        profiles_list.folder_toggled.connect(self._on_folder_toggled)
        self._log_ui_timing("profile_ui.profile_list.create", create_started_at)

        started_at = time.perf_counter()
        profiles_list.build_profiles(tuple(payload.items))
        profiles_list.set_search_query(self._profile_search_query)
        self._log_ui_timing("profile_ui.profile_list.build", started_at, extra=f"{len(payload.items)} items")

        attach_started_at = time.perf_counter()
        self._profiles_list = profiles_list
        self._content_host_layout.addWidget(profiles_list, 1)
        self._empty_state_label = None
        self._log_ui_timing("profile_ui.profile_list.attach", attach_started_at)
        self._log_ui_timing("profile_ui.apply_payload.total", total_started_at)

    def _on_profile_search_text_changed(self, text: str) -> None:
        self._profile_search_query = str(text or "")
        if self._profiles_list is not None:
            self._profiles_list.set_search_query(self._profile_search_query)

    def apply_sidebar_search_query(self, text: str) -> bool:
        query = str(text or "")
        search_input = self._profile_search_input
        if search_input is not None:
            try:
                if str(search_input.text() or "") != query:
                    search_input.setText(query)
                    return True
            except Exception:
                pass
        self._on_profile_search_text_changed(query)
        return True

    def _log_ui_timing(self, label: str, started_at: float, *, extra: str = "") -> None:
        try:
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0
            extra_text = f" | {extra}" if extra else ""
            log(f"{self.__class__.__name__}: {label}: {elapsed_ms:.1f}ms{extra_text}", "DEBUG")
        except Exception:
            pass

    def _show_profile_normalization_info(self, payload) -> None:
        split_count = int(getattr(payload, "normalized_split_profiles", 0) or 0)
        created_count = int(getattr(payload, "normalized_created_profiles", 0) or 0)
        if split_count <= 0 or created_count <= 0:
            return
        try:
            InfoBar.info(
                title="Profile-ы разделены",
                content=(
                    f"Найдено сложных profile-ов: {split_count}. "
                    f"Создано отдельных profile-ов: {created_count}. "
                    "Теперь каждому списку можно менять стратегию отдельно."
                ),
                parent=self.window(),
                duration=6500,
            )
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось показать уведомление о разделении profile-ов: {exc}", "DEBUG")

    def _apply_selected_preset_title(self, payload) -> None:
        if self.title_label is None:
            return
        base_title = tr_catalog(self.title_key, language=self._ui_language, default=self.page_title)
        self.title_label.setText(preset_setup_title_for_payload(payload, base_title))

    def _clear_dynamic_widgets(self) -> None:
        if self._content_host_layout is None:
            return
        while self._content_host_layout.count() > 0:
            item = self._content_host_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self._profiles_list = None
        self._empty_state_label = None

    def _show_empty_state(self, text: str) -> None:
        self._clear_dynamic_widgets()
        if self._content_host_layout is None:
            return
        label = BodyLabel(text)
        label.setWordWrap(True)
        self._content_host_layout.addWidget(label)
        self._empty_state_label = label

    def _on_profile_clicked(self, profile_key: str) -> None:
        self._open_profile_setup(profile_key)

    def _on_profile_context_requested(self, profile_key: str, global_pos) -> None:
        if self._profiles_list is None:
            return
        item = self._profiles_list.profile_item_for_key(profile_key)
        if item is None:
            return
        show_profile_context_menu(
            parent=self,
            item=item,
            global_pos=global_pos,
            actions=ProfileContextMenuActions(
                open_profile=self._open_profile_setup,
                set_enabled=self._set_profile_enabled_from_menu,
                duplicate_profile=self._duplicate_profile_from_menu,
                delete_from_preset=self._delete_profile_from_menu,
                edit_user_profile=self._edit_user_profile_from_menu,
                delete_user_profile=self._delete_user_profile_from_menu,
            ),
        )

    def _set_profile_enabled_from_menu(self, profile_key: str, enabled: bool) -> None:
        self._request_profile_context_action("set_enabled", profile_key, enabled=bool(enabled))

    def _duplicate_profile_from_menu(self, profile_key: str) -> None:
        self._request_profile_context_action("duplicate", profile_key)

    def _delete_profile_from_menu(self, profile_key: str) -> None:
        dialog = MessageBox(
            "Удалить profile из preset",
            "Profile будет убран только из текущего preset. Файлы списков и пользовательский шаблон не удаляются.",
            self,
        )
        dialog.yesButton.setText("Удалить")
        dialog.cancelButton.setText("Отмена")
        if not dialog.exec():
            return
        self._request_profile_context_action("delete", profile_key)

    def _request_profile_context_action(self, action: str, profile_key: str, *, enabled: bool | None = None) -> None:
        profile_key = str(profile_key or "").strip()
        if not profile_key:
            return
        worker = self.__dict__.get("_profile_context_action_worker")
        if worker is not None:
            try:
                if worker.isRunning():
                    return
            except Exception:
                return
        self._profile_context_action_request_id = int(getattr(self, "_profile_context_action_request_id", 0) or 0) + 1
        request_id = self._profile_context_action_request_id
        worker = self._create_profile_context_action_worker(
            request_id,
            self.launch_method,
            action=str(action or ""),
            profile_key=profile_key,
            enabled=enabled,
            parent=self,
        )
        self._profile_context_action_worker = worker
        worker.finished_action.connect(self._on_profile_context_action_finished)
        worker.failed.connect(self._on_profile_context_action_failed)
        worker.finished.connect(lambda w=worker: self._on_profile_context_action_worker_finished(w))
        worker.start()

    def _on_profile_context_action_finished(self, request_id: int, action: str, profile_key: str, result) -> None:
        if request_id != int(getattr(self, "_profile_context_action_request_id", 0) or 0):
            return
        if action == "set_enabled":
            target_key = str(result or profile_key)
            if str(profile_key or "").startswith("profile:") and target_key == str(profile_key or ""):
                self._refresh_profile_item_locally(profile_key, target_key)
            else:
                self._sync_profile_list_locally()
            return
        if action == "duplicate":
            self._sync_profile_list_locally()
            return
        if action == "delete" and bool(result):
            self._sync_profile_list_locally()

    def _on_profile_context_action_failed(self, request_id: int, error: str) -> None:
        if request_id != int(getattr(self, "_profile_context_action_request_id", 0) or 0):
            return
        log(f"{self.__class__.__name__}: не удалось выполнить действие profile: {error}", "ERROR")
        InfoBar.error(title="Ошибка", content=str(error), parent=self.window())

    def _on_profile_context_action_worker_finished(self, worker) -> None:
        if self.__dict__.get("_profile_context_action_worker") is worker:
            self._profile_context_action_worker = None
        worker.deleteLater()

    def _create_profile_context_action_worker(
        self,
        request_id: int,
        launch_method: str,
        *,
        action: str,
        profile_key: str,
        enabled: bool | None = None,
        parent=None,
    ):
        return ProfilePresetProfileActionWorker(
            request_id,
            self._profile,
            launch_method,
            action=action,
            profile_key=profile_key,
            enabled=enabled,
            parent=parent,
        )

    def _sync_profile_list_locally(self) -> None:
        profiles_list = self._profiles_list
        if profiles_list is None:
            self.refresh_from_preset_switch()
            return
        try:
            payload = self._profile.list_profiles(self.launch_method)
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось обновить текущий список profile: {exc}", "ERROR")
            self.refresh_from_preset_switch()
            return
        if not getattr(payload, "items", ()):
            self.refresh_from_preset_switch()
            return
        self._profile_payload_loaded_once = True
        self._profile_payload_dirty = False
        self._profile_load_request_id += 1
        self._apply_selected_preset_title(payload)
        self._show_profile_normalization_info(payload)
        profiles_list.update_profiles(tuple(payload.items))
        profiles_list.set_search_query(self._profile_search_query)

    def _refresh_profile_item_locally(self, old_profile_key: str, profile_key: str) -> None:
        setup = self._profile.get_profile_setup(self.launch_method, profile_key)
        if setup is not None and self._profiles_list is not None:
            if self._profiles_list.replace_profile_item(old_profile_key, setup.item):
                return
            if str(old_profile_key or "") != str(profile_key or "") and self._profiles_list.add_profile_item(setup.item):
                return
        self.refresh_from_preset_switch()

    def _add_profile_item_locally(self, profile_key: str | None) -> None:
        key = str(profile_key or "").strip()
        if not key:
            self.refresh_from_preset_switch()
            return
        setup = self._profile.get_profile_setup(self.launch_method, key)
        if setup is not None and self._profiles_list is not None and self._profiles_list.add_profile_item(setup.item):
            return
        self.refresh_from_preset_switch()

    def _remove_profile_item_locally(self, profile_key: str) -> None:
        if self._profiles_list is not None and self._profiles_list.remove_profile_item(profile_key):
            return
        self.refresh_from_preset_switch()

    def _edit_user_profile_from_menu(self, profile_key: str) -> None:
        if self._profiles_list is None:
            return
        item = self._profiles_list.profile_item_for_key(profile_key)
        if item is None:
            return
        profile_id = _user_profile_id_from_item(profile_key, item)
        if not profile_id:
            return
        protocol, ports = _protocol_and_ports_from_match_lines(tuple(getattr(item, "match_lines", ()) or ()))
        dialog = CreateUserProfileDialog(
            self,
            title="Изменить profile",
            subtitle="Изменяет пользовательский profile и обновляет все preset-ы, где есть старое --name.",
            button_text="Сохранить",
            name=str(getattr(item, "display_name", "") or ""),
            protocol=protocol,
            ports=ports,
        )
        if not dialog.exec():
            return
        name, protocol, ports = dialog.values()
        self._request_user_profile_update(
            profile_id,
            name=name,
            protocol=protocol,
            ports=ports,
        )

    def _delete_user_profile_from_menu(self, profile_key: str) -> None:
        if self._profiles_list is None:
            return
        item = self._profiles_list.profile_item_for_key(profile_key)
        if item is None:
            return
        profile_id = _user_profile_id_from_item(profile_key, item)
        if not profile_id:
            return
        dialog = MessageBox(
            "Удалить пользовательский profile",
            "Profile будет удалён из библиотеки, его файлы списков будут удалены, "
            "а profile-ы с таким же --name будут убраны из preset-ов.",
            self,
        )
        dialog.yesButton.setText("Удалить")
        dialog.cancelButton.setText("Отмена")
        if not dialog.exec():
            return
        self._request_user_profile_delete(profile_id)

    def _set_user_profile_actions_enabled(self, enabled: bool) -> None:
        if self._add_profile_btn is not None:
            self._add_profile_btn.setEnabled(enabled)

    def _user_profile_operation_running(self) -> bool:
        for worker in (
            self.__dict__.get("_user_profile_create_worker"),
            self.__dict__.get("_user_profile_update_worker"),
            self.__dict__.get("_user_profile_delete_worker"),
        ):
            if worker is None:
                continue
            try:
                if worker.isRunning():
                    return True
            except Exception:
                return True
        return False

    def _create_user_profile_create_worker(self, request_id: int, *, name: str, protocol: str, ports: str):
        return ProfileUserProfileCreateWorker(
            request_id,
            self._profile,
            name=name,
            protocol=protocol,
            ports=ports,
            parent=self,
        )

    def _create_user_profile_update_worker(
        self,
        request_id: int,
        *,
        profile_id: str,
        name: str,
        protocol: str,
        ports: str,
    ):
        return ProfileUserProfileUpdateWorker(
            request_id,
            self._profile,
            profile_id=profile_id,
            name=name,
            protocol=protocol,
            ports=ports,
            parent=self,
        )

    def _create_user_profile_delete_worker(self, request_id: int, *, profile_id: str):
        return ProfileUserProfileDeleteWorker(
            request_id,
            self._profile,
            profile_id=profile_id,
            parent=self,
        )

    def _request_user_profile_create(self, *, name: str, protocol: str, ports: str) -> None:
        if self._user_profile_operation_running():
            return
        self._user_profile_create_request_id = int(getattr(self, "_user_profile_create_request_id", 0) or 0) + 1
        request_id = self._user_profile_create_request_id
        self._set_user_profile_actions_enabled(False)
        worker = self._create_user_profile_create_worker(
            request_id,
            name=name,
            protocol=protocol,
            ports=ports,
        )
        self._user_profile_create_worker = worker
        worker.created.connect(self._on_user_profile_create_finished)
        worker.failed.connect(self._on_user_profile_create_failed)
        worker.finished.connect(lambda w=worker: self._on_user_profile_create_worker_finished(w))
        worker.start()

    def _on_user_profile_create_finished(self, request_id: int, _profile_id: str) -> None:
        if request_id != int(getattr(self, "_user_profile_create_request_id", 0) or 0):
            return
        InfoBar.success(
            title="Profile добавлен",
            content="Он появился в общем списке и пока выключен во всех preset-ах.",
            parent=self.window(),
        )
        self.refresh_from_preset_switch()

    def _on_user_profile_create_failed(self, request_id: int, error: str) -> None:
        if request_id != int(getattr(self, "_user_profile_create_request_id", 0) or 0):
            return
        log(f"{self.__class__.__name__}: не удалось создать пользовательский profile: {error}", "ERROR")
        InfoBar.error(title="Ошибка", content=str(error), parent=self.window())

    def _on_user_profile_create_worker_finished(self, worker) -> None:
        if self.__dict__.get("_user_profile_create_worker") is worker:
            self._user_profile_create_worker = None
        worker.deleteLater()
        if not self._user_profile_operation_running():
            self._set_user_profile_actions_enabled(True)

    def _request_user_profile_update(self, profile_id: str, *, name: str, protocol: str, ports: str) -> None:
        profile_id = str(profile_id or "").strip()
        if not profile_id or self._user_profile_operation_running():
            return
        self._user_profile_update_request_id = int(getattr(self, "_user_profile_update_request_id", 0) or 0) + 1
        request_id = self._user_profile_update_request_id
        self._set_user_profile_actions_enabled(False)
        worker = self._create_user_profile_update_worker(
            request_id,
            profile_id=profile_id,
            name=name,
            protocol=protocol,
            ports=ports,
        )
        self._user_profile_update_worker = worker
        worker.updated.connect(self._on_user_profile_update_finished)
        worker.failed.connect(self._on_user_profile_update_failed)
        worker.finished.connect(lambda w=worker: self._on_user_profile_update_worker_finished(w))
        worker.start()

    def _on_user_profile_update_finished(self, request_id: int, _profile_id: str, changed: int) -> None:
        if request_id != int(getattr(self, "_user_profile_update_request_id", 0) or 0):
            return
        InfoBar.success(
            title="Profile изменён",
            content=f"Обновлено profile-ов в preset-ах: {int(changed or 0)}.",
            parent=self.window(),
        )
        self.refresh_from_preset_switch()

    def _on_user_profile_update_failed(self, request_id: int, error: str) -> None:
        if request_id != int(getattr(self, "_user_profile_update_request_id", 0) or 0):
            return
        log(f"{self.__class__.__name__}: не удалось изменить пользовательский profile: {error}", "ERROR")
        InfoBar.error(title="Ошибка", content=str(error), parent=self.window())

    def _on_user_profile_update_worker_finished(self, worker) -> None:
        if self.__dict__.get("_user_profile_update_worker") is worker:
            self._user_profile_update_worker = None
        worker.deleteLater()
        if not self._user_profile_operation_running():
            self._set_user_profile_actions_enabled(True)

    def _request_user_profile_delete(self, profile_id: str) -> None:
        profile_id = str(profile_id or "").strip()
        if not profile_id or self._user_profile_operation_running():
            return
        self._user_profile_delete_request_id = int(getattr(self, "_user_profile_delete_request_id", 0) or 0) + 1
        request_id = self._user_profile_delete_request_id
        self._set_user_profile_actions_enabled(False)
        worker = self._create_user_profile_delete_worker(request_id, profile_id=profile_id)
        self._user_profile_delete_worker = worker
        worker.deleted.connect(self._on_user_profile_delete_finished)
        worker.failed.connect(self._on_user_profile_delete_failed)
        worker.finished.connect(lambda w=worker: self._on_user_profile_delete_worker_finished(w))
        worker.start()

    def _on_user_profile_delete_finished(self, request_id: int, _profile_id: str, changed: int) -> None:
        if request_id != int(getattr(self, "_user_profile_delete_request_id", 0) or 0):
            return
        InfoBar.success(
            title="Profile удалён",
            content=f"Удалено profile-ов из preset-ов: {int(changed or 0)}.",
            parent=self.window(),
        )
        self.refresh_from_preset_switch()

    def _on_user_profile_delete_failed(self, request_id: int, error: str) -> None:
        if request_id != int(getattr(self, "_user_profile_delete_request_id", 0) or 0):
            return
        log(f"{self.__class__.__name__}: не удалось удалить пользовательский profile: {error}", "ERROR")
        InfoBar.error(title="Ошибка", content=str(error), parent=self.window())

    def _on_user_profile_delete_worker_finished(self, worker) -> None:
        if self.__dict__.get("_user_profile_delete_worker") is worker:
            self._user_profile_delete_worker = None
        worker.deleteLater()
        if not self._user_profile_operation_running():
            self._set_user_profile_actions_enabled(True)

    def _apply_profile_move_locally(
        self,
        source_profile_key: str,
        destination_kind: str,
        destination_profile_key: str = "",
        destination_group_key: str = "",
    ) -> None:
        if self._profiles_list is not None and self._profiles_list.move_profile_locally(
            source_profile_key,
            destination_kind,
            destination_profile_key,
            destination_group_key,
        ):
            return
        self.refresh_from_preset_switch()

    def _on_profile_move_requested(
        self,
        source_profile_key: str,
        destination_profile_key: str,
        destination_group_key: str = "",
    ) -> None:
        self._apply_profile_move_locally(
            source_profile_key,
            "profile",
            destination_profile_key,
            destination_group_key,
        )
        self._request_profile_move(
            "before",
            source_profile_key,
            destination_profile_key=destination_profile_key,
            destination_group_key=destination_group_key,
        )

    def _on_profile_move_after_requested(
        self,
        source_profile_key: str,
        destination_profile_key: str,
        destination_group_key: str = "",
    ) -> None:
        self._apply_profile_move_locally(
            source_profile_key,
            "profile_after",
            destination_profile_key,
            destination_group_key,
        )
        self._request_profile_move(
            "after",
            source_profile_key,
            destination_profile_key=destination_profile_key,
            destination_group_key=destination_group_key,
        )

    def _on_profile_move_to_end_requested(self, profile_key: str) -> None:
        self._apply_profile_move_locally(profile_key, "end")
        self._request_profile_move("end", profile_key)

    def _on_profile_move_to_folder_requested(self, profile_key: str, folder_key: str) -> None:
        self._apply_profile_move_locally(profile_key, "folder", destination_group_key=folder_key)
        self._request_profile_move("folder", profile_key, destination_group_key=folder_key)

    def _request_profile_move(
        self,
        action: str,
        source_profile_key: str,
        *,
        destination_profile_key: str = "",
        destination_group_key: str = "",
    ) -> None:
        source_profile_key = str(source_profile_key or "").strip()
        if not source_profile_key:
            return
        worker = self.__dict__.get("_profile_move_worker")
        if worker is not None:
            try:
                if worker.isRunning():
                    return
            except Exception:
                return
        self._profile_move_request_id = int(getattr(self, "_profile_move_request_id", 0) or 0) + 1
        request_id = self._profile_move_request_id
        worker = self._create_profile_move_worker(
            request_id,
            self.launch_method,
            action=str(action or ""),
            source_profile_key=source_profile_key,
            destination_profile_key=destination_profile_key,
            destination_group_key=destination_group_key,
        )
        self._profile_move_worker = worker
        worker.moved.connect(self._on_profile_move_finished)
        worker.failed.connect(self._on_profile_move_failed)
        worker.finished.connect(lambda w=worker: self._on_profile_move_worker_finished(w))
        worker.start()

    def _on_profile_move_finished(
        self,
        request_id: int,
        action: str,
        source_profile_key: str,
        destination_profile_key: str,
        destination_group_key: str,
        result,
    ) -> None:
        if request_id != int(getattr(self, "_profile_move_request_id", 0) or 0):
            return
        if not result:
            self.refresh_from_preset_switch()

    def _on_profile_move_failed(self, request_id: int, error: str) -> None:
        if request_id != int(getattr(self, "_profile_move_request_id", 0) or 0):
            return
        log(f"{self.__class__.__name__}: не удалось переместить profile: {error}", "ERROR")
        self.refresh_from_preset_switch()

    def _on_profile_move_worker_finished(self, worker) -> None:
        if self.__dict__.get("_profile_move_worker") is worker:
            self._profile_move_worker = None
        worker.deleteLater()

    def _create_profile_move_worker(
        self,
        request_id: int,
        launch_method: str,
        *,
        action: str,
        source_profile_key: str,
        destination_profile_key: str = "",
        destination_group_key: str = "",
    ):
        return ProfilePresetProfileMoveWorker(
            request_id,
            self._profile,
            launch_method,
            action=action,
            source_profile_key=source_profile_key,
            destination_profile_key=destination_profile_key,
            destination_group_key=destination_group_key,
            parent=self,
        )

    def _on_folder_context_requested(self, folder_key: str, global_pos) -> None:
        show_profile_folder_menu(
            parent=self,
            folder_key=folder_key,
            global_pos=global_pos,
            refresh_fn=self.refresh_from_preset_switch,
            log_fn=log,
        )

    def _on_folder_toggled(self, folder_key: str, is_expanded: bool) -> None:
        try:
            set_profile_folder_collapsed(folder_key, not bool(is_expanded))
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось запомнить состояние папки profile-ов: {exc}", "ERROR")

    def apply_profile_setup_change(self, profile_key: str, change_kind: str) -> None:
        if str(change_kind or "").strip() in {"strategy", "feedback"} and str(profile_key or "").strip():
            self._refresh_profile_item_locally(profile_key, profile_key)
            return
        self.refresh_from_preset_switch()

    def handle_page_command(self, command: str, payload: dict) -> bool:
        if command == "profile_setup_changed":
            self.apply_profile_setup_change(
                str((payload or {}).get("profile_key") or ""),
                str((payload or {}).get("change_kind") or ""),
            )
            return True
        return False

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        unsubscribe = self._ui_state_unsubscribe
        if callable(unsubscribe):
            try:
                unsubscribe()
            except Exception:
                pass
        self._ui_state_unsubscribe = None
        self._ui_state_store = None
        worker = self._profile_load_worker
        if worker is not None:
            try:
                worker.quit()
            except Exception:
                pass

    def _expand_all(self) -> None:
        if self._profiles_list is not None:
            self._profiles_list.expand_all()

    def _collapse_all(self) -> None:
        if self._profiles_list is not None:
            self._profiles_list.collapse_all()

    def _open_profile_order(self) -> None:
        self._open_profile_order_page()

    def _show_profile_info(self) -> None:
        MessageBox(
            "Настройка пресета",
            "На этой странице показаны профили выбранного пресета. "
            "Если профиля ещё нет в пресете, включите его или выберите для него готовую стратегию. "
            "Если профиль выключить, программа добавит --skip, чтобы движок его пропустил.",
            self,
        ).exec()

    def _on_add_user_profile_clicked(self) -> None:
        dialog = CreateUserProfileDialog(self)
        if not dialog.exec():
            return
        name, protocol, ports = dialog.values()
        self._request_user_profile_create(name=name, protocol=protocol, ports=ports)


class Zapret2PresetSetupPage(PresetSetupPageBase):
    launch_method = ZAPRET2_MODE
    engine_label = "Zapret 2"
    page_title = "Настройка пресета"
    title_key = "page.winws2_pages.title"
    control_key = "page.winws2_pages.back.control"
    toolbar_title_key = "page.winws2_pages.toolbar.title"
    request_button_key = "page.winws2_pages.request.button"
    request_hint_key = "page.winws2_pages.request.hint"
    loading_key = "page.winws2_pages.loading"


class Zapret1PresetSetupPage(PresetSetupPageBase):
    launch_method = ZAPRET1_MODE
    engine_label = "Zapret 1"
    page_title = "Настройка пресета"
    title_key = "page.winws1_pages.title"
    control_key = "page.winws1_pages.back.control"
    toolbar_title_key = "page.winws1_pages.toolbar.title"
    request_button_key = "page.winws1_pages.request.button"
    request_hint_key = "page.winws1_pages.request.hint"
    loading_key = "page.winws1_pages.loading"


def _protocol_and_ports_from_match_lines(match_lines: tuple[str, ...]) -> tuple[str, str]:
    for protocol, option_name in (("tcp", "--filter-tcp"), ("udp", "--filter-udp"), ("l7", "--filter-l7")):
        values = filter_values(match_lines, option_name)
        if values:
            return protocol, values[0]
    return "tcp", ""


def _user_profile_id_from_item(profile_key: str, item) -> str:
    profile_id = str(getattr(item, "user_profile_id", "") or "").strip()
    if profile_id:
        return profile_id
    key = str(profile_key or "").strip()
    if key.startswith("template:user:"):
        return key.split("template:user:", 1)[1].strip()
    return ""
