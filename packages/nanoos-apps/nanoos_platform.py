#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
from pathlib import Path
import shutil
import subprocess


def run(
    command,
    check=False,
):
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def read_file(
    path,
    default="",
):
    try:
        return Path(path).read_text(
            encoding="utf-8",
            errors="replace",
        ).strip()
    except OSError:
        return default


# ============================================================
# FIRMWARE
# ============================================================

def firmware():
    efi = Path(
        "/sys/firmware/efi"
    )

    if not efi.is_dir():
        return {
            "mode": "BIOS",
            "uefi_bits": None,
        }

    bits = 64

    value = read_file(
        efi / "fw_platform_size"
    )

    try:
        if int(value) in (32, 64):
            bits = int(value)
    except ValueError:
        pass

    return {
        "mode": "UEFI",
        "uefi_bits": bits,
    }


# ============================================================
# CPU / ZEN 5
# ============================================================

def cpu_info():
    result = run(
        [
            "lscpu",
        ],
        check=False,
    )

    data = {
        "model": "Unknown",
        "family": "",
        "vendor": "",
        "architecture": "",
    }

    for line in result.stdout.splitlines():

        if ":" not in line:
            continue

        key, value = line.split(
            ":",
            1,
        )

        key = key.strip().lower()
        value = value.strip()

        if key == "model name":
            data["model"] = value

        elif key == "cpu family":
            data["family"] = value

        elif key == "vendor id":
            data["vendor"] = value

        elif key == "architecture":
            data["architecture"] = value

    return data


def _cpuinfo_numbers():
    """(vendor, family, model) of the first CPU from /proc/cpuinfo."""
    vendor, family, model = "", -1, -1
    for line in read_file("/proc/cpuinfo").splitlines():
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key == "vendor_id" and not vendor:
            vendor = value
        elif key == "cpu family" and family < 0 and value.isdigit():
            family = int(value)
        elif key == "model" and model < 0 and value.isdigit():
            model = int(value)
        if vendor and family >= 0 and model >= 0:
            break
    return vendor, family, model


def cpu_profile():
    """AMD Zen generation of this CPU. NanoOS packages and kernels are
    built for every x86-64 CPU; this only drives Zen-specific tuning
    (preferred cores, X3D cache mode) and what Control Center shows."""
    info = cpu_info()
    vendor, family, model = _cpuinfo_numbers()
    profile = "generic"
    if vendor == "AuthenticAMD":
        if family == 0x1A:
            profile = "zen5"
        elif family == 0x19:
            # Family 19h covers Zen 3 and Zen 4; Zen 4 models per AMD's
            # revision guides (Raphael, Phoenix, Genoa, Dragon Range …).
            zen4 = (0x10 <= model <= 0x1F or 0x60 <= model <= 0x7F
                    or 0xA0 <= model <= 0xAF)
            profile = "zen4" if zen4 else "zen3"
        elif family == 0x17:
            profile = "zen2" if model >= 0x30 else "zen"
    return {
        "profile": profile,
        "x3d": bool(list(Path("/sys/bus/platform/drivers/amd_x3d_vcache").glob("*/amd_x3d_mode"))),
        "architecture": info,
    }


# ============================================================
# GPU
# ============================================================

def gpu_info():
    result = run(
        [
            "lspci",
            "-nnk",
        ],
        check=False,
    )

    devices = []

    current = None

    for line in result.stdout.splitlines():

        # With -nn lspci prints "VGA compatible controller [0300]:", so match
        # the class name followed by an optional [code] before the colon.
        if not line[:1].isspace() and re.search(
            r"(VGA compatible controller|3D controller|Display controller)"
            r"(?: \[[0-9a-f]{4}\])?:",
            line,
        ):

            current = {
                "device": line.strip(),
            }

            devices.append(
                current
            )

        elif line[:1] and not line[:1].isspace():
            # A different (non-GPU) device starts; stop attributing its
            # driver lines to the previous GPU.
            current = None

        elif (
            current is not None
            and (
                "Kernel driver in use:"
                in line
                or "Kernel modules:"
                in line
            )
        ):

            current.setdefault(
                "drivers",
                [],
            ).append(
                line.strip()
            )

    return devices


