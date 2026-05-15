# Архитектурный контракт GUI

Дата фиксации: 2026-05-10

Этот документ фиксирует текущие границы проекта. Он нужен не для описания всех деталей,
а чтобы новые правки не возвращали старую схему, где главное окно знает обо всём.

Быстрая проверка границ:

```bash
python src/app/architecture_checks.py
```

## Итоговая карта владения

Целевая схема проекта:

```txt
AppRuntime
  -> собирает ядро приложения: AppPaths, State, Feature-слои

Feature-слои
  -> runtime, presets, profile, premium, dns, hosts, tray, updater и другие входы
  -> не хранят UI-страницы
  -> вызывают только свой public/commands/state/service слой

State
  -> хранит состояние по владельцам
  -> runtime-состояние DPI записывает только LaunchRuntimeService
  -> MainWindowStateStore хранит только состояние оболочки окна и общего UI
  -> feature-слои не используют MainWindowStateStore как общий склад своего состояния
  -> UI читает состояние и показывает его, но не становится источником истины

Commands
  -> выполняют действия feature-слоёв
  -> UI не вызывает service/manager напрямую

UI
  -> показывает данные
  -> получает зависимости от PageFactory
  -> отправляет команды через переданный feature/callback
```

Главное правило: если коду нужна обязательная зависимость, она передаётся явно.
Нельзя искать обязательные зависимости через `getattr` / `hasattr` и тихо
продолжать работу без них. Такие проверки допустимы только для необязательных
Qt-возможностей, визуальных мелочей или динамических полей данных.

## Главное окно

`MainWindow` — это UI-оболочка.

Разрешено:

- держать виджеты окна;
- держать `WindowUiSession`;
- держать центр уведомлений;
- держать геометрию окна;
- держать lifecycle окна: закрытие, сворачивание, cleanup.

Запрещено:

- делать окно источником истины для runtime;
- складывать в окно временные поля навигации вида `window._nav_*`;
- складывать в окно состояние поиска вида `window._sidebar_search_*`;
- обращаться из UI к `launch_runtime` напрямую;
- превращать окно в общий контейнер для всех feature-сервисов.

## WindowUiSession

`WindowUiSession` — это временное состояние UI главного окна.

Там живут:

- `page_factory`;
- `page_host`;
- созданные страницы;
- иконки и подписи навигации;
- состояние поиска в боковом меню;
- текущий язык UI для навигации;
- startup-метрики создания страниц.

Правило:

```txt
window.ui_session -> состояние страниц, навигации и поиска
window.app_runtime.paths -> пути приложения
window.app_runtime.state -> короткий доступ к UI/runtime-state
window.app_runtime.features -> публичные входы feature-слоёв
```

Нельзя держать рядом два пути:

```txt
window._nav_icons
window.ui_session.nav_icons
```

Если поле переехало в `WindowUiSession`, старое поле на окне не возвращать.

## AppRuntime

`AppRuntime` — это точка сборки путей, состояния оболочки и feature-входов приложения.
Он не является заменой старого `AppContext` и не должен давать общий выход
во все внутренности программы.

Там живут:

- `paths` — единый `AppPaths`, то есть источник путей программы;
- `state` — короткий доступ к `ui_state_store` и `app_runtime_state`;
- `features` — публичные входы подсистем: runtime, Premium, presets, profile, DNS, hosts и другие.

`AppContext` удалён из рабочего потока. Его нельзя возвращать как общий
контейнер. То, что раньше лежало в нём, должно жить там, где этому место:

```txt
пути                  -> AppRuntime.paths / AppPaths
UI/runtime state       -> AppRuntime.state
preset/profile сервисы -> PresetsFeature / ProfileFeature
DPI runtime            -> RuntimeFeature + LaunchRuntimeService
orchestra whitelist    -> OrchestraFeature
настройки программы    -> ProgramSettingsFeature
```

Store состояния оболочки окна и общего UI живёт в:

```txt
src/app/state_store.py
```

Там находятся:

```txt
AppUiState
MainWindowStateStore
AppRuntimeState
```

`MainWindowStateStore` не является каноническим хранилищем всего приложения.
Runtime, Premium, Presets/Profile, DNS и Hosts не должны хранить в нём своё
основное состояние как в общем складе.

Его зона ответственности:

```txt
оболочка окна
общие UI-флаги
тексты/сводки, которые уже подготовили feature-слои
визуальные настройки общего интерфейса
```

Основное состояние feature-слоёв должно жить у владельца:

```txt
runtime-состояние DPI   -> LaunchRuntimeService
Premium-состояние       -> PremiumFeature / donater.state
preset/profile state    -> PresetsFeature / ProfileFeature
DNS state               -> DnsFeature / dns.state
Hosts state             -> HostsFeature / hosts.state
```

