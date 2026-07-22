from __future__ import annotations

from PyQt6.QtCore import QCoreApplication, QObject, pyqtSignal

from app_notifications import advisory_notification
from log.log import log
from main.post_startup_gate import bind_startup_gate, is_startup_host_alive
from main.post_startup_threading import enqueue_subsystem_task, schedule_after


class _UpdateCheckBridge(QObject):
    result_ready = pyqtSignal(object)


def install_update_check(
    startup_host,
    *,
    updater_feature,
    notify,
    set_status,
) -> None:
    update_bridge = _UpdateCheckBridge(QCoreApplication.instance())
    startup_check_token: int | None = None

    def _on_update_found(version: str, release_notes: str) -> None:
        if not is_startup_host_alive(startup_host):
            return
        try:
            try:
                set_status(f"Доступно обновление v{version}")
            except Exception:
                pass
            from app.page_names import PageName as StartupPageName

            if not startup_host.confirm_update_install(version):
                return
            startup_host.show_page(StartupPageName.SERVERS)
            page = startup_host.get_loaded_page(StartupPageName.SERVERS)
            if page is not None:
                page.present_startup_update(
                    version,
                    release_notes,
                    install_after_show=True,
                )
        except Exception as exc:
            log(f"Ошибка при показе диалога обновления: {exc}", "❌ ERROR")

    def _on_no_update(current_version: str) -> None:
        if not is_startup_host_alive(startup_host):
            return
        try:
            try:
                set_status(f"Обновлений нет, установлена версия {current_version}")
            except Exception:
                pass
            notify(
                advisory_notification(
                    level="success",
                    title="Обновлений нет",
                    content=f"Установлена актуальная версия {current_version}",
                    source="startup.update_check",
                    presentation="infobar",
                    queue="immediate",
                    duration=4000,
                    dedupe_key=f"startup.update_check:{current_version}",
                )
            )
        except Exception as exc:
            log(f"Ошибка при показе InfoBar: {exc}", "❌ ERROR")

    def _on_update_check_error(error: str) -> None:
        if not is_startup_host_alive(startup_host):
            return
        try:
            set_status("Не удалось проверить обновления")
        except Exception:
            pass
        log(f"Не удалось проверить обновления при запуске: {error}", "⚠️ UPDATE")

    def _on_update_check_skipped(reason: str) -> None:
        if not is_startup_host_alive(startup_host):
            return
        try:
            set_status(str(reason or "Проверка обновлений сейчас не требуется"))
        except Exception:
            pass

    def _on_update_check_finished(result: object) -> None:
        nonlocal startup_check_token
        payload = dict(result or {}) if isinstance(result, dict) else {
            "has_update": False,
            "version": "",
            "release_notes": "",
            "error": "Некорректный результат проверки обновлений",
        }
        token = startup_check_token
        startup_check_token = None
        if token is None or not updater_feature.finish_update_check(
            payload,
            source="startup",
            token=token,
        ):
            return

        if payload.get("skipped"):
            skip_reason = payload.get("skip_reason") or "Проверка обновлений сейчас не требуется"
            log(
                f"Автопроверка обновлений пропущена: {skip_reason}",
                "🔁 UPDATE",
            )
            _on_update_check_skipped(str(skip_reason))
            return
        if payload.get("error"):
            _on_update_check_error(str(payload.get("error") or ""))
            return
        if payload.get("has_update"):
            _on_update_found(
                str(payload.get("version") or ""),
                str(payload.get("release_notes") or ""),
            )
            return
        _on_no_update(str(payload.get("version") or ""))

    update_bridge.result_ready.connect(_on_update_check_finished)

    def _startup_update_worker() -> None:
        try:
            result = updater_feature.run_startup_update_check()
            update_bridge.result_ready.emit(dict(result or {}))
        except Exception as exc:
            log(f"Ошибка воркера проверки обновлений: {exc}", "❌ ERROR")
            update_bridge.result_ready.emit(
                {
                    "has_update": False,
                    "version": "",
                    "release_notes": "",
                    "error": str(exc),
                }
            )

    def _schedule_startup_update_check() -> None:
        nonlocal startup_check_token
        if not is_startup_host_alive(startup_host):
            return
        if not updater_feature.is_auto_update_enabled():
            log("Автопроверка обновлений при запуске отключена", "🔁 UPDATE")
            return
        token = updater_feature.begin_update_check(source="startup")
        if token is None:
            log(
                "Автопроверка при запуске не запущена: проверка уже идёт или выполнена в этой сессии",
                "🔁 UPDATE",
            )
            return
        startup_check_token = int(token)
        try:
            set_status("Проверка обновлений...")
        except Exception:
            pass

        enqueue_subsystem_task("update", "StartupUpdateCheckWorker", _startup_update_worker)

    def _schedule_startup_update_check_deferred() -> None:
        if not is_startup_host_alive(startup_host):
            return
        delay_ms = 12000
        log(f"Автопроверка обновлений отложена на {delay_ms}ms после готовности UI", "DEBUG")
        schedule_after(
            delay_ms,
            lambda: is_startup_host_alive(startup_host) and _schedule_startup_update_check(),
        )

    bind_startup_gate(
        startup_host.startup_post_init_ready,
        _schedule_startup_update_check_deferred,
        is_ready=lambda: bool(startup_host.startup_state.post_init_ready),
    )