# ============================================================
# STORAGE
# ============================================================

def storage_info():
    result = run(
        [
            "lsblk",
            "-J",
            "-o",
            (
                "NAME,PATH,TYPE,SIZE,MODEL,FSTYPE,"
                "PTTYPE,PARTTYPE,LABEL,MOUNTPOINT,RO"
            ),
        ],
        check=False,
    )

    if result.returncode != 0:
        return {
            "blockdevices": [],
            "error": result.stderr.strip(),
        }

    try:
        return json.loads(
            result.stdout
        )
    except json.JSONDecodeError:
        return {
            "blockdevices": [],
            "error": "Invalid lsblk JSON.",
        }


# ============================================================
# KERNEL MANAGER
# ============================================================

def installed_kernels():
    result = run(
        [
            "pacman",
            "-Qq",
        ],
        check=False,
    )

    packages = []

    for line in result.stdout.splitlines():

        name = line.strip()

        if name.startswith(
            "linux"
        ):

            packages.append(
                name
            )

    return sorted(
        set(packages)
    )


def kernel_status():
    return {
        "running": read_file(
            "/proc/sys/kernel/osrelease"
        ),
        "installed": installed_kernels(),
    }


# ============================================================
# SCHEDULER MANAGER
# ============================================================

def scheduler_status():

    sched_ext = Path(
        "/sys/kernel/sched_ext"
    )

    loader = run(
        [
            "systemctl",
            "is-enabled",
            "scx_loader.service",
        ],
        check=False,
    )

    return {
        "sched_ext_available": (
            sched_ext.exists()
        ),
        "scx_loader": loader.stdout.strip()
        or loader.stderr.strip()
        or "unknown",
    }


# ============================================================
# SNAPSHOT MANAGER
# ============================================================

def filesystem_type(
    path="/",
):
    result = run(
        [
            "findmnt",
            "-n",
            "-o",
            "FSTYPE",
            path,
        ],
        check=False,
    )

    return (
        result.stdout.strip()
        or "unknown"
    )


def snapshot_status():

    fstype = filesystem_type(
        "/"
    )

    snapper = shutil.which(
        "snapper"
    )

    if not snapper:
        return {
            "filesystem": fstype,
            "snapper": False,
            "message": (
                "snapper is not installed."
            ),
        }

    result = run(
        [
            snapper,
            "list",
        ],
        check=False,
    )

    return {
        "filesystem": fstype,
        "snapper": True,
        "available": (
            result.returncode == 0
        ),
        "output": (
            result.stdout.strip()
            or result.stderr.strip()
        ),
    }


# ============================================================
# MIRROR MANAGER
# ============================================================

def mirror_status():

    configs = [
        "/etc/pacman.conf",
        "/etc/pacman.d/nanoos-repos.conf",
    ]

    result = {}

    for path in configs:

        text = read_file(
            path
        )

        result[path] = {
            "exists": bool(text),
            "nanoos": (
                "nanoos"
                in text.lower()
            ),
        }

    return result


# ============================================================
# SECURE BOOT
# ============================================================

def secure_boot_status():

    mokutil = shutil.which(
        "mokutil"
    )

    if mokutil:

        result = run(
            [
                mokutil,
                "--sb-state",
            ],
            check=False,
        )

        output = (
            result.stdout.strip()
            or result.stderr.strip()
        )

        return {
            "tool": "mokutil",
            "status": output,
        }

    variables = Path(
        "/sys/firmware/efi/efivars"
    )

    if not variables.is_dir():

        return {
            "tool": None,
            "status": "BIOS / EFI variables unavailable",
        }

    # Without mokutil, read the SecureBoot EFI variable directly: four
    # attribute bytes, then one byte that is 1 when Secure Boot is on.
    for variable in variables.glob("SecureBoot-*"):
        try:
            data = variable.read_bytes()
        except OSError:
            continue
        if len(data) >= 5:
            return {
                "tool": "efivars",
                "status": "Enabled" if data[4] == 1 else "Disabled",
            }

    return {
        "tool": None,
        "status": (
            "UEFI detected; Secure Boot "
            "state could not be queried."
        ),
    }


