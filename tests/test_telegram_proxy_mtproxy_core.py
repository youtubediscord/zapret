from __future__ import annotations

import hashlib
import os
import struct
import unittest
from types import SimpleNamespace


def _xor_bytes(left: bytes, right: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(left, right))


def _build_mtproxy_init(*, secret_hex: str, dc: int, is_media: bool = False) -> bytes:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    secret = bytes.fromhex(secret_hex)
    prekey = os.urandom(32)
    iv = os.urandom(16)
    key = hashlib.sha256(prekey + secret).digest()
    cipher = Cipher(algorithms.AES(key), modes.CTR(iv))
    keystream = cipher.encryptor().update(b"\x00" * 64)

    dc_idx = -int(dc) if is_media else int(dc)
    tail_plain = b"\xee\xee\xee\xee" + struct.pack("<h", dc_idx) + b"\x00\x00"

    init = bytearray(os.urandom(64))
    init[8:40] = prekey
    init[40:56] = iv
    init[56:64] = _xor_bytes(tail_plain, keystream[56:64])
    return bytes(init)


class TelegramProxyMTProxyCoreTests(unittest.TestCase):
    def test_mtproxy_settings_are_normalized_in_settings_json_shape(self) -> None:
        from settings.normalize import normalize_telegram_proxy
        from settings.schema import VALID_TG_PROXY_MODES, default_telegram_proxy
        from telegram_proxy.config.settings import default_state

        defaults = default_telegram_proxy()

        self.assertIn("mtproxy", VALID_TG_PROXY_MODES)
        self.assertIn("mtproxy_secret", defaults)
        self.assertIn("dc_ip", defaults)
        self.assertEqual(default_state().mtproxy_secret, "")

        normalized = normalize_telegram_proxy(
            {
                "mode": "mtproxy",
                "mtproxy_secret": "  AABBCCDDEEFF00112233445566778899  ",
                "dc_ip": [
                    "2:149.154.167.220",
                    "bad",
                    "4:999.1.1.1",
                    "4:149.154.167.220",
                    "203:91.105.192.100",
                ],
            }
        )

        self.assertEqual(normalized["mode"], "mtproxy")
        self.assertEqual(normalized["mtproxy_secret"], "aabbccddeeff00112233445566778899")
        self.assertEqual(
            normalized["dc_ip"],
            [
                "2:149.154.167.220",
                "4:149.154.167.220",
                "203:91.105.192.100",
            ],
        )

        invalid = normalize_telegram_proxy({"mtproxy_secret": "bad"})
        self.assertEqual(invalid["mtproxy_secret"], "")

    def test_mtproxy_link_and_secret_helpers(self) -> None:
        from telegram_proxy.proxy.mtproxy import (
            build_mtproxy_link,
            generate_secret,
            normalize_secret,
        )

        generated = generate_secret()

        self.assertEqual(len(generated), 32)
        self.assertEqual(normalize_secret(" AABBCCDDEEFF00112233445566778899 "), "aabbccddeeff00112233445566778899")
        self.assertEqual(normalize_secret("bad"), "")
        self.assertEqual(
            build_mtproxy_link("127.0.0.1", 1443, "aabbccddeeff00112233445566778899"),
            "tg://proxy?server=127.0.0.1&port=1443&secret=aabbccddeeff00112233445566778899",
        )

    def test_mtproxy_client_init_parser_checks_secret_and_dc(self) -> None:
        from telegram_proxy.proxy.mtproxy import parse_client_init

        secret = "aabbccddeeff00112233445566778899"
        init = _build_mtproxy_init(secret_hex=secret, dc=4, is_media=True)

        parsed = parse_client_init(init, secret)
        wrong_secret = parse_client_init(init, "00112233445566778899aabbccddeeff")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.dc, 4)
        self.assertTrue(parsed.is_media)
        self.assertEqual(parsed.proto_tag, b"\xee\xee\xee\xee")
        self.assertIsNone(wrong_secret)

    def test_mtproxy_crypto_context_builds_relay_init_and_transforms_streams(self) -> None:
        from telegram_proxy.proxy.mtproxy import (
            build_crypto_context,
            generate_relay_init,
            parse_client_init,
        )
        from telegram_proxy.proxy.mtproto import dc_from_init

        secret = "aabbccddeeff00112233445566778899"
        client_init = _build_mtproxy_init(secret_hex=secret, dc=2)
        parsed = parse_client_init(client_init, secret)
        relay_init = generate_relay_init(parsed.proto_tag, dc=2, is_media=False)
        context = build_crypto_context(parsed.client_prekey_iv, secret, relay_init)

        client_payload = b"\x11" * 128
        telegram_payload = context.client_to_telegram(client_payload)
        client_response = context.telegram_to_client(b"\x22" * 128)

        relay_dc, relay_is_media = dc_from_init(relay_init)
        self.assertEqual(relay_dc, 2)
        self.assertFalse(relay_is_media)
        self.assertEqual(len(telegram_payload), len(client_payload))
        self.assertEqual(len(client_response), 128)
        self.assertNotEqual(telegram_payload, client_payload)

    def test_mtproxy_msg_splitter_splits_intermediate_packets(self) -> None:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

        from telegram_proxy.proxy.mtproxy import (
            MTProxyMsgSplitter,
            PROTO_TAG_INTERMEDIATE,
            generate_relay_init,
        )

        relay_init = generate_relay_init(PROTO_TAG_INTERMEDIATE, dc=4, is_media=False)
        encryptor = Cipher(
            algorithms.AES(relay_init[8:40]),
            modes.CTR(relay_init[40:56]),
        ).encryptor()
        encryptor.update(b"\x00" * 64)

        first_packet = struct.pack("<I", 8) + b"12345678"
        second_packet = struct.pack("<I", 4) + b"abcd"
        encrypted = encryptor.update(first_packet + second_packet)

        splitter = MTProxyMsgSplitter(relay_init, PROTO_TAG_INTERMEDIATE)

        self.assertEqual(
            splitter.split(encrypted),
            [encrypted[: len(first_packet)], encrypted[len(first_packet):]],
        )

    def test_mtproxy_relay_sends_split_packets_as_separate_ws_frames(self) -> None:
        import asyncio

        from telegram_proxy.proxy.mtproxy import relay_mtproxy_wss

        class _Reader:
            def __init__(self, chunks):
                self._chunks = list(chunks)

            async def read(self, _size):
                if self._chunks:
                    return self._chunks.pop(0)
                return b""

        class _Writer:
            def write(self, _data):
                return None

            async def drain(self):
                return None

        class _Ws:
            def __init__(self):
                self.sent = []
                self._closed = False

            async def send(self, data):
                self.sent.append(data)

            async def send_batch(self, parts):
                self.sent.extend(parts)

            async def recv(self):
                await asyncio.sleep(1)

            async def close(self):
                self._closed = True

        class _Crypto:
            def client_to_telegram(self, data):
                return data

            def telegram_to_client(self, data):
                return data

        class _Splitter:
            def split(self, data):
                midpoint = len(data) // 2
                return [data[:midpoint], data[midpoint:]]

            def flush(self):
                return []

        ws = _Ws()
        asyncio.run(
            relay_mtproxy_wss(
                client_reader=_Reader([b"aaaabbbb"]),
                client_writer=_Writer(),
                ws=ws,
                crypto=_Crypto(),
                splitter=_Splitter(),
                stats=SimpleNamespace(bytes_sent=0, bytes_received=0),
                log_fn=lambda _message: None,
                label="test",
                dc=4,
            )
        )

        self.assertEqual(ws.sent, [b"aaaa", b"bbbb"])

    def test_runtime_start_config_reads_mtproxy_mode_and_secret(self) -> None:
        from unittest.mock import patch

        import telegram_proxy.runtime.commands as commands

        with (
            patch("settings.store.get_tg_proxy_host", return_value="127.0.0.1"),
            patch("settings.store.get_tg_proxy_port", return_value=1443),
            patch("settings.store.get_tg_proxy_mode", return_value="mtproxy"),
            patch("settings.store.get_tg_proxy_mtproxy_secret", return_value="aabbccddeeff00112233445566778899"),
            patch("settings.store.get_tg_proxy_dc_ip", return_value=["4:149.154.167.220"]),
            patch("telegram_proxy.config.settings.build_upstream_config", return_value=None),
            patch("telegram_proxy.config.settings.build_cloudflare_config", return_value=None),
        ):
            config = commands.get_start_config()

        self.assertEqual(config.mode, "mtproxy")
        self.assertEqual(config.mtproxy_secret, "aabbccddeeff00112233445566778899")
        self.assertEqual(config.dc_endpoint_overrides, {4: "149.154.167.220"})

    def test_mtproxy_dc_endpoint_override_changes_tcp_target(self) -> None:
        import inspect

        import telegram_proxy.wss_proxy as wss_proxy
        from telegram_proxy.proxy.dc_map import dc_to_tcp_endpoint, parse_dc_endpoint_overrides

        overrides = parse_dc_endpoint_overrides(["4:149.154.167.220"])

        self.assertEqual(overrides, {4: "149.154.167.220"})
        self.assertEqual(dc_to_tcp_endpoint(4, overrides), ("149.154.167.220", 443))
        self.assertEqual(dc_to_tcp_endpoint(203), ("91.105.192.100", 443))
        self.assertIn("dc_to_tcp_endpoint(dc, self._dc_endpoint_overrides)", inspect.getsource(wss_proxy.TelegramWSProxy._handle_mtproxy_client))
        self.assertNotIn("TCP_ENDPOINTS.get(dc", inspect.getsource(wss_proxy.TelegramWSProxy._handle_mtproxy_client))

    def test_standalone_cli_accepts_mtproxy_mode_and_secret(self) -> None:
        from telegram_proxy.__main__ import build_arg_parser

        parser = build_arg_parser()
        args = parser.parse_args(
            [
                "--port",
                "1443",
                "--mode",
                "mtproxy",
                "--secret",
                "aabbccddeeff00112233445566778899",
                "--dc-ip",
                "2:149.154.167.220",
                "--dc-ip",
                "4:149.154.167.220",
            ]
        )

        self.assertEqual(args.port, 1443)
        self.assertEqual(args.mode, "mtproxy")
        self.assertEqual(args.secret, "aabbccddeeff00112233445566778899")
        self.assertEqual(args.dc_ip, ["2:149.154.167.220", "4:149.154.167.220"])

    def test_windows_service_command_can_pass_mtproxy_secret(self) -> None:
        from telegram_proxy.service import build_service_args

        args = build_service_args(
            port=1443,
            mode="mtproxy",
            mtproxy_secret="aabbccddeeff00112233445566778899",
            dc_ip=["2:149.154.167.220", "4:149.154.167.220"],
        )

        self.assertEqual(
            args,
            "-m telegram_proxy --port 1443 --mode mtproxy --secret aabbccddeeff00112233445566778899 --dc-ip 2:149.154.167.220 --dc-ip 4:149.154.167.220",
        )

    def test_page_links_follow_selected_local_proxy_mode(self) -> None:
        from telegram_proxy.config.settings import (
            build_manual_instruction_text,
            build_proxy_url,
        )

        secret = "aabbccddeeff00112233445566778899"

        self.assertEqual(
            build_proxy_url("127.0.0.1", 1443, mode="socks5", mtproxy_secret=secret),
            "tg://socks?server=127.0.0.1&port=1443",
        )
        self.assertEqual(
            build_proxy_url("127.0.0.1", 1443, mode="mtproxy", mtproxy_secret=secret),
            "tg://proxy?server=127.0.0.1&port=1443&secret=aabbccddeeff00112233445566778899",
        )
        self.assertEqual(
            build_manual_instruction_text("127.0.0.1", 1443, mode="mtproxy"),
            "  Тип: MTProxy  |  Хост: 127.0.0.1  |  Порт: 1443",
        )

    def test_wss_proxy_has_separate_mtproxy_runtime_entry(self) -> None:
        import inspect
        import telegram_proxy.wss_proxy as wss_proxy

        start_source = inspect.getsource(wss_proxy.TelegramWSProxy.start)
        handler_source = inspect.getsource(wss_proxy.TelegramWSProxy._handle_mtproxy_client)
        tunnel_source = inspect.getsource(wss_proxy.TelegramWSProxy._tunnel_mtproxy_via_wss)

        self.assertIn("_handle_mtproxy_client", start_source)
        self.assertIn("parse_client_init", handler_source)
        self.assertIn("generate_relay_init", handler_source)
        self.assertIn("build_crypto_context", handler_source)
        self.assertIn("relay_mtproxy_wss", tunnel_source)
        self.assertIn("_cloudflare_fallback", tunnel_source)
        self.assertIn("MTProxyMsgSplitter", tunnel_source)
        self.assertIn("splitter=splitter", tunnel_source)

    def test_mtproxy_skips_plain_wss_for_dc_without_own_relay(self) -> None:
        import asyncio
        from unittest.mock import patch

        from telegram_proxy.proxy.mtproxy import PROTO_TAG_INTERMEDIATE, generate_relay_init
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _NoWssPool:
            async def get(self, *_args, **_kwargs):
                raise AssertionError("MTProxy DC without own WSS relay must go straight to fallback")

        async def fake_cloudflare(*_args, **_kwargs):
            return True

        proxy = TelegramWSProxy(mode="mtproxy", mtproxy_secret="aabbccddeeff00112233445566778899")
        proxy._ws_pool = _NoWssPool()
        relay_init = generate_relay_init(PROTO_TAG_INTERMEDIATE, dc=1, is_media=False)

        with (
            patch.object(proxy, "_cloudflare_fallback", side_effect=fake_cloudflare) as cloudflare,
            patch("telegram_proxy.wss_proxy.RawWebSocket.connect") as connect,
        ):
            asyncio.run(
                proxy._tunnel_mtproxy_via_wss(
                    object(),
                    object(),
                    1,
                    False,
                    relay_init,
                    object(),
                    PROTO_TAG_INTERMEDIATE,
                    "149.154.175.50",
                    443,
                    "test",
                )
            )

        self.assertEqual(cloudflare.call_count, 1)
        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
