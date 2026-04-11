"""Centralized UI text catalog and sidebar search index.

This module contains user-facing strings for navigation/search and the
declarative index used by the left sidebar global search.
"""

from dataclasses import dataclass
from typing import Iterable

from ui.page_names import PageName


DEFAULT_UI_LANGUAGE = "ru"
SUPPORTED_UI_LANGUAGES = ("ru", "en")
LANGUAGE_OPTIONS = (
    ("ru", "Русский"),
    ("en", "English"),
)


TEXTS: dict[str, dict[str, str]] = {
    "sidebar.search.placeholder": {
        "ru": "Найти в разделах и страницах",
        "en": "Find in sections and pages",
    },
    "nav.header.settings": {
        "ru": "Настройки Запрета",
        "en": "Zapret Settings",
    },
    "nav.header.system": {
        "ru": "Система",
        "en": "System",
    },
    "nav.header.diagnostics": {
        "ru": "Диагностика",
        "en": "Diagnostics",
    },
    "nav.header.appearance": {
        "ru": "Оформление",
        "en": "Appearance",
    },
    "nav.page.control": {
        "ru": "Управление",
        "en": "Control",
    },
    "nav.page.zapret2_direct_control": {
        "ru": "Управление Zapret 2",
        "en": "Zapret 2 Control",
    },
    "nav.page.zapret1_direct_control": {
        "ru": "Управление Zapret 1",
        "en": "Zapret 1 Control",
    },
    "nav.page.orchestra": {
        "ru": "Оркестратор",
        "en": "Orchestrator",
    },
    "nav.page.hostlist": {
        "ru": "Листы",
        "en": "Lists",
    },
    "nav.page.orchestra_settings": {
        "ru": "Настройки оркестратора",
        "en": "Orchestrator Settings",
    },
    "nav.page.dpi_settings": {
        "ru": "Сменить режим DPI",
        "en": "DPI Mode",
    },
    "nav.page.autostart": {
        "ru": "Автозапуск",
        "en": "Autostart",
    },
    "nav.page.network": {
        "ru": "Сеть",
        "en": "Network",
    },
    "nav.page.hosts": {
        "ru": "Редактор файла hosts",
        "en": "Hosts File Editor",
    },
    "nav.page.blockcheck": {
        "ru": "BlockCheck",
        "en": "BlockCheck",
    },
    "nav.page.appearance": {
        "ru": "Оформление",
        "en": "Appearance",
    },
    "nav.page.premium": {
        "ru": "Донат",
        "en": "Donation",
    },
    "nav.page.logs": {
        "ru": "Логи",
        "en": "Logs",
    },
    "nav.page.about": {
        "ru": "О программе",
        "en": "About",
    },
    "nav.page.zapret2_direct": {
        "ru": "Прямой запуск",
        "en": "Direct Launch",
    },
    "nav.page.zapret2_user_presets": {
        "ru": "Мои пресеты",
        "en": "My Presets",
    },
    "nav.page.zapret1_direct": {
        "ru": "Стратегии Z1",
        "en": "Z1 Strategies",
    },
    "nav.page.zapret1_user_presets": {
        "ru": "Мои пресеты Z1",
        "en": "Z1 Presets",
    },
    "common.toggle.on_off": {
        "ru": "Вкл/Выкл",
        "en": "On/Off",
    },
    "common.ok.got_it": {
        "ru": "Понятно",
        "en": "Got it",
    },
    "common.error.title": {
        "ru": "Ошибка",
        "en": "Error",
    },
    "page.control.title": {
        "ru": "Управление",
        "en": "Control",
    },
    "page.control.status": {
        "ru": "Статус работы",
        "en": "Service Status",
    },
    "page.control.program_settings": {
        "ru": "Настройки программы",
        "en": "Program Settings",
    },
    "page.control.status.checking": {
        "ru": "Проверка...",
        "en": "Checking...",
    },
    "page.control.status.detecting": {
        "ru": "Определение состояния процесса",
        "en": "Detecting process state",
    },
    "page.control.status.running": {
        "ru": "Zapret работает",
        "en": "Zapret is running",
    },
    "page.control.status.stopped": {
        "ru": "Zapret остановлен",
        "en": "Zapret stopped",
    },
    "page.control.status.bypass_active": {
        "ru": "Обход блокировок активен",
        "en": "Bypass is active",
    },
    "page.control.status.press_start": {
        "ru": "Нажмите «Запустить» для активации",
        "en": "Press Start to activate",
    },
    "page.control.button.start": {
        "ru": "Запустить Zapret",
        "en": "Start Zapret",
    },
    "page.control.button.stop_only_winws": {
        "ru": "Остановить только winws.exe",
        "en": "Stop only winws.exe",
    },
    "page.control.button.stop_and_exit": {
        "ru": "Остановить и закрыть программу",
        "en": "Stop and close application",
    },
    "page.control.strategy.not_selected": {
        "ru": "Не выбрана",
        "en": "Not selected",
    },
    "page.control.strategy.select_hint": {
        "ru": "Выберите стратегию в разделе «Стратегии»",
        "en": "Select a strategy in the Strategies section",
    },
    "page.control.strategy.active": {
        "ru": "Активная стратегия",
        "en": "Active strategy",
    },
    "page.control.setting.autostart.title": {
        "ru": "Автозагрузка DPI",
        "en": "DPI Autostart",
    },
    "page.control.setting.autostart.desc": {
        "ru": "Запускать Zapret автоматически при старте программы",
        "en": "Start Zapret automatically on app launch",
    },
    "page.control.setting.defender.title": {
        "ru": "Отключить Windows Defender",
        "en": "Disable Windows Defender",
    },
    "page.control.setting.defender.desc": {
        "ru": "Требуются права администратора",
        "en": "Administrator rights required",
    },
    "page.control.setting.max_block.title": {
        "ru": "Блокировать установку MAX",
        "en": "Block MAX installation",
    },
    "page.control.setting.max_block.desc": {
        "ru": "Блокирует запуск/установку MAX и домены в hosts",
        "en": "Blocks MAX launch/installation and hosts domains",
    },
    "page.control.setting.reset.title": {
        "ru": "Сбросить программу",
        "en": "Reset application",
    },
    "page.control.setting.reset.desc": {
        "ru": "Очистить кэш проверок запуска (без удаления пресетов/настроек)",
        "en": "Clear launch checks cache (without deleting presets/settings)",
    },
    "page.control.button.connection_test": {
        "ru": "Тест соединения",
        "en": "Connection Test",
    },
    "page.control.button.open_folder": {
        "ru": "Открыть папку",
        "en": "Open Folder",
    },
    "page.control.button.reset": {
        "ru": "Сбросить",
        "en": "Reset",
    },
    "page.control.button.reset_confirm": {
        "ru": "Сбросить (подтвердить)",
        "en": "Reset (confirm)",
    },
    "page.z2_control.title": {
        "ru": "Управление Zapret 2",
        "en": "Zapret 2 Control",
    },
    "page.z2_control.preset_switch": {
        "ru": "Сменить пресет обхода блокировок",
        "en": "Switch Bypass Preset",
    },
    "page.z2_control.direct_tuning": {
        "ru": "Настройте пресет более тонко через прямой запуск",
        "en": "Fine Tune via Direct Launch",
    },
    "page.z1_control.title": {
        "ru": "Управление Zapret 1",
        "en": "Zapret 1 Control",
    },
    "page.z1_control.presets": {
        "ru": "Пресеты и стратегии",
        "en": "Presets and Strategies",
    },
    "page.z1_control.status.checking": {
        "ru": "Проверка...",
        "en": "Checking...",
    },
    "page.z1_control.status.detecting": {
        "ru": "Определение состояния процесса",
        "en": "Detecting process state",
    },
    "page.z1_control.status.running": {
        "ru": "Zapret 1 работает",
        "en": "Zapret 1 is running",
    },
    "page.z1_control.status.stopped": {
        "ru": "Zapret 1 остановлен",
        "en": "Zapret 1 stopped",
    },
    "page.z1_control.status.bypass_active": {
        "ru": "Обход блокировок активен",
        "en": "Bypass is active",
    },
    "page.z1_control.status.press_start": {
        "ru": "Нажмите «Запустить» для активации",
        "en": "Press Start to activate",
    },
    "page.z1_control.button.start": {
        "ru": "Запустить Zapret",
        "en": "Start Zapret",
    },
    "page.z1_control.button.stop_winws": {
        "ru": "Остановить winws.exe",
        "en": "Stop winws.exe",
    },
    "page.z1_control.button.stop_and_exit": {
        "ru": "Остановить и закрыть",
        "en": "Stop and close",
    },
    "page.z1_control.preset.not_selected": {
        "ru": "Не выбран",
        "en": "Not selected",
    },
    "page.z1_control.preset.current": {
        "ru": "Текущий активный пресет",
        "en": "Current active preset",
    },
    "page.z1_control.button.my_presets": {
        "ru": "Мои пресеты",
        "en": "My Presets",
    },
    "page.z1_control.strategies.title": {
        "ru": "Стратегии по категориям",
        "en": "Strategies by category",
    },
    "page.z1_control.strategies.desc": {
        "ru": "Выбор стратегии для YouTube, Discord и др.",
        "en": "Select strategy for YouTube, Discord, and more",
    },
    "page.z1_control.button.open": {
        "ru": "Открыть",
        "en": "Open",
    },
    "page.z1_control.setting.autostart.title": {
        "ru": "Автозагрузка DPI",
        "en": "DPI Autostart",
    },
    "page.z1_control.setting.autostart.desc": {
        "ru": "Запускать Zapret автоматически при старте программы",
        "en": "Start Zapret automatically on app launch",
    },
    "page.z1_control.card.advanced": {
        "ru": "ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ",
        "en": "ADVANCED SETTINGS",
    },
    "page.z1_control.advanced.warning": {
        "ru": "Изменяйте только если знаете что делаете",
        "en": "Change only if you know what you are doing",
    },
    "page.z1_control.advanced.discord_restart.title": {
        "ru": "Перезапуск Discord",
        "en": "Restart Discord",
    },
    "page.z1_control.advanced.discord_restart.desc": {
        "ru": "Автоперезапуск при смене стратегии",
        "en": "Auto-restart on strategy change",
    },
    "page.z1_control.advanced.wssize.title": {
        "ru": "Включить --wssize",
        "en": "Enable --wssize",
    },
    "page.z1_control.advanced.wssize.desc": {
        "ru": "Добавляет параметр размера окна TCP",
        "en": "Adds TCP window size parameter",
    },
    "page.z1_control.advanced.debug_log.title": {
        "ru": "Включить лог-файл (--debug)",
        "en": "Enable log file (--debug)",
    },
    "page.z1_control.advanced.debug_log.desc": {
        "ru": "Записывает логи winws в папку logs",
        "en": "Writes winws logs to the logs folder",
    },
    "page.z1_control.blobs.title": {
        "ru": "Блобы",
        "en": "Blobs",
    },
    "page.z1_control.blobs.desc": {
        "ru": "Бинарные данные (.bin / hex) для стратегий",
        "en": "Binary data (.bin / hex) for strategies",
    },
    "page.z1_control.section.additional": {
        "ru": "Дополнительные действия",
        "en": "Additional actions",
    },
    "page.z1_control.button.connection_test": {
        "ru": "Тест соединения",
        "en": "Connection test",
    },
    "page.z1_control.button.connection_test.desc": {
        "ru": "Проверить доступность сети и состояние обхода",
        "en": "Check network reachability and bypass state",
    },
    "page.z1_control.button.open_folder": {
        "ru": "Открыть папку",
        "en": "Open folder",
    },
    "page.z1_control.button.open_folder.desc": {
        "ru": "Перейти в папку программы и служебных файлов",
        "en": "Open the app folder and service files",
    },
    "page.z1_control.button.documentation": {
        "ru": "Документация",
        "en": "Documentation",
    },
    "page.z1_control.button.documentation.desc": {
        "ru": "Открыть справку и описание возможностей",
        "en": "Open help and feature documentation",
    },
    "page.z1_strategy_detail.args_dialog.title": {
        "ru": "Аргументы стратегии",
        "en": "Strategy arguments",
    },
    "page.z1_strategy_detail.args_dialog.hint": {
        "ru": "Один аргумент на строку. Изменяет только выбранный target.",
        "en": "One argument per line. Changes only the selected target.",
    },
    "page.z1_strategy_detail.args_dialog.placeholder": {
        "ru": "Например:\n--dpi-desync=multisplit\n--dpi-desync-split-pos=1",
        "en": "For example:\n--dpi-desync=multisplit\n--dpi-desync-split-pos=1",
    },
    "page.z1_strategy_detail.args_dialog.button.save": {
        "ru": "Сохранить",
        "en": "Save",
    },
    "page.z1_strategy_detail.args_dialog.button.cancel": {
        "ru": "Отмена",
        "en": "Cancel",
    },
    "page.z1_strategy_detail.header.category_fallback": {
        "ru": "Target",
        "en": "Target",
    },
    "page.z1_strategy_detail.back.strategies": {
        "ru": "← Стратегии Zapret 1",
        "en": "← Zapret 1 Strategies",
    },
    "page.z1_strategy_detail.breadcrumb.control": {
        "ru": "Управление",
        "en": "Control",
    },
    "page.z1_strategy_detail.breadcrumb.strategies": {
        "ru": "Прямой запуск Zapret 1",
        "en": "Zapret 1 Direct",
    },
    "page.z1_strategy_detail.state.category_bypass": {
        "ru": "Обход для target'а",
        "en": "Bypass for target",
    },
    "page.z1_strategy_detail.toggle.on": {
        "ru": "Включено",
        "en": "Enabled",
    },
    "page.z1_strategy_detail.toggle.off": {
        "ru": "Выключено",
        "en": "Disabled",
    },
    "page.z1_strategy_detail.filter.label": {
        "ru": "Фильтр:",
        "en": "Filter:",
    },
    "page.z1_strategy_detail.filter.ipset": {
        "ru": "IPset",
        "en": "IPset",
    },
    "page.z1_strategy_detail.filter.hostlist": {
        "ru": "Hostlist",
        "en": "Hostlist",
    },
    "page.z1_strategy_detail.search.placeholder": {
        "ru": "Поиск стратегии по названию или аргументам",
        "en": "Search strategy by name or arguments",
    },
    "page.z1_strategy_detail.sort.recommended": {
        "ru": "По рекомендации",
        "en": "By recommendation",
    },
    "page.z1_strategy_detail.sort.alpha_asc": {
        "ru": "По алфавиту A-Z",
        "en": "Alphabetical A-Z",
    },
    "page.z1_strategy_detail.sort.alpha_desc": {
        "ru": "По алфавиту Z-A",
        "en": "Alphabetical Z-A",
    },
    "page.z1_strategy_detail.button.edit_args": {
        "ru": "Редактировать аргументы",
        "en": "Edit arguments",
    },
    "page.z1_strategy_detail.args.none": {
        "ru": "(нет аргументов)",
        "en": "(no arguments)",
    },
    "page.z1_strategy_detail.args.more": {
        "ru": "\n... (+{count} строк)",
        "en": "\n... (+{count} lines)",
    },
    "page.z1_strategy_detail.card.strategies": {
        "ru": "Стратегии",
        "en": "Strategies",
    },
    "page.z1_strategy_detail.empty.no_strategies": {
        "ru": "Нет доступных стратегий. Проверьте %APPDATA%\\zapret\\direct_zapret1\\",
        "en": "No strategies available. Check %APPDATA%\\zapret\\direct_zapret1\\",
    },
    "page.z1_strategy_detail.tree.disabled.name": {
        "ru": "Выключено",
        "en": "Disabled",
    },
    "page.z1_strategy_detail.tree.disabled.args": {
        "ru": "Отключить обход DPI для этого target'а",
        "en": "Disable DPI bypass for this target",
    },
    "page.z1_strategy_detail.tree.custom.name": {
        "ru": "Свой набор",
        "en": "Custom set",
    },
    "page.z1_strategy_detail.tree.custom.args": {
        "ru": "Пользовательские аргументы",
        "en": "Custom arguments",
    },
    "page.z1_strategy_detail.subtitle.ports": {
        "ru": "порты: {ports}",
        "en": "ports: {ports}",
    },
    "page.z1_strategy_detail.selected.current": {
        "ru": "Текущая стратегия: {strategy}",
        "en": "Current strategy: {strategy}",
    },
    "page.z1_strategy_detail.error.filter_mode_save": {
        "ru": "Не удалось сохранить режим фильтрации",
        "en": "Failed to save filter mode",
    },
    "page.z1_strategy_detail.infobar.filter_mode.title": {
        "ru": "Режим фильтрации",
        "en": "Filter mode",
    },
    "page.z1_strategy_detail.infobar.strategy_applied": {
        "ru": "Стратегия применена",
        "en": "Strategy applied",
    },
    "page.z1_strategy_detail.infobar.args_saved.title": {
        "ru": "Аргументы сохранены",
        "en": "Arguments saved",
    },
    "page.z1_strategy_detail.infobar.args_saved.content": {
        "ru": "Пользовательские аргументы применены",
        "en": "Custom arguments applied",
    },
    "page.z1_strategy_detail.infobar.args_cleared.title": {
        "ru": "Аргументы очищены",
        "en": "Arguments cleared",
    },
    "page.z1_strategy_detail.infobar.args_cleared.content": {
        "ru": "Target возвращён в режим 'Выключено'",
        "en": "Target returned to 'Disabled' mode",
    },
    "page.orchestra.title": {
        "ru": "Оркестратор",
        "en": "Orchestrator",
    },
    "page.orchestra.training_status": {
        "ru": "Статус обучения",
        "en": "Training Status",
    },
    "page.orchestra.log": {
        "ru": "Лог обучения",
        "en": "Training Log",
    },
    "page.hostlist.title": {
        "ru": "Листы",
        "en": "Lists",
    },
    "page.hostlist.hostlist": {
        "ru": "Hostlist",
        "en": "Hostlist",
    },
    "page.hostlist.ipset": {
        "ru": "IPset",
        "en": "IPset",
    },
    "page.hostlist.exclusions": {
        "ru": "Исключения",
        "en": "Exclusions",
    },
    "page.dpi_settings.title": {
        "ru": "Настройки DPI",
        "en": "DPI Settings",
    },
    "page.dpi_settings.launch_method": {
        "ru": "Метод запуска стратегий",
        "en": "Strategy Launch Method",
    },
    "page.autostart.title": {
        "ru": "Автозапуск",
        "en": "Autostart",
    },
    "page.autostart.mode": {
        "ru": "Режим",
        "en": "Mode",
    },
    "page.network.title": {
        "ru": "Сеть",
        "en": "Network",
    },
    "page.network.dns": {
        "ru": "DNS",
        "en": "DNS",
    },
    "page.network.adapters": {
        "ru": "Сетевые адаптеры",
        "en": "Network Adapters",
    },
    "page.network.tools": {
        "ru": "Утилиты",
        "en": "Utilities",
    },
    "page.hosts.title": {
        "ru": "Hosts",
        "en": "Hosts",
    },
    "page.hosts.services": {
        "ru": "Сервисы",
        "en": "Services",
    },
    "page.blockcheck.title": {
        "ru": "BlockCheck",
        "en": "BlockCheck",
    },
    "page.blockcheck.monitoring": {
        "ru": "Живой мониторинг сети",
        "en": "Live Network Monitoring",
    },
    "page.blockcheck.subtitle": {
        "ru": "Автоматический анализ блокировок и диагностика сети в один клик",
        "en": "Automatic blocking analysis and network diagnostics in one click",
    },
    "page.blockcheck.tab.blockcheck": {
        "ru": "BlockCheck",
        "en": "BlockCheck",
    },
    "page.blockcheck.tab.strategy_scan": {
        "ru": "Подбор стратегии",
        "en": "Strategy Selection",
    },
    "page.blockcheck.tab.diagnostics": {
        "ru": "Диагностика",
        "en": "Diagnostics",
    },
    "page.blockcheck.tab.dns_spoofing": {
        "ru": "DNS подмена",
        "en": "DNS Spoofing",
    },
    "page.blockcheck.control": {
        "ru": "Управление",
        "en": "Control",
    },
    "page.blockcheck.mode": {
        "ru": "Режим:",
        "en": "Mode:",
    },
    "page.blockcheck.mode_quick": {
        "ru": "Быстрая",
        "en": "Quick",
    },
    "page.blockcheck.mode_full": {
        "ru": "Полная",
        "en": "Full",
    },
    "page.blockcheck.mode_dpi": {
        "ru": "Только DPI",
        "en": "DPI Only",
    },
    "page.blockcheck.start": {
        "ru": "Запустить",
        "en": "Start",
    },
    "page.blockcheck.stop": {
        "ru": "Остановить",
        "en": "Stop",
    },
    "page.blockcheck.ready": {
        "ru": "Готово",
        "en": "Ready",
    },
    "page.blockcheck.running": {
        "ru": "Запуск тестов...",
        "en": "Running tests...",
    },
    "page.blockcheck.stopping": {
        "ru": "Остановка...",
        "en": "Stopping...",
    },
    "page.blockcheck.done": {
        "ru": "Готово",
        "en": "Done",
    },
    "page.blockcheck.error": {
        "ru": "Ошибка выполнения",
        "en": "Execution error",
    },
    "page.blockcheck.results": {
        "ru": "Результаты",
        "en": "Results",
    },
    "page.blockcheck.col_target": {
        "ru": "Цель",
        "en": "Target",
    },
    "page.blockcheck.dpi_summary": {
        "ru": "DPI Анализ",
        "en": "DPI Analysis",
    },
    "page.blockcheck.no_dpi": {
        "ru": "DPI не обнаружен на проверенных ресурсах",
        "en": "No DPI detected on tested resources",
    },
    "page.blockcheck.log": {
        "ru": "Подробный лог",
        "en": "Detailed Log",
    },
    "page.blockcheck.custom_domains": {
        "ru": "Пользовательские домены",
        "en": "Custom Domains",
    },
    "page.blockcheck.domain_placeholder": {
        "ru": "example.com",
        "en": "example.com",
    },
    "page.blockcheck.add_domain": {
        "ru": "Добавить",
        "en": "Add",
    },
    "page.blockcheck.domain_exists_title": {
        "ru": "Домен уже добавлен",
        "en": "Domain already added",
    },
    "page.appearance.title": {
        "ru": "Оформление",
        "en": "Appearance",
    },
    "page.appearance.display_mode": {
        "ru": "Режим отображения",
        "en": "Display Mode",
    },
    "page.appearance.background": {
        "ru": "Фон окна",
        "en": "Window Background",
    },
    "page.premium.title": {
        "ru": "Premium",
        "en": "Premium",
    },
    "page.premium.subscription_status": {
        "ru": "Статус подписки",
        "en": "Subscription Status",
    },
    "page.logs.title": {
        "ru": "Логи",
        "en": "Logs",
    },
    "page.logs.controls": {
        "ru": "Управление логами",
        "en": "Log Controls",
    },
    "page.about.title": {
        "ru": "О программе",
        "en": "About",
    },
    "page.about.version": {
        "ru": "Версия",
        "en": "Version",
    },
    "page.about.support": {
        "ru": "Каналы поддержки",
        "en": "Support Channels",
    },
    "page.about.subtitle": {
        "ru": "Версия, подписка и информация",
        "en": "Version, subscription and information",
    },
    "page.about.tab.about": {
        "ru": "О ПРОГРАММЕ",
        "en": "ABOUT",
    },
    "page.about.tab.support": {
        "ru": "ПОДДЕРЖКА",
        "en": "SUPPORT",
    },
    "page.about.tab.help": {
        "ru": "СПРАВКА",
        "en": "HELP",
    },
    "page.about.section.version": {
        "ru": "Версия",
        "en": "Version",
    },
    "page.about.section.device": {
        "ru": "Устройство",
        "en": "Device",
    },
    "page.about.section.subscription": {
        "ru": "Подписка",
        "en": "Subscription",
    },
    "page.about.version.value_template": {
        "ru": "Версия {version}",
        "en": "Version {version}",
    },
    "page.about.button.update_settings": {
        "ru": "Настройка обновлений",
        "en": "Update Settings",
    },
    "page.about.device.id": {
        "ru": "ID устройства",
        "en": "Device ID",
    },
    "page.about.button.copy_id": {
        "ru": "Копировать ID",
        "en": "Copy ID",
    },
    "page.about.subscription.free": {
        "ru": "Free версия",
        "en": "Free version",
    },
    "page.about.subscription.premium_active": {
        "ru": "Premium активен",
        "en": "Premium active",
    },
    "page.about.subscription.premium_days": {
        "ru": "Premium (осталось {days} дней)",
        "en": "Premium ({days} days left)",
    },
    "page.about.subscription.desc": {
        "ru": "Подписка Zapret Premium открывает доступ к дополнительным темам, приоритетной поддержке и VPN-сервису.",
        "en": "Zapret Premium gives access to extra themes, priority support, and VPN service.",
    },
    "page.about.button.premium_vpn": {
        "ru": "Premium и VPN",
        "en": "Premium and VPN",
    },
    "page.about.support.section.discussions": {
        "ru": "GitHub Discussions",
        "en": "GitHub Discussions",
    },
    "page.about.support.section.community": {
        "ru": "Каналы сообщества",
        "en": "Community Channels",
    },
    "page.about.support.discussions.title": {
        "ru": "GitHub Discussions",
        "en": "GitHub Discussions",
    },
    "page.about.support.discussions.desc": {
        "ru": "Основной канал поддержки. Здесь можно задать вопрос, описать проблему и приложить материалы вручную.",
        "en": "Main support channel. Ask questions, describe the issue, and attach materials manually.",
    },
    "page.about.support.discussions.button": {
        "ru": "Открыть",
        "en": "Open",
    },
    "page.about.support.telegram.title": {
        "ru": "Telegram",
        "en": "Telegram",
    },
    "page.about.support.telegram.desc": {
        "ru": "Быстрые вопросы и общение с сообществом",
        "en": "Quick questions and community chat",
    },
    "page.about.support.discord.title": {
        "ru": "Discord",
        "en": "Discord",
    },
    "page.about.support.discord.desc": {
        "ru": "Обсуждение и живое общение",
        "en": "Discussion and live chat",
    },
    "page.about.support.button.open": {
        "ru": "Открыть",
        "en": "Open",
    },
    "page.about.help.section.links": {
        "ru": "Ссылки",
        "en": "Links",
    },
    "page.about.help.group.docs": {
        "ru": "Документация",
        "en": "Documentation",
    },
    "page.about.help.group.news": {
        "ru": "Новости",
        "en": "News",
    },
    "page.about.help.button.open": {
        "ru": "Открыть",
        "en": "Open",
    },
    "page.about.help.docs.forum.title": {
        "ru": "Сайт-форум для новичков",
        "en": "Beginner forum site",
    },
    "page.about.help.docs.forum.desc": {
        "ru": "Авторизация через Telegram-бота",
        "en": "Authorization via Telegram bot",
    },
    "page.about.help.docs.info.title": {
        "ru": "Что это такое?",
        "en": "What is this?",
    },
    "page.about.help.docs.info.desc": {
        "ru": "Руководство и ответы на вопросы",
        "en": "Guide and FAQ",
    },
    "page.about.help.docs.folder.title": {
        "ru": "Папка с инструкциями",
        "en": "Help folder",
    },
    "page.about.help.docs.folder.desc": {
        "ru": "Открыть локальную папку help",
        "en": "Open local help folder",
    },
    "page.about.help.docs.android.title": {
        "ru": "На Android (Magisk Zapret, ByeByeDPI и др.)",
        "en": "On Android (Magisk Zapret, ByeByeDPI, etc.)",
    },
    "page.about.help.docs.android.desc": {
        "ru": "Открыть инструкцию на сайте",
        "en": "Open website guide",
    },
    "page.about.help.docs.github.desc": {
        "ru": "Исходный код и документация",
        "en": "Source code and documentation",
    },
    "page.about.help.news.telegram.title": {
        "ru": "Telegram канал",
        "en": "Telegram channel",
    },
    "page.about.help.news.telegram.desc": {
        "ru": "Новости и обновления",
        "en": "News and updates",
    },
    "page.about.help.news.youtube.title": {
        "ru": "YouTube канал",
        "en": "YouTube channel",
    },
    "page.about.help.news.youtube.desc": {
        "ru": "Видео и обновления",
        "en": "Videos and updates",
    },
    "page.about.help.news.mastodon.title": {
        "ru": "Mastodon профиль",
        "en": "Mastodon profile",
    },
    "page.about.help.news.mastodon.desc": {
        "ru": "Новости в Fediverse",
        "en": "Fediverse updates",
    },
    "page.about.help.news.bastyon.title": {
        "ru": "Bastyon профиль",
        "en": "Bastyon profile",
    },
    "page.about.help.news.bastyon.desc": {
        "ru": "Новости в Bastyon",
        "en": "Bastyon updates",
    },
    "page.about.help.motto.title": {
        "ru": "keep thinking, keep searching, keep learning....",
        "en": "keep thinking, keep searching, keep learning....",
    },
    "page.about.help.motto.subtitle": {
        "ru": "Продолжай думать, продолжай искать, продолжай учиться....",
        "en": "Keep thinking, keep searching, keep learning....",
    },
    "page.about.help.motto.cta": {
        "ru": "Zapret2 - думай свободно, ищи смелее, учись всегда.",
        "en": "Zapret2 - think freely, search boldly, learn always.",
    },
    "page.appearance.subtitle": {
        "ru": "Настройка внешнего вида приложения",
        "en": "Application appearance settings",
    },
    "page.appearance.section.display_mode": {
        "ru": "Режим отображения",
        "en": "Display Mode",
    },
    "page.appearance.section.background": {
        "ru": "Фон окна",
        "en": "Window Background",
    },
    "page.appearance.section.holiday": {
        "ru": "Новогоднее оформление",
        "en": "Holiday Effects",
    },
    "page.appearance.section.accent": {
        "ru": "Акцентный цвет",
        "en": "Accent Color",
    },
    "page.appearance.section.performance": {
        "ru": "Производительность",
        "en": "Performance",
    },
    "page.autostart.subtitle": {
        "ru": "Настройка автоматического запуска Zapret",
        "en": "Configure automatic Zapret startup",
    },
    "page.autostart.section.status": {
        "ru": "Статус",
        "en": "Status",
    },
    "page.autostart.section.mode": {
        "ru": "Режим",
        "en": "Mode",
    },
    "page.autostart.section.select_type": {
        "ru": "Автозапуск программы",
        "en": "Application autostart",
    },
    "page.autostart.section.info": {
        "ru": "Информация",
        "en": "Information",
    },
    "page.autostart.status.disabled.title": {
        "ru": "Автозапуск отключён",
        "en": "Autostart disabled",
    },
    "page.autostart.status.disabled.desc": {
        "ru": "Zapret не запускается автоматически",
        "en": "Zapret does not start automatically",
    },
    "page.autostart.status.enabled.title": {
        "ru": "Автозапуск включён",
        "en": "Autostart enabled",
    },
    "page.autostart.status.enabled.desc.base": {
        "ru": "Zapret запускается автоматически при входе в Windows и открывается в трее",
        "en": "Zapret starts automatically on Windows logon and opens in the tray",
    },
    "page.autostart.button.disable": {
        "ru": "Отключить",
        "en": "Disable",
    },
    "page.autostart.mode.current_label": {
        "ru": "Текущий режим:",
        "en": "Current mode:",
    },
    "page.autostart.mode.loading": {
        "ru": "Загрузка...",
        "en": "Loading...",
    },
    "page.autostart.mode.strategy_label": {
        "ru": "Стратегия:",
        "en": "Strategy:",
    },
    "page.autostart.mode.direct_zapret2": {
        "ru": "Прямой запуск (Zapret 2)",
        "en": "Direct launch (Zapret 2)",
    },
    "page.autostart.mode.orchestra_learning": {
        "ru": "Оркестр (автообучение)",
        "en": "Orchestrator (auto-learning)",
    },
    "page.autostart.mode.classic_bat": {
        "ru": "Классический (BAT файлы)",
        "en": "Classic (BAT files)",
    },
    "page.autostart.mode.unknown": {
        "ru": "Неизвестно",
        "en": "Unknown",
    },
    "page.autostart.strategy.not_selected": {
        "ru": "Не выбрана",
        "en": "Not selected",
    },
    "page.autostart.option.gui.title": {
        "ru": "Автозапуск программы Zapret",
        "en": "Autostart Zapret application",
    },
    "page.autostart.option.gui.desc": {
        "ru": "Запускает главное окно программы при входе в Windows. Приложение стартует в трее и уже оттуда применяет текущие настройки.",
        "en": "Starts the main application window on Windows logon. The app launches in the tray and applies the current settings from there.",
    },
    "page.autostart.tip.recommendation": {
        "ru": "Используется один тип автозапуска: запуск самого ZapretGUI в трей через Планировщик заданий Windows.",
        "en": "Only one autostart type is used: launching ZapretGUI itself in the tray through Windows Task Scheduler.",
    },
    "page.blobs.title": {
        "ru": "Блобы",
        "en": "Blobs",
    },
    "page.blobs.subtitle": {
        "ru": "Управление бинарными данными для стратегий",
        "en": "Manage binary data for strategies",
    },
    "page.blobs.button.back": {
        "ru": "Управление",
        "en": "Control",
    },
    "page.blobs.description": {
        "ru": "Блобы — это бинарные данные (файлы .bin или hex-значения), используемые в стратегиях для имитации TLS/QUIC пакетов.\nВы можете добавлять свои блобы для кастомных стратегий.",
        "en": "Blobs are binary data (.bin files or hex values) used in strategies to imitate TLS/QUIC packets.\nYou can add your own blobs for custom strategies.",
    },
    "page.blobs.button.add": {
        "ru": "Добавить блоб",
        "en": "Add blob",
    },
    "page.blobs.button.bin_folder": {
        "ru": "Папка bin",
        "en": "bin folder",
    },
    "page.blobs.button.open_json": {
        "ru": "Открыть JSON",
        "en": "Open JSON",
    },
    "page.blobs.filter.placeholder": {
        "ru": "Фильтр по имени...",
        "en": "Filter by name...",
    },
    "page.blobs.section.user": {
        "ru": "★ Пользовательские ({count})",
        "en": "★ Custom ({count})",
    },
    "page.blobs.section.system": {
        "ru": "Системные ({count})",
        "en": "System ({count})",
    },
    "page.blobs.count": {
        "ru": "{total} блобов ({user} пользовательских)",
        "en": "{total} blobs ({user} custom)",
    },
    "page.blobs.item.user_badge": {
        "ru": "пользовательский",
        "en": "custom",
    },
    "page.blobs.item.file_found": {
        "ru": "Файл найден",
        "en": "File found",
    },
    "page.blobs.item.file_missing": {
        "ru": "Файл не найден",
        "en": "File not found",
    },
    "page.blobs.dialog.delete.title": {
        "ru": "Удаление блоба",
        "en": "Delete blob",
    },
    "page.blobs.dialog.delete.body": {
        "ru": "Удалить пользовательский блоб '{name}'?",
        "en": "Delete custom blob '{name}'?",
    },
    "page.blobs.dialog.add.title": {
        "ru": "Добавить блоб",
        "en": "Add blob",
    },
    "page.blobs.dialog.add.name": {
        "ru": "Имя",
        "en": "Name",
    },
    "page.blobs.dialog.add.name.placeholder": {
        "ru": "Латиница, цифры, подчеркивания",
        "en": "Latin letters, numbers, underscores",
    },
    "page.blobs.dialog.add.type": {
        "ru": "Тип",
        "en": "Type",
    },
    "page.blobs.dialog.add.type.file": {
        "ru": "Файл (.bin)",
        "en": "File (.bin)",
    },
    "page.blobs.dialog.add.type.hex": {
        "ru": "Hex значение",
        "en": "Hex value",
    },
    "page.blobs.dialog.add.value": {
        "ru": "Значение",
        "en": "Value",
    },
    "page.blobs.dialog.add.value.path_placeholder": {
        "ru": "Путь к файлу",
        "en": "File path",
    },
    "page.blobs.dialog.add.value.hex_placeholder": {
        "ru": "Hex значение (например: 0x0E0E0F0E)",
        "en": "Hex value (for example: 0x0E0E0F0E)",
    },
    "page.blobs.dialog.add.value.path_placeholder_bin": {
        "ru": "Путь к .bin файлу",
        "en": "Path to .bin file",
    },
    "page.blobs.dialog.add.browse.tooltip": {
        "ru": "Выбрать файл",
        "en": "Select file",
    },
    "page.blobs.dialog.add.browse.title": {
        "ru": "Выберите файл блоба",
        "en": "Choose blob file",
    },
    "page.blobs.dialog.add.description": {
        "ru": "Описание (опционально)",
        "en": "Description (optional)",
    },
    "page.blobs.dialog.add.description.placeholder": {
        "ru": "Краткое описание блоба",
        "en": "Short blob description",
    },
    "page.blobs.dialog.add.button.add": {
        "ru": "Добавить",
        "en": "Add",
    },
    "page.blobs.dialog.add.button.cancel": {
        "ru": "Отмена",
        "en": "Cancel",
    },
    "page.blobs.dialog.add.error.name_required": {
        "ru": "Введите имя блоба",
        "en": "Enter blob name",
    },
    "page.blobs.dialog.add.error.name_invalid": {
        "ru": "Имя должно начинаться с буквы и содержать только латиницу, цифры и подчеркивания",
        "en": "Name must start with a letter and contain only Latin letters, digits, and underscores",
    },
    "page.blobs.dialog.add.error.value_required": {
        "ru": "Введите значение блоба",
        "en": "Enter blob value",
    },
    "page.blobs.dialog.add.error.hex_prefix": {
        "ru": "Hex значение должно начинаться с 0x",
        "en": "Hex value must start with 0x",
    },
    "page.blobs.error.load": {
        "ru": "❌ Ошибка загрузки: {error}",
        "en": "❌ Load error: {error}",
    },
    "page.blobs.error.save": {
        "ru": "Не удалось сохранить блоб",
        "en": "Failed to save blob",
    },
    "page.blobs.error.add": {
        "ru": "Не удалось добавить блоб: {error}",
        "en": "Failed to add blob: {error}",
    },
    "page.blobs.error.delete_named": {
        "ru": "Не удалось удалить блоб '{name}'",
        "en": "Failed to delete blob '{name}'",
    },
    "page.blobs.error.delete": {
        "ru": "Не удалось удалить блоб: {error}",
        "en": "Failed to delete blob: {error}",
    },
    "page.blobs.error.open_folder": {
        "ru": "Не удалось открыть папку: {error}",
        "en": "Failed to open folder: {error}",
    },
    "page.blobs.error.open_file": {
        "ru": "Не удалось открыть файл: {error}",
        "en": "Failed to open file: {error}",
    },
    "page.connection.title": {
        "ru": "Диагностика соединения",
        "en": "Connection Diagnostics",
    },
    "page.connection.subtitle": {
        "ru": "Автотест Discord и YouTube, проверка DNS подмены и быстрая подготовка обращения в GitHub Discussions",
        "en": "Auto-test Discord and YouTube, check DNS spoofing, and quickly prepare a GitHub Discussions report",
    },
    "page.connection.hero.title": {
        "ru": "Диагностика сетевых соединений",
        "en": "Network Connection Diagnostics",
    },
    "page.connection.hero.subtitle": {
        "ru": "Проверьте доступность Discord и YouTube, а затем одной кнопкой соберите ZIP с логами и откройте GitHub Discussions.",
        "en": "Check Discord and YouTube availability, then create a ZIP with logs and open GitHub Discussions in one click.",
    },
    "page.connection.card.testing": {
        "ru": "Тестирование",
        "en": "Testing",
    },
    "page.connection.card.result": {
        "ru": "Результат тестирования",
        "en": "Test Result",
    },
    "page.connection.test.select": {
        "ru": "Выбор теста:",
        "en": "Test selection:",
    },
    "page.connection.test.all": {
        "ru": "🌐 Все тесты (Discord + YouTube)",
        "en": "🌐 All tests (Discord + YouTube)",
    },
    "page.connection.test.discord_only": {
        "ru": "🎮 Только Discord",
        "en": "🎮 Discord only",
    },
    "page.connection.test.youtube_only": {
        "ru": "🎬 Только YouTube",
        "en": "🎬 YouTube only",
    },
    "page.connection.button.start": {
        "ru": "Запустить тест",
        "en": "Start test",
    },
    "page.connection.button.stop": {
        "ru": "Стоп",
        "en": "Stop",
    },
    "page.connection.button.send_log": {
        "ru": "Подготовить обращение",
        "en": "Prepare report",
    },
    "page.connection.status.ready": {
        "ru": "Готово к тестированию",
        "en": "Ready for testing",
    },
    "page.connection.progress.waiting": {
        "ru": "Ожидает запуска",
        "en": "Waiting to start",
    },
    "page.control.subtitle": {
        "ru": "Запуск и остановка Zapret, быстрые настройки программы.",
        "en": "Start and stop Zapret, quick application settings.",
    },
    "page.control.section.status": {
        "ru": "Статус работы",
        "en": "Service Status",
    },
    "page.control.section.management": {
        "ru": "Управление Zapret",
        "en": "Zapret Control",
    },
    "page.control.section.current_strategy": {
        "ru": "Текущая стратегия",
        "en": "Current Strategy",
    },
    "page.control.section.program_settings": {
        "ru": "Настройки программы",
        "en": "Program Settings",
    },
    "page.control.section.additional": {
        "ru": "Дополнительно",
        "en": "Additional",
    },
    "page.custom_domains.title": {
        "ru": "Кастомные (мои) домены (hostlist) для работы с Zapret",
        "en": "Custom Domains (hostlist) for Zapret",
    },
    "page.custom_domains.subtitle": {
        "ru": "Управление доменами (other.txt). Субдомены учитываются автоматически. Строчка rkn.ru учитывает и сайт fuckyou.rkn.ru и сайт ass.rkn.ru. Чтобы исключить субдомены напишите домен с символов ^ в начале, то есть например так ^rkn.ru",
        "en": "Manage domains (other.txt). Subdomains are handled automatically. Prefix a domain with ^ to match only the exact domain.",
    },
    "page.custom_domains.description": {
        "ru": "Здесь редактируется файл other.user.txt (только ваши домены). Системная база берётся из шаблона и отдельно хранится в other.base.txt, а общий other.txt собирается автоматически. URL автоматически преобразуются в домены. Изменения сохраняются автоматически. Поддерживается Ctrl+Z.",
        "en": "Edit other.user.txt (your domains only). The system base comes from template in other.base.txt, and combined other.txt is rebuilt automatically. URLs are converted to domains automatically. Changes are saved automatically. Ctrl+Z is supported.",
    },
    "page.custom_domains.card.add": {
        "ru": "Добавить домен",
        "en": "Add Domain",
    },
    "page.custom_domains.card.actions": {
        "ru": "Действия",
        "en": "Actions",
    },
    "page.custom_domains.card.editor": {
        "ru": "other.user.txt (редактор)",
        "en": "other.user.txt (editor)",
    },
    "page.custom_domains.input.placeholder": {
        "ru": "Введите домен или URL (например: example.com или https://site.com/page)",
        "en": "Enter a domain or URL (for example: example.com or https://site.com/page)",
    },
    "page.custom_domains.button.add": {
        "ru": "Добавить",
        "en": "Add",
    },
    "page.custom_domains.button.open_file": {
        "ru": "Открыть файл",
        "en": "Open File",
    },
    "page.custom_domains.button.reset_file": {
        "ru": "Сбросить файл",
        "en": "Reset File",
    },
    "page.custom_domains.button.clear_all": {
        "ru": "Очистить всё",
        "en": "Clear All",
    },
    "page.custom_domains.confirm.reset_file": {
        "ru": "Подтвердить сброс",
        "en": "Confirm reset",
    },
    "page.custom_domains.confirm.clear_all": {
        "ru": "Подтвердить очистку",
        "en": "Confirm clear",
    },
    "page.custom_domains.tooltip.open_file": {
        "ru": "Сохраняет изменения и открывает other.user.txt в проводнике",
        "en": "Saves changes and opens other.user.txt in Explorer",
    },
    "page.custom_domains.tooltip.reset_file": {
        "ru": "Очищает other.user.txt (мои домены) и пересобирает other.txt из системной базы",
        "en": "Clears other.user.txt (my domains) and rebuilds other.txt from system base",
    },
    "page.custom_domains.tooltip.clear_all": {
        "ru": "Удаляет только пользовательские домены. Базовые домены из шаблона останутся",
        "en": "Removes only custom domains. Base template domains remain",
    },
    "page.custom_domains.editor.placeholder": {
        "ru": "Домены по одному на строку:\nexample.com\nsubdomain.site.org\n\nКомментарии начинаются с #",
        "en": "One domain per line:\nexample.com\nsubdomain.site.org\n\nComments start with #",
    },
    "page.custom_domains.hint.autosave": {
        "ru": "Изменения сохраняются автоматически через 500мс",
        "en": "Changes are saved automatically after 500 ms",
    },
    "page.custom_domains.status.error": {
        "ru": "❌ Ошибка: {error}",
        "en": "❌ Error: {error}",
    },
    "page.custom_domains.status.suffix.saved": {
        "ru": " • ✅ Сохранено",
        "en": " • ✅ Saved",
    },
    "page.custom_domains.status.suffix.reset": {
        "ru": " • ✅ Сброшено",
        "en": " • ✅ Reset",
    },
    "page.custom_domains.status.stats": {
        "ru": "📊 Доменов: {total} (база: {base}, пользовательские: {user})",
        "en": "📊 Domains: {total} (base: {base}, custom: {user})",
    },
    "page.custom_domains.infobar.error": {
        "ru": "Ошибка",
        "en": "Error",
    },
    "page.custom_domains.infobar.info": {
        "ru": "Информация",
        "en": "Information",
    },
    "page.custom_domains.infobar.invalid_domain": {
        "ru": "Не удалось распознать домен:\n{value}\n\nВведите корректный домен (например: example.com)",
        "en": "Could not recognize domain:\n{value}\n\nEnter a valid domain (for example: example.com)",
    },
    "page.custom_domains.infobar.duplicate": {
        "ru": "Домен уже добавлен:\n{domain}",
        "en": "Domain already added:\n{domain}",
    },
    "page.custom_domains.infobar.reset_failed": {
        "ru": "Не удалось сбросить my hostlist",
        "en": "Failed to reset my hostlist",
    },
    "page.custom_domains.infobar.reset_failed_error": {
        "ru": "Не удалось сбросить:\n{error}",
        "en": "Failed to reset:\n{error}",
    },
    "page.custom_domains.infobar.open_failed": {
        "ru": "Не удалось открыть:\n{error}",
        "en": "Failed to open:\n{error}",
    },
    "page.custom_ipset.title": {
        "ru": "Кастомные (мои) IP и подсети для ipset-all",
        "en": "Custom IPs and Subnets for ipset-all",
    },
    "page.custom_ipset.subtitle": {
        "ru": "Здесь Вы можете редактировать пользовательский список IP/подсетей (ipset-all.user.txt). Пишите только IP/CIDR, изменения сохраняются автоматически.",
        "en": "Edit custom IP/subnet list (ipset-all.user.txt). Use IP/CIDR format only; changes are saved automatically.",
    },
    "page.custom_ipset.description": {
        "ru": "Добавляйте свои IP/подсети в ipset-all.user.txt.\n• Одиночный IP: 1.2.3.4\n• Подсеть: 10.0.0.0/8\nДиапазоны (a-b) не поддерживаются.\nСистемная база хранится в ipset-all.base.txt и объединяется автоматически в ipset-all.txt.",
        "en": "Add your own IPs/subnets to ipset-all.user.txt.\n• Single IP: 1.2.3.4\n• Subnet: 10.0.0.0/8\nRanges (a-b) are not supported.\nSystem base is stored in ipset-all.base.txt and merged into ipset-all.txt automatically.",
    },
    "page.custom_ipset.section.add": {
        "ru": "Добавить IP/подсеть",
        "en": "Add IP/subnet",
    },
    "page.custom_ipset.input.placeholder": {
        "ru": "Например: 1.2.3.4 или 10.0.0.0/8",
        "en": "For example: 1.2.3.4 or 10.0.0.0/8",
    },
    "page.custom_ipset.button.add": {
        "ru": "Добавить",
        "en": "Add",
    },
    "page.custom_ipset.section.actions": {
        "ru": "Действия",
        "en": "Actions",
    },
    "page.custom_ipset.button.open_file": {
        "ru": "Открыть файл",
        "en": "Open file",
    },
    "page.custom_ipset.button.clear_all": {
        "ru": "Очистить всё",
        "en": "Clear all",
    },
    "page.custom_ipset.section.editor": {
        "ru": "ipset-all.user.txt (редактор)",
        "en": "ipset-all.user.txt (editor)",
    },
    "page.custom_ipset.editor.placeholder": {
        "ru": "IP/подсети по одному на строку:\n192.168.0.1\n10.0.0.0/8\n\nКомментарии начинаются с #",
        "en": "IPs/subnets one per line:\n192.168.0.1\n10.0.0.0/8\n\nComments start with #",
    },
    "page.custom_ipset.hint.autosave": {
        "ru": "💡 Изменения сохраняются автоматически через 500мс",
        "en": "💡 Changes are saved automatically after 500 ms",
    },
    "page.custom_ipset.status.error_load": {
        "ru": "❌ Ошибка загрузки: {error}",
        "en": "❌ Load error: {error}",
    },
    "page.custom_ipset.status.summary": {
        "ru": "📊 Записей: {total} (база: {base}, пользовательские: {user})",
        "en": "📊 Entries: {total} (base: {base}, custom: {user})",
    },
    "page.custom_ipset.status.saved_suffix": {
        "ru": " • ✅ Сохранено",
        "en": " • ✅ Saved",
    },
    "page.custom_ipset.validation.invalid_prefix": {
        "ru": "❌ Неверный формат:\n",
        "en": "❌ Invalid format:\n",
    },
    "page.custom_ipset.validation.line": {
        "ru": "Строка {line}: {value}",
        "en": "Line {line}: {value}",
    },
    "page.custom_ipset.validation.more_suffix": {
        "ru": "\n... и ещё {count}",
        "en": "\n... and {count} more",
    },
    "page.custom_ipset.error.parse_entry": {
        "ru": "Не удалось распознать IP или подсеть.\nПримеры:\n- 1.2.3.4\n- 10.0.0.0/8\nДиапазоны a-b не поддерживаются.",
        "en": "Could not recognize IP or subnet.\nExamples:\n- 1.2.3.4\n- 10.0.0.0/8\nRanges a-b are not supported.",
    },
    "page.custom_ipset.infobar.info_title": {
        "ru": "Информация",
        "en": "Information",
    },
    "page.custom_ipset.info.entry_exists": {
        "ru": "Запись уже есть:\n{entry}",
        "en": "Entry already exists:\n{entry}",
    },
    "page.custom_ipset.dialog.clear.title": {
        "ru": "Очистить всё",
        "en": "Clear all",
    },
    "page.custom_ipset.dialog.clear.body": {
        "ru": "Удалить все записи?",
        "en": "Delete all entries?",
    },
    "page.custom_ipset.error.open_file": {
        "ru": "Не удалось открыть:\n{error}",
        "en": "Failed to open:\n{error}",
    },
    "page.dns_check.title": {
        "ru": "Проверка DNS подмены",
        "en": "DNS Spoofing Check",
    },
    "page.dns_check.subtitle": {
        "ru": "Проверка резолвинга доменов YouTube и Discord через различные DNS серверы",
        "en": "Check resolution of YouTube and Discord domains via different DNS servers",
    },
    "page.dns_check.card.what_we_check": {
        "ru": "Что проверяем",
        "en": "What we check",
    },
    "page.dns_check.info.blocking": {
        "ru": "Блокирует ли провайдер сайты через DNS подмену",
        "en": "Whether the provider blocks sites via DNS spoofing",
    },
    "page.dns_check.info.servers": {
        "ru": "Какие DNS серверы возвращают корректные адреса",
        "en": "Which DNS servers return correct addresses",
    },
    "page.dns_check.info.recommended": {
        "ru": "Какой DNS сервер рекомендуется использовать",
        "en": "Which DNS server is recommended",
    },
    "page.dns_check.card.testing": {
        "ru": "Тестирование",
        "en": "Testing",
    },
    "page.dns_check.button.start": {
        "ru": "Начать проверку",
        "en": "Start check",
    },
    "page.dns_check.button.quick": {
        "ru": "Быстрая проверка",
        "en": "Quick check",
    },
    "page.dns_check.button.save": {
        "ru": "Сохранить результаты",
        "en": "Save results",
    },
    "page.dns_check.status.ready": {
        "ru": "Готово к проверке",
        "en": "Ready to check",
    },
    "page.dns_check.card.results": {
        "ru": "Результаты",
        "en": "Results",
    },
    "page.dpi_settings.subtitle": {
        "ru": "Параметры обхода блокировок",
        "en": "Bypass configuration",
    },
    "page.dpi_settings.card.launch_method": {
        "ru": "Метод запуска стратегий (режим работы программы)",
        "en": "Strategy launch method (application mode)",
    },
    "page.dpi_settings.launch_method.desc": {
        "ru": "Выберите способ запуска обхода блокировок",
        "en": "Choose how to run bypass strategies",
    },
    "page.dpi_settings.section.z2": {
        "ru": "Zapret 2 (winws2.exe)",
        "en": "Zapret 2 (winws2.exe)",
    },
    "page.dpi_settings.section.z1": {
        "ru": "Zapret 1 (winws.exe)",
        "en": "Zapret 1 (winws.exe)",
    },
    "page.dpi_settings.option.recommended": {
        "ru": "рекомендуется",
        "en": "recommended",
    },
    "page.dpi_settings.method.direct_z2.title": {
        "ru": "Zapret 2",
        "en": "Zapret 2",
    },
    "page.dpi_settings.method.direct_z2.desc": {
        "ru": "Режим со второй версией Zapret (winws2.exe) + готовые пресеты для быстрого запуска. Поддерживает кастомный lua-код чтобы писать свои стратегии.",
        "en": "Mode with Zapret v2 (winws2.exe) and ready presets for quick launch. Supports custom Lua code for your own strategies.",
    },
    "page.dpi_settings.method.orchestra.title": {
        "ru": "Оркестратор v0.9.6 (Beta)",
        "en": "Orchestrator v0.9.6 (Beta)",
    },
    "page.dpi_settings.method.orchestra.desc": {
        "ru": "Автоматическое обучение. Система сама подбирает лучшие стратегии для каждого домена. Запоминает результаты между запусками.",
        "en": "Automatic learning. The system picks the best strategy per domain and remembers results between launches.",
    },
    "page.dpi_settings.method.direct_z1.title": {
        "ru": "Zapret 1",
        "en": "Zapret 1",
    },
    "page.dpi_settings.method.direct_z1.desc": {
        "ru": "Режим первой версии Zapret 1 (winws.exe) + готовые пресеты для быстрого запуска. Не использует Lua код, нет понятия блобов.",
        "en": "Mode with Zapret v1 (winws.exe) and ready presets for quick launch. Does not use Lua and has no blob concept.",
    },
    "page.dpi_settings.discord_restart.title": {
        "ru": "Перезапуск Discord",
        "en": "Restart Discord",
    },
    "page.dpi_settings.discord_restart.desc": {
        "ru": "Автоперезапуск при смене стратегии",
        "en": "Auto-restart on strategy change",
    },
    "page.dpi_settings.section.orchestra_settings": {
        "ru": "Настройки оркестратора",
        "en": "Orchestrator settings",
    },
    "page.dpi_settings.orchestra.strict_detection.title": {
        "ru": "Строгий режим детекции",
        "en": "Strict detection mode",
    },
    "page.dpi_settings.orchestra.strict_detection.desc": {
        "ru": "HTTP 200 + проверка блок-страниц",
        "en": "HTTP 200 + block-page checks",
    },
    "page.dpi_settings.orchestra.debug_file.title": {
        "ru": "Сохранять debug файл",
        "en": "Save debug file",
    },
    "page.dpi_settings.orchestra.debug_file.desc": {
        "ru": "Сырой debug файл для отладки",
        "en": "Raw debug file for troubleshooting",
    },
    "page.dpi_settings.orchestra.auto_restart_discord.title": {
        "ru": "Авторестарт Discord при FAIL",
        "en": "Auto-restart Discord on FAIL",
    },
    "page.dpi_settings.orchestra.auto_restart_discord.desc": {
        "ru": "Перезапуск Discord при неудачном обходе",
        "en": "Restart Discord on failed bypass",
    },
    "page.dpi_settings.orchestra.discord_fails.title": {
        "ru": "Фейлов для рестарта Discord",
        "en": "Fails before Discord restart",
    },
    "page.dpi_settings.orchestra.discord_fails.desc": {
        "ru": "Сколько FAIL подряд для перезапуска Discord",
        "en": "How many consecutive FAILs trigger Discord restart",
    },
    "page.dpi_settings.orchestra.lock_successes.title": {
        "ru": "Успехов для LOCK",
        "en": "Successes for LOCK",
    },
    "page.dpi_settings.orchestra.lock_successes.desc": {
        "ru": "Количество успешных обходов для закрепления стратегии",
        "en": "Number of successful bypasses to lock strategy",
    },
    "page.dpi_settings.orchestra.unlock_fails.title": {
        "ru": "Ошибок для AUTO-UNLOCK",
        "en": "Fails for AUTO-UNLOCK",
    },
    "page.dpi_settings.orchestra.unlock_fails.desc": {
        "ru": "Количество ошибок для автоматической разблокировки стратегии",
        "en": "Number of errors to auto-unlock strategy",
    },
    "page.dpi_settings.card.advanced": {
        "ru": "ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ",
        "en": "ADVANCED SETTINGS",
    },
    "page.dpi_settings.advanced.warning": {
        "ru": "⚠ Изменяйте только если знаете что делаете",
        "en": "⚠ Change only if you know what you are doing",
    },
    "page.dpi_settings.advanced.wssize.title": {
        "ru": "Включить --wssize",
        "en": "Enable --wssize",
    },
    "page.dpi_settings.advanced.wssize.desc": {
        "ru": "Добавляет параметр размера окна TCP",
        "en": "Adds TCP window size parameter",
    },
    "page.dpi_settings.advanced.debug_log.title": {
        "ru": "Включить лог-файл (--debug)",
        "en": "Enable log file (--debug)",
    },
    "page.dpi_settings.advanced.debug_log.desc": {
        "ru": "Записывает логи winws в папку logs",
        "en": "Writes winws logs to the logs folder",
    },
    "page.hostlist.subtitle": {
        "ru": "Управление hostlist и ipset списками для обхода блокировок",
        "en": "Manage hostlist and ipset lists for bypass",
    },
    "page.hostlist.tab.hostlist": {
        "ru": "Hostlist",
        "en": "Hostlist",
    },
    "page.hostlist.tab.ipset": {
        "ru": "IPset",
        "en": "IPset",
    },
    "page.hostlist.tab.domains": {
        "ru": "Мои домены",
        "en": "My domains",
    },
    "page.hostlist.tab.ips": {
        "ru": "Мои IP",
        "en": "My IPs",
    },
    "page.hostlist.tab.exclusions": {
        "ru": "Исключения",
        "en": "Exclusions",
    },
    "page.hostlist.section.manage": {
        "ru": "Управление",
        "en": "Management",
    },
    "page.hostlist.section.actions": {
        "ru": "Действия",
        "en": "Actions",
    },
    "page.hostlist.button.open": {
        "ru": "Открыть",
        "en": "Open",
    },
    "page.hostlist.button.rebuild": {
        "ru": "Перестроить",
        "en": "Rebuild",
    },
    "page.hostlist.button.add": {
        "ru": "Добавить",
        "en": "Add",
    },
    "page.hostlist.button.open_file": {
        "ru": "Открыть файл",
        "en": "Open file",
    },
    "page.hostlist.button.reset_file": {
        "ru": "Сбросить файл",
        "en": "Reset file",
    },
    "page.hostlist.button.clear_all": {
        "ru": "Очистить всё",
        "en": "Clear all",
    },
    "page.hostlist.confirm.reset": {
        "ru": "Подтвердить сброс",
        "en": "Confirm reset",
    },
    "page.hostlist.confirm.clear": {
        "ru": "Подтвердить очистку",
        "en": "Confirm clear",
    },
    "page.hostlist.dialog.clear.title": {
        "ru": "Очистить всё",
        "en": "Clear all",
    },
    "page.hostlist.hostlist.desc": {
        "ru": "Используется для обхода блокировок по доменам.",
        "en": "Used to bypass domain-based blocks.",
    },
    "page.hostlist.hostlist.action.open_folder.title": {
        "ru": "Открыть папку хостлистов",
        "en": "Open hostlists folder",
    },
    "page.hostlist.hostlist.action.rebuild.title": {
        "ru": "Перестроить хостлисты",
        "en": "Rebuild hostlists",
    },
    "page.hostlist.hostlist.action.rebuild.subtitle": {
        "ru": "Обновляет списки из встроенной базы",
        "en": "Updates lists from built-in base",
    },
    "page.hostlist.ipset.desc": {
        "ru": "Используется для обхода блокировок по IP-адресам и подсетям.",
        "en": "Used to bypass blocks by IP addresses and subnets.",
    },
    "page.hostlist.ipset.action.open_folder.title": {
        "ru": "Открыть папку IP-сетов",
        "en": "Open IP sets folder",
    },
    "page.hostlist.info.loading": {
        "ru": "Загрузка информации...",
        "en": "Loading information...",
    },
    "page.hostlist.info.folder_not_found": {
        "ru": "Папка листов не найдена",
        "en": "Lists folder not found",
    },
    "page.hostlist.info.hostlist.summary": {
        "ru": "📁 Папка: {folder}\n📄 Файлов: {files_count}\n📝 Примерно строк: {lines_count}",
        "en": "📁 Folder: {folder}\n📄 Files: {files_count}\n📝 Approx. lines: {lines_count}",
    },
    "page.hostlist.info.ipset.summary": {
        "ru": "📁 Папка: {folder}\n📄 IP-файлов: {files_count}\n🌐 Примерно IP/подсетей: {lines_count}",
        "en": "📁 Folder: {folder}\n📄 IP files: {files_count}\n🌐 Approx. IPs/subnets: {lines_count}",
    },
    "page.hostlist.info.error": {
        "ru": "Ошибка загрузки информации: {error}",
        "en": "Failed to load info: {error}",
    },
    "page.hostlist.infobar.done": {
        "ru": "Готово",
        "en": "Done",
    },
    "page.hostlist.infobar.hostlists_rebuilt": {
        "ru": "Хостлисты обновлены",
        "en": "Hostlists updated",
    },
    "page.hostlist.infobar.info": {
        "ru": "Информация",
        "en": "Information",
    },
    "page.hostlist.infobar.added": {
        "ru": "Добавлено",
        "en": "Added",
    },
    "page.hostlist.error.open_folder": {
        "ru": "Не удалось открыть папку:\n{error}",
        "en": "Failed to open folder:\n{error}",
    },
    "page.hostlist.error.rebuild": {
        "ru": "Не удалось перестроить:\n{error}",
        "en": "Failed to rebuild:\n{error}",
    },
    "page.hostlist.error.open_file": {
        "ru": "Не удалось открыть:\n{error}",
        "en": "Failed to open:\n{error}",
    },
    "page.hostlist.error.open_final_file": {
        "ru": "Не удалось открыть итоговый файл: {error}",
        "en": "Failed to open final file: {error}",
    },
    "page.hostlist.status.error": {
        "ru": "❌ Ошибка: {error}",
        "en": "❌ Error: {error}",
    },
    "page.hostlist.status.saved_suffix": {
        "ru": " • ✅ Сохранено",
        "en": " • ✅ Saved",
    },
    "page.hostlist.status.reset_suffix": {
        "ru": " • ✅ Сброшено",
        "en": " • ✅ Reset",
    },
    "page.hostlist.domains.desc": {
        "ru": "Редактируется файл other.user.txt (только ваши домены). Системная база хранится в other.base.txt, общий other.txt собирается автоматически. URL автоматически преобразуются в домены. Изменения сохраняются автоматически. Поддерживается Ctrl+Z.",
        "en": "Edit other.user.txt (your domains only). System base is kept in other.base.txt, and combined other.txt is rebuilt automatically. URLs are converted to domains automatically. Changes are saved automatically. Ctrl+Z is supported.",
    },
    "page.hostlist.domains.section.add": {
        "ru": "Добавить домен",
        "en": "Add domain",
    },
    "page.hostlist.domains.input.placeholder": {
        "ru": "Введите домен или URL (например: example.com)",
        "en": "Enter domain or URL (for example: example.com)",
    },
    "page.hostlist.domains.tooltip.open_file": {
        "ru": "Сохраняет изменения и открывает other.user.txt в проводнике",
        "en": "Saves changes and opens other.user.txt in Explorer",
    },
    "page.hostlist.domains.tooltip.reset_file": {
        "ru": "Очищает other.user.txt и пересобирает other.txt из системной базы",
        "en": "Clears other.user.txt and rebuilds other.txt from system base",
    },
    "page.hostlist.domains.tooltip.clear_all": {
        "ru": "Удаляет только пользовательские домены",
        "en": "Removes custom domains only",
    },
    "page.hostlist.domains.section.editor": {
        "ru": "other.user.txt (редактор)",
        "en": "other.user.txt (editor)",
    },
    "page.hostlist.domains.editor.placeholder": {
        "ru": "Домены по одному на строку:\nexample.com\nsubdomain.site.org\n\nКомментарии начинаются с #",
        "en": "One domain per line:\nexample.com\nsubdomain.site.org\n\nComments start with #",
    },
    "page.hostlist.hint.autosave": {
        "ru": "💡 Изменения сохраняются автоматически через 500мс",
        "en": "💡 Changes are saved automatically after 500 ms",
    },
    "page.hostlist.status.domains_count": {
        "ru": "📊 Доменов: {count}",
        "en": "📊 Domains: {count}",
    },
    "page.hostlist.domains.error.invalid_domain": {
        "ru": "Не удалось распознать домен:\n{value}\n\nВведите корректный домен (например: example.com)",
        "en": "Could not recognize domain:\n{value}\n\nEnter a valid domain (for example: example.com)",
    },
    "page.hostlist.domains.info.already_added": {
        "ru": "Домен уже добавлен:\n{domain}",
        "en": "Domain already added:\n{domain}",
    },
    "page.hostlist.domains.error.reset_failed": {
        "ru": "Не удалось сбросить my hostlist",
        "en": "Failed to reset my hostlist",
    },
    "page.hostlist.domains.error.reset_exception": {
        "ru": "Не удалось сбросить:\n{error}",
        "en": "Failed to reset:\n{error}",
    },
    "page.hostlist.ips.desc": {
        "ru": "Добавляйте свои IP/подсети в ipset-all.user.txt.\n• Одиночный IP: 1.2.3.4\n• Подсеть: 10.0.0.0/8\nДиапазоны (a-b) не поддерживаются. Изменения сохраняются автоматически.\nСистемная база хранится в ipset-all.base.txt и автоматически объединяется в ipset-all.txt.",
        "en": "Add your own IPs/subnets to ipset-all.user.txt.\n• Single IP: 1.2.3.4\n• Subnet: 10.0.0.0/8\nRanges (a-b) are not supported. Changes are saved automatically.\nSystem base is stored in ipset-all.base.txt and automatically merged into ipset-all.txt.",
    },
    "page.hostlist.ips.section.add": {
        "ru": "Добавить IP/подсеть",
        "en": "Add IP/subnet",
    },
    "page.hostlist.ips.input.placeholder": {
        "ru": "Например: 1.2.3.4 или 10.0.0.0/8",
        "en": "For example: 1.2.3.4 or 10.0.0.0/8",
    },
    "page.hostlist.ips.section.editor": {
        "ru": "ipset-all.user.txt (редактор)",
        "en": "ipset-all.user.txt (editor)",
    },
    "page.hostlist.ips.editor.placeholder": {
        "ru": "IP/подсети по одному на строку:\n192.168.0.1\n10.0.0.0/8\n\nКомментарии начинаются с #",
        "en": "IPs/subnets one per line:\n192.168.0.1\n10.0.0.0/8\n\nComments start with #",
    },
    "page.hostlist.ips.error.invalid_format": {
        "ru": "❌ Неверный формат: {items}",
        "en": "❌ Invalid format: {items}",
    },
    "page.hostlist.status.entries_count": {
        "ru": "📊 Записей: {total} (база: {base}, пользовательские: {user})",
        "en": "📊 Entries: {total} (base: {base}, custom: {user})",
    },
    "page.hostlist.ips.error.invalid_ip": {
        "ru": "Не удалось распознать IP или подсеть.\nПримеры: 1.2.3.4 или 10.0.0.0/8",
        "en": "Could not recognize IP or subnet.\nExamples: 1.2.3.4 or 10.0.0.0/8",
    },
    "page.hostlist.ips.info.already_exists": {
        "ru": "Запись уже есть:\n{entry}",
        "en": "Entry already exists:\n{entry}",
    },
    "page.hostlist.ips.info.all_entries_exist": {
        "ru": "Все записи уже есть ({count})",
        "en": "All entries already exist ({count})",
    },
    "page.hostlist.ips.info.added_with_skipped": {
        "ru": "Добавлено IP-исключений. Пропущено уже существующих: {count}",
        "en": "IP exclusions added. Skipped already existing: {count}",
    },
    "page.hostlist.ips.dialog.clear.body": {
        "ru": "Удалить все записи?",
        "en": "Delete all entries?",
    },
    "page.hostlist.exclusions.desc": {
        "ru": "Здесь два типа исключений:\n• Домены: netrogat.user.txt -> netrogat.txt (--hostlist-exclude)\n• IP/подсети: ipset-ru.user.txt -> ipset-ru.txt (--ipset-exclude)",
        "en": "Two exclusion types here:\n• Domains: netrogat.user.txt -> netrogat.txt (--hostlist-exclude)\n• IP/subnets: ipset-ru.user.txt -> ipset-ru.txt (--ipset-exclude)",
    },
    "page.hostlist.exclusions.section.add_domain": {
        "ru": "Добавить домен",
        "en": "Add domain",
    },
    "page.hostlist.exclusions.input.domain.placeholder": {
        "ru": "Например: example.com, site.com или через пробел",
        "en": "For example: example.com, site.com or space-separated",
    },
    "page.hostlist.exclusions.button.add_missing": {
        "ru": "Добавить недостающие",
        "en": "Add missing",
    },
    "page.hostlist.exclusions.button.open_final": {
        "ru": "Открыть итоговый",
        "en": "Open final",
    },
    "page.hostlist.exclusions.section.editor_domain": {
        "ru": "netrogat.user.txt (редактор)",
        "en": "netrogat.user.txt (editor)",
    },
    "page.hostlist.exclusions.editor.domain.placeholder": {
        "ru": "Домены по одному на строку:\ngosuslugi.ru\nvk.com\n\nКомментарии начинаются с #",
        "en": "One domain per line:\ngosuslugi.ru\nvk.com\n\nComments start with #",
    },
    "page.hostlist.status.domains_full_count": {
        "ru": "📊 Доменов: {total} (база: {base}, пользовательские: {user})",
        "en": "📊 Domains: {total} (base: {base}, custom: {user})",
    },
    "page.hostlist.exclusions.error.invalid_domain": {
        "ru": "Не удалось распознать домен.",
        "en": "Could not recognize domain.",
    },
    "page.hostlist.exclusions.error.invalid_domains": {
        "ru": "Не удалось распознать домены.",
        "en": "Could not recognize domains.",
    },
    "page.hostlist.exclusions.info.domain_exists": {
        "ru": "Домен уже есть: {domain}",
        "en": "Domain already exists: {domain}",
    },
    "page.hostlist.exclusions.info.all_domains_exist": {
        "ru": "Все домены уже есть ({count})",
        "en": "All domains already exist ({count})",
    },
    "page.hostlist.exclusions.info.added_with_skipped": {
        "ru": "Добавлено доменов. Пропущено уже существующих: {count}",
        "en": "Domains added. Skipped already existing: {count}",
    },
    "page.hostlist.exclusions.dialog.clear.body": {
        "ru": "Удалить все домены?",
        "en": "Delete all domains?",
    },
    "page.hostlist.exclusions.info.defaults_already_present": {
        "ru": "Системная база уже содержит все домены по умолчанию.",
        "en": "System base already contains all default domains.",
    },
    "page.hostlist.exclusions.info.defaults_restored": {
        "ru": "Восстановлено доменов в системной базе: {count}",
        "en": "Domains restored in system base: {count}",
    },
    "page.hostlist.exclusions.ipru.title": {
        "ru": "IP-исключения (--ipset-exclude)",
        "en": "IP exclusions (--ipset-exclude)",
    },
    "page.hostlist.exclusions.ipru.desc": {
        "ru": "Редактируйте только ipset-ru.user.txt. Системная база хранится в ipset-ru.base.txt и автоматически объединяется в ipset-ru.txt.",
        "en": "Edit only ipset-ru.user.txt. System base is stored in ipset-ru.base.txt and automatically merged into ipset-ru.txt.",
    },
    "page.hostlist.exclusions.ipru.section.add": {
        "ru": "Добавить IP/подсеть в исключения",
        "en": "Add IP/subnet to exclusions",
    },
    "page.hostlist.exclusions.ipru.section.actions": {
        "ru": "Действия IP-исключений",
        "en": "IP exclusion actions",
    },
    "page.hostlist.exclusions.ipru.section.editor": {
        "ru": "ipset-ru.user.txt (редактор)",
        "en": "ipset-ru.user.txt (editor)",
    },
    "page.hostlist.exclusions.ipru.editor.placeholder": {
        "ru": "IP/подсети по одному на строку:\n31.13.64.0/18\n77.88.0.0/18\n\nКомментарии начинаются с #",
        "en": "IPs/subnets one per line:\n31.13.64.0/18\n77.88.0.0/18\n\nComments start with #",
    },
    "page.hostlist.status.ipru_count": {
        "ru": "📊 IP-исключений: {total} (база: {base}, пользовательские: {user})",
        "en": "📊 IP exclusions: {total} (base: {base}, custom: {user})",
    },
    "page.hostlist.exclusions.ipru.dialog.clear.body": {
        "ru": "Удалить все IP-исключения?",
        "en": "Delete all IP exclusions?",
    },
    "page.hosts.subtitle": {
        "ru": "Управление разблокировкой сервисов через hosts файл",
        "en": "Manage service unblocking via hosts file",
    },
    "page.hosts.section.additional": {
        "ru": "Дополнительно",
        "en": "Additional",
    },
    "page.hosts.section.services": {
        "ru": "Сервисы",
        "en": "Services",
    },
    "page.hosts.button.restore_access": {
        "ru": " Восстановить права доступа",
        "en": " Restore Access Permissions",
    },
    "page.hosts.button.restoring_access": {
        "ru": " Восстановление...",
        "en": " Restoring...",
    },
    "page.hosts.button.clear": {
        "ru": " Очистить",
        "en": " Clear",
    },
    "page.hosts.button.open": {
        "ru": " Открыть",
        "en": " Open",
    },
    "page.hosts.status.active_domains": {
        "ru": "Активно {count} доменов",
        "en": "{count} active domains",
    },
    "page.hosts.status.none_active": {
        "ru": "Нет активных",
        "en": "No active domains",
    },
    "page.hosts.error.no_access.long": {
        "ru": "Нет доступа для изменения файла hosts.\nЕсли файл редактируется вручную, возможно защитник/антивирус блокирует запись.\nПуть: {path}",
        "en": "No access to modify the hosts file.\nIf the file is edited manually, defender/antivirus may block write access.\nPath: {path}",
    },
    "page.hosts.error.no_access.short": {
        "ru": "Нет доступа для изменения файла hosts. Скорее всего защитник/антивирус заблокировал запись.\nПуть: {path}",
        "en": "No access to modify the hosts file. Most likely defender/antivirus blocked writing.\nPath: {path}",
    },
    "page.hosts.error.read_hosts": {
        "ru": "Ошибка чтения hosts: {error}",
        "en": "Hosts read error: {error}",
    },
    "page.hosts.error.generic": {
        "ru": "Ошибка: {error}",
        "en": "Error: {error}",
    },
    "page.hosts.error.operation_with_path": {
        "ru": "{message}\nПуть: {path}",
        "en": "{message}\nPath: {path}",
    },
    "page.hosts.ipv6.infobar.title": {
        "ru": "IPv6",
        "en": "IPv6",
    },
    "page.hosts.ipv6.infobar.content": {
        "ru": "У провайдера обнаружен IPv6. В hosts.ini добавлены IPv6 разделы DNS-провайдеров.",
        "en": "IPv6 was detected on your provider. IPv6 DNS-provider sections were added to hosts.ini.",
    },
    "page.hosts.permissions.restore.success.title": {
        "ru": "Успех",
        "en": "Success",
    },
    "page.hosts.permissions.restore.success.content": {
        "ru": "Права доступа к файлу hosts успешно восстановлены!",
        "en": "Hosts file access permissions restored successfully!",
    },
    "page.hosts.permissions.restore.fail.title": {
        "ru": "Ошибка",
        "en": "Error",
    },
    "page.hosts.permissions.restore.fail.content": {
        "ru": "Не удалось восстановить права:\n{message}\n\nПопробуйте временно отключить защиту файла hosts в настройках антивируса (Kaspersky, Dr.Web и т.д.)",
        "en": "Failed to restore permissions:\n{message}\n\nTry temporarily disabling hosts file protection in antivirus settings (Kaspersky, Dr.Web, etc.).",
    },
    "page.hosts.info.note": {
        "ru": "Некоторые сервисы (ChatGPT, Spotify и др.) сами блокируют доступ из России — это не блокировка РКН. Решается не через Zapret, а через проксирование: домены направляются через отдельный прокси-сервер в файле hosts.",
        "en": "Some services (ChatGPT, Spotify, etc.) block access from Russia themselves - this is not a Roskomnadzor block. It is solved not through Zapret but via proxying: domains are routed through a dedicated proxy server in hosts.",
    },
    "page.hosts.warning.browser_restart": {
        "ru": "После добавления или удаления доменов необходимо перезапустить браузер, чтобы изменения вступили в силу.",
        "en": "After adding or removing domains, restart your browser for changes to take effect.",
    },
    "page.hosts.dialog.clear.title": {
        "ru": "Очистить hosts?",
        "en": "Clear hosts?",
    },
    "page.hosts.dialog.clear.body": {
        "ru": "Это полностью сбросит файл hosts к стандартному содержимому Windows и удалит ВСЕ записи, включая добавленные вручную.",
        "en": "This will fully reset the hosts file to default Windows content and remove ALL entries, including manually added ones.",
    },
    "page.hosts.open.error.title": {
        "ru": "Ошибка",
        "en": "Error",
    },
    "page.hosts.open.error.content": {
        "ru": "Не удалось открыть: {error}",
        "en": "Failed to open: {error}",
    },
    "page.hosts.services.off": {
        "ru": "Откл.",
        "en": "Off",
    },
    "page.hosts.group.direct": {
        "ru": "Напрямую из hosts",
        "en": "Direct from hosts",
    },
    "page.hosts.group.ai": {
        "ru": "ИИ",
        "en": "AI",
    },
    "page.hosts.group.other": {
        "ru": "Остальные",
        "en": "Other",
    },
    "page.hosts.adobe.description": {
        "ru": "⚠️ Блокирует серверы проверки активации Adobe. Включите, если у вас установлена пиратская версия.",
        "en": "⚠️ Blocks Adobe activation-check servers. Enable this if you use a pirated version.",
    },
    "page.hosts.adobe.title": {
        "ru": "Блокировка Adobe",
        "en": "Adobe Blocking",
    },
    "page.logs.subtitle": {
        "ru": "Просмотр логов приложения в реальном времени",
        "en": "Real-time application logs",
    },
    "page.logs.tab.logs": {
        "ru": "ЛОГИ",
        "en": "LOGS",
    },
    "page.logs.tab.send": {
        "ru": "ПОДДЕРЖКА",
        "en": "SUPPORT",
    },
    "page.logs.card.controls": {
        "ru": "Управление логами",
        "en": "Log Controls",
    },
    "page.logs.card.content": {
        "ru": "Содержимое",
        "en": "Content",
    },
    "page.logs.tooltip.refresh": {
        "ru": "Обновить список файлов",
        "en": "Refresh file list",
    },
    "page.logs.button.copy": {
        "ru": "Копировать",
        "en": "Copy",
    },
    "page.logs.button.clear": {
        "ru": "Очистить",
        "en": "Clear",
    },
    "page.logs.button.folder": {
        "ru": "Папка",
        "en": "Folder",
    },
    "page.logs.errors.title": {
        "ru": "Ошибки и предупреждения",
        "en": "Errors and Warnings",
    },
    "page.logs.errors.count": {
        "ru": "Ошибок: {count}",
        "en": "Errors: {count}",
    },
    "page.logs.stats.loading": {
        "ru": "📊 Загрузка...",
        "en": "📊 Loading...",
    },
    "page.logs.stats.template": {
        "ru": "📊 Логи: {logs} (макс {max_logs}) | 🔧 Debug: {debug} (макс {max_debug}) | 💾 Размер: {size:.2f} MB",
        "en": "📊 Logs: {logs} (max {max_logs}) | 🔧 Debug: {debug} (max {max_debug}) | 💾 Size: {size:.2f} MB",
    },
    "page.logs.winws.title_template": {
        "ru": "Вывод {exe_name}",
        "en": "{exe_name} Output",
    },
    "page.logs.winws.status.not_running": {
        "ru": "Процесс не запущен",
        "en": "Process is not running",
    },
    "page.logs.winws.status.ended_template": {
        "ru": "Процесс завершён (код: {code})",
        "en": "Process ended (code: {code})",
    },
    "page.logs.winws.status.ended_error_template": {
        "ru": "Процесс завершён с ошибкой (код: {code})",
        "en": "Process ended with error (code: {code})",
    },
    "page.logs.send.card.title": {
        "ru": "Поддержка через GitHub Discussions",
        "en": "Support via GitHub Discussions",
    },
    "page.logs.send.orchestra.active": {
        "ru": "В режиме оркестратора проверьте основной лог и файл orchestra_*.log",
        "en": "In orchestrator mode, check both the main log and the orchestra_*.log file",
    },
    "page.logs.send.desc": {
        "ru": "Нажмите кнопку, чтобы собрать ZIP из свежих логов, скопировать шаблон обращения и открыть GitHub Discussions.",
        "en": "Press the button to build a ZIP with fresh logs, copy a report template, and open GitHub Discussions.",
    },
    "page.logs.send.info": {
        "ru": "Будет создан архив в папке logs/support_bundles. Шаблон обращения автоматически попадёт в буфер обмена.",
        "en": "An archive will be created in logs/support_bundles. The report template will be copied to the clipboard automatically.",
    },
    "page.logs.send.button.send": {
        "ru": "Подготовить обращение",
        "en": "Prepare report",
    },
    "page.netrogat.title": {
        "ru": "Исключения",
        "en": "Exclusions",
    },
    "page.netrogat.subtitle": {
        "ru": "Управление пользовательским списком netrogat.user.txt. Итоговый netrogat.txt собирается автоматически.",
        "en": "Manage custom netrogat.user.txt list. Final netrogat.txt is built automatically.",
    },
    "page.netrogat.description": {
        "ru": "Редактируйте только netrogat.user.txt.\nСистемная база хранится в netrogat.base.txt и автоматически объединяется в netrogat.txt.",
        "en": "Edit only netrogat.user.txt.\nSystem base is stored in netrogat.base.txt and automatically merged into netrogat.txt.",
    },
    "page.netrogat.section.add": {
        "ru": "Добавить домен",
        "en": "Add domain",
    },
    "page.netrogat.input.placeholder": {
        "ru": "Например: example.com, site.com или через пробел",
        "en": "For example: example.com, site.com or space-separated",
    },
    "page.netrogat.button.add": {
        "ru": "Добавить",
        "en": "Add",
    },
    "page.netrogat.section.actions": {
        "ru": "Действия",
        "en": "Actions",
    },
    "page.netrogat.button.add_missing": {
        "ru": "Добавить недостающие",
        "en": "Add missing",
    },
    "page.netrogat.button.open_file": {
        "ru": "Открыть файл",
        "en": "Open file",
    },
    "page.netrogat.button.open_final": {
        "ru": "Открыть итоговый",
        "en": "Open final",
    },
    "page.netrogat.button.clear_all": {
        "ru": "Очистить всё",
        "en": "Clear all",
    },
    "page.netrogat.section.editor": {
        "ru": "netrogat.user.txt (редактор)",
        "en": "netrogat.user.txt (editor)",
    },
    "page.netrogat.editor.placeholder": {
        "ru": "Домены по одному на строку:\ngosuslugi.ru\nvk.com\n\nКомментарии начинаются с #",
        "en": "Domains one per line:\ngosuslugi.ru\nvk.com\n\nComments start with #",
    },
    "page.netrogat.hint.autosave": {
        "ru": "💡 Изменения сохраняются автоматически через 500мс",
        "en": "💡 Changes are saved automatically after 500 ms",
    },
    "page.netrogat.status.summary": {
        "ru": "📊 Доменов: {total} (база: {base}, пользовательские: {user})",
        "en": "📊 Domains: {total} (base: {base}, custom: {user})",
    },
    "page.netrogat.status.saved_suffix": {
        "ru": " • ✅ Сохранено",
        "en": " • ✅ Saved",
    },
    "page.netrogat.error.parse_domain": {
        "ru": "Не удалось распознать домен.",
        "en": "Could not recognize domain.",
    },
    "page.netrogat.error.parse_domains": {
        "ru": "Не удалось распознать домены.",
        "en": "Could not recognize domains.",
    },
    "page.netrogat.infobar.info_title": {
        "ru": "Информация",
        "en": "Information",
    },
    "page.netrogat.info.already_exists_one": {
        "ru": "Домен уже есть: {domain}",
        "en": "Domain already exists: {domain}",
    },
    "page.netrogat.info.already_exists_many": {
        "ru": "Все домены уже есть ({count})",
        "en": "All domains already exist ({count})",
    },
    "page.netrogat.infobar.added_title": {
        "ru": "Добавлено",
        "en": "Added",
    },
    "page.netrogat.info.added_with_skipped": {
        "ru": "Добавлено доменов. Пропущено уже существующих: {count}",
        "en": "Domains added. Skipped already existing: {count}",
    },
    "page.netrogat.dialog.clear.title": {
        "ru": "Очистить всё",
        "en": "Clear all",
    },
    "page.netrogat.dialog.clear.body": {
        "ru": "Удалить все домены?",
        "en": "Delete all domains?",
    },
    "page.netrogat.error.open_file": {
        "ru": "Не удалось открыть: {error}",
        "en": "Failed to open: {error}",
    },
    "page.netrogat.error.open_final_file": {
        "ru": "Не удалось открыть итоговый файл: {error}",
        "en": "Failed to open final file: {error}",
    },
    "page.netrogat.infobar.done_title": {
        "ru": "Готово",
        "en": "Done",
    },
    "page.netrogat.info.defaults_already_present": {
        "ru": "Системная база уже содержит все домены по умолчанию.",
        "en": "System base already contains all default domains.",
    },
    "page.netrogat.info.defaults_restored": {
        "ru": "Восстановлено доменов в системной базе: {count}",
        "en": "Restored domains in system base: {count}",
    },
    "page.network.subtitle": {
        "ru": "Настройки DNS и доступа к сервисам",
        "en": "DNS settings and service access",
    },
    "page.network.section.dns_servers": {
        "ru": "DNS Серверы",
        "en": "DNS Servers",
    },
    "page.network.section.adapters": {
        "ru": "Сетевые адаптеры",
        "en": "Network Adapters",
    },
    "page.network.section.tools": {
        "ru": "Утилиты",
        "en": "Utilities",
    },
    "page.network.section.force_dns": {
        "ru": "DNS",
        "en": "DNS",
    },
    "page.network.loading": {
        "ru": "⏳ Загрузка...",
        "en": "⏳ Loading...",
    },
    "page.network.custom.label": {
        "ru": "Свой:",
        "en": "Custom:",
    },
    "page.network.custom.apply": {
        "ru": "OK",
        "en": "OK",
    },
    "page.network.dns.auto": {
        "ru": "Автоматически (DHCP)",
        "en": "Automatic (DHCP)",
    },
    "page.network.button.test": {
        "ru": "Тест соединения",
        "en": "Connection Test",
    },
    "page.network.button.test.in_progress": {
        "ru": "Проверка...",
        "en": "Checking...",
    },
    "page.network.button.flush_dns_cache": {
        "ru": "Сбросить DNS кэш",
        "en": "Flush DNS Cache",
    },
    "page.network.button.flush_dns_cache.confirm": {
        "ru": "Сбросить?",
        "en": "Flush?",
    },
    "page.network.force_dns.card.title": {
        "ru": "Принудительно прописывает Google DNS + OpenDNS для обхода блокировок",
        "en": "Force-sets Google DNS + OpenDNS to bypass blocking",
    },
    "page.network.force_dns.toggle.title": {
        "ru": "Принудительный DNS",
        "en": "Forced DNS",
    },
    "page.network.force_dns.toggle.description": {
        "ru": "Устанавливает Google DNS + OpenDNS на активные адаптеры",
        "en": "Sets Google DNS + OpenDNS on active adapters",
    },
    "page.network.force_dns.reset.button": {
        "ru": "Сбросить DNS на DHCP",
        "en": "Reset DNS to DHCP",
    },
    "page.network.force_dns.reset.confirm": {
        "ru": "Отключить Force DNS и сбросить DNS на DHCP для всех адаптеров?",
        "en": "Disable Force DNS and reset DNS to DHCP for all adapters?",
    },
    "page.network.force_dns.status.enabled": {
        "ru": "Принудительный DNS включен",
        "en": "Forced DNS is enabled",
    },
    "page.network.force_dns.status.disabled": {
        "ru": "Принудительный DNS отключен",
        "en": "Forced DNS is disabled",
    },
    "page.network.force_dns.status.details.adapters_applied": {
        "ru": "{ok_count}/{total} адаптеров",
        "en": "{ok_count}/{total} adapters",
    },
    "page.network.force_dns.status.details.enable_failed": {
        "ru": "Не удалось включить",
        "en": "Failed to enable",
    },
    "page.network.force_dns.status.details.dns_saved": {
        "ru": "Текущий DNS сохранен",
        "en": "Current DNS preserved",
    },
    "page.network.force_dns.status.details.disable_failed": {
        "ru": "Не удалось отключить",
        "en": "Failed to disable",
    },
    "page.network.force_dns.status.details.apply_error": {
        "ru": "Ошибка применения",
        "en": "Apply error",
    },
    "page.network.force_dns.status.details.dhcp_reset": {
        "ru": "DNS сброшен на DHCP",
        "en": "DNS reset to DHCP",
    },
    "page.network.force_dns.status.details.dhcp_not_applied": {
        "ru": "Force DNS отключен, DHCP не применён",
        "en": "Force DNS disabled, DHCP not applied",
    },
    "page.network.error.title": {
        "ru": "Ошибка",
        "en": "Error",
    },
    "page.network.error.flush_cache_failed": {
        "ru": "Не удалось очистить кэш: {error}",
        "en": "Failed to flush cache: {error}",
    },
    "page.network.error.reset_dhcp_failed": {
        "ru": "Не удалось сбросить DNS: {error}",
        "en": "Failed to reset DNS: {error}",
    },
    "page.network.info.title": {
        "ru": "DNS",
        "en": "DNS",
    },
    "page.network.info.dhcp_reset_all": {
        "ru": "DNS сброшен на DHCP для всех адаптеров",
        "en": "DNS reset to DHCP for all adapters",
    },
    "page.network.test.host.google_dns": {
        "ru": "Google DNS",
        "en": "Google DNS",
    },
    "page.network.test.host.cloudflare_dns": {
        "ru": "Cloudflare DNS",
        "en": "Cloudflare DNS",
    },
    "page.network.test.infobar.title": {
        "ru": "Тест соединения",
        "en": "Connection Test",
    },
    "page.network.test.infobar.all_ok": {
        "ru": "Все проверки пройдены:\n\n{report}",
        "en": "All checks passed:\n\n{report}",
    },
    "page.network.test.infobar.partial": {
        "ru": "Некоторые проверки не пройдены:\n\n{report}",
        "en": "Some checks failed:\n\n{report}",
    },
    "page.network.isp_dns.infobar.title": {
        "ru": "DNS от провайдера",
        "en": "ISP DNS detected",
    },
    "page.network.isp_dns.infobar.content": {
        "ru": "У вас установлен DNS от провайдера (получен автоматически через DHCP). Провайдерский DNS может подменять ответы и мешать обходу блокировок.\n\nРекомендуем установить публичный DNS (Google + OpenDNS) для стабильной работы.",
        "en": "Your DNS is set automatically from your ISP (via DHCP). ISP DNS may poison responses and interfere with DPI bypass.\n\nWe recommend setting public DNS (Google + OpenDNS) for stable operation.",
    },
    "page.network.isp_dns.infobar.action": {
        "ru": "Установить рекомендуемый DNS",
        "en": "Set recommended DNS",
    },
    "page.network.isp_dns.infobar.dismiss": {
        "ru": "Нет, спасибо",
        "en": "No, thanks",
    },
    "page.network.dns.doh_supported": {
        "ru": "DoH",
        "en": "DoH",
    },
    "page.orchestra.subtitle": {
        "ru": "Автоматическое обучение стратегий DPI bypass. Система находит лучшую стратегию для каждого домена (TCP: TLS/HTTP, UDP: QUIC/Discord Voice/STUN).\nЧтобы начать обучение зайдите на сайт и через несколько секунд обновите вкладку. Продолжайте это пока стратегия не будет помечена как LOCKED",
        "en": "Automatic DPI bypass strategy learning. The system finds the best strategy per domain (TCP: TLS/HTTP, UDP: QUIC/Discord Voice/STUN).\nOpen the site and refresh after a few seconds until strategy becomes LOCKED.",
    },
    "page.orchestra.status.not_started": {
        "ru": "Не запущен",
        "en": "Not started",
    },
    "page.orchestra.status.modes": {
        "ru": "• IDLE - ожидание соединений\n• LEARNING - перебирает стратегии\n• RUNNING - работает на лучших стратегиях\n• UNLOCKED - переобучение (RST блокировка)",
        "en": "• IDLE - waiting for connections\n• LEARNING - iterating strategies\n• RUNNING - using best strategies\n• UNLOCKED - relearning (RST block)",
    },
    "page.orchestra.log.placeholder": {
        "ru": "Логи обучения будут отображаться здесь...",
        "en": "Training logs will be shown here...",
    },
    "page.orchestra.filter.label": {
        "ru": "Фильтр:",
        "en": "Filter:",
    },
    "page.orchestra.filter.domain.placeholder": {
        "ru": "Домен (например: youtube.com)",
        "en": "Domain (for example: youtube.com)",
    },
    "page.orchestra.filter.protocol.all": {
        "ru": "Все",
        "en": "All",
    },
    "page.orchestra.filter.protocol.tls": {
        "ru": "TLS",
        "en": "TLS",
    },
    "page.orchestra.filter.protocol.http": {
        "ru": "HTTP",
        "en": "HTTP",
    },
    "page.orchestra.filter.protocol.udp": {
        "ru": "UDP",
        "en": "UDP",
    },
    "page.orchestra.filter.protocol.success": {
        "ru": "SUCCESS",
        "en": "SUCCESS",
    },
    "page.orchestra.filter.protocol.fail": {
        "ru": "FAIL",
        "en": "FAIL",
    },
    "page.orchestra.filter.clear.tooltip": {
        "ru": "Сбросить фильтр",
        "en": "Reset filter",
    },
    "page.orchestra.button.clear_log": {
        "ru": "Очистить лог",
        "en": "Clear log",
    },
    "page.orchestra.button.clear_learning": {
        "ru": "Сбросить обучение",
        "en": "Reset learning",
    },
    "page.orchestra.button.clear_learning.pending": {
        "ru": "Это всё сотрёт!",
        "en": "This will erase all!",
    },
    "page.orchestra.button.clear_learning.done": {
        "ru": "✓ Сброшено",
        "en": "✓ Reset",
    },
    "page.orchestra.log_history.title": {
        "ru": "История логов (макс. {max_logs})",
        "en": "Log history (max {max_logs})",
    },
    "page.orchestra.log_history.desc": {
        "ru": "Каждый запуск оркестратора создаёт новый лог с уникальным ID. Старые логи автоматически удаляются.",
        "en": "Each orchestrator launch creates a new log with a unique ID. Old logs are removed automatically.",
    },
    "page.orchestra.button.view_log": {
        "ru": "Просмотреть",
        "en": "View",
    },
    "page.orchestra.button.delete_log": {
        "ru": "Удалить",
        "en": "Delete",
    },
    "page.orchestra.button.clear_all_logs": {
        "ru": "Очистить все",
        "en": "Clear all",
    },
    "page.orchestra.status.running": {
        "ru": "✅ RUNNING - работает на лучших стратегиях",
        "en": "✅ RUNNING - using best strategies",
    },
    "page.orchestra.status.learning": {
        "ru": "🔄 LEARNING - перебирает стратегии",
        "en": "🔄 LEARNING - iterating strategies",
    },
    "page.orchestra.status.unlocked": {
        "ru": "🔓 UNLOCKED - переобучение (RST блокировка)",
        "en": "🔓 UNLOCKED - relearning (RST block)",
    },
    "page.orchestra.status.idle": {
        "ru": "⏸ IDLE - ожидание соединений",
        "en": "⏸ IDLE - waiting for connections",
    },
    "page.orchestra.log.learned_cleared": {
        "ru": "[INFO] Данные обучения сброшены",
        "en": "[INFO] Learning data reset",
    },
    "page.orchestra.log_history.current_suffix": {
        "ru": " (текущий)",
        "en": " (current)",
    },
    "page.orchestra.log_history.none": {
        "ru": "  Нет сохранённых логов",
        "en": "  No saved logs",
    },
    "page.orchestra.log_history.loaded": {
        "ru": "\n[INFO] === Загружен лог: {log_id} ===",
        "en": "\n[INFO] === Loaded log: {log_id} ===",
    },
    "page.orchestra.log_history.read_failed": {
        "ru": "[ERROR] Не удалось прочитать лог: {log_id}",
        "en": "[ERROR] Failed to read log: {log_id}",
    },
    "page.orchestra.log_history.deleted": {
        "ru": "[INFO] Удалён лог: {log_id}",
        "en": "[INFO] Deleted log: {log_id}",
    },
    "page.orchestra.log_history.delete_failed": {
        "ru": "[WARNING] Не удалось удалить лог (возможно, активный)",
        "en": "[WARNING] Failed to delete log (possibly active)",
    },
    "page.orchestra.log_history.deleted_count": {
        "ru": "[INFO] Удалено {count} лог-файлов",
        "en": "[INFO] Deleted {count} log files",
    },
    "page.orchestra.log_history.nothing_to_delete": {
        "ru": "[INFO] Нет логов для удаления",
        "en": "[INFO] No logs to delete",
    },
    "page.orchestra.context.copy_line": {
        "ru": "📋 Копировать строку",
        "en": "📋 Copy line",
    },
    "page.orchestra.context.lock_strategy": {
        "ru": "🔒 Залочить стратегию #{strategy} для {domain}",
        "en": "🔒 Lock strategy #{strategy} for {domain}",
    },
    "page.orchestra.context.unblock_strategy": {
        "ru": "✅ Разблокировать стратегию #{strategy} для {domain}",
        "en": "✅ Unblock strategy #{strategy} for {domain}",
    },
    "page.orchestra.context.block_strategy": {
        "ru": "🚫 Заблокировать стратегию #{strategy} для {domain}",
        "en": "🚫 Block strategy #{strategy} for {domain}",
    },
    "page.orchestra.context.add_whitelist": {
        "ru": "⬚ Добавить {domain} в белый список",
        "en": "⬚ Add {domain} to whitelist",
    },
    "page.orchestra.log.clipboard_copied": {
        "ru": "[INFO] Строка скопирована в буфер обмена",
        "en": "[INFO] Line copied to clipboard",
    },
    "page.orchestra.log.lock_unknown_strategy": {
        "ru": "[WARNING] Невозможно залочить: стратегия неизвестна",
        "en": "[WARNING] Cannot lock: strategy is unknown",
    },
    "page.orchestra.log.strategy_locked": {
        "ru": "[INFO] [USER] 🔒 Залочена стратегия #{strategy} для {domain} [{protocol}]",
        "en": "[INFO] [USER] 🔒 Locked strategy #{strategy} for {domain} [{protocol}]",
    },
    "page.orchestra.log.apply_user_lock": {
        "ru": "[INFO] Применяю user lock (перезапуск)...",
        "en": "[INFO] Applying user lock (restart)...",
    },
    "page.orchestra.log.user_lock_applied": {
        "ru": "[INFO] ✓ User lock применён",
        "en": "[INFO] ✓ User lock applied",
    },
    "page.orchestra.log.restart_failed": {
        "ru": "[ERROR] Не удалось перезапустить оркестратор",
        "en": "[ERROR] Failed to restart orchestrator",
    },
    "page.orchestra.log.not_running_user_lock_saved": {
        "ru": "[WARNING] Оркестратор не запущен, user lock сохранён в реестр",
        "en": "[WARNING] Orchestrator is not running, user lock is saved in registry",
    },
    "page.orchestra.log.not_initialized": {
        "ru": "[ERROR] Оркестратор не инициализирован",
        "en": "[ERROR] Orchestrator is not initialized",
    },
    "page.orchestra.log.error": {
        "ru": "[ERROR] Ошибка: {error}",
        "en": "[ERROR] Error: {error}",
    },
    "page.orchestra.log.block_unknown_strategy": {
        "ru": "[WARNING] Невозможно заблокировать: стратегия неизвестна",
        "en": "[WARNING] Cannot block: strategy is unknown",
    },
    "page.orchestra.log.strategy_blocked": {
        "ru": "[INFO] 🚫 Заблокирована стратегия #{strategy} для {domain} [{protocol}]",
        "en": "[INFO] 🚫 Blocked strategy #{strategy} for {domain} [{protocol}]",
    },
    "page.orchestra.log.restart_for_block": {
        "ru": "[INFO] Перезапуск оркестратора для применения блокировки...",
        "en": "[INFO] Restarting orchestrator to apply block...",
    },
    "page.orchestra.log.strategy_unblocked": {
        "ru": "[INFO] ✅ Разблокирована стратегия #{strategy} для {domain} [{protocol}]",
        "en": "[INFO] ✅ Unblocked strategy #{strategy} for {domain} [{protocol}]",
    },
    "page.orchestra.log.restart_for_unblock": {
        "ru": "[INFO] Перезапуск оркестратора для применения разблокировки...",
        "en": "[INFO] Restarting orchestrator to apply unblock...",
    },
    "page.orchestra.log.whitelist_added": {
        "ru": "[INFO] ✅ Добавлен в белый список: {domain}",
        "en": "[INFO] ✅ Added to whitelist: {domain}",
    },
    "page.orchestra.log.whitelist_add_failed": {
        "ru": "[WARNING] Не удалось добавить: {domain}",
        "en": "[WARNING] Failed to add: {domain}",
    },
    "page.orchestra.blocked.title": {
        "ru": "Заблокированные стратегии",
        "en": "Blocked Strategies",
    },
    "page.orchestra.blocked.subtitle": {
        "ru": "Системные блокировки (strategy=1 для заблокированных РКН сайтов) + пользовательский чёрный список. Оркестратор не будет их использовать.",
        "en": "System blocks (strategy=1 for blocked sites) plus custom blacklist. Orchestrator will not use them.",
    },
    "page.orchestra.blocked.card.add": {
        "ru": "Заблокировать стратегию вручную",
        "en": "Block strategy manually",
    },
    "page.orchestra.blocked.input.domain.placeholder": {
        "ru": "example.com",
        "en": "example.com",
    },
    "page.orchestra.blocked.button.block.tooltip": {
        "ru": "Заблокировать стратегию",
        "en": "Block strategy",
    },
    "page.orchestra.blocked.card.list": {
        "ru": "Чёрный список",
        "en": "Blacklist",
    },
    "page.orchestra.blocked.search.placeholder": {
        "ru": "Поиск по доменам...",
        "en": "Search by domain...",
    },
    "page.orchestra.blocked.button.refresh.tooltip": {
        "ru": "Обновить",
        "en": "Refresh",
    },
    "page.orchestra.blocked.button.clear_user": {
        "ru": "Очистить пользовательские",
        "en": "Clear custom",
    },
    "page.orchestra.blocked.button.clear_user.tooltip": {
        "ru": "Удалить все пользовательские блокировки (системные останутся)",
        "en": "Delete all custom blocks (system blocks remain)",
    },
    "page.orchestra.blocked.hint": {
        "ru": "Измените номер стратегии и она автоматически сохранится • Системные блокировки неизменяемы",
        "en": "Change strategy number and it saves automatically • System blocks are read-only",
    },
    "page.orchestra.blocked.section.user": {
        "ru": "Пользовательские ({count})",
        "en": "Custom ({count})",
    },
    "page.orchestra.blocked.section.system": {
        "ru": "Системные ({count}) - заблокированные РКН сайты",
        "en": "System ({count}) - blocked sites",
    },
    "page.orchestra.blocked.row.add.tooltip": {
        "ru": "Добавить ещё одну заблокированную стратегию для этого домена",
        "en": "Add one more blocked strategy for this domain",
    },
    "page.orchestra.blocked.row.unblock.tooltip": {
        "ru": "Разблокировать",
        "en": "Unblock",
    },
    "page.orchestra.blocked.row.system.tooltip": {
        "ru": "Системная блокировка (нельзя изменить)",
        "en": "System block (cannot be changed)",
    },
    "page.orchestra.blocked.count.reload_hint": {
        "ru": "Нажмите 'Обновить' для загрузки данных",
        "en": "Click 'Refresh' to load data",
    },
    "page.orchestra.blocked.count.total": {
        "ru": "Всего: {total} ({user_count} пользовательских + {default_count} системных)",
        "en": "Total: {total} ({user_count} custom + {default_count} system)",
    },
    "page.orchestra.blocked.infobar.applied.title": {
        "ru": "Применено",
        "en": "Applied",
    },
    "page.orchestra.blocked.infobar.unblocked": {
        "ru": "Стратегия #{strategy} разблокирована для {domain}. Оркестратор перезапускается.",
        "en": "Strategy #{strategy} unblocked for {domain}. Orchestrator is restarting.",
    },
    "page.orchestra.blocked.infobar.blocked": {
        "ru": "Стратегия #{strategy} заблокирована для {domain}. Оркестратор перезапускается.",
        "en": "Strategy #{strategy} blocked for {domain}. Orchestrator is restarting.",
    },
    "page.orchestra.blocked.infobar.info.title": {
        "ru": "Информация",
        "en": "Information",
    },
    "page.orchestra.blocked.infobar.no_user_blocks": {
        "ru": "Нет пользовательских блокировок для удаления. Системные блокировки не удаляются.",
        "en": "No custom blocks to delete. System blocks are not removed.",
    },
    "page.orchestra.blocked.dialog.clear_user.title": {
        "ru": "Подтверждение",
        "en": "Confirmation",
    },
    "page.orchestra.blocked.dialog.clear_user.body": {
        "ru": "Очистить пользовательский чёрный список ({count} записей)?\n\nСистемные блокировки останутся.",
        "en": "Clear custom blacklist ({count} entries)?\n\nSystem blocks will remain.",
    },
    "page.orchestra.blocked.infobar.cleared": {
        "ru": "Чёрный список очищен. Оркестратор перезапускается.",
        "en": "Blacklist cleared. Orchestrator is restarting.",
    },
    "page.orchestra.locked.title": {
        "ru": "Залоченные стратегии",
        "en": "Locked Strategies",
    },
    "page.orchestra.locked.subtitle": {
        "ru": "Домены с фиксированной стратегией. Оркестратор не будет менять стратегию для этих доменов. Это значит что оркестратор нашёл для этих сайтов наилучшую стратегию. Вы можете зафиксировать свою стратегию для домена здесь.\nЕсли Вас не устраивает текущая стратегия - заблокируйте её здесь и оркестратор начнёт обучение заново при следующем посещении сайта.\nЕсли Вы просто хотите начать обучение заново - разлочьте стратегию.",
        "en": "Domains with fixed strategy. Orchestrator will not change strategy for these domains.\nIf current strategy is not acceptable, block it to force relearning.\nUnlock to start learning from scratch.",
    },
    "page.orchestra.locked.card.add": {
        "ru": "Залочить стратегию вручную",
        "en": "Lock strategy manually",
    },
    "page.orchestra.locked.input.domain.placeholder": {
        "ru": "example.com",
        "en": "example.com",
    },
    "page.orchestra.locked.button.lock.tooltip": {
        "ru": "Залочить стратегию",
        "en": "Lock strategy",
    },
    "page.orchestra.locked.card.list": {
        "ru": "Список залоченных",
        "en": "Locked list",
    },
    "page.orchestra.locked.search.placeholder": {
        "ru": "Поиск по доменам...",
        "en": "Search by domain...",
    },
    "page.orchestra.locked.button.refresh.tooltip": {
        "ru": "Обновить",
        "en": "Refresh",
    },
    "page.orchestra.locked.button.unlock_all": {
        "ru": "Разлочить все",
        "en": "Unlock all",
    },
    "page.orchestra.locked.hint": {
        "ru": "Измените номер стратегии и она автоматически сохранится",
        "en": "Change strategy number and it will be saved automatically",
    },
    "page.orchestra.locked.row.unlock.tooltip": {
        "ru": "Разлочить",
        "en": "Unlock",
    },
    "page.orchestra.locked.warning.blocked_strategy": {
        "ru": "Стратегия #{strategy} заблокирована для {domain}. Разблокируйте её на странице 'Заблокированные'.",
        "en": "Strategy #{strategy} is blocked for {domain}. Unblock it on the 'Blocked' page.",
    },
    "page.orchestra.locked.infobar.applied.title": {
        "ru": "Применено",
        "en": "Applied",
    },
    "page.orchestra.locked.infobar.unlocked": {
        "ru": "Стратегия разлочена для {domain}. Оркестратор перезапускается.",
        "en": "Strategy unlocked for {domain}. Orchestrator is restarting.",
    },
    "page.orchestra.locked.count.reload_hint": {
        "ru": "Нажмите 'Обновить' для загрузки данных",
        "en": "Click 'Refresh' to load data",
    },
    "page.orchestra.locked.count.total": {
        "ru": "Всего залочено: {total} (TCP: {tcp_count}, UDP: {udp_count})",
        "en": "Total locked: {total} (TCP: {tcp_count}, UDP: {udp_count})",
    },
    "page.orchestra.locked.dialog.unlock_all.title": {
        "ru": "Подтверждение",
        "en": "Confirmation",
    },
    "page.orchestra.locked.dialog.unlock_all.body": {
        "ru": "Разлочить все {total} стратегий?\nОркестратор начнёт обучение заново.",
        "en": "Unlock all {total} strategies?\nOrchestrator will start learning again.",
    },
    "page.orchestra.locked.infobar.unlocked_all": {
        "ru": "Разлочены все {total} стратегий. Оркестратор перезапускается.",
        "en": "All {total} strategies unlocked. Orchestrator is restarting.",
    },
    "page.orchestra.ratings.title": {
        "ru": "История стратегий (рейтинги)",
        "en": "Strategy History (Ratings)",
    },
    "page.orchestra.ratings.subtitle": {
        "ru": "Рейтинг = успехи / (успехи + провалы). При UNLOCK выбирается лучшая стратегия из истории.",
        "en": "Rating = successes / (successes + failures). On UNLOCK the best strategy from history is selected.",
    },
    "page.orchestra.ratings.card.filter": {
        "ru": "Фильтр",
        "en": "Filter",
    },
    "page.orchestra.ratings.filter.placeholder": {
        "ru": "Поиск по домену...",
        "en": "Search by domain...",
    },
    "page.orchestra.ratings.button.refresh": {
        "ru": "Обновить",
        "en": "Refresh",
    },
    "page.orchestra.ratings.stats.loading": {
        "ru": "Загрузка...",
        "en": "Loading...",
    },
    "page.orchestra.ratings.card.history": {
        "ru": "Рейтинги по доменам",
        "en": "Domain ratings",
    },
    "page.orchestra.ratings.history.placeholder": {
        "ru": "История стратегий появится после обучения...",
        "en": "Strategy history will appear after training...",
    },
    "page.orchestra.ratings.status.not_initialized": {
        "ru": "Оркестратор не инициализирован",
        "en": "Orchestrator is not initialized",
    },
    "page.orchestra.ratings.status.no_history": {
        "ru": "Нет данных истории",
        "en": "No history data",
    },
    "page.orchestra.ratings.status.lock.tls": {
        "ru": " [TLS LOCK]",
        "en": " [TLS LOCK]",
    },
    "page.orchestra.ratings.status.lock.http": {
        "ru": " [HTTP LOCK]",
        "en": " [HTTP LOCK]",
    },
    "page.orchestra.ratings.status.lock.udp": {
        "ru": " [UDP LOCK]",
        "en": " [UDP LOCK]",
    },
    "page.orchestra.ratings.stats.filtered": {
        "ru": "Показано: {shown} из {total} доменов, {records} записей",
        "en": "Shown: {shown} of {total} domains, {records} entries",
    },
    "page.orchestra.ratings.stats.total": {
        "ru": "Всего: {total} доменов, {records} записей",
        "en": "Total: {total} domains, {records} entries",
    },
    "page.orchestra.whitelist.title": {
        "ru": "Белый список",
        "en": "Whitelist",
    },
    "page.orchestra.whitelist.subtitle": {
        "ru": "Домены, которые НЕ обрабатываются оркестратором. Эти сайты работают без DPI bypass.",
        "en": "Domains not processed by orchestrator. These sites run without DPI bypass.",
    },
    "page.orchestra.whitelist.warning.restart_required": {
        "ru": "⚠️ Изменения применятся после перезапуска оркестратора",
        "en": "⚠️ Changes apply after orchestrator restart",
    },
    "page.orchestra.whitelist.card.add": {
        "ru": "Добавить домен",
        "en": "Add domain",
    },
    "page.orchestra.whitelist.input.placeholder": {
        "ru": "example.com",
        "en": "example.com",
    },
    "page.orchestra.whitelist.tooltip.add": {
        "ru": "Добавить в белый список",
        "en": "Add to whitelist",
    },
    "page.orchestra.whitelist.card.list": {
        "ru": "Белый список доменов",
        "en": "Domain whitelist",
    },
    "page.orchestra.whitelist.search.placeholder": {
        "ru": "Поиск по доменам...",
        "en": "Search domains...",
    },
    "page.orchestra.whitelist.button.clear_user": {
        "ru": "Очистить пользовательские",
        "en": "Clear custom",
    },
    "page.orchestra.whitelist.tooltip.clear_user": {
        "ru": "Удалить все пользовательские домены (системные останутся)",
        "en": "Remove all custom domains (system domains stay)",
    },
    "page.orchestra.whitelist.status.init_error": {
        "ru": "Ошибка инициализации",
        "en": "Initialization error",
    },
    "page.orchestra.whitelist.section.user": {
        "ru": "Пользовательские ({count})",
        "en": "Custom ({count})",
    },
    "page.orchestra.whitelist.section.system": {
        "ru": "🔒 Системные ({count}) — нельзя удалить",
        "en": "🔒 System ({count}) — cannot be removed",
    },
    "page.orchestra.whitelist.tooltip.delete": {
        "ru": "Удалить из белого списка",
        "en": "Remove from whitelist",
    },
    "page.orchestra.whitelist.tooltip.system_domain": {
        "ru": "Системный домен (нельзя удалить)",
        "en": "System domain (cannot be removed)",
    },
    "page.orchestra.whitelist.count.total": {
        "ru": "Всего: {total} ({system} системных + {user} пользовательских)",
        "en": "Total: {total} ({system} system + {user} custom)",
    },
    "page.orchestra.whitelist.error.init_runner": {
        "ru": "Не удалось инициализировать оркестратор",
        "en": "Failed to initialize orchestrator",
    },
    "page.orchestra.whitelist.infobar.info_title": {
        "ru": "Информация",
        "en": "Information",
    },
    "page.orchestra.whitelist.info.already_exists": {
        "ru": "Домен {domain} уже в списке",
        "en": "Domain {domain} is already in the list",
    },
    "page.orchestra.whitelist.info.no_user_domains": {
        "ru": "Нет пользовательских доменов для удаления. Системные домены не удаляются.",
        "en": "No custom domains to remove. System domains are not removed.",
    },
    "page.orchestra.whitelist.dialog.clear_user.title": {
        "ru": "Подтверждение",
        "en": "Confirmation",
    },
    "page.orchestra.whitelist.dialog.clear_user.body": {
        "ru": "Удалить все пользовательские домены ({count})?\n\nСистемные домены останутся.",
        "en": "Delete all custom domains ({count})?\n\nSystem domains will remain.",
    },
    "page.premium.subtitle": {
        "ru": "Управление подпиской Zapret Premium",
        "en": "Manage Zapret Premium subscription",
    },
    "page.premium.section.subscription_status": {
        "ru": "Статус подписки",
        "en": "Subscription Status",
    },
    "page.premium.section.device_binding": {
        "ru": "Привязка устройства",
        "en": "Device Binding",
    },
    "page.premium.section.device_info": {
        "ru": "Информация об устройстве",
        "en": "Device Information",
    },
    "page.premium.section.actions": {
        "ru": "Действия",
        "en": "Actions",
    },
    "page.premium.instructions": {
        "ru": "1. Нажмите «Создать код»\n2. Отправьте код боту @zapretvpns_bot в Telegram (сообщением)\n3. Вернитесь сюда и нажмите «Проверить статус»",
        "en": "1. Click \"Create code\"\n2. Send the code to @zapretvpns_bot in Telegram (as a message)\n3. Return here and click \"Refresh status\"",
    },
    "page.premium.placeholder.pair_code": {
        "ru": "ABCD12EF",
        "en": "ABCD12EF",
    },
    "page.premium.button.create_code": {
        "ru": "Создать код",
        "en": "Create code",
    },
    "page.premium.button.create_code.loading": {
        "ru": "Создание...",
        "en": "Creating...",
    },
    "page.premium.button.open_bot": {
        "ru": "Открыть бота",
        "en": "Open bot",
    },
    "page.premium.button.refresh_status": {
        "ru": "Обновить статус",
        "en": "Refresh status",
    },
    "page.premium.button.reset_activation": {
        "ru": "Сбросить активацию",
        "en": "Reset activation",
    },
    "page.premium.button.test_connection": {
        "ru": "Проверить соединение",
        "en": "Test connection",
    },
    "page.premium.button.test_connection.loading": {
        "ru": "Проверка...",
        "en": "Checking...",
    },
    "page.premium.button.extend": {
        "ru": "Продлить подписку",
        "en": "Extend subscription",
    },
    "page.premium.label.device_id.loading": {
        "ru": "ID устройства: загрузка...",
        "en": "Device ID: loading...",
    },
    "page.premium.label.device_id.value": {
        "ru": "ID устройства: {device_id}...",
        "en": "Device ID: {device_id}...",
    },
    "page.premium.label.device_token.none": {
        "ru": "device token: —",
        "en": "device token: -",
    },
    "page.premium.label.device_token.present": {
        "ru": "device token: ✅",
        "en": "device token: ✅",
    },
    "page.premium.label.device_token.absent": {
        "ru": "device token: ❌",
        "en": "device token: ❌",
    },
    "page.premium.label.pair_code.value": {
        "ru": "pair: {pair_code}",
        "en": "pair: {pair_code}",
    },
    "page.premium.label.last_check.none": {
        "ru": "Последняя проверка: —",
        "en": "Last check: -",
    },
    "page.premium.label.last_check.value": {
        "ru": "Последняя проверка: {date}",
        "en": "Last check: {date}",
    },
    "page.premium.label.server.checking": {
        "ru": "Сервер: проверка...",
        "en": "Server: checking...",
    },
    "page.premium.label.server.idle": {
        "ru": "Сервер: нажмите «Проверить соединение»",
        "en": "Server: click \"Test connection\"",
    },
    "page.premium.activation.error.init": {
        "ru": "❌ Ошибка инициализации",
        "en": "❌ Initialization error",
    },
    "page.premium.activation.error.generic": {
        "ru": "❌ Ошибка: {error}",
        "en": "❌ Error: {error}",
    },
    "page.premium.activation.error.invalid_reply": {
        "ru": "Неверный ответ",
        "en": "Invalid response",
    },
    "page.premium.activation.progress.creating_code": {
        "ru": "🔄 Создаю код...",
        "en": "🔄 Creating code...",
    },
    "page.premium.activation.success.code_created": {
        "ru": "✅ Код создан и скопирован. Отправьте его боту в Telegram.",
        "en": "✅ Code created and copied. Send it to the bot in Telegram.",
    },
    "page.premium.connection.progress.testing": {
        "ru": "🔄 Проверка соединения...",
        "en": "🔄 Testing connection...",
    },
    "page.premium.connection.result.template": {
        "ru": "{icon} {message}",
        "en": "{icon} {message}",
    },
    "page.premium.status.checking.title": {
        "ru": "Проверка...",
        "en": "Checking...",
    },
    "page.premium.status.checking.details": {
        "ru": "Подключение к серверу",
        "en": "Connecting to server",
    },
    "page.premium.status.active.title": {
        "ru": "Подписка активна",
        "en": "Subscription active",
    },
    "page.premium.status.active.days_left": {
        "ru": "Осталось {days} дней",
        "en": "{days} days left",
    },
    "page.premium.status.expiring_soon.title": {
        "ru": "Скоро истекает!",
        "en": "Expiring soon!",
    },
    "page.premium.status.inactive.title": {
        "ru": "Подписка не активна",
        "en": "Subscription inactive",
    },
    "page.premium.status.inactive.linked_hint": {
        "ru": "Продлите подписку в боте и нажмите «Обновить статус».",
        "en": "Extend subscription in the bot and click \"Refresh status\".",
    },
    "page.premium.status.inactive.unlinked_hint": {
        "ru": "Создайте код и привяжите устройство.",
        "en": "Create a code and link this device.",
    },
    "page.premium.status.error.title": {
        "ru": "Ошибка",
        "en": "Error",
    },
    "page.premium.status.error.init_failed": {
        "ru": "Не удалось инициализировать",
        "en": "Initialization failed",
    },
    "page.premium.status.error.invalid_response": {
        "ru": "Неверный ответ сервера",
        "en": "Invalid server response",
    },
    "page.premium.status.error.incomplete_response": {
        "ru": "Неполный ответ",
        "en": "Incomplete response",
    },
    "page.premium.status.error.check_failed": {
        "ru": "Ошибка проверки",
        "en": "Check failed",
    },
    "page.premium.status.reset.title": {
        "ru": "Привязка сброшена",
        "en": "Binding reset",
    },
    "page.premium.status.reset.details": {
        "ru": "Создайте новый код для привязки",
        "en": "Create a new code to link the device",
    },
    "page.premium.days_label.normal": {
        "ru": "Осталось дней: {days}",
        "en": "Days left: {days}",
    },
    "page.premium.days_label.warning": {
        "ru": "⚠️ Осталось дней: {days}",
        "en": "⚠️ Days left: {days}",
    },
    "page.premium.days_label.urgent": {
        "ru": "⚠️ Срочно продлите! Осталось: {days}",
        "en": "⚠️ Renew urgently! Left: {days}",
    },
    "page.premium.dialog.reset.title": {
        "ru": "Подтверждение",
        "en": "Confirmation",
    },
    "page.premium.dialog.reset.body": {
        "ru": "Сбросить активацию на этом устройстве?\nБудут удалены device token, offline-кэш и код привязки.\nДля восстановления потребуется повторная привязка в боте.",
        "en": "Reset activation on this device?\nThis will remove device token, offline cache, and pair code.\nYou will need to link again in the bot.",
    },
    "page.premium.error.open_telegram": {
        "ru": "Не удалось открыть Telegram: {error}",
        "en": "Failed to open Telegram: {error}",
    },
    "page.servers.title": {
        "ru": "Серверы",
        "en": "Servers",
    },
    "page.servers.subtitle": {
        "ru": "Мониторинг серверов обновлений",
        "en": "Update servers monitoring",
    },
    "page.servers.back.about": {
        "ru": "О программе",
        "en": "About",
    },
    "page.servers.section.update_servers": {
        "ru": "Серверы обновлений",
        "en": "Update Servers",
    },
    "page.servers.legend.active": {
        "ru": "⭐ активный",
        "en": "⭐ active",
    },
    "page.servers.table.header.server": {
        "ru": "Сервер",
        "en": "Server",
    },
    "page.servers.table.header.status": {
        "ru": "Статус",
        "en": "Status",
    },
    "page.servers.table.header.time": {
        "ru": "Время",
        "en": "Time",
    },
    "page.servers.table.header.versions": {
        "ru": "Версии",
        "en": "Versions",
    },
    "page.servers.settings.title": {
        "ru": "Настройки",
        "en": "Settings",
    },
    "page.servers.settings.auto_check": {
        "ru": "Проверять обновления при запуске",
        "en": "Check for updates on startup",
    },
    "page.servers.settings.version_channel_template": {
        "ru": "v{version} · {channel}",
        "en": "v{version} · {channel}",
    },
    "page.servers.telegram.title": {
        "ru": "Проблемы с обновлением?",
        "en": "Update problems?",
    },
    "page.servers.telegram.info": {
        "ru": "Если возникают трудности с автоматическим обновлением, все версии программы выкладываются в Telegram канале.",
        "en": "If automatic update is difficult to use, all app versions are published in the Telegram channel.",
    },
    "page.servers.telegram.button.open_channel": {
        "ru": "Открыть Telegram канал",
        "en": "Open Telegram Channel",
    },
    "page.servers.table.status.online": {
        "ru": "● Онлайн",
        "en": "● Online",
    },
    "page.servers.table.status.blocked": {
        "ru": "● Блок",
        "en": "● Blocked",
    },
    "page.servers.table.status.offline": {
        "ru": "● Офлайн",
        "en": "● Offline",
    },
    "page.servers.table.time.ms_template": {
        "ru": "{ms}мс",
        "en": "{ms}ms",
    },
    "page.servers.table.time.empty": {
        "ru": "—",
        "en": "—",
    },
    "page.servers.table.versions.stable_template": {
        "ru": "S: {version}",
        "en": "S: {version}",
    },
    "page.servers.table.versions.test_template": {
        "ru": "T: {version}",
        "en": "T: {version}",
    },
    "page.servers.table.versions.both_template": {
        "ru": "S: {stable}, T: {test}",
        "en": "S: {stable}, T: {test}",
    },
    "page.servers.table.versions.rate_limit_template": {
        "ru": "Лимит: {remaining}/{limit}",
        "en": "Limit: {remaining}/{limit}",
    },
    "page.servers.error.version_not_found": {
        "ru": "Версия не найдена",
        "en": "Version not found",
    },
    "page.servers.error.bot_not_configured": {
        "ru": "Бот не настроен",
        "en": "Bot is not configured",
    },
    "page.servers.error.blocked_until_template": {
        "ru": "Заблокирован до {time}",
        "en": "Blocked until {time}",
    },
    "page.servers.error.connect_failed": {
        "ru": "Не удалось подключиться",
        "en": "Connection failed",
    },
    "page.servers.update.title.default": {
        "ru": "Проверка обновлений",
        "en": "Update Check",
    },
    "page.servers.update.title.checking": {
        "ru": "Проверка обновлений...",
        "en": "Checking updates...",
    },
    "page.servers.update.title.available_template": {
        "ru": "Доступно обновление v{version}",
        "en": "Update available v{version}",
    },
    "page.servers.update.title.none": {
        "ru": "Обновлений нет",
        "en": "No updates",
    },
    "page.servers.update.title.error": {
        "ru": "Ошибка проверки",
        "en": "Check error",
    },
    "page.servers.update.title.found_template": {
        "ru": "Найдено обновление v{version}",
        "en": "Found update v{version}",
    },
    "page.servers.update.title.download_error": {
        "ru": "Ошибка загрузки",
        "en": "Download error",
    },
    "page.servers.update.title.deferred_template": {
        "ru": "Обновление v{version} отложено",
        "en": "Update v{version} postponed",
    },
    "page.servers.update.subtitle.default": {
        "ru": "Нажмите для проверки доступных обновлений",
        "en": "Click to check available updates",
    },
    "page.servers.update.subtitle.checking": {
        "ru": "Подождите, идёт проверка серверов",
        "en": "Please wait, checking servers",
    },
    "page.servers.update.subtitle.available": {
        "ru": "Установите обновление ниже или проверьте ещё раз",
        "en": "Install the update below or check again",
    },
    "page.servers.update.subtitle.latest_template": {
        "ru": "Установлена последняя версия {version}",
        "en": "Latest version installed: {version}",
    },
    "page.servers.update.subtitle.source_template": {
        "ru": "Источник: {source}",
        "en": "Source: {source}",
    },
    "page.servers.update.subtitle.try_again": {
        "ru": "Попробуйте снова",
        "en": "Please try again",
    },
    "page.servers.update.subtitle.recheck_hint": {
        "ru": "Нажмите для повторной проверки",
        "en": "Press to recheck",
    },
    "page.servers.update.subtitle.press_button": {
        "ru": "Нажмите кнопку для проверки",
        "en": "Press the button to check",
    },
    "page.servers.update.subtitle.auto_on": {
        "ru": "Автопроверка включена",
        "en": "Auto-check enabled",
    },
    "page.servers.update.subtitle.checked_ago_sec_template": {
        "ru": "Проверено {seconds}с назад",
        "en": "Checked {seconds}s ago",
    },
    "page.servers.update.subtitle.checked_ago_min_sec_template": {
        "ru": "Проверено {minutes}м {seconds}с назад",
        "en": "Checked {minutes}m {seconds}s ago",
    },
    "page.servers.update.button.check": {
        "ru": "Проверить обновления",
        "en": "Check Updates",
    },
    "page.servers.update.button.recheck": {
        "ru": "ПРОВЕРИТЬ СНОВА",
        "en": "CHECK AGAIN",
    },
    "page.servers.update.button.retry": {
        "ru": "Повторить",
        "en": "Retry",
    },
    "page.servers.update.button.manual": {
        "ru": "ПРОВЕРИТЬ ВРУЧНУЮ",
        "en": "CHECK MANUALLY",
    },
    "page.servers.changelog.title.available": {
        "ru": "Доступно обновление",
        "en": "Update Available",
    },
    "page.servers.changelog.title.downloading_template": {
        "ru": "Загрузка v{version}",
        "en": "Downloading v{version}",
    },
    "page.servers.changelog.title.installing": {
        "ru": "Установка...",
        "en": "Installing...",
    },
    "page.servers.changelog.title.download_error": {
        "ru": "Ошибка загрузки",
        "en": "Download error",
    },
    "page.servers.changelog.button.later": {
        "ru": "Позже",
        "en": "Later",
    },
    "page.servers.changelog.button.install": {
        "ru": "Установить",
        "en": "Install",
    },
    "page.servers.changelog.button.retry": {
        "ru": "Повторить",
        "en": "Retry",
    },
    "page.servers.changelog.version.transition_template": {
        "ru": "v{current}  →  v{target}",
        "en": "v{current}  →  v{target}",
    },
    "page.servers.changelog.version.preparing": {
        "ru": "Подготовка к загрузке...",
        "en": "Preparing download...",
    },
    "page.servers.changelog.version.installer_starting": {
        "ru": "Запуск установщика, приложение закроется",
        "en": "Starting installer, application will close",
    },
    "page.servers.changelog.progress.speed_unknown": {
        "ru": "Скорость: —",
        "en": "Speed: —",
    },
    "page.servers.changelog.progress.eta_unknown": {
        "ru": "Осталось: —",
        "en": "Remaining: —",
    },
    "page.servers.changelog.progress.downloaded_mb_template": {
        "ru": "Загружено {done:.1f} / {total:.1f} МБ",
        "en": "Downloaded {done:.1f} / {total:.1f} MB",
    },
    "page.servers.changelog.progress.speed_mb_template": {
        "ru": "Скорость: {value:.1f} МБ/с",
        "en": "Speed: {value:.1f} MB/s",
    },
    "page.servers.changelog.progress.speed_kb_template": {
        "ru": "Скорость: {value:.0f} КБ/с",
        "en": "Speed: {value:.0f} KB/s",
    },
    "page.servers.changelog.progress.eta_sec_template": {
        "ru": "Осталось: {seconds} сек",
        "en": "Remaining: {seconds} sec",
    },
    "page.servers.changelog.progress.eta_min_template": {
        "ru": "Осталось: {minutes} мин",
        "en": "Remaining: {minutes} min",
    },
    "page.support.title": {
        "ru": "Поддержка",
        "en": "Support",
    },
    "page.support.subtitle": {
        "ru": "GitHub Discussions и каналы сообщества",
        "en": "GitHub Discussions and community channels",
    },
    "page.support.section.discussions": {
        "ru": "GitHub Discussions",
        "en": "GitHub Discussions",
    },
    "page.support.section.community": {
        "ru": "Каналы сообщества",
        "en": "Community Channels",
    },
    "page.support.discussions.title": {
        "ru": "GitHub Discussions",
        "en": "GitHub Discussions",
    },
    "page.support.discussions.description": {
        "ru": "Основной канал поддержки. Здесь можно задать вопрос, описать проблему и приложить нужные материалы вручную.",
        "en": "Main support channel. Ask questions, describe the issue, and attach materials manually.",
    },
    "page.support.discussions.button": {
        "ru": "Открыть",
        "en": "Open",
    },
    "page.support.error.open_discussions": {
        "ru": "Не удалось открыть GitHub Discussions:\n{error}",
        "en": "Failed to open GitHub Discussions:\n{error}",
    },
    "page.support.channel.telegram.title": {
        "ru": "Telegram",
        "en": "Telegram",
    },
    "page.support.channel.telegram.desc": {
        "ru": "Быстрые вопросы и общение с сообществом",
        "en": "Quick questions and community chat",
    },
    "page.support.channel.discord.title": {
        "ru": "Discord",
        "en": "Discord",
    },
    "page.support.channel.discord.desc": {
        "ru": "Обсуждение и живое общение",
        "en": "Discussion and live chat",
    },
    "page.support.channel.open": {
        "ru": "Открыть",
        "en": "Open",
    },
    "page.support.error.title": {
        "ru": "Ошибка",
        "en": "Error",
    },
    "page.support.error.open_telegram": {
        "ru": "Не удалось открыть Telegram:\n{error}",
        "en": "Failed to open Telegram:\n{error}",
    },
    "page.support.error.open_discord": {
        "ru": "Не удалось открыть Discord:\n{error}",
        "en": "Failed to open Discord:\n{error}",
    },
    "page.z1_control.subtitle": {
        "ru": "Настройка и запуск Zapret 1 (winws.exe). Выберите стратегии для категорий или переключитесь на другой пресет.",
        "en": "Configure and launch Zapret 1 (winws.exe). Choose category strategies or switch preset.",
    },
    "page.z1_control.section.status": {
        "ru": "Статус работы",
        "en": "Service Status",
    },
    "page.z1_control.section.management": {
        "ru": "Управление Zapret 1",
        "en": "Zapret 1 Control",
    },
    "page.z1_control.section.presets": {
        "ru": "Пресеты и стратегии",
        "en": "Presets and Strategies",
    },
    "page.z1_control.section.program_settings": {
        "ru": "Настройки программы",
        "en": "Program Settings",
    },
    "page.z1_direct.title": {
        "ru": "Прямой запуск Zapret 1",
        "en": "Direct Launch Zapret 1",
    },
    "page.z1_direct.back.control": {
        "ru": "\u2190 Управление",
        "en": "\u2190 Control",
    },
    "page.z1_direct.breadcrumb.control": {
        "ru": "Управление",
        "en": "Control",
    },
    "page.z1_direct.toolbar.expand": {
        "ru": "Развернуть",
        "en": "Expand",
    },
    "page.z1_direct.toolbar.collapse": {
        "ru": "Свернуть",
        "en": "Collapse",
    },
    "page.z1_direct.toolbar.info": {
        "ru": "Что это?",
        "en": "What is this?",
    },
    "page.z1_direct.strategy.off": {
        "ru": "Выключено",
        "en": "Off",
    },
    "page.z1_direct.strategy.custom": {
        "ru": "Свой набор",
        "en": "Custom set",
    },
    "page.z1_direct.info.title": {
        "ru": "Прямой запуск Zapret 1",
        "en": "Direct Launch Zapret 1",
    },
    "page.z1_direct.info.body": {
        "ru": "Чтобы запустить zapret напрямую, выберите по одной стратегии для каждой категории и нажмите «Запустить» на странице управления.",
        "en": "To start Zapret directly, choose one strategy per category and click Start on the control page.",
    },
    "page.z1_user_presets.title": {
        "ru": "Мои пресеты",
        "en": "My Presets",
    },
    "page.z1_user_presets.back.control": {
        "ru": "Управление",
        "en": "Control",
    },
    "page.z1_user_presets.configs.title": {
        "ru": "Обменивайтесь пресетами и категориями в разделе GitHub Discussions",
        "en": "Share presets and categories in GitHub Discussions",
    },
    "page.z1_user_presets.configs.button": {
        "ru": "Получить конфиги",
        "en": "Get configs",
    },
    "page.z1_user_presets.button.restore_deleted": {
        "ru": "Восстановить удалённые пресеты",
        "en": "Restore deleted presets",
    },
    "page.z1_user_presets.button.import": {
        "ru": "Импорт",
        "en": "Import",
    },
    "page.z1_user_presets.button.reset_all": {
        "ru": "Вернуть заводские",
        "en": "Restore defaults",
    },
    "page.z1_user_presets.button.wiki": {
        "ru": "Вики по пресетам",
        "en": "Preset wiki",
    },
    "page.z1_user_presets.button.what_is_this": {
        "ru": "Что это такое?",
        "en": "What is this?",
    },
    "page.z1_user_presets.search.placeholder": {
        "ru": "Поиск пресетов по имени...",
        "en": "Search presets by name...",
    },
    "page.z1_user_presets.tooltip.create": {
        "ru": "Создать новый пресет",
        "en": "Create a new preset",
    },
    "page.z1_user_presets.tooltip.import": {
        "ru": "Импорт пресета из файла",
        "en": "Import preset from file",
    },
    "page.z1_user_presets.tooltip.reset_all": {
        "ru": "Восстанавливает стандартные пресеты. Ваши изменения в стандартных пресетах будут потеряны.",
        "en": "Restores default presets. Your changes to default presets will be lost.",
    },
    "page.z1_user_presets.delegate.tooltip.rename": {
        "ru": "Переименовать",
        "en": "Rename",
    },
    "page.z1_user_presets.delegate.tooltip.duplicate": {
        "ru": "Дублировать",
        "en": "Duplicate",
    },
    "page.z1_user_presets.delegate.tooltip.reset": {
        "ru": "Сбросить",
        "en": "Reset",
    },
    "page.z1_user_presets.delegate.tooltip.delete": {
        "ru": "Удалить",
        "en": "Delete",
    },
    "page.z1_user_presets.delegate.tooltip.export": {
        "ru": "Экспорт",
        "en": "Export",
    },
    "page.z1_user_presets.delegate.tooltip.confirm_again": {
        "ru": "Нажмите ещё раз для подтверждения",
        "en": "Click again to confirm",
    },
    "page.z1_user_presets.delegate.badge.active": {
        "ru": "Активен",
        "en": "Active",
    },
    "page.z1_user_presets.dialog.button.cancel": {
        "ru": "Отмена",
        "en": "Cancel",
    },
    "page.z1_user_presets.dialog.reset_single.title": {
        "ru": "Сбросить пресет?",
        "en": "Reset preset?",
    },
    "page.z1_user_presets.dialog.reset_single.body": {
        "ru": "Пресет '{name}' будет перезаписан данными из шаблона.\nВсе изменения в этом пресете будут потеряны.\nЭтот пресет станет активным и будет применен заново.",
        "en": "Preset '{name}' will be overwritten with template data.\nAll changes in this preset will be lost.\nThis preset will become active and be applied again.",
    },
    "page.z1_user_presets.dialog.reset_single.button": {
        "ru": "Сбросить",
        "en": "Reset",
    },
    "page.z1_user_presets.dialog.delete_single.title": {
        "ru": "Удалить пресет?",
        "en": "Delete preset?",
    },
    "page.z1_user_presets.dialog.delete_single.body": {
        "ru": "Пресет '{name}' будет удален из списка пользовательских пресетов.\nИзменения в этом пресете будут потеряны.\nВернуть его можно только через восстановление удаленных пресетов (если доступен шаблон).",
        "en": "Preset '{name}' will be removed from the user presets list.\nChanges in this preset will be lost.\nYou can restore it only via deleted presets restore (if a template exists).",
    },
    "page.z1_user_presets.dialog.delete_single.button": {
        "ru": "Удалить",
        "en": "Delete",
    },
    "page.z1_user_presets.dialog.create.title": {
        "ru": "Новый пресет",
        "en": "New preset",
    },
    "page.z1_user_presets.dialog.create.subtitle": {
        "ru": "Сохраните текущие настройки как отдельный пресет, чтобы быстро переключаться между конфигурациями.",
        "en": "Save current settings as a separate preset to switch between configurations quickly.",
    },
    "page.z1_user_presets.dialog.create.name": {
        "ru": "Название",
        "en": "Name",
    },
    "page.z1_user_presets.dialog.create.placeholder": {
        "ru": "Например: Игры / YouTube / Дом",
        "en": "For example: Games / YouTube / Home",
    },
    "page.z1_user_presets.dialog.create.source": {
        "ru": "Создать на основе",
        "en": "Create from",
    },
    "page.z1_user_presets.dialog.create.source.current": {
        "ru": "Текущего активного",
        "en": "Current active",
    },
    "page.z1_user_presets.dialog.create.source.empty": {
        "ru": "Пустого",
        "en": "Empty",
    },
    "page.z1_user_presets.dialog.create.button.create": {
        "ru": "Создать",
        "en": "Create",
    },
    "page.z1_user_presets.dialog.rename.title": {
        "ru": "Переименовать",
        "en": "Rename",
    },
    "page.z1_user_presets.dialog.rename.subtitle": {
        "ru": "Имя пресета отображается в списке и используется для переключения.",
        "en": "Preset name is shown in the list and used for switching.",
    },
    "page.z1_user_presets.dialog.rename.current_name": {
        "ru": "Текущее имя: {name}",
        "en": "Current name: {name}",
    },
    "page.z1_user_presets.dialog.rename.new_name": {
        "ru": "Новое имя",
        "en": "New name",
    },
    "page.z1_user_presets.dialog.rename.placeholder": {
        "ru": "Новое имя...",
        "en": "New name...",
    },
    "page.z1_user_presets.dialog.rename.button": {
        "ru": "Переименовать",
        "en": "Rename",
    },
    "page.z1_user_presets.dialog.validation.enter_name": {
        "ru": "Введите название.",
        "en": "Enter a name.",
    },
    "page.z1_user_presets.dialog.validation.exists": {
        "ru": "Пресет «{name}» уже существует.",
        "en": "Preset '{name}' already exists.",
    },
    "page.z1_user_presets.dialog.import_exists.title": {
        "ru": "Пресет существует",
        "en": "Preset exists",
    },
    "page.z1_user_presets.dialog.import_exists.body": {
        "ru": "Пресет '{name}' уже существует. Импортировать с другим именем?",
        "en": "Preset '{name}' already exists. Import with another name?",
    },
    "page.z1_user_presets.dialog.reset_all.title": {
        "ru": "Вернуть заводские пресеты",
        "en": "Restore default presets",
    },
    "page.z1_user_presets.dialog.reset_all.body": {
        "ru": "Стандартные пресеты будут восстановлены как после установки.\nВаши изменения в стандартных пресетах будут потеряны.\nПользовательские пресеты с другими именами останутся.\nТекущий выбранный source-пресет будет применён заново автоматически.",
        "en": "Default presets will be restored as after installation.\nYour changes to default presets will be lost.\nCustom presets with other names will remain.\nCurrent selected source preset will be re-applied automatically.",
    },
    "page.z1_user_presets.dialog.reset_all.button": {
        "ru": "Вернуть заводские",
        "en": "Restore defaults",
    },
    "page.z1_user_presets.section.games": {
        "ru": "Игры (game filter)",
        "en": "Games (game filter)",
    },
    "page.z1_user_presets.section.all_tcp_udp": {
        "ru": "Все сайты и игры (ALL TCP/UDP)",
        "en": "All sites and games (ALL TCP/UDP)",
    },
    "page.z1_user_presets.empty.not_found": {
        "ru": "Ничего не найдено.",
        "en": "Nothing found.",
    },
    "page.z1_user_presets.empty.none": {
        "ru": "Нет пресетов. Создайте новый или импортируйте из файла.",
        "en": "No presets. Create a new one or import from file.",
    },
    "page.z1_user_presets.error.generic": {
        "ru": "Ошибка: {error}",
        "en": "Error: {error}",
    },
    "page.z1_user_presets.error.create_failed": {
        "ru": "Не удалось создать пресет.",
        "en": "Failed to create preset.",
    },
    "page.z1_user_presets.error.rename_failed": {
        "ru": "Не удалось переименовать пресет.",
        "en": "Failed to rename preset.",
    },
    "page.z1_user_presets.error.activate_failed": {
        "ru": "Не удалось активировать пресет '{name}'",
        "en": "Failed to activate preset '{name}'",
    },
    "page.z1_user_presets.error.duplicate_failed": {
        "ru": "Не удалось дублировать пресет",
        "en": "Failed to duplicate preset",
    },
    "page.z1_user_presets.error.reset_failed": {
        "ru": "Не удалось сбросить пресет к настройкам шаблона",
        "en": "Failed to reset preset to template defaults",
    },
    "page.z1_user_presets.error.delete_failed": {
        "ru": "Не удалось удалить пресет",
        "en": "Failed to delete preset",
    },
    "page.z1_user_presets.error.import_failed": {
        "ru": "Не удалось импортировать пресет",
        "en": "Failed to import preset",
    },
    "page.z1_user_presets.error.import_exception": {
        "ru": "Ошибка импорта: {error}",
        "en": "Import error: {error}",
    },
    "page.z1_user_presets.error.export_failed": {
        "ru": "Не удалось экспортировать пресет",
        "en": "Failed to export preset",
    },
    "page.z1_user_presets.error.restore_deleted": {
        "ru": "Ошибка восстановления: {error}",
        "en": "Restore error: {error}",
    },
    "page.z1_user_presets.error.reset_all_exception": {
        "ru": "Ошибка восстановления пресетов: {error}",
        "en": "Preset restore error: {error}",
    },
    "page.z1_user_presets.error.open_telegram": {
        "ru": "Не удалось открыть страницу пресетов: {error}",
        "en": "Failed to open presets page: {error}",
    },
    "page.z1_user_presets.file_dialog.import_title": {
        "ru": "Импортировать пресет",
        "en": "Import preset",
    },
    "page.z1_user_presets.file_dialog.export_title": {
        "ru": "Экспортировать пресет",
        "en": "Export preset",
    },
    "page.z1_user_presets.infobar.success": {
        "ru": "Успех",
        "en": "Success",
    },
    "page.z1_user_presets.info.exported": {
        "ru": "Пресет экспортирован: {path}",
        "en": "Preset exported: {path}",
    },
    "page.z1_user_presets.info.title": {
        "ru": "Что это такое?",
        "en": "What is this?",
    },
    "page.z1_user_presets.info.body": {
        "ru": "Здесь кнопка для нубов — \"хочу чтобы нажал и всё работало\". Выбираете любой пресет — тыкаете — перезагружаете вкладку и смотрите, что ресурс открывается (или не открывается). Если не открывается — тыкаете на следующий пресет. Также здесь можно создавать, импортировать, экспортировать и переключать пользовательские пресеты.",
        "en": "This section is for simple workflow: pick any preset, apply it, reload the tab and check if the target opens. If not, try the next preset. You can also create, import, export and switch custom presets here.",
    },
    "page.z1_strategy_detail.title": {
        "ru": "Детали стратегии",
        "en": "Strategy Details",
    },
    "page.z1_strategy_detail.subtitle": {
        "ru": "",
        "en": "",
    },
    "page.z2_control.subtitle": {
        "ru": "Настройка и запуск Zapret 2. Выберите готовые пресеты-конфиги (как раньше .bat), а при необходимости выполните тонкую настройку для каждой категории в разделе «Прямой запуск».",
        "en": "Configure and launch Zapret 2. Choose ready presets and fine-tune categories in Direct Launch.",
    },
    "page.z2_control.section.status": {
        "ru": "Статус работы",
        "en": "Service Status",
    },
    "page.z2_control.section.management": {
        "ru": "Управление Zapret 2",
        "en": "Zapret 2 Control",
    },
    "page.z2_control.section.preset_switch": {
        "ru": "Сменить пресет обхода блокировок",
        "en": "Switch Bypass Preset",
    },
    "page.z2_control.section.direct_tuning": {
        "ru": "Настройте пресет более тонко через прямой запуск",
        "en": "Fine Tune via Direct Launch",
    },
    "page.z2_control.section.program_settings": {
        "ru": "Настройки программы",
        "en": "Program Settings",
    },
    "page.z2_control.section.advanced_settings": {
        "ru": "Дополнительные настройки",
        "en": "Advanced Settings",
    },
    "page.z2_control.section.additional": {
        "ru": "Дополнительно",
        "en": "Additional",
    },
    "page.z2_control.status.checking": {
        "ru": "Проверка...",
        "en": "Checking...",
    },
    "page.z2_control.status.detecting": {
        "ru": "Определение состояния процесса",
        "en": "Detecting process state",
    },
    "page.z2_control.status.running": {
        "ru": "Zapret работает",
        "en": "Zapret is running",
    },
    "page.z2_control.status.stopped": {
        "ru": "Zapret остановлен",
        "en": "Zapret stopped",
    },
    "page.z2_control.status.bypass_active": {
        "ru": "Обход блокировок активен",
        "en": "Bypass is active",
    },
    "page.z2_control.status.press_start": {
        "ru": "Нажмите «Запустить» для активации",
        "en": "Press Start to activate",
    },
    "page.z2_control.button.start": {
        "ru": "Запустить Zapret",
        "en": "Start Zapret",
    },
    "page.z2_control.button.stop_only_winws": {
        "ru": "Остановить только winws.exe",
        "en": "Stop only winws.exe",
    },
    "page.z2_control.button.stop_only_template": {
        "ru": "Остановить только {exe_name}",
        "en": "Stop only {exe_name}",
    },
    "page.z2_control.button.stop_and_exit": {
        "ru": "Остановить и закрыть программу",
        "en": "Stop and close app",
    },
    "page.z2_control.button.my_presets": {
        "ru": "Мои пресеты",
        "en": "My presets",
    },
    "page.z2_control.button.open": {
        "ru": "Открыть",
        "en": "Open",
    },
    "page.z2_control.button.change_mode": {
        "ru": "Изменить режим",
        "en": "Change mode",
    },
    "page.z2_control.direct_mode.caption": {
        "ru": "Режим прямого запуска",
        "en": "Direct launch mode",
    },
    "page.z2_control.mode.basic": {
        "ru": "Basic",
        "en": "Basic",
    },
    "page.z2_control.mode.advanced": {
        "ru": "Advanced",
        "en": "Advanced",
    },
    "page.z2_control.preset.not_selected": {
        "ru": "Не выбран",
        "en": "Not selected",
    },
    "page.z2_control.preset.no_active_lists": {
        "ru": "Нет активных листов",
        "en": "No active lists",
    },
    "page.z2_control.preset.current": {
        "ru": "Текущий выбранный source-пресет",
        "en": "Current selected source preset",
    },
    "page.z2_control.card.advanced": {
        "ru": "ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ",
        "en": "ADVANCED SETTINGS",
    },
    "page.z2_control.advanced.warning": {
        "ru": "⚠ Изменяйте только если знаете что делаете",
        "en": "⚠ Change only if you know what you are doing",
    },
    "page.z2_control.blobs.title": {
        "ru": "Блобы",
        "en": "Blobs",
    },
    "page.z2_control.blobs.desc": {
        "ru": "Бинарные данные (.bin / hex) для стратегий",
        "en": "Binary data (.bin / hex) for strategies",
    },
    "page.z2_control.button.connection_test": {
        "ru": "Тест соединения",
        "en": "Connection Test",
    },
    "page.z2_control.button.open_folder": {
        "ru": "Открыть папку",
        "en": "Open Folder",
    },
    "page.z2_control.button.documentation": {
        "ru": "Документация",
        "en": "Documentation",
    },
    "page.z2_direct.title": {
        "ru": "Прямой запуск Zapret 2",
        "en": "Direct Launch Zapret 2",
    },
    "page.z2_direct.back.control": {
        "ru": "Управление",
        "en": "Control",
    },
    "page.z2_direct.current.not_selected": {
        "ru": "Не выбрана",
        "en": "Not selected",
    },
    "page.z2_direct.request.button": {
        "ru": "ОТКРЫТЬ ФОРМУ НА GITHUB",
        "en": "OPEN GITHUB FORM",
    },
    "page.z2_direct.toolbar.expand": {
        "ru": "Развернуть",
        "en": "Expand",
    },
    "page.z2_direct.toolbar.collapse": {
        "ru": "Свернуть",
        "en": "Collapse",
    },
    "page.z2_direct.toolbar.info": {
        "ru": "Что это такое?",
        "en": "What is this?",
    },
    "page.z2_direct.info.title": {
        "ru": "Прямой запуск Zapret 2",
        "en": "Direct Launch Zapret 2",
    },
    "page.z2_user_presets.title": {
        "ru": "Мои пресеты",
        "en": "My Presets",
    },
    "page.z2_user_presets.back.control": {
        "ru": "Управление",
        "en": "Control",
    },
    "page.z2_user_presets.configs.title": {
        "ru": "Обменивайтесь пресетами и категориями в разделе GitHub Discussions",
        "en": "Share presets and categories in GitHub Discussions",
    },
    "page.z2_user_presets.configs.button": {
        "ru": "Получить конфиги",
        "en": "Get configs",
    },
    "page.z2_user_presets.button.restore_deleted": {
        "ru": "Восстановить удалённые пресеты",
        "en": "Restore deleted presets",
    },
    "page.z2_user_presets.button.import": {
        "ru": "Импорт",
        "en": "Import",
    },
    "page.z2_user_presets.button.reset_all": {
        "ru": "Вернуть заводские",
        "en": "Restore defaults",
    },
    "page.z2_user_presets.button.wiki": {
        "ru": "Вики по пресетам",
        "en": "Preset wiki",
    },
    "page.z2_user_presets.button.what_is_this": {
        "ru": "Что это такое?",
        "en": "What is this?",
    },
    "page.z2_user_presets.search.placeholder": {
        "ru": "Поиск пресетов по имени...",
        "en": "Search presets by name...",
    },
    "page.z2_user_presets.tooltip.create": {
        "ru": "Создать новый пресет",
        "en": "Create a new preset",
    },
    "page.z2_user_presets.tooltip.import": {
        "ru": "Импорт пресета из файла",
        "en": "Import preset from file",
    },
    "page.z2_user_presets.tooltip.reset_all": {
        "ru": "Восстанавливает стандартные пресеты. Ваши изменения в стандартных пресетах будут потеряны.",
        "en": "Restores default presets. Your changes to default presets will be lost.",
    },
    "page.z2_user_presets.delegate.tooltip.rename": {
        "ru": "Переименовать",
        "en": "Rename",
    },
    "page.z2_user_presets.delegate.tooltip.duplicate": {
        "ru": "Дублировать",
        "en": "Duplicate",
    },
    "page.z2_user_presets.delegate.tooltip.reset": {
        "ru": "Сбросить",
        "en": "Reset",
    },
    "page.z2_user_presets.delegate.tooltip.delete": {
        "ru": "Удалить",
        "en": "Delete",
    },
    "page.z2_user_presets.delegate.tooltip.export": {
        "ru": "Экспорт",
        "en": "Export",
    },
    "page.z2_user_presets.delegate.tooltip.confirm_again": {
        "ru": "Нажмите ещё раз для подтверждения",
        "en": "Click again to confirm",
    },
    "page.z2_user_presets.delegate.badge.active": {
        "ru": "Активен",
        "en": "Active",
    },
    "page.z2_user_presets.dialog.button.cancel": {
        "ru": "Отмена",
        "en": "Cancel",
    },
    "page.z2_user_presets.dialog.reset_single.title": {
        "ru": "Сбросить пресет?",
        "en": "Reset preset?",
    },
    "page.z2_user_presets.dialog.reset_single.body": {
        "ru": "Пресет '{name}' будет перезаписан данными из шаблона.\nВсе изменения в этом пресете будут потеряны.\nЭтот пресет станет активным и будет применен заново.",
        "en": "Preset '{name}' will be overwritten with template data.\nAll changes in this preset will be lost.\nThis preset will become active and be applied again.",
    },
    "page.z2_user_presets.dialog.reset_single.button": {
        "ru": "Сбросить",
        "en": "Reset",
    },
    "page.z2_user_presets.dialog.delete_single.title": {
        "ru": "Удалить пресет?",
        "en": "Delete preset?",
    },
    "page.z2_user_presets.dialog.delete_single.body": {
        "ru": "Пресет '{name}' будет удален из списка пользовательских пресетов.\nИзменения в этом пресете будут потеряны.\nВернуть его можно только через восстановление удаленных пресетов (если доступен шаблон).",
        "en": "Preset '{name}' will be removed from the user presets list.\nChanges in this preset will be lost.\nYou can restore it only via deleted presets restore (if a template exists).",
    },
    "page.z2_user_presets.dialog.delete_single.button": {
        "ru": "Удалить",
        "en": "Delete",
    },
    "page.z2_user_presets.dialog.create.title": {
        "ru": "Новый пресет",
        "en": "New preset",
    },
    "page.z2_user_presets.dialog.create.subtitle": {
        "ru": "Сохраните текущие настройки как отдельный пресет, чтобы быстро переключаться между конфигурациями.",
        "en": "Save current settings as a separate preset to switch between configurations quickly.",
    },
    "page.z2_user_presets.dialog.create.name": {
        "ru": "Название",
        "en": "Name",
    },
    "page.z2_user_presets.dialog.create.placeholder": {
        "ru": "Например: Игры / YouTube / Дом",
        "en": "For example: Games / YouTube / Home",
    },
    "page.z2_user_presets.dialog.create.source": {
        "ru": "Создать на основе",
        "en": "Create from",
    },
    "page.z2_user_presets.dialog.create.source.current": {
        "ru": "Текущего активного",
        "en": "Current active",
    },
    "page.z2_user_presets.dialog.create.source.empty": {
        "ru": "Пустого",
        "en": "Empty",
    },
    "page.z2_user_presets.dialog.create.button.create": {
        "ru": "Создать",
        "en": "Create",
    },
    "page.z2_user_presets.dialog.rename.title": {
        "ru": "Переименовать",
        "en": "Rename",
    },
    "page.z2_user_presets.dialog.rename.subtitle": {
        "ru": "Имя пресета отображается в списке и используется для переключения.",
        "en": "Preset name is shown in the list and used for switching.",
    },
    "page.z2_user_presets.dialog.rename.current_name": {
        "ru": "Текущее имя: {name}",
        "en": "Current name: {name}",
    },
    "page.z2_user_presets.dialog.rename.new_name": {
        "ru": "Новое имя",
        "en": "New name",
    },
    "page.z2_user_presets.dialog.rename.placeholder": {
        "ru": "Новое имя...",
        "en": "New name...",
    },
    "page.z2_user_presets.dialog.rename.button": {
        "ru": "Переименовать",
        "en": "Rename",
    },
    "page.z2_user_presets.dialog.validation.enter_name": {
        "ru": "Введите название.",
        "en": "Enter a name.",
    },
    "page.z2_user_presets.dialog.validation.exists": {
        "ru": "Пресет «{name}» уже существует.",
        "en": "Preset ""{name}"" already exists.",
    },
    "page.z2_user_presets.dialog.import_exists.title": {
        "ru": "Пресет существует",
        "en": "Preset exists",
    },
    "page.z2_user_presets.dialog.import_exists.body": {
        "ru": "Пресет '{name}' уже существует. Импортировать с другим именем?",
        "en": "Preset '{name}' already exists. Import with another name?",
    },
    "page.z2_user_presets.dialog.reset_all.title": {
        "ru": "Вернуть заводские пресеты",
        "en": "Restore default presets",
    },
    "page.z2_user_presets.dialog.reset_all.body": {
        "ru": "Стандартные пресеты будут восстановлены как после установки.\nВаши изменения в стандартных пресетах будут потеряны.\nПользовательские пресеты с другими именами останутся.\nТекущий выбранный source-пресет будет применён заново автоматически.",
        "en": "Default presets will be restored as after installation.\nYour changes to default presets will be lost.\nCustom presets with other names will remain.\nCurrent selected source preset will be re-applied automatically.",
    },
    "page.z2_user_presets.dialog.reset_all.button": {
        "ru": "Вернуть заводские",
        "en": "Restore defaults",
    },
    "page.z2_user_presets.section.games": {
        "ru": "Игры (game filter)",
        "en": "Games (game filter)",
    },
    "page.z2_user_presets.section.all_tcp_udp": {
        "ru": "Все сайты и игры(ALL TCP/UDP)",
        "en": "All sites and games (ALL TCP/UDP)",
    },
    "page.z2_user_presets.empty.not_found": {
        "ru": "Ничего не найдено.",
        "en": "Nothing found.",
    },
    "page.z2_user_presets.empty.none": {
        "ru": "Нет пресетов. Создайте новый или импортируйте из файла.",
        "en": "No presets. Create a new one or import from file.",
    },
    "page.z2_user_presets.error.generic": {
        "ru": "Ошибка: {error}",
        "en": "Error: {error}",
    },
    "page.z2_user_presets.error.create_failed": {
        "ru": "Не удалось создать пресет.",
        "en": "Failed to create preset.",
    },
    "page.z2_user_presets.error.rename_failed": {
        "ru": "Не удалось переименовать пресет.",
        "en": "Failed to rename preset.",
    },
    "page.z2_user_presets.error.activate_failed": {
        "ru": "Не удалось активировать пресет '{name}'",
        "en": "Failed to activate preset '{name}'",
    },
    "page.z2_user_presets.error.duplicate_failed": {
        "ru": "Не удалось дублировать пресет",
        "en": "Failed to duplicate preset",
    },
    "page.z2_user_presets.error.reset_failed": {
        "ru": "Не удалось сбросить пресет к настройкам шаблона",
        "en": "Failed to reset preset to template defaults",
    },
    "page.z2_user_presets.error.delete_failed": {
        "ru": "Не удалось удалить пресет",
        "en": "Failed to delete preset",
    },
    "page.z2_user_presets.error.import_failed": {
        "ru": "Не удалось импортировать пресет",
        "en": "Failed to import preset",
    },
    "page.z2_user_presets.error.import_exception": {
        "ru": "Ошибка импорта: {error}",
        "en": "Import error: {error}",
    },
    "page.z2_user_presets.error.export_failed": {
        "ru": "Не удалось экспортировать пресет",
        "en": "Failed to export preset",
    },
    "page.z2_user_presets.error.restore_deleted": {
        "ru": "Ошибка восстановления: {error}",
        "en": "Restore error: {error}",
    },
    "page.z2_user_presets.error.reset_all_exception": {
        "ru": "Ошибка восстановления пресетов: {error}",
        "en": "Preset restore error: {error}",
    },
    "page.z2_user_presets.error.open_telegram": {
        "ru": "Не удалось открыть страницу пресетов: {error}",
        "en": "Failed to open presets page: {error}",
    },
    "page.z2_user_presets.file_dialog.import_title": {
        "ru": "Импортировать пресет",
        "en": "Import preset",
    },
    "page.z2_user_presets.file_dialog.export_title": {
        "ru": "Экспортировать пресет",
        "en": "Export preset",
    },
    "page.z2_user_presets.infobar.success": {
        "ru": "Успех",
        "en": "Success",
    },
    "page.z2_user_presets.info.exported": {
        "ru": "Пресет экспортирован: {path}",
        "en": "Preset exported: {path}",
    },
    "page.z2_user_presets.info.title": {
        "ru": "Что это такое?",
        "en": "What is this?",
    },
    "page.z2_user_presets.info.body": {
        "ru": "Здесь кнопка для нубов — \"хочу чтобы нажал и всё работало\". Выбираете любой пресет — тыкаете — перезагружаете вкладку и смотрите, что ресурс открывается (или не открывается). Если не открывается — тыкаете на следующий пресет. Также здесь можно создавать, импортировать, экспортировать и переключать пользовательские пресеты.",
        "en": "This section is for simple workflow: pick any preset, apply it, reload the tab and check if the target opens. If not, try the next preset. You can also create, import, export and switch custom presets here.",
    },
    "page.z2_strategy_detail.title": {
        "ru": "Детали стратегии",
        "en": "Strategy Details",
    },
    "page.z2_strategy_detail.subtitle": {
        "ru": "",
        "en": "",
    },
    "page.z2_strategy_detail.args_dialog.title": {
        "ru": "Аргументы стратегии",
        "en": "Strategy arguments",
    },
    "page.z2_strategy_detail.args_dialog.hint": {
        "ru": "Один аргумент на строку. Изменяет только выбранный target.",
        "en": "One argument per line. Applies only to the selected target.",
    },
    "page.z2_strategy_detail.args_dialog.hint.short": {
        "ru": "Один аргумент на строку.",
        "en": "One argument per line.",
    },
    "page.z2_strategy_detail.args_dialog.placeholder": {
        "ru": "Например:\n--dpi-desync=multisplit\n--dpi-desync-split-pos=1",
        "en": "Example:\n--dpi-desync=multisplit\n--dpi-desync-split-pos=1",
    },
    "page.z2_strategy_detail.args_dialog.button.save": {
        "ru": "Сохранить",
        "en": "Save",
    },
    "page.z2_strategy_detail.args_dialog.button.cancel": {
        "ru": "Отмена",
        "en": "Cancel",
    },
    "page.z2_strategy_detail.preset_dialog.create.title": {
        "ru": "Создать пресет",
        "en": "Create preset",
    },
    "page.z2_strategy_detail.preset_dialog.rename.title": {
        "ru": "Переименовать пресет",
        "en": "Rename preset",
    },
    "page.z2_strategy_detail.preset_dialog.rename.current_name": {
        "ru": "Текущее имя: {name}",
        "en": "Current name: {name}",
    },
    "page.z2_strategy_detail.preset_dialog.name_label": {
        "ru": "Название",
        "en": "Name",
    },
    "page.z2_strategy_detail.preset_dialog.name_placeholder": {
        "ru": "Введите название пресета...",
        "en": "Enter preset name...",
    },
    "page.z2_strategy_detail.preset_dialog.button.create": {
        "ru": "Создать",
        "en": "Create",
    },
    "page.z2_strategy_detail.preset_dialog.button.rename": {
        "ru": "Переименовать",
        "en": "Rename",
    },
    "page.z2_strategy_detail.preset_dialog.button.cancel": {
        "ru": "Отмена",
        "en": "Cancel",
    },
    "page.z2_strategy_detail.preset_dialog.error.empty": {
        "ru": "Введите название пресета",
        "en": "Enter preset name",
    },
    "page.z2_strategy_detail.breadcrumb.control": {
        "ru": "Управление",
        "en": "Control",
    },
    "page.z2_strategy_detail.breadcrumb.strategies": {
        "ru": "Прямой запуск Zapret 2",
        "en": "Direct launch Zapret 2",
    },
    "page.z2_strategy_detail.header.category_fallback": {
        "ru": "Target",
        "en": "Target",
    },
    "page.z2_strategy_detail.header.select_category": {
        "ru": "Выберите target",
        "en": "Select a target",
    },
    "page.z2_strategy_detail.back.strategies": {
        "ru": "Прямой запуск Zapret 2",
        "en": "Direct launch Zapret 2",
    },
    "page.z2_strategy_detail.toggle.enable.title": {
        "ru": "Включить обход",
        "en": "Enable bypass",
    },
    "page.z2_strategy_detail.toggle.enable.description": {
        "ru": "Активировать DPI-обход для этого target'а",
        "en": "Enable DPI bypass for this target",
    },
    "page.z2_strategy_detail.filter_mode.title": {
        "ru": "Режим фильтрации",
        "en": "Filtering mode",
    },
    "page.z2_strategy_detail.filter_mode.description": {
        "ru": "Hostlist - по доменам, IPset - по IP",
        "en": "Hostlist by domains, IPset by IP",
    },
    "page.z2_strategy_detail.filter.hostlist": {
        "ru": "Hostlist",
        "en": "Hostlist",
    },
    "page.z2_strategy_detail.filter.ipset": {
        "ru": "IPset",
        "en": "IPset",
    },
    "page.z2_strategy_detail.out_range.mode": {
        "ru": "Режим:",
        "en": "Mode:",
    },
    "page.z2_strategy_detail.out_range.mode.tooltip": {
        "ru": "n = количество пакетов с самого первого, d = отсчитывать ТОЛЬКО количество пакетов с данными",
        "en": "n = count packets from the first one, d = count only packets with payload",
    },
    "page.z2_strategy_detail.out_range.value": {
        "ru": "Значение:",
        "en": "Value:",
    },
    "page.z2_strategy_detail.out_range.value.tooltip": {
        "ru": "--out-range: ограничение количества исходящих пакетов (n) или задержки (d)",
        "en": "--out-range: outgoing packet limit (n) or delay count (d)",
    },
    "page.z2_strategy_detail.search.placeholder": {
        "ru": "Поиск по имени или args...",
        "en": "Search by name or args...",
    },
    "page.z2_strategy_detail.sort.tooltip.short": {
        "ru": "Сортировка",
        "en": "Sort",
    },
    "page.z2_strategy_detail.sort.default": {
        "ru": "По умолчанию",
        "en": "Default",
    },
    "page.z2_strategy_detail.sort.name_asc": {
        "ru": "По имени (А-Я)",
        "en": "By name (A-Z)",
    },
    "page.z2_strategy_detail.sort.name_desc": {
        "ru": "По имени (Я-А)",
        "en": "By name (Z-A)",
    },
    "page.z2_strategy_detail.sort.tooltip": {
        "ru": "Сортировка: {label}",
        "en": "Sort: {label}",
    },
    "page.z2_strategy_detail.filter.technique.all": {
        "ru": "Все техники",
        "en": "All techniques",
    },
    "page.z2_strategy_detail.args.tooltip": {
        "ru": "Аргументы стратегии для выбранного target'а",
        "en": "Strategy arguments for the selected target",
    },
    "page.z2_strategy_detail.subtitle.ports": {
        "ru": "порты: {ports}",
        "en": "ports: {ports}",
    },
    "page.z2_strategy_detail.tree.phase.none.name": {
        "ru": "(без изменений)",
        "en": "(no changes)",
    },
    "page.z2_strategy_detail.tree.phase.none.desc": {
        "ru": "Снять отметку со стратегии (фаза будет пропущена)",
        "en": "Unselect strategy (phase will be skipped)",
    },
    "page.z2_strategy_detail.tree.phase.custom.name": {
        "ru": "Пользовательские аргументы (custom)",
        "en": "Custom arguments (custom)",
    },
    "page.z2_strategy_detail.tree.phase.custom.desc": {
        "ru": "Неизвестные аргументы, загруженные из профиля",
        "en": "Unknown arguments loaded from profile",
    },
    "page.z2_strategy_detail.tree.disabled.name": {
        "ru": "Выключено (без DPI-обхода)",
        "en": "Disabled (no DPI bypass)",
    },
    "page.z2_strategy_detail.tree.disabled.desc": {
        "ru": "Трафик пускается напрямую без модификаций",
        "en": "Traffic passes directly without modifications",
    },
    "page.z2_strategy_detail.infobar.no_strategies.title": {
        "ru": "Нет стратегий",
        "en": "No strategies",
    },
    "page.z2_strategy_detail.infobar.no_strategies.content": {
        "ru": "Для target'а '{category}' не найдено стратегий.",
        "en": "No strategies found for target '{category}'.",
    },
    "page.z2_strategy_detail.infobar.preset.exists.title": {
        "ru": "Уже существует",
        "en": "Already exists",
    },
    "page.z2_strategy_detail.infobar.preset.exists.content": {
        "ru": "Пресет '{name}' уже существует.",
        "en": "Preset '{name}' already exists.",
    },
    "page.z2_strategy_detail.infobar.preset.created.title": {
        "ru": "Пресет создан",
        "en": "Preset created",
    },
    "page.z2_strategy_detail.infobar.preset.created.content": {
        "ru": "Пресет '{name}' создан на основе текущих настроек.",
        "en": "Preset '{name}' was created from current settings.",
    },
    "page.z2_strategy_detail.infobar.preset.create_failed": {
        "ru": "Не удалось создать пресет.",
        "en": "Failed to create preset.",
    },
    "page.z2_strategy_detail.infobar.preset.no_active.title": {
        "ru": "Нет выбранного source-пресета",
        "en": "No selected source preset",
    },
    "page.z2_strategy_detail.infobar.preset.no_active.content": {
        "ru": "Выбранный source-пресет не найден.",
        "en": "Selected source preset was not found.",
    },
    "page.z2_strategy_detail.infobar.preset.renamed.title": {
        "ru": "Переименован",
        "en": "Renamed",
    },
    "page.z2_strategy_detail.infobar.preset.renamed.content": {
        "ru": "Пресет переименован: '{old}' -> '{new}'.",
        "en": "Preset renamed: '{old}' -> '{new}'.",
    },
    "page.z2_strategy_detail.infobar.preset.rename_failed": {
        "ru": "Не удалось переименовать пресет.",
        "en": "Failed to rename preset.",
    },
    "page.z2_strategy_detail.button.create_preset": {
        "ru": "Создать пресет",
        "en": "Create preset",
    },
    "page.z2_strategy_detail.button.create_preset.tooltip": {
        "ru": "Создать новый пресет на основе текущих настроек",
        "en": "Create a new preset from current settings",
    },
    "page.z2_strategy_detail.button.rename_preset": {
        "ru": "Переименовать",
        "en": "Rename",
    },
    "page.z2_strategy_detail.button.rename_preset.tooltip": {
        "ru": "Переименовать текущий выбранный source-пресет",
        "en": "Rename current selected source preset",
    },
    "page.z2_strategy_detail.button.reset_settings": {
        "ru": "Сбросить настройки",
        "en": "Reset settings",
    },
    "page.z2_strategy_detail.button.reset_settings.confirm": {
        "ru": "Сбросить все?",
        "en": "Reset everything?",
    },
    "page.z2_strategy_detail.out_range.title": {
        "ru": "Out Range",
        "en": "Out Range",
    },
    "page.z2_strategy_detail.out_range.description": {
        "ru": "Ограничение исходящих пакетов",
        "en": "Outgoing packet limit",
    },
    "page.z2_strategy_detail.send.toggle.title": {
        "ru": "Send параметры",
        "en": "Send settings",
    },
    "page.z2_strategy_detail.send.toggle.description": {
        "ru": "Отправка копий пакетов",
        "en": "Send packet copies",
    },
    "page.z2_strategy_detail.send.repeats.title": {
        "ru": "repeats",
        "en": "repeats",
    },
    "page.z2_strategy_detail.send.repeats.description": {
        "ru": "Количество повторных отправок",
        "en": "Retry send count",
    },
    "page.z2_strategy_detail.send.ip_ttl.title": {
        "ru": "ip_ttl",
        "en": "ip_ttl",
    },
    "page.z2_strategy_detail.send.ip_ttl.description": {
        "ru": "TTL для IPv4 отправляемых пакетов",
        "en": "TTL for sent IPv4 packets",
    },
    "page.z2_strategy_detail.send.ip6_ttl.title": {
        "ru": "ip6_ttl",
        "en": "ip6_ttl",
    },
    "page.z2_strategy_detail.send.ip6_ttl.description": {
        "ru": "TTL для IPv6 отправляемых пакетов",
        "en": "TTL for sent IPv6 packets",
    },
    "page.z2_strategy_detail.send.ip_id.title": {
        "ru": "ip_id",
        "en": "ip_id",
    },
    "page.z2_strategy_detail.send.ip_id.description": {
        "ru": "Режим IP ID для отправляемых пакетов",
        "en": "IP ID mode for sent packets",
    },
    "page.z2_strategy_detail.send.badsum.title": {
        "ru": "badsum",
        "en": "badsum",
    },
    "page.z2_strategy_detail.send.badsum.description": {
        "ru": "Отправлять пакеты с неправильной контрольной суммой",
        "en": "Send packets with invalid checksum",
    },
    "page.z2_strategy_detail.syndata.toggle.title": {
        "ru": "Syndata параметры",
        "en": "Syndata settings",
    },
    "page.z2_strategy_detail.syndata.toggle.description": {
        "ru": "Дополнительные параметры обхода DPI",
        "en": "Additional DPI bypass settings",
    },
    "page.z2_strategy_detail.syndata.blob.title": {
        "ru": "blob",
        "en": "blob",
    },
    "page.z2_strategy_detail.syndata.blob.description": {
        "ru": "Полезная нагрузка пакета",
        "en": "Packet payload",
    },
    "page.z2_strategy_detail.syndata.tls_mod.title": {
        "ru": "tls_mod",
        "en": "tls_mod",
    },
    "page.z2_strategy_detail.syndata.tls_mod.description": {
        "ru": "Модификация полезной нагрузки TLS",
        "en": "TLS payload modification",
    },
    "page.z2_strategy_detail.syndata.autottl_delta.title": {
        "ru": "AutoTTL Delta",
        "en": "AutoTTL Delta",
    },
    "page.z2_strategy_detail.syndata.autottl_delta.description": {
        "ru": "Смещение от измеренного TTL (OFF = убрать ip_autottl)",
        "en": "Offset from measured TTL (OFF = disable ip_autottl)",
    },
    "page.z2_strategy_detail.syndata.autottl_min.title": {
        "ru": "AutoTTL Min",
        "en": "AutoTTL Min",
    },
    "page.z2_strategy_detail.syndata.autottl_min.description": {
        "ru": "Минимальный TTL",
        "en": "Minimum TTL",
    },
    "page.z2_strategy_detail.syndata.autottl_max.title": {
        "ru": "AutoTTL Max",
        "en": "AutoTTL Max",
    },
    "page.z2_strategy_detail.syndata.autottl_max.description": {
        "ru": "Максимальный TTL",
        "en": "Maximum TTL",
    },
    "page.z2_strategy_detail.syndata.tcp_flags.title": {
        "ru": "tcp_flags_unset",
        "en": "tcp_flags_unset",
    },
    "page.z2_strategy_detail.syndata.tcp_flags.description": {
        "ru": "Сбросить TCP флаги",
        "en": "Unset TCP flags",
    },
    "page.ipset.title": {
        "ru": "IPset",
        "en": "IPset",
    },
    "page.ipset.subtitle": {
        "ru": "Управление IP-адресами и подсетями",
        "en": "Manage IP addresses and subnets",
    },
    "page.ipset.description": {
        "ru": "IP-сеты содержат IP-адреса и подсети для обхода блокировок по IP.\nИспользуются когда блокировка происходит на уровне IP-адресов.",
        "en": "IP sets contain IP addresses and subnets for IP-based bypass.\nUsed when blocking happens at the IP-address level.",
    },
    "page.ipset.section.actions": {
        "ru": "Действия",
        "en": "Actions",
    },
    "page.ipset.open_folder.label": {
        "ru": "Открыть папку IP-сетов",
        "en": "Open IP sets folder",
    },
    "page.ipset.button.open": {
        "ru": "Открыть",
        "en": "Open",
    },
    "page.ipset.section.info": {
        "ru": "Информация",
        "en": "Information",
    },
    "page.ipset.files.loading": {
        "ru": "Загрузка информации...",
        "en": "Loading information...",
    },
    "page.ipset.files.not_found": {
        "ru": "Папка не найдена",
        "en": "Folder not found",
    },
    "page.ipset.files.summary": {
        "ru": "📁 Папка: {folder}\n📄 IP-файлов: {files_count}\n🌐 Примерно IP/подсетей: {total_ips}",
        "en": "📁 Folder: {folder}\n📄 IP files: {files_count}\n🌐 Approx. IPs/subnets: {total_ips}",
    },
    "page.ipset.files.error": {
        "ru": "Ошибка загрузки информации: {error}",
        "en": "Failed to load information: {error}",
    },
    "page.ipset.error.open_folder": {
        "ru": "Не удалось открыть папку:\n{error}",
        "en": "Failed to open folder:\n{error}",
    },
    "page.strategy_sort.title": {
        "ru": "Сортировка",
        "en": "Sorting",
    },
    "page.strategy_sort.subtitle": {
        "ru": "Фильтры и сортировка стратегий",
        "en": "Strategy filters and sorting",
    },
    "page.strategy_sort.section.strategy_type.title": {
        "ru": "Тип стратегии",
        "en": "Strategy type",
    },
    "page.strategy_sort.section.strategy_type.desc": {
        "ru": "Выберите тип стратегии для фильтрации",
        "en": "Choose strategy type for filtering",
    },
    "page.strategy_sort.section.desync.title": {
        "ru": "Техника обхода",
        "en": "Bypass technique",
    },
    "page.strategy_sort.section.desync.desc": {
        "ru": "Можно выбрать несколько техник одновременно",
        "en": "You can choose multiple techniques at once",
    },
    "page.strategy_sort.section.sort.title": {
        "ru": "Сортировка",
        "en": "Sorting",
    },
    "page.strategy_sort.section.sort.desc": {
        "ru": "Порядок отображения стратегий в списке",
        "en": "Display order of strategies in the list",
    },
    "page.strategy_sort.option.all": {
        "ru": "Все",
        "en": "All",
    },
    "page.strategy_sort.option.recommended": {
        "ru": "Рекоменд.",
        "en": "Recomm.",
    },
    "page.strategy_sort.option.experimental": {
        "ru": "Эксперим.",
        "en": "Experim.",
    },
    "page.strategy_sort.option.game": {
        "ru": "Игровые",
        "en": "Gaming",
    },
    "page.strategy_sort.option.deprecated": {
        "ru": "Устаревш.",
        "en": "Deprecated",
    },
    "page.strategy_sort.option.fake": {
        "ru": "Fake",
        "en": "Fake",
    },
    "page.strategy_sort.option.split": {
        "ru": "Split",
        "en": "Split",
    },
    "page.strategy_sort.option.syn": {
        "ru": "SYN",
        "en": "SYN",
    },
    "page.strategy_sort.option.http": {
        "ru": "HTTP",
        "en": "HTTP",
    },
    "page.strategy_sort.option.rst": {
        "ru": "RST",
        "en": "RST",
    },
    "page.strategy_sort.option.wsize": {
        "ru": "WSize",
        "en": "WSize",
    },
    "page.strategy_sort.option.default": {
        "ru": "По умолчанию",
        "en": "Default",
    },
    "page.strategy_sort.option.name_asc": {
        "ru": "А-Я",
        "en": "A-Z",
    },
    "page.strategy_sort.option.name_desc": {
        "ru": "Я-А",
        "en": "Z-A",
    },
    "page.strategy_sort.option.rating": {
        "ru": "Рейтинг",
        "en": "Rating",
    },
    "tab.diagnostics.connection": {
        "ru": "Диагностика соединения",
        "en": "Connection Diagnostics",
    },
    "tab.diagnostics.dns": {
        "ru": "DNS подмена",
        "en": "DNS Spoofing",
    },
    "tab.orchestra.locked": {
        "ru": "Залоченные",
        "en": "Locked",
    },
    "tab.orchestra.blocked": {
        "ru": "Заблокированные",
        "en": "Blocked",
    },
    "tab.orchestra.whitelist": {
        "ru": "Белый список",
        "en": "Whitelist",
    },
    "tab.orchestra.ratings": {
        "ru": "Рейтинги",
        "en": "Ratings",
    },
    "appearance.language.section": {
        "ru": "Язык интерфейса",
        "en": "Interface Language",
    },
    "appearance.language.desc": {
        "ru": "Язык бокового меню и глобального поиска. Полный перевод страниц расширяется поэтапно.",
        "en": "Language for sidebar and global search. Full page translation is being expanded step by step.",
    },
    "appearance.language.label": {
        "ru": "Язык",
        "en": "Language",
    },
}


