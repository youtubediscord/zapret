from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module

from PyQt6.QtWidgets import QWidget

from log.log import log

from ui.navigation.schema import get_page_route_key
from ui.page_names import PageName


@dataclass(frozen=True, slots=True)
class CreatedPage:
    page_name: PageName
    attr_name: str
    page: QWidget
    elapsed_ms: int


class UiPageFactory:
    """Создаёт page-экземпляры по канонической registry-схеме."""

    def __init__(self, window, page_class_specs: dict[PageName, tuple[str, str, str]]):
        self._window = window
        self._page_class_specs = dict(page_class_specs or {})

    @property
    def page_class_specs(self) -> dict[PageName, tuple[str, str, str]]:
        return self._page_class_specs

    def get_page_spec(self, page_name: PageName) -> tuple[str, str, str] | None:
        return self._page_class_specs.get(page_name)

    def create_page(self, page_name: PageName) -> CreatedPage | None:
        spec = self.get_page_spec(page_name)
        if spec is None:
            return None

        attr_name, module_name, class_name = spec

        import time as _time

        started_at = _time.perf_counter()
        try:
            module = import_module(module_name)
            page_cls = getattr(module, class_name)
            page = page_cls(self._window)
        except Exception as e:
            log(f"Ошибка lazy-инициализации страницы {page_name}: {e}", "ERROR")
            return None

        route_key = get_page_route_key(page_name)
        if route_key:
            page.setObjectName(route_key)
        elif not page.objectName():
            page.setObjectName(page.__class__.__name__)

        setter = getattr(page, "_set_page_registry_name", None)
        if callable(setter):
            setter(page_name)
        else:
            setattr(page, "_page_registry_name", page_name)

        elapsed_ms = int((_time.perf_counter() - started_at) * 1000)
        return CreatedPage(
            page_name=page_name,
            attr_name=attr_name,
            page=page,
            elapsed_ms=elapsed_ms,
        )


__all__ = ["CreatedPage", "UiPageFactory"]
