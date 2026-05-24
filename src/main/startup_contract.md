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

После этого `entry.py` не выполняет позднюю обвязку синхронно перед
`app.exec()`. Подключение Windows shutdown hook, оформление окна и IPC-сервер
ставятся через `QTimer.singleShot(0, ...)`, чтобы Qt event loop сначала начал
обрабатывать уже поставленную сборку UI.

Post-startup задачи не устанавливаются сразу в этом позднем bootstrap-шаге.
Они только подготавливаются и привязываются к `StartupInteractive`; реальная
установка идёт следующим Qt-событием после сигнала `startup_interactive_ready`.
Так импорты проверок, DNS, апдейтера и прогревов не попадают в стек сборки
первой страницы.

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
- отметить `StartupInteractive`, когда основной UI уже собран и навигация готова;
- дать Qt короткий зазор на отрисовку и первый ввод пользователя;
- взять `WindowStartupRuntime`;
- создать `StartupCoordinator` через переданный callback;
- запустить `StartupCoordinator`;
- отметить метрики `StartupCoreReady`, `StartupPostInit`.

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

Startup-шаги внутри `StartupCoordinator` не выполняются плотным циклом в одном
проходе главного Qt-потока. Они ставятся по одному через очередь Qt с короткой
паузой между шагами. Так окно уже видно, навигация доступна, а цикл интерфейса
успевает обработать клики и перерисовку между подготовкой runtime, process
monitor и основным startup-контуром.

DPI autostart тоже не запускается в тот же момент, когда post-init только
поставлен. Он получает отдельную короткую задержку после post-init, чтобы
старт DPI не отнимал первый интерактивный момент у GUI.

`application_post_startup.py` собирает явные зависимости для поздних задач из
готового окна и готового `AppRuntime`. Самим post-startup задачам передаётся
`PostStartupHost`, а не полное окно.

`post_startup.py` только принимает `PostStartupDeps` и ставит поздние задачи.
Он не достаёт feature-ы из окна и не импортирует конкретные post-startup
модули на верхнем уровне файла. Конкретный установщик подгружается только при
реальном вызове.

`post_startup_*.py` отвечают за поздние задачи, но не все они ждут одного
сигнала:

- проверки, backend-прогревы Network/Premium/Appearance/Logs, прогрев профилей
  и GUI-прогрев страниц ставятся после `StartupInteractive` с короткими
  задержками, чтобы UI уже успел отрисоваться и принять первый ввод;
- DNS-применение, списки, Telegram Proxy, tray для обычного запуска,
  update-check и maintenance ставятся после `StartupPostInit`;
- GUI-прогрев страниц создаёт видимые страницы бокового меню и идёт по одной
  странице с паузами. Для `Network` отдельно греется backend-кэш DNS-данных, а
  GUI-прогрев создаёт только оболочку страницы без запуска DNS-загрузки.

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
Метрики задач, которые действительно ждут `StartupPostInit`, должны начинаться
с `StartupPostInit...`. Ранний GUI-прогрев страниц ждёт `StartupInteractive`,
поэтому использует отдельные метрики вида `StartupPage...WarmupQueued`.

## Fluent UI

Production-интерфейс требует `qfluentwidgets`. Если этой библиотеки нет, это
ошибка окружения запуска, а не повод строить запасной интерфейс на обычных
Qt-кнопках и полях.