TEXTS_EXTRA: dict[str, dict[str, str]] = {
    "page.blockcheck.domains_section": {
        "ru": "Часть 1: Проверка доменов (TLS + HTTP injection)",
        "en": "Part 1: Domain Checks (TLS + HTTP injection)",
    },
    "page.blockcheck.col_dns_isp": {
        "ru": "DNS/ISP",
        "en": "DNS/ISP",
    },
    "page.blockcheck.tcp_section": {
        "ru": "Часть 2: Проверка TCP 16-20KB",
        "en": "Part 2: TCP 16-20KB Checks",
    },
    "page.blockcheck.col_provider": {
        "ru": "Провайдер",
        "en": "Provider",
    },
    "page.blockcheck.col_status": {
        "ru": "Статус",
        "en": "Status",
    },
    "page.blockcheck.col_error_details": {
        "ru": "Ошибка / Детали",
        "en": "Error / Details",
    },
    "page.blockcheck.warning": {
        "ru": "Предупреждение",
        "en": "Warning",
    },
    "page.blockcheck.col_details": {
        "ru": "Детали",
        "en": "Details",
    },
    "page.control.button.stop_only_template": {
        "ru": "Остановить только {exe_name}",
        "en": "Stop only {exe_name}",
    },
    "page.control.strategy.more_template": {
        "ru": "+{count} ещё",
        "en": "+{count} more",
    },
    "page.strategy_scan.title": {
        "ru": "Подбор стратегии",
        "en": "Strategy Scanner",
    },
    "page.strategy_scan.subtitle": {
        "ru": "Автоматический перебор стратегий обхода DPI",
        "en": "Automatic scan of DPI bypass strategies",
    },
    "page.strategy_scan.back": {
        "ru": "Назад",
        "en": "Back",
    },
    "page.strategy_scan.control": {
        "ru": "Управление сканированием",
        "en": "Scan Controls",
    },
    "page.strategy_scan.protocol": {
        "ru": "Протокол:",
        "en": "Protocol:",
    },
    "page.strategy_scan.protocol_tcp": {
        "ru": "TCP/HTTPS",
        "en": "TCP/HTTPS",
    },
    "page.strategy_scan.protocol_stun": {
        "ru": "STUN Voice (Discord/Telegram)",
        "en": "STUN Voice (Discord/Telegram)",
    },
    "page.strategy_scan.protocol_games": {
        "ru": "UDP Games (Roblox/Amazon/Steam)",
        "en": "UDP Games (Roblox/Amazon/Steam)",
    },
    "page.strategy_scan.udp_scope": {
        "ru": "Охват UDP:",
        "en": "UDP Scope:",
    },
    "page.strategy_scan.udp_scope_all": {
        "ru": "Все ipset (по умолчанию)",
        "en": "All ipset (default)",
    },
    "page.strategy_scan.udp_scope_games_only": {
        "ru": "Только игровые ipset",
        "en": "Games-only ipset",
    },
    "page.strategy_scan.mode": {
        "ru": "Режим:",
        "en": "Mode:",
    },
    "page.strategy_scan.mode_quick": {
        "ru": "Быстрый (30)",
        "en": "Quick (30)",
    },
    "page.strategy_scan.mode_standard": {
        "ru": "Стандартный (80)",
        "en": "Standard (80)",
    },
    "page.strategy_scan.mode_full": {
        "ru": "Полный (все)",
        "en": "Full (all)",
    },
    "page.strategy_scan.target": {
        "ru": "Цель:",
        "en": "Target:",
    },
    "page.strategy_scan.target.default": {
        "ru": "discord.com",
        "en": "discord.com",
    },
    "page.strategy_scan.target.placeholder": {
        "ru": "discord.com",
        "en": "discord.com",
    },
    "page.strategy_scan.quick_domains": {
        "ru": "Быстрый выбор",
        "en": "Quick Pick",
    },
    "page.strategy_scan.quick_domains_hint": {
        "ru": "Выберите домен из готового списка",
        "en": "Choose a domain from the preset list",
    },
    "page.strategy_scan.start": {
        "ru": "Начать сканирование",
        "en": "Start Scan",
    },
    "page.strategy_scan.stop": {
        "ru": "Остановить",
        "en": "Stop",
    },
    "page.strategy_scan.ready": {
        "ru": "Готово к сканированию",
        "en": "Ready to scan",
    },
    "page.strategy_scan.warning_title": {
        "ru": "Внимание",
        "en": "Attention",
    },
    "page.strategy_scan.warning_text": {
        "ru": "Во время сканирования текущий обход DPI будет остановлен. Каждая стратегия тестируется отдельно через winws2. После завершения можно перезапустить обход.",
        "en": "During scanning, the current DPI bypass will be stopped. Each strategy is tested separately through winws2. You can restart bypass after the scan finishes.",
    },
    "page.strategy_scan.results": {
        "ru": "Результаты",
        "en": "Results",
    },
    "page.strategy_scan.col_strategy": {
        "ru": "Стратегия",
        "en": "Strategy",
    },
    "page.strategy_scan.col_status": {
        "ru": "Статус",
        "en": "Status",
    },
    "page.strategy_scan.col_time": {
        "ru": "Время (мс)",
        "en": "Time (ms)",
    },
    "page.strategy_scan.col_action": {
        "ru": "Действие",
        "en": "Action",
    },
    "page.strategy_scan.log": {
        "ru": "Подробный лог",
        "en": "Detailed Log",
    },
    "page.strategy_scan.starting": {
        "ru": "Запуск сканирования...",
        "en": "Starting scan...",
    },
    "page.strategy_scan.stopping": {
        "ru": "Остановка...",
        "en": "Stopping...",
    },
    "page.strategy_scan.apply": {
        "ru": "Применить",
        "en": "Apply",
    },
    "page.strategy_scan.error": {
        "ru": "Ошибка сканирования",
        "en": "Scan error",
    },
    "page.strategy_scan.baseline_ok_title_stun": {
        "ru": "STUN/UDP уже доступен",
        "en": "STUN/UDP already reachable",
    },
    "page.strategy_scan.baseline_ok_text_stun": {
        "ru": "STUN/UDP уже доступен без обхода DPI — результаты могут быть ложноположительными",
        "en": "STUN/UDP is already reachable without DPI bypass - results may be false positives",
    },
    "page.strategy_scan.baseline_ok_title": {
        "ru": "Домен уже доступен",
        "en": "Domain is already reachable",
    },
    "page.strategy_scan.baseline_ok_text": {
        "ru": "Домен доступен без обхода DPI — результаты могут быть ложноположительными",
        "en": "Domain is reachable without DPI bypass - results may be false positives",
    },
    "page.strategy_scan.found": {
        "ru": "Найдены рабочие стратегии",
        "en": "Working strategies found",
    },
    "page.strategy_scan.not_found": {
        "ru": "Рабочих стратегий не найдено",
        "en": "No working strategies found",
    },
    "page.strategy_scan.try_full": {
        "ru": "Попробуйте полный режим сканирования",
        "en": "Try full scan mode",
    },
    "page.strategy_scan.applied": {
        "ru": "Стратегия добавлена",
        "en": "Strategy added",
    },
    "page.z1_direct.empty.no_categories": {
        "ru": "Категории не найдены. Проверьте наличие json/strategies/builtin/categories.txt",
        "en": "No categories found. Check json/strategies/builtin/categories.txt",
    },
    "page.z2_direct.request.hint": {
        "ru": "Хотите добавить новый сайт или сервис в Zapret 2? Откройте готовую форму на GitHub и опишите, что нужно добавить в hostlist или ipset.",
        "en": "Want to add a new site or service to Zapret 2? Open the GitHub form and describe what should be added to the hostlist or ipset.",
    },
    "page.z2_direct.empty.no_presets": {
        "ru": "Пресеты Zapret 2 не найдены. Обычно здесь должны быть txt-файлы в %APPDATA%\\zapret\\presets_v2. Если папка пустая, встроенные пресеты не были скопированы или были удалены.",
        "en": "Zapret 2 presets were not found. Normally txt files should exist in %APPDATA%\\zapret\\presets_v2. If the folder is empty, built-in presets were not copied or were removed.",
    },
    "page.z2_direct.empty.no_selected_preset": {
        "ru": "Не удалось определить выбранный source preset. Откройте список пресетов, выберите любой пресет заново и нажмите «Обновить».",
        "en": "Could not determine the selected source preset. Open the preset list, choose any preset again, and click Refresh.",
    },
    "page.z2_direct.empty.preset_read_error": {
        "ru": "Не удалось прочитать выбранный source preset «{preset_name}». Такое бывает, если файл пустой, повреждён или недоступен для чтения.",
        "en": "Could not read the selected source preset \"{preset_name}\". This may happen if the file is empty, corrupted, or unavailable for reading.",
    },
    "page.z2_direct.empty.no_categories": {
        "ru": "В выбранном source preset «{preset_name}» не найдено ни одной категории для этой страницы. Это значит, что после разбора файла программа не увидела ни одного target'а с фильтрами вроде hostlist, hostlist-domains или ipset.",
        "en": "No categories were found for this page in the selected source preset \"{preset_name}\". This means that after parsing the file, the app did not find any target with filters such as hostlist, hostlist-domains, or ipset.",
    },
    "page.z2_direct.current.active_count": {
        "ru": "{count} активных",
        "en": "{count} active",
    },
    "page.z2_direct.info.body": {
        "ru": "Здесь Вы можете тонко изменить стратегию для каждого target'а, который найден в выбранном source preset. Всего существует несколько фаз дурения (send, syndata, fake, multisplit и т.д.). Последовательность сама определяется программой.\n\nВы можете править пресет вручную через txt-файл или выбирать готовые стратегии в этом меню. Каждая стратегия — это набор аргументов, то есть техник дурения или фуллинга, которые меняют содержимое пакетов по модели TCP/IP, отправляемых вашим устройством. Это помогает сбить алгоритмы ТСПУ провайдера, чтобы они не заметили или пропустили запрещённый контент.",
        "en": "Here you can finely tune the strategy for each target found in the selected source preset. There are several obfuscation phases (send, syndata, fake, multisplit, etc.). Their sequence is determined by the app.\n\nYou can edit the preset manually in a txt file or choose ready-made strategies in this menu. Each strategy is a set of arguments, i.e. packet manipulation techniques used to alter TCP/IP traffic sent by your device. This helps confuse provider TSPU algorithms so they do not detect or block restricted content.",
    },
}

