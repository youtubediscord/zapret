from __future__ import annotations

import os
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget

from hosts.page_plans import (
    HostsServiceGroupPlan,
    HostsServiceRowPlan,
    HostsServicesCatalogPlan,
)
from hosts.ui.page import HostsPage


class HostsServicesLazyUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _make_page(self) -> HostsPage:
        page = HostsPage.__new__(HostsPage)
        page._ui_language = "ru"
        page._services_test_container = QWidget()
        page._services_layout = QVBoxLayout(page._services_test_container)
        page._service_dns_selection = {}
        page.service_combos = {}
        page.service_icon_labels = {}
        page.service_icon_names = {}
        page.service_name_labels = {}
        page.service_icon_base_colors = {}
        page._services_section_title_labels = []
        page._service_group_title_labels = []
        page._service_group_chips_scrolls = []
        page._service_group_chip_buttons = []
        page._services_matrix_model = None
        page._services_matrix_view = None
        page._building_services_ui = False
        page._request_user_selection_save = Mock()
        page._update_profile_row_visual = Mock()
        page._log_ui_timing = Mock()
        page._apply_current_selection = Mock()
        return page

    def _make_catalog_plan(self) -> HostsServicesCatalogPlan:
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
            for idx in range(12)
        ]
        return HostsServicesCatalogPlan(
            groups=[
                HostsServiceGroupPlan(
                    title="Видео",
                    direct_only=False,
                    service_names=[row.service_name for row in rows],
                    common_profiles=[("zapret_dns", "Zapret DNS")],
                    rows=rows,
                )
            ],
            new_selection={},
            selection_changed=False,
        )

    def test_dns_services_are_built_as_one_matrix_without_per_row_combos(self) -> None:
        page = self._make_page()

        HostsPage._build_services_selectors(page, self._make_catalog_plan())

        self.assertEqual(page.service_combos, {})
        self.assertIsNotNone(page._services_matrix_model)
        self.assertEqual(page._services_matrix_model.rowCount(), 13)
        self.assertEqual(page._services_matrix_model.columnCount(), 3)

    def test_current_selection_is_applied_to_matrix_model(self) -> None:
        page = self._make_page()
        page._service_dns_selection = {"Service 0": "zapret_dns"}

        HostsPage._build_services_selectors(page, self._make_catalog_plan())

        self.assertEqual(page._services_matrix_model.selected_profile_for_service("Service 0"), "zapret_dns")


if __name__ == "__main__":
    unittest.main()
