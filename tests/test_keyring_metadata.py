from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KEYRING_DIR = ROOT / "packages" / "stable" / "nanoos-keyring"
FINGERPRINT = "D35A46A77EDBFD4F069B71ACB329E36F597CD358"


class NanoOSKeyringMetadataTests(unittest.TestCase):
    def test_public_key_is_armored_and_not_private_material(self) -> None:
        public_key = (ROOT / "keys" / "nanoos-repo-signing-2026.asc").read_text(
            encoding="utf-8"
        )
        self.assertIn("-----BEGIN PGP PUBLIC KEY BLOCK-----", public_key)
        self.assertIn("-----END PGP PUBLIC KEY BLOCK-----", public_key)
        self.assertNotIn("PRIVATE KEY BLOCK", public_key)

    def test_ownertrust_matches_documented_fingerprint(self) -> None:
        trusted = (KEYRING_DIR / "nanoos-trusted").read_text(encoding="utf-8")
        self.assertEqual(trusted.strip(), f"{FINGERPRINT}:6:")

    def test_pkgbuild_pins_and_checks_the_same_fingerprint(self) -> None:
        pkgbuild = (KEYRING_DIR / "PKGBUILD").read_text(encoding="utf-8")
        match = re.search(r"^_key_fingerprint='([0-9A-F]{40})'$", pkgbuild, re.M)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), FINGERPRINT)
        self.assertIn("nanoos-repo-signing-2026.pub::https://", pkgbuild)
        self.assertIn("gpg --batch --yes --dearmor", pkgbuild)
        install_script = (KEYRING_DIR / "nanoos-keyring.install").read_text(
            encoding="utf-8"
        )
        self.assertIn("pacman-key", install_script)
        self.assertIn("--populate nanoos", install_script)


if __name__ == "__main__":
    unittest.main()