TEXTS.update(TEXTS_EXTRA)


TEXTS_PAGES_FINAL: dict[str, dict[str, str]] = {
    "page.about.app_name": {
        "ru": "Zapret 2 GUI",
        "en": "Zapret 2 GUI",
    },
    "common.badge.premium": {
        "ru": "⭐ Premium",
        "en": "⭐ Premium",
    },
    "common.toggle.on_off": {
        "ru": "Вкл/Выкл",
        "en": "On/Off",
    },
    "page.appearance.display_mode.description": {
        "ru": "Выберите светлый или тёмный режим интерфейса.",
        "en": "Choose light or dark interface mode.",
    },
    "page.appearance.display_mode.option.dark": {
        "ru": "🌙 Тёмный",
        "en": "🌙 Dark",
    },
    "page.appearance.display_mode.option.light": {
        "ru": "☀️ Светлый",
        "en": "☀️ Light",
    },
    "page.appearance.display_mode.option.system": {
        "ru": "⚙ Авто",
        "en": "⚙ Auto",
    },
    "page.appearance.background.description": {
        "ru": "Стандартный фон соответствует режиму отображения. AMOLED и РКН Тян доступны подписчикам Premium. Для РКН Тян можно выбрать готовый фон из списка.",
        "en": "The default background follows display mode. AMOLED and RKN Chan are available for Premium subscribers. For RKN Chan you can choose a ready background from the list.",
    },
    "page.appearance.background.option.standard": {
        "ru": "Стандартный",
        "en": "Standard",
    },
    "page.appearance.background.option.amoled": {
        "ru": "AMOLED — чёрный",
        "en": "AMOLED - black",
    },
    "page.appearance.background.option.rkn_chan": {
        "ru": "РКН Тян",
        "en": "RKN Chan",
    },
    "page.appearance.background.rkn.label": {
        "ru": "Фон РКН Тян",
        "en": "RKN Chan Background",
    },
    "page.appearance.background.rkn.none": {
        "ru": "Фоны не найдены",
        "en": "No backgrounds found",
    },
    "page.appearance.holiday.garland.description": {
        "ru": "Праздничная гирлянда с мерцающими огоньками в верхней части окна. Доступно только для подписчиков Premium.",
        "en": "Festive garland with blinking lights at the top of the window. Available only for Premium subscribers.",
    },
    "page.appearance.holiday.garland.title": {
        "ru": "Новогодняя гирлянда",
        "en": "Holiday Garland",
    },
    "page.appearance.holiday.snowflakes.description": {
        "ru": "Мягко падающие снежинки по всему окну. Создаёт уютную зимнюю атмосферу.",
        "en": "Soft falling snowflakes across the window. Creates a cozy winter atmosphere.",
    },
    "page.appearance.holiday.snowflakes.title": {
        "ru": "Снежинки",
        "en": "Snowflakes",
    },
    "page.appearance.opacity.win11.title": {
        "ru": "Эффект акрилика окна",
        "en": "Window Acrylic Effect",
    },
    "page.appearance.opacity.win11.description": {
        "ru": "Настройка интенсивности акрилового эффекта всего окна приложения. При 0% эффект минимальный, при 100% — максимальный.",
        "en": "Adjust acrylic effect intensity for the entire app window. At 0% the effect is minimal, at 100% maximal.",
    },
    "page.appearance.opacity.legacy.title": {
        "ru": "Прозрачность окна",
        "en": "Window Opacity",
    },
    "page.appearance.opacity.legacy.description": {
        "ru": "Настройка прозрачности всего окна приложения. При 0% окно полностью прозрачное, при 100% — непрозрачное.",
        "en": "Adjust opacity of the entire app window. At 0% the window is fully transparent, at 100% fully opaque.",
    },
    "page.appearance.accent.description": {
        "ru": "Цвет акцентных элементов интерфейса: кнопок, иконок, индикаторов. Изменяет цвет нативных компонентов WinUI.",
        "en": "Accent color for interface elements: buttons, icons, indicators. Changes native WinUI component color.",
    },
    "page.appearance.accent.color.title": {
        "ru": "Цвет акцента",
        "en": "Accent Color",
    },
    "page.appearance.accent.color.pick": {
        "ru": "Выбрать цвет",
        "en": "Pick Color",
    },
    "page.appearance.accent.windows.title": {
        "ru": "Акцент из Windows",
        "en": "Use Windows Accent",
    },
    "page.appearance.accent.windows.description": {
        "ru": "Автоматически использовать системный акцентный цвет Windows",
        "en": "Automatically use the system Windows accent color",
    },
    "page.appearance.accent.tint_background.title": {
        "ru": "Тонировать фон акцентным цветом",
        "en": "Tint Background with Accent",
    },
    "page.appearance.accent.tint_background.description": {
        "ru": "Фон окна окрашивается в оттенок акцентного цвета",
        "en": "Window background is tinted by accent color",
    },
    "page.appearance.accent.tint_intensity.label": {
        "ru": "Интенсивность тонировки:",
        "en": "Tint Intensity:",
    },
    "page.appearance.performance.animations.title": {
        "ru": "Анимации интерфейса",
        "en": "Interface Animations",
    },
    "page.appearance.performance.animations.description": {
        "ru": "Анимации кнопок, переходов и элементов WinUI",
        "en": "Animations for buttons, transitions, and WinUI elements",
    },
    "page.appearance.performance.scroll.title": {
        "ru": "Плавная прокрутка",
        "en": "Smooth Scrolling",
    },
    "page.appearance.performance.scroll.description": {
        "ru": "Инерционная прокрутка страниц настроек",
        "en": "Inertial scrolling on settings pages",
    },
    "page.appearance.performance.editor_scroll.title": {
        "ru": "Плавная прокрутка редакторов",
        "en": "Editor Smooth Scrolling",
    },
    "page.appearance.performance.editor_scroll.description": {
        "ru": "Плавная прокрутка внутри больших текстовых полей и редакторов. Работает только при включённых анимациях интерфейса.",
        "en": "Smooth scrolling inside large text fields and editors. Works only when interface animations are enabled.",
    },
    "page.control.dialog.defender_disable.title": {
        "ru": "Отключение Windows Defender",
        "en": "Disable Windows Defender",
    },
    "page.control.dialog.defender_enable.title": {
        "ru": "Включение Windows Defender",
        "en": "Enable Windows Defender",
    },
    "page.control.dialog.max_block_enable.title": {
        "ru": "Блокировка MAX",
        "en": "Enable MAX Blocking",
    },
    "page.control.dialog.max_block_disable.title": {
        "ru": "Отключение блокировки MAX",
        "en": "Disable MAX Blocking",
    },
    "page.logs.info.winws_cleared": {
        "ru": "🧹 Вывод winws очищен",
        "en": "🧹 winws output cleared",
    },
    "page.logs.info.copied": {
        "ru": "✅ Скопировано в буфер обмена",
        "en": "✅ Copied to clipboard",
    },
    "page.logs.info.empty": {
        "ru": "⚠️ Лог пуст",
        "en": "⚠️ Log is empty",
    },
    "page.logs.info.view_cleared": {
        "ru": "🧹 Вид очищен",
        "en": "🧹 View cleared",
    },
    "page.logs.info.errors_cleared": {
        "ru": "🧹 Ошибки очищены",
        "en": "🧹 Errors cleared",
    },
    "page.strategies_base.title": {
        "ru": "Выбор активных стратегий (и их настройка) Zapret 2",
        "en": "Select Active Strategies (and tune them) for Zapret 2",
    },
    "page.strategies_base.subtitle": {
        "ru": "Для каждой категории (доменов внутри хостлиста или айпишников внутри айпсета) можно выбрать свою стратегию для обхода блокировок. Список всех статегий для каждой категории одинаковый, отличается только по типу трафика (TCP, UDP, stun). Некоторые типы дурения (например send или syndata) можно настроить более точечно чтобы получить больше уникальных стратегий, исходя из того как работает ваше ТСПУ.",
        "en": "For each category (domains in hostlist or IPs in ipset) you can select a separate bypass strategy. The list of strategies is the same for each category and differs only by traffic type (TCP, UDP, STUN). Some techniques (for example send or syndata) can be tuned more precisely to get more unique strategies based on your provider filtering behavior.",
    },
    "page.strategies_base.current_prefix": {
        "ru": "Текущая:",
        "en": "Current:",
    },
    "page.strategies_base.strategy.not_selected": {
        "ru": "Не выбрана",
        "en": "Not selected",
    },
    "page.strategies_base.loading": {
        "ru": "Загрузка...",
        "en": "Loading...",
    },
    "page.strategies_base.strategy.autostart_disabled": {
        "ru": "Автостарт DPI отключен",
        "en": "Autostart DPI is disabled",
    },
    "page.z2_control.mode.dialog.title": {
        "ru": "Режим прямого запуска",
        "en": "Direct Launch Mode",
    },
    "page.z2_control.mode.dialog.description": {
        "ru": "Прямой запуск поддерживает несколько режимов: упрощенный и расширенный для профи. Настройки не сохраняются между режимами Вы можете выбрать любой. Рекомендуем начать с базового. Бывает что базовый из-за готовых стратегий плохо пробивает сайты, тогда рекомендуем попробовать продвинутый в котором можно более тонко настроить техники дурения.",
        "en": "Direct launch supports multiple modes: simplified and advanced for power users. Settings are not shared across modes, so you can choose any mode. We recommend starting with Basic. If Basic does not bypass enough sites, try Advanced for finer technique tuning.",
    },
    "page.z2_control.mode.dialog.basic_description": {
        "ru": "Basic (базовый) — готовая таблица стратегий без понятия фаз. Собирать свои стратегии нельзя.",
        "en": "Basic mode is a ready strategy table without phase-level tuning. Custom strategy composition is not available.",
    },
    "page.z2_control.mode.dialog.advanced_description": {
        "ru": "Advanced (продвинутый) — каждая функция настраивается индивидуально, можно выбирать несколько фаз и смешивать их друг с другом.",
        "en": "Advanced mode allows per-function tuning, selecting multiple phases, and combining them.",
    },
    "page.z2_control.mode.dialog.button.apply": {
        "ru": "Применить",
        "en": "Apply",
    },
    "page.z2_control.mode.dialog.button.cancel": {
        "ru": "Отмена",
        "en": "Cancel",
    },
    "page.z2_control.setting.autostart.title": {
        "ru": "Автозагрузка DPI",
        "en": "DPI Autostart",
    },
    "page.z2_control.setting.autostart.desc": {
        "ru": "Запускать Zapret автоматически при старте программы",
        "en": "Start Zapret automatically on app launch",
    },
    "page.z2_control.setting.defender.title": {
        "ru": "Отключить Windows Defender",
        "en": "Disable Windows Defender",
    },
    "page.z2_control.setting.defender.desc": {
        "ru": "Требуются права администратора",
        "en": "Administrator rights required",
    },
    "page.z2_control.setting.max_block.title": {
        "ru": "Блокировать установку MAX",
        "en": "Block MAX Installation",
    },
    "page.z2_control.setting.max_block.desc": {
        "ru": "Блокирует запуск/установку MAX и домены в hosts",
        "en": "Blocks MAX launch/installation and hosts domains",
    },
    "page.z2_control.setting.reset.title": {
        "ru": "Сбросить программу",
        "en": "Reset Application",
    },
    "page.z2_control.setting.reset.desc": {
        "ru": "Очистить кэш проверок запуска (без удаления пресетов/настроек)",
        "en": "Clear launch checks cache (without deleting presets/settings)",
    },
    "page.z2_control.button.reset": {
        "ru": "Сбросить",
        "en": "Reset",
    },
    "page.z2_control.button.reset_confirm": {
        "ru": "Сбросить?",
        "en": "Reset?",
    },
    "page.z2_control.dialog.defender_disable.title": {
        "ru": "Отключение Windows Defender",
        "en": "Disable Windows Defender",
    },
    "page.z2_control.dialog.defender_enable.title": {
        "ru": "Включение Windows Defender",
        "en": "Enable Windows Defender",
    },
    "page.z2_control.dialog.max_block_enable.title": {
        "ru": "Блокировка MAX",
        "en": "Enable MAX Blocking",
    },
    "page.z2_control.dialog.max_block_disable.title": {
        "ru": "Отключение блокировки MAX",
        "en": "Disable MAX Blocking",
    },
    "page.z2_control.strategy.autostart_disabled": {
        "ru": "Автостарт DPI отключен",
        "en": "Autostart DPI is disabled",
    },
}