Правило:

```txt
страница не берёт сервисы из MainWindow
страница получает нужный feature от PageFactory
```

Нельзя возвращать старую схему:

```txt
page.window().app_runtime.context
page.window().ui_state_store
page.window().launch_controller
page.window().orchestra_runner
```

Если странице нужен только родитель для `InfoBar`, `MessageBox` или диалога,
можно использовать `self.window()` как Qt-родителя. Это не источник состояния,
а только место, к которому прикрепляется всплывающее окно.

## PageFactory и страницы

`PageFactory` создаёт страницы, а `ui.page_composition` передаёт им явные
зависимости.

Правильная схема:

```txt
PageFactory
  -> спрашивает ui.page_composition
  -> передаёт конкретный feature / store / callback
Page
  -> рисует UI
  -> вызывает маленький page-runtime/workflow/controller, если действию нужна логика
Page-runtime/workflow/controller
  -> вызывает переданные зависимости страницы
Feature
  -> вызывает public/commands/state/service
```

Слово `controller` здесь означает небольшой контроллер конкретной страницы или
сценария. Нельзя возвращать старые большие контроллеры, которые одновременно
хранят состояние, создают worker-ы, читают файлы и управляют UI.

Пример правильного направления:

```txt
NetworkPage(deps=DnsPageDeps(...))
HostsPage(deps=HostsPageDeps(...))
PremiumPage(deps=PremiumPageDeps(...))
DpiSettingsPage(dpi_settings_feature=..., orchestra_feature=..., runtime_feature=...)
```

Страницы не должны импортировать `feature.public`, `feature.commands`,
`feature.service` или `feature.manager` напрямую. Для них вход уже готовит
`ui.page_composition`.

Если расчётный код страницы начинает использовать commands или core-функции
feature-слоя, он больше не должен жить в `feature/ui`. Его нужно вынести рядом
с feature-логикой, например:

```txt
src/lists/plans.py
```

А UI получает такие функции через готовый feature-вход:

```txt
lists_feature.build_custom_domains_status_plan(...)
```

Настройки внешнего вида тоже не должны жить как `ui/page_plans`.
Канонический слой для них:

```txt
src/settings/appearance.py
```

Страницы могут использовать его как слой настроек внешнего вида, но не должны
читать сырой `settings.store` напрямую.

Фоновые worker-объекты не должны жить в `feature/ui`.
UI-страница может подключить сигналы worker-а и показать результат, но сам
worker относится к feature-слою:

```txt
src/blockcheck/worker.py
src/hosts/operation_worker.py
src/log/runtime_workflow.py
```

Если файл делает действие, а не только считает внешний вид страницы, он тоже
не должен жить как `ui/page_plans`. Например:

```txt
src/dns/dns_check_plans.py
src/diagnostics/page_plans.py
src/about/plans.py
src/blockcheck/strategy_scan_page_plans.py
src/hosts/page_plans.py
src/presets/user_presets_page_plans.py
```

`ui/page_plans.py` допустим только для простых планов интерфейса:

```txt
текст
видимость
доступность кнопок
цвет/тон статуса
порядок вкладок
```

Там нельзя создавать worker, читать или писать файлы, открывать браузер,
открывать проводник, читать `settings.store` или вызывать service/manager.

`PageFactory` — разрешённая точка сборки зависимостей страниц.
Именно там можно читать:

```txt
window.app_runtime.features
window.app_runtime.state
```

Но только для того, чтобы передать странице конкретные зависимости. Для уже
переведённых страниц это один объект `deps`:

```txt
DnsPageDeps
HostsPageDeps
PremiumPageDeps
```

Для страниц, которые ещё переводятся постепенно, временно могут оставаться
конкретные feature/callback-аргументы:

```txt
presets_feature
profile_feature
runtime_feature
ui_state_store
```

Нельзя передавать странице весь `AppRuntime`, если ей нужен только один feature.
И нельзя возвращать старую схему, где страница сама ищет нужный сервис через
`self.window().app_runtime`.

Финальный контракт для страниц:

```txt
page_factory/page deps -> только конкретные feature/deps
страница              -> не знает app_context
```

`require_page_app_context()` запрещён. Если странице чего-то не хватает,
нужно добавить конкретную зависимость в `ui.page_composition`, а не возвращать
поиск через окно.

## Связи страниц

Старый слой `src/ui/page_signals` удалён.

Страницы больше не должны использовать схему:

```txt
Page
  -> emit signal
  -> MainWindow ловит сигнал
  -> MainWindow вызывает feature command
```

Команды feature-слоёв не должны идти через сигнал страницы и главное окно.
Это относится к сигналам вроде:

