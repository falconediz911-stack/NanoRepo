#!/usr/bin/env python3
"""Validate cross-repository events against NanoRepo's explicit source registry."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "source-registry.json"
ALLOWED_EVENT_TYPES = {
    "nanoos.tool.source.updated",
    "nanoos.iso.published",
    "nanoos.website.feed.updated",
}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_registry() -> dict[str, Any]:
    try:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot load source registry: {exc}")
    if data.get("schema_version") != 1 or not isinstance(data.get("sources"), dict):
        fail("unsupported or malformed source registry")
    return data["sources"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-type", required=True)
    parser.add_argument("--source-repo", required=True)
    parser.add_argument("--package-name")
    args = parser.parse_args()

    if args.event_type not in ALLOWED_EVENT_TYPES:
        fail(f"unsupported event type: {args.event_type}")

    sources = load_registry()
    source = sources.get(args.source_repo)
    if source is None:
        fail(f"source repository is not registered: {args.source_repo}")

    if args.event_type not in source.get("events", []):
        fail(f"{args.source_repo} is not allowed to send {args.event_type}")

    if args.event_type == "nanoos.tool.source.updated":
        if not source.get("package_builds", False):
            fail(f"{args.source_repo} is not registered as a package source")
        if not args.package_name:
            fail("tool update events must include --package-name")
        if args.package_name not in source.get("packages", []):
            fail(f"package is not registered for {args.source_repo}: {args.package_name}")
        print(f"ACCEPTED: {args.source_repo} updated registered package {args.package_name}")
        print("The package build workflow may now look for its matching PKGBUILD.")
    else:
        if source.get("package_builds", False):
            fail("metadata event unexpectedly targets a package-building source")
        print(f"ACCEPTED: metadata-only event {args.event_type} from {args.source_repo}")
        print("This event does not trigger Pacman package builds.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
