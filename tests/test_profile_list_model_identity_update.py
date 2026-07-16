from __future__ import annotations

import os
import unittest
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication


def _profile_row(key: str, name: str, *, persistent_key: str = "") -> dict[str, Any]:
    return {
        "kind": "profile",
        "key": key,
        "persistent_key": persistent_key or key,
        "display_name": name,
        "group": "common",
        "enabled": True,
        "in_preset": True,
    }


def _folder_row(group: str) -> dict[str, Any]:
    return {
        "kind": "folder",
        "group": group,
        "group_name": group.title(),
        "collapsed": False,
        "count": 1,
    }


class ProfileListModelIdentityUpdateTests(unittest.TestCase):
    """AC1/AC2: смена stable identity строк «на месте» применяется через
    dataChanged без reset; несовпадение kind по позициям остаётся reset-ом."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _model_with_rows(self, rows: list[dict[str, Any]]):
        from profile.ui.profile_list_model import ProfileListModel

        model = ProfileListModel()
        model.beginResetModel()
        model._set_rows(list(rows))
        model.endResetModel()

        resets: list[int] = []
        changed_rows: list[int] = []
        model.modelAboutToBeReset.connect(lambda: resets.append(1))
        model.dataChanged.connect(
            lambda top_left, bottom_right, _roles=(): changed_rows.extend(
                range(top_left.row(), bottom_right.row() + 1)
            )
        )
        return model, resets, changed_rows

    def test_in_place_identity_change_emits_data_changed_without_reset(self) -> None:
        rows = [_profile_row(f"profile-{index}", f"Profile {index}") for index in range(5)]
        model, resets, changed_rows = self._model_with_rows(rows)

        next_rows = list(rows)
        # Правка имени меняет persistent_key: та же позиция, новая идентичность.
        next_rows[2] = _profile_row("profile-2-renamed", "Renamed profile")

        # Санкционированное изменение семантики (fix P4, задача
        # profile-list-architecture-refactor): раньше тест закреплял in-place
        # применение при allow_structural=False, но смена идентичности — это
        # структурная правка, при смене фильтров она обязана вести к reset.
        # In-place без reset допустим только при allow_structural=True.
        applied = model._apply_rows_update(next_rows, commit=lambda: None, allow_structural=True)

        self.assertTrue(applied, "in-place смена идентичности обязана применяться без reset")
        self.assertEqual(resets, [], "modelReset не должен эмититься")
        self.assertEqual(sorted(set(changed_rows)), [2], "dataChanged обязан покрыть изменившуюся строку")
        self.assertEqual(model.rowCount(), 5)
        self.assertEqual(model._rows, next_rows)

    def test_in_place_identity_change_requires_allow_structural(self) -> None:
        """Регрессия P4: список «той же формы» с другими идентичностями при
        allow_structural=False (смена фильтров) обязан уйти в reset — иначе
        «новый список» унаследует прокрутку старого."""
        rows = [_profile_row(f"profile-{index}", f"Profile {index}") for index in range(5)]
        model, resets, changed_rows = self._model_with_rows(rows)

        next_rows = list(rows)
        next_rows[2] = _profile_row("profile-2-renamed", "Renamed profile")

        applied = model._apply_rows_update(next_rows, commit=lambda: None, allow_structural=False)
        self.assertFalse(applied, "при allow_structural=False in-place ветка запрещена")
        self.assertEqual(changed_rows, [])

        model._apply_rows_or_reset(next_rows, commit=lambda: None, allow_structural=False)
        self.assertEqual(resets, [1], "смена идентичности при смене фильтров — полный reset")
        self.assertEqual(model._rows, next_rows)

    def test_data_only_update_stays_in_place_without_allow_structural(self) -> None:
        """Равенство old_ids == next_ids — data-only правка: остаётся выше
        гейта allow_structural и применяется dataChanged без reset."""
        rows = [_profile_row(f"profile-{index}", f"Profile {index}") for index in range(4)]
        model, resets, changed_rows = self._model_with_rows(rows)

        next_rows = list(rows)
        next_rows[1] = dict(next_rows[1], display_name="Same identity, new name")

        applied = model._apply_rows_update(next_rows, commit=lambda: None, allow_structural=False)
        self.assertTrue(applied)
        self.assertEqual(resets, [])
        self.assertEqual(sorted(set(changed_rows)), [1])
        self.assertEqual(model._rows, next_rows)

    def test_in_place_identity_change_covers_all_changed_rows(self) -> None:
        rows = [_profile_row(f"profile-{index}", f"Profile {index}") for index in range(6)]
        model, resets, changed_rows = self._model_with_rows(rows)

        next_rows = list(rows)
        next_rows[1] = _profile_row("profile-1-renamed", "Renamed 1")
        next_rows[4] = _profile_row("profile-4-renamed", "Renamed 4")

        applied = model._apply_rows_update(next_rows, commit=lambda: None, allow_structural=True)

        self.assertTrue(applied)
        self.assertEqual(resets, [])
        self.assertEqual(sorted(set(changed_rows)), [1, 4])
        self.assertEqual(model.rowCount(), 6)
        self.assertEqual(model._rows, next_rows)

    def test_apply_rows_or_reset_uses_data_changed_for_identity_change(self) -> None:
        rows = [_folder_row("common"), *(_profile_row(f"profile-{index}", f"Profile {index}") for index in range(4))]
        model, resets, changed_rows = self._model_with_rows(rows)

        next_rows = list(rows)
        next_rows[3] = _profile_row("profile-2-renamed", "Renamed profile")

        # Санкционированное изменение семантики (fix P4): in-place ветка
        # работает только при allow_structural=True (фильтры не менялись).
        model._apply_rows_or_reset(next_rows, commit=lambda: None, allow_structural=True)

        self.assertEqual(resets, [], "reset не нужен: строка сменила идентичность на месте")
        self.assertEqual(sorted(set(changed_rows)), [3])
        self.assertEqual(model._rows, next_rows)

    def test_kind_mismatch_still_resets_model(self) -> None:
        rows = [_profile_row(f"profile-{index}", f"Profile {index}") for index in range(4)]
        model, resets, _changed_rows = self._model_with_rows(rows)

        next_rows = list(rows)
        # Папка на месте профиля: kind по позиции не совпадает, изменение не
        # сводится к insert/remove/move — обязан быть reset.
        next_rows[1] = _folder_row("video")

        applied = model._apply_rows_update(next_rows, commit=lambda: None, allow_structural=True)
        self.assertFalse(applied, "несовпадение kind по позиции не in-place правка")

        model._apply_rows_or_reset(next_rows, commit=lambda: None, allow_structural=True)
        self.assertEqual(resets, [1], "ожидается полный reset модели")
        self.assertEqual(model._rows, next_rows)

    def test_permutation_of_same_identities_is_not_in_place_change(self) -> None:
        from profile.ui.profile_list_model import _is_in_place_identity_change, _stable_row_identity

        rows = [_profile_row(f"profile-{index}", f"Profile {index}") for index in range(4)]
        swapped = [rows[1], rows[0], rows[2], rows[3]]
        old_ids = [_stable_row_identity(row) for row in rows]
        next_ids = [_stable_row_identity(row) for row in swapped]

        # Перестановка прежних идентичностей — работа move-детектора,
        # in-place ветка не должна её перехватывать.
        self.assertFalse(_is_in_place_identity_change(old_ids, next_ids))


if __name__ == "__main__":
    unittest.main()