```txt
start_dpi_requested
stop_dpi_requested
apply_dns_requested
refresh_subscription_requested
```

Правильно:

```txt
Page
  -> получает feature/callback из ui.page_composition
  -> вызывает feature/callback напрямую
```

Неправильно:

```txt
Page
  -> emit command signal
  -> MainWindow ловит сигнал
  -> MainWindow вызывает feature command
```

Если странице нужна навигация, `ui.page_composition` передаёт ей конкретный
callback:

```txt
open_profile_setup
open_preset_raw_editor
open_control
open_root
```

Навигационные сигналы вида `open_*_requested`, `back_clicked` или
`profile_setup_*_requested` не нужны. Это снова делает главное окно
посредником между кнопкой и переходом. Страница должна вызвать переданный
callback напрямую.

Сигналы не запрещены полностью. Они нормальны, когда это именно
UI-синхронизация или событие Qt-виджета:

```txt
textChanged
currentIndexChanged
toggled
selected
item_activated
progress
finished
phase_changed
domains_changed
ipset_changed
adapters_loaded
dns_info_loaded
test_completed
```

Такие сигналы не запускают feature-команду через главное окно. Они только
сообщают странице, что изменился текст, выбран пункт, пришёл результат worker-а
или нужно перерисовать часть интерфейса.

Сигнал дочернего виджета к своей странице допустим, если сама страница уже
имеет нужный feature/callback и выполняет действие напрямую. Например, список
preset-ов может сообщить странице, какой preset выбран. Но страница не должна
пересылать это дальше в `MainWindow` как request-сигнал.

Если странице нужно изменить данные, `ui.page_composition` передаёт ей
конкретный feature или `deps`-объект:

```txt
DnsPageDeps
HostsPageDeps
PremiumPageDeps
presets_feature
profile_feature
runtime_feature
```

Старый слой динамического вызова методов страницы тоже удалён:

```txt
src/ui/page_contracts.py
src/ui/page_method_dispatch.py
```

Не возвращать строковые команды вида `PageMethodName.SHOW_PROFILE`.
Если нужно открыть profile или preset, делать это обычным явным вызовом
страницы или callback из `ui.page_composition`.

`src/ui/window_signal_bindings.py` удалён. Preset-store binding живёт рядом с
preset-логикой в `src/presets/ui_bindings.py`, а стартовое применение настроек
внешнего вида — в `src/ui/window_appearance_bindings.py`.

Причина простая: обработчик не должен позже заново лезть в окно как в контейнер.

`src/ui/window_display_state.py` тоже удалён. Логика краткого отображения
profile/preset живёт рядом с preset-слоем:

```txt
src/presets/display_state.py
```

Именно там готовится `current_strategy_summary`. UI-страницы не считают этот
текст сами: они подписываются на `MainWindowStateStore` и только показывают уже
готовое значение.

Правильная схема:

```txt
presets/display_state.py
  -> MainWindowStateStore.current_strategy_summary
  -> control page показывает готовый текст
```

Нельзя возвращать расчёт profile/preset summary в `MainWindow`,
`window_display_state.py`, `window_bootstrap_runtime.py` или другой `window_*`
файл.

Подписки на `MainWindowStateStore` тоже не должны возвращаться в окно.
Если конкретная страница показывает часть общего UI-состояния, она получает
`ui_state_store` через `ui.page_composition` и подписывается у себя или в своём
маленьком lifecycle-файле. Это нормальная схема:

```txt
ui_state_store -> конкретная страница -> обновление её виджетов
```

Если когда-нибудь понадобится подписка именно оболочки окна, она должна жить в
отдельном `src/ui/window_state_binder.py`. Нельзя добавлять `store.subscribe(...)`
в `MainWindow`, `window_bootstrap_runtime.py`, `window_ui_session.py` или другие
`window_*`-файлы. Иначе окно снова станет общей шиной событий.

`src/main/window_state_sync.py` оставлен только для синхронизации самой оболочки
окна: гирлянда, снежинки, прозрачность, начальный `AppUiState`. Он не должен
ходить в feature-сервисы. Например, Premium-слой передаёт туда уже готовый
ответ `effects_allowed`, а не заставляет окно само проверять Premium.

Правильная схема:

```txt
PremiumFeature / subscription flow
  -> решает, доступны ли Premium-эффекты
  -> window_state_sync применяет готовое значение к окну и UI-state
```

## Runtime

UI вызывает DPI runtime через feature-вход приложения:

```python
window.app_runtime.features.runtime
```

Этот feature-вход уже внутри использует публичный runtime-вход:

```python
import winws_runtime.public as runtime_commands
```

Разрешённый внешний вход:

