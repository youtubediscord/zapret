from __future__ import annotations

from datetime import datetime, timedelta
from typing import List


_APPLICATION_LOG = "Application"
_SUPPORTED_SOURCES = {"Application Error", "Windows Error Reporting"}


def _event_time_is_older(event_time, cutoff: datetime) -> bool:
    try:
        return bool(event_time < cutoff)
    except Exception:
        return False


def _read_event_message(event) -> str:
    try:
        import win32evtlogutil

        text = str(win32evtlogutil.SafeFormatMessage(event, _APPLICATION_LOG) or "").strip()
        if text:
            return text
    except Exception:
        pass

    try:
        inserts = list(getattr(event, "StringInserts", None) or ())
        text = "\n".join(str(item or "").strip() for item in inserts if str(item or "").strip())
        if text:
            return text
    except Exception:
        pass

    return ""


def get_recent_application_error_messages(*, process_name: str, minutes_back: int, max_events: int) -> List[str]:
    """Читает недавние события Application Error / WER для указанного процесса через Windows Event Log API."""
    normalized_process = str(process_name or "").strip().lower()
    if not normalized_process:
        return []

    import win32evtlog

    cutoff = datetime.now() - timedelta(minutes=max(1, int(minutes_back)))
    flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
    messages: List[str] = []

    handle = None
    try:
        handle = win32evtlog.OpenEventLog(None, _APPLICATION_LOG)
        while len(messages) < int(max_events):
            events = win32evtlog.ReadEventLog(handle, flags, 0)
            if not events:
                break

            for event in events:
                generated = getattr(event, "TimeGenerated", None)
                if generated is not None and _event_time_is_older(generated, cutoff):
                    return messages

                source = str(getattr(event, "SourceName", "") or "").strip()
                if source not in _SUPPORTED_SOURCES:
                    continue

                message = _read_event_message(event)
                if not message:
                    continue

                if normalized_process not in message.lower():
                    continue

                messages.append(message)
                if len(messages) >= int(max_events):
                    break
    except Exception:
        return messages
    finally:
        try:
            if handle is not None:
                import win32evtlog

                win32evtlog.CloseEventLog(handle)
        except Exception:
            pass

    return messages
