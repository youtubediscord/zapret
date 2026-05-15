from __future__ import annotations

import re

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from log.log import log
from profile.winws2_editable_settings import normalize_winws2_filter_value
from qfluentwidgets import BodyLabel, BreadcrumbBar, CheckBox, ComboBox, LineEdit, PlainTextEdit, PushButton, TitleLabel
from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE, is_zapret2_launch_method
from ui.pages.base_page import BasePage
from app.text_catalog import tr as tr_catalog


_SIMPLE_RANGE_RE = re.compile(r"^-?(?P<mode>[nd])(?P<value>\d+)$", re.IGNORECASE)


class ProfileSetupPageBase(BasePage):
    profile_ui_mode_override: str | None = None
    launch_method = ZAPRET2_MODE
    title_key_name = "page.winws2_profile_setup.title"
    control_key = "page.winws2_profile_setup.breadcrumb.control"
    profiles_key = "page.winws2_pages.title"
    profiles_default = "Настройка пресета"

    def __init__(self, parent=None, *, profile_feature, open_profiles, open_root, on_profile_changed):
        super().__init__(
            title="",
            parent=parent,
            title_key=self.title_key_name,
        )
        self._profile = profile_feature
        self._open_profiles = open_profiles
        self._open_root = open_root
        self._on_profile_changed_callback = on_profile_changed
        self._profile_key = ""
        self._loading = False
        self._payload = None
        self._profile_subpage = "profile"
        self._main_widgets = []
        self._settings_title = None
        self._settings_container = None
        self._feedback_container = None
        self._feedback_open_button = None
        self._feedback_strategy_label = None
        self._feedback_status_label = None
        self._work_button = None
        self._notwork_button = None
        self._favorite_button = None
        self._clear_feedback_button = None
        self._settings_save_timer = QTimer(self)
        self._settings_save_timer.setSingleShot(True)
        self._settings_save_timer.setInterval(350)
        self._settings_save_timer.timeout.connect(self._autosave_editable_settings)
        self._build_content()

    def _build_content(self) -> None:
        if self.title_label is not None:
            self.title_label.hide()
        if self.subtitle_label is not None:
            self.subtitle_label.hide()

        self._breadcrumb = BreadcrumbBar()
        self._breadcrumb.currentItemChanged.connect(self._on_breadcrumb_item_changed)
        self.layout.addWidget(self._breadcrumb)

        self._title = TitleLabel("Профиль")
        self.layout.addWidget(self._title)

        self._summary = BodyLabel("")
        self._summary.setWordWrap(True)
        self.layout.addWidget(self._summary)

        controls = QWidget(self)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(12)

        self._enabled_checkbox = CheckBox("Включён")
        self._enabled_checkbox.stateChanged.connect(self._on_enabled_changed)
        controls_layout.addWidget(self._enabled_checkbox)

        self._strategy_combo = ComboBox()
        self._strategy_combo.setMinimumWidth(320)
        self._strategy_combo.currentIndexChanged.connect(self._on_strategy_changed)
        controls_layout.addWidget(self._strategy_combo, 1)

        self._feedback_open_button = PushButton("Оценка стратегии")
        self._feedback_open_button.clicked.connect(self._open_feedback_subpage)
        controls_layout.addWidget(self._feedback_open_button)

        self.layout.addWidget(controls)
        self._main_widgets.append(controls)

        self._settings_container = QWidget(self)
        settings_layout = QHBoxLayout(self._settings_container)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(12)

        self._filter_combo = ComboBox()
        self._filter_combo.setMinimumWidth(150)
        self._filter_combo.addItem(tr_catalog("page.winws2_profile_setup.filter.hostlist", language=self._ui_language, default="Hostlist"), userData="hostlist")
        self._filter_combo.addItem(tr_catalog("page.winws2_profile_setup.filter.ipset", language=self._ui_language, default="IPset"), userData="ipset")
        settings_layout.addWidget(self._filter_combo)

        self._filter_value = LineEdit()
        self._filter_value.setMinimumWidth(260)
        self._filter_value.setPlaceholderText("lists/example.txt")
        settings_layout.addWidget(self._filter_value, 1)

        self._in_range_mode = ComboBox()
        self._in_range_mode.setMinimumWidth(86)
        self._fill_range_combo(self._in_range_mode)
        settings_layout.addWidget(BodyLabel("--in-range"))
        settings_layout.addWidget(self._in_range_mode)

        self._in_range_value = LineEdit()
        self._in_range_value.setMinimumWidth(90)
        self._in_range_value.setPlaceholderText("8")
        settings_layout.addWidget(self._in_range_value)

        self._out_range_mode = ComboBox()
        self._out_range_mode.setMinimumWidth(86)
        self._fill_range_combo(self._out_range_mode)
        settings_layout.addWidget(BodyLabel("--out-range"))
        settings_layout.addWidget(self._out_range_mode)

        self._out_range_value = LineEdit()
        self._out_range_value.setMinimumWidth(90)
        self._out_range_value.setPlaceholderText("8")
        settings_layout.addWidget(self._out_range_value)

        self._in_range_mode.currentIndexChanged.connect(
            lambda _index: self._on_range_mode_changed(self._in_range_mode, self._in_range_value)
        )
        self._out_range_mode.currentIndexChanged.connect(
            lambda _index: self._on_range_mode_changed(self._out_range_mode, self._out_range_value)
        )
        self._filter_combo.currentIndexChanged.connect(lambda _index: self._on_filter_kind_changed())
        self._filter_value.textEdited.connect(lambda _text: self._schedule_settings_autosave())
        self._in_range_value.textEdited.connect(lambda _text: self._schedule_settings_autosave())
        self._out_range_value.textEdited.connect(lambda _text: self._schedule_settings_autosave())

        self._settings_title = self.add_section_title("Настройки профиля", return_widget=True)
        self.layout.addWidget(self._settings_container)
        self._main_widgets.extend([self._settings_title, self._settings_container])

        self._match_title = self.add_section_title("Когда профиль применяется", return_widget=True)
        self._match_text = PlainTextEdit()
        self._match_text.setReadOnly(True)
        self._match_text.setMinimumHeight(110)
        self.layout.addWidget(self._match_text)
        self._main_widgets.extend([self._match_title, self._match_text])

        self._strategy_title = self.add_section_title("Выбранная готовая стратегия", return_widget=True)
        self._strategy_text = PlainTextEdit()
        self._strategy_text.setReadOnly(True)
        self._strategy_text.setMinimumHeight(160)
        self.layout.addWidget(self._strategy_text)
        self._main_widgets.extend([self._strategy_title, self._strategy_text])

        self._raw_title = self.add_section_title("Что записано в профиль", return_widget=True)
        self._raw_text = PlainTextEdit()
        self._raw_text.setReadOnly(True)
        self._raw_text.setMinimumHeight(220)
        self.layout.addWidget(self._raw_text)
        self._main_widgets.extend([self._raw_title, self._raw_text])

        self._feedback_container = QWidget(self)
        feedback_layout = QVBoxLayout(self._feedback_container)
        feedback_layout.setContentsMargins(0, 0, 0, 0)
        feedback_layout.setSpacing(12)

        self._feedback_strategy_label = BodyLabel("")
        self._feedback_strategy_label.setWordWrap(True)
        feedback_layout.addWidget(self._feedback_strategy_label)

        self._feedback_status_label = BodyLabel("")
        self._feedback_status_label.setWordWrap(True)
        feedback_layout.addWidget(self._feedback_status_label)

        feedback_actions = QWidget(self._feedback_container)
        feedback_actions_layout = QHBoxLayout(feedback_actions)
        feedback_actions_layout.setContentsMargins(0, 0, 0, 0)
        feedback_actions_layout.setSpacing(12)

        self._work_button = PushButton("Работает")
        self._work_button.clicked.connect(lambda: self._set_current_strategy_feedback(rating="work"))
        feedback_actions_layout.addWidget(self._work_button)

        self._notwork_button = PushButton("Не работает")
        self._notwork_button.clicked.connect(lambda: self._set_current_strategy_feedback(rating="notwork"))
        feedback_actions_layout.addWidget(self._notwork_button)

        self._favorite_button = PushButton("В избранное")
        self._favorite_button.clicked.connect(self._toggle_current_strategy_favorite)
        feedback_actions_layout.addWidget(self._favorite_button)

        self._clear_feedback_button = PushButton("Убрать оценку")
        self._clear_feedback_button.clicked.connect(lambda: self._set_current_strategy_feedback(rating=""))
        feedback_actions_layout.addWidget(self._clear_feedback_button)
        feedback_actions_layout.addStretch(1)
        feedback_layout.addWidget(feedback_actions)

        self._feedback_container.hide()
        self.layout.addWidget(self._feedback_container)

    def _fill_range_combo(self, combo: ComboBox) -> None:
        combo.addItem("a", userData="a")
        combo.addItem("x", userData="x")
        combo.addItem("n", userData="n")
        combo.addItem("d", userData="d")
        combo.addItem("своё", userData="custom")

    def _rebuild_breadcrumb(self) -> None:
        self._breadcrumb.blockSignals(True)
        try:
            self._breadcrumb.clear()
            self._breadcrumb.addItem("control", tr_catalog(self.control_key, language=self._ui_language, default="Управление"))
            self._breadcrumb.addItem("profiles", tr_catalog(self.profiles_key, language=self._ui_language, default=self.profiles_default))
            title = str(getattr(getattr(self._payload, "item", None), "display_name", "") or "Профиль")
            self._breadcrumb.addItem("profile", title)
            if self._profile_subpage == "feedback":
                self._breadcrumb.addItem("feedback", "Оценка стратегии")
        finally:
            self._breadcrumb.blockSignals(False)

    def _on_breadcrumb_item_changed(self, key: str) -> None:
        if key == "control":
            self._open_root()
        elif key == "profiles":
            self._open_profiles()
        elif key == "profile":
            self._profile_subpage = "profile"
            self._sync_subpage_visibility()
            self._rebuild_breadcrumb()
        elif key == "feedback":
            self._profile_subpage = "feedback"
            self._sync_subpage_visibility()
            self._rebuild_breadcrumb()

    def show_profile(self, profile_key: str) -> None:
        self._profile_key = str(profile_key or "").strip()
        self._profile_subpage = "profile"
        self.reload_current_profile()

    def reload_current_profile(self) -> None:
        if not self._profile_key:
            return
        try:
            payload = self._profile.get_profile_setup(self.launch_method, self._profile_key)
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось прочитать профиль {self._profile_key}: {exc}", "ERROR")
            payload = None
        if payload is None:
            self._title.setText("Профиль не найден. Вернитесь к списку и нажмите «Обновить».")
            return
        self._payload = payload
        self._apply_payload(payload)

    def _apply_payload(self, payload) -> None:
        self._loading = True
        try:
            item = payload.item
            self._title.setText(item.display_name)
            self._summary.setText(payload.match_summary)
            self._enabled_checkbox.setChecked(bool(item.enabled))
            self._enabled_checkbox.setEnabled(True)
            self._apply_editable_settings(payload)

            self._strategy_combo.clear()
            self._strategy_combo.addItem("Отключено", userData="none")
            self._strategy_combo.addItem("Своя настройка", userData="custom")
            for strategy_id, entry in payload.strategy_entries.items():
                self._strategy_combo.addItem(entry.name, userData=strategy_id)

            current_id = item.strategy_id or "none"
            for index in range(self._strategy_combo.count()):
                if self._strategy_combo.itemData(index) == current_id:
                    self._strategy_combo.setCurrentIndex(index)
                    break

            self._match_text.setPlainText(payload.match_summary)
            self._strategy_text.setPlainText(payload.raw_strategy_text or "Стратегия не выбрана")
            self._raw_text.setPlainText(payload.raw_profile_text)
            self._apply_feedback_buttons(payload)
            self._sync_subpage_visibility()
            self._rebuild_breadcrumb()
        finally:
            self._loading = False

    def _apply_feedback_buttons(self, payload) -> None:
        item = payload.item
        state = payload.current_strategy_state
        editable = bool(
            item.in_preset
            and item.enabled
            and item.strategy_id not in {"", "none", "custom"}
        )
        if self._feedback_open_button is not None:
            self._feedback_open_button.setEnabled(editable)
        for button in (self._work_button, self._notwork_button, self._favorite_button, self._clear_feedback_button):
            if button is not None:
                button.setEnabled(editable)
        if self._feedback_strategy_label is not None:
            self._feedback_strategy_label.setText(f"Готовая стратегия: {item.strategy_name}")
        if self._feedback_status_label is not None:
            status_parts = []
            if state.rating == "work":
                status_parts.append("Оценка: работает")
            elif state.rating == "notwork":
                status_parts.append("Оценка: не работает")
            else:
                status_parts.append("Оценка не выбрана")
            status_parts.append("В избранном" if state.favorite else "Не в избранном")
            if not editable:
                status_parts.append("Оценка доступна только для готовой стратегии внутри включённого профиля")
            self._feedback_status_label.setText(" • ".join(status_parts))
        if self._favorite_button is not None:
            self._favorite_button.setText("Убрать из избранного" if state.favorite else "В избранное")
        if self._work_button is not None:
            self._work_button.setProperty("selected", state.rating == "work")
        if self._notwork_button is not None:
            self._notwork_button.setProperty("selected", state.rating == "notwork")

    def _open_feedback_subpage(self) -> None:
        self._profile_subpage = "feedback"
        self._sync_subpage_visibility()
        self._rebuild_breadcrumb()

    def _sync_subpage_visibility(self) -> None:
        feedback_visible = self._profile_subpage == "feedback"
        for widget in self._main_widgets:
            if widget is not None:
                widget.setVisible(not feedback_visible)
        if not feedback_visible and not is_zapret2_launch_method(self.launch_method):
            if self._settings_title is not None:
                self._settings_title.hide()
            if self._settings_container is not None:
                self._settings_container.hide()
        if self._feedback_container is not None:
            self._feedback_container.setVisible(feedback_visible)

    def _apply_editable_settings(self, payload) -> None:
        is_winws2 = is_zapret2_launch_method(self.launch_method)
        if self._settings_title is not None:
            self._settings_title.setVisible(is_winws2)
        if self._settings_container is not None:
            self._settings_container.setVisible(is_winws2)
        if not is_winws2:
            return

        filter_enabled = bool(getattr(payload, "editable_filter_enabled", True))
        self._filter_combo.setVisible(filter_enabled)
        self._filter_value.setVisible(filter_enabled)
        self._set_combo_by_data(self._filter_combo, getattr(payload, "editable_filter_kind", "") or "hostlist")
        self._filter_value.setText(str(getattr(payload, "editable_filter_value", "") or ""))
        self._set_range_controls(self._in_range_mode, self._in_range_value, getattr(payload, "in_range", "") or "x")
        self._set_range_controls(self._out_range_mode, self._out_range_value, getattr(payload, "out_range", "") or "a")

    def _set_combo_by_data(self, combo: ComboBox, value: str) -> None:
        wanted = str(value or "").strip()
        for index in range(combo.count()):
            if str(combo.itemData(index) or "") == wanted:
                combo.setCurrentIndex(index)
                return

    def _set_range_controls(self, combo: ComboBox, value_edit: LineEdit, expression: str) -> None:
        expr = str(expression or "").strip().lower()
        if expr in {"a", "x"}:
            self._set_combo_by_data(combo, expr)
            value_edit.clear()
            self._sync_range_value_enabled(combo, value_edit)
            return

        match = _SIMPLE_RANGE_RE.match(expr)
        if match:
            self._set_combo_by_data(combo, match.group("mode").lower())
            value_edit.setText(match.group("value"))
            self._sync_range_value_enabled(combo, value_edit)
            return

        self._set_combo_by_data(combo, "custom")
        value_edit.setText(expr)
        self._sync_range_value_enabled(combo, value_edit)

    def _sync_range_value_enabled(self, combo: ComboBox, value_edit: LineEdit) -> None:
        mode = str(combo.itemData(combo.currentIndex()) or "").strip()
        value_edit.setEnabled(mode not in {"a", "x"})
        if mode in {"a", "x"}:
            value_edit.clear()
        value_edit.setPlaceholderText("s1<d1" if mode == "custom" else "8")

    def _on_range_mode_changed(self, combo: ComboBox, value_edit: LineEdit) -> None:
        self._sync_range_value_enabled(combo, value_edit)
        self._schedule_settings_autosave()

    def _on_filter_kind_changed(self) -> None:
        self._sync_filter_value_for_kind()
        self._schedule_settings_autosave()

    def _sync_filter_value_for_kind(self) -> None:
        if self._loading or not is_zapret2_launch_method(self.launch_method):
            return
        filter_kind = str(self._filter_combo.itemData(self._filter_combo.currentIndex()) or "hostlist")
        normalized = normalize_winws2_filter_value(self._filter_value.text(), filter_kind)
        if normalized and normalized != self._filter_value.text().strip():
            self._filter_value.setText(normalized)

    def _range_expression_from_controls(self, combo: ComboBox, value_edit: LineEdit, *, default: str) -> str:
        mode = str(combo.itemData(combo.currentIndex()) or "").strip().lower()
        value = value_edit.text().strip()
        if mode in {"a", "x"}:
            return mode
        if mode in {"n", "d"}:
            return f"-{mode}{value}" if value.isdigit() else default
        if mode == "custom":
            return value or default
        return default

    def _schedule_settings_autosave(self) -> None:
        if self._loading or not self._profile_key or not is_zapret2_launch_method(self.launch_method):
            return
        self._settings_save_timer.start()

    def _autosave_editable_settings(self) -> None:
        if self._loading or not self._profile_key or not is_zapret2_launch_method(self.launch_method):
            return
        filter_value = self._filter_value.text().strip()
        filter_enabled = bool(getattr(self._payload, "editable_filter_enabled", True))
        if filter_enabled and not filter_value:
            return
        try:
            new_key = self._profile.update_winws2_profile_settings(
                self.launch_method,
                self._profile_key,
                filter_kind=str(self._filter_combo.itemData(self._filter_combo.currentIndex()) or "hostlist"),
                filter_value=filter_value,
                in_range=self._range_expression_from_controls(self._in_range_mode, self._in_range_value, default="x"),
                out_range=self._range_expression_from_controls(self._out_range_mode, self._out_range_value, default="a"),
            )
            if new_key:
                self._profile_key = new_key
            self.reload_current_profile()
            self._on_profile_changed_callback(self._profile_key, "settings")
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось сохранить настройки профиля: {exc}", "ERROR")

    def _on_enabled_changed(self, state: int) -> None:
        if self._loading or not self._profile_key:
            return
        enabled = bool(state == Qt.CheckState.Checked.value or state == 2)
        try:
            new_key = self._profile.set_profile_enabled(self.launch_method, self._profile_key, enabled)
            if new_key:
                self._profile_key = new_key
            self.reload_current_profile()
            self._on_profile_changed_callback(self._profile_key, "enabled" if enabled else "disabled")
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось изменить состояние профиля: {exc}", "ERROR")

    def _on_strategy_changed(self, index: int) -> None:
        if self._loading or not self._profile_key:
            return
        strategy_id = str(self._strategy_combo.itemData(index) or "").strip()
        if not strategy_id or strategy_id in {"none", "custom"}:
            return
        try:
            new_key = self._profile.apply_strategy_to_profile(
                self.launch_method,
                self._profile_key,
                strategy_id,
            )
            if new_key:
                self._profile_key = new_key
            self.reload_current_profile()
            self._on_profile_changed_callback(self._profile_key, "strategy")
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось применить стратегию: {exc}", "ERROR")

    def _set_current_strategy_feedback(self, *, rating: str) -> None:
        if self._loading or not self._profile_key:
            return
        try:
            self._profile.set_current_strategy_state(
                self.launch_method,
                self._profile_key,
                rating=rating,
            )
            self.reload_current_profile()
            self._on_profile_changed_callback(self._profile_key, "feedback")
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось обновить оценку стратегии: {exc}", "ERROR")

    def _toggle_current_strategy_favorite(self) -> None:
        if self._loading or not self._profile_key or self._payload is None:
            return
        try:
            current = bool(self._payload.current_strategy_state.favorite)
            self._profile.set_current_strategy_state(
                self.launch_method,
                self._profile_key,
                favorite=not current,
            )
            self.reload_current_profile()
            self._on_profile_changed_callback(self._profile_key, "feedback")
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось обновить избранную стратегию: {exc}", "ERROR")


class Zapret2ProfileSetupPage(ProfileSetupPageBase):
    launch_method = ZAPRET2_MODE
    title_key_name = "page.winws2_profile_setup.title"
    control_key = "page.winws2_profile_setup.breadcrumb.control"
    profiles_key = "page.winws2_pages.title"
    profiles_default = "Настройка пресета"


class Zapret1ProfileSetupPage(ProfileSetupPageBase):
    launch_method = ZAPRET1_MODE
    title_key_name = "page.winws1_profile_setup.title"
    control_key = "page.winws1_profile_setup.breadcrumb.control"
    profiles_key = "page.winws1_pages.title"
    profiles_default = "Настройка пресета"
