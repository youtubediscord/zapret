from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StatefulLayerDecision:
    key: str
    target: str
    decision: str
    rationale: str


def build_intentionally_stateful_inventory() -> tuple[StatefulLayerDecision, ...]:
    """Возвращает осознанно оставленные stateful-слои архитектуры.

    Этот список нужен не для оправдания legacy, а наоборот:
    чтобы после cutover было явно видно, какие слои остаются stateful
    по архитектурной необходимости, а не по инерции старого дизайна.
    """

    return (
        StatefulLayerDecision(
            key="update_page_controller",
            target="updater.update_page_controller.UpdatePageController",
            decision="intentionally_stateful",
            rationale=(
                "Держит живой update runtime: найденное обновление, текущую проверку, "
                "скачивание и жизненный цикл worker-потоков."
            ),
        ),
        StatefulLayerDecision(
            key="direct_user_presets",
            target="ui.pages.direct_user_presets_page_controller.DirectUserPresetsPageController",
            decision="intentionally_config_driven",
            rationale=(
                "Остаётся config-driven controller: собирает page API bundle вокруг launch method, "
                "selection key, hierarchy scope и direct preset facade."
            ),
        ),
        StatefulLayerDecision(
            key="window_close_controller",
            target="ui.window_close_controller.WindowCloseController",
            decision="stable_window_infrastructure",
            rationale=(
                "Это отдельный стабильный window lifecycle слой: решает пользовательский сценарий закрытия "
                "главного окна и не относится к page-level cutover."
            ),
        ),
        StatefulLayerDecision(
            key="window_geometry_controller",
            target="ui.window_geometry_controller.WindowGeometryController",
            decision="stable_window_infrastructure",
            rationale=(
                "Это отдельный стабильный window runtime слой: владеет геометрией окна, restore/persist "
                "логикой и состоянием maximized/minimized."
            ),
        ),
        StatefulLayerDecision(
            key="window_notification_controller",
            target="ui.window_notification_controller.WindowNotificationController",
            decision="stable_window_infrastructure",
            rationale=(
                "Это отдельный стабильный notification/runtime слой: владеет очередью уведомлений, "
                "дедупликацией и startup display orchestration."
            ),
        ),
        StatefulLayerDecision(
            key="telegram_proxy_manager",
            target="telegram_proxy.manager.TelegramProxyManager",
            decision="singleton_runtime_manager",
            rationale=(
                "Это отдельный singleton runtime manager: держит живой proxy controller, "
                "stats polling и lifecycle фонового прокси-потока."
            ),
        ),
    )
