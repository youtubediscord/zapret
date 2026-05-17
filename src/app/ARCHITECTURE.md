# Архитектурный контракт GUI

Дата фиксации: 2026-05-15.

Этот документ описывает текущее состояние кода. Главное правило простое:
окно показывает интерфейс, но не собирает приложение и не является общим
контейнером сервисов.

## Запуск

Каноническая цепочка запуска:

```text
src/main/entry.py
  -> создаёт QApplication
  -> создаёт ApplicationController
  -> ApplicationController создаёт LupiDPIApp
  -> ApplicationController создаёт AppRuntime
  -> window_runtime_setup.attach_app_runtime_to_window(...)
  -> окно показывает Fluent UI
  -> app.exec()
```

Второго пути создания окна нет. `src/main/window.py` содержит только
`LupiDPIApp`.

## Главное окно

`LupiDPIApp` — это оболочка интерфейса.

Окну разрешено:

- держать навигацию;
- держать `WindowUiSession`, то есть состояние страниц и бокового меню;
- показывать уведомления;
- принимать событие закрытия окна;
- отдавать пользовательские действия наружу через готовые команды.

Окну запрещено:

- создавать `AppRuntime`;
- собирать feature-слои;
- быть складом сервисов;
- хранить `window.app_runtime`;
- хранить `window.*_feature`;
- быть источником данных для страниц.

После подключения runtime окно получает только маленькие внутренние зависимости,
которые нужны самой оболочке окна:

```text
FeatureWindowDeps
  явный порт окна для сборки feature-зависимостей

WindowStateActions
  действия оформления окна и запись короткого UI-состояния

WindowPageActions
  набор callback-ов для страниц; не хранит полное окно

WindowStartupRuntime
  callback продолжения старта

ApplicationLifecycleWindowPort
  узкие действия окна для полного выхода и cleanup

WindowRuntimeBootstrapDeps
  runtime -> UI bridge и preset runtime binding

PostStartupHost
  узкий host для поздних задач после старта

TrayWindowPort
  узкие действия окна для системного трея
```

`src/main/window_runtime_setup.py` остаётся единственным входом подключения
runtime к окну, но сам не содержит подробную сборку. Внутренние части разнесены
по маленьким файлам:

```text
window_page_deps_setup.py
  PageDepsContext и WindowUiRoot

window_lifecycle_setup.py
  геометрия, close-flow и ApplicationLifecycle

window_notifications_setup.py
  уведомления runtime/tray

WindowPageActions создаётся только после `window_notifications_setup.py`.
Причина простая: действия страниц используют `window_notification_center.notify`,
а центр уведомлений появляется именно на этапе `window_notifications_setup.py`.

window_startup_setup.py
  WindowStartupRuntime для позднего старта

window_startup_signal_setup.py
  стартовые сигналы и первый показ окна
```

`PageDepsContext` — маленький набор feature-входов и callback-ов для страниц.
Он передаётся в `WindowUiRoot`, затем в `UiPageFactory`. Контекст не хранится как
`window.page_deps_context`, поэтому окно не становится складом зависимостей
страниц. Callback-и окна приходят в него через `WindowPageActions`, а не через
разбор полного окна. Builder-ы из `src/ui/page_deps/` получают уже этот контекст,
а не всё окно.

## AppRuntime

`AppRuntime` — тонкая сборка приложения.

В нём живут:

- `paths` — единый источник путей программы;
- `state` — состояние оболочки и runtime;
- `features` — публичные входы подсистем.

`AppRuntime` не должен превращаться в новый `AppContext`. В него нельзя добавлять
сценарии кнопок, логику страниц, запуск окна или закрытие приложения.

## AppFeatures

`src/app/features.py` — только dataclass-реестр feature-входов.

Сборка feature-входов живёт в:

```text
src/app/feature_assembly.py
```

Это разделение нужно, чтобы `AppFeatures` не стал большим объектом, который сам
знает, как устроены все подсистемы.

## Страницы

Страницы получают зависимости явно через page deps.

Цепочка такая:

```text
Navigation schema
  -> говорит, какие страницы есть

UiPageFactory
  -> создаёт страницу

page_composition
  -> выбирает builder зависимостей

ui/page_deps/*
  -> собирают конкретные зависимости страницы из PageDepsContext
```

