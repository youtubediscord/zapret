# GUI Inventory

Дата аудита: 2026-04-10

Документ фиксирует текущее состояние GUI перед дальнейшим архитектурным разрезанием. Это не целевая схема, а инвентарь фактических точек входа и связей.

## Точки входа GUI из `main.py`

- Модульный bootstrap: ранняя настройка рабочей директории, crash handler, preload, создание `QApplication`.
- `main()`:
  - проверка специальных аргументов;
  - проверка прав администратора;
  - single-instance и IPC;
  - настройка темы и accent color;
  - сборка `AppContext`;
  - установка `AppContext` в переходный `core/services.py`;
  - создание `LupiDPIApp`;
  - применение window background;
  - запуск event loop.
- `LupiDPIApp.__init__()`:
  - получает `AppContext`;
  - сохраняет `ui_state_store`, `app_runtime_state`, `dpi_runtime_service`;
  - создаёт window-level controllers;
  - показывает окно;
  - запускает `_deferred_init()`.
- `_deferred_init()`:
  - строит базовый UI через `build_ui()`.
- `_continue_deferred_init()`:
  - создаёт startup managers;
  - запускает `InitializationManager.run_async_init()`.

## Места создания глобальных сервисов

- `public_zapretgui/src/app_context.py`:
  - `MainWindowStateStore`;
  - `AppRuntimeState`;
  - `DpiRuntimeService`;
  - `DirectFlowCoordinator`;
  - `PresetSelectionService`;
  - `PresetRepository`;
  - `DirectUiSnapshotService`;
  - `ProgramSettingsRuntimeService`;
  - factory для `UserPresetsRuntimeService`;
  - factory для `PresetRuntimeCoordinator`.
- `public_zapretgui/src/core/services.py`:
  - временный bridge к `AppContext`;
  - fallback service-locator для не переведённых use-site'ов.

## Места создания менеджеров запуска

- `public_zapretgui/src/main.py::_continue_deferred_init()`:
  - `InitializationManager(self)`;
  - `SubscriptionManager(self)`;
  - `ProcessMonitorManager(self)`;
  - `UIManager(self)`.
- `public_zapretgui/src/managers/initialization_manager.py`:
  - внутри phase init создаётся `DPIController(self.app)`;
  - там же поднимаются дополнительные служебные менеджеры и фоновые проверки.

## Места создания runtime-сервисов

- `public_zapretgui/src/app_context.py`:
  - `AppRuntimeState`;
  - `DpiRuntimeService`;
  - `DirectUiSnapshotService`;
  - `ProgramSettingsRuntimeService`;
  - factory `UserPresetsRuntimeService`;
  - factory `PresetRuntimeCoordinator`.

## Места создания page controllers

- `ui/pages/zapret2/direct_control_page.py`: `Zapret2DirectControlPageController`.
- `ui/pages/zapret2/strategy_detail_page.py`: `StrategyDetailPageController`.
- `ui/pages/zapret2/user_presets_page.py`: `DirectUserPresetsPageController`.
- `ui/pages/zapret1/user_presets_page.py`: `DirectUserPresetsPageController`.
- `ui/pages/orchestra_zapret2/user_presets_page.py`: `OrchestraZapret2UserPresetsPageController`.
- `ui/pages/network_page.py`: `NetworkPageController`.
- `ui/pages/blockcheck_page.py`: `BlockcheckPageController`.
- `ui/pages/strategy_scan_page.py`: `StrategyScanPageController`.
- `ui/pages/hosts_page.py`: `HostsPageController`.
- `ui/pages/hostlist_page.py`: `HostlistPageController`.
- `ui/pages/custom_domains_page.py`: `HostlistPageController`.
- `ui/pages/custom_ipset_page.py`: `HostlistPageController`.
- `ui/pages/netrogat_page.py`: `HostlistPageController`.
- `ui/pages/orchestra/orchestra_page.py`: `OrchestraPageController`.
- `ui/pages/telegram_proxy_page.py`:
  - `TelegramProxySettingsController`;
  - `TelegramProxyPageActionsController`;
  - `TelegramProxyRuntimeController`;
  - `TelegramProxyDiagnosticsController`.
- `ui/pages/servers_page.py`:
  - `UpdatePageController`;
  - `UpdatePageViewController`.

## Места прямого изменения состояния окна без store

Найденные прямые window-level изменения:

- `main.py`: прямое `setWindowTitle(...)` через `UIManager`, `show_subscription_dialog()`, декорации окна, видимость окна.
- `ui/main_window_display.py`: есть переходный слой, который частично пишет в store, но часть window behavior меняет напрямую.
- `ui/main_window.py`: навигация и переключение stacked widget идут мимо store, что нормально для navigation shell, но это надо отделять от глобального UI-state.

## Места чтения состояния окна через store

