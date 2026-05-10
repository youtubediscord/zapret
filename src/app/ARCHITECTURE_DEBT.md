# Архитектурный долг

Дата фиксации: 2026-05-10

Это список оставшихся прямых связей. Он нужен, чтобы не забыть, где проект ещё не дошёл
до чистой схемы `UI -> feature.public -> feature internals`.

## Контрольные поиски

Эти команды нужны, чтобы запрещённые связи были видимыми, а не держались в памяти:

```bash
rg -n "from winws_runtime\.(runtime|flow|runners)\.|import winws_runtime\.(runtime|flow|runners)\.|launch_controller|restart_dpi_async|switch_presets_async|stop_and_exit_async" src/ui src/main src/presets src/profile src/blockcheck src/donater -g'*.py'
rg -n "from donater\.(service|subscription_manager|worker|device_store|api|.*_service)\.|import donater\.(service|subscription_manager|worker|device_store|api|.*_service)\.|PremiumService|SubscriptionManager|donate_checker" src/ui src/main src/presets src/profile src/blockcheck src/donater -g'*.py'
rg -n "window\.launch_controller|host\.launch_controller|getattr\([^\\n]*(window|host)[^\\n]*launch_controller" src/ui src/main -g'*.py'
rg -n "window\._|host\._|getattr\((window|host|self\.host|app)[^\\n]*, \"_" src/ui src/main src/presets src/profile src/blockcheck src/donater -g'*.py'
```

Как читать результат:

- совпадение внутри `feature/public.py` обычно нормально, потому что это и есть публичная дверь;
- совпадение внутри самой feature-папки не всегда ошибка, если файл является внутренней частью этой feature;
- совпадение из чужого слоя во внутренний файл feature нужно либо закрыть через `public.py`, либо занести в этот файл как явный долг.

## Runtime

Уже сделано:

- UI/main не трогают `launch_controller` напрямую;
- команды запуска вынесены в `src/winws_runtime/runtime/commands.py`;
- внешний вход создан в `src/winws_runtime/public.py`;
- UI/main для обычных DPI-действий импортируют runtime через `winws_runtime.public`.
- `PresetRuntimeCoordinator` больше не читает `ui_state_store` и `app_context` через `parent()`; эти зависимости передаются явно.
- watcher активного preset-а создаётся через `winws_runtime.public`, а не напрямую из UI bootstrap через внутренний coordinator.
- control page запускает и останавливает DPI через `winws_runtime.public`, без старого `ui/window_action_controller.py`.
- `src/ui/page_signals/mode.py` вызывает смену метода запуска через `winws_runtime.public`, а не напрямую через `runtime.method_switch_flow`.
- `src/main/startup_coordinator.py` запускает runtime startup/autostart через `winws_runtime.public`.
- `src/main/window_lifecycle.py` и `src/blockcheck/strategy_scanner.py` вызывают синхронную остановку через `winws_runtime.public`, а не напрямую через `runtime.sync_shutdown`.
- уведомления runtime о конфликтующих процессах и ошибках runner-а собираются в `src/winws_runtime/runtime/notifications.py`.

Осталось проверить отдельными проходами:

- `src/blockcheck/strategy_scanner.py` импортирует `winws_runtime.runners.constants`;

Это может быть допустимой границей blockcheck/runtime, но её нужно оставить явной и не расширять.

## Premium

Уже сделано:

- `SubscriptionManager` управляет worker-ом и QThread;
- UI-применение Premium-результата вынесено в `src/donater/subscription_ui.py`;
- внешний вход создан в `src/donater/public.py`;
- команды Premium созданы в `src/donater/commands.py`;
- Premium-статус подписки описан явной моделью `PremiumState` в `src/donater/state.py`;
- внешний `get_subscription_info()` на словаре заменён на `get_premium_state()`;
- `subscription_ui.py` принимает `PremiumState`, а не свободный `dict`;
- package-level `donater.__init__` больше не экспортирует `PremiumService` как обход `donater.public`;
- `src/main/window_startup.py` берёт `SubscriptionManager` через `donater.public`.
- Premium-страница запускает создание кода и проверку статуса через `donater.commands`;
- startup worker Premium берёт сервис и статус через `donater.commands`;
- `app.donate_checker` больше не используется как рабочий мост; Premium-сервис остаётся внутри `SubscriptionManager` и `donater.commands`.

Осталось отдельным проходом:

- проверить Premium-страницу и её workflow на прямые запросы к Premium API из UI;
- решить, надо ли выносить `SubscriptionManager.donate_checker` в отдельный Premium-state объект, если понадобится полностью отделить Premium-state от manager-а.

## Presets/Profile

Уже сделано:

