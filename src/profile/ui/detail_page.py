from __future__ import annotations

import re

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import QHBoxLayout, QWidget

from log.log import log
from profile.service import ProfilePresetService
from profile.winws2_editable_settings import normalize_winws2_filter_value
from qfluentwidgets import BodyLabel, BreadcrumbBar, CheckBox, ComboBox, LineEdit, PlainTextEdit, PrimaryPushButton, TitleLabel
from ui.page_dependencies import require_page_app_context
from ui.pages.base_page import BasePage
from ui.text_catalog import tr as tr_catalog


_SIMPLE_RANGE_RE = re.compile(r"^-?(?P<mode>[nd])(?P<value>\d+)$", re.IGNORECASE)


class ProfileDetailPageBase(BasePage):
    strategy_selected = pyqtSignal(str, str)
    back_clicked = pyqtSignal()
    navigate_to_root = pyqtSignal()
    profile_ui_mode_override: str | None = None
    launch_method = "zapret2_mode"
    title_key_name = "page.z2_profile_detail.title"
    control_key = "page.z2_profile_detail.breadcrumb.control"
    profiles_key = "page.z2_pages.title"
    profiles_default = "Профили Zapret 2"

    def __init__(self, parent=None):
        super().__init__(
            title="",
            parent=parent,
            title_key=self.title_key_name,
        )
        self.parent_app = parent
        self._profile_key = ""
        self._loading = False
        self._payload = None
        self._settings_title = None
        self._settings_container = None
        self._build_content()

    def _require_app_context(self):
        return require_page_app_context(
            self,
            parent=self.parent(),
            error_message="AppContext is required for profile detail page",
        )

    def _service(self) -> ProfilePresetService:
        return ProfilePresetService(self._require_app_context(), self.launch_method)

    def _build_content(self) -> None:
        if self.title_label is not None:
            self.title_label.hide()
        if self.subtitle_label is not None:
            self.subtitle_label.hide()

        self._breadcrumb = BreadcrumbBar()
        self._breadcrumb.currentItemChanged.connect(self._on_breadcrumb_item_changed)
        self.layout.addWidget(self._breadcrumb)

        self._title = TitleLabel("Profile")
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

        self._back_button = PrimaryPushButton("К списку profiles")
        self._back_button.clicked.connect(self.back_clicked.emit)
        controls_layout.addWidget(self._back_button)

        self.layout.addWidget(controls)

        self._settings_container = QWidget(self)
        settings_layout = QHBoxLayout(self._settings_container)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(12)

        self._filter_combo = ComboBox()
        self._filter_combo.setMinimumWidth(150)
        self._filter_combo.addItem(tr_catalog("page.z2_profile_detail.filter.hostlist", language=self._ui_language, default="Hostlist"), userData="hostlist")
        self._filter_combo.addItem(tr_catalog("page.z2_profile_detail.filter.ipset", language=self._ui_language, default="IPset"), userData="ipset")
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

        self._save_settings_button = PrimaryPushButton("Сохранить")
        self._save_settings_button.clicked.connect(self._on_save_settings_clicked)
        settings_layout.addWidget(self._save_settings_button)

        self._in_range_mode.currentIndexChanged.connect(
            lambda _index: self._sync_range_value_enabled(self._in_range_mode, self._in_range_value)
        )
        self._out_range_mode.currentIndexChanged.connect(
            lambda _index: self._sync_range_value_enabled(self._out_range_mode, self._out_range_value)
        )
        self._filter_combo.currentIndexChanged.connect(lambda _index: self._sync_filter_value_for_kind())

        self._settings_title = self.add_section_title("Настройки profile", return_widget=True)
        self.layout.addWidget(self._settings_container)

        self.add_section_title("Когда profile применяется")
        self._match_text = PlainTextEdit()
        self._match_text.setReadOnly(True)
        self._match_text.setMinimumHeight(110)
        self.layout.addWidget(self._match_text)

        self.add_section_title("Какая готовая стратегия выбрана")
        self._strategy_text = PlainTextEdit()
        self._strategy_text.setReadOnly(True)
        self._strategy_text.setMinimumHeight(160)
        self.layout.addWidget(self._strategy_text)

        self.add_section_title("Что записано в profile")
        self._raw_text = PlainTextEdit()
        self._raw_text.setReadOnly(True)
        self._raw_text.setMinimumHeight(220)
        self.layout.addWidget(self._raw_text)

    def _fill_range_combo(self, combo: ComboBox) -> None:
        combo.addItem("a", userData="a")
        combo.addItem("x", userData="x")
        combo.addItem("n", userData="n")
        combo.addItem("d", userData="d")
        combo.addItem("custom", userData="custom")

    def _rebuild_breadcrumb(self) -> None:
        self._breadcrumb.blockSignals(True)
        try:
            self._breadcrumb.clear()
            self._breadcrumb.addItem("control", tr_catalog(self.control_key, language=self._ui_language, default="Управление"))
            self._breadcrumb.addItem("profiles", tr_catalog(self.profiles_key, language=self._ui_language, default=self.profiles_default))
            title = str(getattr(getattr(self._payload, "item", None), "display_name", "") or "Profile")
            self._breadcrumb.addItem("detail", title)
        finally:
            self._breadcrumb.blockSignals(False)

    def _on_breadcrumb_item_changed(self, key: str) -> None:
        self._rebuild_breadcrumb()
        if key == "control":
            self.navigate_to_root.emit()
        elif key == "profiles":
            self.back_clicked.emit()

    def show_profile(self, profile_key: str) -> None:
        self._profile_key = str(profile_key or "").strip()
        self.reload_current_profile()

    def reload_current_profile(self) -> None:
        if not self._profile_key:
            return
        try:
            payload = self._service().get_profile_detail(self._profile_key)
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось прочитать profile {self._profile_key}: {exc}", "ERROR")
            payload = None
        if payload is None:
            self._title.setText("Profile не найден")
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
            self._strategy_combo.addItem("custom", userData="custom")
            for strategy_id, entry in payload.strategy_entries.items():
                self._strategy_combo.addItem(entry.name, userData=strategy_id)

            current_id = item.strategy_id or "none"
            for index in range(self._strategy_combo.count()):
                if self._strategy_combo.itemData(index) == current_id:
                    self._strategy_combo.setCurrentIndex(index)
                    break

            self._match_text.setPlainText(payload.match_summary)
            self._strategy_text.setPlainText(payload.raw_strategy_text or "custom")
            self._raw_text.setPlainText(payload.raw_profile_text)
            self._rebuild_breadcrumb()
        finally:
            self._loading = False

    def _apply_editable_settings(self, payload) -> None:
        is_winws2 = self.launch_method == "zapret2_mode"
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

    def _sync_filter_value_for_kind(self) -> None:
        if self._loading or self.launch_method != "zapret2_mode":
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

    def _on_save_settings_clicked(self) -> None:
        if self._loading or not self._profile_key or self.launch_method != "zapret2_mode":
            return
        filter_value = self._filter_value.text().strip()
        filter_enabled = bool(getattr(self._payload, "editable_filter_enabled", True))
        if filter_enabled and not filter_value:
            return
        try:
            new_key = self._service().update_winws2_editable_settings(
                self._profile_key,
                filter_kind=str(self._filter_combo.itemData(self._filter_combo.currentIndex()) or "hostlist"),
                filter_value=filter_value,
                in_range=self._range_expression_from_controls(self._in_range_mode, self._in_range_value, default="x"),
                out_range=self._range_expression_from_controls(self._out_range_mode, self._out_range_value, default="a"),
            )
            if new_key:
                self._profile_key = new_key
            self.reload_current_profile()
            self.strategy_selected.emit(self._profile_key, "custom")
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось сохранить настройки profile: {exc}", "ERROR")

    def _on_enabled_changed(self, state: int) -> None:
        if self._loading or not self._profile_key:
            return
        enabled = bool(state == Qt.CheckState.Checked.value or state == 2)
        try:
            new_key = self._service().set_profile_enabled(self._profile_key, enabled)
            if new_key:
                self._profile_key = new_key
            self.reload_current_profile()
            self.strategy_selected.emit(self._profile_key, "custom" if enabled else "none")
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось изменить состояние profile: {exc}", "ERROR")

    def _on_strategy_changed(self, index: int) -> None:
        if self._loading or not self._profile_key:
            return
        strategy_id = str(self._strategy_combo.itemData(index) or "").strip()
        if not strategy_id or strategy_id in {"none", "custom"}:
            return
        try:
            new_key = self._service().apply_strategy(self._profile_key, strategy_id)
            if new_key:
                self._profile_key = new_key
            self.reload_current_profile()
            self.strategy_selected.emit(self._profile_key, strategy_id)
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось применить strategy: {exc}", "ERROR")


class ProfileDetailPage(ProfileDetailPageBase):
    launch_method = "zapret2_mode"
    title_key_name = "page.z2_profile_detail.title"
    control_key = "page.z2_profile_detail.breadcrumb.control"
    profiles_key = "page.z2_pages.title"
    profiles_default = "Профили Zapret 2"


class Zapret1ProfileDetailPage(ProfileDetailPageBase):
    launch_method = "zapret1_mode"
    title_key_name = "page.z1_profile_detail.title"
    control_key = "page.z1_profile_detail.breadcrumb.control"
    profiles_key = "page.z1_pages.title"
    profiles_default = "Профили Zapret 1"
