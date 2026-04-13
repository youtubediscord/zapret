"""Утилиты для подготовки обязательных файлов приложения."""

import os

from config.config import LISTS_FOLDER

from log.log import log



def ensure_required_files():
    """Проверяет/подготавливает обязательные файлы списков."""
    try:
        os.makedirs(LISTS_FOLDER, exist_ok=True)

        from utils.hostlists_manager import ensure_hostlists_exist
        from utils.ipsets_manager import ensure_ipsets_exist
        from utils.netrogat_manager import ensure_netrogat_exists

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
