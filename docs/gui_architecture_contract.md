# GUI Architecture Contract

Дата фиксации: 2026-04-10

Этот документ описывает не пожелания, а архитектурный контракт GUI, который надо поддерживать при следующих изменениях. Если код начинает делать иначе, это считается архитектурным нарушением, а не локальной особенностью страницы.

## Direct preset flow

- `direct_zapret1` использует выбранный source preset как единственный источник истины.
- `direct_zapret2` использует выбранный source preset как единственный источник истины.
- Канонический путь выбора direct-пресета: `PresetSelectionService` -> `DirectFlowCoordinator` -> source preset файл.
- `runtime/.../launch.txt` не является источником истины для выбора direct-пресета.
- `runtime/.../launch.txt` может быть только производным runtime-артефактом для запуска уже выбранного пресета.
- Новые direct-изменения не должны читать или писать `legacy_registry_launch` как основной direct-контракт.
- Новые direct-изменения не должны вводить fallback-ветки вида "если новый путь не сработал, возьми legacy path".
- Direct runtime switch не должен использовать `selections dict` как источник выбора активного пресета.

## Global state contract

- `MainWindowStateStore` является каноническим источником глобального UI-состояния окна.
- Глобальное UI-состояние должно обновляться через методы store или через сервисы, которые пишут в store.
- Прямые присваивания глобальных полей окна вне store считаются нарушением контракта.
- `AppRuntimeState` и `DpiRuntimeService` являются service-layer обёртками над тем же самым глобальным store, а не отдельными источниками истины.

## Page responsibility contract

- Страница не должна быть владельцем бизнес-логики.
- Страница не должна быть владельцем файловой логики.
- Страница не должна быть владельцем runtime-логики.
- Страница может владеть только представлением, подписками на UI-состояние, локальными визуальными контролами и делегированием действий в controller/service слой.
- Тяжёлая загрузка страницы должна идти через lifecycle `BasePage`, а не через самодельные локальные схемы.
- Общий lifecycle страниц должен идти через `BasePage`.
- Отмена устаревших загрузок страницы должна идти через `PageLoadController`.

## Direct vs orchestra boundary

- Direct-страницы не должны содержать orchestra-ветки.
- Orchestra-страницы не должны наследоваться от direct-страниц.
- Orchestra routing не должен открывать direct-страницы по fallback.
- Shared UI-слой не должен знать `launch method`, если это не часть отдельной router/navigation policy.
- Если для orchestra нужен похожий экран, должен существовать orchestra-only wrapper или отдельная orchestra-only страница, а не наследование direct UI-класса.

## Composition root contract

- Глобальные зависимости приложения должны собираться в явной точке composition root.
- `AppContext` является контейнером для глобальных GUI-зависимостей уровня окна.
- `core/services.py` на переходном этапе допустим только как bridge для старых use-site'ов.
- Новые архитектурные изменения должны идти через `AppContext`, а не расширять service-locator слой.

## Build/runtime contract

- GUI runtime должен брать `PREMIUM_API_BASE_URL` только из канонического build-контура.
- Канонический путь для GUI runtime config: `build_release_gui.py` -> `public_zapretgui/src/config/_build_secrets.py` -> runtime import.
- Нельзя восстанавливать старые значения из предыдущего `_build_secrets.py`.
- Нельзя возвращать repo-based `.env` в build/runtime контур GUI.

