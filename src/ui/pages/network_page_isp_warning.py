"""ISP DNS warning workflow/helper'ы для страницы Network."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class IspWarningWidgets:
    frame: object
    title: object
    content: object
    icon: object
    accept_button: object
    dismiss_button: object


def build_isp_warning_ui(
    *,
    parent,
    plan,
    qframe_cls,
    qvbox_layout_cls,
    qhbox_layout_cls,
    qlabel_cls,
    qpush_button_cls,
    qt_namespace,
    on_accept,
    on_dismiss,
) -> IspWarningWidgets:
    warning = qframe_cls()
    warning.setObjectName("ispDnsWarning")

    warning_layout = qvbox_layout_cls(warning)
    warning_layout.setContentsMargins(14, 10, 14, 10)
    warning_layout.setSpacing(6)

    title_row = qhbox_layout_cls()
    title_row.setSpacing(8)

    icon_label = qlabel_cls()
    title_row.addWidget(icon_label, 0, qt_namespace.AlignmentFlag.AlignTop)

    title_text = qlabel_cls(plan.title)
    title_row.addWidget(title_text, 1)
    warning_layout.addLayout(title_row)

    content_label = qlabel_cls(plan.content)
    content_label.setWordWrap(True)
    warning_layout.addWidget(content_label)

    btn_row = qhbox_layout_cls()
    btn_row.setSpacing(8)

    accept_btn = qpush_button_cls(plan.action_text)
    accept_btn.setCursor(qt_namespace.CursorShape.PointingHandCursor)
    accept_btn.clicked.connect(on_accept)
    btn_row.addWidget(accept_btn)

    dismiss_btn = qpush_button_cls(plan.dismiss_text)
    dismiss_btn.setCursor(qt_namespace.CursorShape.PointingHandCursor)
    dismiss_btn.clicked.connect(on_dismiss)
    btn_row.addWidget(dismiss_btn)

    btn_row.addStretch()
    warning_layout.addLayout(btn_row)

    return IspWarningWidgets(
        frame=warning,
        title=title_text,
        content=content_label,
        icon=icon_label,
        accept_button=accept_btn,
        dismiss_button=dismiss_btn,
    )


def insert_isp_warning_widget(*, layout, before_widget, add_widget_fn, warning_widget) -> None:
    idx = layout.indexOf(before_widget)
    if idx >= 0:
        layout.insertWidget(idx, warning_widget)
    else:
        add_widget_fn(warning_widget)


def render_isp_warning_styles(
    *,
    warning,
    icon_label,
    title_label,
    content_label,
    accept_button,
    dismiss_button,
    qta_module,
    theme_tokens,
) -> None:
    if warning is None:
        return

    warning.setStyleSheet(
        """
        QFrame {
            background-color: rgba(255, 152, 0, 0.12);
            border: 1px solid rgba(255, 152, 0, 0.35);
            border-radius: 8px;
        }
        """
    )
    if icon_label is not None:
        icon_label.setPixmap(qta_module.icon("fa5s.exclamation-triangle", color="#ff9800").pixmap(16, 16))
        icon_label.setStyleSheet("background: transparent; border: none;")
    if title_label is not None:
        title_label.setStyleSheet(
            f"""
            color: {theme_tokens.fg};
            font-size: 13px;
            font-weight: 600;
            background: transparent;
            border: none;
            """
        )
    if content_label is not None:
        content_label.setStyleSheet(
            f"""
            color: {theme_tokens.fg_muted};
            font-size: 12px;
            background: transparent;
            border: none;
            """
        )
    if accept_button is not None:
        accept_button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {theme_tokens.accent_hex};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 5px 14px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {theme_tokens.accent_hover_hex};
            }}
            """
        )
    if dismiss_button is not None:
        dismiss_button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                color: {theme_tokens.fg_muted};
                border: 1px solid {theme_tokens.toggle_off_border};
                border-radius: 6px;
                padding: 5px 14px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {theme_tokens.surface_bg_hover};
            }}
            """
        )


def hide_isp_warning_widget(*, warning_widget) -> None:
    if warning_widget is None:
        return
    warning_widget.hide()
    warning_widget.deleteLater()
