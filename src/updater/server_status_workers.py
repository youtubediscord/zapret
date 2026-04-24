import time as _time
from datetime import datetime

from PyQt6.QtCore import QThread, pyqtSignal

from config.build_info import CHANNEL
from config.config import CHANNEL_DEV, CHANNEL_STABLE

from log.log import log

from ui.text_catalog import tr as tr_catalog
from updater.channel_utils import normalize_update_channel
from updater.github_release import normalize_version
from updater.server_config import CONNECT_TIMEOUT, READ_TIMEOUT, should_verify_ssl
from updater.telegram_updater import TELEGRAM_CHANNELS


class ServerCheckWorker(QThread):
    """Воркер для проверки статуса серверов."""

    server_checked = pyqtSignal(str, dict)
    all_complete = pyqtSignal()
    dpi_restart_needed = pyqtSignal()

    def __init__(self, update_pool_stats: bool = False, telegram_only: bool = False, *, language: str = "ru"):
        super().__init__()
        self._update_pool_stats = update_pool_stats
        self._telegram_only = telegram_only
        self._ui_language = language
        self._first_online_server_id = None
        self._stop_requested = False

    def stop(self) -> None:
        self._stop_requested = True

    def is_stop_requested(self) -> bool:
        return self._stop_requested

    def _tr(self, key: str, default: str) -> str:
        return tr_catalog(key, language=self._ui_language, default=default)

    @staticmethod
    def _request_versions_json(url: str, *, timeout, verify_ssl: bool):
        """Запрашивает all_versions.json без системного прокси."""
        import requests
        from updater.proxy_bypass import request_get_bypass_proxy

        headers = {
            "Accept": "application/json",
            "User-Agent": "Zapret-Updater/3.1",
        }

        if not verify_ssl:
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        def _decode_response(resp):
            if resp.status_code != 200:
                return None, f"HTTP {resp.status_code}"
            try:
                return resp.json(), None
            except Exception as e:
                return None, f"json error: {str(e)[:60]}"

        try:
            response = request_get_bypass_proxy(
                url,
                timeout=timeout,
                verify=verify_ssl,
                headers=headers,
            )
            data, error = _decode_response(response)
            return data, error, "direct"
        except requests.exceptions.Timeout:
            return None, "timeout", "direct"
        except requests.exceptions.ConnectionError as e:
            return None, f"connection error: {str(e)[:80]}", "direct"
        except requests.exceptions.RequestException as e:
            return None, str(e)[:80], "direct"
        except Exception as e:
            return None, str(e)[:80], "direct"

    def run(self):
        from updater.github_release import check_rate_limit
        from updater.server_pool import get_server_pool

        pool = get_server_pool()
        self._first_online_server_id = None
        self._stop_requested = False

        try:
            from updater.telegram_updater import get_telegram_version_info, is_telegram_available

            if self.is_stop_requested():
                self.all_complete.emit()
                return

            if is_telegram_available():
                start_time = _time.time()
                tg_channel = normalize_update_channel(CHANNEL)
                tg_info = get_telegram_version_info(tg_channel)
                response_time = _time.time() - start_time

                stable_version = tg_info.get("version") if tg_channel == CHANNEL_STABLE and tg_info else "—"
                dev_version = tg_info.get("version") if tg_channel == CHANNEL_DEV and tg_info else "—"
                stable_notes = tg_info.get("release_notes") if tg_channel == CHANNEL_STABLE and tg_info else ""
                dev_notes = tg_info.get("release_notes") if tg_channel == CHANNEL_DEV and tg_info else ""

                if tg_info and tg_info.get("version"):
                    tg_status = {
                        "status": "online",
                        "response_time": response_time,
                        "stable_version": stable_version,
                        "dev_version": dev_version,
                        "stable_notes": stable_notes,
                        "dev_notes": dev_notes,
                        "is_current": True,
                    }
                    self._first_online_server_id = "telegram"

                    from updater.update_cache import get_cached_all_versions, set_cached_all_versions

                    all_versions = get_cached_all_versions() or {}
                    all_versions[tg_channel] = {
                        "version": tg_info["version"],
                        "release_notes": tg_info.get("release_notes", ""),
                    }
                    set_cached_all_versions(all_versions, f"Telegram @{TELEGRAM_CHANNELS.get(tg_channel, tg_channel)}")
                else:
                    tg_status = {
                        "status": "error",
                        "response_time": response_time,
                        "error": self._tr("page.servers.error.version_not_found", "Версия не найдена"),
                        "is_current": False,
                    }
            else:
                tg_status = {
                    "status": "offline",
                    "response_time": 0,
                    "error": self._tr("page.servers.error.bot_not_configured", "Бот не настроен"),
                    "is_current": False,
                }

            self.server_checked.emit("Telegram Bot", tg_status)
            _time.sleep(0.02)
        except Exception as e:
            self.server_checked.emit(
                "Telegram Bot",
                {
                    "status": "error",
                    "error": str(e)[:40],
                    "is_current": False,
                },
            )

        if self.is_stop_requested():
            self.all_complete.emit()
            return

        if self._telegram_only:
            for server in pool.servers:
                if self.is_stop_requested():
                    break
                self.server_checked.emit(
                    server["name"],
                    {
                        "status": "skipped",
                        "response_time": 0,
                        "error": self._tr("page.servers.status.rate_limited", "Ожидание"),
                        "is_current": False,
                    },
                )
                _time.sleep(0.02)
            self.all_complete.emit()
            return

        dpi_was_stopped = False
        if self.is_stop_requested():
            self.all_complete.emit()
            return
        if pool.servers:
            first = pool.servers[0]
            test_url = f"https://{first['host']}:{first['https_port']}/api/all_versions.json"
            data, error, _ = self._request_versions_json(
                test_url,
                timeout=(5, 5),
                verify_ssl=should_verify_ssl(),
            )
            if data is None:
                from winws_runtime.runtime.sync_shutdown import is_any_runtime_running_sync, shutdown_runtime_sync

                if is_any_runtime_running_sync():
                    log("⚠️ DPI мешает проверке серверов — временно останавливаем", "🔄 UPDATE")
                    shutdown_runtime_sync(reason="server_status_probe", include_cleanup=True)
                    _time.sleep(0.5)
                    dpi_was_stopped = True

        for server in pool.servers:
            if self.is_stop_requested():
                break
            server_id = server["id"]
            server_name = f"{server['name']}"

            stats = pool.stats.get(server_id, {})
            blocked_until = stats.get("blocked_until")
            current_time = _time.time()

            if blocked_until and current_time < blocked_until:
                until_dt = datetime.fromtimestamp(blocked_until)
                status = {
                    "status": "blocked",
                    "response_time": 0,
                    "error": self._tr(
                        "page.servers.error.blocked_until_template",
                        "Заблокирован до {time}",
                    ).format(time=until_dt.strftime("%H:%M:%S")),
                    "is_current": False,
                }
                self.server_checked.emit(server_name, status)
                _time.sleep(0.02)
                continue

            monitor_timeout = (min(CONNECT_TIMEOUT, 3), min(READ_TIMEOUT, 5))
            status = None
            response_time = 0.0
            last_error = self._tr("page.servers.error.connect_failed", "Не удалось подключиться")

            protocol_attempts = [
                (
                    "HTTPS",
                    f"https://{server['host']}:{server['https_port']}/api/all_versions.json",
                    should_verify_ssl(),
                ),
                (
                    "HTTP",
                    f"http://{server['host']}:{server['http_port']}/api/all_versions.json",
                    False,
                ),
            ]

            for protocol, api_url, verify_ssl in protocol_attempts:
                attempt_start = _time.time()
                data, error, route = self._request_versions_json(
                    api_url,
                    timeout=monitor_timeout,
                    verify_ssl=verify_ssl,
                )
                response_time = _time.time() - attempt_start

                if data:
                    stable_notes = data.get("stable", {}).get("release_notes", "")
                    dev_notes = data.get("dev", {}).get("release_notes", "")

                    is_first_online = self._first_online_server_id is None
                    if is_first_online:
                        self._first_online_server_id = server_id

                    status = {
                        "status": "online",
                        "response_time": response_time,
                        "stable_version": data.get("stable", {}).get("version", "—"),
                        "dev_version": data.get("dev", {}).get("version", "—"),
                        "stable_notes": stable_notes,
                        "dev_notes": dev_notes,
                        "is_current": is_first_online,
                    }

                    from updater.update_cache import set_cached_all_versions

                    source = f"{server_name} ({protocol}{' bypass' if route == 'bypass' else ''})"
                    set_cached_all_versions(data, source)

                    if self._update_pool_stats:
                        pool.record_success(server_id, response_time)
                    break

                if error:
                    last_error = f"{protocol}: {error}"

            if status is None:
                status = {
                    "status": "error",
                    "response_time": response_time,
                    "error": last_error[:80],
                    "is_current": False,
                }
                if self._update_pool_stats:
                    pool.record_failure(server_id, last_error[:80])

            self.server_checked.emit(server_name, status)
            _time.sleep(0.02)

        if self.is_stop_requested():
            self.all_complete.emit()
            return

        try:
            rate_info = check_rate_limit()
            github_status = {
                "status": "online",
                "response_time": 0.5,
                "rate_limit": rate_info["remaining"],
                "rate_limit_max": rate_info["limit"],
            }
        except Exception as e:
            github_status = {
                "status": "error",
                "error": str(e)[:50],
            }

        self.server_checked.emit("GitHub API", github_status)

        if dpi_was_stopped:
            self.dpi_restart_needed.emit()

        self.all_complete.emit()