```txt
src/winws_runtime/public.py
```

Внутренние файлы runtime:

```txt
src/winws_runtime/runtime/*
src/winws_runtime/flow/*
src/winws_runtime/runners/*
```

не должны становиться обычным импортом для UI-страниц.

Runtime-состояние DPI записывает только:

```txt
winws_runtime.state.LaunchRuntimeService
```

Это относится к:

- `launch_phase`;
- `launch_running`;
- `launch_last_error`;
- `launch_busy`;
- `launch_busy_text`.

UI, tray, страницы и startup читают это состояние через:

```python
window.app_runtime.features.runtime.snapshot()
window.app_runtime.features.runtime.is_running()
```

Писать эти поля напрямую нельзя.

Runtime-команды не должны сами искать runtime через `host.app_runtime`.
Они получают `RuntimeFeature` явно:

```python
start_dpi_async(runtime_feature=...)
stop_dpi_async(runtime_feature=...)
shutdown_runtime_sync(runtime_feature=...)
```

Единственный слой, который собирает эти вызовы для UI, — `RuntimeFeature`
в `src/app/feature_facades/runtime.py`. Это защищает проект от скрытой схемы:

```txt
command -> host -> app_runtime -> runtime
```

Такой обратный поиск считается старым контейнерным стилем и не должен
возвращаться.

Живые runtime-объекты принадлежат только `RuntimeFeature`:

```txt
launch_runtime_api
launch_runtime
process_monitor_manager
```

Они не должны храниться на `MainWindow`. Сам `launch_runtime` тоже не должен
держать окно или старый общий контекст. Если ему нужен runtime-state, он берёт
его через `RuntimeFeature.objects.runtime_service`.

Единственная допустимая ссылка на окно в runtime-сборке — `qt_parent`.
Это не контейнер состояния, а Qt-родитель для сигналов и объектов, которым
нужно жить в UI-потоке.

Runtime-события из runner-ов тоже принадлежат `RuntimeFeature`.
Нельзя возвращать схему:

```txt
runner -> MainWindow signal -> window mixin -> runtime state
```

Правильная схема:

```txt
runner
  -> RuntimeEvents.publish_...
  -> RuntimeEventDispatcher
  -> RuntimeEvents.handle_...
  -> LaunchRuntimeService / MainWindowStateStore
  -> RuntimeUiBridge, если нужно показать UI-feedback
```

`runtime_ui_bridge` — это не владелец runtime и не способ спрятать зависимость
runtime от окна. Его задача: уведомления, статусы и отображение runtime в UI.
Он должен оставаться feature-нейтральным: туда нельзя добавлять Premium, DNS,
Hosts, Presets или любую другую конкретную подсистему.
Например:

```txt
runner failure                 -> RuntimeEvents -> RuntimeUiBridge.show_launch_error(...)
runner launch error             -> RuntimeEvents -> RuntimeUiBridge.show_launch_error(...)
runtime content changed         -> RuntimeEvents -> RuntimeUiBridge -> mark_content_changed callback
короткий runtime status         -> RuntimeUiBridge.set_status(...)
runtime phase/running/last_error -> LaunchRuntimeService -> MainWindowStateStore
```

Правило:

```txt
runtime ownership -> RuntimeFeature
runtime state     -> LaunchRuntimeService
runtime -> UI     -> runtime_ui_bridge
```

Нельзя возвращать старую связку:

```txt
runtime -> host.launch_runtime
runtime -> host.launch_runtime_api
runtime -> host.app_context.launch_runtime_service
```

Если runtime-коду нужен живой runtime-объект, он получает его через
`RuntimeFeature`. Если нужен runtime-state, он получает `LaunchRuntimeService`
через `RuntimeFeature.objects.runtime_service`.

Синхронная остановка DPI тоже идёт через runtime feature:

```python
window.app_runtime.features.runtime.shutdown_sync(...)
```

Нельзя вызывать синхронную остановку из UI, updater или blockcheck напрямую через
`winws_runtime.public.shutdown_runtime_sync(...)` без `RuntimeFeature`.
`sync_shutdown.py` не должен сам собирать runtime API как запасной путь.
Он получает `runtime_feature` явно и берёт `runtime_service`,
`launch_runtime_api` и `orchestra_feature` только из него.

Runtime worker-ы тоже не должны доставать runtime API через окно:

```txt
PresetLaunchStartWorker(runtime_feature=..., runtime_api=...)
PresetLaunchStopWorker(runtime_feature=..., runtime_api=...)
StopAndExitWorker(runtime_feature=...)
```

То есть worker получает нужные зависимости при создании, а не ищет их через
`app_instance.app_runtime.features.runtime`.

Короткий текст статуса в главном окне для runtime проходит через:

