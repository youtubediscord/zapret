from __future__ import annotations


_EDITOR_SMOOTH_SCROLL_PROPERTY = "zapretEditorSmoothScrollTarget"


def apply_smooth_scroll_mode(widget, enabled: bool) -> None:
    """Применяет нужный режим плавной прокрутки к fluent-виджету."""
    try:
        from PyQt6.QtCore import Qt
        from qfluentwidgets.common.smooth_scroll import SmoothMode

        mode = SmoothMode.COSINE if enabled else SmoothMode.NO_SMOOTH

        def _apply_delegate_mode(delegate) -> None:
            if delegate is None:
                return

            try:
                if hasattr(delegate, "useAni"):
                    if not hasattr(delegate, "_zapret_base_use_ani"):
                        delegate._zapret_base_use_ani = bool(delegate.useAni)
                    delegate.useAni = bool(delegate._zapret_base_use_ani) if enabled else False
            except Exception:
                pass

            for smooth_attr in ("verticalSmoothScroll", "horizonSmoothScroll"):
                smooth = getattr(delegate, smooth_attr, None)
                setter = getattr(smooth, "setSmoothMode", None)
                if callable(setter):
                    try:
                        setter(mode)
                    except Exception:
                        pass

            setter = getattr(delegate, "setSmoothMode", None)
            if callable(setter):
                try:
                    setter(mode)
                except TypeError:
                    try:
                        setter(mode, Qt.Orientation.Vertical)
                    except Exception:
                        pass
                except Exception:
                    pass

        setter = getattr(widget, "setSmoothMode", None)
        if callable(setter):
            try:
                setter(mode, Qt.Orientation.Vertical)
            except TypeError:
                setter(mode)
            except Exception:
                pass

        _apply_delegate_mode(getattr(widget, "scrollDelegate", None))
        _apply_delegate_mode(getattr(widget, "scrollDelagate", None))
        _apply_delegate_mode(getattr(widget, "delegate", None))
        _apply_delegate_mode(getattr(widget, "_presets_scroll_delegate", None))
        _apply_delegate_mode(getattr(widget, "_smooth_scroll_delegate", None))
    except Exception:
        pass


def mark_as_editor_smooth_scroll_target(widget) -> None:
    """Помечает виджет как редактор, который должен жить по отдельной настройке."""
    try:
        widget.setProperty(_EDITOR_SMOOTH_SCROLL_PROPERTY, True)
    except Exception:
        pass

    try:
        setattr(widget, "_zapret_editor_smooth_scroll_target", True)
    except Exception:
        pass


def is_editor_smooth_scroll_target(widget) -> bool:
    """Проверяет, что виджет относится именно к текстовым редакторам."""
    try:
        prop_value = widget.property(_EDITOR_SMOOTH_SCROLL_PROPERTY)
        if prop_value is not None:
            return bool(prop_value)
    except Exception:
        pass

    return bool(getattr(widget, "_zapret_editor_smooth_scroll_target", False))


def get_page_smooth_scroll_enabled() -> bool:
    """Читает обычную настройку плавной прокрутки страниц и списков."""
    try:
        from settings.store import get_smooth_scroll_enabled as get_scroll_flag

        return bool(get_scroll_flag())
    except Exception:
        return False


def get_editor_smooth_scroll_enabled() -> bool:
    """Читает пользовательскую настройку плавной прокрутки редакторов."""
    try:
        from settings.store import get_editor_smooth_scroll_enabled as get_editor_scroll_flag

        return bool(get_editor_scroll_flag())
    except Exception:
        return False


def get_effective_editor_smooth_scroll_enabled(preference: bool | None = None) -> bool:
    """Возвращает итоговый флаг редакторов с учётом мастер-настройки анимаций."""
    try:
        from settings.store import get_animations_enabled as get_animation_flag

        animations_enabled = bool(get_animation_flag())
    except Exception:
        animations_enabled = False

    if preference is None:
        preference = get_editor_smooth_scroll_enabled()

    return bool(animations_enabled) and bool(preference)


def apply_page_smooth_scroll_preference(widget) -> None:
    """Применяет обычную настройку прокрутки страниц к виджету."""
    apply_smooth_scroll_mode(widget, get_page_smooth_scroll_enabled())


def apply_editor_smooth_scroll_preference(widget, enabled: bool | None = None) -> None:
    """Применяет настройку прокрутки редакторов к конкретному текстовому полю."""
    mark_as_editor_smooth_scroll_target(widget)
    apply_smooth_scroll_mode(widget, get_effective_editor_smooth_scroll_enabled(enabled))
