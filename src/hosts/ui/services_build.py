"""Build-helper секции сервисов Hosts page."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame

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
    chips_scroll: QScrollArea | None
    chip_buttons: list[object]


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
        off_btn.clicked.connect(
            lambda _checked=False, n=tuple(group_plan.service_names): on_bulk_apply(list(n), None)
        )
        chips_layout.addWidget(off_btn)

        for profile_name, label in group_plan.common_profiles:
            if not label:
                continue
            btn = make_chip(label)
            chip_buttons.append(btn)
            btn.clicked.connect(
                lambda _checked=False, n=tuple(group_plan.service_names), p=profile_name: on_bulk_apply(list(n), p)
            )
            chips_layout.addWidget(btn)

        chips_scroll = QScrollArea()
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

    card.add_layout(header)
    return HostsServicesGroupWidgets(
        card=card,
        title_label=title_label,
        chips_scroll=chips_scroll,
        chip_buttons=chip_buttons,
    )


def build_hosts_service_row(
    row_plan,
    *,
    body_label_cls,
    combo_cls,
    has_fluent: bool,
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
        control.toggled.connect(
            lambda checked, s=row_plan.service_name: on_direct_toggle(s, checked)
        )
        row.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
    else:
        if has_fluent and combo_cls is not None:
            control = combo_cls()
        else:
            from PyQt6.QtWidgets import QComboBox as _QComboBox

            control = _QComboBox()
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
