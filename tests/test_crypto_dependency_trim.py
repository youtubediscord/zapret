from __future__ import annotations

import base64
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CryptoDependencyTrimTests(unittest.TestCase):
    def test_runtime_and_release_inputs_do_not_depend_on_cryptography(self) -> None:
        checked_paths = list(ROOT.glob("requirements*.txt"))
        checked_paths.append(ROOT / ".github" / "workflows" / "windows-release.yml")
        checked_paths.extend(path for path in (ROOT / "src").rglob("*.py") if "__pycache__" not in path.parts)

        offenders = [
            str(path.relative_to(ROOT))
            for path in checked_paths
            if "cryptography" in path.read_text(encoding="utf-8", errors="ignore")
        ]

        self.assertEqual(offenders, [])

        runtime_requirements = (ROOT / "requirements-runtime.txt").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "windows-release.yml").read_text(encoding="utf-8")
        self.assertIn('python-version: "3.14"', workflow)
        self.assertNotIn('python-version: "3.12"', workflow)
        self.assertIn("TgCrypto==1.2.5", runtime_requirements)
        self.assertIn("-r requirements-build.txt", workflow)

    def test_aes_ctr_stream_matches_standard_vector_and_keeps_chunk_state(self) -> None:
        from telegram_proxy.proxy.aes_ctr import AesCtrStream, aes_ctr_crypt

        key = bytes.fromhex(
            "603deb1015ca71be2b73aef0857d7781"
            "1f352c073b6108d72d9810a30914dff4"
        )
        iv = bytes.fromhex("f0f1f2f3f4f5f6f7f8f9fafbfcfdfeff")
        plaintext = bytes.fromhex(
            "6bc1bee22e409f96e93d7e117393172a"
            "ae2d8a571e03ac9c9eb76fac45af8e51"
            "30c81c46a35ce411e5fbc1191a0a52ef"
            "f69f2445df4f9b17ad2b417be66c3710"
        )
        ciphertext = bytes.fromhex(
            "601ec313775789a5b7a7f504bbf3d228"
            "f443e3ca4d62b59aca84e990cacaf5c5"
            "2b0930daa23de94ce87017ba2d84988d"
            "dfc9c58db67aada613c2dd08457941a6"
        )

        stream = AesCtrStream(key, iv)
        encrypted = stream.update(plaintext[:17]) + stream.update(b"") + stream.update(plaintext[17:])

        self.assertEqual(encrypted, ciphertext)
        self.assertEqual(aes_ctr_crypt(key, iv, ciphertext), plaintext)

    def test_ed25519_verifier_accepts_rfc_vector_and_rejects_tampering(self) -> None:
        from donater.ed25519 import verify_ed25519_signature

        public_key = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
        signature = bytes.fromhex(
            "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
            "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
        )

        self.assertTrue(verify_ed25519_signature(public_key, signature, b""))
        self.assertFalse(verify_ed25519_signature(public_key, signature[:-1] + b"\x00", b""))
        self.assertFalse(verify_ed25519_signature(public_key, signature, b"tampered"))

    def test_premium_signed_response_uses_pure_python_ed25519(self) -> None:
        from donater.crypto import verify_signed_response

        signed = {
            "type": "zapret_premium_status",
            "device_id": "device-1",
            "nonce": "nonce-1",
            "activated": True,
            "days_remaining": 7,
        }
        public_key_b64 = "11qYAYKxCrfVS/7TyWQHOg7hcvPapiMlrwIaaPcHURo="
        sig = "nugTwSDyXBiEcJoTPPNHS0s9hPbLvm83wGiBnrfZwj0blQaMbXOn_qIbuk5i-jzBBV0uPqqVYk5hUMbMVXnmBA"
        resp = {"signed": signed, "kid": "test", "sig": sig}

        self.assertEqual(
            verify_signed_response(
                resp,
                expected_device_id="device-1",
                expected_nonce="nonce-1",
                trusted_public_keys_b64={"test": public_key_b64},
            ),
            signed,
        )

        bad_resp = dict(resp)
        bad_resp["sig"] = base64.urlsafe_b64encode(b"\x00" * 64).decode("ascii").rstrip("=")
        self.assertIsNone(
            verify_signed_response(
                bad_resp,
                expected_device_id="device-1",
                expected_nonce="nonce-1",
                trusted_public_keys_b64={"test": public_key_b64},
            )
        )
