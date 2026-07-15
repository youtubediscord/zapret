from __future__ import annotations

import hashlib
import hmac
import os
import struct
import time
import unittest
from types import SimpleNamespace


def _xor_bytes(left: bytes, right: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(left, right))


def _build_mtproxy_init(*, secret_hex: str, dc: int, is_media: bool = False) -> bytes:
    from telegram_proxy.proxy.aes_ctr import aes_ctr_keystream

    secret = bytes.fromhex(secret_hex)
    prekey = os.urandom(32)
    iv = os.urandom(16)
    key = hashlib.sha256(prekey + secret).digest()
    keystream = aes_ctr_keystream(key, iv, 64)

    dc_idx = -int(dc) if is_media else int(dc)
    tail_plain = b"\xee\xee\xee\xee" + struct.pack("<h", dc_idx) + b"\x00\x00"

    init = bytearray(os.urandom(64))
    init[8:40] = prekey
    init[40:56] = iv
    init[56:64] = _xor_bytes(tail_plain, keystream[56:64])
    return bytes(init)


def _build_fake_tls_client_hello(secret_hex: str, *, session_id: bytes = b"") -> bytes:
    secret = bytes.fromhex(secret_hex)
    body = bytearray(96)
    body[0] = 0x01
    body[1:4] = (len(body) - 4).to_bytes(3, "big")
    body[4:6] = b"\x03\x03"
    body[6:38] = b"\x00" * 32
    body[38] = len(session_id)
    body[39:39 + len(session_id)] = session_id

    hello = bytearray(b"\x16\x03\x03" + len(body).to_bytes(2, "big") + bytes(body))
    expected = hmac.new(secret, bytes(hello), hashlib.sha256).digest()
    timestamp = int(time.time())
    random_tail = bytes(
        value ^ mask
        for value, mask in zip(timestamp.to_bytes(4, "little"), expected[28:32])
    )
    hello[11:43] = expected[:28] + random_tail
    return bytes(hello)


def _tls_app_data(payload: bytes) -> bytes:
    return b"\x17\x03\x03" + len(payload).to_bytes(2, "big") + bytes(payload)


