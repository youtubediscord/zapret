# GUI Fluent Cutover Plan

Дата фиксации: 2026-04-12

Этот документ описывает не абстрактные идеи, а целевой план полной замены текущего `main_window*` orchestration-слоя на новый fluent-first каркас GUI.

Документ нужен как передаваемый контекст для следующего ИИ или следующей сессии. Его задача:

- зафиксировать, что именно мы считаем проблемой;
- зафиксировать, что именно мы сохраняем;
- зафиксировать, что именно подлежит полному удалению;
- дать один непротиворечивый план cutover без fallback и без второго источника истины.

## 1. Зачем вообще нужен этот cutover

Проблема проекта не в том, что GUI "не на Fluent". Наоборот, проект уже глубоко использует `qfluentwidgets`:

- главное окно уже построено на `FluentWindow`;
- многие страницы уже используют `InfoBar`, `MessageBox`, `BreadcrumbBar`, `SegmentedWidget` и другие fluent-компоненты;
- визуальный слой уже частично стандартизирован.

Главная проблема в другом:

- orchestration GUI держится на старом центре `main_window*`;
- создание страниц, навигация, переходы, режимные ограничения и часть runtime-feedback до сих пор склеены через этот слой;
- страницы местами берут зависимости через `self.window()`;
- runtime местами знает про `main_window`;
- часть контрактов между страницами и окном неявная.

Проще говоря:

визуально проект уже близок к Fluent,
но архитектурно он всё ещё завязан на большой glue-центр.

## 2. Что мы хотим получить в конце

Целевое состояние должно читаться одной фразой:

`startup создаёт fluent shell, composition root собирает UI-контроллеры, navigation schema решает какие страницы разрешены и видимы в текущем режиме, page host создаёт и показывает страницы, workflow-слой управляет переходами и сценариями, runtime bridge обновляет UI без знания о main_window.`

Это означает:

- один источник истины для навигации и режимной видимости;
- один источник истины для глобального UI-состояния;
- один рабочий путь runtime -> UI;
- один рабочий путь page lifecycle;
- физическое удаление старого `main_window*` слоя после cutover.

## 3. Почему этот план считается корректным

Перед фиксацией план был перепроверен на логические ошибки и неоднозначности. Ниже перечислены ключевые решения, которые делают его архитектурно честным, а не "спасением старого слоя под новым названием".

### 3.1 Мы не строим второй параллельный shell

В проекте уже есть хороший fluent-shell:

- `src/ui/fluent_app_window.py`
- `src/main/window.py`
- `src/main/window_startup.py`
- `src/main/window_lifecycle.py`
- `src/main/window_state_sync.py`

Значит новый план не должен создавать второй независимый shell рядом с ними.

Правильный путь:

- сохранить `ZapretFluentWindow` как основу окна;
- сохранить startup/lifecycle/state-sync mixin-слой, если он остаётся архитектурно чистым;
- убрать только `MainWindowUI` и весь старый `main_window*` orchestration;
- новый UI-root подключить в существующий startup-контур.

Иначе появятся два shell-слоя, и миграция сама внесёт новый дубликат архитектуры.

### 3.2 Мы не держим два navigation schema одновременно

Сейчас `src/ui/router.py` уже содержит полезные data-oriented элементы:

- описание страниц;
- `launch_modes`;
- `is_hidden`;
- `is_top_level`;
- `breadcrumb_parent`;
- `sidebar_group`.

Это хороший фундамент, поэтому правильный путь для этого проекта такой:

- создать новый канонический schema-модуль;
- в одном срезе перенести туда данные и правила, которые действительно относятся к navigation/schema;
- сразу погасить старый `router.py` путь как активный truth source.

Если для безопасного перехода понадобится краткоживущий compatibility layer, он должен исчезнуть в cutover.
В финале активный navigation truth source остаётся один: новый schema-модуль.

### 3.3 Мы не переписываем все страницы "на всякий случай"

Этот cutover не про массовое переписывание всех UI-страниц с нуля.

Правильный путь:

- сохранять страницы, если у них нормальная визуальная и локальная логика;
- переписывать только те страницы, которые реально слишком завязаны на `window()` и старый orchestration;
- не трогать здоровую fluent-разметку только ради "полного ощущения новой архитектуры".

Иначе миграция станет слишком широкой и потеряет управляемость.

### 3.4 Мы не пытаемся "обернуть" старый main_window вместо его удаления

Запрещённый путь:

- оставить `main_window.py`;
- навесить поверх него новые контроллеры;
- объявить это новой архитектурой.

Это не cutover, а консервация старого центра.

Правильный путь:

- новый каркас создаётся рядом;
- use-site'ы переводятся на него;
- после покрытия сценариев старый `main_window*` слой физически удаляется.

### 3.5 Мы учитываем режимную видимость страниц как архитектурный контракт

Это не косметика и не "потом доделаем".

Новый каркас обязан уметь отвечать на три разных вопроса:

- страница вообще существует?
- страница разрешена в текущем режиме?
- страница должна быть видима в sidebar?

Если это не встроено в центральную navigation policy, архитектура снова расползётся в условные ветки по окну и страницам.

## 4. Что сохраняем как основу

