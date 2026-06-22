from __future__ import annotations

import os
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme

from hosts.page_plans import HostsServiceGroupPlan, HostsServiceRowPlan
from hosts.ui.services_matrix import (
    HostsServicesMatrixCanvas,
    HostsServicesMatrixDelegate,
    HostsServicesMatrixModel,
    build_hosts_services_matrix,
)


class HostsServicesMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        setTheme(Theme.DARK)

    def test_dns_profile_columns_use_fixed_width_instead_of_content_resize(self) -> None:
        rows = [
            HostsServiceRowPlan(
                service_name=f"Service {idx}",
                icon_name="fa5s.globe",
                icon_color=None,
                direct_only=False,
                available_profiles=["zapret_dns"],
                profile_items=[("zapret_dns", "Zapret DNS")],
                selected_profile=None,
                toggle_enabled=True,
                toggle_checked=False,
            )
            for idx in range(4)
        ]
        group = HostsServiceGroupPlan(
            title="Видео",
            direct_only=False,
            service_names=[row.service_name for row in rows],
            common_profiles=[("zapret_dns", "Zapret DNS")],
            rows=rows,
        )

        widgets = build_hosts_services_matrix(
            [group],
            off_label="Откл.",
            on_profile_selected=Mock(),
            on_bulk_profile_selected=Mock(),
        )

        self.assertEqual(widgets.view.profile_column_width(), 88)
        self.assertGreaterEqual(widgets.view.minimumWidth(), 260 + 88 * (widgets.model.columnCount() - 1))

    def test_service_rows_expose_icon_metadata_for_painter(self) -> None:
        group = HostsServiceGroupPlan(
            title="ИИ",
            direct_only=False,
            service_names=["ChatGPT"],
            common_profiles=[("zapret_dns", "Zapret DNS")],
            rows=[
                HostsServiceRowPlan(
                    service_name="ChatGPT",
                    icon_name="mdi.robot",
                    icon_color="#10a37f",
                    direct_only=False,
                    available_profiles=["zapret_dns"],
                    profile_items=[("zapret_dns", "Zapret DNS")],
                    selected_profile="zapret_dns",
                    toggle_enabled=True,
                    toggle_checked=False,
                )
            ],
        )

        model = HostsServicesMatrixModel([group], off_label="Откл.")

        self.assertEqual(model.data(model.index(1, 0), model.IconNameRole), "mdi.robot")
        self.assertEqual(model.data(model.index(1, 0), model.IconColorRole), "#10a37f")

    def test_matrix_uses_lightweight_delegate_without_item_stylesheet(self) -> None:
        group = HostsServiceGroupPlan(
            title="ИИ",
            direct_only=False,
            service_names=["ChatGPT"],
            common_profiles=[("zapret_dns", "Zapret DNS")],
            rows=[
                HostsServiceRowPlan(
                    service_name="ChatGPT",
                    icon_name="mdi.robot",
                    icon_color="#10a37f",
                    direct_only=False,
                    available_profiles=["zapret_dns"],
                    profile_items=[("zapret_dns", "Zapret DNS")],
                    selected_profile=None,
                    toggle_enabled=True,
                    toggle_checked=False,
                )
            ],
        )

        widgets = build_hosts_services_matrix(
            [group],
            off_label="Откл.",
            on_profile_selected=Mock(),
            on_bulk_profile_selected=Mock(),
        )

        self.assertIsInstance(widgets.view, HostsServicesMatrixCanvas)
        self.assertNotIn("QTableView#hostsServicesMatrix::item", widgets.view.styleSheet())
        unselected = widgets.view.delegate().dot_colors(selected=False, available=True)
        self.assertGreater(unselected[0].lightness(), 120)

    def test_matrix_does_not_use_qtable_selection_highlight(self) -> None:
        group = HostsServiceGroupPlan(
            title="ИИ",
            direct_only=False,
            service_names=["Windsurf"],
            common_profiles=[("zapret_dns", "Zapret DNS")],
            rows=[
                HostsServiceRowPlan(
                    service_name="Windsurf",
                    icon_name="fa5s.wind",
                    icon_color="#25d9d1",
                    direct_only=False,
                    available_profiles=["zapret_dns"],
                    profile_items=[("zapret_dns", "Zapret DNS")],
                    selected_profile="zapret_dns",
                    toggle_enabled=True,
                    toggle_checked=False,
                )
            ],
        )

        widgets = build_hosts_services_matrix(
            [group],
            off_label="Откл.",
            on_profile_selected=Mock(),
            on_bulk_profile_selected=Mock(),
        )

        self.assertEqual(widgets.view.focusPolicy(), Qt.FocusPolicy.NoFocus)

    def test_delegate_reuses_cached_dot_pixmaps_for_scroll_painting(self) -> None:
        delegate = HostsServicesMatrixDelegate()

        first = delegate.dot_pixmap(selected=False, available=True)
        second = delegate.dot_pixmap(selected=False, available=True)
        selected = delegate.dot_pixmap(selected=True, available=True)

        self.assertFalse(first.isNull())
        self.assertEqual(first.cacheKey(), second.cacheKey())
        self.assertNotEqual(first.cacheKey(), selected.cacheKey())

    def test_canvas_limits_repaint_to_visible_rows(self) -> None:
        rows = [
            HostsServiceRowPlan(
                service_name=f"Service {idx}",
                icon_name="fa5s.globe",
                icon_color=None,
                direct_only=False,
                available_profiles=["zapret_dns"],
                profile_items=[("zapret_dns", "Zapret DNS")],
                selected_profile=None,
                toggle_enabled=True,
                toggle_checked=False,
            )
            for idx in range(40)
        ]
        group = HostsServiceGroupPlan(
            title="Остальные",
            direct_only=False,
            service_names=[row.service_name for row in rows],
            common_profiles=[("zapret_dns", "Zapret DNS")],
            rows=rows,
        )

        widgets = build_hosts_services_matrix(
            [group],
            off_label="Откл.",
            on_profile_selected=Mock(),
            on_bulk_profile_selected=Mock(),
        )

        visible_rows = widgets.view.visible_rows_for_rect(QRect(0, 120, 900, 180))

        self.assertLess(len(visible_rows), widgets.model.rowCount())
        self.assertGreater(len(visible_rows), 0)

    def test_canvas_clicks_keep_profile_selection_callbacks(self) -> None:
        row = HostsServiceRowPlan(
            service_name="ChatGPT",
            icon_name="mdi.robot",
            icon_color="#10a37f",
            direct_only=False,
            available_profiles=["zapret_dns"],
            profile_items=[("zapret_dns", "Zapret DNS")],
            selected_profile=None,
            toggle_enabled=True,
            toggle_checked=False,
        )
        group = HostsServiceGroupPlan(
            title="ИИ",
            direct_only=False,
            service_names=[row.service_name],
            common_profiles=[("zapret_dns", "Zapret DNS")],
            rows=[row],
        )
        on_profile = Mock()
        on_bulk = Mock()

        widgets = build_hosts_services_matrix(
            [group],
            off_label="Откл.",
            on_profile_selected=on_profile,
            on_bulk_profile_selected=on_bulk,
        )
        widgets.view.resize(widgets.view.minimumWidth(), widgets.view.sizeHint().height())
        widgets.view.show()
        self._app.processEvents()

        profile_cell = QRect(
            widgets.view._column_rect(2).left(),
            widgets.view._row_tops[1],
            widgets.view.profile_column_width(),
            widgets.view._row_heights[1],
        )
        QTest.mouseClick(widgets.view, Qt.MouseButton.LeftButton, pos=profile_cell.center())
        header_point = QPoint(widgets.view._column_rect(2).center().x(), widgets.view._HEADER_HEIGHT // 2)
        QTest.mouseClick(widgets.view, Qt.MouseButton.LeftButton, pos=header_point)

        on_profile.assert_called_once_with("ChatGPT", "zapret_dns")
        on_bulk.assert_called_once_with(["ChatGPT"], "zapret_dns")


if __name__ == "__main__":
    unittest.main()