TEXTS.update(TEXTS_PAGES_FINAL)


NAV_PAGE_TEXT_KEYS: dict[PageName, str] = {
    PageName.CONTROL: "nav.page.control",
    PageName.ZAPRET2_DIRECT_CONTROL: "nav.page.zapret2_direct_control",
    PageName.ZAPRET1_DIRECT_CONTROL: "nav.page.zapret1_direct_control",
    PageName.ORCHESTRA: "nav.page.orchestra",
    PageName.HOSTLIST: "nav.page.hostlist",
    PageName.NETROGAT: "page.netrogat.title",
    PageName.CUSTOM_DOMAINS: "page.custom_domains.title",
    PageName.CUSTOM_IPSET: "page.custom_ipset.title",
    PageName.BLOBS: "page.blobs.title",
    PageName.ORCHESTRA_SETTINGS: "nav.page.orchestra_settings",
    PageName.DPI_SETTINGS: "nav.page.dpi_settings",
    PageName.AUTOSTART: "nav.page.autostart",
    PageName.NETWORK: "nav.page.network",
    PageName.HOSTS: "nav.page.hosts",
    PageName.BLOCKCHECK: "nav.page.blockcheck",
    PageName.APPEARANCE: "nav.page.appearance",
    PageName.PREMIUM: "nav.page.premium",
    PageName.LOGS: "nav.page.logs",
    PageName.SERVERS: "page.servers.title",
    PageName.ABOUT: "nav.page.about",
    PageName.SUPPORT: "page.support.title",
    PageName.ZAPRET2_DIRECT: "nav.page.zapret2_direct",
    PageName.ZAPRET2_USER_PRESETS: "nav.page.zapret2_user_presets",
    PageName.ZAPRET2_STRATEGY_DETAIL: "page.z2_strategy_detail.title",
    PageName.ZAPRET1_DIRECT: "nav.page.zapret1_direct",
    PageName.ZAPRET1_USER_PRESETS: "nav.page.zapret1_user_presets",
    PageName.ZAPRET1_STRATEGY_DETAIL: "page.z1_strategy_detail.title",
}