Следующие части считаются хорошим фундаментом и не подлежат автоматическому удалению только потому, что они "старые":

### 4.1 Fluent shell

- `src/ui/fluent_app_window.py`

Это уже корректная основа fluent-окна.

### 4.2 Startup / lifecycle / state-sync слой окна

- `src/main/window.py`
- `src/main/window_startup.py`
- `src/main/window_lifecycle.py`
- `src/main/window_state_sync.py`

Эти файлы надо не сломать, а переподключить к новому UI-root.

### 4.3 AppContext

- `src/app_context.py`

Это канонический контейнер глобальных GUI-зависимостей уровня окна.

### 4.4 MainWindowStateStore

- `src/app_state/main_window_state.py`

Это канонический источник глобального UI-состояния окна.

### 4.5 Fluent widgets как обязательный UI-standard

Для нового каркаса сохраняется и усиливается правило:

- использовать только штатные fluent-паттерны и fluent-виджеты, если библиотека уже закрывает сценарий;
- не изобретать самодельные pseudo-fluent контролы;
- все detail/subpage workflow делать через fluent breadcrumbs и штатные паттерны библиотеки.

## 5. Что считается legacy и должно быть удалено

После cutover под физическое удаление попадает весь старый orchestration-layer:

- `src/ui/main_window.py`
- `src/ui/main_window_pages.py`
- `src/ui/main_window_navigation.py`
- `src/ui/main_window_navigation_build.py`
- `src/ui/main_window_mode_switch.py`
- `src/ui/main_window_bootstrap_flow.py`
- `src/ui/main_window_page_dispatch.py`
- `src/ui/main_window_signals.py`
- остальные `main_window_*`, если они останутся только промежуточными glue-модулями.

Вместе с ними должны уйти:

- runtime -> `main_window` прямые вызовы;
- implicit-контракты страниц через `hasattr(...)`;
- строковые dispatch-вызовы страниц как основной механизм orchestration;
- service-locator доступ через `self.window()` там, где это не просто родитель окна, а канал к глобальным сервисам.

## 6. Архитектурные инварианты нового каркаса

Это жёсткие правила. Если новая реализация их нарушает, это считается ошибкой архитектуры, а не допустимой вариацией.

### 6.1 Один shell

GUI опирается на один fluent shell, а не на несколько оболочек окна.

### 6.2 Один navigation truth source

В проекте должен быть один канонический слой, который знает:

- какие страницы существуют;
- какие из них root;
- какие hidden/detail;
- какие разрешены для `direct_zapret2`, `direct_zapret1`, `orchestra`;
- какие видимы в sidebar;
- какие участвуют в sidebar search;
- какая breadcrumb-цепочка у каждой страницы.

### 6.3 Один page lifecycle path

Страницы создаются только через page factory / page host, а не руками из разных orchestration helper'ов.

### 6.4 Один runtime -> UI path

Runtime не знает про `main_window`, `FluentWindow` и приватные UI-методы.
Он знает только `runtime_ui_bridge`.

### 6.5 Один global UI state source

Глобальное состояние GUI живёт только в `MainWindowStateStore` и сервисах над ним.

### 6.6 Страница не владеет бизнес-логикой

Страница отвечает только за:

- fluent UI;
- локальные визуальные состояния;
- подписку на store;
- делегирование действий в workflow/service слой.

### 6.7 Один page lifecycle contract

Новый каркас обязан сохранить и формализовать уже существующий page lifecycle contract, а не потерять его при переносе orchestration.

Обязательные элементы этого контракта:

- страницы продолжают жить на базе `BasePage`, если нет веской причины уходить с него;
- тяжёлая загрузка и отмена устаревших загрузок идут через общий lifecycle, а не через локальные самодельные схемы;
- `PageLoadController` и связанная логика отмены устаревших загрузок не должны быть потеряны;
- `bind_ui_state_store(...)` остаётся частью page integration contract;
- `cleanup()` остаётся обязательным cleanup-hook для страницы и должен продолжать вызываться window/lifecycle слоем.

Если новая архитектура не знает, как:

- страница получает store;
- страница чистит свои ресурсы;
- страница отменяет устаревшие загрузки;

то это ещё не законченный replacement orchestration, а только новая обёртка вокруг старого поведения.

### 6.8 Sidebar search — часть navigation architecture

Sidebar search не является второстепенной фичей старого `main_window_navigation_build.py`.
Это часть navigation contract.

Новый каркас обязан сохранить:

- фильтрацию поисковых результатов по текущему режиму;
- связь поиска с каноническим navigation/schema truth-source;
- открытие найденной страницы через новый page host / workflow путь;
- исключение из поисковой выдачи страниц, недоступных в текущем режиме.

То есть sidebar search должен мигрировать вместе с navigation layer, а не "потом отдельно".

### 6.9 Нельзя создавать нового god object под именем `ui_root` или `ui_workflows`

Новая архитектура считается неуспешной, если вместо `main_window.py` в проекте появится другой скрытый центр, который снова знает "обо всём сразу".

Особенно опасные кандидаты:

- `ui_root`
- `ui_workflows`
- `page_host`

Правильные границы такие:

