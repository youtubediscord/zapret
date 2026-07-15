"""Centralized application text catalog and sidebar search index.

This module contains user-facing strings for navigation/search and the
declarative index used by the left sidebar global search.
"""

from settings.mode import ENGINE_WINWS1, ENGINE_WINWS2, EXE_NAME_WINWS1, EXE_NAME_WINWS2
from app.page_names import PageName


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
        "ru": "Инструменты",
        "en": "Tools",
    },
    "nav.header.diagnostics": {
        "ru": "Диагностика",
        "en": "Diagnostics",
    },
    "nav.header.appearance": {
        "ru": "Оформление",
        "en": "Appearance",
    },
    "nav.page.zapret2_mode_control": {
        "ru": "Управление Zapret 2",
        "en": "Zapret 2 Control",
    },
    "nav.page.zapret1_mode_control": {
        "ru": "Управление Zapret 1",
        "en": "Zapret 1 Control",
    },
    "nav.page.orchestra": {
        "ru": "Оркестратор",
        "en": "Orchestrator",
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
        "ru": "Настройка DNS",
        "en": "DNS Settings",
    },
    "nav.page.hosts": {
        "ru": "Редактор hosts",
        "en": "Hosts Editor",
    },
    "nav.page.blockcheck": {
        "ru": "BlockCheck",
        "en": "BlockCheck",
    },
    "nav.page.winws_log_analyzer": {
        "ru": "Анализ лога winws2",
        "en": "winws2 Log Analysis",
    },
    "page.winws_log_analyzer.title": {
        "ru": "Анализ лога winws2",
        "en": "winws2 Log Analysis",
    },
    "page.winws_log_analyzer.subtitle": {
        "ru": "Разбор debug-лога: соединения, протоколы, профили и вердикты",
        "en": "Debug log breakdown: connections, protocols, profiles and verdicts",
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
    "nav.page.zapret2_mode": {
        "ru": "Профили пресета",
        "en": "Preset profiles",
    },
    "nav.page.zapret2_user_presets": {
        "ru": "Мои пресеты",
        "en": "My Presets",
    },
    "nav.page.zapret1_mode": {
        "ru": "Профили пресета",
        "en": "Preset profiles",
    },
    "nav.page.zapret1_user_presets": {
        "ru": "Мои пресеты",
        "en": "My presets",
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
    "page.control.status": {
        "ru": "Статус работы",
        "en": "Service Status",
    },
    "page.control.status.checking": {
        "ru": "Проверка...",
        "en": "Checking...",
    },
    "page.control.status.detecting": {
        "ru": "Определение состояния процесса",
        "en": "Detecting process state",
    },
    "page.control.summary.preset.caption": {
        "ru": "Текущий preset",
        "en": "Current preset",
    },
    "page.control.summary.profiles.caption": {
        "ru": "Профили",
        "en": "Profiles",
    },
    "page.control.summary.profiles.enabled_template": {
        "ru": "{count} включено",
        "en": "{count} enabled",
    },
    "page.control.summary.profiles.unavailable": {
        "ru": "Проверяем...",
        "en": "Checking...",
    },
    "page.control.summary.mode.caption": {
        "ru": "Текущий режим",
        "en": "Current mode",
    },
    "page.control.summary.premium.free_details": {
        "ru": "Базовые функции",
        "en": "Basic features",
    },
    "page.control.summary.premium.days_left": {
        "ru": "Осталось {days} дней",
        "en": "{days} days left",
    },
    "page.control.summary.premium.active_details": {
        "ru": "Активен",
        "en": "Active",
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
    "page.control.last_message.title": {
        "ru": "Последнее сообщение",
        "en": "Latest message",
    },
    "page.control.last_message.empty": {
        "ru": "Пока нет новых сообщений",
        "en": "No new messages yet",
    },
    "page.control.button.start": {
        "ru": "Запустить Zapret",
        "en": "Start Zapret",
    },
    "page.control.button.stop_only_winws": {
        "ru": f"Остановить только {EXE_NAME_WINWS1}",
        "en": f"Stop only {EXE_NAME_WINWS1}",
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
        "ru": "Автозапуск DPI после старта программы",
        "en": "Auto-start DPI after app launch",
    },
    "page.control.setting.autostart.desc": {
        "ru": "После запуска ZapretGUI автоматически запускать текущий DPI-режим",
        "en": "Automatically start the current DPI mode after ZapretGUI launches",
    },
    "page.control.setting.gui_autostart.title": {
        "ru": "Автозапуск ZapretGUI",
        "en": "ZapretGUI autostart",
    },
    "page.control.setting.gui_autostart.desc": {
        "ru": "Запускать программу в трее при входе в Windows",
        "en": "Start the app in the tray when signing in to Windows",
    },
    "page.control.setting.tray_close_mode.title": {
        "ru": "Поведение окна и трея",
        "en": "Window and tray behavior",
    },
    "page.control.setting.tray_close_mode.desc": {
        "ru": "Выберите, когда ZapretGUI будет скрывать окно в системный трей",
        "en": "Choose when ZapretGUI hides the window to the system tray",
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
    "page.control.setting.state_media_block.title": {
        "ru": "Блокировать государственные СМИ РФ",
        "en": "Block Russian state media",
    },
    "page.control.setting.state_media_block.desc": {
        "ru": "Добавляет базовый список государственных новостных сайтов в hosts",
        "en": "Adds a basic list of state news sites to hosts",
    },
    "page.control.button.connection_test": {
        "ru": "Тест соединения",
        "en": "Connection Test",
    },
    "page.control.button.open_folder": {
        "ru": "Открыть папку",
        "en": "Open Folder",
    },
    "page.winws2_control.title": {
        "ru": "Управление Zapret 2",
        "en": "Zapret 2 Control",
    },
    "page.winws2_control.preset_switch": {
        "ru": "Сменить пресет обхода блокировок",
        "en": "Switch Bypass Preset",
    },
    "page.winws2_control.profile_tuning": {
        "ru": "Настройка пресета",
        "en": "Preset setup",
    },
    "page.winws1_control.title": {
        "ru": "Управление Zapret 1",
        "en": "Zapret 1 Control",
    },
    "page.winws1_control.presets": {
        "ru": "Пресеты и настройка пресета",
        "en": "Presets and preset setup",
    },
    "page.winws1_control.status.checking": {
        "ru": "Проверка...",
        "en": "Checking...",
    },
    "page.winws1_control.status.detecting": {
        "ru": "Определение состояния процесса",
        "en": "Detecting process state",
    },
    "page.winws1_control.status.running": {
        "ru": "Zapret 1 работает",
        "en": "Zapret 1 is running",
    },
    "page.winws1_control.status.stopped": {
        "ru": "Zapret 1 остановлен",
        "en": "Zapret 1 stopped",
    },
    "page.winws1_control.status.bypass_active": {
        "ru": "Обход блокировок активен",
        "en": "Bypass is active",
    },
    "page.winws1_control.status.press_start": {
        "ru": "Нажмите «Запустить» для активации",
        "en": "Press Start to activate",
    },
    "page.winws1_control.button.start": {
        "ru": "Запустить Zapret",
        "en": "Start Zapret",
    },
    "page.winws1_control.button.stop_winws": {
        "ru": f"Остановить {EXE_NAME_WINWS1}",
        "en": f"Stop {EXE_NAME_WINWS1}",
    },
    "page.winws1_control.button.stop_and_exit": {
        "ru": "Остановить и закрыть",
        "en": "Stop and close",
    },
    "page.winws1_control.preset.not_selected": {
        "ru": "Не выбран",
        "en": "Not selected",
    },
    "page.winws1_control.preset.current": {
        "ru": "Текущий активный пресет",
        "en": "Current active preset",
    },
    "page.winws1_control.button.my_presets": {
        "ru": "Мои пресеты",
        "en": "My Presets",
    },
    "page.winws1_control.profiles.title": {
        "ru": "Настройка пресета",
        "en": "Preset setup",
    },
    "page.winws1_control.profiles.desc": {
        "ru": "Открыть профили выбранного пресета и выбрать готовые стратегии",
        "en": "Open profiles from the selected preset and choose ready strategies",
    },
    "page.winws1_control.button.open": {
        "ru": "Открыть",
        "en": "Open",
    },
    "page.winws1_control.setting.autostart.title": {
        "ru": "Автозапуск DPI после старта программы",
        "en": "Auto-start DPI after app launch",
    },
    "page.winws1_control.setting.autostart.desc": {
        "ru": "После запуска ZapretGUI автоматически запускать текущий DPI-режим",
        "en": "Automatically start the current DPI mode after ZapretGUI launches",
    },
    "page.winws1_control.card.advanced": {
        "ru": "Дополнительные настройки",
        "en": "ADVANCED SETTINGS",
    },
    "page.winws1_control.advanced.warning": {
        "ru": "Изменяйте только если знаете что делаете",
        "en": "Change only if you know what you are doing",
    },
    "page.winws1_control.advanced.discord_restart.title": {
        "ru": "Перезапуск Discord",
        "en": "Restart Discord",
    },
    "page.winws1_control.advanced.discord_restart.desc": {
        "ru": "Автоперезапуск при смене стратегии",
        "en": "Auto-restart on strategy change",
    },
    "page.winws1_control.advanced.wssize.title": {
        "ru": "Включить --wssize",
        "en": "Enable --wssize",
    },
    "page.winws1_control.advanced.wssize.desc": {
        "ru": "Добавляет параметр размера окна TCP",
        "en": "Adds TCP window size parameter",
    },
    "page.winws1_control.advanced.debug_log.title": {
        "ru": "Включить лог-файл (--debug)",
        "en": "Enable log file (--debug)",
    },
    "page.winws1_control.advanced.debug_log.desc": {
        "ru": "Записывает логи winws в папку logs",
        "en": "Writes winws logs to the logs folder",
    },
    "page.winws1_control.section.additional": {
        "ru": "Дополнительные действия",
        "en": "Additional actions",
    },
    "page.winws1_control.button.connection_test": {
        "ru": "Тест соединения",
        "en": "Connection test",
    },
    "page.winws1_control.button.connection_test.desc": {
        "ru": "Проверить доступность сети и состояние обхода",
        "en": "Check network reachability and bypass state",
    },
    "page.winws1_control.button.open_folder": {
        "ru": "Открыть папку",
        "en": "Open folder",
    },
    "page.winws1_control.button.open_folder.desc": {
        "ru": "Перейти в папку программы и служебных файлов",
        "en": "Open the app folder and service files",
    },
    "page.winws1_control.button.documentation": {
        "ru": "Документация",
        "en": "Documentation",
    },
    "page.winws1_control.button.documentation.desc": {
        "ru": "Открыть справку и описание возможностей",
        "en": "Open help and feature documentation",
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
        "ru": "Настройка DNS",
        "en": "DNS Settings",
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
        "ru": "Редактор hosts",
        "en": "Hosts Editor",
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
    "page.about.button.open": {
        "ru": "Открыть",
        "en": "Open",
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
    "page.about.button.zapret_kvn": {
        "ru": "Zapret KVN",
        "en": "Zapret KVN",
    },
    "page.about.action.zapret_kvn.accessible_name": {
        "ru": "Открыть Zapret KVN на GitHub",
        "en": "Open Zapret KVN on GitHub",
    },
    "page.about.action.zapret_kvn.description": {
        "ru": "Открывает репозиторий проекта Zapret KVN на GitHub.",
        "en": "Opens the Zapret KVN project repository on GitHub.",
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
        "ru": "Вики-сайт",
        "en": "Wiki site",
    },
    "page.about.help.docs.forum.desc": {
        "ru": "Документация и инструкции",
        "en": "Documentation and guides",
    },
    "page.about.help.docs.info.title": {
        "ru": "Что это такое?",
        "en": "What is this?",
    },
    "page.about.help.docs.info.desc": {
        "ru": "Руководство и ответы на вопросы",
        "en": "Guide and FAQ",
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
    "page.about.course.group": {
        "ru": "Обучение",
        "en": "Learning",
    },
    "page.about.course.youtube.title": {
        "ru": "Курс и гайд по Zapret 2",
        "en": "Zapret 2 course and guide",
    },
    "page.about.course.youtube.desc": {
        "ru": "Видео по настройке и пониманию Zapret 2",
        "en": "Videos about setting up and understanding Zapret 2",
    },
    "page.about.course.youtube_playlist.title": {
        "ru": "Плейлист курса по Zapret 2",
        "en": "Zapret 2 course playlist",
    },
    "page.about.course.youtube_playlist.desc": {
        "ru": "Все видео курса одним списком",
        "en": "All course videos in one playlist",
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
    "page.autostart.mode.zapret2_mode": {
        "ru": "Профили (Zapret 2)",
        "en": "Zapret 2 mode",
    },
    "page.autostart.mode.orchestra_learning": {
        "ru": "Оркестр (автообучение)",
        "en": "Orchestrator (auto-learning)",
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
        "ru": "Используется один тип автозапуска: ярлык ZapretGUI в папке автозагрузки Windows.",
        "en": "Only one autostart type is used: a ZapretGUI shortcut in the Windows Startup folder.",
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
    "page.custom_domains.title": {
        "ru": "Кастомные (мои) домены (hostlist) для работы с Zapret",
        "en": "Custom Domains (hostlist) for Zapret",
    },
    "page.custom_domains.subtitle": {
        "ru": "Управление доменами (other.txt). Субдомены учитываются автоматически. Строчка rkn.ru учитывает и сайт fuckyou.rkn.ru и сайт ass.rkn.ru. Чтобы исключить субдомены напишите домен с символов ^ в начале, то есть например так ^rkn.ru",
        "en": "Manage domains (other.txt). Subdomains are handled automatically. Prefix a domain with ^ to match only the exact domain.",
    },
    "page.custom_domains.description": {
        "ru": "Здесь редактируется пользовательский список доменов `lists/user/other.txt`. Системная база лежит в `lists/base/other.txt`, а итоговый `lists/other.txt` собирается автоматически. URL автоматически преобразуются в домены. Изменения сохраняются автоматически. Поддерживается Ctrl+Z.",
        "en": "Edit the custom domains list `lists/user/other.txt`. The system base lives in `lists/base/other.txt`, and the final `lists/other.txt` is rebuilt automatically. URLs are converted to domains automatically. Changes are saved automatically. Ctrl+Z is supported.",
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
        "ru": "lists/user/other.txt (редактор)",
        "en": "lists/user/other.txt (editor)",
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
        "ru": "Сохраняет изменения и открывает `lists/user/other.txt` в проводнике",
        "en": "Saves changes and opens `lists/user/other.txt` in Explorer",
    },
    "page.custom_domains.tooltip.reset_file": {
        "ru": "Очищает `lists/user/other.txt` и пересобирает `lists/other.txt` из системной базы",
        "en": "Clears `lists/user/other.txt` and rebuilds `lists/other.txt` from the system base",
    },
    "page.custom_domains.tooltip.clear_all": {
        "ru": "Удаляет только пользовательские домены. Системная база из `lists/base/other.txt` останется",
        "en": "Removes only custom domains. The system base from `lists/base/other.txt` remains",
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
        "ru": "Здесь Вы можете редактировать пользовательский список IP/подсетей `lists/user/ipset-all.txt`. Пишите только IP/CIDR, изменения сохраняются автоматически.",
        "en": "Edit the custom IP/subnet list `lists/user/ipset-all.txt`. Use IP/CIDR format only; changes are saved automatically.",
    },
    "page.custom_ipset.description": {
        "ru": "Добавляйте свои IP/подсети в `lists/user/ipset-all.txt`.\n• Одиночный IP: 1.2.3.4\n• Подсеть: 10.0.0.0/8\nДиапазоны (a-b) не поддерживаются.\nСистемная база хранится в `lists/base/ipset-all.txt`, а итоговый `lists/ipset-all.txt` собирается автоматически.",
        "en": "Add your own IPs/subnets to `lists/user/ipset-all.txt`.\n• Single IP: 1.2.3.4\n• Subnet: 10.0.0.0/8\nRanges (a-b) are not supported.\nThe system base is stored in `lists/base/ipset-all.txt`, and the final `lists/ipset-all.txt` is rebuilt automatically.",
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
        "ru": "lists/user/ipset-all.txt (редактор)",
        "en": "lists/user/ipset-all.txt (editor)",
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
    "page.dpi_settings.section.zapret2": {
        "ru": f"Zapret 2 ({EXE_NAME_WINWS2})",
        "en": f"Zapret 2 ({EXE_NAME_WINWS2})",
    },
    "page.dpi_settings.section.zapret1": {
        "ru": f"Zapret 1 ({EXE_NAME_WINWS1})",
        "en": f"Zapret 1 ({EXE_NAME_WINWS1})",
    },
    "page.dpi_settings.option.recommended": {
        "ru": "рекомендуется",
        "en": "recommended",
    },
    "page.dpi_settings.method.zapret2_mode.title": {
        "ru": "Zapret 2",
        "en": "Zapret 2",
    },
    "page.dpi_settings.method.zapret2_mode.desc": {
        "ru": f"Режим Zapret 2 на движке {ENGINE_WINWS2} ({EXE_NAME_WINWS2}) + готовые пресеты для быстрого запуска. Поддерживает Lua-код для своих стратегий.",
        "en": f"Zapret 2 mode on {ENGINE_WINWS2} ({EXE_NAME_WINWS2}) with ready presets for quick launch. Supports custom Lua code for your own strategies.",
    },
    "page.dpi_settings.method.orchestra.title": {
        "ru": "Оркестратор v0.9.6 (Beta)",
        "en": "Orchestrator v0.9.6 (Beta)",
    },
    "page.dpi_settings.method.orchestra.desc": {
        "ru": "Автоматическое обучение. Система сама подбирает лучшие стратегии для каждого домена. Запоминает результаты между запусками.",
        "en": "Automatic learning. The system picks the best strategy per domain and remembers results between launches.",
    },
    "page.dpi_settings.method.zapret1_mode.title": {
        "ru": "Zapret 1",
        "en": "Zapret 1",
    },
    "page.dpi_settings.method.zapret1_mode.desc": {
        "ru": f"Режим Zapret 1 на движке {ENGINE_WINWS1} ({EXE_NAME_WINWS1}) + готовые пресеты для быстрого запуска. Не использует Lua-код и блобы.",
        "en": f"Zapret 1 mode on {ENGINE_WINWS1} ({EXE_NAME_WINWS1}) with ready presets for quick launch. Does not use Lua code or blobs.",
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
        "ru": "Дополнительные настройки",
        "en": "ADVANCED SETTINGS",
    },
    "page.dpi_settings.advanced.warning": {
        "ru": "Изменяйте только если знаете что делаете",
        "en": "Change only if you know what you are doing",
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
        "ru": "Очистить записи ZapretGUI?",
        "en": "Clear ZapretGUI entries?",
    },
    "page.hosts.dialog.clear.body": {
        "ru": "Будет удалён только блок записей ZapretGUI. Ручные записи в файле hosts останутся на месте.",
        "en": "Only the ZapretGUI managed block will be removed. Manual hosts entries will remain untouched.",
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
    "page.logs.tab.manage": {
        "ru": "УПРАВЛЕНИЕ",
        "en": "MANAGE",
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
    "page.network.subtitle": {
        "ru": "Здесь можно посмотреть текущие DNS, выбрать другие серверы и проверить, помогает ли настройка обходу блокировок.",
        "en": "View current DNS servers, choose different servers, and check whether the setting helps bypass blocking.",
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
        "ru": "",
        "en": "",
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
    "page.network.force_dns.action.enable.button": {
        "ru": "Применить выбранный DNS",
        "en": "Apply selected DNS",
    },
    "page.network.force_dns.action.disable.button": {
        "ru": "Ручная настройка DNS",
        "en": "Manual DNS setup",
    },
    "page.network.force_dns.action.enable.description": {
        "ru": "Выберите DNS из списка или добавьте свой адрес. Программа применит его только по вашему нажатию.",
        "en": "Choose DNS from the list or add your own address. The app applies it only when you ask.",
    },
    "page.network.force_dns.action.enable.confirm": {
        "ru": "Программа применит выбранный DNS на отмеченных сетевых адаптерах. Это может помочь, если провайдер подменяет ответы DNS и сайты открываются неправильно. Продолжить?",
        "en": "The app will apply the selected DNS to the checked network adapters. This may help when the provider tampers with DNS answers and sites open incorrectly. Continue?",
    },
    "page.network.force_dns.action.disable.description": {
        "ru": "DNS меняется только вручную: выберите сервер, добавьте свой адрес или верните автоматическое получение через DHCP.",
        "en": "DNS changes only manually: choose a server, add your own address, or restore automatic DNS through DHCP.",
    },
    "page.network.force_dns.action.disable.confirm": {
        "ru": "DNS меняется только вручную. Уже прописанные адреса останутся до следующей настройки или сброса на DHCP. Продолжить?",
        "en": "DNS changes only manually. Already applied addresses remain until the next setup or DHCP reset. Continue?",
    },
    "page.network.force_dns.action.reset.description": {
        "ru": "DNS будет снова получаться автоматически от роутера или провайдера через DHCP. Это полезно, если интернет работает нестабильно после ручной настройки DNS.",
        "en": "DNS will be received automatically from the router or provider through DHCP again. This is useful if the internet is unstable after manual DNS setup.",
    },
    "page.network.force_dns.reset.button": {
        "ru": "Вернуть DNS автоматически",
        "en": "Restore automatic DNS",
    },
    "page.network.force_dns.reset.confirm": {
        "ru": "Программа вернёт автоматическое получение DNS через DHCP для выбранных адаптеров. DHCP — это обычный режим, когда DNS выдаёт роутер или провайдер. Продолжить?",
        "en": "The app will restore automatic DNS through DHCP for selected adapters. DHCP is the normal mode where DNS is provided by the router or provider. Continue?",
    },
    "page.network.force_dns.status.details.enable_failed": {
        "ru": "Не удалось включить",
        "en": "Failed to enable",
    },
    "page.network.force_dns.status.details.disable_failed": {
        "ru": "Не удалось отключить",
        "en": "Failed to disable",
    },
    "page.network.force_dns.status.details.apply_error": {
        "ru": "Ошибка применения",
        "en": "Apply error",
    },
    "page.network.force_dns.status.details.dhcp_not_applied": {
        "ru": "DHCP не применён",
        "en": "DHCP was not applied",
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
        "ru": "У вас установлен DNS от провайдера (получен автоматически через DHCP). Провайдерский DNS может подменять ответы и мешать обходу блокировок.\n\nМожно вручную применить публичный DNS Quad9 или выбрать другой DNS из списка ниже.",
        "en": "Your DNS is set automatically from your ISP (via DHCP). ISP DNS may poison responses and interfere with DPI bypass.\n\nYou can manually apply public Quad9 DNS or choose another DNS from the list below.",
    },
    "page.network.isp_dns.infobar.action": {
        "ru": "Применить Quad9",
        "en": "Apply Quad9",
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
        "ru": "[WARNING] Оркестратор не запущен, user lock сохранён в settings.json",
        "en": "[WARNING] Orchestrator is not running, user lock is saved in settings.json",
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
        "ru": "Системные блокировки (стратегия 1 для заблокированных РКН сайтов) + пользовательский чёрный список. Оркестратор не будет их использовать.",
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
        "ru": "Управление подпиской Zapret Premium (премиум)",
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
        "ru": "✅ Код создан примерно на 10 минут и скопирован. Сразу отправьте его боту в Telegram.",
        "en": "✅ Code was created for about 10 minutes and copied. Send it to the bot right away.",
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
    "page.servers.table.versions.dev_template": {
        "ru": "D: {version}",
        "en": "D: {version}",
    },
    "page.servers.table.versions.both_template": {
        "ru": "S: {stable}, D: {dev}",
        "en": "S: {stable}, D: {dev}",
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
    "page.winws1_control.subtitle": {
        "ru": f"Настройка и запуск Zapret 1 ({EXE_NAME_WINWS1}). В «Мои пресеты» выбирается пресет, а в «Настройка пресета» меняются профили и выбранные для них готовые стратегии.",
        "en": f"Configure and launch Zapret 1 ({EXE_NAME_WINWS1}). My presets selects a preset; preset setup changes profiles and ready strategies.",
    },
    "page.winws1_control.section.status": {
        "ru": "Статус работы",
        "en": "Service Status",
    },
    "page.winws1_control.section.management": {
        "ru": "Управление Zapret 1",
        "en": "Zapret 1 Control",
    },
    "page.winws1_control.section.presets": {
        "ru": "Пресеты и настройка пресета",
        "en": "Presets and preset setup",
    },
    "page.winws1_control.section.program_settings": {
        "ru": "Настройки программы",
        "en": "Program Settings",
    },
    "page.winws1_pages.title": {
        "ru": "Настройка пресета",
        "en": "Preset setup",
    },
    "page.winws1_pages.back.control": {
        "ru": "\u2190 Управление",
        "en": "\u2190 Control",
    },
    "page.winws1_pages.breadcrumb.control": {
        "ru": "Управление",
        "en": "Control",
    },
    "page.winws1_pages.toolbar.expand": {
        "ru": "Развернуть",
        "en": "Expand",
    },
    "page.winws1_pages.toolbar.collapse": {
        "ru": "Свернуть",
        "en": "Collapse",
    },
    "page.winws1_pages.toolbar.view_menu": {
        "ru": "Вид",
        "en": "View",
    },
    "page.winws1_pages.toolbar.show_added_only": {
        "ru": "Показать только добавленные",
        "en": "Show added only",
    },
    "page.winws1_pages.toolbar.show_all_profiles": {
        "ru": "Показать все профили",
        "en": "Show all profiles",
    },
    "page.winws1_pages.toolbar.info": {
        "ru": "Что это?",
        "en": "What is this?",
    },
    "page.winws1_pages.toolbar.title": {
        "ru": "Профили",
        "en": "Profiles",
    },
    "page.winws1_pages.toolbar.search.placeholder": {
        "ru": "Поиск профиля по имени, портам и т.д.",
        "en": "Search profiles by name, ports, etc.",
    },
    "page.winws1_pages.request.button": {
        "ru": "Предложить профиль",
        "en": "Suggest profile",
    },
    "page.winws1_pages.request.hint": {
        "ru": "Если нужного профиля нет в списке, его можно добавить позже в набор доступных профилей.",
        "en": "If the needed profile is missing, it can be added later to the available profiles.",
    },
    "page.winws1_pages.loading": {
        "ru": "Читаем профили из выбранного пресета...",
        "en": "Reading profiles from the selected preset...",
    },
    "page.winws1_pages.strategy.off": {
        "ru": "Выключено",
        "en": "Off",
    },
    "page.winws1_pages.strategy.custom": {
        "ru": "Свой набор",
        "en": "Custom set",
    },
    "page.winws1_pages.info.title": {
        "ru": "Настройка пресета",
        "en": "Preset setup",
    },
    "page.winws1_pages.info.body": {
        "ru": "Чтобы запустить zapret напрямую, включите нужные профили, выберите для них готовые стратегии и нажмите «Запустить» на странице управления.",
        "en": "To start Zapret directly, enable the needed profiles, choose ready strategies for them, and click Start on the control page.",
    },
    "page.winws1_user_presets.title": {
        "ru": "Мои пресеты",
        "en": "My Presets",
    },
    "page.winws1_user_presets.back.control": {
        "ru": "Управление",
        "en": "Control",
    },
    "page.winws1_user_presets.configs.title": {
        "ru": "Обменивайтесь пресетами и профилями в разделе GitHub Discussions",
        "en": "Share presets and profiles in GitHub Discussions",
    },
    "page.winws1_user_presets.configs.button": {
        "ru": "Получить конфиги",
        "en": "Get configs",
    },
    "page.winws1_user_presets.button.import": {
        "ru": "Импорт",
        "en": "Import",
    },
    "page.winws1_user_presets.button.open_folder": {
        "ru": "Папка пресетов",
        "en": "Presets folder",
    },
    "page.winws1_user_presets.button.reset_all": {
        "ru": "Вернуть встроенные",
        "en": "Restore defaults",
    },
    "page.winws1_user_presets.button.wiki": {
        "ru": "Вики по пресетам",
        "en": "Preset wiki",
    },
    "page.winws1_user_presets.button.what_is_this": {
        "ru": "Что это такое?",
        "en": "What is this?",
    },
    "page.winws1_user_presets.search.placeholder": {
        "ru": "Поиск пресетов по имени...",
        "en": "Search presets by name...",
    },
    "page.winws1_user_presets.tooltip.create": {
        "ru": "Создать новый пресет",
        "en": "Create a new preset",
    },
    "page.winws1_user_presets.tooltip.import": {
        "ru": "Импорт пресета из файла",
        "en": "Import preset from file",
    },
    "page.winws1_user_presets.tooltip.open_folder": {
        "ru": "Открыть папку, где лежат ваши пресеты",
        "en": "Open the folder where your presets are stored",
    },
    "page.winws1_user_presets.tooltip.reset_all": {
        "ru": "Возвращает встроенные пресеты. Ваши изменения во встроенных пресетах будут потеряны.",
        "en": "Restores built-in presets. Your changes to built-in presets will be lost.",
    },
    "page.winws1_user_presets.delegate.tooltip.rename": {
        "ru": "Переименовать",
        "en": "Rename",
    },
    "page.winws1_user_presets.delegate.tooltip.duplicate": {
        "ru": "Дублировать",
        "en": "Duplicate",
    },
    "page.winws1_user_presets.delegate.tooltip.reset": {
        "ru": "Вернуть встроенный",
        "en": "Restore built-in",
    },
    "page.winws1_user_presets.delegate.tooltip.delete": {
        "ru": "Удалить",
        "en": "Delete",
    },
    "page.winws1_user_presets.delegate.tooltip.export": {
        "ru": "Экспорт",
        "en": "Export",
    },
    "page.winws1_user_presets.delegate.tooltip.confirm_again": {
        "ru": "Нажмите ещё раз для подтверждения",
        "en": "Click again to confirm",
    },
    "page.winws1_user_presets.delegate.badge.active": {
        "ru": "Активен",
        "en": "Active",
    },
    "page.winws1_user_presets.dialog.button.cancel": {
        "ru": "Отмена",
        "en": "Cancel",
    },
    "page.winws1_user_presets.dialog.reset_single.title": {
        "ru": "Вернуть встроенный пресет?",
        "en": "Restore built-in preset?",
    },
    "page.winws1_user_presets.dialog.reset_single.body": {
        "ru": "Будет удалён ваш изменённый файл пресета «{name}».\nПосле этого снова появится встроенный пресет с тем же именем файла.\nИзменения в этом файле будут потеряны.",
        "en": "User preset file '{name}' will be removed.\nThe built-in preset with the same file name will be used again.\nChanges in the user file will be lost.",
    },
    "page.winws1_user_presets.dialog.reset_single.button": {
        "ru": "Вернуть встроенный",
        "en": "Restore built-in",
    },
    "page.winws1_user_presets.dialog.delete_single.title": {
        "ru": "Удалить пресет?",
        "en": "Delete preset?",
    },
    "page.winws1_user_presets.dialog.delete_single.body": {
        "ru": "Пользовательский пресет «{name}» будет удалён.\nИзменения в нём будут потеряны.\nВернуть его можно только создав новый пресет или импортировав txt-файл.",
        "en": "Preset '{name}' will be removed from the user presets list.\nChanges in this preset will be lost.\nYou can restore it only by creating a new preset or importing a file.",
    },
    "page.winws1_user_presets.dialog.delete_single.button": {
        "ru": "Удалить",
        "en": "Delete",
    },
    "page.winws1_user_presets.dialog.create.title": {
        "ru": "Новый пресет",
        "en": "New preset",
    },
    "page.winws1_user_presets.dialog.create.subtitle": {
        "ru": "Сохраните текущие настройки как отдельный пресет, чтобы быстро переключаться между разными настройками.",
        "en": "Save current settings as a separate preset to switch between configurations quickly.",
    },
    "page.winws1_user_presets.dialog.create.name": {
        "ru": "Название",
        "en": "Name",
    },
    "page.winws1_user_presets.dialog.create.placeholder": {
        "ru": "Например: Игры / YouTube / Дом",
        "en": "For example: Games / YouTube / Home",
    },
    "page.winws1_user_presets.dialog.create.source": {
        "ru": "Создать на основе",
        "en": "Create from",
    },
    "page.winws1_user_presets.dialog.create.source.current": {
        "ru": "Текущего пресета",
        "en": "Current active",
    },
    "page.winws1_user_presets.dialog.create.source.standard": {
        "ru": "Встроенного пресета",
        "en": "Standard preset",
    },
    "page.winws1_user_presets.dialog.create.button.create": {
        "ru": "Создать",
        "en": "Create",
    },
    "page.winws1_user_presets.dialog.rename.title": {
        "ru": "Переименовать",
        "en": "Rename",
    },
    "page.winws1_user_presets.dialog.rename.subtitle": {
        "ru": "Имя пресета отображается в списке и используется для переключения.",
        "en": "Preset name is shown in the list and used for switching.",
    },
    "page.winws1_user_presets.dialog.rename.current_name": {
        "ru": "Текущее имя: {name}",
        "en": "Current name: {name}",
    },
    "page.winws1_user_presets.dialog.rename.new_name": {
        "ru": "Новое имя",
        "en": "New name",
    },
    "page.winws1_user_presets.dialog.rename.placeholder": {
        "ru": "Новое имя...",
        "en": "New name...",
    },
    "page.winws1_user_presets.dialog.rename.button": {
        "ru": "Переименовать",
        "en": "Rename",
    },
    "page.winws1_user_presets.dialog.validation.enter_name": {
        "ru": "Введите название.",
        "en": "Enter a name.",
    },
    "page.winws1_user_presets.dialog.validation.exists": {
        "ru": "Пресет «{name}» уже существует.",
        "en": "Preset '{name}' already exists.",
    },
    "page.winws1_user_presets.dialog.import_exists.title": {
        "ru": "Пресет существует",
        "en": "Preset exists",
    },
    "page.winws1_user_presets.dialog.import_exists.body": {
        "ru": "Пресет «{name}» уже существует. Импортировать с другим именем?",
        "en": "Preset '{name}' already exists. Import with another name?",
    },
    "page.winws1_user_presets.dialog.reset_all.title": {
        "ru": "Вернуть встроенные пресеты",
        "en": "Restore default presets",
    },
    "page.winws1_user_presets.dialog.reset_all.body": {
        "ru": "Мы вернём встроенные пресеты к состоянию после установки.\nЕсли вы меняли встроенный пресет, эти изменения будут потеряны.\nПользовательские пресеты с другими именами останутся.\nТекущий выбранный пресет будет применён заново.",
        "en": "Built-in presets will be restored to their post-install state.\nYour changes to built-in presets will be lost.\nCustom presets with other names will remain.\nCurrent selected preset will be re-applied automatically.",
    },
    "page.winws1_user_presets.dialog.reset_all.button": {
        "ru": "Вернуть встроенные",
        "en": "Restore defaults",
    },
    "page.winws1_user_presets.section.games": {
        "ru": "Игры (game filter)",
        "en": "Games (game filter)",
    },
    "page.winws1_user_presets.section.all_tcp_udp": {
        "ru": "Все сайты и игры (ALL TCP/UDP)",
        "en": "All sites and games (ALL TCP/UDP)",
    },
    "page.winws1_user_presets.empty.not_found": {
        "ru": "По этому поиску пресетов нет. Измените запрос или очистите строку поиска.",
        "en": "No presets match this search. Change the query or clear the search field.",
    },
    "page.winws1_user_presets.empty.none": {
        "ru": "Пресеты не найдены. Создайте новый пресет или импортируйте txt-файл.",
        "en": "No presets. Create a new one or import from file.",
    },
    "page.winws1_user_presets.error.generic": {
        "ru": "Ошибка: {error}",
        "en": "Error: {error}",
    },
    "page.winws1_user_presets.error.create_failed": {
        "ru": "Не удалось создать пресет.",
        "en": "Failed to create preset.",
    },
    "page.winws1_user_presets.error.rename_failed": {
        "ru": "Не удалось переименовать пресет.",
        "en": "Failed to rename preset.",
    },
    "page.winws1_user_presets.error.activate_failed": {
        "ru": "Не удалось активировать пресет '{name}'",
        "en": "Failed to activate preset '{name}'",
    },
    "page.winws1_user_presets.error.duplicate_failed": {
        "ru": "Не удалось дублировать пресет",
        "en": "Failed to duplicate preset",
    },
    "page.winws1_user_presets.error.reset_failed": {
        "ru": "Не удалось вернуть встроенный пресет",
        "en": "Failed to restore built-in preset",
    },
    "page.winws1_user_presets.error.delete_failed": {
        "ru": "Не удалось удалить пресет",
        "en": "Failed to delete preset",
    },
    "page.winws1_user_presets.error.import_failed": {
        "ru": "Не удалось импортировать пресет",
        "en": "Failed to import preset",
    },
    "page.winws1_user_presets.error.import_exception": {
        "ru": "Не удалось импортировать пресет: {error}",
        "en": "Import error: {error}",
    },
    "page.winws1_user_presets.error.open_folder": {
        "ru": "Не удалось открыть папку пресетов: {error}",
        "en": "Could not open presets folder: {error}",
    },
    "page.winws1_user_presets.error.export_failed": {
        "ru": "Не удалось экспортировать пресет",
        "en": "Failed to export preset",
    },
    "page.winws1_user_presets.error.restore_deleted": {
        "ru": "Ошибка восстановления: {error}",
        "en": "Restore error: {error}",
    },
    "page.winws1_user_presets.error.reset_all_exception": {
        "ru": "Ошибка восстановления пресетов: {error}",
        "en": "Preset restore error: {error}",
    },
    "page.winws1_user_presets.error.open_telegram": {
        "ru": "Не удалось открыть страницу пресетов: {error}",
        "en": "Failed to open presets page: {error}",
    },
    "page.winws1_user_presets.file_dialog.import_title": {
        "ru": "Импортировать пресет",
        "en": "Import preset",
    },
    "page.winws1_user_presets.file_dialog.export_title": {
        "ru": "Экспортировать пресет",
        "en": "Export preset",
    },
    "page.winws1_user_presets.infobar.success": {
        "ru": "Успех",
        "en": "Success",
    },
    "page.winws1_user_presets.info.exported": {
        "ru": "Пресет экспортирован: {path}",
        "en": "Preset exported: {path}",
    },
    "page.winws1_user_presets.info.title": {
        "ru": "Что это такое?",
        "en": "What is this?",
    },
    "page.winws1_user_presets.info.body": {
        "ru": (
            "Пресет, или конфиг, — это один или несколько .txt-файлов со списком флагов Zapret. "
            "Формат такой же, как у winws2.exe или winws.exe, поэтому GUI может быстро читать и менять настройки.\n\n"
            "Пресеты доступны с Zapret2 v20.3 для режимов Zapret 1 и Zapret 2. "
            "Они нужны, чтобы быстрее делать новые настройки, проще обмениваться ими и держать GUI и консольный Zapret в одном формате.\n\n"
            "При запуске активный пресет передаётся в winws2.exe для Zapret 2 или в winws.exe для Zapret 1 через @<config_file>. "
            "Это значит: прочитать параметры командной строки из файла. Остальные параметры командной строки при таком запуске не используются.\n\n"
            "Файл %AppData%\\ZapretTwoDev\\preset-zapret2.txt хранит только активный пресет. "
            "Сам по себе он не считается пользовательским пресетом. Ваши пресеты лежат в папке presets. "
            "По умолчанию используется Default, также есть встроенный Gaming.\n\n"
            "Пресетами можно обмениваться напрямую.\n\n"
            "Почему пресеты иногда плохо подходят: в них стратегии часто заранее прописаны под разные фильтры и hostlist. "
            "Из-за этого один сайт может заработать, а другой перестать. Для более точной настройки лучше использовать прямой запуск: "
            "там стратегия подбирается отдельно для нужной категории и hostlist."
        ),
        "en": (
            "A preset, or config, is one or more .txt files with Zapret flags. "
            "It uses the same format as winws2.exe or winws.exe, so the GUI can read and edit these settings.\n\n"
            "The active preset is passed to winws2.exe for Zapret 2 or winws.exe for Zapret 1 through @<config_file>, "
            "which means: read command-line options from a file. Other command-line options are not used in this launch mode.\n\n"
            "%AppData%\\ZapretTwoDev\\preset-zapret2.txt only stores the active preset copy. "
            "User presets are stored in the presets folder. More details are available from the button below."
        ),
    },
    "page.winws1_user_presets.info.open_site.button": {
        "ru": "Открыть сайт с пресетами",
        "en": "Open preset site",
    },
    "page.winws1_user_presets.info.open_site.description": {
        "ru": "Открывает сайт, где можно посмотреть и скачать пресеты.",
        "en": "Opens the site where presets can be viewed and downloaded.",
    },
    "page.winws1_profile_setup.title": {
        "ru": "Настройка профиля",
        "en": "Profile setup",
    },
    "page.winws1_profile_setup.breadcrumb.control": {
        "ru": "Управление",
        "en": "Control",
    },
    "page.winws2_control.subtitle": {
        "ru": "Настройка и запуск Zapret 2. В «Мои пресеты» выбирается пресет, а в «Настройка пресета» меняются профили и выбранные для них готовые стратегии.",
        "en": "Configure and launch Zapret 2. My presets selects a preset; preset setup changes profiles and ready strategies.",
    },
    "page.winws2_control.section.status": {
        "ru": "Статус работы",
        "en": "Service Status",
    },
    "page.winws2_control.section.management": {
        "ru": "Управление Zapret 2",
        "en": "Zapret 2 Control",
    },
    "page.winws2_control.section.preset_switch": {
        "ru": "Сменить пресет обхода блокировок",
        "en": "Switch Bypass Preset",
    },
    "page.winws2_control.section.profile_tuning": {
        "ru": "Настройка пресета",
        "en": "Preset setup",
    },
    "page.winws2_control.section.program_settings": {
        "ru": "Настройки программы",
        "en": "Program Settings",
    },
    "page.winws2_control.section.additional_settings": {
        "ru": "Дополнительные настройки",
        "en": "Additional Settings",
    },
    "page.winws2_control.section.additional": {
        "ru": "Дополнительно",
        "en": "Additional",
    },
    "page.winws2_control.status.checking": {
        "ru": "Проверка...",
        "en": "Checking...",
    },
    "page.winws2_control.status.detecting": {
        "ru": "Определение состояния процесса",
        "en": "Detecting process state",
    },
    "page.winws2_control.status.running": {
        "ru": "Zapret работает",
        "en": "Zapret is running",
    },
    "page.winws2_control.status.stopped": {
        "ru": "Zapret остановлен",
        "en": "Zapret stopped",
    },
    "page.winws2_control.status.bypass_active": {
        "ru": "Обход блокировок активен",
        "en": "Bypass is active",
    },
    "page.winws2_control.status.press_start": {
        "ru": "Нажмите «Запустить» для активации",
        "en": "Press Start to activate",
    },
    "page.winws2_control.button.start": {
        "ru": "Запустить Zapret",
        "en": "Start Zapret",
    },
    "page.winws2_control.button.stop_only_winws": {
        "ru": f"Остановить только {EXE_NAME_WINWS1}",
        "en": f"Stop only {EXE_NAME_WINWS1}",
    },
    "page.winws2_control.button.stop_only_template": {
        "ru": "Остановить только {exe_name}",
        "en": "Stop only {exe_name}",
    },
    "page.winws2_control.button.stop_and_exit": {
        "ru": "Остановить и закрыть программу",
        "en": "Stop and close app",
    },
    "page.winws2_control.button.my_presets": {
        "ru": "Мои пресеты",
        "en": "My presets",
    },
    "page.winws2_control.button.open": {
        "ru": "Открыть",
        "en": "Open",
    },
    "page.winws2_control.preset.not_selected": {
        "ru": "Не выбран",
        "en": "Not selected",
    },
    "page.winws2_control.preset.current": {
        "ru": "Текущий выбранный пресет",
        "en": "Current selected preset",
    },
    "page.winws2_control.card.advanced": {
        "ru": "Дополнительные настройки",
        "en": "ADVANCED SETTINGS",
    },
    "page.winws2_control.advanced.warning": {
        "ru": "Изменяйте только если знаете что делаете",
        "en": "Change only if you know what you are doing",
    },
    "page.winws2_control.button.connection_test": {
        "ru": "Тест соединения",
        "en": "Connection Test",
    },
    "page.winws2_control.button.open_folder": {
        "ru": "Открыть папку",
        "en": "Open Folder",
    },
    "page.winws2_control.button.documentation": {
        "ru": "Документация",
        "en": "Documentation",
    },
    "page.winws2_pages.title": {
        "ru": "Настройка пресета",
        "en": "Preset setup",
    },
    "page.winws2_pages.back.control": {
        "ru": "Управление",
        "en": "Control",
    },
    "page.winws2_pages.current.not_selected": {
        "ru": "Не выбрана",
        "en": "Not selected",
    },
    "page.winws2_pages.request.button": {
        "ru": "ОТКРЫТЬ ФОРМУ НА GITHUB",
        "en": "OPEN GITHUB FORM",
    },
    "page.winws2_pages.toolbar.title": {
        "ru": "Профили",
        "en": "Profiles",
    },
    "page.winws2_pages.toolbar.expand": {
        "ru": "Развернуть",
        "en": "Expand",
    },
    "page.winws2_pages.toolbar.collapse": {
        "ru": "Свернуть",
        "en": "Collapse",
    },
    "page.winws2_pages.toolbar.view_menu": {
        "ru": "Вид",
        "en": "View",
    },
    "page.winws2_pages.toolbar.show_added_only": {
        "ru": "Показать только добавленные",
        "en": "Show added only",
    },
    "page.winws2_pages.toolbar.show_all_profiles": {
        "ru": "Показать все профили",
        "en": "Show all profiles",
    },
    "page.winws2_pages.toolbar.info": {
        "ru": "Что это такое?",
        "en": "What is this?",
    },
    "page.winws2_pages.toolbar.search.placeholder": {
        "ru": "Поиск профиля по имени, портам и т.д.",
        "en": "Search profiles by name, ports, etc.",
    },
    "page.winws2_pages.info.title": {
        "ru": "Настройка пресета",
        "en": "Preset setup",
    },
    "page.winws2_user_presets.title": {
        "ru": "Мои пресеты",
        "en": "My Presets",
    },
    "page.winws2_user_presets.back.control": {
        "ru": "Управление",
        "en": "Control",
    },
    "page.winws2_user_presets.configs.title": {
        "ru": "Обменивайтесь пресетами и профилями в разделе GitHub Discussions",
        "en": "Share presets and profiles in GitHub Discussions",
    },
    "page.winws2_user_presets.configs.button": {
        "ru": "Получить конфиги",
        "en": "Get configs",
    },
    "page.winws2_user_presets.button.import": {
        "ru": "Импорт",
        "en": "Import",
    },
    "page.winws2_user_presets.button.open_folder": {
        "ru": "Папка пресетов",
        "en": "Presets folder",
    },
    "page.winws2_user_presets.button.reset_all": {
        "ru": "Вернуть встроенные",
        "en": "Restore defaults",
    },
    "page.winws2_user_presets.button.wiki": {
        "ru": "Вики по пресетам",
        "en": "Preset wiki",
    },
    "page.winws2_user_presets.button.what_is_this": {
        "ru": "Что это такое?",
        "en": "What is this?",
    },
    "page.winws2_user_presets.search.placeholder": {
        "ru": "Поиск пресетов по имени...",
        "en": "Search presets by name...",
    },
    "page.winws2_user_presets.tooltip.create": {
        "ru": "Создать новый пресет",
        "en": "Create a new preset",
    },
    "page.winws2_user_presets.tooltip.import": {
        "ru": "Импорт пресета из файла",
        "en": "Import preset from file",
    },
    "page.winws2_user_presets.tooltip.open_folder": {
        "ru": "Открыть папку, где лежат ваши пресеты",
        "en": "Open the folder where your presets are stored",
    },
    "page.winws2_user_presets.tooltip.reset_all": {
        "ru": "Возвращает встроенные пресеты. Ваши изменения во встроенных пресетах будут потеряны.",
        "en": "Restores built-in presets. Your changes to built-in presets will be lost.",
    },
    "page.winws2_user_presets.delegate.tooltip.rename": {
        "ru": "Переименовать",
        "en": "Rename",
    },
    "page.winws2_user_presets.delegate.tooltip.duplicate": {
        "ru": "Дублировать",
        "en": "Duplicate",
    },
    "page.winws2_user_presets.delegate.tooltip.reset": {
        "ru": "Вернуть встроенный",
        "en": "Restore built-in",
    },
    "page.winws2_user_presets.delegate.tooltip.delete": {
        "ru": "Удалить",
        "en": "Delete",
    },
    "page.winws2_user_presets.delegate.tooltip.export": {
        "ru": "Экспорт",
        "en": "Export",
    },
    "page.winws2_user_presets.delegate.tooltip.confirm_again": {
        "ru": "Нажмите ещё раз для подтверждения",
        "en": "Click again to confirm",
    },
    "page.winws2_user_presets.delegate.badge.active": {
        "ru": "Активен",
        "en": "Active",
    },
    "page.winws2_user_presets.dialog.button.cancel": {
        "ru": "Отмена",
        "en": "Cancel",
    },
    "page.winws2_user_presets.dialog.reset_single.title": {
        "ru": "Вернуть встроенный пресет?",
        "en": "Restore built-in preset?",
    },
    "page.winws2_user_presets.dialog.reset_single.body": {
        "ru": "Будет удалён ваш изменённый файл пресета «{name}».\nПосле этого снова появится встроенный пресет с тем же именем файла.\nИзменения в этом файле будут потеряны.",
        "en": "User preset file '{name}' will be removed.\nThe built-in preset with the same file name will be used again.\nChanges in the user file will be lost.",
    },
    "page.winws2_user_presets.dialog.reset_single.button": {
        "ru": "Вернуть встроенный",
        "en": "Restore built-in",
    },
    "page.winws2_user_presets.dialog.delete_single.title": {
        "ru": "Удалить пресет?",
        "en": "Delete preset?",
    },
    "page.winws2_user_presets.dialog.delete_single.body": {
        "ru": "Пользовательский пресет «{name}» будет удалён.\nИзменения в нём будут потеряны.\nВернуть его можно только создав новый пресет или импортировав txt-файл.",
        "en": "Preset '{name}' will be removed from the user presets list.\nChanges in this preset will be lost.\nYou can restore it only by creating a new preset or importing a file.",
    },
    "page.winws2_user_presets.dialog.delete_single.button": {
        "ru": "Удалить",
        "en": "Delete",
    },
    "page.winws2_user_presets.dialog.create.title": {
        "ru": "Новый пресет",
        "en": "New preset",
    },
    "page.winws2_user_presets.dialog.create.subtitle": {
        "ru": "Сохраните текущие настройки как отдельный пресет, чтобы быстро переключаться между разными настройками.",
        "en": "Save current settings as a separate preset to switch between configurations quickly.",
    },
    "page.winws2_user_presets.dialog.create.name": {
        "ru": "Название",
        "en": "Name",
    },
    "page.winws2_user_presets.dialog.create.placeholder": {
        "ru": "Например: Игры / YouTube / Дом",
        "en": "For example: Games / YouTube / Home",
    },
    "page.winws2_user_presets.dialog.create.source": {
        "ru": "Создать на основе",
        "en": "Create from",
    },
    "page.winws2_user_presets.dialog.create.source.current": {
        "ru": "Текущего пресета",
        "en": "Current active",
    },
    "page.winws2_user_presets.dialog.create.source.standard": {
        "ru": "Встроенного пресета",
        "en": "Standard preset",
    },
    "page.winws2_user_presets.dialog.create.button.create": {
        "ru": "Создать",
        "en": "Create",
    },
    "page.winws2_user_presets.dialog.rename.title": {
        "ru": "Переименовать",
        "en": "Rename",
    },
    "page.winws2_user_presets.dialog.rename.subtitle": {
        "ru": "Имя пресета отображается в списке и используется для переключения.",
        "en": "Preset name is shown in the list and used for switching.",
    },
    "page.winws2_user_presets.dialog.rename.current_name": {
        "ru": "Текущее имя: {name}",
        "en": "Current name: {name}",
    },
    "page.winws2_user_presets.dialog.rename.new_name": {
        "ru": "Новое имя",
        "en": "New name",
    },
    "page.winws2_user_presets.dialog.rename.placeholder": {
        "ru": "Новое имя...",
        "en": "New name...",
    },
    "page.winws2_user_presets.dialog.rename.button": {
        "ru": "Переименовать",
        "en": "Rename",
    },
    "page.winws2_user_presets.dialog.validation.enter_name": {
        "ru": "Введите название.",
        "en": "Enter a name.",
    },
    "page.winws2_user_presets.dialog.validation.exists": {
        "ru": "Пресет «{name}» уже существует.",
        "en": "Preset ""{name}"" already exists.",
    },
    "page.winws2_user_presets.dialog.import_exists.title": {
        "ru": "Пресет существует",
        "en": "Preset exists",
    },
    "page.winws2_user_presets.dialog.import_exists.body": {
        "ru": "Пресет «{name}» уже существует. Импортировать с другим именем?",
        "en": "Preset '{name}' already exists. Import with another name?",
    },
    "page.winws2_user_presets.dialog.reset_all.title": {
        "ru": "Вернуть встроенные пресеты",
        "en": "Restore default presets",
    },
    "page.winws2_user_presets.dialog.reset_all.body": {
        "ru": "Мы вернём встроенные пресеты к состоянию после установки.\nЕсли вы меняли встроенный пресет, эти изменения будут потеряны.\nПользовательские пресеты с другими именами останутся.\nТекущий выбранный пресет будет применён заново.",
        "en": "Built-in presets will be restored to their post-install state.\nYour changes to built-in presets will be lost.\nCustom presets with other names will remain.\nCurrent selected preset will be re-applied automatically.",
    },
    "page.winws2_user_presets.dialog.reset_all.button": {
        "ru": "Вернуть встроенные",
        "en": "Restore defaults",
    },
    "page.winws2_user_presets.section.games": {
        "ru": "Игры (game filter)",
        "en": "Games (game filter)",
    },
    "page.winws2_user_presets.section.all_tcp_udp": {
        "ru": "Все сайты и игры(ALL TCP/UDP)",
        "en": "All sites and games (ALL TCP/UDP)",
    },
    "page.winws2_user_presets.empty.not_found": {
        "ru": "По этому поиску пресетов нет. Измените запрос или очистите строку поиска.",
        "en": "No presets match this search. Change the query or clear the search field.",
    },
    "page.winws2_user_presets.empty.none": {
        "ru": "Пресеты не найдены. Создайте новый пресет или импортируйте txt-файл.",
        "en": "No presets. Create a new one or import from file.",
    },
    "page.winws2_user_presets.error.generic": {
        "ru": "Ошибка: {error}",
        "en": "Error: {error}",
    },
    "page.winws2_user_presets.error.create_failed": {
        "ru": "Не удалось создать пресет.",
        "en": "Failed to create preset.",
    },
    "page.winws2_user_presets.error.rename_failed": {
        "ru": "Не удалось переименовать пресет.",
        "en": "Failed to rename preset.",
    },
    "page.winws2_user_presets.error.activate_failed": {
        "ru": "Не удалось активировать пресет '{name}'",
        "en": "Failed to activate preset '{name}'",
    },
    "page.winws2_user_presets.error.duplicate_failed": {
        "ru": "Не удалось дублировать пресет",
        "en": "Failed to duplicate preset",
    },
    "page.winws2_user_presets.error.reset_failed": {
        "ru": "Не удалось вернуть встроенный пресет",
        "en": "Failed to restore built-in preset",
    },
    "page.winws2_user_presets.error.delete_failed": {
        "ru": "Не удалось удалить пресет",
        "en": "Failed to delete preset",
    },
    "page.winws2_user_presets.error.import_failed": {
        "ru": "Не удалось импортировать пресет",
        "en": "Failed to import preset",
    },
    "page.winws2_user_presets.error.import_exception": {
        "ru": "Не удалось импортировать пресет: {error}",
        "en": "Import error: {error}",
    },
    "page.winws2_user_presets.error.open_folder": {
        "ru": "Не удалось открыть папку пресетов: {error}",
        "en": "Could not open presets folder: {error}",
    },
    "page.winws2_user_presets.error.export_failed": {
        "ru": "Не удалось экспортировать пресет",
        "en": "Failed to export preset",
    },
    "page.winws2_user_presets.error.restore_deleted": {
        "ru": "Ошибка восстановления: {error}",
        "en": "Restore error: {error}",
    },
    "page.winws2_user_presets.error.reset_all_exception": {
        "ru": "Ошибка восстановления пресетов: {error}",
        "en": "Preset restore error: {error}",
    },
    "page.winws2_user_presets.error.open_telegram": {
        "ru": "Не удалось открыть страницу пресетов: {error}",
        "en": "Failed to open presets page: {error}",
    },
    "page.winws2_user_presets.file_dialog.import_title": {
        "ru": "Импортировать пресет",
        "en": "Import preset",
    },
    "page.winws2_user_presets.file_dialog.export_title": {
        "ru": "Экспортировать пресет",
        "en": "Export preset",
    },
    "page.winws2_user_presets.infobar.success": {
        "ru": "Успех",
        "en": "Success",
    },
    "page.winws2_user_presets.info.exported": {
        "ru": "Пресет экспортирован: {path}",
        "en": "Preset exported: {path}",
    },
    "page.winws2_user_presets.info.title": {
        "ru": "Что это такое?",
        "en": "What is this?",
    },
    "page.winws2_user_presets.info.body": {
        "ru": (
            "Пресет, или конфиг, — это один или несколько .txt-файлов со списком флагов Zapret. "
            "Формат такой же, как у winws2.exe или winws.exe, поэтому GUI может быстро читать и менять настройки.\n\n"
            "Пресеты доступны с Zapret2 v20.3 для режимов Zapret 1 и Zapret 2. "
            "Они нужны, чтобы быстрее делать новые настройки, проще обмениваться ими и держать GUI и консольный Zapret в одном формате.\n\n"
            "При запуске активный пресет передаётся в winws2.exe для Zapret 2 или в winws.exe для Zapret 1 через @<config_file>. "
            "Это значит: прочитать параметры командной строки из файла. Остальные параметры командной строки при таком запуске не используются.\n\n"
            "Файл %AppData%\\ZapretTwoDev\\preset-zapret2.txt хранит только активный пресет. "
            "Сам по себе он не считается пользовательским пресетом. Ваши пресеты лежат в папке presets. "
            "По умолчанию используется Default, также есть встроенный Gaming.\n\n"
            "Пресетами можно обмениваться напрямую.\n\n"
            "Почему пресеты иногда плохо подходят: в них стратегии часто заранее прописаны под разные фильтры и hostlist. "
            "Из-за этого один сайт может заработать, а другой перестать. Для более точной настройки лучше использовать прямой запуск: "
            "там стратегия подбирается отдельно для нужной категории и hostlist."
        ),
        "en": (
            "A preset, or config, is one or more .txt files with Zapret flags. "
            "It uses the same format as winws2.exe or winws.exe, so the GUI can read and edit these settings.\n\n"
            "The active preset is passed to winws2.exe for Zapret 2 or winws.exe for Zapret 1 through @<config_file>, "
            "which means: read command-line options from a file. Other command-line options are not used in this launch mode.\n\n"
            "%AppData%\\ZapretTwoDev\\preset-zapret2.txt only stores the active preset copy. "
            "User presets are stored in the presets folder. More details are available from the button below."
        ),
    },
    "page.winws2_user_presets.info.open_site.button": {
        "ru": "Открыть сайт с пресетами",
        "en": "Open preset site",
    },
    "page.winws2_user_presets.info.open_site.description": {
        "ru": "Открывает сайт, где можно посмотреть и скачать пресеты.",
        "en": "Opens the site where presets can be viewed and downloaded.",
    },
    "page.winws2_profile_setup.title": {
        "ru": "Настройка профиля",
        "en": "Profile setup",
    },
    "page.winws2_profile_setup.preset_dialog.create.title": {
        "ru": "Создать пресет",
        "en": "Create preset",
    },
    "page.winws2_profile_setup.preset_dialog.rename.title": {
        "ru": "Переименовать пресет",
        "en": "Rename preset",
    },
    "page.winws2_profile_setup.preset_dialog.rename.current_name": {
        "ru": "Текущее имя: {name}",
        "en": "Current name: {name}",
    },
    "page.winws2_profile_setup.preset_dialog.name_label": {
        "ru": "Название",
        "en": "Name",
    },
    "page.winws2_profile_setup.preset_dialog.name_placeholder": {
        "ru": "Введите название пресета...",
        "en": "Enter preset name...",
    },
    "page.winws2_profile_setup.preset_dialog.button.create": {
        "ru": "Создать",
        "en": "Create",
    },
    "page.winws2_profile_setup.preset_dialog.button.rename": {
        "ru": "Переименовать",
        "en": "Rename",
    },
    "page.winws2_profile_setup.preset_dialog.button.cancel": {
        "ru": "Отмена",
        "en": "Cancel",
    },
    "page.winws2_profile_setup.preset_dialog.error.empty": {
        "ru": "Введите название пресета",
        "en": "Enter preset name",
    },
    "page.winws2_profile_setup.breadcrumb.control": {
        "ru": "Управление",
        "en": "Control",
    },
    "page.winws2_profile_setup.filter.hostlist": {
        "ru": "Hostlist",
        "en": "Hostlist",
    },
    "page.winws2_profile_setup.filter.ipset": {
        "ru": "IPset",
        "en": "IPset",
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
        "ru": f"Во время сканирования текущий обход DPI будет остановлен. Каждая стратегия тестируется отдельно через {ENGINE_WINWS2}. После завершения можно перезапустить обход.",
        "en": f"During scanning, the current DPI bypass will be stopped. Each strategy is tested separately through {ENGINE_WINWS2}. You can restart bypass after the scan finishes.",
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
    "page.winws1_pages.empty.no_categories": {
        "ru": "В выбранном пресете нет профилей, которые можно показать на этой странице. Попробуйте другой пресет или добавьте нужный профиль.",
        "en": "The selected preset has no profiles to show on this page. Try another preset or add the needed profile.",
    },
    "page.winws2_pages.request.hint": {
        "ru": "Хотите добавить новый сайт или сервис в Zapret 2? Откройте готовую форму на GitHub и опишите, что нужно добавить в hostlist или ipset.",
        "en": "Want to add a new site or service to Zapret 2? Open the GitHub form and describe what should be added to the hostlist or ipset.",
    },
    "page.winws2_pages.empty.no_presets": {
        "ru": "Пресеты Zapret 2 не найдены. Импортируйте пресет или переустановите приложение, чтобы вернуть встроенные пресеты.",
        "en": "Zapret 2 presets were not found. Import a preset or reinstall the app to restore built-in presets.",
    },
    "page.winws2_pages.empty.no_selected_preset": {
        "ru": "Не удалось понять, какой пресет выбран. Откройте «Мои пресеты» и выберите preset заново.",
        "en": "Could not determine which preset is selected. Open My Presets and choose a preset again.",
    },
    "page.winws2_pages.empty.preset_read_error": {
        "ru": "Не удалось открыть выбранный пресет «{preset_name}». Файл мог быть удалён, очищен или повреждён. Выберите другой пресет или верните встроенный.",
        "en": "Could not open the selected preset \"{preset_name}\". The file may have been deleted, emptied, or corrupted. Choose another preset or restore the built-in one.",
    },
    "page.winws2_pages.empty.unknown_error": {
        "ru": "Не удалось показать profile-ы preset-а «{preset_name}». Если ошибка повторится, выберите другой preset.",
        "en": "Could not show profiles from preset \"{preset_name}\". If the error repeats, choose another preset.",
    },
    "page.winws2_pages.empty.no_categories": {
        "ru": "В выбранном пресете «{preset_name}» нет профилей, которые можно показать на этой странице. Попробуйте другой пресет или добавьте нужный профиль.",
        "en": "The selected preset \"{preset_name}\" has no profiles to show on this page. Try another preset or add the needed profile.",
    },
    "page.winws2_pages.current.active_count": {
        "ru": "{count} активных",
        "en": "{count} active",
    },
    "page.winws2_pages.info.body": {
        "ru": "Здесь вы можете тонко изменить стратегию для каждого профиля, который найден в выбранном пресете. Всего существует несколько фаз дурения (send, syndata, fake, multisplit и т.д.). Последовательность сама определяется программой.\n\nВы можете править пресет вручную через txt-файл или выбрать готовую стратегию в этом меню. В интерфейсе готовая стратегия означает заранее собранный набор аргументов, который программа подставляет в профиль. Это не отдельный синтаксис winws2, а удобный способ выбрать техники дурения или фуллинга для TCP/IP-пакетов.",
        "en": "Here you can finely tune the strategy for each profile found in the selected preset. There are several obfuscation phases (send, syndata, fake, multisplit, etc.). Their sequence is determined by the app.\n\nYou can edit the preset manually in a txt file or choose a ready strategy in this menu. In the interface, a ready strategy means a prebuilt set of arguments that the app inserts into a profile. It is not separate winws2 syntax, but a convenient way to choose obfuscation or fooling techniques for TCP/IP packets.",
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
    "page.appearance.opacity.standard.title": {
        "ru": "Прозрачность окна",
        "en": "Window Opacity",
    },
    "page.appearance.opacity.standard.description": {
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
    "page.control.dialog.state_media_block_enable.title": {
        "ru": "Блокировка государственных СМИ РФ",
        "en": "Block Russian State Media",
    },
    "page.control.dialog.state_media_block_disable.title": {
        "ru": "Отключение блокировки государственных СМИ РФ",
        "en": "Disable Russian State Media Blocking",
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
    "page.winws2_control.setting.autostart.title": {
        "ru": "Автозапуск DPI после старта программы",
        "en": "Auto-start DPI after app launch",
    },
    "page.winws2_control.setting.autostart.desc": {
        "ru": "После запуска ZapretGUI автоматически запускать текущий DPI-режим",
        "en": "Automatically start the current DPI mode after ZapretGUI launches",
    },
    "page.winws2_control.strategy.autostart_disabled": {
        "ru": "Автозапуск DPI после старта программы отключён",
        "en": "Auto-start DPI after app launch is disabled",
    },
}

TEXTS.update(TEXTS_PAGES_FINAL)


NAV_PAGE_TEXT_KEYS: dict[PageName, str] = {
    PageName.ZAPRET2_MODE_CONTROL: "nav.page.zapret2_mode_control",
    PageName.ZAPRET1_MODE_CONTROL: "nav.page.zapret1_mode_control",
    PageName.ORCHESTRA: "nav.page.orchestra",
    PageName.ORCHESTRA_SETTINGS: "nav.page.orchestra_settings",
    PageName.DPI_SETTINGS: "nav.page.dpi_settings",
    PageName.NETWORK: "nav.page.network",
    PageName.HOSTS: "nav.page.hosts",
    PageName.BLOCKCHECK: "nav.page.blockcheck",
    PageName.WINWS_LOG_ANALYZER: "nav.page.winws_log_analyzer",
    PageName.APPEARANCE: "nav.page.appearance",
    PageName.PREMIUM: "nav.page.premium",
    PageName.LOGS: "nav.page.logs",
    PageName.SERVERS: "page.servers.title",
    PageName.ABOUT: "nav.page.about",
    PageName.SUPPORT: "page.support.title",
    PageName.ZAPRET2_PRESET_SETUP: "nav.page.zapret2_mode",
    PageName.ZAPRET2_USER_PRESETS: "nav.page.zapret2_user_presets",
    PageName.ZAPRET2_PROFILE_SETUP: "page.winws2_profile_setup.title",
    PageName.ZAPRET1_PRESET_SETUP: "nav.page.zapret1_mode",
    PageName.ZAPRET1_USER_PRESETS: "nav.page.zapret1_user_presets",
    PageName.ZAPRET1_PROFILE_SETUP: "page.winws1_profile_setup.title",
}


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