```txt
src/winws_runtime/runtime/status_feedback.py
```

Runtime-flow не должен напрямую вызывать:

```txt
runtime_owner.app.set_status(...)
window.set_status(...)
progress_slot=runtime_owner.app.set_status
status_callback=app.set_status
notify_threadsafe(...)
```

## Уведомления

`WindowNotificationCenter` отвечает только за верхнеуровневый показ уведомлений:

- нормализация входящего уведомления;
- дедупликация;
- очередь уведомлений во время старта;
- выбор tray/infobar;
- создание кнопок внутри infobar.

Действия кнопок уведомлений живут отдельно:

```txt
src/ui/window_notification_actions.py
```

Именно там находятся переходы по кнопкам, копирование текста, отключение предупреждений, действия при конфликте запуска DPI и auto-fix.
Так центр уведомлений не смешивает показ UI и действия кнопок.

## Premium

Premium делится на две части:

```txt
SubscriptionManager -> получает Premium-данные и управляет QThread
subscription_ui.py   -> применяет результат к UI
```

`SubscriptionManager` не должен напрямую:

- менять статус окна;
- писать в `ui_state_store`;
- обновлять Premium-метку;
- запускать гирлянду/снежинки;
- писать `app.donate_checker`;
- показывать уведомления.

Эти действия относятся к:

```txt
src/donater/subscription_ui.py
```

Внешний вход Premium:

```txt
src/donater/public.py
```

Слои `main` и `ui` должны обращаться к Premium через:

```txt
window.app_runtime.features.premium
```

Это относится и к startup: создание, запуск и cleanup subscription manager не должны идти прямым импортом `donater.public`.

## Startup

`StartupCoordinator` отвечает за порядок запуска.

Он может:

- запустить минимальные компоненты, нужные для первого клика;
- отложить тяжёлые задачи после первого показа окна;
- записать startup-метрики.

Он не должен:

- становиться местом feature-логики;
- возвращать тяжёлые операции в первый кадр окна;
- смешивать startup и runtime-правила.

Post-startup задачи живут в `src/main/post_startup*.py`.
Их общий установщик:

```txt
src/main/post_startup.py
```

собирает зависимости из окна и `AppRuntime`, а отдельные post-startup модули
получают уже готовые функции:

```txt
set_status
log_startup_metric
notify / notify_many
apply_dns_on_startup_async
startup_lists_check
start_proxy_if_enabled_async
```

Отдельные post-startup модули не должны сами читать:

```txt
window.app_runtime.features.*
window.window_notification_center
```

Исключение — сам `post_startup.py`, потому что это точка сборки этих зависимостей.

Системный tray — отдельный feature-слой:

```txt
src/app/feature_facades/tray.py
src/tray_commands.py
src/tray.py
```

Правило:

```txt
TrayFeature
  -> вызывает tray_commands
tray_commands
  -> создаёт SystemTrayManager и выполняет tray-действия
SystemTrayManager
  -> рисует tray UI и вызывает TrayFeature
```

`SystemTrayManager` не должен напрямую обращаться к runtime, Telegram proxy,
settings.store или другим внутренностям приложения. Он показывает меню,
уведомления и отправляет команды в `TrayFeature`.

## Feature API

Внешний слой приложения видит feature только через:

```txt
window.app_runtime.features.*
```

Это значит:

```txt
UI / main / tray / другая feature
  -> вызывает явный метод feature-фасада
  -> не просит service/store/manager/worker
```

Для UI-страниц правило строже:

```txt
PageFactory передаёт странице готовый feature-вход из window.app_runtime.features.*
страница не импортирует feature.public сама
```

Внутренние `service`, `store`, `manager`, `worker` не являются API feature.
Если внешний код просит такой объект, нужно добавить явный метод feature.

Правильно:

```txt
features.presets.select_preset(...)
features.profile.list_profiles(...)
features.runtime.start(...)
features.premium.initialize_subscription(...)
features.tray.hide_to_tray(...)
```

Для presets/profile это означает:

```txt
внешний слой -> PresetsFeature / ProfileFeature
PresetsFeature -> presets.commands -> presets service/store
ProfileFeature -> profile.commands -> profile service/settings
```

`PresetFileService`, `ProfilePresetService`, `PresetModeCoordinator`,
`PresetFileStore` и `PresetSelectionService` не являются внешним API.
Они могут использоваться внутри своих feature-слоёв, но UI/main/tray не должны
просить их напрямую.

Неправильно:

```txt
features.presets.preset_file_store
features.profile.ProfilePresetService(...)
features.runtime.objects.launch_runtime
features.premium.subscription_manager
features.tray.manager()
```

