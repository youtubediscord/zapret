from __future__ import annotations

import subprocess
from dataclasses import dataclass

from config import REGISTRY_PATH
from log import log
from ui.text_catalog import tr as tr_catalog


@dataclass(slots=True)
class NetworkPageData:
    adapters: list[tuple[str, str]]
    dns_info: dict[str, dict[str, list[str]]]
    ipv6_available: bool
    force_dns_active: bool


@dataclass(slots=True)
class NetworkPageInitPlan:
    should_start_initial_load: bool
    load_delay_ms: int


@dataclass(slots=True)
class NetworkForceDnsStatusPlan:
    text: str
    enabled: bool


@dataclass(slots=True)
class NetworkForceDnsTogglePlan:
    final_checked: bool
    force_dns_active: bool
    details_key: str | None
    details_kwargs: dict
    details_fallback: str


@dataclass(slots=True)
class NetworkConnectivityTestPlan:
    test_hosts: list[tuple[str, str]]


@dataclass(slots=True)
class NetworkConnectivityTestResultPlan:
    all_ok: bool
    report: str
    infobar_level: str
    title: str
    content: str


@dataclass(slots=True)
class NetworkProviderDnsPlan:
    valid: bool
    ipv4: list[str]
    ipv6: list[str]
    log_level: str | None
    log_message: str


@dataclass(slots=True)
class NetworkDnsApplyResultPlan:
    should_refresh: bool
    log_level: str | None
    log_message: str


@dataclass(slots=True)
class NetworkResetDhcpResultPlan:
    force_dns_active: bool
    should_select_auto: bool
    status_details_key: str
    infobar_level: str
    infobar_title: str
    infobar_content: str


@dataclass(slots=True)
class NetworkFlushDnsCacheResultPlan:
    success: bool
    infobar_level: str | None
    title: str
    content: str


@dataclass(slots=True)
class NetworkIspDnsWarningPlan:
    should_show: bool
    title: str
    content: str
    action_text: str
    dismiss_text: str


@dataclass(slots=True)
class NetworkIspDnsActionPlan:
    hide_warning: bool
    enable_force_dns: bool


@dataclass(slots=True)
class NetworkAdapterDnsRefreshEntry:
    adapter_name: str
    adapter_data: dict
    ipv4: list[str]
    ipv6: list[str]


@dataclass(slots=True)
class NetworkAdapterDnsRefreshPlan:
    entries: list[NetworkAdapterDnsRefreshEntry]
    log_level: str
    log_message: str


@dataclass(slots=True)
class NetworkDnsSelectionPlan:
    kind: str
    selected_provider: str | None
    custom_primary: str
    custom_secondary: str


