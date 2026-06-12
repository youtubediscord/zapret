from __future__ import annotations

from dataclasses import dataclass

from telegram_proxy.config.upstream_catalog import UpstreamCatalog, UpstreamPresetResolver
from telegram_proxy.proxy.cloudflare import AUTO_CLOUDFLARE_DOMAINS, CloudflareFallbackConfig, normalize_domain_list
from telegram_proxy.proxy.dc_map import parse_dc_endpoint_overrides
from telegram_proxy.proxy.fake_tls import normalize_fake_tls_domain
from telegram_proxy.proxy.mtproxy import build_mtproxy_link, generate_secret, normalize_secret


@dataclass(slots=True)
class TelegramProxySettingsState:
    host: str
    port: int
    mode: str
    upstream_enabled: bool
    upstream_host: str
    upstream_port: int
    upstream_preset_id: str
    upstream_user: str
    upstream_password: str
    upstream_mode: str
    upstream_preset_index: int
    cloudflare_enabled: bool
    cloudflare_domains: tuple[str, ...]
    cloudflare_worker_enabled: bool
    cloudflare_worker_domains: tuple[str, ...]
    mtproxy_secret: str
    dc_ip: tuple[str, ...]
    pool_size: int
    buffer_kb: int
    fake_tls_domain: str
    proxy_protocol: bool


@dataclass(slots=True)
class TelegramProxyPageInitialStatePlan:
    upstream_catalog: UpstreamCatalog
    settings: TelegramProxySettingsState


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 1353
DEFAULT_UPSTREAM_PORT = 1080

def default_state() -> TelegramProxySettingsState:
    return TelegramProxySettingsState(
        host=DEFAULT_HOST,
        port=DEFAULT_PORT,
        mode="socks5",
        upstream_enabled=True,
        upstream_host="",
        upstream_port=DEFAULT_UPSTREAM_PORT,
        upstream_preset_id="",
        upstream_user="",
        upstream_password="",
        upstream_mode="fallback",
        upstream_preset_index=0,
        cloudflare_enabled=False,
        cloudflare_domains=(),
        cloudflare_worker_enabled=False,
        cloudflare_worker_domains=(),
        mtproxy_secret="",
        dc_ip=(),
        pool_size=4,
        buffer_kb=256,
        fake_tls_domain="",
        proxy_protocol=False,
    )

def validate_host(host: str) -> bool:
    if not host:
        return False
    parts = host.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(part) <= 255 for part in parts)
    except ValueError:
        return False

def normalize_host(host: str) -> str:
    text = str(host or "").strip()
    if validate_host(text):
        return text
    return DEFAULT_HOST

def normalize_port(port: int | None) -> int:
    try:
        value = int(port or 0)
    except (TypeError, ValueError):
        return DEFAULT_PORT
    if 1024 <= value <= 65535:
        return value
    return DEFAULT_PORT

def normalize_upstream_port(port: int | None) -> int:
    try:
        value = int(port or 0)
    except (TypeError, ValueError):
        return DEFAULT_UPSTREAM_PORT
    if 1 <= value <= 65535:
        return value
    return DEFAULT_UPSTREAM_PORT

def normalize_proxy_mode(mode: object) -> str:
    text = str(mode or "").strip().lower()
    if text == "mtproxy":
        return "mtproxy"
    return "socks5"


def normalize_pool_size(value: object) -> int:
    try:
        number = int(value)
    except Exception:
        return 4
    return max(0, min(32, number))


def normalize_buffer_kb(value: object) -> int:
    try:
        number = int(value)
    except Exception:
        return 256
    return max(4, min(4096, number))


def build_manual_instruction_text(host: str, port: int, *, mode: object = "socks5") -> str:
    proxy_type = "MTProxy" if normalize_proxy_mode(mode) == "mtproxy" else "SOCKS5"
    return f"  Тип: {proxy_type}  |  Хост: {normalize_host(host)}  |  Порт: {normalize_port(port)}"

