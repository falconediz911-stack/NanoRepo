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


def load_registry() -> dict[str, Any]:
    try:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load source registry: {exc}") from exc
    if data.get("schema_version") != 1 or not isinstance(data.get("sources"), dict):
        raise ValueError("unsupported or malformed source registry")
    return data["sources"]


def validate_event(event_type: str, source_repo: str, package_name: str | None = None) -> str:
    if event_type not in ALLOWED_EVENT_TYPES:
        raise ValueError(f"unsupported event type: {event_type}")

    sources = load_registry()
    source = sources.get(source_repo)
    if source is None:
        raise ValueError(f"source repository is not registered: {source_repo}")

    if event_type not in source.get("events", []):
        raise ValueError(f"{source_repo} is not allowed to send {event_type}")

    if event_type == "nanoos.tool.source.updated":
        if not source.get("package_builds", False):
            raise ValueError(f"{source_repo} is not registered as a package source")
        if not package_name:
            raise ValueError("tool update events must include a package name")
        if package_name not in source.get("packages", []):
            raise ValueError(f"package is not registered for {source_repo}: {package_name}")
        return f"ACCEPTED: {source_repo} updated registered package {package_name}"

    if source.get("package_builds", False):
        raise ValueError("metadata event unexpectedly targets a package-building source")
    return f"ACCEPTED: metadata-only event {event_type} from {source_repo}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-type", required=True)
    parser.add_argument("--source-repo", required=True)
    parser.add_argument("--package-name")
    args = parser.parse_args()

    try:
        result = validate_event(args.event_type, args.source_repo, args.package_name)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(result)
    if args.event_type == "nanoos.tool.source.updated":
        print("The package build workflow may now look for its matching PKGBUILD.")
    else:
        print("This event does not trigger Pacman package builds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
