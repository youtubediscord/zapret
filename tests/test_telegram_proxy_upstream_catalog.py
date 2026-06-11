import unittest


class TelegramProxyUpstreamCatalogTest(unittest.TestCase):
    def test_bundled_socks_proxy_is_first_choice(self) -> None:
        from telegram_proxy.config.upstream_catalog import MANUAL_PRESET_ID, UpstreamCatalog

        catalog_fixture = [
            {
                "id": "bundled",
                "name": "Готовый прокси",
                "type": "socks5",
                "host": "203.0.113.10",
                "port": 443,
                "username": "preset_user",
                "password": "preset_password",
                "tls": True,
                "tls_server_name": "proxy.example.test",
            }
        ]
        catalog = UpstreamCatalog(build_presets=catalog_fixture)

        self.assertEqual(catalog.choices[0]["id"], "bundled")
        self.assertEqual(catalog.choices[0]["name"], "Готовый прокси")
        self.assertEqual(set(catalog.choices[0]), {"id", "name", "type"})
        self.assertNotIn("host", catalog.choices[0])
        self.assertNotIn("username", catalog.choices[0])
        self.assertNotIn("password", catalog.choices[0])
        self.assertEqual(catalog.choices[1]["id"], MANUAL_PRESET_ID)

    def test_enabling_first_bundled_socks_proxy_saves_only_preset_id(self) -> None:
        from telegram_proxy.config.upstream_catalog import UpstreamCatalog
        from telegram_proxy.ui.upstream_workflow import handle_upstream_toggle

        catalog_fixture = [
            {
                "id": "bundled",
                "name": "Готовый прокси",
                "type": "socks5",
                "host": "203.0.113.10",
                "port": 443,
                "username": "preset_user",
                "password": "preset_password",
                "tls": True,
                "tls_server_name": "proxy.example.test",
            }
        ]
        catalog = UpstreamCatalog(build_presets=catalog_fixture)
        enabled_values = []
        saved_presets = []

        handle_upstream_toggle(
            checked=True,
            request_upstream_enabled=enabled_values.append,
            apply_upstream_preset_ui=lambda index: None,
            current_index=0,
            upstream_catalog=catalog,
            request_upstream_preset_save=saved_presets.append,
        )

        self.assertEqual(enabled_values, [True])
        self.assertEqual(saved_presets, ["bundled"])

    def test_bundled_socks_credentials_are_resolved_from_catalog_not_settings(self) -> None:
        from telegram_proxy.config.settings import (
            DEFAULT_UPSTREAM_PORT,
            _settings_state_from_data,
            build_upstream_config,
            load_upstream_test_target,
            set_manual_upstream,
            set_upstream_preset,
        )
        from telegram_proxy.config.upstream_catalog import UpstreamCatalog, UpstreamPresetResolver

        catalog_fixture = [
            {
                "id": "bundled",
                "name": "Готовый прокси",
                "type": "socks5",
                "host": "203.0.113.10",
                "port": 443,
                "username": "preset_user",
                "password": "preset_password",
                "tls": True,
                "tls_server_name": "proxy.example.test",
            }
        ]
        catalog = UpstreamCatalog(build_presets=catalog_fixture)
        data = {
            "telegram_proxy": {
                "upstream_enabled": True,
                "upstream_preset_id": "bundled",
                "upstream_host": "",
                "upstream_port": DEFAULT_UPSTREAM_PORT,
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
            patch(
                "telegram_proxy.config.settings.UpstreamPresetResolver.load_from_runtime",
                return_value=UpstreamPresetResolver(catalog_fixture),
            ),
            patch("settings.store.read_settings", return_value=data),
        ):
            upstream = build_upstream_config()

        self.assertIsNotNone(upstream)
        self.assertEqual(upstream.host, "203.0.113.10")
        self.assertEqual(upstream.port, 443)
        self.assertEqual(upstream.username, "preset_user")
        self.assertEqual(upstream.password, "preset_password")
        self.assertTrue(upstream.tls)
        self.assertEqual(upstream.tls_server_name, "proxy.example.test")
        self.assertFalse(upstream.tls_verify)

        saved = []

        def remember(name):
            return lambda value: saved.append((name, value))

        with (
            patch("settings.store.set_tg_proxy_upstream_host", remember("host")),
            patch("settings.store.set_tg_proxy_upstream_port", remember("port")),
            patch("settings.store.set_tg_proxy_upstream_preset_id", remember("preset_id")),
            patch("settings.store.set_tg_proxy_upstream_user", remember("user")),
            patch("settings.store.set_tg_proxy_upstream_pass", remember("password")),
        ):
            set_upstream_preset("bundled")

        self.assertEqual(
            saved,
            [
                ("preset_id", "bundled"),
                ("host", ""),
                ("port", DEFAULT_UPSTREAM_PORT),
                ("user", ""),
                ("password", ""),
            ],
        )

        with (
            patch(
                "telegram_proxy.config.settings.UpstreamPresetResolver.load_from_runtime",
                return_value=UpstreamPresetResolver(catalog_fixture),
            ),
            patch("settings.store.read_settings", return_value=data),
        ):
            self.assertEqual(
                load_upstream_test_target(),
                (
                    "203.0.113.10",
                    443,
                    "preset_user",
                    "preset_password",
                    True,
                    "proxy.example.test",
                    False,
                ),
            )

        saved = []
        with (
            patch("settings.store.set_tg_proxy_upstream_host", remember("host")),
            patch("settings.store.set_tg_proxy_upstream_port", remember("port")),
            patch("settings.store.set_tg_proxy_upstream_preset_id", remember("preset_id")),
            patch("settings.store.set_tg_proxy_upstream_user", remember("user")),
            patch("settings.store.set_tg_proxy_upstream_pass", remember("password")),
        ):
            set_manual_upstream("198.51.100.20", 1081, "manual_user", "manual_pass")

        self.assertEqual(
            saved,
            [
                ("preset_id", ""),
                ("host", "198.51.100.20"),
                ("port", 1081),
                ("user", "manual_user"),
                ("password", "manual_pass"),
            ],
        )

    def test_empty_enabled_upstream_uses_first_bundled_socks_proxy(self) -> None:
        from telegram_proxy.config.settings import (
            DEFAULT_UPSTREAM_PORT,
            build_upstream_config,
            load_upstream_test_target,
        )
        from telegram_proxy.config.upstream_catalog import UpstreamPresetResolver

        catalog_fixture = [
            {
                "id": "first",
                "name": "Первый прокси",
                "type": "socks5",
                "host": "203.0.113.10",
                "port": 443,
                "username": "preset_user",
                "password": "preset_password",
                "tls": True,
            }
        ]
        data = {
            "telegram_proxy": {
                "upstream_enabled": True,
                "upstream_preset_id": "",
                "upstream_host": "",
                "upstream_port": DEFAULT_UPSTREAM_PORT,
                "upstream_user": "",
                "upstream_pass": "",
                "upstream_mode": "always",
            }
        }

        from unittest.mock import patch

        with (
            patch(
                "telegram_proxy.config.settings.UpstreamPresetResolver.load_from_runtime",
                return_value=UpstreamPresetResolver(catalog_fixture),
            ),
            patch("settings.store.read_settings", return_value=data),
        ):
            upstream = build_upstream_config()
            test_target = load_upstream_test_target()

        self.assertIsNotNone(upstream)
        self.assertEqual(upstream.host, "203.0.113.10")
        self.assertEqual(upstream.port, 443)
        self.assertEqual(upstream.username, "preset_user")
        self.assertEqual(upstream.password, "preset_password")
        self.assertTrue(upstream.tls)
        self.assertEqual(
            test_target,
            ("203.0.113.10", 443, "preset_user", "preset_password", True, "", False),
        )


if __name__ == "__main__":
    unittest.main()