`src/ui/page_composition.py` содержит только карту `PageName -> builder` и
проверку покрытия. Конкретные зависимости лежат в `src/ui/page_deps/`.
Builder-ы не получают окно целиком.

Страница не должна брать данные через:

```text
self.window().app_runtime
self.window().ui_session
self.window().navigationInterface
self.window().stackedWidget
```

`self.window()` можно использовать как родителя для `InfoBar`, `MessageBox` и
других окон сообщений.

## Состояние

`MainWindowStateStore` хранит только короткое состояние общей оболочки UI.
Подробная карта владельцев состояния находится в:

```text
src/app/STATE_OWNERSHIP.md
```

Feature state остаётся внутри feature-слоёв. Например DNS-подробности не должны
жить в общем store окна.

## Настройки И Файлы

Единственный рабочий файл настроек и состояния пользователя:

```text
<install_dir>/settings/settings.json
```

В `settings.json` должны храниться:

- Premium-состояние, код привязки и Premium-кэш;
- выбранные hosts-профили пользователя;
- геометрия окна;
- предупреждения;
- настройки интерфейса;
- состояние orchestra;
- другие данные, которые программа запоминает про пользователя.

Запрещено добавлять отдельные рабочие файлы пользовательского состояния:

```text
premium.ini
user_hosts.ini
новые .ini
отдельные .json для пользовательских настроек
```

Запрещены fallback-ветки вида "если нет в settings.json, прочитать старый
ini/реестр/старый файл". Старый путь не должен участвовать в чтении, записи,
очистке, восстановлении или установке.

Реестр Windows не используется как хранилище настроек ZapretGUI. При этом
системные Windows-функции могут работать с реестром, если сам механизм Windows
этого требует: DNS, Defender, политики запуска, службы, проверка установленных
программ.

`hosts_catalog.json` остаётся отдельным файлом-шаблоном каталога доменов:

```text
source: <project>/private_zapretgui/resources/json/hosts_catalog.json
exe:    <exe_dir>/json/hosts_catalog.json
```

`hosts_catalog.json` не является пользовательскими настройками. Пользовательский выбор
из hosts-каталога хранится только в `settings.json`.

Встроенные ресурсы программы могут оставаться отдельными файлами, потому что это
не состояние пользователя: preset-ы, `profile/templates`,
`profile/strategy_catalogs`, lua, иконки, темы, exe/bin.

## Fluent UI

Production UI требует `qfluentwidgets`.

Запрещено держать запасную ветку импорта, где при отсутствии Fluent-виджета
код подменяет его обычным Qt-виджетом.

Если `qfluentwidgets` не установлен, это ошибка окружения запуска. Программа не
должна строить другой интерфейс на обычных Qt-виджетах.

Переключатели и checkbox-элементы в production UI должны идти через stock
`qfluentwidgets`, например `SwitchButton` или `CheckBox`. Старый самодельный
`Win11ToggleSwitch` и прямой `QCheckBox` из `PyQt6.QtWidgets` не являются
рабочим UI-путём.

Многострочные поля ввода/лога должны использовать проектные fluent-обёртки,
например `ScrollBlockingTextEdit`, а не обычный `QTextEdit` из
`PyQt6.QtWidgets`.

Вложенные страницы используют `BreadcrumbBar`. Одиночная кнопка "Назад" не
является рабочим путём для подстраниц.

## Автопроверка

Границы проверяются командой:

```bash
PYTHONPATH=src python -m app.architecture_checks
```

Проверка ловит возврат старых слоёв:

- `app_context`;
- второй путь создания окна в `window.py`;
- создание `AppRuntime` внутри окна;
- хранение `window.app_runtime`;
- хранение `window.*_feature` в оконном слое;
- сборку feature-зависимостей из полного окна вместо `FeatureWindowDeps`;
- сборку page deps из полного окна вместо `WindowPageActions`;
- передачу полного окна в post-startup как feature-контейнера;
- передачу окна в Discord tray command;
- page signals как командную шину;
- qfluentwidgets fallback-и на обычный Qt UI;
- одиночную кнопку "Назад" во вложенных preset-страницах.
