# State ownership

Этот документ фиксирует владение состоянием после чистки слоёв окна.

Главное правило:

```text
feature state хранит данные feature;
MainWindowStateStore хранит только короткое состояние, нужное общему UI.
```

`MainWindowStateStore` живёт в:

```text
src/app/state_store.py
```

Старые файлы не должны возвращаться:

```text
src/ui/state/main_window_state.py
src/ui/state/app_runtime_state.py
```

## MainWindowStateStore

| Поле | Writer | Readers | Решение |
| --- | --- | --- | --- |
| `launch_method` | `LaunchRuntimeService.build_initial_ui_state`, `LaunchRuntimeService.begin_start`, `LaunchRuntimeService.mark_autostart_pending`, `LaunchRuntimeService.bootstrap_probe` | runtime snapshot, tray, close flow, control pages | Оставить. Это короткая UI-сводка текущего способа запуска. |
| `launch_phase` | `LaunchRuntimeService` | control pages, tray, close flow, runtime facade | Оставить. Писать только через `LaunchRuntimeService`. |
| `launch_running` | `LaunchRuntimeService` | control pages, tray, close flow, runtime facade | Оставить. Это UI-сводка, не process tracking. |
| `launch_busy` / `launch_busy_text` | `LaunchRuntimeService.set_busy` | control pages | Оставить. Это состояние кнопок и загрузки UI. |
| `launch_last_error` | `LaunchRuntimeService` | control pages, runtime snapshot | Оставить. Это короткая ошибка для UI, не лог runtime. |
| `current_strategy_summary` | `presets.display_state` | control pages | Оставить. Текст готовит presets feature, UI только показывает. |
| `autostart_enabled` | `LaunchRuntimeService.build_initial_ui_state` из `settings.json` | program settings, tray/runtime snapshot | Оставить. Это короткий UI-флаг автозапуска GUI. |
| `subscription_is_premium` / `subscription_days_remaining` | `donater.subscription_ui` | Premium page, About page, Appearance page, title badge | Оставить только как UI-сводку. Подробности Premium живут в `donater.state.PremiumState`. |
| `garland_enabled` / `snowflakes_enabled` | `main.window_state_actions` | Appearance page | Оставить. Это состояние общей оболочки окна. |
| `window_opacity` | `main.window_state_actions` | Appearance page | Оставить. Это состояние общей оболочки окна. |
| `active_preset_revision` | `core.runtime.preset_runtime_coordinator` | control pages | Оставить. Это сигнал обновления UI после смены активного preset-а. |
| `preset_content_revision` | `core.runtime.preset_runtime_coordinator`, `RuntimeUiBridge` setup | page refresh flow | Оставить. Это счётчик изменения содержимого, не данные preset-а. |
| `preset_structure_revision` | presets UI subpage layer | user presets pages | Оставить временно как UI-сигнал структуры. Данные preset-ов не хранить в store. |
| `mode_revision` | `winws_runtime.runtime.method_switch_flow` | Zapret 2 control page | Оставить. Это сигнал пересинхронизации UI после смены режима. |

## Feature State

Эти состояния не должны копироваться целиком в `MainWindowStateStore`.

| Feature | State | Где живёт | Что можно класть в MainWindowStateStore |
| --- | --- | --- | --- |
| Runtime | public snapshot + private tracking state | `winws_runtime/state/launch_runtime_service.py` | Только `launch_*` UI-сводку. `pid`, expected process и счётчики проверок остаются внутри runtime. |
| Premium | `PremiumState` | `src/donater/state.py` | Только `subscription_is_premium` и `subscription_days_remaining` для глобального UI. Pairing, status, level, source, error остаются в Premium layer. |
| Presets/Profile | `PresetSelectionState`, profile payload/state | `src/presets/state.py`, `src/profile/state.py` | Только `current_strategy_summary` и revision-счётчики. Имена файлов, profile details и selected source path остаются в presets/profile. |
| DNS | `DnsState`, `DnsCommandResult` | `src/dns/state.py` | Ничего. DNS details нужны DNS-странице и DNS feature. |
| Hosts | `HostsState`, `HostsCommandResult` | `src/hosts/state.py` | Ничего. Hosts details нужны Hosts-странице и Hosts feature. |

## Writer Contract

Запись в `MainWindowStateStore` защищена в:

```text
src/app/architecture_checks.py
```

Проверка называется:

```text
check_ui_state_store_writer_ownership
```

Если новому коду нужно писать уже существующее поле из другого места, сначала
нужно изменить эту карту владения состоянием. Нельзя просто добавить второй
writer рядом.

## Reader Contract

Окно и страницы могут читать готовый snapshot или подписываться на нужные поля,
но не должны вычислять feature state сами.

Окно не хранит `window.app_runtime` и не держит публичный
`window.ui_state_store`. Действия оформления живут в `WindowStateActions`,
который создаёт `ApplicationController`.

Окно также не должно быть точкой доступа к feature-зависимостям. Для сборочных
мест используются маленькие порты:

```text
FeatureWindowDeps
  только то, что нужно feature assembly

WindowPageActions
  только действия, которые можно дать страницам

PostStartupHost
  только состояние старта, живость окна и навигация для поздних задач

TrayWindowPort
  только действия окна, нужные системному трею
```

Запрещены старые параллельные атрибуты вида:

```text
window.app_runtime_state
self.ui_state_store
window.ui_state_store
self._ui_state_store
self._app_runtime_state
```

Если store нужен странице, он передаётся явно через deps/page composition.
Страница не должна брать его через `self.window()`.

```text
WindowStateActions -> оформление окна и короткий UI-state
page deps          -> страницы
```

Нормальный путь:

```text
feature/service
  -> пишет свой state или короткую UI-сводку

MainWindowStateStore
  -> хранит только UI-срез

страница или оболочка окна
  -> читает готовое значение
  -> обновляет виджеты
```

Ненормальный путь:

```text
страница/окно
  -> читает внутренние сервисы feature
  -> сама собирает состояние
  -> пишет в общий store
```