# ============================================================
# BOOT MANAGER
# ============================================================

def boot_manager_status():

    found = []

    checks = {
        "GRUB": [
            "/boot/grub",
            "/usr/bin/grub-install",
        ],
        "systemd-boot": [
            "/boot/loader",
            "/usr/lib/systemd/systemd-boot",
        ],
        "Limine": [
            "/boot/EFI/BOOT/limine.conf",
            "/boot/limine.conf",
        ],
        "rEFInd": [
            "/boot/EFI/refind",
            "/boot/refind",
        ],
    }

    for name, paths in checks.items():

        if any(
            Path(path).exists()
            for path in paths
        ):
            found.append(
                name
            )

    return found


# ============================================================
# GAMING
# ============================================================

def gaming_status():

    wanted = [
        "steam",
        "gamescope",
        "mangohud",
        "gamemode",
        "obs-studio",
        "wine",
        "winetricks",
        "protontricks",
    ]

    installed = set(
        installed_kernels()
    )

    # Query pacman separately because these are not kernels.
    result = run(
        [
            "pacman",
            "-Qq",
        ],
        check=False,
    )

    installed = set(
        result.stdout.splitlines()
    )

    return {
        package: package in installed
        for package in wanted
    }


# ============================================================
# HARDWARE PROFILE
# ============================================================

def hardware_profile():

    profile = cpu_profile()

    firmware_info = firmware()

    return {
        "cpu_profile": profile[
            "profile"
        ],
        "compiler_target": profile[
            "compiler_target"
        ],
        "cpu": profile[
            "architecture"
        ],
        "firmware": firmware_info,
    }


# ============================================================
# FULL REPORT
# ============================================================

def full_report():

    profile = hardware_profile()

    return {
        "firmware": firmware(),
        "cpu": cpu_info(),
        "cpu_profile": profile,
        "gpu": gpu_info(),
        "storage": storage_info(),
        "kernel": kernel_status(),
        "scheduler": scheduler_status(),
        "snapshots": snapshot_status(),
        "mirrors": mirror_status(),
        "secure_boot": secure_boot_status(),
        "boot_managers": boot_manager_status(),
        "gaming": gaming_status(),
    }


# ============================================================
# LIVE ISO GUARD
# ============================================================

def running_live_iso():

    return (
        Path(
            "/run/archiso"
        ).exists()
        or Path(
            "/etc/archiso"
        ).exists()
    )


def require_installed_system():

    if running_live_iso():
        raise RuntimeError(
            "This operation is disabled in the "
            "live ISO. It may only modify an "
            "installed NanoOS system."
        )


# ============================================================
# UPDATE
# ============================================================

def system_update():

    require_installed_system()

    # Inherit the terminal: pacman must be able to show its prompts and
    # progress (capturing output made it wait invisibly for an answer).
    return subprocess.run(
        ["pacman", "-Syu"],
        check=False,
    )


# ============================================================
# MANAGER DISPATCH
# ============================================================

def command_status(command):

    commands = {
        "status": full_report,
        "hardware": lambda: {
            "cpu": cpu_info(),
            "gpu": gpu_info(),
            "storage": storage_info(),
        },
        "kernel": kernel_status,
        "scheduler": scheduler_status,
        "snapshot": snapshot_status,
        "mirror": mirror_status,
        "secureboot": secure_boot_status,
        "boot": boot_manager_status,
        "gaming": gaming_status,
        "profile": hardware_profile,
    }

    if command == "update":

        result = system_update()

        return {
            "returncode": result.returncode,
        }

    if command not in commands:

        raise ValueError(
            "Unknown command: "
            + command
        )

    return commands[command]()
