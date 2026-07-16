from __future__ import annotations

import gc
import sys
from pathlib import Path

import pytest

PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


def _qt_slot_excepthook(exc_type, exc, tb) -> None:
    """Не даёт PyQt6 убивать процесс из-за исключения в слоте.

    PyQt ≥ 5.5: необработанное Python-исключение в слоте, таймере или
    виртуальном методе завершает процесс через qFatal (fail-fast
    0xC0000409) — traceback при этом уходит в перехваченный pytest'ом
    stderr и теряется.  Именно так «падал» кластер tests/test_p*.py:
    отложенный QTimer координатора срабатывал в чужом тесте, его слот
    натыкался на уже удалённые объекты и кидал RuntimeError.  Нативный
    стек: QMessageLogger::fatal ← QtCore.pyd ← QMetaObject::activate ←
    QEventDispatcherWin32 ← processEvents.

    Установка собственного sys.excepthook — документированный способ
    вернуть старое поведение: PyQt зовёт хук и продолжает работу.
    Печатаем traceback в настоящий stderr, чтобы шум был виден.
    """
    import traceback

    print("[qt-slot-exception] необработанное исключение в Qt-слоте:", file=sys.__stderr__)
    traceback.print_exception(exc_type, exc, tb, file=sys.__stderr__)


sys.excepthook = _qt_slot_excepthook


_SESSION_EXIT_STATUS = {"status": 0}


def pytest_sessionfinish(session, exitstatus):
    _SESSION_EXIT_STATUS["status"] = int(exitstatus)


def pytest_unconfigure(config):
    """Пропускает финализацию интерпретатора, если в процессе жил Qt.

    После сотен Qt-тестов в одном процессе остаются осиротевшие C++-объекты
    (координаторы, таймеры, воркеры), которые невозможно перечислить и
    удалить в правильном порядке.  Любая финализация — что обычное
    завершение Python, что явное sip.delete(QApplication) — падает
    сегфолтом уже ПОСЛЕ строки "N passed", ломая код выхода.  Поэтому после
    вывода итогов pytest завершаем процесс через os._exit с сохранением
    кода выхода.  Для прогонов без Qt поведение не меняется.
    """
    qtwidgets = sys.modules.get("PyQt6.QtWidgets")
    if qtwidgets is None:
        return
    if qtwidgets.QApplication.instance() is None:
        return
    import os

    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(_SESSION_EXIT_STATUS["status"])


_QT_APP_KEEPALIVE: list[object] = []


def _ensure_qapplication_owned() -> None:
    """Создаёт и удерживает QApplication на весь pytest-процесс.

    Многие тесты пишут ``app = QApplication.instance() or QApplication([])``
    и держат app только в локальной переменной.  Если такой тест оказался
    первым создателем приложения, QApplication разрушается прямо при выходе
    из тестового метода (счётчик ссылок обёртки падает до нуля).
    ~QApplication при этом удаляет все top-level-виджеты — в том числе
    popup чужого QCompleter, на который сам QCompleter держит сырой
    C++-указатель.  Когда позже GC добирается до владельца QCompleter,
    деструктор делает delete по уже освобождённой памяти: куча портится,
    «умирает» случайный живой QObject (например, глобальный qconfig из
    qfluentwidgets — тогда все последующие qfluentwidgets-виджеты падают
    с "wrapped C/C++ object of type QConfig has been deleted") либо процесс
    завершается fail-fast 0xC0000409.

    Поэтому, как только PyQt6.QtWidgets импортирован (тестом или при
    коллекции), conftest сам создаёт QApplication и держит ссылку до конца
    процесса.  Тесты с паттерном ``instance() or QApplication([])`` находят
    готовый экземпляр и больше никогда не становятся его владельцами.
    Для прогонов без Qt ничего не создаётся и не импортируется.
    """
    if _QT_APP_KEEPALIVE:
        return
    qtwidgets = sys.modules.get("PyQt6.QtWidgets")
    if qtwidgets is None:
        return
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = qtwidgets.QApplication.instance()
    if app is None:
        app = qtwidgets.QApplication(["pytest"])
    _QT_APP_KEEPALIVE.append(app)


def pytest_collection_finish(session):
    # Коллекция уже импортировала модули тестов; если кто-то из них привёз
    # QtWidgets — владеем приложением с самого начала прогона.
    _ensure_qapplication_owned()


_LIVE_QTHREADS: "weakref.WeakSet" = None  # type: ignore[assignment]


def _install_qthread_tracker(qtcore) -> None:
    """Регистрирует каждый создаваемый QThread в WeakSet.

    Дешевле, чем gc.get_objects() на каждый teardown (на ~4000 тестах
    полное сканирование кучи добавляло минуты к прогону).
    """
    global _LIVE_QTHREADS
    if _LIVE_QTHREADS is not None:
        return
    import weakref

    _LIVE_QTHREADS = weakref.WeakSet()
    original_init = qtcore.QThread.__init__

    def _tracking_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        try:
            _LIVE_QTHREADS.add(self)
        except Exception:
            pass

    qtcore.QThread.__init__ = _tracking_init