def build_proxy_url(
    host: str,
    port: int,
    *,
    mode: object = "socks5",
    mtproxy_secret: str = "",
    fake_tls_domain: str = "",
) -> str:
    normalized_host = normalize_host(host)
    normalized_port = normalize_port(port)
    if normalize_proxy_mode(mode) == "mtproxy":
        return build_mtproxy_link(
            normalized_host,
            normalized_port,
            mtproxy_secret,
            fake_tls_domain=normalize_fake_tls_domain(fake_tls_domain),
        )
    return f"tg://socks?server={normalized_host}&port={normalized_port}"


def _settings_state_from_data(data: dict, upstream_catalog: UpstreamCatalog) -> TelegramProxySettingsState:
    raw = dict((data or {}).get("telegram_proxy") or {})
    mode = normalize_proxy_mode(raw.get("mode"))
    upstream_host = str(raw.get("upstream_host") or "").strip()
    upstream_port = normalize_upstream_port(raw.get("upstream_port"))
    upstream_preset_id = str(raw.get("upstream_preset_id") or "").strip()
    upstream_user = str(raw.get("upstream_user") or "").strip()
    upstream_password = str(raw.get("upstream_pass") or "")
    upstream_mode = str(raw.get("upstream_mode") or "fallback").strip().lower() or "fallback"
    cloudflare_domains = normalize_domain_list(raw.get("cloudflare_domains"))
    cloudflare_worker_domains = normalize_domain_list(raw.get("cloudflare_worker_domains"))
    mtproxy_secret = normalize_secret(raw.get("mtproxy_secret"))
    dc_ip = tuple(f"{dc}:{ip}" for dc, ip in parse_dc_endpoint_overrides(raw.get("dc_ip")).items())
    pool_size = normalize_pool_size(raw.get("pool_size", 4))
    buffer_kb = normalize_buffer_kb(raw.get("buffer_kb", 256))
    fake_tls_domain = normalize_fake_tls_domain(raw.get("fake_tls_domain"))
    proxy_protocol = bool(raw.get("proxy_protocol", False))

    return TelegramProxySettingsState(
        host=normalize_host(raw.get("host")),
        port=normalize_port(raw.get("port")),
        mode=mode,
        upstream_enabled=bool(raw.get("upstream_enabled", True)),
        upstream_host=upstream_host,
        upstream_port=upstream_port,
        upstream_preset_id=upstream_preset_id,
        upstream_user=upstream_user,
        upstream_password=upstream_password,
        upstream_mode=upstream_mode,
        upstream_preset_index=upstream_catalog.find_choice_index(
            host=upstream_host,
            port=upstream_port,
            username=upstream_user,
            password=upstream_password,
            preset_id=upstream_preset_id,
        ),
        cloudflare_enabled=bool(raw.get("cloudflare_enabled", False)),
        cloudflare_domains=cloudflare_domains,
        cloudflare_worker_enabled=bool(raw.get("cloudflare_worker_enabled", False)),
        cloudflare_worker_domains=cloudflare_worker_domains,
        mtproxy_secret=mtproxy_secret,
        dc_ip=dc_ip,
        pool_size=pool_size,
        buffer_kb=buffer_kb,
        fake_tls_domain=fake_tls_domain,
        proxy_protocol=proxy_protocol,
    )


def load_page_initial_state() -> TelegramProxyPageInitialStatePlan:
    upstream_catalog = UpstreamCatalog.load_from_runtime()
    try:
        from settings.store import read_settings

        state = _settings_state_from_data(read_settings(), upstream_catalog)
    except Exception:
        state = default_state()
    return TelegramProxyPageInitialStatePlan(upstream_catalog=upstream_catalog, settings=state)


def set_port(port: int) -> int:
    normalized = normalize_port(port)
    try:
        from settings.store import set_tg_proxy_port

        set_tg_proxy_port(normalized)
    except Exception:
        pass
    return normalized