@dataclass(frozen=True)
class SearchEntry:
    entry_id: str
    page_name: PageName
    text_key: str
    section_key: str | None = None
    tab_key: str | None = None
    keywords: tuple[str, ...] = ()
    text_prefixes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SearchMatch:
    entry: SearchEntry
    score: int


SEARCH_ENTRIES: tuple[SearchEntry, ...] = (
    SearchEntry("control.title", PageName.CONTROL, "page.control.title"),
    SearchEntry("control.status", PageName.CONTROL, "page.control.status", section_key="page.control.status"),
    SearchEntry("control.settings", PageName.CONTROL, "page.control.program_settings", section_key="page.control.program_settings"),
    SearchEntry("z2.control.title", PageName.ZAPRET2_DIRECT_CONTROL, "page.z2_control.title"),
    SearchEntry("z2.control.status", PageName.ZAPRET2_DIRECT_CONTROL, "page.control.status", section_key="page.control.status"),
    SearchEntry("z2.control.preset", PageName.ZAPRET2_DIRECT_CONTROL, "page.z2_control.preset_switch", section_key="page.z2_control.preset_switch"),
    SearchEntry("z2.control.direct", PageName.ZAPRET2_DIRECT_CONTROL, "page.z2_control.direct_tuning", section_key="page.z2_control.direct_tuning"),
    SearchEntry("z2.direct.title", PageName.ZAPRET2_DIRECT, "page.z2_direct.title"),
    SearchEntry("z2.user_presets.title", PageName.ZAPRET2_USER_PRESETS, "page.z2_user_presets.title"),
    SearchEntry("z2.strategy_detail.title", PageName.ZAPRET2_STRATEGY_DETAIL, "page.z2_strategy_detail.title"),
    SearchEntry("z1.control.title", PageName.ZAPRET1_DIRECT_CONTROL, "page.z1_control.title"),
    SearchEntry("z1.control.presets", PageName.ZAPRET1_DIRECT_CONTROL, "page.z1_control.presets", section_key="page.z1_control.presets"),
    SearchEntry("z1.direct.title", PageName.ZAPRET1_DIRECT, "page.z1_direct.title"),
    SearchEntry("z1.user_presets.title", PageName.ZAPRET1_USER_PRESETS, "page.z1_user_presets.title"),
    SearchEntry("z1.strategy_detail.title", PageName.ZAPRET1_STRATEGY_DETAIL, "page.z1_strategy_detail.title"),
    SearchEntry("orchestra.title", PageName.ORCHESTRA, "page.orchestra.title"),
    SearchEntry("orchestra.training", PageName.ORCHESTRA, "page.orchestra.training_status", section_key="page.orchestra.training_status"),
    SearchEntry("orchestra.log", PageName.ORCHESTRA, "page.orchestra.log", section_key="page.orchestra.log"),
    SearchEntry("hostlist.title", PageName.HOSTLIST, "page.hostlist.title"),
    SearchEntry("netrogat.title", PageName.NETROGAT, "page.netrogat.title"),
    SearchEntry("custom_domains.title", PageName.CUSTOM_DOMAINS, "page.custom_domains.title"),
    SearchEntry("custom_ipset.title", PageName.CUSTOM_IPSET, "page.custom_ipset.title"),
    SearchEntry("blobs.title", PageName.BLOBS, "page.blobs.title"),
    SearchEntry("hostlist.hostlist", PageName.HOSTLIST, "page.hostlist.hostlist", section_key="page.hostlist.hostlist"),
    SearchEntry("hostlist.ipset", PageName.HOSTLIST, "page.hostlist.ipset", section_key="page.hostlist.ipset"),
    SearchEntry("hostlist.exclusions", PageName.HOSTLIST, "page.hostlist.exclusions", section_key="page.hostlist.exclusions"),
    SearchEntry("dpi.title", PageName.DPI_SETTINGS, "page.dpi_settings.title"),
    SearchEntry("dpi.launch_method", PageName.DPI_SETTINGS, "page.dpi_settings.launch_method", section_key="page.dpi_settings.launch_method"),
    SearchEntry("autostart.title", PageName.AUTOSTART, "page.autostart.title"),
    SearchEntry("autostart.mode", PageName.AUTOSTART, "page.autostart.mode", section_key="page.autostart.mode"),
    SearchEntry("network.title", PageName.NETWORK, "page.network.title"),
    SearchEntry("network.dns", PageName.NETWORK, "page.network.dns", section_key="page.network.dns"),
    SearchEntry("network.adapters", PageName.NETWORK, "page.network.adapters", section_key="page.network.adapters"),
    SearchEntry("network.tools", PageName.NETWORK, "page.network.tools", section_key="page.network.tools"),
    SearchEntry("blockcheck.tab.blockcheck", PageName.BLOCKCHECK, "page.blockcheck.tab.blockcheck", section_key="nav.page.blockcheck", tab_key="blockcheck", text_prefixes=("page.blockcheck.",)),
    SearchEntry("blockcheck.tab.strategy_scan", PageName.BLOCKCHECK, "page.blockcheck.tab.strategy_scan", section_key="nav.page.blockcheck", tab_key="strategy_scan", text_prefixes=("page.strategy_scan.", "page.strategy_sort.")),
    SearchEntry("blockcheck.tab.diagnostics", PageName.BLOCKCHECK, "page.blockcheck.tab.diagnostics", section_key="nav.page.blockcheck", tab_key="diagnostics", text_prefixes=("page.connection.",)),
    SearchEntry("blockcheck.tab.dns_spoofing", PageName.BLOCKCHECK, "page.blockcheck.tab.dns_spoofing", section_key="nav.page.blockcheck", tab_key="dns_spoofing", text_prefixes=("page.dns_check.",)),
    SearchEntry("diag.tab.connection", PageName.BLOCKCHECK, "tab.diagnostics.connection", section_key="nav.page.blockcheck", tab_key="diagnostics"),
    SearchEntry("diag.tab.dns", PageName.BLOCKCHECK, "tab.diagnostics.dns", section_key="nav.page.blockcheck", tab_key="dns_spoofing"),
    SearchEntry("blockcheck.connection.title", PageName.BLOCKCHECK, "page.connection.title", section_key="page.blockcheck.tab.diagnostics", tab_key="diagnostics"),
    SearchEntry("blockcheck.dns_check.title", PageName.BLOCKCHECK, "page.dns_check.title", section_key="page.blockcheck.tab.dns_spoofing", tab_key="dns_spoofing"),
    SearchEntry("blockcheck.strategy_scan.title", PageName.BLOCKCHECK, "page.strategy_scan.title", section_key="page.blockcheck.tab.strategy_scan", tab_key="strategy_scan"),
    SearchEntry("blockcheck.strategy_sort.title", PageName.BLOCKCHECK, "page.strategy_sort.title", section_key="page.blockcheck.tab.strategy_scan", tab_key="strategy_scan"),
    SearchEntry("hosts.title", PageName.HOSTS, "page.hosts.title"),
    SearchEntry("hosts.services", PageName.HOSTS, "page.hosts.services", section_key="page.hosts.services"),
    SearchEntry("blockcheck.title", PageName.BLOCKCHECK, "page.blockcheck.title"),
    SearchEntry("blockcheck.monitoring", PageName.BLOCKCHECK, "page.blockcheck.monitoring", section_key="page.blockcheck.monitoring"),
    SearchEntry("appearance.title", PageName.APPEARANCE, "page.appearance.title"),
    SearchEntry("appearance.display_mode", PageName.APPEARANCE, "page.appearance.display_mode", section_key="page.appearance.display_mode"),
    SearchEntry("appearance.background", PageName.APPEARANCE, "page.appearance.background", section_key="page.appearance.background"),
    SearchEntry("premium.title", PageName.PREMIUM, "page.premium.title"),
    SearchEntry("premium.subscription", PageName.PREMIUM, "page.premium.subscription_status", section_key="page.premium.subscription_status"),
    SearchEntry("logs.title", PageName.LOGS, "page.logs.title"),
    SearchEntry("logs.controls", PageName.LOGS, "page.logs.controls", section_key="page.logs.controls"),
    SearchEntry("servers.title", PageName.SERVERS, "page.servers.title"),
    SearchEntry("about.title", PageName.ABOUT, "page.about.title"),
    SearchEntry("about.version", PageName.ABOUT, "page.about.version", section_key="page.about.version"),
    SearchEntry("about.support", PageName.ABOUT, "page.about.support", section_key="page.about.support"),
    SearchEntry("about.tab.support", PageName.ABOUT, "page.about.tab.support", section_key="page.about.title", tab_key="support", text_prefixes=("page.about.support.",)),
    SearchEntry("about.tab.help", PageName.ABOUT, "page.about.tab.help", section_key="page.about.title", tab_key="help", text_prefixes=("page.about.help.",)),
    SearchEntry("about.support.discussions", PageName.ABOUT, "page.about.support.discussions.title", section_key="page.about.tab.support", tab_key="support"),
    SearchEntry("about.support.telegram", PageName.ABOUT, "page.about.support.telegram.title", section_key="page.about.tab.support", tab_key="support"),
    SearchEntry("about.support.discord", PageName.ABOUT, "page.about.support.discord.title", section_key="page.about.tab.support", tab_key="support"),
    SearchEntry("about.help.docs.forum", PageName.ABOUT, "page.about.help.docs.forum.title", section_key="page.about.tab.help", tab_key="help"),
    SearchEntry("about.help.docs.info", PageName.ABOUT, "page.about.help.docs.info.title", section_key="page.about.tab.help", tab_key="help"),
    SearchEntry("about.help.docs.folder", PageName.ABOUT, "page.about.help.docs.folder.title", section_key="page.about.tab.help", tab_key="help"),
    SearchEntry("about.help.docs.android", PageName.ABOUT, "page.about.help.docs.android.title", section_key="page.about.tab.help", tab_key="help"),
    SearchEntry("about.help.news.telegram", PageName.ABOUT, "page.about.help.news.telegram.title", section_key="page.about.tab.help", tab_key="help"),
    SearchEntry("about.help.news.youtube", PageName.ABOUT, "page.about.help.news.youtube.title", section_key="page.about.tab.help", tab_key="help"),
    SearchEntry("about.help.news.mastodon", PageName.ABOUT, "page.about.help.news.mastodon.title", section_key="page.about.tab.help", tab_key="help"),
    SearchEntry("about.help.news.bastyon", PageName.ABOUT, "page.about.help.news.bastyon.title", section_key="page.about.tab.help", tab_key="help"),
    SearchEntry("support.title", PageName.SUPPORT, "page.support.title"),
    SearchEntry("orch.tab.locked", PageName.ORCHESTRA_SETTINGS, "tab.orchestra.locked", section_key="nav.page.orchestra_settings", tab_key="locked", text_prefixes=("page.orchestra.locked.",)),
    SearchEntry("orch.tab.blocked", PageName.ORCHESTRA_SETTINGS, "tab.orchestra.blocked", section_key="nav.page.orchestra_settings", tab_key="blocked", text_prefixes=("page.orchestra.blocked.",)),
    SearchEntry("orch.tab.whitelist", PageName.ORCHESTRA_SETTINGS, "tab.orchestra.whitelist", section_key="nav.page.orchestra_settings", tab_key="whitelist", text_prefixes=("page.orchestra.whitelist.",)),
    SearchEntry("orch.tab.ratings", PageName.ORCHESTRA_SETTINGS, "tab.orchestra.ratings", section_key="nav.page.orchestra_settings", tab_key="ratings", text_prefixes=("page.orchestra.ratings.",)),
)


