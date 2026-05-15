from __future__ import annotations

import time

from PyQt6.QtCore import Q_ARG, QMetaObject, QObject, Qt, QTimer, pyqtSlot

from app_notifications import advisory_notification, normalize_notification_payload
from log.log import global_logger, log
from ui.window_notification_actions import WindowNotificationActionHandler


class WindowNotificationCenter(QObject):
    """Единый центр показа верхнеуровневых системных уведомлений."""

    def __init__(
        self,
        parent,
        *,
        startup_state,
        runtime_feature,
        show_tray_notification,
        show_page,
        is_window_visible,
        is_window_minimized,
    ) -> None:
        super().__init__(parent)
        self._parent = parent
        self._startup_state = startup_state
        self._show_tray_notification = show_tray_notification
        self._show_page = show_page
        self._is_window_visible = is_window_visible
        self._is_window_minimized = is_window_minimized
        self._startup_notification_queue: list[dict] = []
        self._startup_notification_timer = QTimer(self)
        self._startup_notification_timer.setSingleShot(True)
        self._startup_notification_timer.timeout.connect(self.flush_startup_notification_queue)
        self._recent_signatures: dict[str, float] = {}
        self._action_handler = WindowNotificationActionHandler(
            notify=self.notify,
            runtime_feature=runtime_feature,
            show_page=self._show_page,
        )

    def register_global_error_notifier(self) -> None:
        """Подключает глобальные ERROR/CRITICAL логи к общему центру уведомлений."""
        try:
            if hasattr(global_logger, "set_ui_error_notifier"):
                global_logger.set_ui_error_notifier(self.enqueue_global_error_notification)
        except Exception as e:
            log(f"Ошибка подключения глобального error-notifier: {e}", "DEBUG")

    def enqueue_global_error_notification(self, message: str) -> None:
        text = str(message or "").strip()
        if not text:
            return

        self.notify_threadsafe(
            advisory_notification(
                level="error",
                title="Ошибка",
                content=text,
                source="global_logger",
                presentation="infobar",
                queue="immediate",
                duration=10000,
                dedupe_key=f"global_logger:{' '.join(text.split()).lower()}",
                dedupe_window_ms=2000,
            )
        )

    def notify_threadsafe(self, payload: dict | None) -> None:
        normalized = normalize_notification_payload(payload)
        if normalized is None:
            return

        try:
            QMetaObject.invokeMethod(
                self,
                "_notify_from_payload",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(object, dict(normalized)),
            )
        except Exception:
            self.notify(normalized)

    @pyqtSlot(object)
    def _notify_from_payload(self, payload: object) -> None:
        self.notify(payload if isinstance(payload, dict) else None)

    def notify_many(self, payloads: list[dict] | tuple[dict, ...] | None) -> None:
        for payload in payloads or ():
            self.notify(payload)

    def notify(self, payload: dict | None) -> None:
        normalized = normalize_notification_payload(payload)
        if normalized is None:
            return

        try:
            log(
                "Notification received: "
                f"source={normalized.get('source', '')}, "
                f"level={normalized.get('level', '')}, "
                f"queue={normalized.get('queue', '')}",
                "⏱ STARTUP",
            )
        except Exception:
            pass

        if self._should_skip_duplicate(normalized):
            try:
                log(
                    f"Notification skipped as duplicate: source={normalized.get('source', '')}",
                    "⏱ STARTUP",
                )
            except Exception:
                pass
            return

        if self._show_tray_notification_if_needed(normalized):
            try:
                log(
                    f"Notification redirected to tray: source={normalized.get('source', '')}",
                    "⏱ STARTUP",
                )
            except Exception:
                pass
            return

        if self._should_enqueue_for_startup(normalized):
            self._startup_notification_queue.append(dict(normalized))
            try:
                log(
                    "Notification queued for startup display: "
                    f"source={normalized.get('source', '')}, "
                    f"queue_size={len(self._startup_notification_queue)}",
                    "⏱ STARTUP",
                )
            except Exception:
                pass
            self.schedule_startup_notification_queue()
            return

        self._present_notification(normalized)

    def can_show_startup_notification_now(self) -> bool:
        startup_state = self._startup_state
        if startup_state is None:
            return False
        if not bool(startup_state.post_init_ready):
            return False
        if not bool(startup_state.background_init_started):
            return False
        try:
            return bool(self._is_window_visible())
        except Exception:
            return False

    def schedule_startup_notification_queue(self, delay_ms: int = 0) -> None:
        if self._startup_notification_timer.isActive():
            return
        self._startup_notification_timer.start(max(0, int(delay_ms)))

    def flush_startup_notification_queue(self) -> None:
        startup_state = self._startup_state
        if startup_state is None:
            self.schedule_startup_notification_queue(300)
            return
        if not bool(startup_state.post_init_ready):
            self.schedule_startup_notification_queue(300)
            return
        if not bool(startup_state.background_init_started):
            self.schedule_startup_notification_queue(300)
            return
        if not self._is_window_visible():
            return
        if not self._startup_notification_queue:
            return

        payload = self._startup_notification_queue.pop(0)
        try:
            log(
                "Notification dequeued for display: "
                f"source={payload.get('source', '')}, "
                f"remaining={len(self._startup_notification_queue)}",
                "⏱ STARTUP",
            )
        except Exception:
            pass
        self._present_notification(payload)

        if self._startup_notification_queue:
            self.schedule_startup_notification_queue(900)

    def _should_enqueue_for_startup(self, payload: dict) -> bool:
        queue_mode = str(payload.get("queue") or "auto").lower()
        if queue_mode == "immediate":
            return False
        if queue_mode == "startup":
            return not self.can_show_startup_notification_now()

        source = str(payload.get("source") or "")
        if source.startswith(("startup.", "deferred.")):
            return not self.can_show_startup_notification_now()

        return False

    def _present_notification(self, payload: dict) -> None:
        presentation = str(payload.get("presentation") or "auto").lower()

        try:
            log(
                "Notification presenting: "
                f"source={payload.get('source', '')}, "
                f"presentation={presentation}",
                "⏱ STARTUP",
            )
        except Exception:
            pass

        self._show_infobar_notification(payload)

    def _show_infobar_notification(self, payload: dict) -> None:
        try:
            from qfluentwidgets import InfoBar as _InfoBar, InfoBarPosition as _IBPos, PushButton

            level = str(payload.get("level") or "warning").strip().lower()
            title = self._resolve_title(payload)
            content = str(payload.get("content") or "").strip()
            duration = int(payload.get("duration", 12000) or 12000)
            orient = Qt.Orientation.Vertical if len(content) > 120 or "\n" in content else Qt.Orientation.Horizontal
            position = (
                _IBPos.TOP
                if str(payload.get("source") or "").startswith(("launch.", "global_logger"))
                else _IBPos.TOP_RIGHT
            )

            factory = {
                "success": _InfoBar.success,
                "info": _InfoBar.info,
                "error": _InfoBar.error,
                "warning": _InfoBar.warning,
            }.get(level, _InfoBar.warning)

            bar = factory(
                title=title,
                content=content,
                orient=orient,
                isClosable=True,
                position=position,
                duration=duration,
                parent=self._parent,
            )

            for action in payload.get("buttons") or []:
                button_text = str(action.get("text") or "").strip()
                if not button_text or bar is None:
                    continue

                callback = self._action_handler.build_action_callback(action, bar)
                if callback is None:
                    continue

                btn = PushButton(button_text)
                btn.setAutoDefault(False)
                btn.setDefault(False)

                def _wrap(_checked=False, _btn=btn, _callback=callback):
                    try:
                        _btn.setEnabled(False)
                        _callback()
                    finally:
                        _btn.setEnabled(True)

                btn.clicked.connect(_wrap)
                bar.addWidget(btn)
        except Exception as e:
            log(f"Не удалось показать InfoBar уведомление: {e}", "DEBUG")

    def _show_tray_notification_if_needed(self, payload: dict) -> bool:
        tray_title = str(payload.get("tray_title") or "").strip()
        tray_content = str(payload.get("tray_content") or "").strip()
        if not tray_title or not tray_content:
            return False

        if self._window_available_for_parenting():
            return False

        try:
            return bool(self._show_tray_notification(tray_title, tray_content))
        except Exception as e:
            log(f"Не удалось показать tray-уведомление: {e}", "DEBUG")
            return False

    def _window_available_for_parenting(self) -> bool:
        try:
            if not self._is_window_visible():
                return False
        except Exception:
            return False

        try:
            if self._is_window_minimized():
                return False
        except Exception:
            pass

        return True

    def _resolve_title(self, payload: dict) -> str:
        title = str(payload.get("title") or "").strip()
        if title:
            return title

        level = str(payload.get("level") or "info").strip().lower()
        return {
            "success": "Готово",
            "info": "Информация",
            "warning": "Предупреждение",
            "error": "Ошибка",
        }.get(level, "Уведомление")

    def _should_skip_duplicate(self, payload: dict) -> bool:
        self._prune_old_signatures()

        dedupe_window_ms = int(payload.get("dedupe_window_ms", 1500) or 0)
        if dedupe_window_ms <= 0:
            return False

        signature = str(payload.get("dedupe_key") or "").strip()
        if not signature:
            signature = "|".join(
                [
                    str(payload.get("source") or ""),
                    str(payload.get("level") or ""),
                    str(payload.get("title") or ""),
                    " ".join(str(payload.get("content") or "").split()),
                ]
            ).lower()

        if not signature:
            return False

        now_ts = time.time()
        last_ts = float(self._recent_signatures.get(signature, 0.0) or 0.0)
        if last_ts and (now_ts - last_ts) < (dedupe_window_ms / 1000.0):
            return True

        self._recent_signatures[signature] = now_ts
        return False

    def _prune_old_signatures(self) -> None:
        if not self._recent_signatures:
            return

        cutoff = time.time() - 30.0
        stale_keys = [key for key, ts in self._recent_signatures.items() if ts < cutoff]
        for key in stale_keys:
            self._recent_signatures.pop(key, None)