def set_host(host: str) -> str:
    normalized = normalize_host(host)
    try:
        from settings.store import set_tg_proxy_host

        set_tg_proxy_host(normalized)
    except Exception:
        pass
    return normalized

def set_proxy_enabled(enabled: bool) -> None:
    try:
        from settings.store import set_tg_proxy_enabled

        set_tg_proxy_enabled(bool(enabled))
    except Exception:
        pass

def set_proxy_mode(mode: object) -> str:
    normalized = normalize_proxy_mode(mode)
    try:
        from settings.store import set_tg_proxy_mode

        set_tg_proxy_mode(normalized)
    except Exception:
        pass
    return normalized

def generate_mtproxy_secret() -> str:
    return generate_secret()

def set_mtproxy_secret(secret: str) -> str:
    normalized = normalize_secret(secret)
    try:
        from settings.store import set_tg_proxy_mtproxy_secret

        set_tg_proxy_mtproxy_secret(normalized)
    except Exception:
        pass
    return normalized


def ensure_mtproxy_secret_for_mode(mode: object, secret: object) -> str:
    if normalize_proxy_mode(mode) != "mtproxy":
        return ""

    normalized = normalize_secret(secret)
    if normalized:
        return normalized

    generated = generate_mtproxy_secret()
    set_mtproxy_secret(generated)
    return generated


def set_dc_ip(value: object) -> tuple[str, ...]:
    overrides = parse_dc_endpoint_overrides(value)
    result = tuple(f"{dc}:{ip}" for dc, ip in overrides.items())
    try:
        from settings.store import set_tg_proxy_dc_ip

        set_tg_proxy_dc_ip(list(result))
    except Exception:
        pass
    return result


def set_pool_size(value: object) -> int:
    normalized = normalize_pool_size(value)
    try:
        from settings.store import set_tg_proxy_pool_size

        set_tg_proxy_pool_size(normalized)
    except Exception:
        pass
    return normalized


def set_buffer_kb(value: object) -> int:
    normalized = normalize_buffer_kb(value)
    try:
        from settings.store import set_tg_proxy_buffer_kb

        set_tg_proxy_buffer_kb(normalized)
    except Exception:
        pass
    return normalized


def set_fake_tls_domain(value: object) -> str:
    domain = normalize_fake_tls_domain(value)
    try:
        from settings.store import set_tg_proxy_fake_tls_domain

        set_tg_proxy_fake_tls_domain(domain)
    except Exception:
        pass
    return domain


def set_proxy_protocol(enabled: bool) -> None:
    try:
        from settings.store import set_tg_proxy_proxy_protocol

        set_tg_proxy_proxy_protocol(bool(enabled))
    except Exception:
        pass


def set_upstream_enabled(enabled: bool) -> None:
    try:
        from settings.store import set_tg_proxy_upstream_enabled

        set_tg_proxy_upstream_enabled(bool(enabled))
    except Exception:
        pass

def set_upstream_mode(always_enabled: bool) -> None:
    try:
        from settings.store import set_tg_proxy_upstream_mode

        set_tg_proxy_upstream_mode("always" if always_enabled else "fallback")
    except Exception:
        pass

def set_upstream_preset(preset_id: str) -> None:
    try:
        from settings.store import (
            set_tg_proxy_upstream_host,
            set_tg_proxy_upstream_pass,
            set_tg_proxy_upstream_preset_id,
            set_tg_proxy_upstream_port,
            set_tg_proxy_upstream_user,
        )

        normalized_preset_id = str(preset_id or "").strip()
        set_tg_proxy_upstream_preset_id(normalized_preset_id)
        set_tg_proxy_upstream_host("")
        set_tg_proxy_upstream_port(DEFAULT_UPSTREAM_PORT)
        set_tg_proxy_upstream_user("")
        set_tg_proxy_upstream_pass("")
    except Exception:
        pass