class VersionCheckWorker(QThread):
    """Воркер для получения версий."""

    version_found = pyqtSignal(str, dict)
    complete = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._stop_requested = False

    def stop(self) -> None:
        self._stop_requested = True

    def is_stop_requested(self) -> bool:
        return self._stop_requested

    def run(self):
        from updater.release_manager import get_latest_release
        from updater.server_pool import get_server_pool
        from updater.update_cache import (
            get_all_versions_source,
            get_cached_all_versions,
            set_cached_all_versions,
        )

        all_versions = get_cached_all_versions()
        source_name = get_all_versions_source() if all_versions else None
        self._stop_requested = False

        if not all_versions:
            pool = get_server_pool()
            current_server = pool.get_current_server()
            server_urls = pool.get_server_urls(current_server)
            monitor_timeout = (min(CONNECT_TIMEOUT, 3), min(READ_TIMEOUT, 5))

            for protocol, base_url in [("HTTPS", server_urls["https"]), ("HTTP", server_urls["http"])]:
                if self.is_stop_requested():
                    self.complete.emit()
                    return
                verify_ssl = should_verify_ssl() if protocol == "HTTPS" else False
                data, _, route = ServerCheckWorker._request_versions_json(
                    f"{base_url}/api/all_versions.json",
                    timeout=monitor_timeout,
                    verify_ssl=verify_ssl,
                )
                if data:
                    all_versions = data
                    source_name = f"{current_server['name']} ({protocol}{' bypass' if route == 'bypass' else ''})"
                    set_cached_all_versions(all_versions, source_name)
                    break

        if not all_versions:
            for channel in [CHANNEL_STABLE, CHANNEL_DEV]:
                if self.is_stop_requested():
                    break
                try:
                    release = get_latest_release(channel, use_cache=False)
                    if release:
                        self.version_found.emit(channel, release)
                    else:
                        self.version_found.emit(channel, {"error": "Не удалось получить"})
                except Exception as e:
                    self.version_found.emit(channel, {"error": str(e)})
            self.complete.emit()
            return

        for ui_channel, api_channel in {CHANNEL_STABLE: CHANNEL_STABLE, CHANNEL_DEV: CHANNEL_DEV}.items():
            if self.is_stop_requested():
                break
            data = all_versions.get(api_channel, {})
            if data and data.get("version"):
                result = {
                    "version": normalize_version(data.get("version", "0.0.0")),
                    "release_notes": data.get("release_notes", ""),
                    "source": source_name,
                }
                self.version_found.emit(ui_channel, result)
            else:
                self.version_found.emit(ui_channel, {"error": "Нет данных"})

        self.complete.emit()


__all__ = [
    "ServerCheckWorker",
    "VersionCheckWorker",
]
