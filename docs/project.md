# PROJECT.md — Техническая документация Zapret2 GUI

**Версия:** 2.0  
**Актуальность:** март 2026


## Содержание

1. [Введение](#1-введение)
2. [Архитектура приложения](#2-архитектура-приложения)
3. [Структура проекта](#3-структура-проекта)
4. [Модули и компоненты](#4-модули-и-компоненты)
5. [Потоки выполнения](#5-потоки-выполнения)
6. [Системные требования](#6-системные-требования)
7. [Сборка и установка](#7-сборка-и-установка)
8. [Конфигурация](#8-конфигурация)
9. [API и интеграции](#9-api-и-интеграции)
10. [Ссылки](#10-ссылки)


## 1. Введение

### 1.1 О проекте

Zapret2 GUI — графическая оболочка для утилиты обхода Deep Packet Inspection (DPI). Проект обеспечивает интерфейс для настройки и управления стратегиями обхода блокировок на операционной системе Windows.

### 1.2 Основные возможности

| Возможность | Описание |
|-------------|----------|
| Три режима работы | BAT (Zapret 1), Direct (Zapret 2), Оркестратор (автообучение) |
| Управление стратегиями | Визуальный выбор, комбинирование, импорт/экспорт |
| Оркестратор | Автоматический подбор стратегий в реальном времени |
| DNS настройки | Принудительная установка DNS, проверка подмены |
| Hosts менеджер | Разблокировка GEO-ограниченных сервисов |
| Автозапуск | Планировщик задач, службы Windows, NSSM |
| Premium подписка | Эксклюзивные темы |
| Telegram логи | Автоматическая отправка логов для диагностики |


## 2. Архитектура приложения

### 2.1 Общая архитектура

Схема архитектуры представлена в [DIAGRAMS.md#1-общая-архитектура](DIAGRAMS.md#1-общая-архитектура).

**Слои архитектуры:**

| Слой | Компоненты | Назначение |
|------|------------|------------|
| UI Layer | main.py, ui/, pages/, sidebar.py, theme.py | Интерфейс пользователя |
| Core Layer | dpi/, strategy_menu/, orchestra/, dns/, hosts/ | Бизнес-логика |
| Infrastructure | config/, log/, autostart/, updater/, tgram/, donater/ | Конфигурация, логирование, интеграции |
| System Layer | Windows API, Реестр, NSSM, WinDivert | Системные вызовы |


## 3. Структура проекта

### 3.1 Дерево каталогов

```
zapret/
├── main.py                          # Точка входа
├── config/                          # Конфигурация и реестр
├── dpi/                             # Управление DPI
├── strategy_menu/                   # Управление стратегиями
├── orchestra/                       # Оркестратор
├── dns/                             # DNS настройки
├── hosts/                           # Управление файлом hosts
├── ui/                              # Интерфейс пользователя
├── autostart/                       # Автозапуск
├── donater/                         # Premium подписка
├── tgram/                           # Telegram интеграция
├── log/                             # Логирование и краш-хендлер
├── startup/                         # Стартовые проверки
├── managers/                        # Менеджеры приложения
├── utils/                           # Вспомогательные функции
├── altmenu/                         # Верхнее меню
├── updater/                         # Обновления
├── discord/                         # Управление Discord
├── build_tools/                     # Инструменты сборки
└── docs/                            # Документация
```

### 3.2 Основные файлы и их назначение

| Файл | Назначение |
|------|------------|
| main.py | Точка входа, инициализация приложения |
| config/config.py | Пути, константы, размеры окна |
| config/reg.py | Универсальный helper для реестра |
| dpi/dpi_controller.py | Асинхронный контроллер DPI |
| dpi/bat_start.py | Запуск DPI через BAT/Zapret 1 |
| strategy_menu/strategies_registry.py | Центральный реестр стратегий |
| strategy_menu/strategy_runner.py | Запуск winws2.exe |
| orchestra/orchestra_runner.py | Оркестратор автообучения |
| ui/theme.py | Управление темами |
| ui/sidebar.py | Боковая навигация |


## 4. Модули и компоненты

### 4.1 Модуль DPI (dpi/)

Схема классов ядра представлена в [DIAGRAMS.md#3-диаграмма-классов-ядро](DIAGRAMS.md#3-диаграмма-классов-ядро).

| Класс/Файл | Назначение | Ключевые методы |
|------------|------------|-----------------|
| DPIController | Асинхронное управление DPI | start_dpi_async, stop_dpi_async |
| DPIStartWorker | Воркер запуска в потоке | run, _start_direct, _start_bat, _start_orchestra |
| BatDPIStart | Запуск через BAT | start_dpi, check_process_running_fast |
| process_health_check | Диагностика падений | check_process_health, diagnose_startup_error |
| stop | Остановка DPI | stop_dpi, stop_dpi_direct, stop_dpi_universal |

**Поток запуска DPI** показан в [DIAGRAMS.md#4-диаграмма-последовательности-запуск-dpi](DIAGRAMS.md#4-диаграмма-последовательности-запуск-dpi).

### 4.2 Модуль стратегий (strategy_menu/)

Схема структуры стратегий представлена в [DIAGRAMS.md#8-структура-стратегий](DIAGRAMS.md#8-структура-стратегий).

| Класс/Файл | Назначение | Ключевые методы |
|------------|------------|-----------------|
| StrategiesRegistry | Центральный реестр стратегий | get_category_strategies, get_strategy_args_safe |
| StrategyManager | Управление BAT стратегиями | get_strategies_list, download_single_strategy_bat |
| BatZapret1Manager | Сканирование .bat файлов | get_local_strategies_only, _parse_bat_metadata |
| StrategyRunner | Запуск winws2.exe | start_strategy_custom, stop |
| combine_strategies | Объединение категорий | combine_strategies |
| apply_filters | Применение настроек | apply_all_filters, apply_wssize_parameter |

**Источники стратегий:**
- GitHub / nozapret.ru — index.json (BAT режим)
- папка bat/ — локальные .bat файлы
- json/strategies/builtin/ — встроенные JSON стратегии
- json/strategies/user/ — пользовательские JSON

### 4.3 Модуль оркестратора (orchestra/)

Схема последовательности оркестратора представлена в [DIAGRAMS.md#5-диаграмма-последовательности-оркестратор](DIAGRAMS.md#5-диаграмма-последовательности-оркестратор).

| Класс/Файл | Назначение | Ключевые методы |
|------------|------------|-----------------|
| OrchestraRunner | Запуск и управление | start, stop, prepare, _read_output |
| LogParser | Парсинг логов winws2 | parse_line, nld_cut, ip_to_subnet16 |
| LockedStrategiesManager | Залоченные стратегии | lock, unlock, save, load |
| BlockedStrategiesManager | Черный список | block, unblock, is_blocked |

**Алгоритм оркестратора:**
1. Начинает с strategy=1 для каждого нового домена
2. Отслеживает успехи (получено >2KB данных, протокол определён)
3. Отслеживает неудачи (RST, таймаут, retransmission)
4. При 3 успехах подряд -> LOCK (стратегия закрепляется)
5. При 2 неудачах подряд -> UNLOCK (переход к следующей стратегии)
6. Группировка субдоменов (rr1---sn-xxx.googlevideo.com -> googlevideo.com)

### 4.4 Модуль DNS (dns/)

Схема DNS настройки представлена в [DIAGRAMS.md#10-схема-dns-настройки-win32-api](DIAGRAMS.md#10-схема-dns-настройки-win32-api).

| Класс/Файл | Назначение | Ключевые методы |
|------------|------------|-----------------|
| DNSManager | Управление DNS | get_network_adapters_fast, set_custom_dns, flush_dns_cache |
| DNSForceManager | Принудительная установка DNS | force_dns_on_all_adapters, enable_force_dns, disable_force_dns |
| DNSUIManager | UI для DNS операций | apply_dns_settings_async, cleanup |
| DNSStartupManager | DNS при запуске | apply_dns_on_startup_async |

**Технологии:**
- WMI — получение списка адаптеров
- Реестр Windows — чтение/запись DNS
- IP Helper API — GetAdaptersInfo
- DNS API — DnsFlushResolverCache

### 4.5 Модуль hosts (hosts/)

Схема работы с hosts файлом представлена в [DIAGRAMS.md#11-схема-работы-с-файлом-hosts](DIAGRAMS.md#11-схема-работы-с-файлом-hosts).

| Класс/Файл | Назначение | Ключевые методы |
|------------|------------|-----------------|
| HostsManager | Управление hosts файлом | add_proxy_domains, remove_proxy_domains, apply_selected_domains |
| HostsSelectorDialog | Выбор сервисов | get_selected_domains, select_all, deselect_all |
| restore_hosts_permissions | Восстановление прав | 8 методов (attrib, takeown, icacls, SID, PowerShell, temp copy) |

### 4.6 Модуль интерфейса (ui/)

Схема наследования UI компонентов представлена в [DIAGRAMS.md#14-граф-наследования-ui-компонентов](DIAGRAMS.md#14-граф-наследования-ui-компонентов).

| Класс/Файл | Назначение |
|------------|------------|
| LupiDPIApp | Главное окно, наследует MainWindowUI, ThemeSubscriptionManager, FramelessWindowMixin |
| MainWindowUI | Построение UI (миксин) |
| SideNavBar | Боковая панель навигации |
| CustomTitleBar | Кастомный заголовок окна |
| FramelessWindowMixin | Безрамочное окно с изменением размера |
| ThemeManager | Управление темами, асинхронная генерация CSS |
| ThemeHandler | Обработчик тем для страниц |

**Страницы интерфейса (ui/pages/):**

| Страница | Файл | Назначение |
|----------|------|------------|
| Управление | control_page.py | Альтернативное управление |
| Стратегии | strategies_page.py | Выбор стратегий |
| Хостлисты | hostlist_page.py | Управление доменами |
| IPsets | ipset_page.py | Управление IP |
| Блобы | blobs_page.py | Бинарные данные Zapret 2 |
| Настройки DPI | dpi_settings_page.py | Параметры запуска |
| Автозапуск | autostart_page.py | Настройка автозапуска |
| Сеть | network_page.py | DNS настройки |
| Диагностика | connection_page.py | Проверка доступности |
| Hosts | hosts_page.py | GEO-разблокировка |
| Оформление | appearance_page.py | Темы |
| Premium | premium_page.py | Подписка |
| Логи | logs_page.py | Просмотр логов |
| Оркестратор | orchestra/orchestra_page.py | Логи оркестратора |
| Залоченные | orchestra_locked_page.py | Зафиксированные стратегии |
| Заблокированные | orchestra_blocked_page.py | Черный список |
| Белый список | orchestra_whitelist_page.py | Исключения оркестратора |
| Рейтинги | orchestra_ratings_page.py | История стратегий |

### 4.7 Модуль автозапуска (autostart/)

Схема автозапуска представлена в [DIAGRAMS.md#9-схема-автозапуска](DIAGRAMS.md#9-схема-автозапуска).

| Класс/Файл | Назначение | Ключевые методы |
|------------|------------|-----------------|
| service_api | Windows API для служб | create_service, delete_service, start_service |
| nssm_service | NSSM обёртка | create_service_with_nssm, remove_service_with_nssm |
| setup_service_for_strategy | Служба для BAT | setup_service_for_strategy |
| setup_direct_service | Служба для Direct | setup_direct_service |
| setup_direct_autostart_task | Задача ONLOGON | setup_direct_autostart_task |
| setup_autostart_for_exe | Автозапуск GUI | setup_autostart_for_exe |

### 4.8 Модуль Premium (donater/)

Схема Premium подписки представлена в [DIAGRAMS.md#12-схема-premium-подписки](DIAGRAMS.md#12-схема-premium-подписки).

| Класс/Файл | Назначение | Ключевые методы |
|------------|------------|-----------------|
| SimpleDonateChecker | Проверка подписки | get_full_subscription_info, activate, check_device_activation |
| RegistryManager | Хранение в реестре | get_key, save_key, get_device_id |
| SubscriptionDialog | UI подписки | _activate_key, _check_status |
| APIClient | HTTP клиент | _request, activate_key, check_device_status |

**API эндпоинты:**
- GET /status — проверка соединения
- POST /activate_key — активация ключа
- POST /check_device — проверка статуса устройства

### 4.9 Модуль Telegram (tgram/)

Схема Telegram интеграции представлена в [DIAGRAMS.md#13-схема-telegram-интеграции](DIAGRAMS.md#13-схема-telegram-интеграции).

| Класс/Файл | Назначение | Ключевые методы |
|------------|------------|-----------------|
| FullLogDaemon | Периодическая отправка | _tick, _snapshot |
| LogDeltaDaemon | Отправка изменений | send_delta |
| TgSendWorker | Воркер отправки | run |
| send_file_to_tg | Отправка файла | send_file_to_tg |
| send_log_to_tg | Отправка текста | send_log_to_tg |


## 5. Потоки выполнения

Схема потоков инициализации представлена в [DIAGRAMS.md#7-диаграмма-потоков-инициализация-приложения](DIAGRAMS.md#7-диаграмма-потоков-инициализация-приложения).

### 5.1 Потоки при запуске

| Поток | Назначение |
|-------|------------|
| Main Thread | GUI, обработка событий Qt |
| Preload Thread | Предзагрузка модулей |
| HeavyInit Thread | Тяжелая инициализация |
| Subscription Thread | Проверка подписки |
| IPC Server Thread | Межпроцессное взаимодействие |
| Process Monitor Thread | Мониторинг winws.exe |
| Log Tail Thread | Хвост логов |
| Theme Build Thread | Генерация CSS |
| Orchestra Reader Thread | Чтение stdout оркестратора |

### 5.2 Таймеры

| Таймер | Интервал | Назначение |
|--------|----------|------------|
| Process Monitor | 5000 ms | Проверка статуса winws.exe |
| Full Log Daemon | 1800 s | Отправка полного лога |
| Splash Animation | 16 ms | Анимация загрузки |
| Garland Animation | 50 ms | Анимация гирлянды |
| Snowflakes Animation | 33 ms | Анимация снежинок |


## 6. Системные требования

### 6.1 Минимальные

| Компонент | Требование |
|-----------|------------|
| ОС | Windows 10 (build 17134+) или Windows 11 |
| Архитектура | x86_64 (64-бит) |
| RAM | 256 MB |
| Диск | 200 MB свободного места |
| Права | Администратор |

### 6.2 Зависимости Python

```
PyQt6>=6.4.0
packaging>=21.3
requests>=2.28.0
python-telegram-bot>=20.0
psutil>=5.9.0
qt_material>=2.14
qtawesome>=1.2.0
pyperclip>=1.8.0
pywin32>=305
wmi>=1.5.1
```

### 6.3 Внешние зависимости

| Компонент | Назначение |
|-----------|------------|
| NSSM | Создание служб Windows |
| WinDivert | Перехват сетевого трафика |
| Inno Setup | Сборка инсталлятора |
| PyInstaller | Сборка exe |


## 7. Сборка и установка

### 7.1 Подготовка окружения

```bash
git clone https://github.com/youtubediscord/zapret.git
cd zapret
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 7.2 Сборка exe (PyInstaller)

```bash
python zapretbuild.py --channel stable
python zapretbuild.py --channel test
python zapretbuild.py --debug
```

### 7.3 Сборка инсталлятора (Inno Setup)

```bash
ISCC.exe zapret_stable.iss
ISCC.exe zapret_test.iss
```

### 7.4 Автоматическая сборка (build_release.py)

```python
# build_tools/build_release.py
# 1. Выбор канала (stable/test)
# 2. Определение версии
# 3. Release notes
# 4. Генерация build_info.py
# 5. Остановка запущенного Zapret
# 6. PyInstaller сборка
# 7. Inno Setup сборка
# 8. Загрузка на сервер
# 9. Обновление version.json
```


## 8. Конфигурация

### 8.1 Реестр Windows

Базовый путь: `HKCU\Software\Zapret2Reg` (stable) или `HKCU\Software\Zapret2DevReg` (test)

| Ключ | Тип | Назначение |
|------|-----|------------|
| LastBatStrategy | REG_SZ | Последняя выбранная BAT стратегия |
| DPIAutoStart | REG_DWORD | Автозапуск DPI (1/0) |
| SelectedTheme | REG_SZ | Выбранная тема |
| RemoveGitHubAPI | REG_DWORD | Удаление api.github.com из hosts |
| ForceDNS | REG_DWORD | Принудительный DNS (1/0) |
| AutoUpdateEnabled | REG_DWORD | Автопроверка обновлений |

### 8.2 Файлы конфигурации

| Файл | Путь | Назначение |
|------|------|------------|
| config.py | config/ | Пути, константы |
| build_info.py | config/ | Версия, канал (автоген.) |
| urls.py | config/ | URL для обновлений |
| tokens.py | config/ | Токены |
| index.json | bat/ | Метаданные стратегий (BAT) |
| categories.json | json/strategies/builtin/ | Категории стратегий |
| tcp.json | json/strategies/builtin/ | TCP стратегии |
| udp.json | json/strategies/builtin/ | UDP стратегии |

### 8.3 Переменные окружения

| Переменная | Значение по умолчанию | Назначение |
|------------|----------------------|------------|
| QT_AUTO_SCREEN_SCALE_FACTOR | 1 | Масштабирование Qt |
| TMPDIR | %TEMP% | Временная директория |


## 9. API и интеграции

### 9.1 GitHub API (обновления, стратегии)

```python
# updater/github_release.py
def get_latest_release(repo: str) -> dict:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()
```

### 9.2 Telegram Bot API

```python
# tgram/tg_sender.py
API = f"https://api.telegram.org/bot{TOKEN}"

def send_file_to_tg(file_path: str, caption: str = "") -> bool:
    with open(file_path, "rb") as fh:
        files = {"document": fh}
        data = {"chat_id": CHAT_ID, "caption": caption}
        response = requests.post(f"{API}/sendDocument", files=files, data=data, timeout=30)
    return response.status_code == 200
```

### 9.3 Premium API

```python
# donater/donate.py
API_BASE_URL = "http://84.54.30.233:6666/api"

def activate_key(key: str, device_id: str) -> dict:
    url = f"{API_BASE_URL}/activate_key"
    payload = {"key": key, "device_id": device_id}
    response = requests.post(url, json=payload, timeout=10)
    return response.json()

def check_device_status(device_id: str) -> dict:
    url = f"{API_BASE_URL}/check_device"
    payload = {"device_id": device_id}
    response = requests.post(url, json=payload, timeout=10)
    return response.json()
```
