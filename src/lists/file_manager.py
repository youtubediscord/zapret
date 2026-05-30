"""Утилиты для подготовки обязательных файлов приложения."""

import os

from lists.core.paths import get_lists_dir

LISTS_FOLDER = get_lists_dir()

REQUIRED_RUNTIME_LIST_FILES = ("other.txt", "ipset-all.txt", "ipset-ru.txt")


def _runtime_required_file_ready(path: str) -> bool:
    try:
        return os.path.isfile(path) and os.path.getsize(path) > 0
    except OSError:
        return False


def _log(message: str, level: str) -> None:
    from log.log import log

    log(message, level)


def ensure_required_files_fast():
    """Быстро проверяет готовность итоговых списков для обычного запуска."""
    try:
        os.makedirs(LISTS_FOLDER, exist_ok=True)
        missing_files = [
            name
            for name in REQUIRED_RUNTIME_LIST_FILES
            if not _runtime_required_file_ready(os.path.join(LISTS_FOLDER, name))
        ]
        if not missing_files:
            _log("Обязательные итоговые списки уже готовы", "DEBUG")
            return True

        _log(
            "Не найдены обязательные итоговые списки: "
            f"{', '.join(missing_files)}; выполняем полную подготовку",
            "WARNING",
        )
        return bool(ensure_required_files())
    except Exception as e:
        _log(f"Ошибка ensure_required_files_fast: {e}", "❌ ERROR")
        return False


def ensure_required_files():
    """Проверяет/подготавливает обязательные файлы списков."""
    try:
        os.makedirs(LISTS_FOLDER, exist_ok=True)

        from lists.hostlists_manager import ensure_hostlists_exist
        from lists.ipsets_manager import ensure_ipsets_exist
        from lists.core.layered_files import rebuild_all_layered_list_files

        hostlists_ok = ensure_hostlists_exist()
        ipsets_ok = ensure_ipsets_exist()
        rebuilt_count = rebuild_all_layered_list_files(LISTS_FOLDER)
        _log(f"Итоговые списки пересобраны: {rebuilt_count}", "DEBUG")

        result = bool(hostlists_ok and ipsets_ok)
        if result:
            _log("Обязательные файлы списков готовы", "DEBUG")
        else:
            _log(
                f"Не все обязательные файлы готовы: hostlists={hostlists_ok}, ipsets={ipsets_ok}",
                "WARNING",
            )
        return result
    except Exception as e:
        _log(f"Ошибка ensure_required_files: {e}", "❌ ERROR")
        return False
