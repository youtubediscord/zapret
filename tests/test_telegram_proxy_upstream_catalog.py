import unittest


class TelegramProxyUpstreamCatalogTest(unittest.TestCase):
    def test_bundled_socks_proxy_is_first_choice(self) -> None:
        from telegram_proxy.config.upstream_catalog import MANUAL_PRESET_ID, UpstreamCatalog

        catalog = UpstreamCatalog(
            build_presets=[
                {
                    "id": "uk",
                    "name": "Великобритания",
                    "type": "socks5",
                    "host": "144.31.213.169",
                    "port": 443,
                    "username": "uk_proxy",
                    "password": "secret",
                }
            ]
        )

        self.assertEqual(catalog.choices[0]["id"], "uk")
        self.assertEqual(catalog.choices[0]["name"], "Великобритания")
        self.assertEqual(catalog.choices[1]["id"], MANUAL_PRESET_ID)

    def test_enabling_first_bundled_socks_proxy_saves_its_fields(self) -> None:
        from telegram_proxy.config.upstream_catalog import UpstreamCatalog
        from telegram_proxy.ui.upstream_workflow import handle_upstream_toggle

        catalog = UpstreamCatalog(
            build_presets=[
                {
                    "id": "uk",
                    "name": "Великобритания",
                    "type": "socks5",
                    "host": "144.31.213.169",
                    "port": 443,
                    "username": "uk_proxy",
                    "password": "secret",
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
            request_upstream_fields_save=lambda host, port, user, password: saved_fields.append(
                (host, port, user, password)
            ),
        )

        self.assertEqual(enabled_values, [True])
        self.assertEqual(saved_fields, [("144.31.213.169", 443, "uk_proxy", "secret")])


if __name__ == "__main__":
    unittest.main()