- `ui_root` только собирает зависимости и соединяет слои;
- `navigation_controller` владеет только sidebar/navigation presentation;
- `page_host` владеет только lifecycle и показом страниц;
- workflow-слой владеет только пользовательскими сценариями и переходами;
- `runtime_ui_bridge` владеет только runtime -> UI feedback.

Недопустимо:

- чтобы `ui_root` сам решал режимные переходы, detail routing, runtime feedback и page lifecycle;
- чтобы `page_host` сам решал продуктовые сценарии, а не только open/show/gating;
- чтобы один огромный `ui_workflows.py` собрал весь direct/orchestra/about/lists/system flow в одном файле.

То есть новый каркас должен быть действительно многомодульным, а не просто переименованным `main_window`.

## 7. Новый каркас: состав модулей

Ниже описан рекомендуемый состав нового UI-слоя. Это не означает, что все модули обязаны быть именно с этими именами, но их роли должны существовать как отдельные сущности.

### 7.1 `ui_root`

Роль:

- центральная точка сборки UI;
- получает `app_context`;
- создаёт и соединяет новый каркас;
- не содержит старый `main_window*` glue.

Важно:

`ui_root` — это composition root, а не controller всего GUI.
Он не должен содержать:

- route decisions;
- page open logic;
- mode switch workflow;
- runtime reaction logic;
- sidebar filtering logic.

Если в `ui_root` начинает стекаться такая логика, это новый god object.

### 7.2 `navigation schema`

Роль:

- каноническое описание страниц;
- mode gating;
- root/hidden/detail classification;
- breadcrumbs;
- sidebar/search visibility.

Для этого проекта каноническим владельцем этого слоя должен стать новый schema-модуль.
Данные из `src/ui/router.py` должны быть перенесены туда в один срез, после чего старый router-path перестаёт быть активным truth source.

### 7.2.1 Прямой путь и имя нового schema-модуля

Для этой миграции прямой целевой путь фиксируется так:

- `src/ui/navigation/__init__.py`
- `src/ui/navigation/schema.py`

Это и есть новый канонический navigation truth source.

Если для типизации или dataclass-моделей позже понадобится дополнительный файл, допустим только один аккуратный вариант:

- `src/ui/navigation/types.py`

Но на старте миграции базовый целевой слой считается таким:

- `schema.py` — data + query helpers
- `navigation_controller.py` — fluent sidebar/controller logic

Важно:

- `schema.py` не должен содержать workflow-логику;
- `schema.py` не должен содержать page creation;
- `schema.py` не должен знать про concrete widgets;
- `schema.py` должен быть чистым data/query слоем.

### 7.3 `navigation_controller`

Роль:

- строит fluent sidebar;
- знает только про навигацию;
- скрывает лишние страницы по режиму;
- не управляет runtime и не создаёт страницы.

### 7.4 `page_factory`

Роль:

- создаёт страницы;
- передаёт им зависимости явно;
- перестаёт рассчитывать на `self.window().app_context`.

### 7.5 `page_host`

Роль:

- lazy loading;
- кэш экземпляров страниц;
- открытие root и hidden страниц;
- запрет открытия страниц, не разрешённых текущему режиму.

### 7.6 `ui_workflows`

Роль:

- сценарии навигации и переходов;
- detail/preset workflow;
- back/root behavior;
- реакция на page signals;
- смена режима как UI-сценарий, а не как хаотичная смесь runtime и menu-логики.

Архитектурное уточнение:

`ui_workflows` должен пониматься не как один обязательный большой файл, а как workflow-layer.

Предпочтительная структура:

- `src/ui/workflows/__init__.py`
- `src/ui/workflows/common.py`
- `src/ui/workflows/direct_z2.py`
- `src/ui/workflows/direct_z1.py`
- `src/ui/workflows/orchestra.py`
- `src/ui/workflows/about.py`
- `src/ui/workflows/lists.py`

Если нужен единый фасад для wiring, он допустим только как тонкий aggregator, а не как новый центр всей логики.

### 7.7 `runtime_ui_bridge`

Роль:

- принимает runtime feedback;
- обновляет UI через store и разрешённые UI-hook'и;
- полностью разрывает прямую связь runtime -> `main_window`.

### 7.8 `page_contracts`

Роль:

- явные интерфейсы страниц;
- описывают, какие сигналы и методы реально допустимы;
- убирают implicit-контракты через `hasattr(...)` и строковые имена.

## 8. Режимы и видимость страниц

Это одна из ключевых частей нового контракта.

Для каждой страницы должно храниться как минимум:

- `mode_scope`
- `entry_kind`
- `sidebar_visible`
- `search_visible`
- `breadcrumb_parent`
- `allow_direct_open`

### 8.1 Что означают эти поля

`mode_scope`

- в каких режимах страница вообще допустима.

`entry_kind`

- root
- hidden
- detail
- internal-subpage

`sidebar_visible`

- должна ли страница быть видима в боковой панели.

`search_visible`

- должна ли страница участвовать в sidebar search.

`allow_direct_open`

- можно ли открыть страницу напрямую, или она должна открываться только через workflow.

### 8.2 Жёсткое правило по режимам

Если режим `direct_zapret1`, то `zapret2`-страницы:

- не должны быть видимы в sidebar;
- не должны быть доступны как допустимые root-entry;
- не должны открываться напрямую как легальная hidden-page навигация.