- Страницы с `bind_ui_state_store()` и `store.subscribe(...)`:
  - `ui/pages/control_page.py`;
  - `ui/pages/autostart_page.py`;
  - `ui/pages/appearance_page.py`;
  - `ui/pages/about_page.py`;
  - `ui/pages/premium_page.py`;
  - `ui/pages/zapret2/direct_control_page.py`;
  - `ui/pages/zapret2/direct_zapret2_page.py`;
  - `ui/pages/zapret2/strategy_detail_page.py`;
  - `ui/pages/zapret2/user_presets_page.py`;
  - `ui/pages/zapret2_orchestra_strategies_page.py`;
  - `ui/pages/zapret1/direct_control_page.py`;
  - `ui/pages/zapret1/direct_zapret1_page.py`;
  - `ui/pages/zapret1/strategy_detail_page_v1.py`;
  - `ui/pages/zapret1/user_presets_page.py`.

## Места ручного управления навигацией

- `ui/main_window_navigation.py`: отдельные функции маршрутизации и переходов.
- `ui/main_window_pages.py`: прямые connect'ы сигналов страниц к `window.show_page(...)`.
- `ui/main_window.py`: `show_page()`, `_on_strategy_detail_back()`, служебные wrapper-методы навигации.

## Hidden pages

Текущая hidden-регистрация в `ui/main_window_navigation_build.py`:

- `PageName.ZAPRET2_DIRECT`
- `PageName.ZAPRET2_ORCHESTRA`
- `PageName.ZAPRET2_USER_PRESETS`
- `PageName.ZAPRET2_ORCHESTRA_USER_PRESETS`
- `PageName.ZAPRET2_STRATEGY_DETAIL`
- `PageName.ZAPRET2_PRESET_DETAIL`
- `PageName.ZAPRET2_ORCHESTRA_STRATEGY_DETAIL`
- `PageName.ZAPRET2_ORCHESTRA_PRESET_DETAIL`
- `PageName.BLOBS`
- `PageName.ZAPRET1_DIRECT`
- `PageName.ZAPRET1_USER_PRESETS`
- `PageName.ZAPRET1_STRATEGY_DETAIL`
- `PageName.ZAPRET1_PRESET_DETAIL`

## Direct use-site'ы `legacy_registry_launch`

По состоянию аудита direct/общие use-site'ы видны в:

- `strategy_menu/__init__.py`
- `dpi/dpi_settings_page_controller.py`
- `launcher_common/builder_factory.py`
- `launcher_common/blobs.py`
- `managers/initialization_manager.py`
- `ui/control_page_controller.py`
- `ui/main_window_display.py`
- `autostart/autostart_direct.py`

Обновление после cutover:

- direct use-site'ы `legacy_registry_launch.selection_store.py` в основном GUI/runtime scope удалены;
- direct use-site'ы `legacy_registry_launch.strategies_registry.py` в основном GUI/runtime scope удалены;
- orchestra strategies page переведена на `preset_orchestra_zapret2` и `catalog.py`;
- остаточный `legacy_registry_launch` в текущем основном scope живёт только в orchestra-only bridge:
  - `launcher_common/orchestra_legacy_bridge.py`

## Orchestra use-site'ы direct page-классов

Обновление после wrapper-cutover:

- `ui/pages/orchestra_zapret2/direct_control_page.py` больше не наследуется от direct-страницы, а использует композицию через `WrappedInnerPage`
- `ui/pages/orchestra_zapret2/user_presets_page.py` больше не наследуется от direct-страницы, а использует композицию через `WrappedInnerPage`
- `ui/pages/orchestra_zapret2/strategy_detail_page.py` больше не наследуется от direct-страницы, а использует композицию через `WrappedInnerPage`

## Use-site'ы `core/services.py`

Ключевые use-site'ы на момент аудита:

- `main.py`
- `dpi/zapret2_core_restart.py`
- `managers/initialization_manager.py`
- `managers/dpi_manager.py`
- `dpi/dpi_controller.py`
- `dpi/direct_runtime_apply_policy.py`
- `strategy_checker.py`
- `core/runtime/preset_runtime_coordinator.py`
- `core/runtime/direct_ui_snapshot_service.py`
- `core/presets/runtime_store.py`
- `core/presets/direct_facade_backend.py`
- `ui/main_window_mode_switch.py`
- `ui/pages/zapret2/direct_control_page.py`
- `ui/pages/zapret2/strategy_detail_page.py`
- `ui/pages/zapret2/direct_control_page_controller.py`
- `ui/pages/direct_user_presets_page_controller.py`
- `ui/pages/zapret1/direct_control_page.py`
- `ui/pages/zapret1/strategy_detail_page_v1.py`
- `ui/pages/preset_subpage_base.py`
- `autostart/autostart_direct.py`

## Текущее архитектурное наблюдение

- В проекте уже появился `MainWindowStateStore` и page lifecycle через `BasePage`.
- При этом navigation policy, реестр страниц и route policy всё ещё раздроблены по нескольким файлам.
- Direct flow уже во многом переехал на source preset, но рядом ещё живут legacy use-site'ы `legacy_registry_launch`.
- Orchestra boundary пока ещё нарушена наследованием orchestra-страниц от direct-страниц.
