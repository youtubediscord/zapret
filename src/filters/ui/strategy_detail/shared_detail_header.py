from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DetailHeaderTextState:
    title_text: str
    subtitle_text: str
    detail_text: str
    description_text: str


def _read_target_field(target_info, field_name: str, default: str = "") -> str:
    if target_info is None:
        return str(default or "")
    try:
        if isinstance(target_info, dict):
            return str(target_info.get(field_name, default) or default or "").strip()
        return str(getattr(target_info, field_name, default) or default or "").strip()
    except Exception:
        return str(default or "")


def build_detail_header_text_state(
    *,
    target_info,
    target_key: str = "",
    tr,
    ports_text_key: str,
    ports_text_default: str,
    empty_title: str = "",
    empty_detail: str = "Target",
) -> DetailHeaderTextState:
    target_title = _read_target_field(target_info, "full_name", target_key)
    description = _read_target_field(target_info, "description", "")
    protocol = _read_target_field(target_info, "protocol", "")
    ports = _read_target_field(target_info, "ports", "")

    subtitle_parts: list[str] = []
    if protocol:
        subtitle_parts.append(protocol)
    if ports:
        subtitle_parts.append(tr(ports_text_key, ports_text_default, ports=ports))

    resolved_title = target_title or str(empty_title or target_key or "")
    resolved_detail = target_title or str(empty_detail or target_key or "")

    return DetailHeaderTextState(
        title_text=resolved_title,
        subtitle_text=" | ".join(subtitle_parts),
        detail_text=resolved_detail,
        description_text=description,
    )


def apply_detail_breadcrumb(
    breadcrumb,
    *,
    control_text: str,
    strategies_text: str,
    detail_text: str,
) -> None:
    if breadcrumb is None:
        return

    breadcrumb.blockSignals(True)
    try:
        breadcrumb.clear()
        breadcrumb.addItem("control", control_text)
        breadcrumb.addItem("strategies", strategies_text)
        breadcrumb.addItem("detail", detail_text)
    finally:
        breadcrumb.blockSignals(False)


def apply_detail_header_state(
    title_label,
    subtitle_label,
    breadcrumb,
    *,
    title_text: str,
    subtitle_text: str,
    detail_text: str,
    control_text: str,
    strategies_text: str,
) -> None:
    try:
        if title_label is not None:
            title_label.setText(title_text)
    except Exception:
        pass

    try:
        if subtitle_label is not None:
            subtitle_label.setText(subtitle_text)
    except Exception:
        pass

    apply_detail_breadcrumb(
        breadcrumb,
        control_text=control_text,
        strategies_text=strategies_text,
        detail_text=detail_text,
    )