Аналогично:

- `direct_zapret2` не должен видеть и открывать `zapret1` и `orchestra` ветки;
- `orchestra` не должен видеть и открывать `zapret1` и `zapret2` ветки.

### 8.3 Common pages

Общие страницы могут существовать во всех режимах, но это должно быть явно задано в schema, а не получаться "по умолчанию случайно".

## 9. Рекомендуемая стратегия миграции

Пользовательский выбор для этого проекта:

- новый каркас создаётся рядом;
- legacy не режется по кускам в середине работы;
- когда новый путь покрывает сценарии, делается один отдельный cutover-коммит на удаление legacy.

Это правильная стратегия, потому что она:

- не заставляет держать fallback-ветки;
- не плодит две наполовину живые архитектуры надолго;
- позволяет построить новый путь честно, а потом удалить старый слой одним срезом.

## 10. Последовательность работ

Ниже порядок не случайный. Он выбран так, чтобы не плодить второй источник истины и не зависнуть в гибридной архитектуре.

### Этап 0. Зафиксировать два обязательных артефакта перед кодом

До начала реальной реализации должны быть явно зафиксированы два артефакта:

- `window adapter contract`
- `navigation contract matrix`

Текущая рабочая версия матрицы зафиксирована отдельно в:

- `docs/gui_navigation_contract_matrix.md`

Без них новый каркас слишком легко снова начнёт расползаться:

- часть логики останется в window-level helper'ах;
- часть логики уйдёт в schema;
- часть — в page host;
- часть — обратно в страницы.

Эти два артефакта нужны не как бюрократия, а как способ удержать одну понятную архитектуру.

### Этап 1. Зафиксировать канонический navigation schema

Сделать один data-driven слой, который описывает:

- страницы;
- режимы;
- root/hidden/detail;
- breadcrumbs;
- sidebar/search visibility;
- допустимость прямого открытия.

Важно:

итоговым truth-source уже выбран новый schema-модуль.
На этом этапе данные из `src/ui/router.py` нужно не дублировать, а перенести в один срез с немедленным гашением старого router-path как источника истины.

### Этап 1.1. First slice migration map из `router.py`

Первый срез переноса из `src/ui/router.py` в `src/ui/navigation/schema.py` должен быть максимально честным и ограниченным.

В новый schema-модуль в первом срезе должны переехать именно те вещи, которые относятся к schema/data/query слою.

#### Переезжает в первый срез

- dataclass спецификации страницы:
  - текущий `PageRouteSpec`
  - при желании с переименованием в что-то вроде `PageSchemaSpec`
- mode constants:
  - `_COMMON`
  - `_Z2_DIRECT`
  - `_Z1_DIRECT`
  - `_ORCHESTRA`
- основной registry страниц:
  - `PAGE_ROUTE_SPECS`
- порядок sidebar groups:
  - `SIDEBAR_GROUP_ORDER`
- entry pages по режиму:
  - `MODE_ENTRY_PAGES`
- базовые read-only query helpers:
  - `get_page_spec(...)`
  - `iter_page_specs()`
  - `normalize_launch_method_for_ui(...)`
  - `_matches_method(...)`
  - `_is_sidebar_visible_in_method(...)`
  - `get_page_route_key(...)`
  - `get_mode_entry_page(...)`
  - `get_eager_page_names_for_method(...)`
  - `get_sidebar_pages_for_method(...)`
  - `get_hidden_pages_for_method(...)`
  - `get_breadcrumb_chain(...)`
  - `get_mode_gated_nav_pages()`
  - `get_nav_visibility(...)`
  - `get_sidebar_search_pages_for_method(...)`

#### Не должно переезжать в первый срез как часть schema

Следующие вещи не должны смешиваться с новым schema-layer, если они содержат не data/query, а product/workflow semantics:

- page creation logic;
- fluent sidebar build logic;
- signal wiring;
- mode switch orchestration;
- runtime feedback wiring;
- page show/open side effects;
- search UI popup behavior;
- page method dispatch по строкам.

#### Что делать с оставшимся `router.py` в том же срезе

После переноса в первый срез допустимы только два состояния:

1. `router.py` удалён, а use-site'ы сразу переведены на `ui.navigation.schema`
2. `router.py` остаётся временным тонким compatibility re-export без собственной логики

Недопустимое состояние:

- `router.py` и `schema.py` одновременно содержат живые копии одних и тех же page specs и query правил.

### Этап 1.2. Что пока не переносится из соседних модулей

Чтобы не расползти scope первого среза, следующие вещи на старте остаются вне schema-модуля:

- workflow-resolve helpers из `navigation_targets.py`, если они ещё нужны переходному коду;
- concrete sidebar/search widget behavior из legacy navigation-build слоя;
- product-specific back/root сценарии, которые должны потом переехать в `ui_workflows`, а не в schema.

Это важно, чтобы новый `schema.py` не стал сразу новой свалкой всей navigation-логики.

### Этап 2. Сделать `page_factory`

Новый factory должен:

- создавать страницы;
- передавать зависимости явно;
- уметь оборачивать старые страницы без возврата к `window()` как к service-locator.

### Этап 3. Сделать `page_host`

Новый host должен:

- делать lazy loading;
- хранить экземпляры страниц;
- показывать текущую страницу;
- уметь открывать hidden/detail pages;
- проверять mode gating до показа страницы.

### Этап 4. Сделать `navigation_controller`

Новый navigation controller должен:

- строить fluent sidebar по schema;
- скрывать лишние root pages для текущего режима;
- уметь обновляться при смене режима;
- не содержать бизнес-логики direct/orchestra.

### Этап 5. Сделать `ui_workflows`

Вынести туда:

- detail page open;
- preset detail open;
- back/root routes;
- page signal handling;
- UI-side часть mode switch workflow.

### Этап 6. Сделать `runtime_ui_bridge`

Перевести runtime feedback из прямых main_window-вызовов на bridge.

Это касается как минимум use-site'ов:

- `src/direct_launch/runtime/controller.py`
- `src/direct_launch/runtime/restart_flow.py`
- `src/direct_launch/runtime/lifecycle_feedback.py`

### Этап 7. Подключить новый `ui_root` в существующий startup

Не делать второй shell. Правильный путь:

- сохранить `ZapretFluentWindow`;
- сохранить существующий startup/lifecycle контур, если он остаётся чистым;
- заменить `MainWindowUI` на новый `ui_root` и новый набор UI-layer сущностей.

Важно:

существующий startup/lifecycle слой уже ожидает определённые window-level контракты. Новый каркас обязан либо сохранить их в совместимой форме, либо мигрировать эти use-site'ы в том же срезе.

Критичные ожидания, которые уже есть в коде:

- `WindowStartupMixin` вызывает `build_ui()` и `finish_ui_bootstrap()`;
- `WindowLifecycleMixin` использует `get_loaded_page(...)`, `pages` и `_update_titlebar_search_width()`;
- `WindowActionsMixin` использует `show_page(...)` и `_route_search_result(...)`;
- `main/post_startup.py` и другие post-startup сценарии используют window-level page navigation;
- `tray.py` использует router/window-level UI integration.

Это значит:

- новый каркас должен иметь чёткий window-facing adapter слой;
- нельзя просто заменить `MainWindowUI` на набор свободных объектов без сохранения этого внешнего surface;
- если какой-то старый window-level API удаляется, все его внешние use-site'ы должны мигрировать в том же срезе.

### Этап 8. Перевести страницы первой волны

Первая волна — страницы с наибольшей зависимостью от старого orchestration:

- direct control Z1/Z2
- strategy pages
- strategy detail pages
- user presets pages
- preset detail pages
- control page

### Этап 9. Перевести общие страницы

Вторая волна:

- about
- appearance
- premium
- autostart
- logs
- hosts
- network
- telegram proxy
- прочие common pages

### Этап 10. Cutover-коммит

После покрытия сценариев:

- удалить `main_window*`;
- удалить старые use-site'ы;
- удалить старые dispatch helper'ы;
- удалить runtime -> main_window связки;
- повторным поиском убедиться, что legacy не осталось в scope.

## 11. Страницы, требующие обязательного аудита на зависимость от window()

Ниже список UI-файлов, где уже найден доступ к глобальным зависимостям через `self.window()` или эквивалентный паттерн. Это не означает обязательную полную перепись, но означает обязательный аудит и, вероятно, переход на явное внедрение зависимостей.

- `src/autostart/ui/page.py`
- `src/blockcheck/ui/strategy_scan_page.py`
- `src/core/presets/ui/preset_subpage_base.py`
- `src/direct_control/zapret1/page.py`
- `src/direct_control/zapret2/page.py`
- `src/filters/pages/direct_zapret1_targets_page.py`
- `src/filters/pages/direct_zapret2_targets_page.py`
- `src/filters/strategy_detail/zapret2/page.py`
- `src/orchestra/ui/whitelist_page.py`
- `src/preset_zapret1/ui/user_presets_page.py`
- `src/preset_zapret2/ui/user_presets_page.py`
- `src/ui/pages/control_page.py`

Для этих страниц при переносе надо ответить на вопрос:

- страницу можно оставить и просто дать ей явные зависимости?
- или страница настолько завязана на старый orchestration, что её выгоднее частично переписать?

## 11.0 Window adapter contract

Это обязательный артефакт первой технической фазы.

Его задача — зафиксировать, какой внешний API окна ещё нужен существующему коду во время миграции, и чем именно он будет обслуживаться новым каркасом.

### 11.0.1 Зачем он нужен

Сейчас разные части проекта ожидают, что окно умеет:

- `build_ui()`
- `finish_ui_bootstrap()`
- `show_page(page_name)`
- `get_loaded_page(page_name)`
- хранить `pages`
- обновлять titlebar search width
- маршрутизировать sidebar search result

Если это не описать отдельно, следующий ИИ легко сделает одну из двух ошибок:

- или оставит старый `MainWindowUI` "пока временно";
- или удалит старый API раньше времени и сломает startup/lifecycle/tray/post-startup контракты.

### 11.0.2 Что должно быть в adapter contract

Для каждого window-level метода или поля нужно явно зафиксировать:

- имя текущего API;
- кто его сейчас вызывает;
- остаётся ли он временно;
- чем он реализуется в новом каркасе;
- когда он будет удалён или сужен.

