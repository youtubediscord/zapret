"""Утилиты для подготовки обязательных файлов приложения."""

import os

from log.log import log
from lists.core.paths import get_lists_dir

LISTS_FOLDER = get_lists_dir()



def ensure_required_files():
    """Проверяет/подготавливает обязательные файлы списков."""
    try:
        os.makedirs(LISTS_FOLDER, exist_ok=True)

        from lists.hostlists_manager import ensure_hostlists_exist
        from lists.ipsets_manager import ensure_ipsets_exist
        from lists.netrogat_manager import ensure_netrogat_exists

        hostlists_ok = ensure_hostlists_exist()
        ipsets_ok = ensure_ipsets_exist()
        netrogat_ok = ensure_netrogat_exists()

        result = bool(hostlists_ok and ipsets_ok and netrogat_ok)
        if result:
            log("Обязательные файлы списков готовы", "DEBUG")
        else:
            log(
                f"Не все обязательные файлы готовы: hostlists={hostlists_ok}, ipsets={ipsets_ok}, netrogat={netrogat_ok}",
                "WARNING",
            )
        return result
    except Exception as e:
        log(f"Ошибка ensure_required_files: {e}", "❌ ERROR")
        return False
