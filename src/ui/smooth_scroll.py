from __future__ import annotations

import weakref


_EDITOR_SMOOTH_SCROLL_PROPERTY = "zapretEditorSmoothScrollTarget"

# Все живые qfluentwidgets-виджеты с механикой плавной прокрутки.
# Наполняется глобальным патчем install_global_smooth_scroll_policy().
_managed_scroll_widgets: weakref.WeakSet = weakref.WeakSet()
_global_policy_installed = False


def _resolve_smooth_mode(enabled: bool):
    from qfluentwidgets.common.smooth_scroll import SmoothMode

    return SmoothMode.COSINE if enabled else SmoothMode.NO_SMOOTH


def _apply_mode_to_delegate(delegate, enabled: bool) -> None:
    """Применяет режим прокрутки к SmoothScrollDelegate/SmoothScroll qfluentwidgets."""
    if delegate is None:
        return

    try:
        from PyQt6.QtCore import Qt

        mode = _resolve_smooth_mode(enabled)
    except Exception:
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


def apply_smooth_scroll_mode(widget, enabled: bool) -> None:
    """Применяет нужный режим плавной прокрутки к fluent-виджету."""
    try:
        from PyQt6.QtCore import Qt

        mode = _resolve_smooth_mode(enabled)

        setter = getattr(widget, "setSmoothMode", None)
        if callable(setter):
            try:
                setter(mode, Qt.Orientation.Vertical)
            except TypeError:
                setter(mode)
            except Exception:
                pass

        for delegate_attr in (
            "scrollDelegate",
            "scrollDelagate",
            "delegate",
            "smoothScroll",
            "_presets_scroll_delegate",
            "_smooth_scroll_delegate",
        ):
            _apply_mode_to_delegate(getattr(widget, delegate_attr, None), enabled)
    except Exception:
        pass


def _register_managed_scroll_widget(widget) -> None:
    try:
        _managed_scroll_widgets.add(widget)
    except Exception:
        pass


def iter_managed_smooth_scroll_widgets() -> tuple:
    """Возвращает снимок всех живых виджетов с плавной прокруткой qfluentwidgets."""
    try:
        from PyQt6 import sip

        return tuple(widget for widget in _managed_scroll_widgets if not sip.isdeleted(widget))
    except Exception:
        return ()


def install_global_smooth_scroll_policy() -> None:
    """Глобально патчит qfluentwidgets: каждый виджет с плавной прокруткой при
    создании регистрируется в реестре и сразу получает текущую настройку.

    Это единая точка вместо локального применения на каждой странице: лениво
    создаваемые страницы, диалоги и меню тоже подчиняются настройке.
    """
    global _global_policy_installed
    if _global_policy_installed:
        return

    try:
        from qfluentwidgets.common.smooth_scroll import SmoothScroll
        from qfluentwidgets.components.widgets.scroll_bar import SmoothScrollDelegate
    except Exception:
        return

    original_smooth_scroll_init = SmoothScroll.__init__

    def _smooth_scroll_init(self, widget, *args, **kwargs):
        original_smooth_scroll_init(self, widget, *args, **kwargs)
        try:
            _register_managed_scroll_widget(widget)
            if not is_editor_smooth_scroll_target(widget):
                _apply_mode_to_delegate(self, get_page_smooth_scroll_enabled())
        except Exception:
            pass

    original_delegate_init = SmoothScrollDelegate.__init__

    def _delegate_init(self, parent, *args, **kwargs):
        original_delegate_init(self, parent, *args, **kwargs)
        try:
            _register_managed_scroll_widget(parent)
            if not is_editor_smooth_scroll_target(parent):
                _apply_mode_to_delegate(self, get_page_smooth_scroll_enabled())
        except Exception:
            pass

    SmoothScroll.__init__ = _smooth_scroll_init
    SmoothScrollDelegate.__init__ = _delegate_init
    _global_policy_installed = True


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
        from settings.appearance import peek_warmed_smooth_scroll_enabled

        return bool(peek_warmed_smooth_scroll_enabled())
    except Exception:
        return False


def get_editor_smooth_scroll_enabled() -> bool:
    """Читает пользовательскую настройку плавной прокрутки редакторов."""
    try:
        from settings.appearance import peek_warmed_editor_smooth_scroll_enabled

        return bool(peek_warmed_editor_smooth_scroll_enabled())
    except Exception:
        return False


def get_effective_editor_smooth_scroll_enabled(preference: bool | None = None) -> bool:
    """Возвращает итоговый флаг редакторов с учётом мастер-настройки анимаций."""
    try:
        from settings.appearance import peek_warmed_animations_enabled

        animations_enabled = bool(peek_warmed_animations_enabled())
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
