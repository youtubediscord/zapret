from __future__ import annotations

from PyQt6.QtCore import pyqtSignal, QTimer

from log.log import log
from profile.service import ProfilePresetService
from profile.ui.profiles_list import ProfilesList
from profile.ui.shell import build_profile_shell
from qfluentwidgets import BodyLabel, BreadcrumbBar, MessageBox
from ui.page_dependencies import require_page_app_context
from ui.pages.base_page import BasePage
from ui.text_catalog import tr as tr_catalog


class ProfilesPageBase(BasePage):
    open_profile_detail = pyqtSignal(str, str)
    strategy_selected = pyqtSignal(str, str)
    back_clicked = pyqtSignal()
    profile_ui_mode_override: str | None = None
    launch_method = "zapret2_mode"
    engine_label = "Zapret 2"
    page_title = "Профили Zapret 2"
    title_key = "page.z2_pages.title"
    control_key = "page.z2_pages.back.control"
    toolbar_title_key = "page.z2_pages.toolbar.title"
    request_button_key = "page.z2_pages.request.button"
    request_hint_key = "page.z2_pages.request.hint"
    loading_key = "page.z2_pages.loading"

    def __init__(self, parent=None):
        super().__init__(
            title=self.page_title,
            parent=parent,
            title_key=self.title_key,
        )
        self.parent_app = parent
        self._breadcrumb = BreadcrumbBar()
        self._rebuild_breadcrumb()
        self._breadcrumb.currentItemChanged.connect(self._on_breadcrumb_item_changed)
        self.layout.insertWidget(0, self._breadcrumb)

        self._profiles_list: ProfilesList | None = None
        self._empty_state_label = None
        self._content_host_layout = None
        self._loading_label = None
        self._reload_btn = None
        self._expand_btn = None
        self._collapse_btn = None
        self._request_btn = None
        self._info_btn = None
        self._toolbar_actions_bar = None
        self._cleanup_in_progress = False
        self._build_content()
        QTimer.singleShot(0, self.refresh_from_preset_switch)

    def _require_app_context(self):
        return require_page_app_context(
            self,
            parent=self.parent(),
            error_message=f"AppContext is required for {self.engine_label} profiles page",
        )

    def _service(self) -> ProfilePresetService:
        return ProfilePresetService(self._require_app_context(), self.launch_method)

    def _rebuild_breadcrumb(self) -> None:
        self._breadcrumb.blockSignals(True)
        try:
            self._breadcrumb.clear()
            self._breadcrumb.addItem("control", tr_catalog(self.control_key, language=self._ui_language, default="Управление"))
            self._breadcrumb.addItem("profiles", tr_catalog(self.title_key, language=self._ui_language, default=self.page_title))
        finally:
            self._breadcrumb.blockSignals(False)

    def _on_breadcrumb_item_changed(self, key: str) -> None:
        self._rebuild_breadcrumb()
        if key == "control":
            self.back_clicked.emit()

    def on_page_activated(self) -> None:
        self._rebuild_breadcrumb()
        self.refresh_from_preset_switch()

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
            on_reload=self._reload_profiles,
            on_expand_all=self._expand_all,
            on_collapse_all=self._collapse_all,
            on_show_info_popup=self._show_profile_info,
        )
        self._toolbar_actions_bar = shell.toolbar_actions_bar
        self._request_btn = shell.request_btn
        self._reload_btn = shell.reload_btn
        self._expand_btn = shell.expand_btn
        self._collapse_btn = shell.collapse_btn
        self._info_btn = shell.info_btn
        self._content_host_layout = shell.content_host_layout
        self._loading_label = shell.loading_label

    def _reload_profiles(self) -> None:
        self.refresh_from_preset_switch()

    def refresh_from_preset_switch(self) -> None:
        if self._cleanup_in_progress:
            return
        try:
            if self._reload_btn is not None:
                self._reload_btn.set_loading(True)
        except Exception:
            pass
        try:
            payload = self._service().list_profiles()
            self._apply_payload(payload)
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось прочитать profiles: {exc}", "ERROR")
            self._show_empty_state("Не удалось прочитать profiles выбранного preset. Проверьте лог и сам preset-файл.")
        finally:
            try:
                if self._reload_btn is not None:
                    self._reload_btn.set_loading(False)
            except Exception:
                pass

    def _apply_payload(self, payload) -> None:
        if self._content_host_layout is None:
            return
        self._clear_dynamic_widgets()
        if not payload.items:
            self._show_empty_state("В выбранном preset не найдено ни одного profile.")
            return
        profiles_list = ProfilesList(self)
        profiles_list.profile_selected.connect(self._on_profile_clicked)
        profiles_list.profile_context_action_requested.connect(self._on_profile_context_action)
        profiles_list.profile_move_requested.connect(self._on_profile_move_requested)
        profiles_list.profile_move_to_end_requested.connect(self._on_profile_move_to_end_requested)
        profiles_list.build_profiles(tuple(payload.items))
        self._profiles_list = profiles_list
        self._content_host_layout.addWidget(profiles_list, 1)
        self._empty_state_label = None

    def _clear_dynamic_widgets(self) -> None:
        if self._content_host_layout is None:
            return
        while self._content_host_layout.count() > 1:
            item = self._content_host_layout.takeAt(1)
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

    def _on_profile_clicked(self, profile_key: str, strategy_id: str) -> None:
        self.open_profile_detail.emit(profile_key, strategy_id)

    def _on_profile_context_action(self, profile_key: str, action: str) -> None:
        normalized_action = str(action or "").strip().lower()
        if normalized_action == "duplicate":
            self._duplicate_profile(profile_key)
        elif normalized_action == "delete":
            self._delete_profile(profile_key)

    def _duplicate_profile(self, profile_key: str) -> None:
        try:
            new_key = self._service().duplicate_profile(profile_key)
            self.refresh_from_preset_switch()
            if new_key:
                self.open_profile_detail.emit(new_key, "custom")
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось дублировать profile: {exc}", "ERROR")
            self._show_empty_state("Не удалось дублировать profile. Проверьте лог и preset-файл.")

    def _delete_profile(self, profile_key: str) -> None:
        if MessageBox is not None:
            box = MessageBox(
                "Удалить profile?",
                "Profile будет физически удалён из выбранного preset-файла. Это не то же самое, что выключить через --skip.",
                self.window(),
            )
            box.yesButton.setText("Удалить")
            box.cancelButton.setText("Отмена")
            if not box.exec():
                return
        try:
            self._service().delete_profile(profile_key)
            self.refresh_from_preset_switch()
            self.strategy_selected.emit(profile_key, "custom")
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось удалить profile: {exc}", "ERROR")
            self._show_empty_state("Не удалось удалить profile. Проверьте лог и preset-файл.")

    def _on_profile_move_requested(self, source_profile_key: str, destination_profile_key: str) -> None:
        try:
            self._service().move_profile_before(source_profile_key, destination_profile_key)
            self.refresh_from_preset_switch()
            self.strategy_selected.emit(source_profile_key, "custom")
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось переместить profile: {exc}", "ERROR")

    def _on_profile_move_to_end_requested(self, profile_key: str) -> None:
        try:
            self._service().move_profile_to_end(profile_key)
            self.refresh_from_preset_switch()
            self.strategy_selected.emit(profile_key, "custom")
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось переместить profile в конец: {exc}", "ERROR")

    def apply_strategy_selection(self, profile_key: str, strategy_id: str) -> None:
        _ = (profile_key, strategy_id)
        self.refresh_from_preset_switch()

    def _expand_all(self) -> None:
        if self._profiles_list is not None:
            self._profiles_list.expand_all()

    def _collapse_all(self) -> None:
        if self._profiles_list is not None:
            self._profiles_list.collapse_all()

    def _show_profile_info(self) -> None:
        MessageBox(
            "Profiles",
            "На этой странице показаны profiles выбранного preset. Включение шаблона добавляет его в preset, выключение существующего profile записывает --skip.",
            self,
        ).exec()


class Zapret2ProfilesPage(ProfilesPageBase):
    launch_method = "zapret2_mode"
    engine_label = "Zapret 2"
    page_title = "Профили Zapret 2"
    title_key = "page.z2_pages.title"
    control_key = "page.z2_pages.back.control"
    toolbar_title_key = "page.z2_pages.toolbar.title"
    request_button_key = "page.z2_pages.request.button"
    request_hint_key = "page.z2_pages.request.hint"
    loading_key = "page.z2_pages.loading"


class Zapret1ProfilesPage(ProfilesPageBase):
    launch_method = "zapret1_mode"
    engine_label = "Zapret 1"
    page_title = "Профили Zapret 1"
    title_key = "page.z1_pages.title"
    control_key = "page.z1_pages.back.control"
    toolbar_title_key = "page.z1_pages.toolbar.title"
    request_button_key = "page.z1_pages.request.button"
    request_hint_key = "page.z1_pages.request.hint"
    loading_key = "page.z1_pages.loading"
