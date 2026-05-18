from __future__ import annotations

from PyQt6.QtCore import QTimer

from log.log import log
from profile.ui.profiles_list import ProfilesList
from profile.ui.shell import build_profile_shell
from qfluentwidgets import BodyLabel, BreadcrumbBar, MessageBox
from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE
from ui.pages.base_page import BasePage
from app.text_catalog import tr as tr_catalog


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

    def __init__(self, parent=None, *, profile_feature, open_control, open_profile_setup):
        super().__init__(
            title=self.page_title,
            parent=parent,
            title_key=self.title_key,
        )
        self._profile = profile_feature
        self._open_control = open_control
        self._open_profile_setup = open_profile_setup
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
            self._open_control()

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
            payload = self._profile.list_profiles(self.launch_method)
            self._apply_payload(payload)
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось прочитать профили: {exc}", "ERROR")
            self._show_empty_state(
                "Не удалось показать профили выбранного пресета. "
                "Файл мог быть удалён, очищен или повреждён. "
                "Выберите пресет заново и нажмите «Обновить»."
            )
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
            self._show_empty_state(
                "В выбранном пресете нет профилей, которые можно показать на этой странице. "
                "Попробуйте другой пресет или добавьте нужный профиль."
            )
            return
        profiles_list = ProfilesList(self)
        profiles_list.profile_selected.connect(self._on_profile_clicked)
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

    def _on_profile_clicked(self, profile_key: str) -> None:
        self._open_profile_setup(profile_key)

    def _on_profile_move_requested(self, source_profile_key: str, destination_profile_key: str) -> None:
        try:
            self._profile.move_profile_before(
                self.launch_method,
                source_profile_key,
                destination_profile_key,
            )
            self.refresh_from_preset_switch()
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось переместить профиль: {exc}", "ERROR")

    def _on_profile_move_to_end_requested(self, profile_key: str) -> None:
        try:
            self._profile.move_profile_to_end(self.launch_method, profile_key)
            self.refresh_from_preset_switch()
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось переместить профиль в конец: {exc}", "ERROR")

    def apply_profile_setup_change(self, profile_key: str, change_kind: str) -> None:
        _ = (profile_key, change_kind)
        self.refresh_from_preset_switch()

    def handle_page_command(self, command: str, payload: dict) -> bool:
        if command == "profile_setup_changed":
            self.apply_profile_setup_change(
                str((payload or {}).get("profile_key") or ""),
                str((payload or {}).get("change_kind") or ""),
            )
            return True
        return False

    def _expand_all(self) -> None:
        if self._profiles_list is not None:
            self._profiles_list.expand_all()

    def _collapse_all(self) -> None:
        if self._profiles_list is not None:
            self._profiles_list.collapse_all()

    def _show_profile_info(self) -> None:
        MessageBox(
            "Настройка пресета",
            "На этой странице показаны профили выбранного пресета. "
            "Если профиля ещё нет в пресете, включите его или выберите для него готовую стратегию. "
            "Если профиль выключить, программа добавит --skip, чтобы движок его пропустил.",
            self,
        ).exec()


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
