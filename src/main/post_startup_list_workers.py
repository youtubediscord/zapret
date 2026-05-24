from __future__ import annotations

from log.log import log


def run_startup_lists_check(*, startup_lists_check) -> None:
    """Проверяет итоговые файлы списков после основного запуска, не блокируя окно."""
    try:
        log("🔧 Начинаем проверку итоговых списков (post-startup)", "DEBUG")

        hostlists_ok, ipsets_ok = startup_lists_check()
        if hostlists_ok:
            log("✅ Hostlist-файлы проверены и готовы", "SUCCESS")
        else:
            log("⚠️ Проблемы с hostlist-файлами", "WARNING")
    except Exception as exc:
        log(f"❌ Ошибка проверки итоговых списков: {exc}", "ERROR")
        ipsets_ok = False

    try:
        if ipsets_ok:
            log("✅ IPset-файлы проверены и готовы", "SUCCESS")
        else:
            log("⚠️ Проблемы с IPset-файлами", "WARNING")
    except Exception as exc:
        log(f"❌ Ошибка проверки IPsets: {exc}", "ERROR")
