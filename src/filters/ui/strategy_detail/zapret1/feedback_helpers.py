"""Feedback/loading helper'ы для страницы деталей стратегии Zapret 1."""

from __future__ import annotations

from filters.ui.strategy_detail.shared_detail_feedback import apply_detail_loading_indicator


def show_loading_feedback_v1(
    *,
    cleanup_in_progress: bool,
    spinner,
    success_icon,
) -> None:
    if cleanup_in_progress:
        return
    apply_detail_loading_indicator(
        spinner,
        success_icon,
        loading=True,
    )


def show_success_feedback_v1(
    *,
    cleanup_in_progress: bool,
    spinner,
    success_icon,
    success_timer,
    success_pixmap,
) -> None:
    if cleanup_in_progress:
        return
    apply_detail_loading_indicator(
        spinner,
        success_icon,
        success=True,
        success_pixmap=success_pixmap,
    )
    success_timer.start(1200)


def hide_success_feedback_v1(
    *,
    cleanup_in_progress: bool,
    spinner,
    success_icon,
) -> None:
    if cleanup_in_progress:
        return
    apply_detail_loading_indicator(
        spinner,
        success_icon,
        loading=False,
        success=False,
    )