Минимальная таблица должна содержать такие строки:

- `build_ui()` -> вызывается startup -> временно сохраняется как фасад над `ui_root.build()`
- `finish_ui_bootstrap()` -> вызывается startup -> временно сохраняется как фасад над `ui_root.finish_bootstrap()`
- `show_page(PageName)` -> вызывается actions/post-startup/страницы -> сохраняется как фасад над `page_host.show_page()`
- `get_loaded_page(PageName)` -> вызывается lifecycle/workflows -> сохраняется как фасад над `page_host.get_loaded_page()`
- `pages` -> используется lifecycle/post-startup -> временно остаётся как проксируемый registry `page_host`
- `_update_titlebar_search_width()` -> вызывается lifecycle resize path -> переносится в navigation/search adapter
- `_route_search_result(...)` -> вызывается `WindowActionsMixin` и search flow -> переносится в navigation/workflow слой

### 11.0.3 Архитектурное правило

`window adapter contract` не является второй архитектурой.
Это только временный совместимый surface окна, который нужен на время миграции.

Новый канонический владелец поведения должен жить в:

- `ui_root`
- `page_host`
- `navigation controller`
- `ui_workflows`
- `runtime_ui_bridge`

А не в адаптере.

### 11.0.3.1 Exit condition для adapter layer

У adapter layer должна быть явная точка смерти.

После завершения cutover нужно отдельно проверить:

- какие window-level compatibility методы ещё реально нужны;
- какие из них можно удалить;
- какие из них должны остаться только как тонкие фасады над новыми слоями.

Недопустимо, чтобы window adapter навсегда стал новым местом, где живёт вся orchestration-логика окна.

## 11.0.4 Нужно ли переписывать Startup / lifecycle как структуру

Базовый ответ для этой миграции:

- нет, не нужно переписывать `Startup / lifecycle` с нуля;
- да, их нужно локально адаптировать под новый каркас.

Это важное различие.

Что сохраняем:

- `WindowStartupMixin` как точку входа и orchestration старта окна;
- `WindowLifecycleMixin` как контейнер window-level lifecycle событий;
- существующие startup/post-startup сигналы;
- geometry / notification / tray / close behavior.

Что допускается менять:

- их зависимости на старый `MainWindowUI`;
- способ, которым они вызывают page/navigation/search функции;
- внутреннюю прокладку к новому `ui_root` и `page_host`.

Что не надо делать в этой фазе:

- не переписывать весь startup pipeline ради "чистой архитектуры";
- не переносить lifecycle целиком в другой слой, если проблема решается адаптером;
- не плодить новый второй startup-framework рядом со старым.

То есть:

`Startup / lifecycle сохраняются как структура, но их зависимость от legacy MainWindowUI заменяется новым adapter surface.`

## 11.0.5 Нужно ли менять BasePage как структуру

Базовый ответ для этой миграции:

- нет, `BasePage` не надо переписывать с нуля;
- да, его контракт надо явно сохранить и при необходимости слегка подчистить.

Почему:

- `BasePage` уже является общим lifecycle-слоем страниц;
- на него завязаны десятки страниц;
- он уже содержит полезную инфраструктуру: scroll behavior, theme refresh, page lifecycle hooks, cleanup hooks.

Что сохраняем:

- сам `BasePage` как базовый класс;
- `bind_ui_state_store(...)` как часть integration contract;
- `cleanup()` как обязательный lifecycle hook;
- готовность страницы / callbacks;
- интеграцию с `PageLoadController`.

Что допускается менять:

- как именно `BasePage` подключается к новому page host;
- как и когда вызываются page activation / page hidden hooks;
- как в него прокидываются schema-aware или workflow-aware сигналы, если это нужно.

Что не надо делать в этой фазе:

- не переписывать весь `BasePage` только ради смены orchestration;
- не отказываться от него до тех пор, пока нет явного доказательства, что он мешает архитектурно;
- не дублировать новый lifecycle рядом со старым lifecycle BasePage.

То есть:

`BasePage сохраняется как структура общего page-lifecycle слоя и не является стартовой целью переписывания.`

## 11.0.6 Когда допустим отдельный рефактор Startup / lifecycle или BasePage

Только после cutover orchestration и только если появится конкретное подтверждение, что:

- startup/lifecycle по-прежнему содержит лишний orchestration;
- `BasePage` по-прежнему мешает page host / workflow дизайну;
- текущая структура реально удерживает legacy-path, который нельзя убрать локально.

До этого момента они считаются:

- сохраняемыми structural layers;
- не главным target этой миграции.

## 11.0.7 Navigation contract matrix

Это второй обязательный артефакт первой технической фазы.

Его задача — до кода зафиксировать, как каждая страница живёт в новой navigation architecture.

### 11.0.7.1 Что должно быть в матрице

Для каждой страницы нужно зафиксировать минимум:

- `page_name`
- `module`
- `mode_scope`
- `entry_kind`
- `sidebar_visible`
- `search_visible`
- `breadcrumb_parent`
- `allow_direct_open`
- `factory_owner`
- `workflow_owner`

Где:

- `factory_owner` показывает, кто отвечает за создание страницы;
- `workflow_owner` показывает, какой workflow/controller имеет право её открывать и координировать.