Если код находится внутри самой feature-папки, он может использовать свои
`commands`, `service`, `store`, `manager` и `worker`. Это внутренняя кухня
подсистемы. Например, `telegram_proxy/ui` может работать с proxy-manager через
свой feature-слой, но `main`, `tray` или другая feature не должны просить этот
manager напрямую.

`feature/public.py` больше не считается местом, куда надо складывать всё подряд.
Он может экспортировать стабильные типы состояния, простые команды без выдачи
внутренних объектов и небольшие публичные функции feature. Но он не должен
экспортировать:

```txt
create_*_manager
create_*_worker
create_*_services
get_*_manager
*_store
*_service
```

Если feature-фасаду нужен внутренний worker или manager, он берёт его из
`feature.commands` внутри своей подсистемы и наружу отдаёт понятное действие.

## AppRuntime / Feature Cutover

Этот раздел фиксирует финальный переход от старого контейнерного стиля к
новой схеме feature-слоёв.

`AppRuntime` не должен содержать `context` как общий выход во всё приложение.
Разрешённая форма:

```txt
AppRuntime.paths
AppRuntime.state
AppRuntime.features
```

Запрещено:

```txt
AppRuntime.context
window.app_context
page.window().app_runtime.context
```

Владение runtime:

```txt
RuntimeFeature
  -> launch_runtime
  -> launch_runtime_api
  -> process_monitor_manager

LaunchRuntimeService
  -> единственная точка записи runtime-состояния DPI
```

`MainWindow` не хранит эти объекты.

Владение Premium:

```txt
PremiumFeature
  -> subscription/premium flow
  -> внутренний checker/storage
  -> создание и cleanup SubscriptionManager
```

Страницы Premium не получают checker/storage и не импортируют
`donater.service` или `SubscriptionManager`.

Владение preset/profile:

```txt
PresetsFeature
  -> выбранный source preset
  -> selected preset/profile summary
  -> launch snapshot для runtime

ProfileFeature
  -> profile
  -> templates
  -> strategy catalog
```

`PresetFileService`, `PresetSelectionService`, `PresetModeCoordinator` и
`ProfilePresetService` — внутренние детали своих feature-слоёв.

Владение окна:

```txt
MainWindow
  -> создаёт AppRuntime
  -> создаёт страницы
  -> держит WindowUiSession
  -> обрабатывает lifecycle окна
```

`MainWindow` не хранит бизнес-сервисы и не является источником истины для
runtime, Premium, presets/profile, DNS или hosts.

Владение страниц:

```txt
PageFactory / ui.page_composition
  -> передаёт странице конкретный feature/store/callback

Page
  -> рисует UI
  -> вызывает переданный feature/callback
```

Финальный контракт запрещает:

```txt
require_page_app_context()
page_dependencies.py
page.window().app_runtime.context
```

Для каждого состояния должен быть один владелец записи:

```txt
runtime DPI       -> LaunchRuntimeService
Premium           -> PremiumFeature / donater.state
preset/profile    -> PresetsFeature / ProfileFeature
DNS               -> DnsFeature / dns.state
Hosts             -> HostsFeature / hosts.state
оболочка окна     -> MainWindowStateStore
```

Если новое изменение требует второй writer для того же состояния, сначала надо
менять контракт состояния, а не добавлять запасной путь.

## AppRuntime

`AppRuntime` — это тонкая сборка готовых публичных входов приложения.

Он живёт в:

```txt
src/app/runtime.py
src/app/features.py
src/app/feature_facades/
```

Правило:

```txt
window.app_runtime.paths -> общий AppPaths
window.app_runtime.state -> общий state приложения
window.app_runtime.features -> публичные входы feature-слоёв
```

`AppRuntime` не содержит бизнес-логику сам.
Он не запускает DPI, не меняет DNS, не сохраняет preset и не проверяет Premium напрямую.
Он только собирает уже готовые feature-фасады.

`src/app/features.py` тоже не должен становиться большим складом всех feature.
Его роль:

```txt
AppFeatures dataclass
build_app_features(...)
```

Сами feature-фасады живут в отдельных файлах:

```txt
src/app/feature_facades/autostart.py
src/app/feature_facades/blockcheck.py
src/app/feature_facades/blobs.py
src/app/feature_facades/diagnostics.py
src/app/feature_facades/dns.py
src/app/feature_facades/dpi_settings.py
src/app/feature_facades/external.py
src/app/feature_facades/hosts.py
src/app/feature_facades/lists.py
src/app/feature_facades/logs.py
src/app/feature_facades/orchestra.py
src/app/feature_facades/premium.py
src/app/feature_facades/presets.py
src/app/feature_facades/profile.py
src/app/feature_facades/program_settings.py
src/app/feature_facades/runtime.py
src/app/feature_facades/telegram_proxy.py
src/app/feature_facades/tray.py
```

