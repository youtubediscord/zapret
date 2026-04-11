"""Runtime/status helper'ы для страницы логов."""

from __future__ import annotations

import html


def render_send_status_label(*, label, text: str, tone: str, theme_tokens) -> None:
    if label is None:
        return

    normalized_text = str(text or "")
    normalized_tone = str(tone or "neutral").strip().lower()

    label.setText(normalized_text)
    if not normalized_text:
        label.setStyleSheet("")
        return

    color = theme_tokens.accent_hex
    if normalized_tone == "error":
        color = "#f87171" if not theme_tokens.is_light else "#dc2626"
    label.setStyleSheet(f"color: {color}; font-size: 11px;")


def resolve_winws_status_style(
    *,
    current_text: str,
    neutral_color: str,
    running_color: str,
    error_color: str,
) -> tuple[str, str]:
    text = str(current_text or "").strip()
    if not text:
        return "neutral", ""
    if "PID:" in text:
        return "running", text
    if "ошиб" in text.lower():
        return "error", text
    return "neutral", text


def set_winws_status(label, *, kind: str, text: str, neutral_color: str, running_color: str, error_color: str) -> None:
    if kind == "running":
        color = running_color
    elif kind == "error":
        color = error_color
    else:
        color = neutral_color

    label.setText(text)
    label.setStyleSheet(f"color: {color}; font-size: 11px;")


def compute_errors_text_height(*, text_edit, min_height: int, max_height: int) -> int:
    try:
        is_empty = not bool(text_edit.toPlainText().strip())
    except Exception:
        is_empty = True

    if is_empty:
        return min_height

    try:
        document_height = int(text_edit.document().size().height())
    except Exception:
        document_height = min_height

    frame_height = int(text_edit.frameWidth()) * 2
    content_padding = 16
    target_height = document_height + frame_height + content_padding
    return max(min_height, min(max_height, target_height))


def append_error(*, errors_text, errors_count_label, tr_fn, current_count: int, text: str) -> int:
    next_count = int(current_count) + 1
    errors_count_label.setText(
        tr_fn("page.logs.errors.count", "Ошибок: {count}").format(count=next_count)
    )
    errors_text.append(text)
    return next_count


def clear_errors(*, errors_text, errors_count_label, tr_fn) -> int:
    errors_text.clear()
    errors_count_label.setText(
        tr_fn("page.logs.errors.count", "Ошибок: {count}").format(count=0)
    )
    return 0


def format_winws_output_line(*, text: str, stream_type: str, stdout_color: str, stderr_color: str) -> str:
    safe_text = html.escape(text)
    if stream_type == "stderr":
        return f'<span style="color: {stderr_color};">{safe_text}</span>'
    return f'<span style="color: {stdout_color};">{safe_text}</span>'
