# Контракт Запуска

Этот документ фиксирует текущий контракт запуска GUI после разгрузки первого старта.

## Основные Роли

`ApplicationController` создаёт главное окно, собирает `AppRuntime` и явно
подключает его к окну через `attach_app_runtime_to_window(...)`.

Главное окно создаётся напрямую в `ApplicationController`. Там же оно
регистрируется как активное окно приложения.

`window_runtime_setup.attach_app_runtime_to_window(...)` — единственное место,
где готовый `AppRuntime` подключается к окну. Сам файл остаётся коротким
координатором, а подробная сборка разнесена по маленьким setup-файлам:
lifecycle, уведомления, page deps и стартовые сигналы.

Порядок внутри этого шага важен:

```text
attach_window_lifecycle(...)
attach_window_notifications(...)
build_window_page_actions(...)
attach_startup_deps_to_window(...)
attach_window_ui_root(...)
restore_window_geometry(...)
connect_window_startup_signals(...)
show_initial_window_if_needed(...)
start_window_deferred_init(...)
```

`WindowPageActions` создаётся после уведомлений, потому что действия страниц
используют `window_notification_center.notify`.

Feature-зависимости не собираются из полного окна. Для этого есть
`FeatureWindowDeps`: маленький явный набор Qt-parent, startup/close state и
callback-ов окна. Для страниц есть `WindowPageActions`, то есть отдельный набор
разрешённых действий окна. `WindowPageActions` не хранит полное окно: он
передаёт дальше только готовые callback-и.

`AppRuntime` — это тонкая сборка путей, состояния и feature-входов приложения.
Его создаёт управляющий слой приложения, а не само окно. `AppContext` в рабочем
потоке больше нет.

`WindowStartupMixin` отвечает за жизненный цикл окна во время старта:

- подготовить стартовое состояние окна;
- показать окно как можно раньше;
- собрать основной UI после первого показа;
- взять `WindowStartupRuntime`;
- создать `StartupCoordinator` через переданный callback;
- запустить `StartupCoordinator`;
- отметить метрики `StartupInteractive`, `StartupCoreReady`, `StartupPostInit`.

`ApplicationLifecycle` исполняет полный выход из приложения:

- скрыть tray-иконку;
- сохранить геометрию;
- остановить DPI, если пользователь выбрал выход с остановкой;
- очистить Premium, runtime threads, страницы и визуальные ресурсы;
- вызвать `QApplication.quit()`.

`ApplicationLifecycle` не хранит главное окно напрямую. Для действий, которым
всё ещё нужен Qt-объект окна, используется `ApplicationLifecycleWindowPort`.

`WindowLifecycleMixin` только принимает Qt-события окна и передаёт команды в
`ApplicationLifecycle`.

`StartupCoordinator` отвечает только за порядок запуска:

- минимальный интерактивный контур;
- основной стартовый контур;
- постановка post-init задач;
- постановка DPI autostart.

`application_post_startup.py` собирает явные зависимости для поздних задач из
готового окна и готового `AppRuntime`. Самим post-startup задачам передаётся
`PostStartupHost`, а не полное окно.

`post_startup.py` только принимает `PostStartupDeps` и ставит поздние задачи.
Он не достаёт feature-ы из окна.

`post_startup_*.py` отвечают за поздние задачи после `StartupPostInit`: проверки,
DNS, списки, Telegram Proxy, tray для обычного запуска, update-check и
диагностику.

## Что Не Создаётся На Первом Старте

На первом старте не создаются:

- `HostsManager`;
- `DNSUIManager`;
- `DiscordManager`;
- старый `UIManager`.

`HostsManager` создаётся при открытии hosts-страницы. DNS при старте идёт через DNS startup worker. `DiscordManager` создаётся лениво только при реальной попытке перезапуска Discord.

## Канонические Startup-Метрики

- `StartupTTFF` — первый показ окна.
- `StartupInteractive` — окно уже готово к первому взаимодействию.
- `StartupCoreReady` — основной стартовый контур готов.
- `StartupPostInit` — post-init задачи поставлены.
- `StartupDpiAutostart` — DPI autostart передан в поздний запуск.

Все startup-метрики должны начинаться с `Startup...`.
Дополнительные поздние метрики должны начинаться с `StartupPostInit...`.

## Fluent UI

Production-интерфейс требует `qfluentwidgets`. Если этой библиотеки нет, это
ошибка окружения запуска, а не повод строить запасной интерфейс на обычных
Qt-кнопках и полях.
