"""
updater/startup_update_check.py
────────────────────────────────────────────────────────────────
Синхронная проверка обновлений при запуске приложения.
Не содержит Qt-импортов — безопасно вызывать из фонового потока.
"""
from __future__ import annotations

from log.log import log



def check_for_update_sync() -> dict:
    """
    Проверяет наличие обновлений синхронно.

    Возвращает dict:
        has_update   : bool      — найдено ли новое обновление
        version      : str|None  — версия обновления (если has_update) или текущая
        release_notes: str       — заметки к релизу
        error        : str|None  — текст ошибки (если проверка не удалась)
        release_info : dict|None — полный release_info (для передачи в UpdateWorker)
    """
    try:
        from config.build_info import CHANNEL, APP_VERSION

        from updater.release_manager import get_latest_release
        from updater.github_release import normalize_version
        from updater.update import compare_versions

        log("Проверка обновлений при запуске...", "🔁 UPDATE")

        release_info = get_latest_release(CHANNEL, use_cache=False)
        if not release_info:
            return {
                'has_update': False,
                'version': None,
                'release_notes': '',
                'error': 'Не удалось получить информацию о релизах',
                'release_info': None,
            }

        new_ver = release_info.get('version', '')
        release_notes = release_info.get('release_notes', '')

        try:
            app_ver_norm = normalize_version(APP_VERSION)
        except Exception:
            app_ver_norm = APP_VERSION

        cmp = compare_versions(app_ver_norm, new_ver)

        if cmp < 0:
            log(f"Найдено обновление v{new_ver} (текущая v{app_ver_norm})", "🔁 UPDATE")
            return {
                'has_update': True,
                'version': new_ver,
                'release_notes': release_notes,
                'error': None,
                'release_info': release_info,
            }
        else:
            log(f"Обновлений нет (v{app_ver_norm})", "🔁 UPDATE")
            return {
                'has_update': False,
                'version': app_ver_norm,
                'release_notes': '',
                'error': None,
                'release_info': None,
            }

    except Exception as e:
        log(f"Ошибка проверки обновлений при запуске: {e}", "❌ ERROR")
        return {
            'has_update': False,
            'version': None,
            'release_notes': '',
            'error': str(e),
            'release_info': None,
        }