### 11.0.7.2 Зачем это нужно

Без этой матрицы следующий ИИ может сделать "почти правильный" каркас, в котором:

- root visibility живёт в schema;
- hidden page gating живёт в page host;
- back route живёт в странице;
- search visibility живёт в text_catalog;
- breadcrumbs живут отдельно в UI.

Это снова приведёт к расползанию архитектуры.

Матрица нужна, чтобы до кода было видно:

- кто владеет страницей;
- в каком режиме она существует;
- как она открывается;
- видит ли её пользователь в меню и поиске;
- откуда у неё берётся breadcrumb path.

### 11.0.7.3 Минимальные режимные группы для матрицы

Матрица обязана явно покрывать:

- `common`
- `direct_zapret2`
- `direct_zapret1`
- `orchestra`

И отдельно различать:

- root pages
- hidden pages
- detail pages
- internal subpages

### 11.0.7.4 Архитектурное правило

После появления `navigation contract matrix` ни одна page-level ветка не должна "сама решать" свою режимную доступность.

Страница может знать:

- как она выглядит;
- какие сигналы отдаёт;
- как показать breadcrumb.

Но страница не должна быть владельцем решения:

- можно ли её открыть в текущем режиме;
- должна ли она быть видна в sidebar;
- должна ли она участвовать в sidebar search.

## 11.1 Не только страницы: дополнительные use-site'ы, которые должен покрыть cutover

Чтобы миграция реально покрывала исходный код, нельзя смотреть только на страницы. Есть ещё внешние слои, которые уже завязаны на window/router contracts и должны быть включены в closure map перед финальным cutover.

Минимальный обязательный список:

- `src/main/window_startup.py`
- `src/main/window_lifecycle.py`
- `src/main/window_actions.py`
- `src/main/post_startup.py`
- `src/tray.py`
- `src/direct_launch/runtime/controller.py`
- `src/direct_launch/runtime/restart_flow.py`
- `src/direct_launch/runtime/lifecycle_feedback.py`
- `src/ui/theme_subscription_manager.py`
- `src/ui/window_notification_controller.py`
- `src/ui/window_geometry_controller.py`

Эти файлы не все входят в "перепись UI orchestration", но они обязаны быть учтены в плане, потому что уже используют текущие window/router/page contracts.

## 11.2 Сервисы окна, которые сохраняются и не должны потеряться

Новый план не должен случайно потерять существующие window-services, которые не относятся к legacy `main_window*`, но всё равно критичны для поведения приложения.

Обязательно сохранить и переподключить:

- geometry persistence;
- notification controller;
- holiday effects;
- theme subscription hooks;
- tray integration;
- startup interactive/post-startup hooks;
- opacity/garland/snowflakes window-level integration.

## 11.3 Общий page lifecycle, который тоже должен войти в closure map

Кроме самих страниц и window-level use-site'ов, новый каркас обязан включить в closure map общий lifecycle страниц.

Минимальный обязательный список:

- `src/ui/pages/base_page.py`
- `src/ui/page_runtime.py`
- все страницы, реализующие `bind_ui_state_store(...)`
- все страницы, реализующие `cleanup()`

Это критично, потому что orchestration GUI управляет не только показом страницы, но и:

- тем, когда страница считается активированной;
- как страница подписывается на store;
- как страница очищает ресурсы;
- как предотвращаются устаревшие асинхронные загрузки.

## 11.4 Sidebar search и search index тоже входят в migration scope

Чтобы план реально покрывал исходный код, migration scope обязан включать не только sidebar visibility, но и поиск по страницам.

Минимальный обязательный список:

- `src/ui/text_catalog.py`
- `src/ui/main_window_navigation_build.py` как legacy-источник текущего search glue
- router/schema mode gating для search visibility

В новой архитектуре sidebar search должен быть переподключён к:

- каноническому schema-layer;
- текущему режиму;
- page host / workflow navigation;

а не остаться скрытым legacy-механизмом.

Это не часть старого orchestration-ядра, но это часть реального поведения окна.

## 12. Что делать нельзя

Ниже перечислены решения, которые запрещены этим планом.

### 12.1 Нельзя оставлять fallback на старый `main_window*`

Если новый путь покрывает сценарий, старый orchestration-layer должен быть удалён, а не сохранён "на всякий случай".

### 12.2 Нельзя делать dual truth source для navigation

В финале нельзя иметь:

- `router.py` как старый источник истины;
- и новый schema-модуль как второй живой источник истины.

### 12.3 Нельзя делать runtime-aware window glue заново

Нельзя заменять старые `_show_active_strategy_page_loading()` на новые приватные window-hooks под другим именем, если runtime всё равно знает о concrete window object.

### 12.4 Нельзя превращать page host в новый god object

`page_host` отвечает только за lifecycle и open/show.
Если он начинает сам решать бизнес-переходы, mode switch и runtime feedback, значит в проекте просто появился новый `main_window.py`.

### 12.5 Нельзя держать mode visibility в трёх местах

Нельзя одновременно вычислять режимную доступность:

- в schema;
- в navigation controller;
- в отдельных страницах.

Один truth source, остальные только читают или удаляются.

### 12.6 Нельзя переписывать здоровые fluent-страницы без причины

