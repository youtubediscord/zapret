from __future__ import annotations

from ui.pages.zapret2.strategy_detail_page import StrategyDetailPage
from ui.text_catalog import tr as tr_catalog


class OrchestraZapret2StrategyDetailPage(StrategyDetailPage):
    def on_page_activated(self, first_show: bool) -> None:
        super().on_page_activated(first_show)
        try:
            self.title_label.setText(
                tr_catalog(
                    "page.z2_orchestra_strategy_detail.title",
                    language=getattr(self, "_ui_language", None),
                    default="Детали стратегии Orchestra Z2",
                )
            )
        except Exception:
            pass

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        try:
            self.title_label.setText(
                tr_catalog(
                    "page.z2_orchestra_strategy_detail.title",
                    language=language,
                    default="Детали стратегии Orchestra Z2",
                )
            )
        except Exception:
            pass
