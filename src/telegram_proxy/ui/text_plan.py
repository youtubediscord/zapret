"""Короткие тексты страницы Telegram Proxy."""

from __future__ import annotations

from dataclasses import astuple, dataclass


@dataclass(frozen=True, slots=True)
class TelegramProxySettingsText:
    page_subtitle: str
    setup_title: str
    setup_description: str
    setup_fallback: str
    settings_title: str
    proxy_mode_title: str
    proxy_mode_description: str
    auto_setup_title: str
    auto_setup_description: str
    upstream_title: str
    upstream_toggle_title: str
    upstream_toggle_description: str
    upstream_preset_title: str
    upstream_preset_description: str
    upstream_catalog_missing: str
    upstream_mode_title: str
    upstream_mode_description: str
    cloudflare_toggle_title: str
    cloudflare_toggle_description: str
    cloudflare_worker_toggle_title: str
    cloudflare_worker_toggle_description: str
    manual_hidden_title: str
    manual_path: str
    diag_description: str

    def __iter__(self):
        return iter(astuple(self))


TELEGRAM_PROXY_SETTINGS_TEXT = TelegramProxySettingsText(
    page_subtitle="Локальный прокси для Telegram. Используйте его, если Telegram подключается нестабильно.",
    setup_title="Подключить Telegram",
    setup_description="Откройте ссылку. Telegram сам предложит добавить прокси.",
    setup_fallback="Если Telegram не открылся, скопируйте ссылку и отправьте её себе в чат.",
    settings_title="Основные настройки",
    proxy_mode_title="Режим прокси",
    proxy_mode_description="SOCKS5 — основной режим. MTProxy нужен для secret, Fake TLS и Cloudflare-сценариев.",
    auto_setup_title="Авто-настройка Telegram",
    auto_setup_description="Открывать ссылку при первом запуске прокси",
    upstream_title="Дополнительно",
    upstream_toggle_title="Внешний прокси",
    upstream_toggle_description="Резервный SOCKS5, если часть серверов Telegram не отвечает.",
    upstream_preset_title="Сервер",
    upstream_preset_description="Выберите сервер из списка или переключитесь на ручной ввод",
    upstream_catalog_missing="В этой сборке список предустановленных прокси не загружен. Доступен только ручной ввод.",
    upstream_mode_title="Весь трафик через прокси",
    upstream_mode_description="Если выключено — только проблемные серверы Telegram. Если включено — весь трафик Telegram.",
    cloudflare_toggle_title="Cloudflare fallback",
    cloudflare_toggle_description="Пробовать запасные Cloudflare-домены. Если поле доменов пустое, используется авто-список.",
    cloudflare_worker_toggle_title="Cloudflare Worker fallback",
    cloudflare_worker_toggle_description="Пробовать Worker-домены как отдельный запасной путь.",
    manual_hidden_title="Ручная настройка",
    manual_path="Telegram → Настройки → Продвинутые → Тип соединения → Прокси",
    diag_description=(
        "Проверяет соединение с серверами Telegram, локальный SOCKS5 прокси "
        "и возможные проблемы с маршрутом."
    ),
)
