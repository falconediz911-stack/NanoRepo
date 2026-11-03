#!/usr/bin/env python3
"""Static validation for the NanoRepo source repository.

This tool does not execute PKGBUILDs. It checks repository structure,
basic package metadata declarations, and rejects host-specific -march=native.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CHANNELS = ("stable", "testing", "znver5")
REQUIRED_FILES = (
    "README.md",
    "docs/REPOSITORY-ARCHITECTURE.md",
    "docs/BUILD-AND-RELEASE.md",
    "docs/SECURITY.md",
    "docs/ZEN5-BUILD-PROFILE.md",
    "docs/CPU-ENGINE.md",
    "docs/ROADMAP.md",
    "packaging/profiles/znver5/makepkg.conf.example",
)

def fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)

def main() -> int:
    print("NanoRepo static validation")
    print(f"Root: {ROOT}")

    for relative in REQUIRED_FILES:
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size == 0:
            fail(f"required file missing or empty: {relative}")
        print(f"OK: {relative}")

    for channel in CHANNELS:
        for relative in (f"channels/{channel}/README.md",
                         f"packages/{channel}/README.md"):
            path = ROOT / relative
            if not path.is_file() or path.stat().st_size == 0:
                fail(f"channel documentation missing: {relative}")
            print(f"OK: {relative}")

    pkgbuilds = sorted((ROOT / "packages").glob("**/PKGBUILD"))
    seen_names: dict[str, pathlib.Path] = {}

    for pkgbuild in pkgbuilds:
        relative = pkgbuild.relative_to(ROOT).as_posix()
        result = subprocess.run(
            ["bash", "-n", str(pkgbuild)],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            fail(f"PKGBUILD syntax error in {relative}: {result.stderr.strip()}")

        source = pkgbuild.read_text(encoding="utf-8")
        if re.search(r"-march\s*=\s*native", source):
            fail(f"host-specific -march=native found in {relative}")

        names = re.findall(r"^pkgname\s*=\s*['\"]?([A-Za-z0-9@._+-]+)", source, re.M)
        if not names:
            fail(f"could not statically identify pkgname in {relative}")

        for name in names:
            if name in seen_names:
                fail(f"duplicate package name {name}: {relative} and {seen_names[name]}")
            seen_names[name] = pkgbuild

        print(f"OK: {relative}")

    if not pkgbuilds:
        print("INFO: no PKGBUILDs yet; package-source audit is still pending.")

    profile = (ROOT / "packaging/profiles/znver5/makepkg.conf.example").read_text(
        encoding="utf-8"
    )
    if "-march=znver5" not in profile:
        fail("Zen 5 makepkg example must declare -march=znver5")
    if "-march=native" in profile:
        fail("Zen 5 profile must not use -march=native")

    print(f"PASS: {len(pkgbuilds)} PKGBUILD(s) checked.")
    print("PASS: repository foundation is structurally valid.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
