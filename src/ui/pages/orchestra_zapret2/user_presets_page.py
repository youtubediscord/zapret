"""Orchestra Zapret2 user presets page."""

from __future__ import annotations

from core.services import get_user_presets_runtime_service
from ui.pages.zapret2.user_presets_page import BaseZapret2UserPresetsPage

from .user_presets_page_controller import OrchestraZapret2UserPresetsPageController


class OrchestraZapret2UserPresetsPage(BaseZapret2UserPresetsPage):
    def _build_controller(self):
        return OrchestraZapret2UserPresetsPageController()

    def _build_runtime_service(self):
        return get_user_presets_runtime_service("preset_orchestra_zapret2")

    def _current_breadcrumb_title(self) -> str:
        return self._tr("page.z2_user_presets.title.orchestra", "Мои пресеты (Оркестратор Z2)")

    def _apply_mode_labels(self) -> None:
        try:
            self.title_label.setText(
                self._tr("page.z2_user_presets.title.orchestra", "Мои пресеты (Оркестратор Z2)")
            )
            if self.subtitle_label is not None:
                self.subtitle_label.setText(
                    self._tr(
                        "page.z2_user_presets.subtitle.orchestra",
                        "Управление пресетами для режима direct_zapret2_orchestra",
                    )
                )
            self._rebuild_breadcrumb()
        except Exception:
            pass
