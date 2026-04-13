from __future__ import annotations

from typing import Any


_LEVELS = {"success", "info", "warning", "error"}
_PRESENTATIONS = {"auto", "infobar"}
_QUEUES = {"auto", "startup", "immediate"}


def _normalize_text(value: Any, default: str = "") -> str:
    text = str(value or default).strip()
    return text or str(default or "").strip()


def notification_action(kind: str, text: str, **extra: Any) -> dict[str, Any]:
    action_kind = _normalize_text(kind)
    action_text = _normalize_text(text)
    if not action_kind or not action_text:
        return {}

    payload: dict[str, Any] = {
        "kind": action_kind,
        "text": action_text,
    }
    for key, value in extra.items():
        if value is not None:
            payload[str(key)] = value
    return payload


def notification_payload(
    *,
    level: str = "info",
    title: str = "",
    content: str = "",
    source: str = "system",
    presentation: str = "auto",
    queue: str = "auto",
    duration: int = 12000,
    buttons: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    dedupe_key: str = "",
    dedupe_window_ms: int = 1500,
    tray_title: str = "",
    tray_content: str = "",
) -> dict[str, Any]:
    normalized_level = _normalize_text(level, "info").lower()
    if normalized_level not in _LEVELS:
        normalized_level = "info"

    normalized_presentation = _normalize_text(presentation, "auto").lower()
    if normalized_presentation not in _PRESENTATIONS:
        normalized_presentation = "infobar"

    normalized_queue = _normalize_text(queue, "auto").lower()
    if normalized_queue not in _QUEUES:
        normalized_queue = "auto"

    normalized_buttons: list[dict[str, Any]] = []
    for item in buttons or ():
        if isinstance(item, dict):
            action = notification_action(
                str(item.get("kind") or ""),
                str(item.get("text") or ""),
                **{k: v for k, v in item.items() if k not in {"kind", "text"}},
            )
            if action:
                normalized_buttons.append(action)

    return {
        "level": normalized_level,
        "title": _normalize_text(title),
        "content": _normalize_text(content),
        "source": _normalize_text(source, "system"),
        "presentation": normalized_presentation,
        "queue": normalized_queue,
        "duration": max(-1, int(duration)),
        "buttons": normalized_buttons,
        "dedupe_key": _normalize_text(dedupe_key),
        "dedupe_window_ms": max(0, int(dedupe_window_ms)),
        "tray_title": _normalize_text(tray_title),
        "tray_content": _normalize_text(tray_content),
    }


def advisory_notification(
    *,
    level: str = "warning",
    title: str = "",
    content: str = "",
    source: str = "system",
    presentation: str = "infobar",
    queue: str = "startup",
    duration: int = 12000,
    buttons: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    dedupe_key: str = "",
    dedupe_window_ms: int = 1500,
    tray_title: str = "",
    tray_content: str = "",
) -> dict[str, Any]:
    return notification_payload(
        level=level,
        title=title,
        content=content,
        source=source,
        presentation=presentation,
        queue=queue,
        duration=duration,
        buttons=buttons,
        dedupe_key=dedupe_key,
        dedupe_window_ms=dedupe_window_ms,
        tray_title=tray_title,
        tray_content=tray_content,
    )


def normalize_notification_payload(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    return notification_payload(
        level=str(payload.get("level") or "info"),
        title=str(payload.get("title") or ""),
        content=str(payload.get("content") or ""),
        source=str(payload.get("source") or "system"),
        presentation=str(payload.get("presentation") or "auto"),
        queue=str(payload.get("queue") or "auto"),
        duration=int(payload.get("duration", 12000) or 12000),
        buttons=payload.get("buttons") or (),
        dedupe_key=str(payload.get("dedupe_key") or ""),
        dedupe_window_ms=int(payload.get("dedupe_window_ms", 1500) or 0),
        tray_title=str(payload.get("tray_title") or ""),
        tray_content=str(payload.get("tray_content") or ""),
    )