_PAGE_SEARCH_EXTRA_PREFIXES: dict[PageName, tuple[str, ...]] = {
    PageName.HOSTLIST: ("page.ipset.",),
    PageName.ZAPRET2_DIRECT: ("page.strategies_base.",),
    PageName.ZAPRET1_DIRECT: ("page.strategies_base.",),
    PageName.BLOCKCHECK: (
        "page.connection.",
        "page.dns_check.",
        "page.strategy_scan.",
        "page.strategy_sort.",
    ),
}


def _extract_page_prefix(text_key: str | None) -> str | None:
    if not text_key or not text_key.startswith("page."):
        return None

    parts = text_key.split(".")
    if len(parts) < 3:
        return None

    return f"page.{parts[1]}."


def _build_page_search_prefixes() -> dict[PageName, tuple[str, ...]]:
    grouped: dict[PageName, list[str]] = {}

    for entry in SEARCH_ENTRIES:
        page_prefixes = grouped.setdefault(entry.page_name, [])
        for text_key in (entry.text_key, entry.section_key):
            prefix = _extract_page_prefix(text_key)
            if prefix and prefix not in page_prefixes:
                page_prefixes.append(prefix)

    for page_name, extra_prefixes in _PAGE_SEARCH_EXTRA_PREFIXES.items():
        page_prefixes = grouped.setdefault(page_name, [])
        for prefix in extra_prefixes:
            if prefix and prefix not in page_prefixes:
                page_prefixes.append(prefix)

    return {page_name: tuple(prefixes) for page_name, prefixes in grouped.items()}