Каждый фасад вызывает вход своей подсистемы:

```txt
feature.public   -> если это стабильный публичный API без внутреннего объекта
feature.commands -> если это внутренняя команда feature
feature.state    -> если нужен тип состояния
```

Для tray используется `tray_commands.py`, потому что сам `tray.py` уже занят
нативным Windows UI системного трея.

Нельзя возвращать `src/app/features.py` или один общий файл фасадов в состояние
большого каталога методов и классов на сотни строк. Если feature разрастается,
она должна жить в своём файле внутри `src/app/feature_facades`, а настоящая
логика должна оставаться в `feature.public` / `feature.commands` /
`feature.state`.

Сборка `AppRuntime` не должна выполнять тяжёлые действия: запуск DPI, проверку
Premium, чтение больших файлов, сетевые запросы, DNS/hosts операции. Она только
собирает объекты и callbacks.

Запрещено превращать `AppRuntime` в новый общий мешок полей.
Если feature ещё не имеет понятного публичного входа, сначала надо сделать `public.py` / `commands.py`, а не класть внутренний сервис прямо в `AppRuntime`.

Новый UI-код получает feature через зависимости страницы:

```python
NetworkPage(deps=DnsPageDeps(dns_feature=window.app_runtime.features.dns))
```

Эти зависимости создаёт `PageFactory`.
Если конкретная страница переведена на явные зависимости, внутри неё не надо оставлять параллельный прямой импорт той же feature.

## Команды

Если UI просит feature что-то сделать, нужен явный command-вход.

Текущие command-входы:

```txt
src/winws_runtime/runtime/commands.py
donater/commands.py
presets/commands.py
profile/commands.py
blockcheck/commands.py или blockcheck/public.py как публичный action-вход
blobs/commands.py
dns/commands.py
hosts/commands.py
lists/commands.py
autostart/public.py как action-вход автозапуска GUI
telegram_proxy/commands.py
orchestra/commands.py
program_settings/commands.py
tray_commands.py
```

Правило:

- `public.py` показывает внешний вход feature;
- `commands.py` содержит действия feature;
- UI и соседние feature не должны вызывать сервисы напрямую, если для этого действия уже есть command-функция.

Примеры текущих действий:

- `presets.commands` сохраняет, создаёт, переименовывает, импортирует, экспортирует, дублирует, сбрасывает и удаляет preset-файлы;
- `presets.commands` отдаёт `PresetSelectionState`: выбранный source preset, имя файла, путь, выбранный profile и краткую сводку;
- `presets.commands.get_launch_snapshot()` — единый внешний вход для runtime, когда ему нужен выбранный source preset для запуска;
- `presets.mode_coordinator` владеет выбором source preset-а и живёт в preset-слое, а не внутри DPI runtime;
- `profile.commands` читает profile-ы выбранного preset-а, применяет готовую стратегию, включает/выключает profile, двигает profile и сохраняет оценку стратегии;
- `dns.commands` отдаёт `DnsState`, применяет auto/provider/custom DNS, управляет принудительным DNS и возвращает `DnsCommandResult`;
- `dns.ui.page_plans` строит только планы отображения DNS-страницы: тексты, статусы, подсветку, выбор карточек и предупреждения;
- `dns.dns_check_plans` содержит действия DNS-check: быструю проверку, сохранение результата и планы запуска/завершения;
- `hosts.commands` отдаёт `HostsState`, читает/пишет hosts, применяет service-profile, очищает hosts, восстанавливает права и возвращает `HostsCommandResult`;
- `hosts.page_plans` строит планы hosts-страницы: группы сервисов, выбор profile, статусы, ошибки доступа и результат операции;
- `hosts.ui.page_runtime` держит только временный runtime-cache hosts-страницы и создание `HostsManager` для UI;
- `lists.commands` читает и сохраняет пользовательские списки `hostlist`, `ipset`, `ipset-ru`, `netrogat`, открывает файлы и пересобирает итоговые списки;
- `lists.ui.page_plans` строит только планы отображения страниц списков: счётчики, проверки ввода и результат добавления строки;
- `presets.user_presets_page_plans` строит строки списка пользовательских preset-ов без импорта UI-runtime-service;
- `donater.commands` создаёт код привязки, проверяет Premium-статус, создаёт Premium worker, читает/сбрасывает локальное Premium-состояние и отдаёт `PremiumState`;
- `diagnostics.public` создаёт worker диагностики соединения, а `diagnostics.page_plans` готовит архив обращения по логам;
- `about.plans` содержит действия About/Support: открыть Telegram, GitHub, Discord, Discussions и папку помощи;
- `autostart.public` включает/отключает канонический автозапуск GUI и сохраняет его состояние;
- `telegram_proxy.commands` отдаёт runtime-manager и настройки запуска, строит планы диагностики, запускает диагностику, открывает ссылки/лог и обновляет Telegram-записи в `hosts`;
- `orchestra.commands` отдаёт actions/settings/runtime для orchestra UI;
- `blobs.commands` отдаёт планы и операции blob-страницы;
- `program_settings.commands` меняет автозапуск DPI, Windows Defender и блокировку MAX.
- `tray_commands` создаёт tray, показывает tray-уведомления, сворачивает окно,
  меняет прозрачность окна и выполняет команды tray-консоли.