- внешний вход создан в `src/presets/public.py`;
- внешний вход создан в `src/profile/public.py`;
- первые команды preset-слоя созданы в `src/presets/commands.py`;
- команды profile-слоя созданы в `src/profile/commands.py`;
- внешние слои берут `PresetFileService`, `PresetFileStore`, `PresetSelectionService`, `PresetUiStore`, `PresetManifest` через `presets.public`;
- `winws_runtime.flow.preset_mode`, `profile` и `blockcheck` больше не импортируют preset-файлы напрямую.
- сохранение source preset-а из `profile` и `blockcheck` идёт через `presets.commands`.
- создание, переименование, импорт, экспорт, дублирование, сброс и удаление preset-а доступны через `presets.commands`.
- raw preset editor и страница "Мои пресеты" используют preset-команды для изменения файлов.
- control page, raw preset editor и общие страницы preset-ов получают выбранный source preset, manifest, имя файла и путь через `presets.commands`.
- profile UI, control page и краткое отображение текущей стратегии читают profile-ы через `profile.public`, а не через прямое создание `ProfilePresetService`.
- выбранный source preset описан явной моделью `PresetSelectionState` в `src/presets/state.py`;
- runtime autostart, method-switch, start-preparation, runtime apply, preset watcher и preset switch worker получают launch snapshot/source path через `presets.public`;
- `profile` и `blockcheck` получают manifest выбранного source preset-а через `presets.public`, а не через прямой вызов `preset_mode_coordinator`.

Осталось отдельными проходами:

- у `profile` и `presets` много мест, где напрямую передаётся `app_context`;
- `src/profile/service.py` и `src/profile/settings.py` используют preset-сервисы через `presets.public`, но всё ещё получают их через общий `app_context`;
- нужно решить, какие profile-действия можно перевести с общего `app_context` на более точные зависимости.

Это не баг само по себе, но это следующий слой для уменьшения зависимости от окна и `app_context`.

## Program Settings

Уже сделано:

- внешний вход создан в `src/program_settings/public.py`;
- команды общих настроек созданы в `src/program_settings/commands.py`;
- подписка на общий снимок настроек живёт в `src/program_settings/runtime.py`;
- control pages больше не читают и не пишут `settings.store`, `WindowsDefenderManager` и `MaxBlockerManager` напрямую;
- control pages только показывают кнопки и вызывают program-settings команды.
- runtime autostart и method-switch читают флаг автозапуска DPI через `program_settings.public.is_auto_dpi_enabled()`, а не напрямую из `settings.store`.

Осталось отдельным проходом:

- проверить, нужно ли переводить автозапуск самого GUI через Windows Task Scheduler в отдельный public-вход, если будем чистить app-autostart отдельно.

## DNS/Hosts

Уже сделано:

- внешний вход DNS создан в `src/dns/public.py`;
- внешний вход hosts создан в `src/hosts/public.py`;
- первые команды DNS созданы в `src/dns/commands.py`;
- первые команды hosts созданы в `src/hosts/commands.py`;
- DNS-состояние описано моделью `DnsState` в `src/dns/state.py`;
- DNS-действия возвращают `DnsCommandResult`, а не разрозненные tuple-значения;
- наружный экспорт `DNSForceManager` удалён из `dns.public`; доступность IPv6 идёт через `dns.public.check_ipv6_connectivity`;
- hosts-состояние описано моделью `HostsState` в `src/hosts/state.py`;
- hosts-действия возвращают `HostsCommandResult`, а не разрозненные tuple-значения;
- внешние слои используют `dns.public` для DNS-проверки, DNS startup, DNS provider-ов и WinAPI-списка адаптеров;
- DNS-страница использует `dns.commands` для загрузки данных, обновления DNS, применения auto/provider/custom DNS, принудительного DNS, сброса на DHCP и очистки DNS-кэша;
- hosts-команды умеют создать `HostsManager`, применить service-profile, очистить hosts, восстановить права и включить/выключить Adobe-блокировку;
- `telegram_proxy` использует `hosts.public` для чтения и записи `hosts`.

Осталось отдельным проходом:

- решить, надо ли выносить catalog/selection-операции hosts в отдельные команды или оставить их частью hosts controller.

## UI State

Уже сделано:

- состояние страниц, навигации и поиска перенесено в `WindowUiSession`;
- старые поля главного окна вида `window._nav_*`, `window._sidebar_search_*`, `window._page_host`, `window.pages` не используются.
- `ui/window_display_state.py` больше не принимает всё окно как рабочую зависимость; функции получают `app_context`, `ui_state_store` или `app_runtime_state`.

Осталось отдельными проходами:

- `main/window_state_sync.py` напрямую пишет в `ui_state_store`;
- страницы `appearance` и `about` держат свой `_ui_state_store`, это локальное состояние страниц, но позже его можно упростить.
- `src/ui/window_signal_bindings.py` пишет в `window._preset_runtime_coordinator`;
- `src/ui/ui_root.py` создаёт `window._preset_runtime_coordinator`;
- `src/main/window_lifecycle_cleanup.py`, `src/ui/window_geometry_controller.py`, `src/ui/window_close_controller.py` и post-startup gate-файлы используют приватные поля окна для lifecycle/drag/resize/startup-состояния;
- эти поля не относятся к `WindowUiSession`, но их стоит отдельно разделить на lifecycle/geometry/startup state, если будем дальше разгружать окно.

## Следующие маленькие шаги

Рекомендуемый порядок:

1. Проверить `runtime_ui_bridge`: направление `runtime -> UI`.
2. Проверить Premium-страницу на прямые API-запросы и при необходимости добавить более явные Premium-команды.
3. Расширить profile/preset/DNS/hosts команды только там, где ещё остаётся реальный обход feature-входа.
4. Только после этого думать про общий `AppRuntime`.