_PAGE_SEARCH_PREFIXES = _build_page_search_prefixes()
_PAGE_SEARCH_TEXT_CACHE: dict[PageName, tuple[str, ...]] = {}
_CUSTOM_PREFIX_TEXT_CACHE: dict[tuple[str, ...], tuple[str, ...]] = {}


def _get_page_search_texts(page_name: PageName) -> tuple[str, ...]:
    cached = _PAGE_SEARCH_TEXT_CACHE.get(page_name)
    if cached is not None:
        return cached

    prefixes = _PAGE_SEARCH_PREFIXES.get(page_name, ())
    if not prefixes:
        _PAGE_SEARCH_TEXT_CACHE[page_name] = ()
        return ()

    result: list[str] = []
    for text_key in TEXTS:
        if text_key.startswith(prefixes):
            for text in _text_variants(text_key):
                result.append(text)

    unique_result = tuple(dict.fromkeys(result))
    _PAGE_SEARCH_TEXT_CACHE[page_name] = unique_result
    return unique_result


def _normalize_text_prefixes(prefixes: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for prefix in prefixes:
        if isinstance(prefix, str) and prefix and prefix not in normalized:
            normalized.append(prefix)
    return tuple(normalized)


def _get_prefixed_search_texts(prefixes: tuple[str, ...]) -> tuple[str, ...]:
    normalized_prefixes = _normalize_text_prefixes(prefixes)
    if not normalized_prefixes:
        return ()

    cached = _CUSTOM_PREFIX_TEXT_CACHE.get(normalized_prefixes)
    if cached is not None:
        return cached

    result: list[str] = []
    for text_key in TEXTS:
        if text_key.startswith(normalized_prefixes):
            for text in _text_variants(text_key):
                result.append(text)

    unique_result = tuple(dict.fromkeys(result))
    _CUSTOM_PREFIX_TEXT_CACHE[normalized_prefixes] = unique_result
    return unique_result


def _is_primary_page_entry(entry: SearchEntry) -> bool:
    return entry.section_key is None and entry.tab_key is None and entry.entry_id.endswith(".title")


def normalize_language(language: str | None) -> str:
    candidate = (language or DEFAULT_UI_LANGUAGE).strip().lower()
    if candidate in SUPPORTED_UI_LANGUAGES:
        return candidate
    return DEFAULT_UI_LANGUAGE


def tr(key: str, language: str | None = None, default: str | None = None) -> str:
    lang = normalize_language(language)
    values = TEXTS.get(key)
    if not values:
        return default if default is not None else key

    value = values.get(lang)
    if isinstance(value, str) and value:
        return value

    fallback = values.get(DEFAULT_UI_LANGUAGE)
    if isinstance(fallback, str) and fallback:
        return fallback

    for candidate in values.values():
        if isinstance(candidate, str) and candidate:
            return candidate

    return default if default is not None else key


def _text_variants(key: str | None) -> tuple[str, ...]:
    if not key:
        return ()

    values = TEXTS.get(key) or {}
    result: list[str] = []
    for raw in values.values():
        if isinstance(raw, str) and raw:
            result.append(raw)
    return tuple(dict.fromkeys(result))


def get_nav_page_label(page_name: PageName, language: str | None = None, fallback: str | None = None) -> str:
    key = NAV_PAGE_TEXT_KEYS.get(page_name)
    if key is None:
        if fallback is not None:
            return fallback
        return page_name.name
    return tr(key, language=language, default=fallback or page_name.name)


def format_search_result(entry: SearchEntry, language: str | None = None) -> tuple[str, str]:
    title = tr(entry.text_key, language=language)
    page_label = get_nav_page_label(entry.page_name, language=language)

    section = ""
    if entry.section_key:
        section = tr(entry.section_key, language=language)

    location = page_label if not section else f"{page_label} / {section}"
    return title, location


def _iter_candidate_texts(entry: SearchEntry) -> Iterable[str]:
    for text in _text_variants(entry.text_key):
        yield text

    nav_key = NAV_PAGE_TEXT_KEYS.get(entry.page_name)
    if nav_key:
        for text in _text_variants(nav_key):
            yield text

    for text in _text_variants(entry.section_key):
        yield text

    for keyword in entry.keywords:
        if isinstance(keyword, str) and keyword:
            yield keyword

    for text in _get_prefixed_search_texts(entry.text_prefixes):
        yield text

    if _is_primary_page_entry(entry):
        for text in _get_page_search_texts(entry.page_name):
            yield text


def find_search_entries(
    query: str,
    language: str | None = None,
    *,
    visible_pages: set[PageName] | None = None,
    max_results: int = 12,
) -> tuple[SearchMatch, ...]:
    needle = (query or "").strip().casefold()
    if not needle:
        return ()

    lang = normalize_language(language)
    matches: list[SearchMatch] = []

    for entry in SEARCH_ENTRIES:
        if visible_pages is not None and entry.page_name not in visible_pages:
            continue

        score = 0

        localized_title = tr(entry.text_key, language=lang).casefold()
        if needle in localized_title:
            score = max(score, 120 if localized_title.startswith(needle) else 100)

        for title_variant in _text_variants(entry.text_key):
            title_variant_cf = title_variant.casefold()
            if needle in title_variant_cf:
                score = max(score, 115 if title_variant_cf.startswith(needle) else 95)
                break

        localized_section = tr(entry.section_key, language=lang, default="") if entry.section_key else ""
        if localized_section and needle in localized_section.casefold():
            score = max(score, 85)

        for section_variant in _text_variants(entry.section_key):
            if needle in section_variant.casefold():
                score = max(score, 82)
                break

        localized_page = get_nav_page_label(entry.page_name, language=lang).casefold()
        if needle in localized_page:
            score = max(score, 70)

        nav_key = NAV_PAGE_TEXT_KEYS.get(entry.page_name)
        for page_variant in _text_variants(nav_key):
            if needle in page_variant.casefold():
                score = max(score, 68)
                break

        for prefixed_text in _get_prefixed_search_texts(entry.text_prefixes):
            prefixed_cf = prefixed_text.casefold()
            if needle in prefixed_cf:
                score = max(score, 94 if prefixed_cf.startswith(needle) else 78)
                break

        if _is_primary_page_entry(entry):
            for page_text in _get_page_search_texts(entry.page_name):
                page_text_cf = page_text.casefold()
                if needle in page_text_cf:
                    score = max(score, 92 if page_text_cf.startswith(needle) else 76)
                    break

        for candidate in _iter_candidate_texts(entry):
            if needle in candidate.casefold():
                score = max(score, 60)
                break

        if _is_primary_page_entry(entry) and score >= 95:
            score += 1

        if score > 0:
            matches.append(SearchMatch(entry=entry, score=score))

    matches.sort(
        key=lambda item: (
            -item.score,
            tr(item.entry.text_key, language=lang).casefold(),
            item.entry.entry_id,
        )
    )
    return tuple(matches[: max(1, int(max_results))])
