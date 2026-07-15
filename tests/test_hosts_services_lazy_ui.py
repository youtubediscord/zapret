from __future__ import annotations

import os
import unittest
from dataclasses import replace
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

    def _make_direct_catalog_plan(self, *, checked: bool) -> HostsServicesCatalogPlan:
        row = HostsServiceRowPlan(
            service_name="Direct Service",
            icon_name="fa5s.globe",
            icon_color=None,
            direct_only=True,
            available_profiles=["hosts"],
            profile_items=[("hosts", "Hosts")],
            selected_profile="hosts" if checked else None,
            toggle_enabled=True,
            toggle_checked=checked,
        )
        return HostsServicesCatalogPlan(
            groups=[
                HostsServiceGroupPlan(
                    title="Напрямую из hosts",
                    direct_only=True,
                    service_names=[row.service_name],
                    common_profiles=[("hosts", "Hosts")],
                    rows=[row],
                )
            ],
            new_selection={"Direct Service": "hosts"} if checked else {},
            selection_changed=True,
        )

    def test_dns_services_are_built_as_one_matrix_without_per_row_combos(self) -> None:
        page = self._make_page()

        HostsPage._build_services_selectors(page, self._make_catalog_plan())

        self.assertEqual(page.service_combos, {})
        self.assertIsNotNone(page._services_matrix_model)
        self.assertEqual(page._services_matrix_model.rowCount(), 13)
        self.assertEqual(page._services_matrix_model.columnCount(), 2)

    def test_current_selection_is_applied_to_matrix_model(self) -> None:
        page = self._make_page()
        page._service_dns_selection = {"Service 0": "zapret_dns"}

        HostsPage._build_services_selectors(page, self._make_catalog_plan())

        self.assertEqual(page._services_matrix_model.selected_profile_for_service("Service 0"), "zapret_dns")

    def test_rebuild_with_same_service_shape_updates_matrix_without_clearing_layout(self) -> None:
        page = self._make_page()
        first_plan = self._make_catalog_plan()
        HostsPage._build_services_selectors(page, first_plan)

        second_plan = replace(
            first_plan,
            new_selection={"Service 0": "zapret_dns"},
            selection_changed=True,
        )
        page._clear_layout = Mock(side_effect=AssertionError("layout не должен очищаться"))
        page._reset_services_runtime_bindings = Mock(side_effect=AssertionError("виджеты не должны пересоздаваться"))

        HostsPage._build_services_selectors(page, second_plan, sync_selection=True)

        page._clear_layout.assert_not_called()
        page._reset_services_runtime_bindings.assert_not_called()
        self.assertEqual(page._services_matrix_model.selected_profile_for_service("Service 0"), "zapret_dns")

    def test_catalog_refresh_does_not_clear_layout_before_new_plan_arrives(self) -> None:
        page = self._make_page()
        HostsPage._build_services_selectors(page, self._make_catalog_plan())

        page._clear_layout = Mock(side_effect=AssertionError("layout не должен очищаться до получения нового плана"))
        page._reset_services_runtime_bindings = Mock(
            side_effect=AssertionError("виджеты не должны сбрасываться до получения нового плана")
        )
        page._start_services_catalog_worker = Mock()

        HostsPage._refresh_services_selectors(page)

        page._start_services_catalog_worker.assert_called_once_with()

    def test_catalog_refresh_falls_back_to_rebuild_when_ui_not_mounted(self) -> None:
        page = self._make_page()
        page._services_ui_mounted = False
        page._rebuild_services_selectors = Mock()
        page._start_services_catalog_worker = Mock()

        HostsPage._refresh_services_selectors(page)

        page._rebuild_services_selectors.assert_called_once_with()
        page._start_services_catalog_worker.assert_not_called()

    def test_rebuild_with_same_direct_shape_updates_toggle_without_clearing_layout(self) -> None:
        page = self._make_page()
        first_plan = self._make_direct_catalog_plan(checked=False)
        HostsPage._build_services_selectors(page, first_plan, sync_selection=True)
        switch = page.service_combos["Direct Service"]
        self.assertFalse(switch.isChecked())

        second_plan = self._make_direct_catalog_plan(checked=True)
        page._clear_layout = Mock(side_effect=AssertionError("layout не должен очищаться"))
        page._reset_services_runtime_bindings = Mock(side_effect=AssertionError("виджеты не должны пересоздаваться"))

        HostsPage._build_services_selectors(page, second_plan, sync_selection=True)

        page._clear_layout.assert_not_called()
        page._reset_services_runtime_bindings.assert_not_called()
        self.assertTrue(switch.isChecked())


if __name__ == "__main__":
    unittest.main()
