import unittest


class TintedAppearanceSettingsTests(unittest.TestCase):
    def test_normalize_appearance_keeps_full_tinted_intensity_range(self) -> None:
        from settings.normalize import normalize_appearance

        normalized = normalize_appearance({"tinted_background_intensity": 80})

        self.assertEqual(normalized["tinted_background_intensity"], 80)

    def test_warmed_tinted_settings_keep_full_tinted_intensity_range(self) -> None:
        import settings.appearance as appearance_settings

        self.addCleanup(appearance_settings.clear_warmed_tinted_settings_cache)
        appearance_settings.store_warmed_tinted_settings(False, True, 80)

        plan = appearance_settings.peek_warmed_tinted_settings()

        self.assertIsNotNone(plan)
        self.assertEqual(plan.tinted_intensity, 80)


if __name__ == "__main__":
    unittest.main()
