from __future__ import annotations

from typing import Set

from log.log import log



# Показываем подсказку не чаще 1 раза на "сценарий", чтобы не засорять логи.
_HINT_SHOWN: Set[str] = set()


def _is_proxy_related_error(exc: BaseException) -> bool:
    """Грубая эвристика: ошибка похожа на проблему прокси."""
    try:
        s = (str(exc) or "").lower()
    except Exception:
        return False

    # requests / urllib3
    if "proxy" in s:
        return True

    # русские сообщения
    if "прокси" in s:
        return True

    # частый кейс при корпоративных/локальных прокси
    if "tunnel connection" in s and "failed" in s:
        return True

    return False


def maybe_log_disable_dpi_for_update(exc: BaseException, *, scope: str, level: str) -> None:
    """
    Логирует подсказку выключить DPI/Запрет на время обновления.

    Args:
        exc: исходное исключение
        scope: ключ сценария (например: "update_check" или "download")
        level: куда логировать (например: "🔄 RELEASE" / "🔄 DOWNLOAD" / "📱 TG")
    """
    if scope in _HINT_SHOWN:
        return
    if not _is_proxy_related_error(exc):
        return

    _HINT_SHOWN.add(scope)
    log(
        "ℹ️ Подсказка: ошибка похожа на проблему прокси. Если у вас включен DPI/Запрет (winws/winws2) "+
        "или другой прокси/VPN, отключите его на время проверки/скачивания обновлений и повторите.",
        level,
    )
