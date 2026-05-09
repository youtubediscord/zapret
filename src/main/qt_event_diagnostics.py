from __future__ import annotations

from collections import Counter

from PyQt6.QtCore import QEvent, QObject, QTimer

from log.log import log


class QtEventDiagnosticFilter(QObject):
    """Lightweight Qt event counter for finding hidden repaint/timer loops."""

    _EVENT_NAMES = {
        int(QEvent.Type.Paint): "Paint",
        int(QEvent.Type.Timer): "Timer",
        int(QEvent.Type.UpdateRequest): "UpdateRequest",
        int(QEvent.Type.LayoutRequest): "LayoutRequest",
        int(QEvent.Type.Resize): "Resize",
        int(QEvent.Type.Move): "Move",
        int(QEvent.Type.Show): "Show",
        int(QEvent.Type.Hide): "Hide",
        int(QEvent.Type.StyleChange): "StyleChange",
        int(QEvent.Type.PaletteChange): "PaletteChange",
        int(QEvent.Type.DynamicPropertyChange): "DynamicPropertyChange",
    }

    def __init__(self, app, *, interval_ms: int = 5000, top_n: int = 12, max_reports: int | None = None):
        super().__init__(app)
        self._app = app
        self._top_n = max(1, int(top_n))
        self._max_reports = max(1, int(max_reports)) if max_reports is not None else None
        self._reports_done = 0
        self._events: Counter[tuple[str, str]] = Counter()
        self._timer = QTimer(self)
        self._timer.setInterval(max(1000, int(interval_ms)))
        self._timer.timeout.connect(self._flush)

    def start(self) -> None:
        self._app.installEventFilter(self)
        self._timer.start()
        log("Qt event diagnostic started", "INFO")

    def eventFilter(self, obj, event):  # noqa: N802
        try:
            event_type = int(event.type())
            event_name = self._EVENT_NAMES.get(event_type)
            if event_name is not None:
                cls_name = obj.__class__.__name__ if obj is not None else "<none>"
                object_name = ""
                try:
                    object_name = str(obj.objectName() or "")
                except Exception:
                    object_name = ""
                label = f"{cls_name}:{object_name}" if object_name else cls_name
                self._events[(event_name, label)] += 1
        except Exception:
            pass
        return False

    def _flush(self) -> None:
        self._reports_done += 1
        if not self._events:
            log("[QT_EVENT_DIAG] no counted events", "INFO")
            self._stop_if_complete()
            return
        top = self._events.most_common(self._top_n)
        self._events.clear()
        report = "\n".join(
            f"  {count:5d}  {event_name:<22} {label}"
            for (event_name, label), count in top
        )
        log(f"[QT_EVENT_DIAG top-{self._top_n} per {self._timer.interval()}ms]\n{report}", "INFO")
        self._stop_if_complete()

    def _stop_if_complete(self) -> None:
        if self._max_reports is None:
            return
        if self._reports_done < self._max_reports:
            return
        self.stop()

    def stop(self) -> None:
        try:
            self._timer.stop()
        except Exception:
            pass
        try:
            self._app.removeEventFilter(self)
        except Exception:
            pass
        try:
            if getattr(self._app, "_zapret_qt_event_diagnostic", None) is self:
                setattr(self._app, "_zapret_qt_event_diagnostic", None)
        except Exception:
            pass


def install_qt_event_diagnostic(
    app,
    *,
    interval_ms: int = 5000,
    top_n: int = 12,
    max_reports: int | None = None,
) -> QtEventDiagnosticFilter | None:
    if app is None:
        return None
    existing = getattr(app, "_zapret_qt_event_diagnostic", None)
    if isinstance(existing, QtEventDiagnosticFilter):
        return existing
    diagnostic = QtEventDiagnosticFilter(
        app,
        interval_ms=interval_ms,
        top_n=top_n,
        max_reports=max_reports,
    )
    setattr(app, "_zapret_qt_event_diagnostic", diagnostic)
    diagnostic.start()
    return diagnostic
