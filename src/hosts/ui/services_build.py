"""Build-helper секции сервисов Hosts page."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFrame
from qfluentwidgets import ScrollArea

from ui.accessibility import set_control_accessibility, set_state_text
from ui.combo_accessibility import set_combo_items_accessibility
from ui.fluent_widgets import SettingsCard
from ui.theme import get_theme_tokens


@dataclass(slots=True)
class HostsServicesContainerWidgets:
    container: QWidget
    layout: QVBoxLayout


@dataclass(slots=True)
class HostsServicesGroupWidgets:
    card: SettingsCard
    title_label: object
    chips_scroll: ScrollArea | None
    chip_buttons: list[object]
    expand_button: object | None


@dataclass(slots=True)
class HostsServicesRowWidgets:
    row_layout: QHBoxLayout
    icon_label: QLabel
    name_label: object
    control: object


def build_hosts_services_container() -> HostsServicesContainerWidgets:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(16)
    return HostsServicesContainerWidgets(
        container=container,
        layout=layout,
    )


def build_hosts_services_section_title(*, text: str) -> QLabel:
    label = QLabel(text)
    tokens = get_theme_tokens()
    label.setStyleSheet(
        f"color: {tokens.fg_muted}; font-size: 13px; font-weight: 600; padding-top: 8px; padding-bottom: 4px;"
    )
    return label


def build_hosts_services_group(
    group_plan,
    *,
    off_label: str,
    strong_body_label_cls,
    make_chip,
    on_bulk_apply,
    expanded: bool = True,
    row_count: int | None = None,
    make_expand_button=None,
    on_toggle_expanded=None,
) -> HostsServicesGroupWidgets:
    card = SettingsCard()

    header = QHBoxLayout()
    header.setContentsMargins(0, 0, 0, 0)
    header.setSpacing(10)

    title_label = strong_body_label_cls(group_plan.title)
    header.addWidget(title_label, 0, Qt.AlignmentFlag.AlignVCenter)

    chips_scroll = None
    chip_buttons: list[object] = []

    if not group_plan.direct_only:
        chips = QWidget()
        chips_layout = QHBoxLayout(chips)
        chips_layout.setContentsMargins(0, 0, 0, 0)
        chips_layout.setSpacing(4)
        chips_layout.addStretch(1)

        off_btn = make_chip(off_label)
        chip_buttons.append(off_btn)
        _set_group_chip_accessibility(
            off_btn,
            group_title=group_plan.title,
            service_names=group_plan.service_names,
            profile_label="",
        )
        off_btn.clicked.connect(
            lambda _checked=False, n=tuple(group_plan.service_names): on_bulk_apply(list(n), None)
        )
        chips_layout.addWidget(off_btn)

        for profile_name, label in group_plan.common_profiles:
            if not label:
                continue
            btn = make_chip(label)
            chip_buttons.append(btn)
            _set_group_chip_accessibility(
                btn,
                group_title=group_plan.title,
                service_names=group_plan.service_names,
                profile_label=label,
            )
            btn.clicked.connect(
                lambda _checked=False, n=tuple(group_plan.service_names), p=profile_name: on_bulk_apply(list(n), p)
            )
            chips_layout.addWidget(btn)

        chips_scroll = ScrollArea()
        chips_scroll.setFrameShape(QFrame.Shape.NoFrame)
        chips_scroll.setWidgetResizable(True)
        chips_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        chips_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        chips_scroll.setFixedHeight(30)
        tokens = get_theme_tokens()
        chips_scroll.setStyleSheet(
            (
                "QScrollArea { background: transparent; border: none; }"
                "QScrollArea QWidget { background: transparent; }"
                "QScrollBar:horizontal { height: 4px; background: transparent; margin: 0px; }"
                f"QScrollBar::handle:horizontal {{ background: {tokens.scrollbar_handle}; border-radius: 2px; min-width: 24px; }}"
                f"QScrollBar::handle:horizontal:hover {{ background: {tokens.scrollbar_handle_hover}; }}"
                "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; height: 0px; background: transparent; border: none; }"
                "QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }"
            )
        )
        chips_scroll.setWidget(chips)
        header.addWidget(chips_scroll, 1, Qt.AlignmentFlag.AlignVCenter)
    else:
        header.addStretch(1)

    expand_button = None
    if row_count is not None and make_expand_button is not None and on_toggle_expanded is not None:
        count = max(0, int(row_count))
        label = "Скрыть" if expanded else f"Показать {count}"
        expand_button = make_expand_button(label)
        action_name = "Скрыть" if expanded else "Показать"
        set_control_accessibility(
            expand_button,
            name=f"{action_name} сервисы группы {group_plan.title}",
            description=f"В группе {group_plan.title}: {count} сервисов.",
        )
        set_state_text(expand_button, f"{action_name} сервисы группы {group_plan.title}")
        expand_button.clicked.connect(lambda _checked=False, t=group_plan.title: on_toggle_expanded(t))
        header.addWidget(expand_button, 0, Qt.AlignmentFlag.AlignVCenter)

    card.add_layout(header)
    return HostsServicesGroupWidgets(
        card=card,
        title_label=title_label,
        chips_scroll=chips_scroll,
        chip_buttons=chip_buttons,
        expand_button=expand_button,
    )


def build_hosts_service_row(
    row_plan,
    *,
    body_label_cls,
    combo_cls,
    toggle_cls,
    off_label: str,
    on_direct_toggle,
    on_profile_changed,
) -> HostsServicesRowWidgets:
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(10)

    icon_label = QLabel()
    icon_label.setFixedSize(20, 20)
    row.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

    name_label = body_label_cls(row_plan.service_name)
    row.addWidget(name_label, 1, Qt.AlignmentFlag.AlignVCenter)

    if row_plan.direct_only:
        control = toggle_cls()
        control.setEnabled(row_plan.toggle_enabled)
        control.setChecked(row_plan.toggle_checked)
        _update_direct_service_accessibility(
            control,
            service_name=row_plan.service_name,
            checked=row_plan.toggle_checked,
        )
        toggle_signal = getattr(control, "checkedChanged", None) or getattr(control, "toggled", None)
        toggle_signal.connect(
            lambda checked, c=control, s=row_plan.service_name: _update_direct_service_accessibility(
                c,
                service_name=s,
                checked=checked,
            )
        )
        toggle_signal.connect(
            lambda checked, s=row_plan.service_name: on_direct_toggle(s, checked)
        )
        row.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
    else:
        control = combo_cls()
        control.setFixedHeight(32)
        control.setCursor(Qt.CursorShape.PointingHandCursor)
        control.setMinimumWidth(220)
        control.addItem(off_label, userData=None)
        for profile_name, label in row_plan.profile_items:
            control.addItem(label, userData=profile_name)

        if row_plan.selected_profile:
            inferred_idx = control.findData(row_plan.selected_profile)
            if inferred_idx >= 0:
                control.setCurrentIndex(inferred_idx)
            else:
                control.setCurrentIndex(0)
        else:
            control.setCurrentIndex(0)

        _update_profile_service_accessibility(
            control,
            service_name=row_plan.service_name,
            off_label=off_label,
        )
        control.currentIndexChanged.connect(
            lambda _idx, c=control, s=row_plan.service_name, o=off_label: _update_profile_service_accessibility(
                c,
                service_name=s,
                off_label=o,
            )
        )
        control.currentIndexChanged.connect(
            lambda _idx, s=row_plan.service_name, c=control: on_profile_changed(s, c.currentData())
        )
        row.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)

    return HostsServicesRowWidgets(
        row_layout=row,
        icon_label=icon_label,
        name_label=name_label,
        control=control,
    )


def _update_direct_service_accessibility(control, *, service_name: str, checked: bool) -> None:
    state = "включено" if bool(checked) else "выключено"
    state_text = f"{service_name}, {state}"
    set_state_text(control, state_text)
    set_control_accessibility(
        control,
        name=state_text,
        description=f"Включает или отключает hosts-запись для сервиса {service_name}.",
    )


def _update_profile_service_accessibility(control, *, service_name: str, off_label: str) -> None:
    selected_text = str(control.currentText() or "").strip()
    if not selected_text or selected_text == str(off_label or ""):
        state = "отключено"
    else:
        state = f"выбран профиль {selected_text}"
    state_text = f"{service_name}, {state}"
    set_state_text(control, state_text)
    set_control_accessibility(
        control,
        name=state_text,
        description=(
            f"Выберите профиль hosts для сервиса {service_name}. "
            "Откройте список и выберите профиль стрелками вверх и вниз."
        ),
    )
    set_combo_items_accessibility(control, name=service_name)


def _set_group_chip_accessibility(button, *, group_title: str, service_names: list[str], profile_label: str) -> None:
    services_text = ", ".join(str(name) for name in service_names if str(name or "").strip())
    if profile_label:
        name = f"Применить {profile_label} к группе {group_title}"
        description = f"Применяет профиль {profile_label} к сервисам: {services_text}."
    else:
        name = f"Отключить группу {group_title}"
        description = f"Отключает hosts-профили для сервисов: {services_text}."
    set_control_accessibility(
        button,
        name=name,
        description=description,
    )
    set_state_text(button, name)
