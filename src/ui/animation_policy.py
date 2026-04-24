from __future__ import annotations


def are_animations_enabled() -> bool:
    """Читает текущее пользовательское состояние мастер-переключателя анимаций."""
    try:
        from settings.store import get_animations_enabled

        return bool(get_animations_enabled())
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
        from settings.store import get_editor_smooth_scroll_enabled

        apply_window_editor_smooth_scroll_policy(window, get_editor_smooth_scroll_enabled())
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
    try:
        from ui.smooth_scroll import apply_smooth_scroll_mode, is_editor_smooth_scroll_target

        def _apply_smooth_mode(target) -> None:
            if is_editor_smooth_scroll_target(target):
                return

            apply_smooth_scroll_mode(target, enabled)
            custom_setter = getattr(target, "set_smooth_scroll_enabled", None)
            if callable(custom_setter):
                try:
                    custom_setter(enabled)
                except Exception:
                    pass

        for target in _iter_window_pages_and_children(window):
            _apply_smooth_mode(target)
    except Exception:
        pass


def apply_window_editor_smooth_scroll_policy(window, enabled: bool) -> None:
    """Переключает плавную прокрутку только у текстовых редакторов."""
    try:
        from ui.smooth_scroll import (
            apply_smooth_scroll_mode,
            get_effective_editor_smooth_scroll_enabled,
            is_editor_smooth_scroll_target,
        )

        effective_enabled = get_effective_editor_smooth_scroll_enabled(enabled)

        def _apply_editor_smooth_mode(target) -> None:
            if not is_editor_smooth_scroll_target(target):
                return

            apply_smooth_scroll_mode(target, effective_enabled)

            custom_setter = getattr(target, "set_smooth_scroll_enabled", None)
            if callable(custom_setter):
                try:
                    custom_setter(effective_enabled)
                except Exception:
                    pass

        for target in _iter_window_pages_and_children(window):
            _apply_editor_smooth_mode(target)
    except Exception:
        pass


def _iter_window_pages_and_children(window):
    """Итерирует по страницам окна и всем их дочерним QWidget-элементам."""
    try:
        from PyQt6.QtWidgets import QWidget
    except Exception:
        return

    for page in list(getattr(window, "pages", {}).values()):
        yield page
        for child in page.findChildren(QWidget):
            yield child
