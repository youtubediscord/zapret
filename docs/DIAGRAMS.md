# Zapret2 GUI — Архитектурные диаграммы
## Содержание

1. [Общая архитектура](#1-общая-архитектура)
2. [Диаграмма модулей и зависимостей](#2-диаграмма-модулей-и-зависимостей)
3. [Диаграмма классов (ядро)](#3-диаграмма-классов-ядро)
4. [Диаграмма последовательности: запуск DPI](#4-диаграмма-последовательности-запуск-dpi)
5. [Диаграмма последовательности: оркестратор](#5-диаграмма-последовательности-оркестратор)
6. [Диаграмма состояний: DPI процесс](#6-диаграмма-состояний-dpi-процесс)
7. [Диаграмма потоков: инициализация приложения](#7-диаграмма-потоков-инициализация-приложения)
8. [Структура стратегий](#8-структура-стратегий)
9. [Схема автозапуска](#9-схема-автозапуска)
10. [Схема DNS настройки (Win32 API)](#10-схема-dns-настройки-win32-api)
11. [Схема работы с файлом hosts](#11-схема-работы-с-файлом-hosts)
12. [Схема Premium подписки](#12-схема-premium-подписки)
13. [Схема Telegram интеграции](#13-схема-telegram-интеграции)
14. [Граф наследования UI компонентов](#14-граф-наследования-ui-компонентов)
15. [Схема сборки и распространения](#15-схема-сборки-и-распространения)


## 1. Общая архитектура

```mermaid
graph TB
    subgraph "Пользовательский интерфейс (PyQt6)"
        MAIN[main.py<br/>точка входа]
        UI[ui/]
        SIDEBAR[sidebar.py<br/>боковая навигация]
        PAGES[pages/<br/>страницы приложения]
        THEME[theme.py<br/>управление темами]
    end
    
    subgraph "Ядро приложения"
        DPI[dpi/<br/>управление DPI]
        STRATEGY[strategy_menu/<br/>стратегии обхода]
        ORCHESTRA[orchestra/<br/>оркестратор]
        DNS[dns/<br/>DNS настройки]
        HOSTS[hosts/<br/>управление hosts]
    end
    
    subgraph "Инфраструктура"
        CONFIG[config/<br/>конфигурация, реестр]
        LOG[log/<br/>логирование, краш-хендлер]
        AUTOSTART[autostart/<br/>автозапуск]
        UPDATER[updater/<br/>обновления]
        TGRAM[tgram/<br/>Telegram интеграция]
        DONATER[donater/<br/>Premium подписка]
    end
    
    subgraph "Системный уровень"
        WINAPI[Windows API]
        REG[Реестр Windows]
        NSSM[NSSM<br/>Service Manager]
        WINDIVERT[WinDivert драйвер]
        SUBPROC[subprocess]
    end
    
    subgraph "Внешние сервисы"
        GITHUB[GitHub API<br/>стратегии, обновления]
        TELEGRAM[Telegram Bot API<br/>отправка логов]
        PREMIUM[Premium API<br/>проверка подписки]
    end
    
    MAIN --> UI
    MAIN --> DPI
    UI --> SIDEBAR
    UI --> PAGES
    UI --> THEME
    
    DPI --> STRATEGY
    DPI --> ORCHESTRA
    DPI --> WINAPI
    DPI --> SUBPROC
    
    STRATEGY --> CONFIG
    ORCHESTRA --> CONFIG
    DNS --> WINAPI
    HOSTS --> WINAPI
    HOSTS --> REG
    
    AUTOSTART --> NSSM
    AUTOSTART --> WINAPI
    AUTOSTART --> REG
    
    UPDATER --> GITHUB
    TGRAM --> TELEGRAM
    DONATER --> PREMIUM
    
    LOG --> WINAPI
    CONFIG --> REG
    
    style MAIN fill:#4c8ee7,stroke:#2c5aa3,color:#fff
    style DPI fill:#6ccb5f,stroke:#3a8a2e,color:#fff
    style STRATEGY fill:#ffc107,stroke:#c98f00,color:#000
    style ORCHESTRA fill:#9b59b6,stroke:#6c3483,color:#fff
```


## 2. Диаграмма модулей и зависимостей

```mermaid
graph LR
    subgraph "UI Layer"
        MAIN[main.py]
        UI_PAGES[ui/pages/*]
        UI_WIDGETS[ui/widgets/*]
        SIDEBAR[ui/sidebar.py]
        TITLEBAR[ui/custom_titlebar.py]
        THEME[ui/theme.py]
    end
    
    subgraph "Managers"
        INIT_MGR[managers/initialization_manager.py]
        DPI_MGR[managers/dpi_manager.py]
        SUBSCR_MGR[managers/subscription_manager.py]
        UI_MGR[managers/ui_manager.py]
        PROCESS_MON[managers/process_monitor_manager.py]
    end
    
    subgraph "Core"
        DPI_CTRL[dpi/dpi_controller.py]
        BAT_START[dpi/bat_start.py]
        STOP[dpi/stop.py]
        HEALTH[dpi/process_health_check.py]
    end
    
    subgraph "Strategy"
        REGISTRY[strategy_menu/strategies_registry.py]
        COMBINE[strategy_menu/strategy_lists_separated.py]
        RUNNER[strategy_menu/strategy_runner.py]
        TABLE[strategy_menu/strategy_table_widget.py]
        BLOBS[strategy_menu/strategies/blobs.py]
    end
    
    subgraph "Orchestra"
        ORCH_RUNNER[orchestra/orchestra_runner.py]
        LOG_PARSER[orchestra/log_parser.py]
        LOCKED_MGR[orchestra/locked_strategies_manager.py]
        BLOCKED_MGR[orchestra/blocked_strategies_manager.py]
    end
    
    MAIN --> UI_PAGES
    MAIN --> INIT_MGR
    MAIN --> DPI_CTRL
    
    UI_PAGES --> SIDEBAR
    UI_PAGES --> TITLEBAR
    UI_PAGES --> THEME
    
    INIT_MGR --> DPI_MGR
    INIT_MGR --> SUBSCR_MGR
    INIT_MGR --> UI_MGR
    INIT_MGR --> PROCESS_MON
    
    DPI_MGR --> DPI_CTRL
    DPI_CTRL --> BAT_START
    DPI_CTRL --> RUNNER
    DPI_CTRL --> ORCH_RUNNER
    
    BAT_START --> RUNNER
    BAT_START --> STOP
    
    RUNNER --> REGISTRY
    RUNNER --> COMBINE
    RUNNER --> BLOBS
    
    ORCH_RUNNER --> LOG_PARSER
    ORCH_RUNNER --> LOCKED_MGR
    ORCH_RUNNER --> BLOCKED_MGR
    
    REGISTRY --> COMBINE
    TABLE --> REGISTRY
```


## 3. Диаграмма классов (ядро)

```mermaid
classDiagram
    direction TB
    
    class LupiDPIApp {
        -_is_exiting: bool
        -_splash_closed: bool
        -_dpi_autostart_initiated: bool
        +ui_manager: UIManager
        +dpi_manager: DPIManager
        +dpi_controller: DPIController
        +dpi_starter: BatDPIStart
        +theme_manager: ThemeManager
        +subscription_manager: SubscriptionManager
        +closeEvent(event)
        +restore_window_geometry()
        +set_status(text: str)
        +update_ui(running: bool)
    }
    
    class DPIController {
        -_dpi_start_thread: QThread
        -_dpi_stop_thread: QThread
        -_dpi_start_worker: DPIStartWorker
        +start_dpi_async(selected_mode, launch_method)
        +stop_dpi_async()
        +stop_and_exit_async()
        -_on_dpi_start_finished(success, error)
        -_on_dpi_stop_finished(success, error)
    }
    
    class DPIStartWorker {
        +finished: pyqtSignal(bool, str)
        +progress: pyqtSignal(str)
        +run()
        -_start_direct() bool
        -_start_bat() bool
        -_start_orchestra() bool
    }
    
    class BatDPIStart {
        -winws_exe: str
        -status_callback: Callable
        +check_process_running_fast() bool
        +start_dpi(selected_mode) bool
        +stop_all_processes() bool
        +cleanup_windivert_service() bool
        -_execute_bat_file(bat_file, strategy_name) bool
        -_execute_bat_file_fallback(bat_file, strategy_name) bool
    }
    
    class StrategyRunner {
        -winws_exe: str
        -running_process: Popen
        -work_dir: str
        -lists_dir: str
        +start_strategy_custom(args, name, retry) bool
        +stop() bool
        +is_running() bool
        -_resolve_file_paths(args) List[str]
        -_apply_filters(args) List[str]
        -_aggressive_windivert_cleanup()
    }
    
    class OrchestraRunner {
        -winws_exe: str
        -running_process: Popen
        -output_thread: Thread
        -locked_manager: LockedStrategiesManager
        -blocked_manager: BlockedStrategiesManager
        +prepare() bool
        +start() bool
        +stop() bool
        +is_running() bool
        -_generate_circular_config() bool
        -_generate_learned_lua() str
        -_read_output()
    }
    
    class StrategiesRegistry {
        -_categories: Dict[str, CategoryInfo]
        -_strategies_cache: Dict
        -_sorted_keys_cache: List
        +get_category_strategies(category) Dict
        +get_strategy_args_safe(category, strategy_id) str
        +get_all_category_keys() List[str]
        +get_default_selections() Dict
    }
    
    class ThemeManager {
        -app: QApplication
        -widget: QWidget
        -current_theme: str
        -_theme_applied: bool
        -_premium_cache: Tuple
        +apply_theme_async(theme_name, persist, callback)
        +get_available_themes() List[str]
        +get_clean_theme_name(display_name) str
        -_on_theme_css_ready(css, theme_name)
        -_apply_css_only(css, theme_name, persist)
    }
    
    LupiDPIApp --> DPIController : управляет
    LupiDPIApp --> BatDPIStart : содержит
    LupiDPIApp --> ThemeManager : содержит
    LupiDPIApp --> StrategiesRegistry : использует
    
    DPIController --> DPIStartWorker : создаёт
    DPIController --> BatDPIStart : вызывает
    
    DPIStartWorker --> BatDPIStart : использует
    DPIStartWorker --> StrategyRunner : использует
    DPIStartWorker --> OrchestraRunner : использует
    
    BatDPIStart --> StrategyRunner : использует
    
    OrchestraRunner --> StrategiesRegistry : использует
    OrchestraRunner --> LockedStrategiesManager : использует
    OrchestraRunner --> BlockedStrategiesManager : использует
```


## 4. Диаграмма последовательности: запуск DPI

```mermaid
sequenceDiagram
    participant User
    participant ControlPage as zapret2/direct_control_page.py
    participant DPI_CTRL as dpi_controller.py
    participant Worker as DPIStartWorker
    participant BatStart as bat_start.py
    participant Runner as strategy_runner.py
    participant WinWS as winws2.exe
    participant Killer as process_killer.py
    
    User->>ControlPage: Нажать "Запустить"
    activate ControlPage
    ControlPage->>ControlPage: show_loading()
    ControlPage->>DPI_CTRL: start_dpi_async()
    deactivate ControlPage
    
    activate DPI_CTRL
    DPI_CTRL->>DPI_CTRL: проверка running
    DPI_CTRL->>DPI_CTRL: создание QThread
    
    DPI_CTRL->>Worker: moveToThread(thread)
    DPI_CTRL->>Worker: run()
    activate Worker
    
    Worker->>Worker: определение launch_method
    
    alt launch_method == "direct"
        Worker->>Runner: get_strategy_runner()
        Worker->>Runner: start_strategy_custom(args, name)
        
        activate Runner
        Runner->>Runner: stop() (предыдущий процесс)
        Runner->>Killer: kill_winws_force()
        Runner->>Runner: _resolve_file_paths(args)
        Runner->>Runner: apply_all_filters(args)
        Runner->>WinWS: subprocess.Popen(cmd)
        WinWS-->>Runner: PID
        Runner-->>Worker: success=True
        deactivate Runner
        
    else launch_method == "orchestra"
        Worker->>Runner: OrchestraRunner.start()
        activate Runner
        Runner->>Runner: prepare()
        Runner->>Runner: load_existing_strategies()
        Runner->>Runner: _generate_circular_config()
        Runner->>Runner: _generate_learned_lua()
        Runner->>WinWS: subprocess.Popen([winws2.exe, @config])
        WinWS-->>Runner: PID
        Runner-->>Worker: success=True
        deactivate Runner
        
    else launch_method == "bat"
        Worker->>BatStart: start_dpi(selected_mode)
        activate BatStart
        BatStart->>BatStart: check_process_running_fast()
        BatStart->>BatStart: _execute_bat_file(bat_file)
        BatStart->>Runner: create_process_direct()
        Runner->>WinWS: subprocess.Popen()
        WinWS-->>Runner: PID
        Runner-->>BatStart: success
        BatStart-->>Worker: success
        deactivate BatStart
    end
    
    Worker->>Worker: проверка процесса
    Worker-->>DPI_CTRL: finished.emit(success, error)
    deactivate Worker
    
    DPI_CTRL->>DPI_CTRL: _on_dpi_start_finished()
    DPI_CTRL->>ControlPage: update_ui_state(running=True)
    DPI_CTRL->>ControlPage: show_success()
    deactivate DPI_CTRL
    
    ControlPage->>User: отображение статуса "Запущен"
```


## 5. Диаграмма последовательности: оркестратор

```mermaid
sequenceDiagram
    participant User
    participant OrchestraPage as orchestra/orchestra_page.py
    participant OR as orchestra_runner.py
    participant Parser as log_parser.py
    participant LockedMgr as locked_strategies_manager.py
    participant BlockedMgr as blocked_strategies_manager.py
    participant WinWS as winws2.exe
    participant Reg as Реестр Windows
    
    User->>OrchestraPage: Запуск оркестратора
    activate OrchestraPage
    OrchestraPage->>OR: start()
    deactivate OrchestraPage
    
    activate OR
    OR->>OR: prepare()
    OR->>OR: _generate_circular_config()
    OR->>OR: _generate_whitelist_file()
    OR->>OR: _generate_numbered_strategies()
    
    OR->>LockedMgr: load()
    LockedMgr->>Reg: чтение HKCU\Software\Zapret2Reg\Orchestra\TLS
    Reg-->>LockedMgr: locked_strategies
    LockedMgr-->>OR: locked_strategies
    
    OR->>BlockedMgr: load()
    BlockedMgr->>Reg: чтение HKCU\Software\Zapret2Reg\Orchestra\Blocked
    Reg-->>BlockedMgr: blocked_strategies
    BlockedMgr-->>OR: blocked_strategies
    
    OR->>OR: _generate_learned_lua()
    OR->>WinWS: subprocess.Popen([winws2.exe, @config, --lua-init=learned.lua])
    WinWS-->>OR: PID
    
    loop Чтение stdout
        WinWS-->>OR: строка лога
        OR->>Parser: parse_line(line)
        
        alt LOCK
            Parser-->>OR: EventType.LOCK
            OR->>LockedMgr: lock(hostname, strategy, proto)
            LockedMgr->>Reg: запись в реестр
            OR->>OrchestraPage: update_locked(hostname, strategy)
        else UNLOCK
            Parser-->>OR: EventType.UNLOCK
            OR->>LockedMgr: unlock(hostname, proto)
            LockedMgr->>Reg: удаление из реестра
            OR->>OrchestraPage: update_unlocked(hostname)
        else SUCCESS
            Parser-->>OR: EventType.SUCCESS
            OR->>LockedMgr: increment_history(hostname, strategy, success=True)
            OR->>OR: проверка lock_threshold (3 успеха)
            OR->>LockedMgr: lock(hostname, strategy)
            OR->>OrchestraPage: update_strategy_stats(hostname, strategy, successes)
        else FAIL
            Parser-->>OR: EventType.FAIL
            OR->>LockedMgr: increment_history(hostname, strategy, success=False)
            OR->>OR: проверка fail_threshold (2 неудачи)
            OR->>LockedMgr: unlock(hostname)
            OR->>OrchestraPage: update_strategy_stats(hostname, strategy, failures)
        else RST
            Parser-->>OR: EventType.RST
            OR->>OrchestraPage: log_message("RST detected")
        end
    end
    
    User->>OrchestraPage: Остановка
    OrchestraPage->>OR: stop()
    
    OR->>LockedMgr: save()
    LockedMgr->>Reg: запись стратегий
    OR->>LockedMgr: save_history()
    LockedMgr->>Reg: запись истории
    OR->>WinWS: terminate()
    deactivate OR
```


## 6. Диаграмма состояний: DPI процесс

```mermaid
stateDiagram-v2
    [*] --> Stopped
    
    state Stopped {
        [*] --> Idle
        Idle --> Configured: стратегия выбрана
        Configured --> Idle: сброс стратегии
    }
    
    Stopped --> Starting: нажать "Запустить"
    
    state Starting {
        [*] --> CheckRunning
        CheckRunning --> KillPrevious: процесс уже запущен
        KillPrevious --> Prepare
        CheckRunning --> Prepare: процесс не запущен
        Prepare --> Launch
        Launch --> Verify: Popen создан
        Verify --> [*]: процесс жив
        Verify --> Error: процесс упал сразу
    }
    
    Starting --> Running: успешный запуск
    Starting --> Stopped: ошибка запуска
    
    state Running {
        [*] --> Processing
        Processing --> Active: трафик идёт
        Active --> Processing: продолжение
        Processing --> [*]: ожидание
    }
    
    Running --> Stopping: нажать "Остановить"
    Running --> Crashed: краш процесса
    
    state Stopping {
        [*] --> Terminate
        Terminate --> Wait
        Wait --> Kill: таймаут 5 сек
        Kill --> Cleanup
        Cleanup --> [*]
    }
    
    Stopping --> Stopped: процесс остановлен
    
    Crashed --> Stopped: автоочистка
    Crashed --> Restarting: автоперезапуск
    Restarting --> Starting
```


## 7. Диаграмма потоков: инициализация приложения

```mermaid
flowchart TD
    Start(["Запуск main.py"]) --> CheckArgs{"--version?<br/>--update?"}
    CheckArgs -->|Да| HandleArgs["Обработка спец. аргументов"]
    HandleArgs --> Exit(["Выход"])
    
    CheckArgs -->|Нет| CheckAdmin{"Права<br/>администратора?"}
    CheckAdmin -->|Нет| Elevate["Запрос повышения прав"]
    Elevate --> Start
    
    CheckAdmin -->|Да| SingleInstance{"Другой<br/>экземпляр?"}
    SingleInstance -->|Да| IPC["Показать существующее окно"]
    IPC --> Exit
    
    SingleInstance -->|Нет| CheckConflicts{"GoodbyeDPI/<br/>mitmproxy?"}
    CheckConflicts -->|Да| ShowWarning["Показать предупреждение"]
    ShowWarning --> CheckConflicts
    
    CheckConflicts -->|Нет| InitQt["Инициализация QApplication"]
    InitQt --> InstallCrashHandler["Установка crash_handler"]
    InstallCrashHandler --> CreateWindow["Создание LupiDPIApp"]
    
    CreateWindow --> StartSplash["Показать SplashScreen"]
    StartSplash --> PreloadModules["Предзагрузка модулей<br/>фон"]
    
    PreloadModules --> InitTheme["ThemeManager.init"]
    InitTheme --> InitManagers["InitializationManager.run_async_init"]
    
    subgraph "Фаза 1 0-50ms"
        InitManagers --> InitDPICore["_init_dpi_starter<br/>_init_dpi_controller"]
    end
    
    subgraph "Фаза 2 60-100ms"
        InitDPICore --> InitManagersCore["_init_core_managers<br/>_init_network_managers"]
    end
    
    subgraph "Фаза 3 100-200ms"
        InitManagersCore --> InitThemeAsync["ThemeManager.apply_theme_async<br/>генерация CSS в фоне"]
    end
    
    subgraph "Фаза 4 200+ms"
        InitThemeAsync --> InitSubscr["SubscriptionManager.initialize_async"]
        InitSubscr --> CheckPremium["Проверка Premium подписки"]
    end
    
    InitThemeAsync --> ThemeReady["CSS готов"]
    ThemeReady --> CloseSplash["Закрыть Splash"]
    CloseSplash --> ShowWindow["Показать главное окно"]
    
    CheckPremium --> UpdateUI["Обновить UI<br/>темы, кнопка Premium"]
    
    ShowWindow --> CheckAutoStart{"DPI автозапуск?"}
    CheckAutoStart -->|Да| AutoStartDPI["DPIManager.delayed_dpi_start"]
    AutoStartDPI --> Ready(["Готово"])
    
    CheckAutoStart -->|Нет| Ready
```


## 8. Структура стратегий

```mermaid
graph TB
    subgraph "Источники стратегий"
        GITHUB[GitHub / nozapret.ru<br/>index.json]
        LOCAL_BAT[папка bat/<br/>локальные .bat файлы]
        BUILTIN_JSON[папка json/strategies/builtin/<br/>встроенные JSON стратегии]
        USER_JSON[папка json/strategies/user/<br/>пользовательские JSON]
    end
    
    subgraph "Загрузчики"
        STRAT_MGR[StrategyManager<br/>BAT режим]
        BAT_ZAPRET1[BatZapret1Manager<br/>сканирование .bat файлов]
        REGISTRY[StrategiesRegistry<br/>JSON стратегии]
        LOADER["strategy_loader.py<br/>load_category_strategies"]
    end
    
    subgraph "Обработка"
        FILTERS[apply_filters.py<br/>применение настроек]
        COMBINE["combine_strategies()<br/>объединение категорий"]
        BLOBS[blobs.py<br/>дедупликация блобов]
    end
    
    subgraph "Выполнение"
        RUNNER[StrategyRunner<br/>запуск winws2.exe]
        ORCHESTRA[OrchestraRunner<br/>автообучение]
    end
    
    subgraph "Хранение"
        REG[Реестр Windows<br/>HKCU\Software\Zapret2Reg]
        CACHE[кэш CSS, лог-файлы]
    end
    
    GITHUB --> STRAT_MGR
    LOCAL_BAT --> BAT_ZAPRET1
    BUILTIN_JSON --> LOADER
    USER_JSON --> LOADER
    
    LOADER --> REGISTRY
    STRAT_MGR --> REGISTRY
    BAT_ZAPRET1 --> REGISTRY
    
    REGISTRY --> COMBINE
    REGISTRY --> BLOBS
    
    COMBINE --> FILTERS
    FILTERS --> RUNNER
    
    REGISTRY --> ORCHESTRA
    ORCHESTRA --> REG
    
    RUNNER --> REG
    ORCHESTRA --> CACHE
```


## 9. Схема автозапуска

```mermaid
flowchart TD
    Start[Пользователь включает автозапуск] --> DetectMode{Режим запуска?}
    
    DetectMode -->|BAT режим| BAT[.bat стратегия]
    DetectMode -->|Direct режим| DIRECT[winws2.exe + Lua]
    DetectMode -->|Оркестратор| ORCH[winws2.exe + circular]
    
    BAT --> ChooseMethod{Тип автозапуска?}
    DIRECT --> ChooseMethod
    ORCH --> ChooseMethod
    
    ChooseMethod -->|GUI| GUI_METHOD[Автозапуск GUI]
    ChooseMethod -->|При входе| LOGIN_TASK[Задача ONLOGON]
    ChooseMethod -->|При загрузке| BOOT_TASK[Задача ONSTART]
    ChooseMethod -->|Служба| SERVICE[Служба Windows]
    
    GUI_METHOD --> SCHTASKS[schtasks /Create /TN ZapretGUI_AutoStart]
    
    LOGIN_TASK --> SCHTASKS_TASK[schtasks /Create /TN ZapretStrategy /SC ONLOGON]
    BOOT_TASK --> XML_TASK[создание XML задачи с триггером ONSTART]
    
    SERVICE --> NSSM_CHECK{NSSM доступен?}
    NSSM_CHECK -->|Да| NSSM_CREATE[nssm install ZapretDirectService]
    NSSM_CHECK -->|Нет| API_CREATE[Windows API CreateServiceW]
    
    NSSM_CREATE --> NSSM_CONFIG[nssm set AppParameters]
    API_CREATE --> API_CONFIG[установка параметров службы]
    
    NSSM_CONFIG --> START_SVC[nssm start]
    API_CONFIG --> START_API[StartService]
    
    SCHTASKS --> REG_SAVE[сохранение в реестр<br/>AutostartEnabled=1]
    SCHTASKS_TASK --> REG_SAVE
    XML_TASK --> REG_SAVE
    START_SVC --> REG_SAVE
    START_API --> REG_SAVE
    
    REG_SAVE --> Done[Автозапуск настроен]
    
    subgraph "Очистка"
        REMOVE[удаление автозапуска]
        REMOVE --> DEL_TASK[schtasks /Delete]
        REMOVE --> DEL_SVC[nssm remove / sc delete]
        REMOVE --> REG_CLEAR[AutostartEnabled=0]
    end
```


## 10. Схема DNS настройки (Win32 API)

```mermaid
flowchart TB
    subgraph "UI"
        DNS_DIALOG["dns_dialog.py<br/>DNSSettingsDialog"]
        FORCE_PAGE["dns_force.py<br/>DNSForceManager UI"]
    end
    
    subgraph "DNS Manager Win32 API"
        DNS_CORE["dns_core.py<br/>DNSManager"]
        GET_ADAPTERS["get_network_adapters_fast"]
        GET_DNS["get_current_dns"]
        SET_DNS["set_custom_dns"]
        SET_AUTO["set_auto_dns"]
        FLUSH["flush_dns_cache_native"]
    end
    
    subgraph "Windows API"
        WMI["WMI Win32_NetworkAdapter"]
        REGISTRY["Реестр<br/>Tcpip\Parameters\Interfaces"]
        IPHLP["IP Helper API<br/>GetAdaptersInfo"]
        DNSAPI["DNS API<br/>DnsFlushResolverCache"]
    end
    
    subgraph "Система"
        ADAPTERS["Сетевые адаптеры"]
        DNS_CACHE["DNS кэш"]
        TCPIP["TCP/IP стек"]
    end
    
    DNS_DIALOG --> DNS_CORE
    FORCE_PAGE --> DNS_CORE
    
    DNS_CORE --> GET_ADAPTERS
    DNS_CORE --> GET_DNS
    DNS_CORE --> SET_DNS
    DNS_CORE --> SET_AUTO
    DNS_CORE --> FLUSH
    
    GET_ADAPTERS --> WMI
    GET_ADAPTERS --> IPHLP
    
    GET_DNS --> REGISTRY
    SET_DNS --> REGISTRY
    SET_AUTO --> REGISTRY
    
    FLUSH --> DNSAPI
    
    WMI --> ADAPTERS
    IPHLP --> ADAPTERS
    REGISTRY --> TCPIP
    DNSAPI --> DNS_CACHE
    
    subgraph "Исключаемые адаптеры"
        EXCLUDE["VMware, VirtualBox, Hyper-V<br/>OpenVPN, WireGuard, TAP<br/>Loopback, Bluetooth, Docker"]
    end
    
    GET_ADAPTERS -.-> EXCLUDE
```


## 11. Схема работы с файлом hosts

```mermaid
flowchart TB
    subgraph "UI"
        HOSTS_PAGE["hosts_page.py"]
        SELECTOR["menu.py<br/>HostsSelectorDialog"]
        PROXY_DOMAINS["proxy_domains.py<br/>SERVICES"]
    end
    
    subgraph "HostsManager"
        HOSTS_MGR["hosts.py<br/>HostsManager"]
        READ["read_hosts_file"]
        WRITE["write_hosts_file"]
        PERMISSIONS["restore_hosts_permissions"]
        GITHUB_API["check_and_remove_github_api"]
    end
    
    subgraph "Windows"
        HOSTS_FILE["C:\Windows\System32\drivers\etc\hosts"]
        ACL["ACL / права доступа"]
        ATTRIB["атрибуты файла"]
    end
    
    HOSTS_PAGE --> HOSTS_MGR
    SELECTOR --> HOSTS_MGR
    PROXY_DOMAINS --> HOSTS_MGR
    
    HOSTS_MGR --> READ
    HOSTS_MGR --> WRITE
    HOSTS_MGR --> PERMISSIONS
    HOSTS_MGR --> GITHUB_API
    
    READ --> HOSTS_FILE
    WRITE --> HOSTS_FILE
    
    PERMISSIONS --> ACL
    PERMISSIONS --> ATTRIB
    
    subgraph "Методы восстановления прав"
        ATTRIB_CMD["attrib -R -S -H"]
        TAKEOWN["takeown /F /A"]
        ICACLS["icacls /reset /grant"]
        SID_GRANT["icacls /grant *S-1-5-32-544:F"]
        PS_ACL["PowerShell Set-Acl"]
        TEMP_COPY["копирование через временный файл"]
    end
    
    PERMISSIONS --> ATTRIB_CMD
    PERMISSIONS --> TAKEOWN
    PERMISSIONS --> ICACLS
    PERMISSIONS --> SID_GRANT
    PERMISSIONS --> PS_ACL
    PERMISSIONS --> TEMP_COPY
```


## 12. Схема Premium подписки

```mermaid
sequenceDiagram
    participant App as Приложение
    participant Checker as SimpleDonateChecker
    participant Cache as Кэш (60 сек)
    participant Reg as Реестр
    participant API as API сервер<br/>84.54.30.233:6666
    
    App->>Checker: get_full_subscription_info()
    
    alt кэш действителен
        Checker->>Cache: чтение кэша
        Cache-->>Checker: (is_premium, days, status)
    else кэш устарел
        Checker->>Reg: get_key()
        Reg-->>Checker: saved_key или None
        
        Checker->>API: POST /check_device
        Note over API: {"device_id": "md5hash"}
        
        alt сервер доступен
            API-->>Checker: {"activated": true, "days_remaining": 7}
            Checker->>Reg: save_last_check()
            Checker->>Cache: обновить кэш
        else сервер недоступен
            alt saved_key существует
                Checker-->>App: is_premium=True (offline)
            else saved_key отсутствует
                Checker-->>App: is_premium=False
            end
        end
    end
    
    Checker-->>App: (is_premium, status_msg, days_remaining)
    
    App->>App: update_title_with_subscription_status()
    App->>App: update_subscription_button_text()
    
    opt Премиум тема
        App->>ThemeManager: apply_theme_async(theme_name)
        alt is_premium = True
            ThemeManager->>ThemeManager: _apply_css_only(theme_name)
            ThemeManager-->>App: тема применена
        else is_premium = False
            ThemeManager-->>App: "Премиум темы недоступны"
            App->>App: show_subscription_dialog()
        end
    end
    
    opt Ручная активация
        App->>Checker: activate_key(key)
        Checker->>API: POST /activate_key
        API-->>Checker: {"success": true}
        Checker->>Reg: save_key(key)
        Checker->>Reg: save_last_check()
        Checker-->>App: активация успешна
    end
```


## 13. Схема Telegram интеграции

```mermaid
graph TB
    subgraph "Приложение"
        LOGS[logs/zapret_log_*.txt]
        CRASH[logs/crashes/*.log]
        ORCH_LOGS[logs/orchestra_*.log]
    end
    
    subgraph "Демоны"
        FULL_DAEMON[FullLogDaemon<br/>периодическая отправка]
        DELTA_DAEMON[LogDeltaDaemon<br/>отправка изменений]
    end
    
    subgraph "Отправка ручная"
        MENU["Меню &quot;Отправить лог&quot;"]
        REPORT_DIALOG[LogReportDialog<br/>описание проблемы]
    end
    
    subgraph "Worker'ы"
        TG_SENDER[tg_sender.py]
        BOT_SENDER[GitHub Discussions<br/>ручное обращение без отдельного бота]
    end
    
    subgraph "Telegram API"
        TG_API[api.telegram.org/bot_TOKEN_]
    end
    
    subgraph "Каналы"
        STABLE_TOPIC[топик 1<br/>stable сборки]
        TEST_TOPIC[топик 10854<br/>test сборки]
        ERROR_TOPIC[топик 12681<br/>ошибки]
    end
    
    LOGS --> FULL_DAEMON
    LOGS --> DELTA_DAEMON
    
    FULL_DAEMON --> TG_SENDER
    DELTA_DAEMON --> TG_SENDER
    
    MENU --> REPORT_DIALOG
    REPORT_DIALOG --> BOT_SENDER
    
    TG_SENDER --> TG_API
    BOT_SENDER --> TG_API
    
    TG_API --> CHAT
    
    CHAT --> STABLE_TOPIC
    CHAT --> TEST_TOPIC
    CHAT --> ERROR_TOPIC
    
    subgraph "Обработка flood-wait"
        FLOOD["429 Too Many Requests"]
        FLOOD --> COOLDOWN[cooldown 30 мин]
        COOLDOWN --> TG_SENDER
    end
```


## 14. Граф наследования UI компонентов

```mermaid
classDiagram
    direction TB
    
    class QWidget {
        <<Qt>>
    }
    
    class FramelessWindowMixin {
        +init_frameless()
        +_start_resize()
        +_perform_resize()
    }
    
    class ThemeSubscriptionManager {
        +update_title_with_subscription_status()
        +update_subscription_button_text()
        +change_theme()
    }
    
    class MainWindowUI {
        +build_ui()
        +_create_pages()
        +_on_section_changed()
        +update_process_status()
        +update_current_strategy_display()
    }
    
    class LupiDPIApp {
        +closeEvent()
        +restore_window_geometry()
        +set_status()
        +update_ui()
    }
    
    class BasePage {
        +set_status()
        +show_loading()
        +show_success()
        +show_error()
    }
    
    class ControlPage {
        +update_dpi_status()
        +update_subscription_status()
        +set_status()
        +start_btn_clicked()
    }
    
    class ControlPage {
        +update_status()
        +update_strategy()
        +start_btn_clicked()
    }
    
    class StrategiesPage {
        +populate_strategies()
        +update_current_strategy()
        +strategy_selected signal
    }
    
    class SideNavBar {
        +set_section()
        +set_page()
        +_on_button_clicked()
        +section_changed signal
    }
    
    QWidget <|-- LupiDPIApp
    QWidget <|-- BasePage
    QWidget <|-- SideNavBar
    
    FramelessWindowMixin <|-- LupiDPIApp
    ThemeSubscriptionManager <|-- LupiDPIApp
    MainWindowUI <|-- LupiDPIApp
    
    BasePage <|-- ControlPage
    BasePage <|-- StrategiesPage
    BasePage <|-- AppearancePage
    BasePage <|-- NetworkPage
    BasePage <|-- DpiSettingsPage
    BasePage <|-- OrchestraPage
    BasePage <|-- PremiumPage
    BasePage <|-- LogsPage
    BasePage <|-- AboutPage
    
    LupiDPIApp --> SideNavBar : содержит
    LupiDPIApp --> ControlPage : содержит
    LupiDPIApp --> StrategiesPage : содержит
```


## 15. Схема сборки и распространения

```mermaid
flowchart TB
    subgraph "Исходный код"
        MAIN[main.py]
        MODULES[все модули Python]
        ASSETS[иконки, темы, Lua]
        ISS[zapret.iss<br/>Inno Setup]
        SPEC[zapret.spec<br/>PyInstaller]
    end
    
    subgraph "Сборка (build_tools/)"
        BUILD_RELEASE[build_release.py<br/>интерактивная сборка]
        WRITE_INFO[write_build_info.py<br/>генерация build_info.py]
        PYINSTALLER[PyInstaller<br/>--onefile --windowed]
    end
    
    subgraph "Параметры сборки"
        CHANNEL{Канал}
        CHANNEL -->|stable| STABLE_EXE[zapret.exe]
        CHANNEL -->|test| TEST_EXE[zapret.exe]
    end
    
    subgraph "Упаковка"
        INNO_SETUP[Inno Setup<br/>ISCC.exe]
        ISS_STABLE[zapret_stable.iss]
        ISS_TEST[zapret_test.iss]
    end
    
    subgraph "Артефакты"
        STABLE_INST[ZapretSetup.exe<br/>stable]
        TEST_INST[ZapretSetup_TEST.exe<br/>test]
    end
    
    subgraph "Публикация"
        GITHUB_RELEASE[GitHub Releases]
        SERVER[Сервер<br/>zapretdpi.ru]
        VERSION_JSON[version.json]
    end
    
    subgraph "Распространение"
        USER[Пользователь]
        AUTO_UPDATE[Автообновление]
        TELEGRAM[Telegram каналы]
    end
    
    MAIN --> BUILD_RELEASE
    MODULES --> BUILD_RELEASE
    ASSETS --> BUILD_RELEASE
    
    BUILD_RELEASE --> WRITE_INFO
    WRITE_INFO --> PYINSTALLER
    
    PYINSTALLER --> STABLE_EXE
    PYINSTALLER --> TEST_EXE
    
    STABLE_EXE --> INNO_SETUP
    TEST_EXE --> INNO_SETUP
    
    INNO_SETUP --> ISS_STABLE
    INNO_SETUP --> ISS_TEST
    
    ISS_STABLE --> STABLE_INST
    ISS_TEST --> TEST_INST
    
    STABLE_INST --> GITHUB_RELEASE
    TEST_INST --> GITHUB_RELEASE
    
    GITHUB_RELEASE --> SERVER
    SERVER --> VERSION_JSON
    
    USER --> AUTO_UPDATE
    USER --> GITHUB_RELEASE
    USER --> TELEGRAM
    
    AUTO_UPDATE --> SERVER
    SERVER --> VERSION_JSON
    VERSION_JSON --> AUTO_UPDATE
```
