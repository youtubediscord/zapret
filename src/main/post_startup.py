from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def install_startup_checks(*args, **kwargs):
    from main.post_startup_checks import install_startup_checks as install

    return install(*args, **kwargs)


def install_backend_page_data_warmup(*args, **kwargs):
    from main.post_startup_backend_warmup import install_backend_page_data_warmup as install

    return install(*args, **kwargs)


def install_cpu_diagnostic(*args, **kwargs):
    from main.post_startup_diagnostics import install_cpu_diagnostic as install

    return install(*args, **kwargs)


def install_global_exception_handler(*args, **kwargs):
    from main.post_startup_diagnostics import install_global_exception_handler as install

    return install(*args, **kwargs)


def install_qt_event_diagnostic_probe(*args, **kwargs):
    from main.post_startup_diagnostics import install_qt_event_diagnostic_probe as install

    return install(*args, **kwargs)


def install_startup_audit(*args, **kwargs):
    from main.startup_audit import install_startup_audit as install

    return install(*args, **kwargs)


def install_dns_startup(*args, **kwargs):
    from main.post_startup_dns import install_dns_startup as install

    return install(*args, **kwargs)


def install_dns_page_data_warmup(*args, **kwargs):
    from main.post_startup_dns_warmup import install_dns_page_data_warmup as install

    return install(*args, **kwargs)


def install_lists_check(*args, **kwargs):
    from main.post_startup_lists import install_lists_check as install

    return install(*args, **kwargs)


def install_deferred_maintenance(*args, **kwargs):
    from main.post_startup_maintenance import install_deferred_maintenance as install

    return install(*args, **kwargs)


def install_profile_warmup(*args, **kwargs):
    from main.post_startup_profile_warmup import install_profile_warmup as install

    return install(*args, **kwargs)


def install_user_presets_warmup(*args, **kwargs):
    from main.post_startup_user_presets_warmup import install_user_presets_warmup as install

    return install(*args, **kwargs)


def install_telegram_proxy_startup(*args, **kwargs):
    from main.post_startup_proxy import install_telegram_proxy_startup as install

    return install(*args, **kwargs)


def install_update_check(*args, **kwargs):
    from main.post_startup_update import install_update_check as install

    return install(*args, **kwargs)

@dataclass(frozen=True, slots=True)
class PostStartupDeps:
    startup_host: Any
    profile_feature: Any
    dns_feature: Any
    notify: Any
    notify_many: Any
    set_status: Any
    log_startup_metric: Any
    start_proxy_if_enabled_async: Any
    startup_lists_check: Any
    apply_dns_on_startup_async: Any
    install_tray_post_startup: Any
    updater_feature: Any
    premium_feature: Any = None
    logs_feature: Any = None
    presets_feature: Any = None


def install_post_startup_tasks(deps: PostStartupDeps) -> None:
    startup_host = deps.startup_host

    install_startup_checks(
        startup_host,
        notify_many=deps.notify_many,
        set_status=deps.set_status,
        log_startup_metric=deps.log_startup_metric,
    )
    install_deferred_maintenance(
        startup_host,
        notify_many=deps.notify_many,
        log_startup_metric=deps.log_startup_metric,
    )
    install_telegram_proxy_startup(
        startup_host,
        start_proxy_if_enabled_async=deps.start_proxy_if_enabled_async,
        log_startup_metric=deps.log_startup_metric,
    )
    install_lists_check(
        startup_host,
        startup_lists_check=deps.startup_lists_check,
        log_startup_metric=deps.log_startup_metric,
    )
    install_dns_startup(
        startup_host,
        apply_dns_on_startup_async=deps.apply_dns_on_startup_async,
        set_status=deps.set_status,
        log_startup_metric=deps.log_startup_metric,
    )
    install_dns_page_data_warmup(
        startup_host,
        dns_feature=deps.dns_feature,
        log_startup_metric=deps.log_startup_metric,
    )
    if deps.premium_feature is not None and deps.logs_feature is not None:
        install_backend_page_data_warmup(
            startup_host,
            premium_feature=deps.premium_feature,
            logs_feature=deps.logs_feature,
            log_startup_metric=deps.log_startup_metric,
        )
    install_profile_warmup(
        startup_host,
        profile_feature=deps.profile_feature,
        log_startup_metric=deps.log_startup_metric,
    )
    if deps.presets_feature is not None:
        install_user_presets_warmup(
            startup_host,
            presets_feature=deps.presets_feature,
            log_startup_metric=deps.log_startup_metric,
        )
    deps.install_tray_post_startup()
    install_update_check(
        startup_host,
        updater_feature=deps.updater_feature,
        notify=deps.notify,
        set_status=deps.set_status,
    )
    install_cpu_diagnostic()
    install_qt_event_diagnostic_probe()
    install_startup_audit()
    install_global_exception_handler()


__all__ = ["PostStartupDeps", "install_post_startup_tasks"]
