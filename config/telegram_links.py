# config/telegram_links.py
"""Утилиты для открытия Telegram ссылок с fallback на https"""

import webbrowser
import winreg
from log import log


def is_telegram_installed() -> bool:
    """Проверяет наличие обработчика tg:// протокола в Windows"""
    try:
        # Проверяем реестр на наличие обработчика tg://
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "tg") as key:
            return True
    except FileNotFoundError:
        return False
    except Exception as e:
        log(f"Ошибка проверки tg:// протокола: {e}", "DEBUG")
        return False


def open_telegram_link(domain: str, post: int = None, slug: str = None) -> None:
    """
    Открывает Telegram ссылку через tg:// или https:// (fallback)

    Args:
        domain: Имя канала/бота (например 'zaprethelp')
        post: Номер поста (опционально)
        slug: Slug для addlist (опционально, вместо domain)
    """
    if slug:
        # Ссылка на папку с каналами
        tg_url = f"tg://addlist?slug={slug}"
        https_url = f"https://t.me/addlist/{slug}"
    elif post:
        tg_url = f"tg://resolve?domain={domain}&post={post}"
        https_url = f"https://t.me/{domain}/{post}"
    else:
        tg_url = f"tg://resolve?domain={domain}"
        https_url = f"https://t.me/{domain}"

    if is_telegram_installed():
        log(f"Открываю Telegram: {tg_url}", "DEBUG")
        webbrowser.open(tg_url)
    else:
        log(f"Telegram не установлен, открываю в браузере: {https_url}", "DEBUG")
        webbrowser.open(https_url)


def open_telegram_url(tg_url: str, https_url: str) -> None:
    """
    Открывает Telegram ссылку с готовыми URL

    Args:
        tg_url: URL в формате tg://
        https_url: Fallback URL в формате https://
    """
    if is_telegram_installed():
        webbrowser.open(tg_url)
    else:
        webbrowser.open(https_url)
