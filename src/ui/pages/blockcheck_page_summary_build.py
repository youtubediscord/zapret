"""Build-helper DPI summary секции для Blockcheck page."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt


@dataclass(slots=True)
class BlockcheckSummaryWidgets:
    card: object
    badge: object
    detail: object
    dns_summary: object
    recommendation: object


def build_dpi_summary_section(
    *,
    tr_fn,
    settings_card_cls,
    qlabel_cls,
    body_label_cls,
    caption_label_cls,
    qt_namespace=Qt,
) -> BlockcheckSummaryWidgets:
    card = settings_card_cls(
        tr_fn("page.blockcheck.dpi_summary", "DPI Анализ")
    )
    card.setVisible(False)

    badge = qlabel_cls()
    badge.setAlignment(qt_namespace.AlignmentFlag.AlignCenter)
    badge.setFixedHeight(36)
    card.add_widget(badge)

    detail = body_label_cls()
    detail.setWordWrap(True)
    card.add_widget(detail)

    dns_summary = caption_label_cls()
    dns_summary.setWordWrap(True)
    card.add_widget(dns_summary)

    recommendation = body_label_cls()
    recommendation.setWordWrap(True)
    card.add_widget(recommendation)

    return BlockcheckSummaryWidgets(
        card=card,
        badge=badge,
        detail=detail,
        dns_summary=dns_summary,
        recommendation=recommendation,
    )
