from __future__ import annotations

import unittest


class TelegramProxyUiTextsTests(unittest.TestCase):
    def test_settings_text_plan_matches_clean_main_scenario(self) -> None:
        from telegram_proxy.ui import text_plan

        plan = text_plan.TELEGRAM_PROXY_SETTINGS_TEXT

        self.assertEqual(
            plan.page_subtitle,
            "Локальный прокси для Telegram. Используйте его, если Telegram подключается нестабильно.",
        )
        self.assertEqual(plan.setup_title, "Подключить Telegram")
        self.assertEqual(
            plan.setup_description,
            "Откройте ссылку. Telegram сам предложит добавить прокси. "
            "Если Telegram не открылся, скопируйте ссылку и отправьте её себе в чат.",
        )
        self.assertEqual(
            plan.setup_fallback,
            "Если ничего не помогает — скачайте Zastogram.",
        )
        self.assertEqual(plan.upstream_title, "Дополнительно")
        self.assertEqual(plan.upstream_toggle_title, "Внешний прокси")
        self.assertEqual(
            plan.proxy_mode_description,
            "SOCKS5 — основной режим. MTProxy нужен для secret, Fake TLS и Cloudflare-сценариев.",
        )
        self.assertEqual(
            plan.upstream_toggle_description,
            "Резервный SOCKS5, если часть серверов Telegram не отвечает.",
        )

        joined = "\n".join(plan)
        self.assertNotIn("ПЕРЕЗАПУСТИТЬ", joined)
        self.assertNotIn("upstream", joined)
        self.assertNotIn("WSS relay", joined)

    def test_setup_hint_is_shown_under_setup_buttons(self) -> None:
        import inspect
        from telegram_proxy.ui import settings_build

        source = inspect.getsource(settings_build.build_telegram_proxy_settings_panel)

        self.assertIn("setup_desc_label", source)
        self.assertIn("layout.addWidget(setup_fallback_label)", source)

    def test_cloudflare_settings_panel_exposes_test_and_copy_actions(self) -> None:
        import inspect
        from telegram_proxy.ui import settings_build

        signature = inspect.signature(settings_build.build_telegram_proxy_settings_panel)
        source = inspect.getsource(settings_build)

        self.assertIn("on_test_cloudflare", signature.parameters)
        self.assertIn("on_copy_cloudflare_dns", signature.parameters)
        self.assertIn("on_test_cloudflare_worker", signature.parameters)
        self.assertIn("on_copy_cloudflare_worker_code", signature.parameters)
        self.assertIn("on_copy_fake_tls_nginx_config", signature.parameters)
        self.assertIn("cloudflare_test_btn", source)
        self.assertIn("cloudflare_dns_btn", source)
        self.assertIn("cloudflare_worker_test_btn", source)
        self.assertIn("cloudflare_worker_code_btn", source)
        self.assertIn("fake_tls_nginx_btn", source)
        self.assertIn("Проверить", source)
        self.assertIn("DNS", source)
        self.assertIn("Код Worker", source)
        self.assertIn("Nginx", source)

    def test_advanced_settings_panel_exposes_all_technical_options(self) -> None:
        import inspect
        from telegram_proxy.ui import page, settings_build

        build_source = inspect.getsource(settings_build)
        page_source = inspect.getsource(page.TelegramProxyPage)

        self.assertIn("advanced_toggle", build_source)
        self.assertIn("advanced_card", build_source)
        self.assertIn("fake_tls_domain_edit", build_source)
        self.assertIn("proxy_protocol_toggle", build_source)
        self.assertIn("dc_ip_edit", build_source)
        self.assertIn("pool_size_spin", build_source)
        self.assertIn("buffer_kb_spin", build_source)
        self.assertIn("Cloudflare", build_source)
        self.assertIn("Cloudflare Worker", build_source)
        self.assertIn("Nginx", build_source)

        self.assertIn("_apply_advanced_settings_ui", page_source)
        self.assertIn("_advanced_settings_should_open", page_source)
        self.assertIn("_on_pool_size_changed", page_source)
        self.assertIn("_on_buffer_kb_changed", page_source)

    def test_advanced_texts_are_plain_and_not_shown_as_main_scenario(self) -> None:
        from telegram_proxy.ui import text_plan

        plan = text_plan.TELEGRAM_PROXY_SETTINGS_TEXT

        self.assertEqual(plan.advanced_title, "Продвинутый режим")
        self.assertIn("Cloudflare", plan.advanced_description)
        self.assertIn("Fake TLS", plan.advanced_description)
        self.assertEqual(plan.performance_title, "Производительность")

    def test_proxy_mode_choice_marks_socks5_as_recommended(self) -> None:
        import inspect
        from telegram_proxy.ui import settings_build

        source = inspect.getsource(settings_build)

        self.assertIn("SOCKS5 (рекомендуется)", source)
        self.assertIn("MTProxy (продвинутый)", source)

    def test_page_activation_resyncs_advanced_settings_block(self) -> None:
        import inspect
        from telegram_proxy.ui.page import TelegramProxyPage

        source = inspect.getsource(TelegramProxyPage.on_page_activated)

        self.assertIn("_apply_advanced_settings_ui()", source)

    def test_page_uses_settings_ui_state_plan_for_advanced_visibility(self) -> None:
        import inspect
        from telegram_proxy.ui import page

        source = inspect.getsource(page)

        self.assertIn("from telegram_proxy.ui.settings_ui_state import", source)
        self.assertIn("build_advanced_settings_ui_plan", source)
        self.assertIn("build_advanced_settings_auto_sections", source)


if __name__ == "__main__":
    unittest.main()
