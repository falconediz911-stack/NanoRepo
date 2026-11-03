#!/usr/bin/env python3
"""Read-only CPU and cpufreq capability inspector for NanoOS.

This first CPU Engine component intentionally does not write sysfs settings.
It reports what the current kernel exposes so later profile code can make
capability-aware decisions rather than assuming a particular driver or EPP.
"""

from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
from typing import Any


VERSION = "0.1.0"
DEFAULT_CPUINFO = Path("/proc/cpuinfo")
DEFAULT_CPUFREQ_ROOT = Path("/sys/devices/system/cpu/cpufreq")


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None


def parse_cpuinfo(contents: str) -> dict[str, Any]:
    """Parse the first Linux /proc/cpuinfo processor block."""
    first_block = contents.strip().split("\n\n", 1)[0] if contents.strip() else ""
    fields: dict[str, str] = {}

    for line in first_block.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip().lower()] = value.strip()

    raw_flags = fields.get("flags", fields.get("features", ""))
    return {
        "vendor_id": fields.get("vendor_id", fields.get("cpu implementer")),
        "model_name": fields.get("model name", fields.get("hardware")),
        "family": fields.get("cpu family"),
        "model": fields.get("model"),
        "stepping": fields.get("stepping"),
        "flags": sorted(set(raw_flags.split())),
    }


def _read_policy(policy_dir: Path) -> dict[str, Any]:
    names = (
        "scaling_driver",
        "scaling_governor",
        "scaling_available_governors",
        "energy_performance_preference",
        "energy_performance_available_preferences",
        "scaling_min_freq",
        "scaling_max_freq",
        "scaling_cur_freq",
    )
    values: dict[str, Any] = {"policy": policy_dir.name}

    for name in names:
        value = _read_text(policy_dir / name)
        if value is None:
            continue
        if name.endswith("_governors") or name.endswith("_preferences"):
            values[name] = value.split()
        else:
            values[name] = value

    available_epp = values.get("energy_performance_available_preferences", [])
    values["epp_supported"] = bool(available_epp)
    return values


def collect_snapshot(
    cpuinfo_path: Path = DEFAULT_CPUINFO,
    cpufreq_root: Path = DEFAULT_CPUFREQ_ROOT,
) -> dict[str, Any]:
    """Collect a read-only CPU/cpufreq snapshot from procfs and sysfs."""
    cpuinfo_contents = _read_text(cpuinfo_path) or ""
    cpu = parse_cpuinfo(cpuinfo_contents)

    try:
        policy_dirs = sorted(
            (path for path in cpufreq_root.glob("policy*") if path.is_dir()),
            key=lambda path: path.name,
        )
    except OSError:
        policy_dirs = []

    policies = [_read_policy(path) for path in policy_dirs]
    return {
        "tool": "nanoos-cpu-info",
        "version": VERSION,
        "architecture": platform.machine(),
        "cpu": {
            "vendor_id": cpu["vendor_id"],
            "model_name": cpu["model_name"],
            "family": cpu["family"],
            "model": cpu["model"],
            "stepping": cpu["stepping"],
            "logical_processors": len(
                [line for line in cpuinfo_contents.splitlines()
                 if line.strip().startswith("processor") and ":" in line]
            ),
            "flags": cpu["flags"],
        },
        "cpufreq": {
            "policy_count": len(policies),
            "policies": policies,
            "any_epp_available": any(item["epp_supported"] for item in policies),
        },
        "access": {
            "mode": "read-only",
            "writes_sysfs": False,
            "requires_root": False,
        },
    }


def render_text(snapshot: dict[str, Any]) -> str:
    cpu = snapshot["cpu"]
    cpufreq = snapshot["cpufreq"]
    lines = [
        f'NanoOS CPU Info {snapshot["version"]}',
        "=" * 48,
        f'Architecture: {snapshot["architecture"]}',
        f'CPU: {cpu["model_name"] or "Unknown"}',
        f'Vendor: {cpu["vendor_id"] or "Unknown"}',
        f'Family / model: {cpu["family"] or "?"} / {cpu["model"] or "?"}',
        f'Logical processors: {cpu["logical_processors"] or "Unknown"}',
        "",
        "CPU frequency interface",
        "-" * 48,
        f'Policies detected: {cpufreq["policy_count"]}',
        f'EPP available: {"yes" if cpufreq["any_epp_available"] else "no / not exposed"}',
    ]

    if not cpufreq["policies"]:
        lines.append("No cpufreq policy directories were found.")

    for policy in cpufreq["policies"]:
        lines.extend([
            "",
            f'[{policy["policy"]}]',
            f'  Driver: {policy.get("scaling_driver", "not exposed")}',
            f'  Governor: {policy.get("scaling_governor", "not exposed")}',
            f'  Available governors: {", ".join(policy.get("scaling_available_governors", [])) or "not exposed"}',
            f'  EPP: {policy.get("energy_performance_preference", "not exposed")}',
            f'  Available EPP: {", ".join(policy.get("energy_performance_available_preferences", [])) or "not exposed"}',
        ])

    lines.extend([
        "",
        "Safety: read-only inspection; no settings were changed.",
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect CPU and Linux cpufreq capabilities without changing settings."
    )
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    args = parser.parse_args(argv)

    snapshot = collect_snapshot()
    if args.json:
        print(json.dumps(snapshot, indent=2, sort_keys=True))
    else:
        print(render_text(snapshot))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
