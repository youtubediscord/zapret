from __future__ import annotations

from ui.window_ui_session import get_window_ui_session


def are_animations_enabled() -> bool:
    """Читает текущее пользовательское состояние мастер-переключателя анимаций."""
    try:
        from settings.appearance import peek_warmed_animations_enabled

        return bool(peek_warmed_animations_enabled())
    except Exception:
        return False


def register_managed_animation(animation, duration_ms: int | None = None):
    """Запоминает базовую длительность анимации и сразу применяет текущую policy."""
    try:
        if duration_ms is not None:
            animation.setDuration(int(duration_ms))
            base_duration = int(duration_ms)
        else:
            base_duration = int(animation.duration())

        animation._zapret_base_duration = max(0, base_duration)
    except Exception:
        pass

    apply_animation_policy(animation)
    return animation


def apply_animation_policy(animation) -> None:
    """Применяет текущую policy к конкретной анимации без её запуска."""
    try:
        base_duration = int(getattr(animation, "_zapret_base_duration", animation.duration()))
    except Exception:
        return

    try:
        animation.setDuration(base_duration if are_animations_enabled() else 0)
    except Exception:
        pass


def start_managed_animation(animation, policy=None) -> None:
    """Запускает анимацию после применения локальной policy по длительности."""
    apply_animation_policy(animation)

    try:
        if policy is None:
            animation.start()
        else:
            animation.start(policy)
    except Exception:
        pass


def apply_window_animation_policy(window, enabled: bool) -> None:
    """Применяет мастер-политику анимаций и пересчитывает зависимую прокрутку редакторов."""
    apply_process_animation_fallback(enabled)

    try:
        from settings.appearance import peek_warmed_editor_smooth_scroll_enabled

        apply_window_editor_smooth_scroll_policy(window, bool(peek_warmed_editor_smooth_scroll_enabled()))
    except Exception:
        pass


def apply_process_animation_fallback(enabled: bool) -> None:
    """Временно включает или отключает глобальный fallback для QPropertyAnimation."""
    try:
        from PyQt6.QtCore import QAbstractAnimation, QPropertyAnimation

        if enabled:
            if hasattr(QPropertyAnimation, "_zapret_original_start"):
                QPropertyAnimation.start = QPropertyAnimation._zapret_original_start
                del QPropertyAnimation._zapret_original_start
            return

        if not hasattr(QPropertyAnimation, "_zapret_original_start"):
            original_start = QPropertyAnimation.start
            QPropertyAnimation._zapret_original_start = original_start

            def _instant_start(
                self,
                policy=QAbstractAnimation.DeletionPolicy.KeepWhenStopped,
            ):
                self.setDuration(0)
                QPropertyAnimation._zapret_original_start(self, policy)

            QPropertyAnimation.start = _instant_start
    except Exception:
        pass


def apply_window_smooth_scroll_policy(window, enabled: bool) -> None:
    """Переключает плавную прокрутку страниц, списков и деревьев, но не редакторов."""
    _apply_smooth_scroll_policy_to_targets(window, bool(enabled), editors=False)


def apply_window_editor_smooth_scroll_policy(window, enabled: bool) -> None:
    """Переключает плавную прокрутку только у текстовых редакторов."""
    try:
        from ui.smooth_scroll import get_effective_editor_smooth_scroll_enabled

        effective_enabled = get_effective_editor_smooth_scroll_enabled(enabled)
    except Exception:
        return

    _apply_smooth_scroll_policy_to_targets(window, effective_enabled, editors=True)


def _apply_smooth_scroll_policy_to_targets(window, enabled: bool, *, editors: bool) -> None:
    """Применяет режим прокрутки к редакторам или ко всем остальным виджетам."""
    try:
        from ui.smooth_scroll import apply_smooth_scroll_mode, is_editor_smooth_scroll_target
    except Exception:
        return

    iterator = _iter_smooth_scroll_targets(window)
    while True:
        try:
            target = next(iterator)
        except StopIteration:
            break
        except Exception:
            break

        # Ошибка одного виджета (например, уже удалённого на C++-стороне)
        # не должна отменять применение настройки к остальным.
        try:
            if bool(is_editor_smooth_scroll_target(target)) != editors:
                continue

            apply_smooth_scroll_mode(target, enabled)
            custom_setter = getattr(target, "set_smooth_scroll_enabled", None)
            if callable(custom_setter):
                try:
                    custom_setter(enabled)
                except Exception:
                    pass
        except Exception:
            continue


def _iter_smooth_scroll_targets(window):
    """Объединяет обход страниц окна с глобальным реестром smooth-scroll виджетов.

    Реестр закрывает лениво созданные страницы и диалоги, которых нет
    в session.pages на момент переключения настройки.
    """
    seen_ids = set()

    for target in _iter_window_pages_and_children(window):
        if id(target) in seen_ids:
            continue
        seen_ids.add(id(target))
        yield target

    try:
        from ui.smooth_scroll import iter_managed_smooth_scroll_widgets

        managed = iter_managed_smooth_scroll_widgets()
    except Exception:
        managed = ()

    for target in managed:
        if id(target) in seen_ids:
            continue
        seen_ids.add(id(target))
        yield target


def _iter_window_pages_and_children(window):
    """Итерирует по страницам окна и всем их дочерним QWidget-элементам."""
    try:
        from PyQt6.QtWidgets import QWidget
    except Exception:
        return

    session = get_window_ui_session(window)
    pages = [] if session is None else list(session.pages.values())
    for page in pages:
        yield page
        for child in page.findChildren(QWidget):
            yield child
