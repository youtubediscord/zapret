import unittest


class TelegramProxyUpstreamCatalogTest(unittest.TestCase):
    def test_bundled_socks_proxy_is_first_choice(self) -> None:
        from telegram_proxy.config.upstream_catalog import MANUAL_PRESET_ID, UpstreamCatalog

        catalog = UpstreamCatalog(
            build_presets=[
                {
                    "id": "bundled",
                    "name": "Готовый прокси",
                    "type": "socks5",
                    "host": "203.0.113.10",
                    "port": 443,
                    "username": "preset_user",
                    "password": "preset_password",
                }
            ]
        )

        self.assertEqual(catalog.choices[0]["id"], "bundled")
        self.assertEqual(catalog.choices[0]["name"], "Готовый прокси")
        self.assertEqual(catalog.choices[1]["id"], MANUAL_PRESET_ID)

    def test_enabling_first_bundled_socks_proxy_saves_only_preset_id(self) -> None:
        from telegram_proxy.config.upstream_catalog import UpstreamCatalog
        from telegram_proxy.ui.upstream_workflow import handle_upstream_toggle

        catalog = UpstreamCatalog(
            build_presets=[
                {
                    "id": "bundled",
                    "name": "Готовый прокси",
                    "type": "socks5",
                    "host": "203.0.113.10",
                    "port": 443,
                    "username": "preset_user",
                    "password": "preset_password",
                }
            ]
        )
        enabled_values = []
        saved_fields = []

        handle_upstream_toggle(
            checked=True,
            request_upstream_enabled=enabled_values.append,
            apply_upstream_preset_ui=lambda index: None,
            current_index=0,
            upstream_catalog=catalog,
            request_upstream_fields_save=lambda host, port, user, password, preset_id="": saved_fields.append(
                (host, port, user, password, preset_id)
            ),
        )

        self.assertEqual(enabled_values, [True])
        self.assertEqual(saved_fields, [("203.0.113.10", 443, "", "", "bundled")])

    def test_bundled_socks_credentials_are_resolved_from_catalog_not_settings(self) -> None:
        from telegram_proxy.config.settings import _settings_state_from_data, build_upstream_config
        from telegram_proxy.config.upstream_catalog import UpstreamCatalog

        catalog = UpstreamCatalog(
            build_presets=[
                {
                    "id": "bundled",
                    "name": "Готовый прокси",
                    "type": "socks5",
                    "host": "203.0.113.10",
                    "port": 443,
                    "username": "preset_user",
                    "password": "preset_password",
                }
            ]
        )
        data = {
            "telegram_proxy": {
                "upstream_enabled": True,
                "upstream_preset_id": "bundled",
                "upstream_host": "203.0.113.10",
                "upstream_port": 443,
                "upstream_user": "",
                "upstream_pass": "",
                "upstream_mode": "fallback",
            }
        }

        state = _settings_state_from_data(data, catalog)

        self.assertEqual(state.upstream_preset_id, "bundled")
        self.assertEqual(state.upstream_preset_index, 0)

        from unittest.mock import patch

        with (
            patch("telegram_proxy.config.upstream_catalog.UpstreamCatalog.load_from_runtime", return_value=catalog),
            patch("settings.store.read_settings", return_value=data),
        ):
            upstream = build_upstream_config()

        self.assertIsNotNone(upstream)
        self.assertEqual(upstream.username, "preset_user")
        self.assertEqual(upstream.password, "preset_password")


if __name__ == "__main__":
    unittest.main()
