from __future__ import annotations

import hashlib
import secrets
import struct
from dataclasses import dataclass
from urllib.parse import urlencode

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


HANDSHAKE_LEN = 64
SKIP_LEN = 8
PREKEY_LEN = 32
IV_LEN = 16
PROTO_TAG_POS = 56
DC_IDX_POS = 60

PROTO_TAG_ABRIDGED = b"\xef\xef\xef\xef"
PROTO_TAG_INTERMEDIATE = b"\xee\xee\xee\xee"
PROTO_TAG_SECURE = b"\xdd\xdd\xdd\xdd"
VALID_PROTO_TAGS = frozenset({PROTO_TAG_ABRIDGED, PROTO_TAG_INTERMEDIATE, PROTO_TAG_SECURE})


@dataclass(frozen=True, slots=True)
class MTProxyClientInit:
    dc: int
    is_media: bool
    proto_tag: bytes
    client_prekey_iv: bytes


def normalize_secret(value: object) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 32:
        return ""
    if not all(ch in "0123456789abcdef" for ch in text):
        return ""
    return text


def generate_secret() -> str:
    return secrets.token_hex(16)


def build_mtproxy_link(host: str, port: int, secret: str) -> str:
    normalized_secret = normalize_secret(secret)
    query = urlencode(
        {
            "server": str(host or "127.0.0.1").strip() or "127.0.0.1",
            "port": str(int(port or 0)),
            "secret": normalized_secret,
        }
    )
    return f"tg://proxy?{query}"


def parse_client_init(init: bytes, secret: str) -> MTProxyClientInit | None:
    normalized_secret = normalize_secret(secret)
    if len(init or b"") < HANDSHAKE_LEN or not normalized_secret:
        return None

    secret_bytes = bytes.fromhex(normalized_secret)
    client_prekey_iv = bytes(init[SKIP_LEN:SKIP_LEN + PREKEY_LEN + IV_LEN])
    prekey = client_prekey_iv[:PREKEY_LEN]
    iv = client_prekey_iv[PREKEY_LEN:]
    key = hashlib.sha256(prekey + secret_bytes).digest()

    cipher = Cipher(algorithms.AES(key), modes.CTR(iv))
    decrypted = cipher.encryptor().update(bytes(init[:HANDSHAKE_LEN]))

    proto_tag = decrypted[PROTO_TAG_POS:PROTO_TAG_POS + 4]
    if proto_tag not in VALID_PROTO_TAGS:
        return None

    dc_idx = struct.unpack("<h", decrypted[DC_IDX_POS:DC_IDX_POS + 2])[0]
    dc = abs(dc_idx)
    if dc <= 0:
        return None

    return MTProxyClientInit(
        dc=dc,
        is_media=dc_idx < 0,
        proto_tag=proto_tag,
        client_prekey_iv=client_prekey_iv,
    )


__all__ = [
    "MTProxyClientInit",
    "build_mtproxy_link",
    "generate_secret",
    "normalize_secret",
    "parse_client_init",
]
