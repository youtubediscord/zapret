from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class DnsPageLoadWorker(QThread):
    loaded = pyqtSignal(int, object)
    finished_loading = pyqtSignal()

    def __init__(self, request_id: int, load_page_data_fn, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._load_page_data_fn = load_page_data_fn

    def run(self) -> None:
        try:
            state = self._load_page_data_fn()
            self.loaded.emit(self._request_id, state)
        except Exception as exc:
            log(f"DnsPageLoadWorker: ошибка загрузки DNS страницы: {exc}", "ERROR")
        self.finished_loading.emit()


class DnsConnectivityTestWorker(QThread):
    completed = pyqtSignal(int, list)

    def __init__(self, request_id: int, run_connectivity_test_fn, test_hosts, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._run_connectivity_test_fn = run_connectivity_test_fn
        self._test_hosts = tuple(test_hosts or ())

    def run(self) -> None:
        try:
            results = self._run_connectivity_test_fn(self._test_hosts)
        except Exception as exc:
            log(f"DnsConnectivityTestWorker: ошибка проверки DNS: {exc}", "ERROR")
            results = []
        self.completed.emit(self._request_id, list(results or []))


class DnsForceDnsActionWorker(QThread):
    completed = pyqtSignal(int, str, object, object)
    failed = pyqtSignal(int, str, str, object)

    def __init__(
        self,
        request_id: int,
        *,
        action: str,
        enabled: bool | None = None,
        adapters=None,
        language: str = "ru",
        get_force_dns_status: Callable[[], bool],
        enable_force_dns: Callable[..., Any],
        disable_force_dns: Callable[..., Any],
        refresh_dns_info: Callable[[list], Any],
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._action = str(action or "").strip()
        self._enabled = None if enabled is None else bool(enabled)
        self._adapters = list(adapters or [])
        self._language = str(language or "ru")
        self._get_force_dns_status = get_force_dns_status
        self._enable_force_dns = enable_force_dns
        self._disable_force_dns = disable_force_dns
        self._refresh_dns_info_action = refresh_dns_info

    def run(self) -> None:
        context = {
            "enabled": self._enabled,
            "language": self._language,
        }
        try:
            if self._action == "toggle":
                result = self._run_toggle()
            elif self._action == "reset_dhcp":
                result = self._run_reset_dhcp()
            else:
                raise ValueError(f"Неизвестное Force DNS действие: {self._action}")
        except Exception as exc:
            log(f"DnsForceDnsActionWorker: действие {self._action} не выполнено: {exc}", "ERROR")
            self.failed.emit(self._request_id, self._action, str(exc), context)
            return
        self.completed.emit(self._request_id, self._action, result, context)

    def _run_toggle(self) -> dict[str, object]:
        from dns.ui import page_plans as dns_page_plans

        requested_enabled = bool(self._enabled)
        current_state = bool(self._get_force_dns_status())
        if requested_enabled == current_state:
            plan = dns_page_plans.NetworkForceDnsTogglePlan(
                final_checked=current_state,
                force_dns_active=current_state,
                details_key=None,
                details_kwargs={},
                details_fallback="",
            )
            return {"plan": plan, "message": "", "changed": False}

        if requested_enabled:
            command_result = self._enable_force_dns(include_disconnected=False)
            plan = dns_page_plans.build_force_dns_toggle_plan(
                requested_enabled=True,
                success=bool(command_result.success),
                ok_count=int(command_result.affected_count or 0),
                total=int(command_result.total_count or 0),
            )
        else:
            command_result = self._disable_force_dns(reset_to_auto=False)
            plan = dns_page_plans.build_force_dns_toggle_plan(
                requested_enabled=False,
                success=bool(command_result.success),
            )
        return {
            "plan": plan,
            "message": str(command_result.message or ""),
            "changed": True,
            "dns_info": self._load_dns_info(),
        }

    def _run_reset_dhcp(self) -> dict[str, object]:
        from dns.ui import page_plans as dns_page_plans

        command_result = self._disable_force_dns(reset_to_auto=True)
        force_dns_active = bool(self._get_force_dns_status())
        plan = dns_page_plans.build_reset_dhcp_result_plan(
            success=bool(command_result.success),
            message=str(command_result.message or ""),
            force_dns_active=force_dns_active,
            language=self._language,
        )
        return {
            "plan": plan,
            "message": str(command_result.message or ""),
            "dns_info": self._load_dns_info(),
        }

    def _load_dns_info(self):
        if not self._adapters:
            return None
        return self._refresh_dns_info_action(self._adapters)


class DnsFlushCacheWorker(QThread):
    completed = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        *,
        language: str = "ru",
        flush_dns_cache: Callable[[], Any],
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._language = str(language or "ru")
        self._flush_dns_cache = flush_dns_cache

    def run(self) -> None:
        from dns.ui import page_plans as dns_page_plans

        try:
            result = self._flush_dns_cache()
            plan = dns_page_plans.build_flush_dns_cache_result_plan(
                success=bool(result.success),
                message=str(result.message or ""),
                language=self._language,
            )
        except Exception as exc:
            log(f"DnsFlushCacheWorker: ошибка сброса DNS кэша: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.completed.emit(self._request_id, plan)


class DnsIspWarningWorker(QThread):
    completed = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        *,
        adapters,
        dns_info: dict,
        force_dns_active: bool,
        language: str = "ru",
        is_isp_dns_warning_shown: Callable[[], bool],
        mark_isp_dns_warning_shown: Callable[[], Any],
        normalize_adapter_alias: Callable[[str], str],
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._adapters = list(adapters or [])
        self._dns_info = dict(dns_info or {})
        self._force_dns_active = bool(force_dns_active)
        self._language = str(language or "ru")
        self._is_isp_dns_warning_shown = is_isp_dns_warning_shown
        self._mark_isp_dns_warning_shown = mark_isp_dns_warning_shown
        self._normalize_adapter_alias = normalize_adapter_alias

    def run(self) -> None:
        from dns.ui import page_plans as dns_page_plans

        try:
            plan = dns_page_plans.build_isp_dns_warning_plan(
                self._adapters,
                self._dns_info,
                force_dns_active=self._force_dns_active,
                warning_already_shown=self._is_isp_dns_warning_shown(),
                normalize_alias_fn=self._normalize_adapter_alias,
                language=self._language,
            )
            if plan.should_show:
                self._mark_isp_dns_warning_shown()
        except Exception as exc:
            log(f"DnsIspWarningWorker: ошибка подготовки предупреждения ISP DNS: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.completed.emit(self._request_id, plan)


class DnsApplyWorker(QThread):
    completed = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        *,
        action: str,
        adapters,
        name: str = "",
        data=None,
        primary: str = "",
        secondary: str | None = None,
        ipv6_available: bool = False,
        apply_auto_dns: Callable[[list], Any],
        apply_provider_dns: Callable[..., Any],
        apply_custom_dns: Callable[..., Any],
        refresh_dns_info: Callable[[list], Any],
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._action = str(action or "").strip()
        self._adapters = list(adapters or [])
        self._name = str(name or "")
        self._data = dict(data or {})
        self._primary = str(primary or "").strip()
        self._secondary = None if secondary is None else str(secondary or "").strip()
        self._ipv6_available = bool(ipv6_available)
        self._apply_auto_dns = apply_auto_dns
        self._apply_provider_dns = apply_provider_dns
        self._apply_custom_dns = apply_custom_dns
        self._refresh_dns_info = refresh_dns_info

    def run(self) -> None:
        try:
            result = self._run_apply()
        except Exception as exc:
            log(f"DnsApplyWorker: действие {self._action} не выполнено: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.completed.emit(self._request_id, result)

    def _run_apply(self) -> dict[str, object]:
        from dns.ui import page_plans as dns_page_plans

        if not self._adapters:
            return {"plan": None, "dns_info": None}

        if self._action == "auto":
            command_result = self._apply_auto_dns(self._adapters)
            plan = dns_page_plans.build_auto_dns_apply_result_plan(
                adapter_count=len(self._adapters),
                success_count=int(command_result.affected_count or 0),
            )
        elif self._action == "provider":
            provider_plan = dns_page_plans.build_provider_dns_plan(
                name=self._name,
                data=self._data,
                ipv6_available=self._ipv6_available,
            )
            if not provider_plan.valid:
                return {
                    "plan": provider_plan,
                    "dns_info": None,
                }
            command_result = self._apply_provider_dns(
                self._adapters,
                provider_plan.ipv4,
                provider_plan.ipv6,
                ipv6_available=self._ipv6_available,
            )
            plan = dns_page_plans.build_provider_dns_apply_result_plan(
                name=self._name,
                adapter_count=len(self._adapters),
                success_count=int(command_result.affected_count or 0),
                ipv6_available=self._ipv6_available,
                ipv6=provider_plan.ipv6,
            )
        elif self._action == "custom":
            if not self._primary:
                return {"plan": None, "dns_info": None}
            command_result = self._apply_custom_dns(
                self._adapters,
                self._primary,
                self._secondary,
            )
            plan = dns_page_plans.build_custom_dns_apply_result_plan(
                primary=self._primary,
                adapter_count=len(self._adapters),
                success_count=int(command_result.affected_count or 0),
            )
        else:
            raise ValueError(f"Неизвестное DNS действие: {self._action}")

        dns_info = self._refresh_dns_info(self._adapters) if getattr(plan, "should_refresh", False) else None
        return {
            "plan": plan,
            "dns_info": dns_info,
            "adapters": self._adapters,
        }
