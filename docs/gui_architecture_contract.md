# GUI Architecture Contract

Дата фиксации: 2026-04-10

Этот документ описывает не пожелания, а архитектурный контракт GUI, который надо поддерживать при следующих изменениях. Если код начинает делать иначе, это считается архитектурным нарушением, а не локальной особенностью страницы.

## Direct preset flow

- `direct_zapret1` использует выбранный source preset как единственный источник истины.
- `direct_zapret2` использует выбранный source preset как единственный источник истины.
- Канонический путь выбора direct-пресета: `PresetSelectionService` -> `DirectFlowCoordinator` -> source preset файл.
- Канонический корень пресетов: `presets/` рядом с программой.
- Пользовательские direct-пресеты лежат только в `presets/presets_v1` и `presets/presets_v2`.
- Встроенные direct-пресеты лежат только в `presets/presets_v1_builtin` и `presets/presets_v2_builtin`.
- Установщик обязан заранее раскладывать built-in пресеты по этим папкам.
- GUI runtime не должен автокопировать built-in пресеты из Python-кода на первом запуске.
- `runtime/.../launch.txt` не является источником истины для выбора direct-пресета.
- `runtime/.../launch.txt` может быть только производным runtime-артефактом для запуска уже выбранного пресета.
- Новые direct-изменения не должны читать или писать `legacy_registry_launch` как основной direct-контракт.
- Новые direct-изменения не должны вводить fallback-ветки вида "если новый путь не сработал, возьми legacy path".
- Direct runtime switch не должен использовать `selections dict` как источник выбора активного пресета.

## Lists and catalogs contract

- Канонический корень списков: `lists/` рядом с программой.
- Для управляемых GUI-списков системная база лежит только в `lists/base/<name>.txt`.
- Пользовательские правки лежат только в `lists/user/<name>.txt`.
- Итоговый рабочий файл для движка лежит только в `lists/<name>.txt`.
- Установщик обязан заранее раскладывать системную базу в `lists/base`.
- GUI не должен перезаписывать системную базу списков на каждом запуске.
- Для `direct_preset/catalogs` и `direct_preset/metadata` установщик обязан заранее раскладывать файлы рядом с программой.
- GUI runtime не должен копировать `direct_preset/catalogs` из package-layer в рабочую папку на первом запуске.

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
- Серверный Premium backend хранится отдельно от GUI в репозитории `G:\Privacy\zapret-premium-api`.
- `ZapretGUI` не содержит внутри себя Premium API backend и работает с ним только по `PREMIUM_API_BASE_URL`.
- Нельзя восстанавливать старые значения из предыдущего `_build_secrets.py`.
- Нельзя возвращать repo-based `.env` в build/runtime контур GUI.
