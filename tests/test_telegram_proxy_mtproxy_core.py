from __future__ import annotations

import hashlib
import os
import struct
import unittest


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
        self.assertEqual(default_state().mtproxy_secret, "")

        normalized = normalize_telegram_proxy(
            {
                "mode": "mtproxy",
                "mtproxy_secret": "  AABBCCDDEEFF00112233445566778899  ",
            }
        )

        self.assertEqual(normalized["mode"], "mtproxy")
        self.assertEqual(normalized["mtproxy_secret"], "aabbccddeeff00112233445566778899")

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


if __name__ == "__main__":
    unittest.main()