class NetworkPageController:
    _dns_manager_instance = None

    @staticmethod
    def build_page_init_plan(*, runtime_initialized: bool) -> NetworkPageInitPlan:
        return NetworkPageInitPlan(
            should_start_initial_load=not bool(runtime_initialized),
            load_delay_ms=0,
        )

    @staticmethod
    def _new_dns_manager():
        from .dns_core import DNSManager

        return DNSManager()

    @staticmethod
    def _new_force_dns_manager():
        from .dns_force import DNSForceManager

        return DNSForceManager()

    @classmethod
    def _get_dns_manager(cls):
        if cls._dns_manager_instance is None:
            cls._dns_manager_instance = cls._new_dns_manager()
        return cls._dns_manager_instance

    @staticmethod
    def detect_ipv6_availability() -> bool:
        try:
            from .dns_force import DNSForceManager

            return bool(DNSForceManager.check_ipv6_connectivity())
        except Exception as exc:
            log(f"Ошибка проверки IPv6 у провайдера: {exc}", "DEBUG")
            return False

    @classmethod
    def load_page_data(cls) -> NetworkPageData:
        ipv6_available = cls.detect_ipv6_availability()

        from .dns_core import refresh_exclusion_cache
        from .dns_force import ensure_default_force_dns

        dns_manager = cls._get_dns_manager()
        all_adapters = dns_manager.get_network_adapters_fast(
            include_ignored=True,
            include_disconnected=True,
        )
        filtered = [
            (name, desc)
            for name, desc in all_adapters
            if not dns_manager.should_ignore_adapter(name, desc)
        ]
        adapter_names = [name for name, _ in all_adapters]
        dns_info = dns_manager.get_all_dns_info_fast(adapter_names)

        ensure_default_force_dns()
        force_dns_active = cls._new_force_dns_manager().is_force_dns_enabled()

        return NetworkPageData(
            adapters=filtered,
            dns_info=dns_info,
            ipv6_available=ipv6_available,
            force_dns_active=force_dns_active,
        )

    @classmethod
    def refresh_dns_info(cls, adapter_names: list[str]) -> dict[str, dict[str, list[str]]]:
        return cls._get_dns_manager().get_all_dns_info_fast(adapter_names)

    @classmethod
    def apply_auto_dns(cls, adapters: list[str]) -> int:
        dns_manager = cls._get_dns_manager()
        success_count = 0
        for adapter in adapters:
            ok_v4, _ = dns_manager.set_auto_dns(adapter, "IPv4")
            ok_v6, _ = dns_manager.set_auto_dns(adapter, "IPv6")
            if ok_v4 and ok_v6:
                success_count += 1
        dns_manager.flush_dns_cache()
        return success_count

    @classmethod
    def apply_provider_dns(
        cls,
        adapters: list[str],
        ipv4: list[str],
        ipv6: list[str],
        *,
        ipv6_available: bool,
    ) -> int:
        dns_manager = cls._get_dns_manager()
        success_count = 0
        for adapter in adapters:
            ok_v4, _ = dns_manager.set_custom_dns(
                adapter,
                ipv4[0],
                ipv4[1] if len(ipv4) > 1 else None,
                "IPv4",
            )
            ok_v6 = True
            if ipv6_available and ipv6:
                ok_v6, _ = dns_manager.set_custom_dns(
                    adapter,
                    ipv6[0],
                    ipv6[1] if len(ipv6) > 1 else None,
                    "IPv6",
                )
            if ok_v4 and ok_v6:
                success_count += 1
        dns_manager.flush_dns_cache()
        return success_count

    @classmethod
    def apply_custom_dns(cls, adapters: list[str], primary: str, secondary: str | None) -> int:
        dns_manager = cls._get_dns_manager()
        success_count = 0
        for adapter in adapters:
            ok, _ = dns_manager.set_custom_dns(adapter, primary, secondary, "IPv4")
            if ok:
                success_count += 1
        dns_manager.flush_dns_cache()
        return success_count

    @staticmethod
    def get_force_dns_status() -> bool:
        return NetworkPageController._new_force_dns_manager().is_force_dns_enabled()

    @staticmethod
    def enable_force_dns(*, include_disconnected: bool = False) -> tuple[bool, int, int, str]:
        return NetworkPageController._new_force_dns_manager().enable_force_dns(include_disconnected=include_disconnected)

    @staticmethod
    def disable_force_dns(*, reset_to_auto: bool) -> tuple[bool, str]:
        return NetworkPageController._new_force_dns_manager().disable_force_dns(reset_to_auto=reset_to_auto)

    @classmethod
    def flush_dns_cache(cls) -> tuple[bool, str]:
        return cls._get_dns_manager().flush_dns_cache()

    def run_connectivity_test(self, test_hosts: list[tuple[str, str]]) -> list[tuple[str, str, bool]]:
        results: list[tuple[str, str, bool]] = []
        for name, host in test_hosts:
            try:
                result = subprocess.run(
                    ["ping", "-n", "1", "-w", "2000", host],
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                results.append((name, host, result.returncode == 0))
            except Exception:
                results.append((name, host, False))
        return results

    @staticmethod
    def build_force_dns_status_plan(
        *,
        enabled: bool,
        details_key: str | None = None,
        details_kwargs: dict | None = None,
        details_fallback: str = "",
        language: str = "ru",
    ) -> NetworkForceDnsStatusPlan:
        status = (
            tr_catalog("page.network.force_dns.status.enabled", language=language, default="Принудительный DNS включен")
            if enabled
            else tr_catalog("page.network.force_dns.status.disabled", language=language, default="Принудительный DNS отключен")
        )

        details_text = ""
        if details_key:
            details_default = details_fallback or ""
            template = tr_catalog(details_key, language=language, default=details_default)
            try:
                details_text = template.format(**(details_kwargs or {}))
            except Exception:
                details_text = template
        elif details_fallback:
            details_text = details_fallback

        if details_text:
            status = f"{status} ({details_text})"

        return NetworkForceDnsStatusPlan(text=status, enabled=bool(enabled))

    @staticmethod
    def build_force_dns_toggle_plan(
        *,
        requested_enabled: bool,
        success: bool,
        ok_count: int = 0,
        total: int = 0,
    ) -> NetworkForceDnsTogglePlan:
        if requested_enabled:
            if success:
                return NetworkForceDnsTogglePlan(
                    final_checked=True,
                    force_dns_active=True,
                    details_key="page.network.force_dns.status.details.adapters_applied",
                    details_kwargs={"ok_count": ok_count, "total": total},
                    details_fallback=f"{ok_count}/{total} адаптеров",
                )
            return NetworkForceDnsTogglePlan(
                final_checked=False,
                force_dns_active=False,
                details_key="page.network.force_dns.status.details.enable_failed",
                details_kwargs={},
                details_fallback="",
            )

        if success:
            return NetworkForceDnsTogglePlan(
                final_checked=False,
                force_dns_active=False,
                details_key="page.network.force_dns.status.details.dns_saved",
                details_kwargs={},
                details_fallback="",
            )

        return NetworkForceDnsTogglePlan(
            final_checked=True,
            force_dns_active=True,
            details_key="page.network.force_dns.status.details.disable_failed",
            details_kwargs={},
            details_fallback="",
        )

    @staticmethod
    def build_force_dns_toggle_error_plan(*, requested_enabled: bool) -> NetworkForceDnsTogglePlan:
        return NetworkForceDnsTogglePlan(
            final_checked=not requested_enabled,
            force_dns_active=not requested_enabled,
            details_key="page.network.force_dns.status.details.apply_error",
            details_kwargs={},
            details_fallback="",
        )

    @staticmethod
    def build_connectivity_test_plan(*, language: str = "ru") -> NetworkConnectivityTestPlan:
        return NetworkConnectivityTestPlan(
            test_hosts=[
                (tr_catalog("page.network.test.host.google_dns", language=language, default="Google DNS"), "8.8.8.8"),
                (tr_catalog("page.network.test.host.cloudflare_dns", language=language, default="Cloudflare DNS"), "1.1.1.1"),
                ("google.com", "google.com"),
                ("youtube.com", "youtube.com"),
            ]
        )

    @staticmethod
    def build_connectivity_test_result_plan(
        results: list[tuple[str, str, bool]],
        *,
        language: str = "ru",
    ) -> NetworkConnectivityTestResultPlan:
        report_lines: list[str] = []
        all_ok = True
        for name, host, success in results:
            status = "✓" if success else "✗"
            report_lines.append(f"{status} {name} ({host})")
            if not success:
                all_ok = False

        report = "\n".join(report_lines)
        title = tr_catalog("page.network.test.infobar.title", language=language, default="Тест соединения")
        if all_ok:
            content = tr_catalog(
                "page.network.test.infobar.all_ok",
                language=language,
                default="Все проверки пройдены:\n\n{report}",
            ).format(report=report)
            return NetworkConnectivityTestResultPlan(
                all_ok=True,
                report=report,
                infobar_level="success",
                title=title,
                content=content,
            )

        content = tr_catalog(
            "page.network.test.infobar.partial",
            language=language,
            default="Некоторые проверки не пройдены:\n\n{report}",
        ).format(report=report)
        return NetworkConnectivityTestResultPlan(
            all_ok=False,
            report=report,
            infobar_level="warning",
            title=title,
            content=content,
        )

    @staticmethod
    def build_provider_dns_plan(
        *,
        name: str,
        data: dict,
        ipv6_available: bool,
    ) -> NetworkProviderDnsPlan:
        ipv4 = DNSProviderCardProxy.normalize_dns_list(data.get("ipv4", []))
        if not ipv4:
            return NetworkProviderDnsPlan(
                valid=False,
                ipv4=[],
                ipv6=[],
                log_level="WARNING",
                log_message=f"DNS: у провайдера {name} нет IPv4 адресов",
            )

        ipv6 = DNSProviderCardProxy.normalize_dns_list(data.get("ipv6", [])) if ipv6_available else []
        return NetworkProviderDnsPlan(
            valid=True,
            ipv4=ipv4,
            ipv6=ipv6,
            log_level=None,
            log_message="",
        )

    @staticmethod
    def build_auto_dns_apply_result_plan(*, adapter_count: int, success_count: int) -> NetworkDnsApplyResultPlan:
        log_message = ""
        log_level = None
        if adapter_count > 0 and success_count == adapter_count:
            log_message = f"DNS: Автоматический (IPv4+IPv6) применён к {success_count} адаптерам"
            log_level = "INFO"
        return NetworkDnsApplyResultPlan(
            should_refresh=bool(adapter_count),
            log_level=log_level,
            log_message=log_message,
        )

    @staticmethod
    def build_provider_dns_apply_result_plan(
        *,
        name: str,
        adapter_count: int,
        success_count: int,
        ipv6_available: bool,
        ipv6: list[str],
    ) -> NetworkDnsApplyResultPlan:
        log_message = ""
        log_level = None
        if adapter_count > 0 and success_count == adapter_count:
            if ipv6_available and ipv6:
                log_message = f"DNS: {name} (IPv4+IPv6) применён к {success_count} адаптерам"
            else:
                log_message = f"DNS: {name} применён к {success_count} адаптерам"
            log_level = "INFO"
        return NetworkDnsApplyResultPlan(
            should_refresh=bool(adapter_count),
            log_level=log_level,
            log_message=log_message,
        )

    @staticmethod
    def build_custom_dns_apply_result_plan(*, primary: str, adapter_count: int, success_count: int) -> NetworkDnsApplyResultPlan:
        log_message = ""
        log_level = None
        if adapter_count > 0 and success_count == adapter_count:
            log_message = f"DNS: {primary} применён к {success_count} адаптерам"
            log_level = "INFO"
        return NetworkDnsApplyResultPlan(
            should_refresh=bool(adapter_count),
            log_level=log_level,
            log_message=log_message,
        )

    @staticmethod
    def build_reset_dhcp_result_plan(
        *,
        success: bool,
        message: str,
        force_dns_active: bool,
        language: str = "ru",
    ) -> NetworkResetDhcpResultPlan:
        title = tr_catalog("page.network.info.title", language=language, default="DNS")
        if success:
            return NetworkResetDhcpResultPlan(
                force_dns_active=bool(force_dns_active),
                should_select_auto=not force_dns_active,
                status_details_key="page.network.force_dns.status.details.dhcp_reset",
                infobar_level="success",
                infobar_title=title,
                infobar_content=tr_catalog(
                    "page.network.info.dhcp_reset_all",
                    language=language,
                    default="DNS сброшен на DHCP для всех адаптеров",
                ),
            )
        return NetworkResetDhcpResultPlan(
            force_dns_active=bool(force_dns_active),
            should_select_auto=not force_dns_active,
            status_details_key="page.network.force_dns.status.details.dhcp_not_applied",
            infobar_level="warning",
            infobar_title=title,
            infobar_content=message,
        )

    @staticmethod
    def build_flush_dns_cache_result_plan(
        *,
        success: bool,
        message: str,
        language: str = "ru",
    ) -> NetworkFlushDnsCacheResultPlan:
        if success:
            return NetworkFlushDnsCacheResultPlan(
                success=True,
                infobar_level=None,
                title="",
                content="",
            )
        return NetworkFlushDnsCacheResultPlan(
            success=False,
            infobar_level="warning",
            title=tr_catalog("page.network.error.title", language=language, default="Ошибка"),
            content=tr_catalog(
                "page.network.error.flush_cache_failed",
                language=language,
                default="Не удалось очистить кэш: {error}",
            ).format(error=message),
        )

    @staticmethod
    def build_isp_dns_warning_plan(
        adapters: list[tuple[str, str]],
        dns_info: dict[str, dict[str, list[str]]],
        *,
        force_dns_active: bool,
        language: str = "ru",
    ) -> NetworkIspDnsWarningPlan:
        should_show = NetworkPageController.should_show_isp_dns_warning(
            adapters,
            dns_info,
            force_dns_active=force_dns_active,
        )
        return NetworkIspDnsWarningPlan(
            should_show=should_show,
            title=tr_catalog(
                "page.network.isp_dns.infobar.title",
                language=language,
                default="DNS от провайдера",
            ),
            content=tr_catalog(
                "page.network.isp_dns.infobar.content",
                language=language,
                default=(
                    "У вас установлен DNS от провайдера (получен автоматически через DHCP). "
                    "Провайдерский DNS может подменять ответы и мешать обходу блокировок.\n\n"
                    "Рекомендуем установить публичный DNS (Google + OpenDNS) для стабильной работы."
                ),
            ),
            action_text=tr_catalog(
                "page.network.isp_dns.infobar.action",
                language=language,
                default="Установить рекомендуемый DNS",
            ),
            dismiss_text=tr_catalog(
                "page.network.isp_dns.infobar.dismiss",
                language=language,
                default="Нет, спасибо",
            ),
        )

    @staticmethod
    def build_accept_isp_dns_warning_plan() -> NetworkIspDnsActionPlan:
        return NetworkIspDnsActionPlan(
            hide_warning=True,
            enable_force_dns=True,
        )

    @staticmethod
    def build_dismiss_isp_dns_warning_plan() -> NetworkIspDnsActionPlan:
        return NetworkIspDnsActionPlan(
            hide_warning=True,
            enable_force_dns=False,
        )

    @staticmethod
    def _is_current_dns(provider_ips: list, current_ips: list) -> bool:
        return (
            len(provider_ips) > 0
            and len(current_ips) > 0
            and provider_ips[0] == current_ips[0]
        )

    @staticmethod
    def get_selected_adapter_dns(
        selected_adapters: list[str],
        dns_info: dict[str, dict[str, list[str]]],
    ) -> tuple[list[str], list[str]] | None:
        if not selected_adapters:
            return None

        from .dns_core import _normalize_alias

        clean = _normalize_alias(selected_adapters[0])
        adapter_data = dns_info.get(clean, {"ipv4": [], "ipv6": []})
        current_dns_v4 = DNSProviderCardProxy.normalize_dns_list(adapter_data.get("ipv4", []))
        current_dns_v6 = DNSProviderCardProxy.normalize_dns_list(adapter_data.get("ipv6", []))
        return current_dns_v4, current_dns_v6

    @classmethod
    def build_dns_selection_plan(
        cls,
        *,
        selected_adapters: list[str],
        dns_info: dict[str, dict[str, list[str]]],
        providers: dict,
    ) -> NetworkDnsSelectionPlan:
        selected_dns = cls.get_selected_adapter_dns(selected_adapters, dns_info)
        if selected_dns is None:
            return NetworkDnsSelectionPlan(
                kind="none",
                selected_provider=None,
                custom_primary="",
                custom_secondary="",
            )

        current_dns_v4, current_dns_v6 = selected_dns
        _ = current_dns_v6
        if not current_dns_v4 and not current_dns_v6:
            return NetworkDnsSelectionPlan(
                kind="auto",
                selected_provider=None,
                custom_primary="",
                custom_secondary="",
            )

        for providers_group in providers.values():
            for name, data in providers_group.items():
                if cls._is_current_dns(data.get("ipv4", []), current_dns_v4):
                    return NetworkDnsSelectionPlan(
                        kind="provider",
                        selected_provider=name,
                        custom_primary="",
                        custom_secondary="",
                    )

        return NetworkDnsSelectionPlan(
            kind="custom",
            selected_provider=None,
            custom_primary=current_dns_v4[0] if current_dns_v4 else "",
            custom_secondary=current_dns_v4[1] if len(current_dns_v4) > 1 else "",
        )

    @staticmethod
    def build_adapter_dns_refresh_plan(
        adapter_names: list[str],
        dns_info: dict[str, dict[str, list[str]]],
    ) -> NetworkAdapterDnsRefreshPlan:
        from .dns_core import _normalize_alias

        entries: list[NetworkAdapterDnsRefreshEntry] = []
        for adapter_name in adapter_names:
            clean_name = _normalize_alias(adapter_name)
            adapter_data = dns_info.get(clean_name, {})
            entries.append(
                NetworkAdapterDnsRefreshEntry(
                    adapter_name=adapter_name,
                    adapter_data=adapter_data,
                    ipv4=adapter_data.get("ipv4", []),
                    ipv6=adapter_data.get("ipv6", []),
                )
            )

        return NetworkAdapterDnsRefreshPlan(
            entries=entries,
            log_level="DEBUG",
            log_message="DNS информация адаптеров обновлена",
        )

    @staticmethod
    def should_show_isp_dns_warning(
        adapters: list[tuple[str, str]],
        dns_info: dict[str, dict[str, list[str]]],
        *,
        force_dns_active: bool,
    ) -> bool:
        from .dns_core import _normalize_alias

        if force_dns_active:
            return False

        try:
            from config.reg import reg

            if reg(REGISTRY_PATH, "ISPDNSInfoShown"):
                return False
        except Exception:
            pass

        has_adapters = False
        all_dhcp = True
        for name, _desc in adapters:
            has_adapters = True
            clean = _normalize_alias(name)
            adapter_data = dns_info.get(clean, {"ipv4": [], "ipv6": []})
            ipv4 = DNSProviderCardProxy.normalize_dns_list(adapter_data.get("ipv4", []))
            if ipv4:
                all_dhcp = False
                break
        return bool(has_adapters and all_dhcp)

    @staticmethod
    def mark_isp_dns_warning_shown() -> None:
        try:
            from config.reg import reg

            reg(REGISTRY_PATH, "ISPDNSInfoShown", 1)
        except Exception:
            pass


class DNSProviderCardProxy:
    @staticmethod
    def normalize_dns_list(value) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.replace(",", " ").split() if item.strip()]
        if isinstance(value, list):
            result: list[str] = []
            for item in value:
                item_s = str(item).strip()
                if item_s:
                    result.append(item_s)
            return result
        return []
