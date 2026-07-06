"""
Единый контракт игнорируемых целей оркестратора.

Сейчас сюда входят только relay/служебные хосты отдельного Telegram Proxy
модуля. Это намеренно узкое правило: обычный Telegram Web не выключаем.

Список доменов инициализируется лениво: импорт telegram_proxy.telegram_hosts
исполняет __init__ всего пакета telegram_proxy (wss_proxy, mtproxy, asyncio)
и стоит ~240 мс на старте GUI. Оркестратору эти домены нужны только в
рантайме, поэтому импорт откладывается до первого обращения.
"""

from __future__ import annotations

_FALLBACK_TELEGRAM_PROXY_DOMAINS = [
    "zws4.web.telegram.org",
    "vesta.web.telegram.org",
    "my.telegram.org",
    "core.telegram.org",
    "vesta-1.web.telegram.org",
    "venus-1.web.telegram.org",
    "telegram.me",
    "telegram.dog",
    "telegram.space",
    "telesco.pe",
    "tg.dev",
    "telegram.org",
    "t.me",
    "api.telegram.org",
    "td.telegram.org",
    "venus.web.telegram.org",
    "web.telegram.org",
    "kws2-1.web.telegram.org",
    "kws2.web.telegram.org",
    "kws4-1.web.telegram.org",
    "kws4.web.telegram.org",
    "zws2-1.web.telegram.org",
    "zws2.web.telegram.org",
    "zws4-1.web.telegram.org",
]

_IGNORED_EXACT_DOMAINS: tuple[str, ...] | None = None
_IGNORED_DOMAIN_SET: set[str] | None = None


def _load_telegram_proxy_domains() -> list[str]:
    try:
        from telegram_proxy.telegram_hosts import TELEGRAM_DOMAINS

        return list(TELEGRAM_DOMAINS)
    except Exception:
        return _FALLBACK_TELEGRAM_PROXY_DOMAINS


def _ensure_ignored_domains() -> tuple[str, ...]:
    global _IGNORED_EXACT_DOMAINS, _IGNORED_DOMAIN_SET
    if _IGNORED_EXACT_DOMAINS is None:
        _IGNORED_EXACT_DOMAINS = tuple(
            sorted(
                {
                    normalized
                    for domain in _load_telegram_proxy_domains()
                    for normalized in [str(domain).strip().lower().rstrip(".")]
                    if normalized and ".web.telegram.org" in normalized
                }
            )
        )
        _IGNORED_DOMAIN_SET = set(_IGNORED_EXACT_DOMAINS)
    return _IGNORED_EXACT_DOMAINS


def get_orchestra_ignored_exact_domains() -> tuple[str, ...]:
    """Возвращает канонический список точных доменов, игнорируемых оркестратором."""
    return _ensure_ignored_domains()


def is_orchestra_ignored_target(hostname: str) -> bool:
    """
    Проверяет, должен ли оркестратор полностью игнорировать этот хост.

    Важно:
    - правило точечное и работает только по relay/служебным доменам proxy-модуля;
    - мы сознательно НЕ игнорируем абстрактные ярлыки вроде "TELEGRAM",
      чтобы не отключить другие Telegram-профили оркестратора по ошибке.
    """
    normalized = str(hostname or "").strip().lower().rstrip(".")
    if not normalized:
        return False
    _ensure_ignored_domains()
    assert _IGNORED_DOMAIN_SET is not None
    return normalized in _IGNORED_DOMAIN_SET
