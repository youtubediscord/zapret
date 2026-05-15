# Контракт Запуска

Этот документ фиксирует текущий контракт запуска GUI после разгрузки первого старта.

## Основные Роли

`window_bootstrap_for(...)` создаёт главное окно и регистрирует окно как активное.

`WindowStartupMixin` создаёт `AppRuntime`, то есть тонкую сборку путей,
состояния и feature-входов приложения. `AppContext` в рабочем потоке больше
нет.

`WindowStartupMixin` отвечает за жизненный цикл окна во время старта:

- показать окно как можно раньше;
- собрать основной UI после первого показа;
- создать стартовые объекты через `startup_bootstrap_for(...)`;
- запустить `StartupCoordinator`;
- отметить метрики `StartupInteractive`, `StartupCoreReady`, `StartupPostInit`.

`StartupCoordinator` отвечает только за порядок запуска:

- минимальный интерактивный контур;
- основной стартовый контур;
- постановка post-init задач;
- постановка DPI autostart.

`post_startup_*.py` отвечают за поздние задачи после `StartupPostInit`: проверки, DNS, списки, Telegram Proxy, tray для обычного запуска, update-check и диагностику.

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
