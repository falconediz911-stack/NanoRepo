#!/usr/bin/env python3

import json
import os
import platform
import re
import subprocess
import shutil
import sys
from pathlib import Path


CPUFREQ = Path("/sys/devices/system/cpu/cpufreq")
PLATFORM_PROFILE = Path("/sys/firmware/acpi/platform_profile")
PLATFORM_PROFILES = Path("/sys/firmware/acpi/platform_profile_choices")


def read_text(path):
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None


def write_sysfs(path, value):
    path = Path(path)

    try:
        path.write_text(str(value), encoding="ascii")
        return True, ""
    except PermissionError:
        pass
    except OSError as exc:
        return False, str(exc)

    try:
        result = subprocess.run(
            [
                "pkexec",
                "/usr/bin/tee",
                str(path),
            ],
            input=str(value) + "\n",
            text=True,
            capture_output=True,
            timeout=20,
        )

        if result.returncode == 0:
            return True, ""

        return False, (
            result.stderr.strip()
            or "Privileged write failed."
        )

    except FileNotFoundError:
        return False, "pkexec is not installed."
    except subprocess.TimeoutExpired:
        return False, "Privileged write timed out."
    except OSError as exc:
        return False, str(exc)


def cpu_info():
    info = {
        "architecture": platform.machine(),
        "vendor": "Unknown",
        "model": "Unknown",
        "family": None,
        "model_number": None,
        "stepping": None,
        "microcode": None,
        "logical_cpus": os.cpu_count() or 1,
    }

    try:
        cpuinfo = Path("/proc/cpuinfo").read_text(
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return info

    first_cpu = cpuinfo.split("\n\n", 1)[0]

    fields = {}

    for line in first_cpu.splitlines():
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()

    info["vendor"] = (
        fields.get("vendor_id")
        or fields.get("CPU implementer")
        or fields.get("Hardware")
        or "Unknown"
    )

    info["model"] = (
        fields.get("model name")
        or fields.get("Processor")
        or fields.get("Model")
        or "Unknown"
    )

    info["family"] = fields.get("cpu family")
    info["model_number"] = fields.get("model")
    info["stepping"] = fields.get("stepping")
    info["microcode"] = fields.get("microcode")

    return info


def cpu_policies():
    policies = []

    if not CPUFREQ.exists():
        return policies

    for policy in sorted(CPUFREQ.glob("policy*")):
        if not policy.is_dir():
            continue

        available_governors = read_text(
            policy / "scaling_available_governors"
        )

        epp_choices = read_text(
            policy / "energy_performance_available_preferences"
        )

        policies.append(
            {
                "path": str(policy),
                "name": policy.name,
                "driver": read_text(
                    policy / "scaling_driver"
                ),
                "governor": read_text(
                    policy / "scaling_governor"
                ),
                "available_governors": (
                    available_governors.split()
                    if available_governors
                    else []
                ),
                "epp": read_text(
                    policy / "energy_performance_preference"
                ),
                "available_epp": (
                    epp_choices.split()
                    if epp_choices
                    else []
                ),
                "related_cpus": read_text(
                    policy / "related_cpus"
                ),
                "min_freq": read_text(
                    policy / "scaling_min_freq"
                ),
                "max_freq": read_text(
                    policy / "scaling_max_freq"
                ),
            }
        )

    return policies


def _normalize_pci_slot(slot):
    if not slot:
        return None

    slot = slot.strip()

    # nvidia-smi may return 00000000:01:00.0 while sysfs/lspci
    # uses 0000:01:00.0.
    match = re.search(
        r"(?:[0-9a-fA-F]{4,8}:)?"
        r"([0-9a-fA-F]{2}):"
        r"([0-9a-fA-F]{2})\."
        r"([0-9])$",
        slot,
    )

    if not match:
        return slot

    return (
        f"0000:{match.group(1).lower()}:"
        f"{match.group(2).lower()}.{match.group(3)}"
    )


def _gpu_vendor_name(vendor_id):
    vendors = {
        "0x1002": "AMD",
        "0x10de": "NVIDIA",
        "0x8086": "Intel",
    }

    return vendors.get(
        vendor_id.lower(),
        "Unknown",
    )


def _gpu_driver(device):
    driver = device / "driver"

    if driver.is_symlink():
        try:
            return driver.resolve().name
        except OSError:
            pass

    return None


def _gpu_pci_slot(device):
    current = device

    # The DRM device usually resolves to:
    # /sys/devices/.../0000:bb:ss.f
    for _ in range(8):
        name = current.name

        if re.fullmatch(
            r"[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:"
            r"[0-9a-fA-F]{2}\.[0-9]",
            name,
        ):
            return _normalize_pci_slot(name)

        if current.parent == current:
            break

        current = current.parent

    return None


def _lspci_gpu_name(slot):
    if not shutil.which("lspci") or not slot:
        return None

    try:
        result = subprocess.run(
            [
                "lspci",
                "-Dnn",
                "-s",
                slot,
            ],
            capture_output=True,
            text=True,
            timeout=3,
        )

        if result.returncode != 0:
            return None

        for line in result.stdout.splitlines():
            match = re.match(
                r"^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:"
                r"[0-9a-fA-F]{2}\.[0-9]\s+"
                r".*?:\s+(.+?)\s+"
                r"\[[0-9a-fA-F]{4}:"
                r"[0-9a-fA-F]{4}\]",
                line,
            )

            if match:
                return match.group(1).strip()

    except (OSError, subprocess.TimeoutExpired):
        pass

    return None


def _vulkan_gpus():
    """
    Read Vulkan physical-device information.

    Vulkan gives us a vendor-neutral deviceType:
      INTEGRATED_GPU
      DISCRETE_GPU
      VIRTUAL_GPU
      CPU
      OTHER

    vendorID/deviceID let us associate the Vulkan device with the
    PCI/DRM device discovered through sysfs.
    """

    if not shutil.which("vulkaninfo"):
        return []

    try:
        result = subprocess.run(
            [
                "vulkaninfo",
                "--summary",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return []

    except (OSError, subprocess.TimeoutExpired):
        return []

    devices = []
    current = None

    for raw_line in result.stdout.splitlines():
        line = raw_line.rstrip()

        if re.match(
            r"^\s*GPU[0-9]+:\s*$",
            line,
        ):
            if current:
                devices.append(current)

            current = {
                "vendor_id": None,
                "device_id": None,
                "device_type": None,
                "name": None,
            }

            continue

        if current is None:
            continue

        match = re.match(
            r"^\s*(vendorID|deviceID|deviceType|deviceName)"
            r"\s*=\s*(.+?)\s*$",
            line,
        )

        if not match:
            continue

        key, value = match.groups()

        if key == "vendorID":
            current["vendor_id"] = value.strip()

        elif key == "deviceID":
            current["device_id"] = value.strip()

        elif key == "deviceType":
            current["device_type"] = value.strip()

        elif key == "deviceName":
            current["name"] = value.strip()

    if current:
        devices.append(current)

    return devices


def _classify_from_vulkan(vulkan_device):
    if not vulkan_device:
        return "unknown", "none"

    device_type = (
        vulkan_device.get("device_type")
        or ""
    ).upper()

    if "INTEGRATED_GPU" in device_type:
        return "integrated", "high"

    if "DISCRETE_GPU" in device_type:
        return "dedicated", "high"

    if "VIRTUAL_GPU" in device_type:
        return "virtual", "high"

    if "CPU" in device_type:
        return "cpu", "high"

    return "unknown", "low"


def _pci_ancestor_slots(device):
    """Return PCI BDFs found while walking upward through sysfs."""

    slots = []
    current = Path(device)

    for _ in range(10):
        current = current.parent

        name = current.name

        if re.fullmatch(
            r"[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:"
            r"[0-9a-fA-F]{2}\.[0-9]",
            name,
        ):
            slots.append(
                _normalize_pci_slot(name)
            )

    return slots


def _pci_ancestor_text(device):
    """Read human-readable descriptions of the PCI ancestors."""

    if not shutil.which("lspci"):
        return ""

    descriptions = []

    for slot in _pci_ancestor_slots(device):
        try:
            result = subprocess.run(
                [
                    "lspci",
                    "-Dnn",
                    "-s",
                    slot,
                ],
                capture_output=True,
                text=True,
                timeout=3,
            )

            if result.returncode == 0:
                descriptions.append(
                    result.stdout.strip().lower()
                )

        except (OSError, subprocess.TimeoutExpired):
            continue

    return "\n".join(descriptions)


def _classify_from_pci_topology(device, vendor, name):
    """
    Conservative fallback when Vulkan does not expose the GPU.

    Signals:
      * AMD Internal GPP Bridge -> integrated hint
      * explicit 'integrated graphics' -> integrated
      * Intel's common 00:02.x integrated-GPU placement -> integrated
      * conventional PCIe Root Port -> dedicated hint

    This function deliberately returns a confidence level so the
    frontend can avoid presenting uncertain classifications as fact.
    """

    ancestor_text = _pci_ancestor_text(device)
    lower_name = (name or "").lower()

    # Strong AMD APU/iGPU topology signal.
    if (
        vendor == "AMD"
        and (
            "internal gpp bridge" in ancestor_text
            or "internal gpp" in ancestor_text
        )
    ):
        return "integrated", "high", (
            "AMD internal GPP bridge topology"
        )

    # Explicit terminology from firmware/PCI databases.
    if "integrated graphics" in lower_name:
        return "integrated", "high", (
            "hardware name reports integrated graphics"
        )

    # Common Intel integrated graphics placement.
    slot = _normalize_pci_slot(
        _gpu_pci_slot(device)
    )

    if (
        vendor == "Intel"
        and slot
        and re.fullmatch(
            r"0000:00:02\.[0-9]",
            slot,
        )
    ):
        return "integrated", "medium", (
            "Intel graphics device on common 00:02.x topology"
        )

    # A conventional PCIe root-port path is a useful dedicated-GPU
    # hint, but not strong enough for high confidence.
    if "pci express root port" in ancestor_text:
        return "dedicated", "medium", (
            "GPU is behind a conventional PCIe root port"
        )

    return "unknown", "none", (
        "No reliable integrated/discrete signal available"
    )



def _nvidia_smi_gpus():
    if not shutil.which("nvidia-smi"):
        return []

    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,pci.bus_id,driver_version,"
                "memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return []

    except (OSError, subprocess.TimeoutExpired):
        return []

    devices = []

    for line in result.stdout.splitlines():
        fields = [
            field.strip()
            for field in line.split(",")
        ]

        if len(fields) != 4:
            continue

        name, bus_id, driver_version, memory_mb = fields

        try:
            memory_bytes = (
                int(float(memory_mb))
                * 1024
                * 1024
            )
        except ValueError:
            memory_bytes = None

        devices.append(
            {
                "vendor": "NVIDIA",
                "name": name,
                "pci_slot": _normalize_pci_slot(bus_id),
                "driver_version": driver_version,
                "vram_bytes": memory_bytes,
            }
        )

    return devices


def gpu_devices():
    drm_root = Path("/sys/class/drm")

    if not drm_root.exists():
        return []

    cards = sorted(
        (
            card
            for card in drm_root.glob("card[0-9]*")
            if card.name[4:].isdigit()
        ),
        key=lambda path: int(path.name[4:]),
    )

    vulkan = _vulkan_gpus()
    nvidia = _nvidia_smi_gpus()

    results = []

    for card in cards:
        try:
            device = card.resolve() / "device"
        except OSError:
            continue

        if not device.exists():
            continue

        vendor_id = read_text(
            device / "vendor"
        )

        device_id = read_text(
            device / "device"
        )

        if vendor_id is None:
            continue

        vendor = _gpu_vendor_name(vendor_id)

        normalized_vendor_id = vendor_id.lower()

        normalized_device_id = (
            device_id.lower()
            if device_id
            else None
        )

        pci_slot = _gpu_pci_slot(device)

        driver = _gpu_driver(device)

        matching_vulkan = None

        for vk in vulkan:
            vk_vendor = (
                vk.get("vendor_id") or ""
            ).lower()

            vk_device = (
                vk.get("device_id") or ""
            ).lower()

            vk_vendor = (
                vk_vendor
                if vk_vendor.startswith("0x")
                else f"0x{vk_vendor}"
            )

            vk_device = (
                vk_device
                if vk_device.startswith("0x")
                else f"0x{vk_device}"
            )

            if (
                vk_vendor == normalized_vendor_id
                and vk_device == normalized_device_id
            ):
                matching_vulkan = vk
                break

        gpu_type, confidence = _classify_from_vulkan(
            matching_vulkan
        )

        name = None

        if matching_vulkan:
            name = matching_vulkan.get("name")

        if not name:
            name = _lspci_gpu_name(pci_slot)

        if not name:
            name = f"{vendor} GPU"

        if gpu_type == "unknown":
            (
                topology_type,
                topology_confidence,
                topology_reason,
            ) = _classify_from_pci_topology(
                device,
                vendor,
                name,
            )

            if topology_type != "unknown":
                gpu_type = topology_type
                confidence = topology_confidence
            else:
                topology_reason = (
                    "No reliable integrated/discrete signal available"
                )
        else:
            topology_reason = (
                "Vulkan physical-device classification"
            )

        entry = {
            "vendor": vendor,
            "name": name,
            "type": gpu_type,
            "classification_confidence": confidence,
            "classification_reason": topology_reason,
            "driver": driver,
            "pci_slot": pci_slot,
            "pci_vendor_id": vendor_id,
            "pci_device_id": device_id,
            "boot_vga": read_text(
                device / "boot_vga"
            ),
            "drm_card": card.name,
            "vram_bytes": None,
            "driver_version": None,
            "vulkan_device_type": (
                matching_vulkan.get("device_type")
                if matching_vulkan
                else None
            ),
            "source": "sysfs",
        }

        # amdgpu commonly exposes VRAM information through sysfs.
        vram = read_text(
            device / "mem_info_vram_total"
        )

        if vram:
            try:
                entry["vram_bytes"] = int(vram)
            except ValueError:
                pass

        # Merge nvidia-smi data instead of adding a duplicate GPU.
        if vendor == "NVIDIA":
            for nv in nvidia:
                if (
                    nv.get("pci_slot")
                    and pci_slot
                    and nv["pci_slot"] == pci_slot
                ):
                    entry["name"] = nv["name"]
                    entry["driver_version"] = (
                        nv["driver_version"]
                    )
                    entry["vram_bytes"] = (
                        nv["vram_bytes"]
                    )

                    if entry["type"] == "unknown":
                        # nvidia-smi identifies a real NVIDIA GPU,
                        # but we still don't infer integrated/discrete
                        # without Vulkan or another reliable classifier.
                        entry["classification_confidence"] = "low"

                    entry["source"] = (
                        "sysfs+nvidia-smi"
                    )

                    break

        results.append(entry)

    return results


def boost_capability():
    boost = CPUFREQ / "boost"

    if not boost.exists():
        return {
            "supported": False,
            "path": None,
            "value": None,
        }

    return {
        "supported": True,
        "path": str(boost),
        "value": read_text(boost),
    }


def platform_profile():
    sysfs_supported = PLATFORM_PROFILE.exists()

    profiles = []

    if PLATFORM_PROFILES.exists():
        choices = read_text(PLATFORM_PROFILES)
        if choices:
            profiles = choices.split()

    powerprofiles = False
    powerprofile_current = None

    if Path("/usr/bin/powerprofilesctl").exists():
        powerprofiles = True

        try:
            result = subprocess.run(
                ["powerprofilesctl", "get"],
                capture_output=True,
                text=True,
                timeout=4,
            )

            if result.returncode == 0:
                powerprofile_current = result.stdout.strip()

        except (OSError, subprocess.TimeoutExpired):
            pass

    return {
        "sysfs_supported": sysfs_supported,
        "sysfs_path": str(PLATFORM_PROFILE)
        if sysfs_supported
        else None,
        "current": read_text(PLATFORM_PROFILE)
        if sysfs_supported
        else powerprofile_current,
        "choices": profiles,
        "powerprofilesctl": powerprofiles,
    }


def gamemode_info():
    executable = "gamemoded"

    if not Path("/usr/bin/gamemoded").exists():
        return {
            "installed": False,
            "version": None,
        }

    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=4,
        )

        output = (
            result.stdout + "\n" + result.stderr
        ).strip()

        match = re.search(
            r"v?([0-9]+(?:\.[0-9]+)+)",
            output,
        )

        return {
            "installed": True,
            "version": match.group(1)
            if match
            else None,
        }

    except (OSError, subprocess.TimeoutExpired):
        return {
            "installed": True,
            "version": None,
        }


def capabilities():
    policies = cpu_policies()

    governor_sets = [
        set(policy["available_governors"])
        for policy in policies
        if policy["available_governors"]
    ]

    common_governors = (
        sorted(set.intersection(*governor_sets))
        if governor_sets
        else []
    )

    epp_sets = [
        set(policy["available_epp"])
        for policy in policies
        if policy["available_epp"]
    ]

    common_epp = (
        sorted(set.intersection(*epp_sets))
        if epp_sets
        else []
    )

    return {
        "cpu": cpu_info(),
        "gpus": gpu_devices(),
        "policies": policies,
        "governors": common_governors,
        "epp": common_epp,
        "boost": boost_capability(),
        "platform_profile": platform_profile(),
        "gamemode": gamemode_info(),
    }


def set_boost(enabled):
    capability = boost_capability()

    if not capability["supported"]:
        return False, (
            "This kernel/CPU driver does not expose "
            "the generic CPU boost control."
        )

    return write_sysfs(
        Path(capability["path"]),
        "1" if enabled else "0",
    )


def set_governor(governor):
    policies = cpu_policies()

    if not policies:
        return False, "No CPUFreq policies were detected."

    for policy in policies:
        if governor not in policy["available_governors"]:
            return False, (
                f"Governor '{governor}' is not available "
                f"for {policy['name']}."
            )

    for policy in policies:
        ok, error = write_sysfs(
            Path(policy["path"]) / "scaling_governor",
            governor,
        )

        if not ok:
            return False, error

    return True, ""


def set_epp(value):
    policies = cpu_policies()

    if not policies:
        return False, "No CPUFreq policies were detected."

    for policy in policies:
        if not policy["available_epp"]:
            return False, (
                "Energy-performance preference is not "
                "available on every CPU policy."
            )

        if value not in policy["available_epp"]:
            return False, (
                f"EPP '{value}' is not available "
                f"for {policy['name']}."
            )

    for policy in policies:
        ok, error = write_sysfs(
            Path(policy["path"])
            / "energy_performance_preference",
            value,
        )

        if not ok:
            return False, error

    return True, ""


def set_platform_profile(profile):
    if PLATFORM_PROFILE.exists():
        choices = read_text(
            PLATFORM_PROFILES
        )

        if choices and profile not in choices.split():
            return False, (
                f"Platform profile '{profile}' "
                "is not available."
            )

        return write_sysfs(
            PLATFORM_PROFILE,
            profile,
        )

    if Path("/usr/bin/powerprofilesctl").exists():
        try:
            result = subprocess.run(
                [
                    "powerprofilesctl",
                    "set",
                    profile,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                return True, ""

            return False, (
                result.stderr.strip()
                or "powerprofilesctl failed."
            )

        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, str(exc)

    return False, (
        "No supported platform-profile interface "
        "was detected."
    )


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="NanoOS GameMode hardware backend"
    )

    sub = parser.add_subparsers(
        dest="command",
        required=True,
    )

    sub.add_parser("detect")

    boost = sub.add_parser("boost")
    boost.add_argument(
        "state",
        choices=["on", "off"],
    )

    governor = sub.add_parser("governor")
    governor.add_argument(
        "value",
    )

    epp = sub.add_parser("epp")
    epp.add_argument(
        "value",
    )

    profile = sub.add_parser("platform-profile")
    profile.add_argument(
        "value",
    )

    args = parser.parse_args()

    if args.command == "detect":
        print(
            json.dumps(
                capabilities(),
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "boost":
        ok, error = set_boost(args.state == "on")
    elif args.command == "governor":
        ok, error = set_governor(args.value)
    elif args.command == "epp":
        ok, error = set_epp(args.value)
    elif args.command == "platform-profile":
        ok, error = set_platform_profile(args.value)
    else:
        return 2

    if not ok:
        print(error, file=sys.stderr)
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
