"""Live system readings for the NanoOS Control Center dashboard.

Everything comes from /proc and /sys, so one sample costs well under a
millisecond. NVIDIA GPUs have no sysfs load/temperature, so their reading
comes from nvidia-smi, which the dashboard runs asynchronously (QProcess)
and never on the GUI thread.
"""

import glob
import os
import time
from pathlib import Path


def _read(path, default=""):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read().strip()
    except OSError:
        return default


def _hwmon(names):
    """First hwmon directory whose name is in `names`."""
    for directory in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        if _read(f"{directory}/name") in names:
            return directory
    return None


def _temp_by_label(directory, wanted):
    """Temperature (°C) of the input labelled one of `wanted`, else temp1."""
    if not directory:
        return None
    fallback = None
    for label_file in sorted(glob.glob(f"{directory}/temp*_label")):
        if _read(label_file) in wanted:
            value = _read(label_file.replace("_label", "_input"))
            if value.lstrip("-").isdigit():
                return int(value) / 1000
    value = _read(f"{directory}/temp1_input")
    if value.lstrip("-").isdigit():
        fallback = int(value) / 1000
    return fallback


class LiveSampler:
    """Call sample() once per tick; rates are computed between calls."""

    def __init__(self):
        self._cpu_prev = None
        self._net_prev = None
        self._net_time = None
        self.cpu_hwmon = _hwmon({"k10temp", "zenpower", "coretemp", "cpu_thermal"})
        self.amd_gpu = self._find_amd_gpu()

    # -------------------------------------------------------------- CPU
    def cpu_percent(self):
        line = _read("/proc/stat").split("\n", 1)[0].split()
        if not line or line[0] != "cpu":
            return None
        values = [int(v) for v in line[1:9]]
        idle = values[3] + values[4]
        total = sum(values)
        previous, self._cpu_prev = self._cpu_prev, (idle, total)
        if previous is None or total == previous[1]:
            return None
        return 100.0 * (1 - (idle - previous[0]) / (total - previous[1]))

    @staticmethod
    def cpu_clock_ghz():
        freqs = []
        for path in glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq"):
            value = _read(path)
            if value.isdigit():
                freqs.append(int(value))
        return (max(freqs) / 1e6, sum(freqs) / len(freqs) / 1e6) if freqs else (None, None)

    def cpu_temp(self):
        return _temp_by_label(self.cpu_hwmon, {"Tctl", "Tdie", "Package id 0"})

    # -------------------------------------------------------------- memory
    @staticmethod
    def memory():
        info = {}
        for line in _read("/proc/meminfo").splitlines():
            key, _, value = line.partition(":")
            parts = value.split()
            if parts and parts[0].isdigit():
                info[key] = int(parts[0]) * 1024
        total = info.get("MemTotal", 0)
        used = total - info.get("MemAvailable", 0)
        swap_total = info.get("SwapTotal", 0)
        swap_used = swap_total - info.get("SwapFree", 0)
        return used, total, swap_used, swap_total

    # -------------------------------------------------------------- network
    def network_rates(self):
        """(download, upload) in bytes/s over physical interfaces."""
        rx = tx = 0
        for line in _read("/proc/net/dev").splitlines()[2:]:
            name, _, data = line.partition(":")
            name = name.strip()
            if name == "lo" or name.startswith(("veth", "docker", "br-", "virbr", "tun", "tap")):
                continue
            fields = data.split()
            if len(fields) >= 9:
                rx += int(fields[0])
                tx += int(fields[8])
        now = time.monotonic()
        previous, previous_time = self._net_prev, self._net_time
        self._net_prev, self._net_time = (rx, tx), now
        if previous is None or now <= previous_time:
            return None, None
        span = now - previous_time
        return max(0, rx - previous[0]) / span, max(0, tx - previous[1]) / span

    # -------------------------------------------------------------- AMD GPU
    @staticmethod
    def _find_amd_gpu():
        """sysfs device of the AMD GPU, preferring a discrete card."""
        best = None
        for busy in sorted(glob.glob("/sys/class/drm/card[0-9]*/device/gpu_busy_percent")):
            device = os.path.dirname(busy)
            vram = _read(f"{device}/mem_info_vram_total")
            size = int(vram) if vram.isdigit() else 0
            if best is None or size > best[1]:
                best = (device, size)
        return best[0] if best else None

    def amd_gpu_sample(self):
        if not self.amd_gpu:
            return None
        busy = _read(f"{self.amd_gpu}/gpu_busy_percent")
        hwmon = (glob.glob(f"{self.amd_gpu}/hwmon/hwmon*") or [None])[0]
        temp = _temp_by_label(hwmon, {"edge", "junction"})
        used = _read(f"{self.amd_gpu}/mem_info_vram_used")
        total = _read(f"{self.amd_gpu}/mem_info_vram_total")
        return {
            "load": int(busy) if busy.isdigit() else None,
            "temp": temp,
            "vram_used": int(used) if used.isdigit() else None,
            "vram_total": int(total) if total.isdigit() else None,
        }


NVIDIA_QUERY = [
    "--query-gpu=utilization.gpu,temperature.gpu,clocks.gr,memory.used,memory.total,power.draw,name",
    "--format=csv,noheader,nounits",
]


def parse_nvidia(text):
    """First GPU line of nvidia-smi NVIDIA_QUERY output -> dict, or None."""
    line = (text or "").strip().splitlines()[:1]
    if not line:
        return None
    fields = [field.strip() for field in line[0].split(",")]
    if len(fields) < 7:
        return None

    def number(value):
        try:
            return float(value)
        except ValueError:
            return None

    return {
        "load": number(fields[0]),
        "temp": number(fields[1]),
        "clock": number(fields[2]),
        "vram_used": (number(fields[3]) or 0) * 1024 * 1024,
        "vram_total": (number(fields[4]) or 0) * 1024 * 1024,
        "power": number(fields[5]),
        "name": fields[6],
    }


def rate_text(value):
    if value is None:
        return "–"
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if value < 1000 or unit == "GB/s":
            return f"{value:.0f} {unit}" if unit == "B/s" else f"{value:.1f} {unit}"
        value /= 1000
    return "–"


def nvidia_present():
    return Path("/proc/driver/nvidia/version").is_file()