Если страница здорова и требует только явного DI, не надо переписывать её "для чистоты".

### 12.7 Нельзя недооценивать внешние window contracts

Нельзя считать, что cutover покрыт только переносом страниц и navigation logic, если при этом остались старые ожидания startup/lifecycle/tray/post-startup слоёв к window API.

Если новый каркас ломает:

- `build_ui()`
- `finish_ui_bootstrap()`
- `show_page()`
- `get_loaded_page()`
- `pages`
- `_update_titlebar_search_width()`
- `_route_search_result()`

то это не "мелкая интеграция", а незавершённый cutover.

## 12.8 Нельзя сейчас расширять scope до полного переписывания shell без причины

Замена shell с нуля допускается только как отдельная следующая фаза, если после cutover выяснится, что:

- `ZapretFluentWindow` сам по себе грязный архитектурно;
- startup/lifecycle слой не удаётся разумно удержать;
- shell содержит orchestration, который не получается из него вынести без переписи.

На текущем этапе shell replacement не является обязательным условием новой архитектуры.
Иначе мы одновременно тронем:

- shell;
- startup;
- lifecycle;
- navigation;
- page host;
- runtime bridge;

и миграция станет слишком широкой и рискованной.

## 13. Acceptance criteria

Миграция GUI orchestration считается законченной только если одновременно выполнены все условия ниже.

- `main_window*` legacy-слой удалён из рабочего пути.
- Runtime больше не знает про `main_window`.
- Страницы больше не тянут глобальные сервисы через `self.window()` там, где это service-locator зависимость.
- Есть один канонический navigation truth source.
- Есть один page lifecycle path через factory/host.
- Есть один runtime -> UI path через bridge.
- Режим `direct_zapret1` не может открыть `zapret2`-ветку.
- Режим `direct_zapret2` не может открыть `zapret1`-ветку.
- Режим `orchestra` не может открыть direct-ветки.
- Sidebar search не показывает страницы, недоступные текущему режиму.
- В проекте не осталось intended legacy use-site'ов старого orchestration-слоя в рамках target scope.

## 14. Минимальная проверка после каждого крупного этапа

Так как фокус сейчас на `public_zapretgui/src`, а не на тестовом слое, минимальная проверка должна быть такой:

- `python -m compileall` по изменённым файлам;
- узкая ручная проверка старта окна;
- ручная проверка mode gating;
- ручная проверка navigation/back/breadcrumb сценариев;
- ручная проверка detail/subpage открытия;
- ручная проверка runtime feedback loading/success/error;
- отдельная фиксация того, что удалось проверить, а что упёрлось в WSL/Windows среду.

## 15. С чего начинать следующему ИИ

Следующий ИИ не должен начинать с хаотичного редактирования страниц.

Правильная первая задача:

1. выбрать и зафиксировать единственный будущий navigation truth source;
2. создать новый schema-модуль и в одном срезе перенести в него navigation-данные из `src/ui/router.py`;
3. только после этого делать page host и navigation controller.

Если начать со страниц или со случайных signal-wiring правок раньше schema, проект снова уедет в полуручной orchestration.

## 15.1 Дополнительная decision rule по `router.py`

Базовый план для этой миграции:

- не использовать `src/ui/router.py` как финальный schema-layer;
- использовать его только как источник данных для одноразового переноса в новый schema-модуль.

- Правильный целевой путь уже выбран:

- в одном срезе вынести schema-data в новый модуль;
- сразу перевести `router.py` на zero-logic compatibility layer или удалить его;
- не держать дублирующие данные в двух местах дольше переходного среза.

То есть вопрос "reuse router.py or not" для этого плана уже закрыт.
Мы не эволюционируем старый `router.py` в новый truth source.
Мы переносим данные в новый schema-модуль и гасим старый путь сразу, а не растягиваем двойную архитектуру.

### 15.1.1 Canonical import rule после первого среза

После первого среза новый canonical import path должен быть таким:

- `from ui.navigation.schema import ...`

А не:

- `from ui.router import ...`

Если временный compatibility re-export в `ui.router` всё ещё существует, он считается переходным слоем и не должен использоваться для новых use-site'ов.

## 15.2 Дополнительная decision rule по shell

Базовый план для этой миграции:

- не переписывать shell с нуля до cutover orchestration;
- сохранить `ZapretFluentWindow` и существующий startup/lifecycle-контур;
- сосредоточиться на замене `MainWindowUI` и `main_window*`.

После завершения этого cutover допускается отдельный post-cutover аудит shell.

Если тогда выяснится, что shell всё ещё архитектурно перегружен, можно планировать вторую фазу:

- shell cleanup;
- shell rename;
- или shell rewrite.

Но это отдельная задача, а не обязательный стартовый шаг текущей миграции.

## 16. Короткая формула проекта после cutover

Вот как должна описываться новая архитектура после завершения миграции:

`FluentWindow остаётся shell-основой, AppContext остаётся контейнером зависимостей, MainWindowStateStore остаётся глобальным UI-store, navigation schema становится единственным источником истины по страницам и режимам, page host управляет жизненным циклом страниц, workflow-слой управляет пользовательскими сценариями, runtime bridge связывает runtime и UI без знания о concrete window object, а старый main_window* слой больше не существует.`