def set_manual_upstream(host: str, port: int, user: str, password: str) -> None:
    try:
        from settings.store import (
            set_tg_proxy_upstream_host,
            set_tg_proxy_upstream_pass,
            set_tg_proxy_upstream_preset_id,
            set_tg_proxy_upstream_port,
            set_tg_proxy_upstream_user,
        )

        set_tg_proxy_upstream_preset_id("")
        set_tg_proxy_upstream_host(str(host or "").strip())
        set_tg_proxy_upstream_port(normalize_upstream_port(port))
        set_tg_proxy_upstream_user(str(user or "").strip())
        set_tg_proxy_upstream_pass(str(password or ""))
    except Exception:
        pass


def set_cloudflare_enabled(enabled: bool) -> None:
    try:
        from settings.store import set_tg_proxy_cloudflare_enabled

        set_tg_proxy_cloudflare_enabled(bool(enabled))
    except Exception:
        pass


def set_cloudflare_domains(value: object) -> tuple[str, ...]:
    domains = normalize_domain_list(value)
    try:
        from settings.store import set_tg_proxy_cloudflare_domains

        set_tg_proxy_cloudflare_domains(list(domains))
    except Exception:
        pass
    return domains


def set_cloudflare_worker_enabled(enabled: bool) -> None:
    try:
        from settings.store import set_tg_proxy_cloudflare_worker_enabled

        set_tg_proxy_cloudflare_worker_enabled(bool(enabled))
    except Exception:
        pass


def set_cloudflare_worker_domains(value: object) -> tuple[str, ...]:
    domains = normalize_domain_list(value)
    try:
        from settings.store import set_tg_proxy_cloudflare_worker_domains

        set_tg_proxy_cloudflare_worker_domains(list(domains))
    except Exception:
        pass
    return domains


def build_cloudflare_config() -> CloudflareFallbackConfig:
    try:
        from settings.store import (
            get_tg_proxy_cloudflare_domains,
            get_tg_proxy_cloudflare_enabled,
            get_tg_proxy_cloudflare_worker_domains,
            get_tg_proxy_cloudflare_worker_enabled,
        )

        domains = normalize_domain_list(get_tg_proxy_cloudflare_domains())
        cloudflare_enabled = bool(get_tg_proxy_cloudflare_enabled())
        if cloudflare_enabled and not domains:
            domains = AUTO_CLOUDFLARE_DOMAINS
        worker_domains = normalize_domain_list(get_tg_proxy_cloudflare_worker_domains())
        return CloudflareFallbackConfig(
            enabled=cloudflare_enabled and bool(domains),
            domains=domains,
            worker_enabled=bool(get_tg_proxy_cloudflare_worker_enabled()) and bool(worker_domains),
            worker_domains=worker_domains,
        )
    except Exception:
        return CloudflareFallbackConfig()


def build_dc_endpoint_overrides() -> dict[int, str]:
    try:
        from settings.store import get_tg_proxy_dc_ip

        return parse_dc_endpoint_overrides(get_tg_proxy_dc_ip())
    except Exception:
        return {}


def load_upstream_test_target() -> tuple | None:
    try:
        from settings.store import (
            get_tg_proxy_upstream_enabled,
            get_tg_proxy_upstream_host,
            get_tg_proxy_upstream_pass,
            get_tg_proxy_upstream_preset_id,
            get_tg_proxy_upstream_port,
            get_tg_proxy_upstream_user,
        )

        if not get_tg_proxy_upstream_enabled():
            return None

        preset_id = str(get_tg_proxy_upstream_preset_id() or "").strip()
        resolver = UpstreamPresetResolver.load_from_runtime()
        target = resolver.test_target_by_id(preset_id) if preset_id else None
        if target is not None:
            return target

        host = str(get_tg_proxy_upstream_host() or "").strip()
        port = normalize_upstream_port(get_tg_proxy_upstream_port())
        if not host:
            preset = resolver.first_socks5()
            if preset is None:
                return None
            return (
                str(preset["host"]),
                normalize_upstream_port(preset["port"]),
                str(preset["username"]),
                str(preset["password"]),
                bool(preset.get("tls", False)),
                str(preset.get("tls_server_name") or ""),
                bool(preset.get("tls_verify", False)),
            )
        if port <= 0:
            return None
        return (
            host,
            port,
            str(get_tg_proxy_upstream_user() or "").strip(),
            str(get_tg_proxy_upstream_pass() or ""),
            False,
            "",
            False,
        )
    except Exception:
        return None