class TelegramProxyMTProxyCoreTests(unittest.TestCase):
    def test_mtproxy_no_init_connections_are_summarized_without_log_spam(self) -> None:
        import asyncio
        from unittest.mock import patch

        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _Writer:
            def get_extra_info(self, name, default=None):
                if name == "peername":
                    return ("127.0.0.1", 13579)
                return default

            def close(self):
                return None

            async def wait_closed(self):
                return None

        async def no_init(*_args, **_kwargs):
            return None

        logs: list[str] = []
        proxy = TelegramWSProxy(
            mode="mtproxy",
            mtproxy_secret="aabbccddeeff00112233445566778899",
            on_log=logs.append,
        )

        with patch("telegram_proxy.wss_proxy.read_mtproxy_client_init", side_effect=no_init):
            for _ in range(6):
                asyncio.run(proxy._handle_mtproxy_client(object(), _Writer()))

        self.assertEqual(proxy.stats.mtproxy_invalid_init_count, 6)
        joined = "\n".join(logs)
        self.assertEqual(joined.count("MTProxy init packet не получен"), 2)
        self.assertIn("повторов: 1", joined)
        self.assertIn("повторов: 5", joined)
        self.assertIn("проверьте тип прокси", joined)
        self.assertNotIn("no MTProxy init packet", joined)

    def test_mtproxy_bad_handshake_points_to_secret_or_secret_type(self) -> None:
        import asyncio
        from unittest.mock import patch

        from telegram_proxy.proxy.fake_tls import FakeTlsClientInit
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _Writer:
            def get_extra_info(self, name, default=None):
                if name == "peername":
                    return ("127.0.0.1", 24680)
                return default

            def close(self):
                return None

            async def wait_closed(self):
                return None

        client = FakeTlsClientInit(
            init=b"x" * 64,
            reader=object(),
            writer=_Writer(),
            label="127.0.0.1:24680",
        )
        logs: list[str] = []
        proxy = TelegramWSProxy(
            mode="mtproxy",
            mtproxy_secret="aabbccddeeff00112233445566778899",
            on_log=logs.append,
        )

        with (
            patch("telegram_proxy.wss_proxy.read_mtproxy_client_init", return_value=client),
            patch("telegram_proxy.wss_proxy.parse_client_init", return_value=None),
        ):
            asyncio.run(proxy._handle_mtproxy_client(object(), _Writer()))

        self.assertEqual(proxy.stats.mtproxy_bad_handshake_count, 1)
        joined = "\n".join(logs)
        self.assertIn("MTProxy init получен, но не расшифровался", joined)
        self.assertIn("secret", joined)
        self.assertIn("dd/ee", joined)

    def test_mtproxy_settings_are_normalized_in_settings_json_shape(self) -> None:
        from settings.normalize import normalize_telegram_proxy
        from settings.schema import VALID_TG_PROXY_MODES, default_telegram_proxy
        from telegram_proxy.config.settings import default_state, normalize_proxy_mode

        defaults = default_telegram_proxy()

        self.assertEqual(VALID_TG_PROXY_MODES, frozenset({"socks5", "mtproxy"}))
        self.assertIn("mtproxy_secret", defaults)
        self.assertIn("dc_ip", defaults)
        self.assertEqual(defaults["pool_size"], 4)
        self.assertEqual(defaults["buffer_kb"], 256)
        self.assertEqual(defaults["mode"], "mtproxy")
        self.assertTrue(defaults["upstream_enabled"])
        self.assertFalse(defaults["upstream_udp_enabled"])
        self.assertEqual(normalize_telegram_proxy({})["mode"], "mtproxy")
        self.assertTrue(normalize_telegram_proxy({})["upstream_enabled"])
        self.assertFalse(normalize_telegram_proxy({})["upstream_udp_enabled"])
        self.assertEqual(default_state().mode, "mtproxy")
        self.assertTrue(default_state().upstream_enabled)
        self.assertFalse(default_state().upstream_udp_enabled)
        self.assertEqual(normalize_proxy_mode("bad"), "socks5")
        self.assertEqual(normalize_telegram_proxy({"mode": "transparent"})["mode"], "mtproxy")
        self.assertEqual(normalize_telegram_proxy({"mode": "both"})["mode"], "mtproxy")
        self.assertEqual(default_state().mtproxy_secret, "")

        normalized = normalize_telegram_proxy(
            {
                "mode": "mtproxy",
                "mtproxy_secret": "  AABBCCDDEEFF00112233445566778899  ",
                "pool_size": 99,
                "buffer_kb": 2,
                "upstream_udp_enabled": True,
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
        self.assertTrue(normalized["upstream_udp_enabled"])
        self.assertEqual(normalized["mtproxy_secret"], "aabbccddeeff00112233445566778899")
        self.assertEqual(normalized["pool_size"], 32)
        self.assertEqual(normalized["buffer_kb"], 4)
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
            "tg://proxy?server=127.0.0.1&port=1443&secret=ddaabbccddeeff00112233445566778899",
        )
        self.assertEqual(
            build_mtproxy_link(
                "proxy.example.com",
                443,
                "aabbccddeeff00112233445566778899",
                fake_tls_domain="front.example.com",
            ),
            "tg://proxy?server=proxy.example.com&port=443&secret=eeaabbccddeeff0011223344556677889966726f6e742e6578616d706c652e636f6d",
        )
        self.assertEqual(
            build_mtproxy_link(
                "proxy.example.com",
                443,
                "aabbccddeeff00112233445566778899",
                fake_tls_domain="bad domain",
            ),
            "tg://proxy?server=proxy.example.com&port=443&secret=ddaabbccddeeff00112233445566778899",
        )

    def test_fake_tls_settings_are_normalized_in_settings_json_shape(self) -> None:
        from settings.normalize import normalize_telegram_proxy
        from settings.schema import default_telegram_proxy
        from telegram_proxy.config.settings import default_state
        from telegram_proxy.proxy.fake_tls import build_fake_tls_nginx_config

        defaults = default_telegram_proxy()

        self.assertEqual(defaults["fake_tls_domain"], "")
        self.assertFalse(defaults["proxy_protocol"])
        self.assertEqual(default_state().fake_tls_domain, "")
        self.assertFalse(default_state().proxy_protocol)

        normalized = normalize_telegram_proxy(
            {
                "fake_tls_domain": " Front.Example.Com ",
                "proxy_protocol": "yes",
            }
        )

        self.assertEqual(normalized["fake_tls_domain"], "front.example.com")
        self.assertTrue(normalized["proxy_protocol"])

        nginx_config = build_fake_tls_nginx_config(
            fake_tls_domain="Front.Example.Com",
            upstream_host="127.0.0.1",
            upstream_port=8446,
        )
        self.assertIn("upstream mtproxy", nginx_config)
        self.assertIn("server 127.0.0.1:8446;", nginx_config)
        self.assertIn("front.example.com mtproxy;", nginx_config)
        self.assertIn("proxy_protocol on;", nginx_config)
        self.assertIn("ssl_preread on;", nginx_config)

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
        from telegram_proxy.proxy.aes_ctr import AesCtrStream
        from telegram_proxy.proxy.mtproxy import (
            MTProxyMsgSplitter,
            PROTO_TAG_INTERMEDIATE,
            generate_relay_init,
        )

        relay_init = generate_relay_init(PROTO_TAG_INTERMEDIATE, dc=4, is_media=False)
        encryptor = AesCtrStream(relay_init[8:40], relay_init[40:56])
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
            patch("settings.store.get_tg_proxy_pool_size", return_value=6),
            patch("settings.store.get_tg_proxy_buffer_kb", return_value=512),
            patch("settings.store.get_tg_proxy_fake_tls_domain", return_value="front.example.com"),
            patch("settings.store.get_tg_proxy_proxy_protocol", return_value=True),
            patch("telegram_proxy.config.settings.build_upstream_config", return_value=None),
            patch("telegram_proxy.config.settings.build_cloudflare_config", return_value=None),
        ):
            config = commands.get_start_config()

        self.assertEqual(config.mode, "mtproxy")
        self.assertEqual(config.mtproxy_secret, "aabbccddeeff00112233445566778899")
        self.assertEqual(config.dc_endpoint_overrides, {4: "149.154.167.220"})
        self.assertEqual(config.pool_size, 6)
        self.assertEqual(config.buffer_kb, 512)
        self.assertEqual(config.fake_tls_domain, "front.example.com")
        self.assertTrue(config.proxy_protocol)

    def test_runtime_start_config_creates_secret_for_default_mtproxy(self) -> None:
        from unittest.mock import patch

        import telegram_proxy.runtime.commands as commands

        generated = "00112233445566778899aabbccddeeff"

        with (
            patch("settings.store.get_tg_proxy_host", return_value="127.0.0.1"),
            patch("settings.store.get_tg_proxy_port", return_value=1353),
            patch("settings.store.get_tg_proxy_mode", return_value="mtproxy"),
            patch("settings.store.get_tg_proxy_mtproxy_secret", return_value=""),
            patch("settings.store.get_tg_proxy_dc_ip", return_value=[]),
            patch("settings.store.get_tg_proxy_pool_size", return_value=4),
            patch("settings.store.get_tg_proxy_buffer_kb", return_value=256),
            patch("settings.store.get_tg_proxy_fake_tls_domain", return_value=""),
            patch("settings.store.get_tg_proxy_proxy_protocol", return_value=False),
            patch("telegram_proxy.config.settings.generate_mtproxy_secret", return_value=generated),
            patch("telegram_proxy.config.settings.set_mtproxy_secret") as save_secret,
            patch("telegram_proxy.config.settings.build_upstream_config", return_value=None),
            patch("telegram_proxy.config.settings.build_cloudflare_config", return_value=None),
        ):
            config = commands.get_start_config()

        self.assertEqual(config.mode, "mtproxy")
        self.assertEqual(config.mtproxy_secret, generated)
        save_secret.assert_called_once_with(generated)

    def test_runtime_start_config_falls_back_to_socks5_for_empty_mode(self) -> None:
        from unittest.mock import patch

        import telegram_proxy.runtime.commands as commands

        with (
            patch("settings.store.get_tg_proxy_host", return_value="127.0.0.1"),
            patch("settings.store.get_tg_proxy_port", return_value=1353),
            patch("settings.store.get_tg_proxy_mode", return_value=""),
            patch("settings.store.get_tg_proxy_mtproxy_secret", return_value=""),
            patch("settings.store.get_tg_proxy_pool_size", return_value=4),
            patch("settings.store.get_tg_proxy_buffer_kb", return_value=256),
            patch("settings.store.get_tg_proxy_fake_tls_domain", return_value=""),
            patch("settings.store.get_tg_proxy_proxy_protocol", return_value=False),
            patch("telegram_proxy.config.settings.ensure_mtproxy_secret_for_mode", return_value="") as ensure_secret,
            patch("telegram_proxy.config.settings.build_dc_endpoint_overrides", return_value={}),
            patch("telegram_proxy.config.settings.build_upstream_config", return_value=None),
            patch("telegram_proxy.config.settings.build_cloudflare_config", return_value=None),
        ):
            config = commands.get_start_config()

        self.assertEqual(config.mode, "socks5")
        self.assertEqual(config.mtproxy_secret, "")
        ensure_secret.assert_called_once_with("socks5", "")

    def test_mtproxy_performance_settings_reach_proxy_pools(self) -> None:
        from telegram_proxy.wss_proxy import TelegramWSProxy

        proxy = TelegramWSProxy(
            mode="mtproxy",
            mtproxy_secret="aabbccddeeff00112233445566778899",
            pool_size=7,
            buffer_kb=384,
            fake_tls_domain="front.example.com",
            proxy_protocol=True,
        )

        self.assertEqual(proxy._ws_pool._pool_size, 7)
        self.assertEqual(proxy._cloudflare_worker_pool._pool_size, 7)
        self.assertEqual(proxy._buffer_size, 384 * 1024)
        self.assertEqual(proxy._fake_tls_domain, "front.example.com")
        self.assertTrue(proxy._proxy_protocol)

    def test_fake_tls_client_init_reader_unwraps_mtproxy_handshake(self) -> None:
        import asyncio

        from telegram_proxy.proxy.fake_tls import read_mtproxy_client_init

        secret = "aabbccddeeff00112233445566778899"
        mtproxy_init = _build_mtproxy_init(secret_hex=secret, dc=2)
        payload = _build_fake_tls_client_hello(secret) + _tls_app_data(mtproxy_init)

        class _Reader:
            def __init__(self, data: bytes):
                self._data = bytearray(data)

            async def readexactly(self, size: int) -> bytes:
                if len(self._data) < size:
                    raise asyncio.IncompleteReadError(bytes(self._data), size)
                result = bytes(self._data[:size])
                del self._data[:size]
                return result

            async def readline(self) -> bytes:
                marker = self._data.find(b"\n")
                if marker < 0:
                    return b""
                result = bytes(self._data[:marker + 1])
                del self._data[:marker + 1]
                return result

            async def read(self, size: int = -1) -> bytes:
                if not self._data:
                    return b""
                if size < 0:
                    size = len(self._data)
                result = bytes(self._data[:size])
                del self._data[:size]
                return result

        class _Writer:
            def __init__(self):
                self.writes: list[bytes] = []
                self.closed = False

            def write(self, data: bytes) -> None:
                self.writes.append(bytes(data))

            async def drain(self) -> None:
                return None

            def close(self) -> None:
                self.closed = True

            async def wait_closed(self) -> None:
                return None

            def get_extra_info(self, _name, default=None):
                return default

        writer = _Writer()
        result = asyncio.run(
            read_mtproxy_client_init(
                _Reader(payload),
                writer,
                secret,
                "127.0.0.1:1",
                fake_tls_domain="front.example.com",
            )
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.init, mtproxy_init)
        self.assertIs(result.reader, result.writer)
        self.assertTrue(writer.writes)
        self.assertTrue(writer.writes[0].startswith(b"\x16\x03\x03"))

    def test_mtproxy_dc_endpoint_override_changes_tcp_target(self) -> None:
        import inspect

        import telegram_proxy.wss_proxy as wss_proxy
        from telegram_proxy.proxy.dc_map import dc_to_tcp_endpoint, parse_dc_endpoint_overrides

        overrides = parse_dc_endpoint_overrides(["4:149.154.167.220"])

        self.assertEqual(overrides, {4: "149.154.167.220"})
        self.assertEqual(dc_to_tcp_endpoint(4, overrides), ("149.154.167.220", 443))
        self.assertEqual(dc_to_tcp_endpoint(2, is_media=True), ("149.154.167.151", 443))
        self.assertEqual(dc_to_tcp_endpoint(4, is_media=True), ("149.154.164.250", 443))
        self.assertEqual(dc_to_tcp_endpoint(4, overrides, is_media=True), ("149.154.167.220", 443))
        self.assertEqual(dc_to_tcp_endpoint(203), ("91.105.192.100", 443))
        self.assertIn("dc_to_tcp_endpoint(dc, self._dc_endpoint_overrides, is_media=is_media)", inspect.getsource(wss_proxy.TelegramWSProxy._handle_mtproxy_client))
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
                "--fake-tls-domain",
                "front.example.com",
                "--proxy-protocol",
            ]
        )

        self.assertEqual(args.port, 1443)
        self.assertEqual(args.mode, "mtproxy")
        self.assertEqual(args.secret, "aabbccddeeff00112233445566778899")
        self.assertEqual(args.dc_ip, ["2:149.154.167.220", "4:149.154.167.220"])
        self.assertEqual(args.fake_tls_domain, "front.example.com")
        self.assertTrue(args.proxy_protocol)

    def test_windows_service_command_can_pass_mtproxy_secret(self) -> None:
        from telegram_proxy.service import build_service_args

        args = build_service_args(
            port=1443,
            mode="mtproxy",
            mtproxy_secret="aabbccddeeff00112233445566778899",
            dc_ip=["2:149.154.167.220", "4:149.154.167.220"],
            fake_tls_domain="front.example.com",
            proxy_protocol=True,
        )

        self.assertEqual(
            args,
            "-m telegram_proxy --port 1443 --mode mtproxy --secret aabbccddeeff00112233445566778899 --dc-ip 2:149.154.167.220 --dc-ip 4:149.154.167.220 --fake-tls-domain front.example.com --proxy-protocol",
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
            "tg://proxy?server=127.0.0.1&port=1443&secret=ddaabbccddeeff00112233445566778899",
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

    def test_mtproxy_respects_upstream_always_mode_before_wss(self) -> None:
        import asyncio
        from unittest.mock import patch

        from telegram_proxy.proxy.mtproxy import PROTO_TAG_INTERMEDIATE, generate_relay_init
        from telegram_proxy.proxy.routing import UpstreamProxyConfig
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _NoWssPool:
            async def get(self, *_args, **_kwargs):
                raise AssertionError("MTProxy upstream always mode must skip WSS")

        async def fake_upstream(*_args, **_kwargs):
            return True

        proxy = TelegramWSProxy(
            mode="mtproxy",
            mtproxy_secret="aabbccddeeff00112233445566778899",
            upstream_config=UpstreamProxyConfig(
                enabled=True,
                host="127.0.0.1",
                port=1080,
                mode="always",
            ),
        )
        proxy._ws_pool = _NoWssPool()
        relay_init = generate_relay_init(PROTO_TAG_INTERMEDIATE, dc=2, is_media=True)

        with (
            patch.object(proxy, "_mtproxy_upstream_proxy_connect", side_effect=fake_upstream) as upstream,
            patch.object(proxy, "_cloudflare_fallback") as cloudflare,
            patch("telegram_proxy.wss_proxy.RawWebSocket.connect") as connect,
        ):
            asyncio.run(
                proxy._tunnel_mtproxy_via_wss(
                    object(),
                    object(),
                    2,
                    True,
                    relay_init,
                    object(),
                    PROTO_TAG_INTERMEDIATE,
                    "149.154.167.151",
                    443,
                    "test",
                )
            )

        self.assertEqual(upstream.call_count, 1)
        cloudflare.assert_not_called()
        connect.assert_not_called()

    def test_mtproxy_upstream_zero_recv_deprioritizes_current_bundled_proxy(self) -> None:
        import asyncio
        from unittest.mock import patch

        from telegram_proxy.proxy.mtproxy import PROTO_TAG_INTERMEDIATE, generate_relay_init
        from telegram_proxy.proxy.routing import UpstreamProxyConfig, UpstreamProxyEndpoint
        from telegram_proxy.proxy.upstream_controller import ZERO_RECV_OBSERVATION_WINDOW
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _RemoteWriter:
            transport = None

            def write(self, _data):
                return None

            async def drain(self):
                return None

        async def fake_connect(proxy_host, *_args, **_kwargs):
            seen_hosts.append(proxy_host)
            return object(), _RemoteWriter()

        async def fake_relay(*_args, **_kwargs):
            return (0, 1)

        async def run_seven(proxy: TelegramWSProxy):
            for index in range(7):
                if index == 5:
                    clock[0] += ZERO_RECV_OBSERVATION_WINDOW
                await proxy._mtproxy_upstream_proxy_connect(
                    object(),
                    object(),
                    "91.108.56.102",
                    443,
                    relay_init,
                    object(),
                    f"test-{index}",
                    5,
                    True,
                )

        seen_hosts: list[str] = []
        logs: list[str] = []
        clock = [1000.0]
        relay_init = generate_relay_init(PROTO_TAG_INTERMEDIATE, dc=5, is_media=True)
        proxy = TelegramWSProxy(
            mode="mtproxy",
            mtproxy_secret="aabbccddeeff00112233445566778899",
            on_log=logs.append,
            upstream_config=UpstreamProxyConfig(
                enabled=True,
                host="slow.proxy",
                port=443,
                tls=True,
                preset_id="ee",
                preset_name="Эстония",
                mode="always",
                fallback_proxies=(
                    UpstreamProxyEndpoint(host="fast.proxy", port=443, tls=True),
                ),
            ),
        )
        proxy._upstream_runtime.controller._clock = lambda: clock[0]

        with (
            patch("telegram_proxy.wss_proxy.socks5.connect_via_socks5", side_effect=fake_connect),
            patch("telegram_proxy.wss_proxy.relay_mtproxy_tcp", side_effect=fake_relay),
        ):
            asyncio.run(run_seven(proxy))

        self.assertEqual(seen_hosts, ["slow.proxy"] * 6 + ["fast.proxy"])
        self.assertIn("шесть соединений без ответных данных", "\n".join(logs))

    def test_mtproxy_tcp_fallback_tries_upstream_after_direct_connect_failure(self) -> None:
        import asyncio
        from unittest.mock import patch

        from telegram_proxy.proxy.mtproxy import PROTO_TAG_INTERMEDIATE, generate_relay_init
        from telegram_proxy.proxy.routing import UpstreamProxyConfig
        from telegram_proxy.wss_proxy import TelegramWSProxy

        async def fake_upstream(*_args, **_kwargs):
            return True

        proxy = TelegramWSProxy(
            mode="mtproxy",
            mtproxy_secret="aabbccddeeff00112233445566778899",
            upstream_config=UpstreamProxyConfig(
                enabled=True,
                host="127.0.0.1",
                port=1080,
                mode="fallback",
            ),
        )
        relay_init = generate_relay_init(PROTO_TAG_INTERMEDIATE, dc=5, is_media=False)

        with (
            patch("telegram_proxy.wss_proxy.asyncio.open_connection", side_effect=OSError("blocked")),
            patch.object(proxy, "_mtproxy_upstream_proxy_connect", side_effect=fake_upstream) as upstream,
        ):
            asyncio.run(
                proxy._mtproxy_tcp_fallback(
                    object(),
                    object(),
                    "91.108.56.100",
                    443,
                    relay_init,
                    object(),
                    "test",
                    5,
                    False,
                )
            )

        self.assertEqual(upstream.call_count, 1)
        self.assertEqual(
            [
                (event.dc, event.is_media, event.route, event.status, event.reason)
                for event in proxy.stats.route_events
            ],
            [(5, False, "TCP", "ошибка", "OSError: blocked")],
        )


if __name__ == "__main__":
    unittest.main()
