# Архитектурный контракт GUI

Дата фиксации: 2026-05-10

Этот документ фиксирует текущие границы проекта. Он нужен не для описания всех деталей,
а чтобы новые правки не возвращали старую схему, где главное окно знает обо всём.

## Главное окно

`MainWindow` — это UI-оболочка.

Разрешено:

- держать виджеты окна;
- держать `WindowUiSession`;
- держать контроллер уведомлений;
- держать геометрию окна;
- держать lifecycle окна: закрытие, сворачивание, cleanup.

Запрещено:

- делать окно источником истины для runtime;
- складывать в окно временные поля навигации вида `window._nav_*`;
- складывать в окно состояние поиска вида `window._sidebar_search_*`;
- обращаться из UI к `launch_controller` напрямую;
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
window.app_context -> сервисы приложения и общие store-объекты
```

Нельзя держать рядом два пути:

```txt
window._nav_icons
window.ui_session.nav_icons
```

Если поле переехало в `WindowUiSession`, старое поле на окне не возвращать.

## Runtime

UI вызывает DPI runtime только через публичный вход:

```python
import winws_runtime.public as runtime_commands
```

или:

```python
from winws_runtime.public import start_dpi_async
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

Исключение на текущем этапе:

- startup-код может создавать runtime-контроллер;
- аварийное закрытие может использовать sync shutdown;
- эти исключения должны быть видны в `src/app/ARCHITECTURE_DEBT.md` и не расширяться.

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

## Feature public.py

Для новых границ используется простой вход:

```txt
feature/public.py
```

Примеры:

```txt
src/winws_runtime/public.py
src/donater/public.py
src/presets/public.py
src/profile/public.py
src/dns/public.py
src/hosts/public.py
src/program_settings/public.py
```

Правило:

```txt
внешний слой импортирует feature через public.py
```

Это не значит, что все внутренние импорты сразу запрещены внутри самой feature-папки.
Например, `donater/ui/*` может работать с внутренними Premium-классами, потому что это часть самой Premium-подсистемы.

Текущие публичные входы:

- `winws_runtime.public` — команды запуска, остановки, перезапуска DPI, смены метода запуска, autostart, sync shutdown и runtime-state;
- `donater.public` — PremiumState, Premium-команды и startup-доступ к SubscriptionManager;
- `presets.public` — сервисы, модели и состояние выбранного source preset-а;
- `profile.public` — команды profile-слоя, список profile-ов, настройка profile и оценки готовых стратегий;
- `dns.public` — DNS-состояние, DNS-команды, DNS-проверка и общие DNS-данные;
- `hosts.public` — hosts-состояние, команды изменения Windows `hosts` и безопасное чтение/запись файла;
- `program_settings.public` — общие настройки программы: автозапуск DPI, Windows Defender, блокировка MAX и подписка на их общий снимок.

## Команды

Если UI просит feature что-то сделать, нужен явный command-вход.

Текущие command-входы:

```txt
src/winws_runtime/runtime/commands.py
donater/commands.py
presets/commands.py
profile/commands.py
dns/commands.py
hosts/commands.py
program_settings/commands.py
```

Правило:

- `public.py` показывает внешний вход feature;
- `commands.py` содержит действия feature;
- UI и соседние feature не должны вызывать сервисы напрямую, если для этого действия уже есть command-функция.

Примеры текущих действий:

- `presets.commands` сохраняет, создаёт, переименовывает, импортирует, экспортирует, дублирует, сбрасывает и удаляет preset-файлы;
- `presets.commands` отдаёт `PresetSelectionState`: выбранный source preset, имя файла, путь, выбранный profile и краткую сводку;
- `presets.commands.get_launch_snapshot()` — единый внешний вход для runtime, когда ему нужен выбранный source preset для запуска;
- `profile.commands` читает profile-ы выбранного preset-а, применяет готовую стратегию, включает/выключает profile, двигает profile и сохраняет оценку стратегии;
- `dns.commands` отдаёт `DnsState`, применяет auto/provider/custom DNS, управляет принудительным DNS и возвращает `DnsCommandResult`;
- `hosts.commands` отдаёт `HostsState`, читает/пишет hosts, применяет service-profile, очищает hosts, восстанавливает права и возвращает `HostsCommandResult`;
- `donater.commands` создаёт код привязки, проверяет Premium-статус и отдаёт `PremiumState`.
- `program_settings.commands` меняет автозапуск DPI, Windows Defender и блокировку MAX.

Не нужно сразу строить большой `AppRuntime`. Сначала у каждой feature должен быть понятный вход.

## Как уменьшать зависимость от window

Плохой вариант:

```python
SomeController(window)
```

Лучше:

```python
SomeController(
    ui_state_store=window.ui_state_store,
    app_context=window.app_context,
    start_dpi=start_dpi_async,
)
```

Правило:

- если нужен только `ui_state_store`, передавать `ui_state_store`;
- если нужен только `app_context`, передавать `app_context`;
- если нужна команда runtime, передавать command-функцию;
- если нужен только родительский виджет, передавать `parent`.

Так окно постепенно перестаёт быть контейнером всего приложения.

Первое правило для новых правок:

```txt
QObject parent может оставаться window, если это нужно для Qt lifetime.
Business dependency не должна доставаться через parent().
```

Например, если объекту нужны `app_context`, `ui_state_store` и команда runtime,
передавать их явно в конструктор. Не читать их позже из `self.parent()`.