def build_upstream_config():
    try:
        from telegram_proxy.proxy.routing import UpstreamProxyConfig, UpstreamProxyEndpoint
        from settings.store import (
            get_tg_proxy_upstream_enabled,
            get_tg_proxy_upstream_host,
            get_tg_proxy_upstream_mode,
            get_tg_proxy_upstream_pass,
            get_tg_proxy_upstream_preset_id,
            get_tg_proxy_upstream_port,
            get_tg_proxy_upstream_user,
        )

        if not get_tg_proxy_upstream_enabled():
            return None

        preset_id = str(get_tg_proxy_upstream_preset_id() or "").strip()
        resolver = UpstreamPresetResolver.load_from_runtime()
        preset = resolver.socks5_by_id(preset_id) if preset_id else None
        selected_preset_id = preset_id
        fallback_presets: list[dict] = []
        if preset is not None:
            host = str(preset["host"])
            port = normalize_upstream_port(preset["port"])
            username = str(preset["username"])
            password = str(preset["password"])
            tls = bool(preset.get("tls", False))
            tls_server_name = str(preset.get("tls_server_name") or "")
            tls_verify = bool(preset.get("tls_verify", False))
            fallback_presets = resolver.socks5_fallbacks(selected_preset_id)
        else:
            host = str(get_tg_proxy_upstream_host() or "").strip()
            port = normalize_upstream_port(get_tg_proxy_upstream_port())
            username = str(get_tg_proxy_upstream_user() or "").strip()
            password = str(get_tg_proxy_upstream_pass() or "")
            tls = False
            tls_server_name = ""
            tls_verify = False
            if not host:
                preset = resolver.first_socks5()
                if preset is None:
                    return None
                selected_preset_id = str(preset.get("id") or "").strip()
                host = str(preset["host"])
                port = normalize_upstream_port(preset["port"])
                username = str(preset["username"])
                password = str(preset["password"])
                tls = bool(preset.get("tls", False))
                tls_server_name = str(preset.get("tls_server_name") or "")
                tls_verify = bool(preset.get("tls_verify", False))
                fallback_presets = resolver.socks5_fallbacks(selected_preset_id)

        if not host or port <= 0:
            return None

        fallback_proxies = tuple(
            UpstreamProxyEndpoint(
                host=str(item["host"]),
                port=normalize_upstream_port(item["port"]),
                username=str(item["username"]),
                password=str(item["password"]),
                tls=bool(item.get("tls", False)),
                tls_server_name=str(item.get("tls_server_name") or ""),
                tls_verify=bool(item.get("tls_verify", False)),
            )
            for item in fallback_presets
            if str(item.get("host") or "").strip()
            and normalize_upstream_port(item.get("port")) > 0
        )

        return UpstreamProxyConfig(
            enabled=True,
            host=host,
            port=port,
            mode=str(get_tg_proxy_upstream_mode() or "fallback"),
            username=username,
            password=password,
            tls=tls,
            tls_server_name=tls_server_name,
            tls_verify=tls_verify,
            fallback_proxies=fallback_proxies,
        )
    except Exception:
        return None


def get_upstream_mtproxy_link(preset_id: str) -> str:
    try:
        return UpstreamPresetResolver.load_from_runtime().mtproxy_link_by_id(preset_id)
    except Exception:
        return ""

def consume_auto_deeplink_request() -> bool:
    try:
        from settings.store import get_tg_proxy_deeplink_done, set_tg_proxy_deeplink_done

        if get_tg_proxy_deeplink_done():
            return False
        set_tg_proxy_deeplink_done(True)
        return True
    except Exception:
        return False