def _quiesce_user_qthreads(qtcore) -> None:
    """Дожидается пользовательских QThread до уборки Qt-состояния.

    Если удалить QThread, пока поток ещё работает, Qt делает fail-fast
    (0xC0000409).  В трекере только созданные из Python потоки — обёртка
    главного потока туда не попадает.
    """
    if _LIVE_QTHREADS is None:
        return
    for obj in list(_LIVE_QTHREADS):
        try:
            if obj.isRunning():
                obj.wait(5000)
        except RuntimeError:
            pass  # C++-объект уже удалён


@pytest.fixture(autouse=True)
def _isolated_settings_dir(tmp_path, monkeypatch):
    """Изолирует settings.json на каждый тест.

    Реестр идентичности профилей (и прочая мета) пишется при любой загрузке
    выбранного пресета через ProfilePresetService — тест без изоляции молча
    засорял бы рабочий settings/settings.json репозитория. Тесты, которым
    нужен свой каталог, по-прежнему патчат settings.store.MAIN_DIRECTORY
    сами — их patch вкладывается поверх этого."""
    monkeypatch.setattr("settings.store.MAIN_DIRECTORY", str(tmp_path), raising=False)


@pytest.fixture(autouse=True)
def _qt_state_sweep():
    """Держит общий QApplication чистым между тестами.

    Qt-тесты пакета переиспользуют один QApplication на весь процесс pytest
    и в большинстве своём не удаляют ни виджеты, ни отложенные события.
    Накопленная очередь (PolishRequest, MetaCall из воркеров, DeferredDelete)
    со временем начинает указывать на уже освобождённую память — и первый же
    ``processEvents()`` в каком-нибудь позднем тесте падает с
    "Windows fatal exception: access violation" (Python 3.14, PyQt6 6.11,
    offscreen).  Поэтому полный прогон падал в случайных accessibility-тестах,
    а каждый файл в одиночку проходил.

    Уборка после каждого теста; порядок существенен:

    1. дождаться пользовательских QThread — удаление работающего потока
       (например, воркера координатора) даёт мгновенный fail-fast 0xC0000409;
    2. выбросить ВСЕ накопленные posted-события — тест завершён, доставлять
       их некому, а доставка в мёртвые объекты и есть источник падений;
    3. спрятать и удалить оставшиеся top-level-виджеты на C++-стороне, пока
       их Python-обёртки живы (иначе циклический GC оставит от них «оболочки»
       с разрушенным Python-состоянием); скрытие до удаления обязательно —
       sip.delete показанного виджета с фокусом иногда даёт fail-fast;
       удалять можно ТОЛЬКО виджеты во владении Python (sip.ispyowned):
       например, popup у QCompleter — top-level QListView, которым владеет
       сам QCompleter через сырой C++-указатель; sip.delete такого popup
       оставляет висячий указатель, и деструктор QCompleter добивает чужую
       память — кучa портится, и позже процесс падает 0xC0000409/0xC0000005
       в случайном месте (или «умирает» посторонний QObject вроде qconfig);
    4. снова выбросить события, поставленные в очередь самим удалением;
    5. только теперь собрать циклический мусор.
    """
    # Setup-фаза: если Qt появился по ходу прогона (ленивый импорт в тестовом
    # методе), забрать владение QApplication до следующего Qt-теста.
    _ensure_qapplication_owned()
    _qtcore_setup = sys.modules.get("PyQt6.QtCore")
    if _qtcore_setup is not None:
        _install_qthread_tracker(_qtcore_setup)
    yield
    qtwidgets = sys.modules.get("PyQt6.QtWidgets")
    if qtwidgets is None:
        return
    app = qtwidgets.QApplication.instance()
    if app is None:
        return
    from PyQt6 import sip

    qtcore = sys.modules.get("PyQt6.QtCore")
    if qtcore is not None:
        _quiesce_user_qthreads(qtcore)

    app.removePostedEvents(None, 0)

    # Некоторые тесты создают QCoreApplication — у него нет виджетов.
    if isinstance(app, qtwidgets.QApplication):
        for widget in app.topLevelWidgets():
            try:
                widget.hide()
            except (RuntimeError, TypeError):
                pass
        for widget in app.topLevelWidgets():
            try:
                if not sip.ispyowned(widget):
                    continue  # C++-владелец удалит сам (например, QCompleter)
                sip.delete(widget)
            except (RuntimeError, TypeError):
                pass  # уже удалён (например, вместе с другим top-level)
        app.removePostedEvents(None, 0)

    # Глобальный styleSheetManager qfluentwidgets держит виджеты всех
    # прошедших тестов; setThemeColor()/updateStyleSheet() в позднем тесте
    # перебирает их и падает access violation на удалённом sweep'ом виджете
    # (обёртка не всегда помечена из-за переиспользования адресов).
    # Записи чужих тестов — мусор: свои виджеты тест регистрирует заново
    # при создании.
    qfw_style = sys.modules.get("qfluentwidgets.common.style_sheet")
    if qfw_style is not None:
        try:
            qfw_style.styleSheetManager.widgets.clear()
        except Exception:
            pass

    gc.collect()