`AppRuntime` может собирать только эти публичные входы. Он не заменяет `commands.py` и не становится местом новой логики.

## Как уменьшать зависимость от window

Плохой вариант:

```python
SomeFeatureUi(window)
```

Лучше:

```python
SomeFeatureUi(
    feature=window.app_runtime.features.some_feature,
    set_status=window.set_status,
    parent=window,
)
```

Правило:

- если нужен feature, передавать конкретный `window.app_runtime.features.<feature>`;
- если нужен только `ui_state_store`, брать его из `window.app_runtime.state.ui` или передавать явно;
- если нужны пути, брать `window.app_runtime.paths` или передавать конкретный путь явно;
- если нужен сервис feature, брать конкретный feature из `window.app_runtime.features`, а не общий контейнер;
- если нужна команда runtime, передавать `window.app_runtime.features.runtime`;
- если нужен только родительский виджет, передавать `parent`.

Так окно не становится контейнером всего приложения.

Состояние самого окна хранится в отдельных объектах:

```txt
window.ui_session    -> страницы, навигация, поиск, runtime UI bridge
window.startup_state -> startup-флаги, startup-метрики, отложенный tray-показ
window.close_state   -> сценарий закрытия: выход, остановка DPI, закрытие полностью
window.visual_state  -> временные визуальные overlay-объекты
```

Эти состояния не должны возвращаться в россыпь приватных полей окна.

## Страницы

Страница отвечает за UI: виджеты, сигналы, отображение текста и состояния.

`PageFactory` отвечает за создание страниц и передачу зависимостей.

`PageFactory` не записывает страницы в поля главного окна:

```txt
window.network_page
window.logs_page
window.orchestra_page
```

Страницы живут в едином месте:

```txt
window.ui_session.page_host.pages
```

Открытие, получение загруженной страницы, добавление в `stackedWidget`,
переключение текущей страницы и синхронизация активного пункта навигации идут
через `PageHost`.

Правильная схема:

```txt
ui.window_adapter / navigation callback
  -> WindowUiSession.page_host
  -> ensure_page / show_page / current_page
```

Нельзя делать это из случайных файлов окна или навигации:

```txt
window.stackedWidget.addWidget(...)
window.stackedWidget.currentWidget()
window.stackedWidget.setCurrentWidget(...)
window.navigationInterface.setCurrentItem(...)
```

Флаг `page_stack_bootstrap_complete` тоже меняет только `PageHost`.

`PageRouteSpec` не содержит `attr_name`, потому что старый путь
`window.<page_attr>` больше не является рабочим API.

Схема создания:

```txt
MainWindow
  -> PageFactory
      -> Page(feature=..., state=..., callbacks=..., parent=window)
```

Правило:

- страница не ищет feature через `self.parent()`;
- страница не импортирует `feature.public`, если `PageFactory` уже может передать нужный feature;
- страница не создаёт service/manager напрямую;
- если нужен долгоживущий объект страницы, он должен называться по роли: `runtime`, `workflow`, `plans`, `state`, а не общим словом `controller`;
- бывшие `*controller.py` не возвращать как новую точку смешения UI, состояния и действий.

Первое правило для новых правок:

```txt
QObject parent может оставаться window, если это нужно для Qt lifetime.
Business dependency не должна доставаться через parent().
```

## Общие тексты и имена страниц

`PageName` и общий каталог текстов живут в `src/app`, а не в `src/ui`:

```txt
src/app/page_names.py
src/app/text_catalog.py
```

Причина: эти данные нужны не только виджетам. Ими пользуются `main`,
`blockcheck`, `updater`, навигация и страницы. Поэтому `ui` не должен быть
скрытым источником общих app-level сущностей.

Старые пути удалены:

```txt
src/ui/page_names.py
src/ui/text_catalog.py
```

Нельзя возвращать их как wrappers или compatibility imports.

Например, если объекту нужны `ui_state_store`, пути и команда runtime,
передавать их явно в конструктор. Не доставать их из `self.parent()`.
