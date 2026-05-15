from __future__ import annotations

from log.log import log


def run_startup_lists_check(*, startup_lists_check) -> None:
    """Проверяет hostlists/ipsets после основного запуска, не блокируя окно."""
    try:
        log("🔧 Начинаем проверку хостлистов (post-startup)", "DEBUG")

        hostlists_ok, ipsets_ok = startup_lists_check()
        if hostlists_ok:
            log("✅ Хостлисты проверены и готовы", "SUCCESS")
        else:
            log("⚠️ Проблемы с хостлистами, создаем минимальные", "WARNING")
    except Exception as exc:
        log(f"❌ Ошибка проверки хостлистов: {exc}", "ERROR")
        ipsets_ok = False

    try:
        log("🔧 Начинаем проверку IPsets (post-startup)", "DEBUG")
        if ipsets_ok:
            log("✅ IPsets проверены и готовы", "SUCCESS")
        else:
            log("⚠️ Проблемы с IPsets, создаем минимальные", "WARNING")
    except Exception as exc:
        log(f"❌ Ошибка проверки IPsets: {exc}", "ERROR")
