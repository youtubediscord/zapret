from __future__ import annotations

import time
import webbrowser

from PyQt6.QtCore import Q_ARG, QMetaObject, QObject, Qt, QTimer, pyqtSlot
from PyQt6.QtWidgets import QApplication

from app_notifications import advisory_notification, normalize_notification_payload
from log.log import global_logger, log



class WindowNotificationController(QObject):
    """Единый центр показа верхнеуровневых системных уведомлений."""

    def __init__(self, host) -> None:
        super().__init__(host)
        self.host = host
        self._startup_notification_queue: list[dict] = []
        self._startup_notification_timer = QTimer(self)
        self._startup_notification_timer.setSingleShot(True)
        self._startup_notification_timer.timeout.connect(self.flush_startup_notification_queue)
        self._recent_signatures: dict[str, float] = {}

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
        if not bool(getattr(self.host, "_startup_post_init_ready", False)):
            return False
        if not bool(getattr(self.host, "_startup_background_init_started", False)):
            return False
        try:
            return bool(self.host.isVisible())
        except Exception:
            return False

    def schedule_startup_notification_queue(self, delay_ms: int = 0) -> None:
        if self._startup_notification_timer.isActive():
            return
        self._startup_notification_timer.start(max(0, int(delay_ms)))

    def flush_startup_notification_queue(self) -> None:
        if not bool(getattr(self.host, "_startup_post_init_ready", False)):
            self.schedule_startup_notification_queue(300)
            return
        if not bool(getattr(self.host, "_startup_background_init_started", False)):
            self.schedule_startup_notification_queue(300)
            return
        if not self.host.isVisible():
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

    def copy_to_clipboard_with_feedback(self, text: str, *, label: str = "Текст") -> None:
        try:
            clipboard = QApplication.clipboard()
            if clipboard is None:
                raise RuntimeError("Буфер обмена недоступен")
            clipboard.setText(str(text or ""))
            self.notify(
                advisory_notification(
                    level="info",
                    title="Скопировано",
                    content=f"{label} скопирован в буфер обмена",
                    source="system.clipboard",
                    presentation="infobar",
                    queue="immediate",
                    duration=5000,
                    dedupe_key=f"clipboard.success:{label.lower()}",
                )
            )
        except Exception as e:
            log(f"Не удалось скопировать в буфер обмена: {e}", "DEBUG")
            self.notify(
                advisory_notification(
                    level="warning",
                    title="Не удалось скопировать",
                    content=f"Не удалось скопировать {label.lower()}",
                    source="system.clipboard",
                    presentation="infobar",
                    queue="immediate",
                    duration=7000,
                    dedupe_key=f"clipboard.failure:{label.lower()}",
                )
            )

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
                parent=self.host,
            )

            for action in payload.get("buttons") or []:
                button_text = str(action.get("text") or "").strip()
                if not button_text or bar is None:
                    continue

                callback = self._build_action_callback(action, bar)
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

    def _build_action_callback(self, action: dict, bar):
        kind = str(action.get("kind") or "").strip().lower()
        if not kind:
            return None

        if kind == "copy_text":
            return lambda: self.copy_to_clipboard_with_feedback(
                str(action.get("value") or ""),
                label=str(action.get("feedback_label") or "Текст"),
            )

        if kind == "open_url":
            return lambda: webbrowser.open(str(action.get("value") or ""))

        if kind == "open_strategy_page":
            return lambda: self._open_strategy_page_for_method(str(action.get("value") or ""), bar)

        if kind == "launch_conflict_kill_start":
            return lambda: self._run_launch_conflict_action(
                request_id=int(action.get("value") or 0),
                close_conflicts=True,
                bar=bar,
            )

        if kind == "launch_conflict_ignore_start":
            return lambda: self._run_launch_conflict_action(
                request_id=int(action.get("value") or 0),
                close_conflicts=False,
                bar=bar,
            )

        if kind == "launch_conflict_cancel":
            return lambda: self._cancel_launch_conflict_action(
                request_id=int(action.get("value") or 0),
                bar=bar,
            )

        if kind == "disable_proxy":
            return self._disable_proxy_with_feedback

        if kind == "disable_kaspersky_warning":
            return lambda: self._disable_kaspersky_warning_forever(bar)

        if kind == "disable_telega_warning":
            return lambda: self._disable_telega_warning_forever(bar)

        if kind == "autofix":
            return lambda: self._run_windivert_autofix(str(action.get("value") or ""), bar)

        return None

    def _disable_proxy_with_feedback(self) -> None:
        try:
            from startup.check_start import _disable_proxy

            success, disable_error = _disable_proxy()
        except Exception as e:
            success, disable_error = False, str(e)

        self.notify(
            advisory_notification(
                level="success" if success else "warning",
                title="Прокси отключен" if success else "Не удалось отключить прокси",
                content=(
                    "Ручной системный прокси был отключен."
                    if success else str(disable_error or "Настройки прокси не были изменены.")
                ),
                source="startup.proxy.action",
                presentation="infobar",
                queue="immediate",
                duration=7000 if success else 10000,
                dedupe_key="startup.proxy.action",
            )
        )

    def _run_launch_conflict_action(self, *, request_id: int, close_conflicts: bool, bar=None) -> None:
        controller = getattr(self.host, "launch_controller", None)
        if controller is None:
            self.notify(
                advisory_notification(
                    level="warning",
                    title="Не удалось продолжить запуск",
                    content="Контроллер запуска DPI недоступен.",
                    source="launch.conflicting_processes.action",
                    presentation="infobar",
                    queue="immediate",
                    duration=7000,
                    dedupe_key="launch.conflicting_processes.action",
                )
            )
            return

        try:
            if bar is not None:
                bar.close()
        except Exception:
            pass

        try:
            controller._resume_start_after_conflict_resolution(
                int(request_id or 0),
                close_conflicts=bool(close_conflicts),
            )
        except Exception as e:
            log(f"Не удалось обработать действие по конфликтующим процессам: {e}", "DEBUG")
            self.notify(
                advisory_notification(
                    level="warning",
                    title="Не удалось продолжить запуск",
                    content="Во время обработки конфликтующих процессов произошла ошибка.",
                    source="launch.conflicting_processes.action",
                    presentation="infobar",
                    queue="immediate",
                    duration=7000,
                    dedupe_key="launch.conflicting_processes.action",
                )
            )

    def _cancel_launch_conflict_action(self, *, request_id: int, bar=None) -> None:
        controller = getattr(self.host, "launch_controller", None)
        if controller is None:
            return

        try:
            if bar is not None:
                bar.close()
        except Exception:
            pass

        try:
            controller._cancel_start_after_conflict_prompt(int(request_id or 0))
        except Exception as e:
            log(f"Не удалось отменить запуск после предупреждения о конфликтах: {e}", "DEBUG")

    def _open_strategy_page_for_method(self, method: str, bar=None) -> None:
        try:
            from ui.navigation_targets import resolve_strategy_page_for_method
            from ui.window_adapter import show_page

            target_page = resolve_strategy_page_for_method(str(method or "").strip().lower())
            if target_page is None:
                raise RuntimeError("Не удалось определить страницу стратегий для текущего режима")

            ok = bool(show_page(self.host, target_page, allow_internal=True))
            if not ok:
                raise RuntimeError("Не удалось открыть страницу стратегий")

            try:
                if bar is not None:
                    bar.close()
            except Exception:
                pass
        except Exception as e:
            log(f"Не удалось открыть страницу стратегий: {e}", "DEBUG")
            self.notify(
                advisory_notification(
                    level="warning",
                    title="Не удалось открыть раздел",
                    content="Не удалось перейти в раздел стратегий автоматически.",
                    source="navigation.strategy_page",
                    presentation="infobar",
                    queue="immediate",
                    duration=7000,
                    dedupe_key="navigation.strategy_page",
                )
            )

    def _disable_kaspersky_warning_forever(self, bar=None) -> None:
        try:
            from startup.kaspersky import disable_kaspersky_warning_forever

            success = bool(disable_kaspersky_warning_forever())
        except Exception as e:
            log(f"Не удалось отключить предупреждение Kaspersky: {e}", "DEBUG")
            success = False

        try:
            if success and bar is not None:
                bar.close()
        except Exception:
            pass

        self.notify(
            advisory_notification(
                level="success" if success else "warning",
                title="Напоминание отключено" if success else "Не удалось отключить напоминание",
                content=(
                    "Предупреждение о Kaspersky больше не будет показываться."
                    if success else
                    "Не удалось сохранить настройку для предупреждения о Kaspersky."
                ),
                source="startup.kaspersky.action",
                presentation="infobar",
                queue="immediate",
                duration=5000 if success else 8000,
                dedupe_key="startup.kaspersky.action.disable_warning",
            )
        )

    def _disable_telega_warning_forever(self, bar=None) -> None:
        try:
            from startup.telega_check import disable_telega_warning_forever

            success = bool(disable_telega_warning_forever())
        except Exception as e:
            log(f"Не удалось отключить предупреждение Telega: {e}", "DEBUG")
            success = False

        try:
            if success and bar is not None:
                bar.close()
        except Exception:
            pass

        self.notify(
            advisory_notification(
                level="success" if success else "warning",
                title="Напоминание отключено" if success else "Не удалось отключить напоминание",
                content=(
                    "Предупреждение о Telega Desktop больше не будет показываться."
                    if success else
                    "Не удалось сохранить настройку для предупреждения о Telega Desktop."
                ),
                source="startup.telega.action",
                presentation="infobar",
                queue="immediate",
                duration=5000 if success else 8000,
                dedupe_key="startup.telega.action.disable_warning",
            )
        )

    def _run_windivert_autofix(self, action: str, bar) -> None:
        if not action:
            return

        try:
            from winws_runtime.health.process_health_check import execute_windivert_auto_fix

            ok, message = execute_windivert_auto_fix(action)
            try:
                if bar is not None:
                    bar.close()
            except Exception:
                pass

            self.notify(
                advisory_notification(
                    level="success" if ok else "warning",
                    title="Готово" if ok else "Не удалось",
                    content=str(message or ""),
                    source="launch.autofix",
                    presentation="infobar",
                    queue="immediate",
                    duration=5000 if ok else 8000,
                    dedupe_key=f"launch.autofix:{action}",
                )
            )
        except Exception as e:
            log(f"Auto-fix error: {e}", "ERROR")

    def _show_tray_notification_if_needed(self, payload: dict) -> bool:
        tray_title = str(payload.get("tray_title") or "").strip()
        tray_content = str(payload.get("tray_content") or "").strip()
        if not tray_title or not tray_content:
            return False

        tray_manager = getattr(self.host, "tray_manager", None)
        if tray_manager is None:
            return False

        if self._window_available_for_parenting():
            return False

        try:
            tray_manager.show_notification(tray_title, tray_content)
            return True
        except Exception as e:
            log(f"Не удалось показать tray-уведомление: {e}", "DEBUG")
            return False

    def _window_available_for_parenting(self) -> bool:
        try:
            if not self.host.isVisible():
                return False
        except Exception:
            return False

        try:
            if self.host.isMinimized():
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
