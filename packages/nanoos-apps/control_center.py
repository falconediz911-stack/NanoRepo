#!/usr/bin/env python3
"""NanoOS Control Center.

Live system dashboard, CPU Boost modes, gaming tools, kernels and boot,
storage, snapshots, an update center and system details. Built on the shared NanoOS UI kit so it looks
and works like NanoOS Welcome: the same shell, cards and buttons, and
administrator actions run through pkexec with live output in the panel.
"""

import getpass
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    from PySide6.QtCore import QProcess, QThread, QTimer, Signal
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QGridLayout, QInputDialog, QWidget
except ImportError:
    print("NanoOS Control Center requires PySide6 (pacman -S pyside6).", file=sys.stderr)
    sys.exit(1)

import nanoos_platform as platform_api
import nanoos_live as live
from nanoos_ui import ActionCard, NanoShell, StatTile

APP_NAME = "NanoOS Control Center"
VERSION = "2.0"
BOOT_CONFIG = "/usr/lib/nanoos-apps/nanoos-boot-config"
GRUB_DISPLAY = "/usr/bin/nanoos-grub-display"
CPU_BOOST = "/usr/local/bin/nanoos-cpu-boost"
CPU_BOOST_STATE = Path("/etc/nanoos/cpu-boost.conf")
GAMEMODE_APP = "/usr/bin/nanoos-gamemode"
WELCOME_APP = "/usr/bin/nanoos-welcome"
DESKTOP_ID = "org.nanoos.ControlCenter"


def _nanoos_edition():
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if line.startswith("NAME="):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return "NanoOS"


# NanoOS Basic has no gaming apps; every other NanoOS install is Gaming.
GAMING = _nanoos_edition() != "NanoOS Basic"

CPU_MODES = [
    ("ultra-power-saving", "Ultra Power Saving", "Quietest and coolest. Best on battery."),
    ("balanced", "Balanced", "Responsive desktop with sensible power use."),
    ("performance", "Performance", "Favors clock speed for heavy work."),
    ("gaming", "Gaming", "Maximum boost hint for the lowest frame times."),
]

ZEN_NAMES = {"zen": "AMD Zen", "zen2": "AMD Zen 2", "zen3": "AMD Zen 3",
             "zen4": "AMD Zen 4", "zen5": "AMD Zen 5"}

GAMING_TOOLS = [
    ("steam", "Steam", "Valve's PC gaming platform."),
    ("gamescope", "Gamescope", "SteamOS-style micro-compositor."),
    ("mangohud", "MangoHud", "Gaming performance overlay."),
    ("nanoos-gamemode", "NanoOS Game Mode", "Per-game profiles and gaming optimizations."),
    ("gamemode", "GameMode", "Game performance optimization daemon."),
    ("wine", "Wine", "Windows compatibility layer."),
    ("winetricks", "Winetricks", "Helper for Wine environments."),
    ("protontricks", "Protontricks", "Winetricks for Proton games."),
    ("obs-studio", "OBS Studio", "Recording and streaming."),
]


# ---------------------------------------------------------------- data
def human_bytes(value):
    value = float(value or 0)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024


def os_pretty_name():
    for path in ("/etc/os-release", "/usr/lib/os-release"):
        for line in platform_api.read_file(path).splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip().strip('"')
    return "NanoOS"


def uptime_text():
    try:
        seconds = int(float(Path("/proc/uptime").read_text().split()[0]))
    except (OSError, ValueError, IndexError):
        return "unknown"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    parts = ([f"{days}d"] if days else []) + ([f"{hours}h"] if hours or days else []) + [f"{minutes}m"]
    return " ".join(parts)


def memory_usage():
    info = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            info[key] = int(value.split()[0]) * 1024
    except (OSError, ValueError):
        return 0, 0
    total = info.get("MemTotal", 0)
    return total - info.get("MemAvailable", 0), total


def gpu_summary(devices):
    """lspci lines -> [(\"NVIDIA GeForce RTX 5070 Ti\", \"nvidia\"), ...]."""
    out = []
    for device in devices:
        line = device.get("device", "")
        text = line.split("]: ", 1)[-1] if "]: " in line else line.split(": ", 1)[-1]
        text = re.sub(r"\s*\(rev [0-9a-f]+\)", "", text)
        text = re.sub(r"\s*\[[0-9a-f]{4}:[0-9a-f]{4}\]", "", text)
        vendor = ("NVIDIA" if text.startswith("NVIDIA") else
                  "AMD" if text.startswith("Advanced Micro Devices") else
                  "Intel" if text.startswith("Intel") else "")
        models = [m for m in re.findall(r"\[([^\]]+)\]", text) if m != "AMD/ATI"]
        name = f"{vendor} {models[-1]}".strip() if models else text
        driver = ""
        for entry in device.get("drivers", []):
            if "in use" in entry:
                driver = entry.split(":", 1)[1].strip()
        out.append((name, driver))
    return out


def saved_cpu_mode():
    text = platform_api.read_file(str(CPU_BOOST_STATE))
    for line in text.splitlines():
        line = line.strip()
        if "=" in line:
            key, value = line.split("=", 1)
            if key.strip().lower() in {"profile", "mode"}:
                return value.strip().strip('"')
        elif line and not line.startswith("#"):
            return line
    return ""


def cpu_epp_summary():
    if not os.path.isfile(CPU_BOOST):
        return {"available": False}
    result = platform_api.run([sys.executable, CPU_BOOST, "status"])
    driver = current = ""
    for line in result.stdout.splitlines():
        if "driver:" in line and not driver:
            driver = line.split("driver:", 1)[1].strip()
        elif line.strip().startswith("Current:") and not current:
            current = line.split(":", 1)[1].strip()
    return {"available": result.returncode == 0 and bool(driver),
            "driver": driver, "current": current,
            "error": (result.stderr or result.stdout).strip() if result.returncode else ""}


def pacman_installed():
    result = platform_api.run(["pacman", "-Qq"])
    return set(result.stdout.split())


KERNEL_EXTRAS = ("-headers", "-docs", "-firmware", "-api-headers")
KERNEL_NAMES = {
    "linux": "Linux", "linux-lts": "Linux LTS", "linux-zen": "Linux Zen",
    "linux-hardened": "Linux Hardened", "linux-rt": "Linux RT", "linux-rt-lts": "Linux RT LTS",
    "linux-nanoos-gaming": "NanoOS Gaming Kernel", "linux-nanoos-fluffy": "NanoOS Fluffy Kernel",
}


def package_versions():
    """{package: version} of every installed package (one pacman call)."""
    result = platform_api.run(["pacman", "-Q"])
    versions = {}
    for line in result.stdout.splitlines():
        name, _, version = line.partition(" ")
        versions[name] = version
    return versions


def grub_default_kernel():
    """Kernel package GRUB boots by default, or "" for the first entry."""
    text = platform_api.read_file("/etc/default/grub")
    match = re.search(r'(?m)^GRUB_DEFAULT=["\']?([^"\'\n]*)', text)
    if not match or match.group(1) != "saved":
        return ""
    for line in platform_api.read_file("/boot/grub/grubenv").splitlines():
        if line.startswith("saved_entry="):
            # saved_entry=<submenu id>><entry id>; the kernel is in the entry id.
            entry = line.split("=", 1)[1].rsplit(">", 1)[-1]
            found = re.match(r"gnulinux-(.+?)-advanced-", entry)
            return found.group(1) if found else ""
    return ""


def grub_timeout():
    match = re.search(r'(?m)^GRUB_TIMEOUT=["\']?(\d+)', platform_api.read_file("/etc/default/grub"))
    return match.group(1) if match else None


def boot_report(versions):
    """Installed kernels with headers / NVIDIA driver status, GRUB settings."""
    module_dirs = {}
    for directory in Path("/usr/lib/modules").glob("*"):
        base = platform_api.read_file(str(directory / "pkgbase")).strip()
        if base:
            module_dirs[base] = directory
    try:
        running = Path(f"/usr/lib/modules/{os.uname().release}/pkgbase").read_text().strip()
    except OSError:
        running = ""
    nvidia_dkms = any(name.startswith("nvidia") and name.endswith("-dkms") for name in versions)
    dkms = any(name.endswith("-dkms") for name in versions)
    kernels = []
    for name in sorted(versions):
        if not re.fullmatch(r"linux(-[a-z0-9]+)*", name) or name.endswith(KERNEL_EXTRAS) \
                or name.startswith("linux-firmware") or not Path(f"/boot/vmlinuz-{name}").is_file():
            continue
        modules = module_dirs.get(name)
        nvidia = None
        if nvidia_dkms and modules is not None:
            nvidia = any(modules.glob("updates/dkms/nvidia.ko*")) or any(modules.glob("extramodules/nvidia.ko*"))
        kernels.append({
            "name": name,
            "title": KERNEL_NAMES.get(name, name),
            "version": versions[name],
            "headers": f"{name}-headers" in versions,
            "nvidia": nvidia,
            "running": name == running,
        })
    display = ""
    if os.path.isfile(GRUB_DISPLAY):
        display = platform_api.run([GRUB_DISPLAY, "--status"]).stdout.strip()
    return {
        "kernels": kernels,
        "dkms": dkms,
        "default": grub_default_kernel(),
        "timeout": grub_timeout(),
        "grub": Path("/etc/default/grub").is_file(),
        "display": display,
        # The running kernel's modules were replaced by an update.
        "reboot_needed": not Path(f"/usr/lib/modules/{os.uname().release}").is_dir(),
    }


def last_full_update():
    """When `pacman -Syu` last ran, from /var/log/pacman.log."""
    stamp = ""
    try:
        with open("/var/log/pacman.log", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if "starting full system upgrade" in line:
                    stamp = line[1:line.index("]")]
    except (OSError, ValueError):
        return ""
    return stamp[:16].replace("T", " ") if stamp else ""


def parse_updates(lines):
    """checkupdates lines -> [(name, old, new)]."""
    out = []
    for line in lines or ():
        match = re.match(r"(\S+)\s+(\S+)\s+->\s+(\S+)", line)
        if match:
            out.append(match.groups())
    return out


def update_group(name):
    if name.startswith(("nanoos-", "linux-nanoos")):
        return "nanoos"
    if (re.fullmatch(r"linux(-[a-z0-9]+)*", name) and not name.endswith(("-docs", "-api-headers"))) \
            or name.startswith(("nvidia", "linux-firmware", "mesa", "vulkan-", "lib32-nvidia",
                                "lib32-mesa", "systemd", "glibc", "amd-ucode", "intel-ucode")):
        return "core"
    return "other"


def collect_report():
    """Everything the pages show. Runs in a worker thread."""
    started = time.monotonic()
    report = {
        "os": os_pretty_name(),
        "user": getpass.getuser(),
        "uptime": uptime_text(),
        "memory": memory_usage(),
        "root_usage": shutil.disk_usage("/"),
        "home_usage": shutil.disk_usage(os.path.expanduser("~")),
        "firmware": platform_api.firmware(),
        "cpu": platform_api.cpu_info(),
        "cpu_profile": platform_api.cpu_profile()["profile"],
        "x3d_mode": platform_api.read_file(
            next((str(p) for p in Path("/sys/bus/platform/drivers/amd_x3d_vcache").glob("*/amd_x3d_mode")), "")
        ).strip() if Path("/sys/bus/platform/drivers/amd_x3d_vcache").is_dir() else "",
        "prefcore": platform_api.read_file("/sys/devices/system/cpu/amd_pstate/prefcore").strip(),
        "gpus": gpu_summary(platform_api.gpu_info()),
        "storage": platform_api.storage_info(),
        "kernel": platform_api.kernel_status(),
        "scheduler": platform_api.scheduler_status(),
        "snapshots": platform_api.snapshot_status(),
        "mirrors": platform_api.mirror_status(),
        "secure_boot": platform_api.secure_boot_status(),
        "boot_managers": platform_api.boot_manager_status(),
        "packages": set(versions := package_versions()),
        "boot": boot_report(versions),
        "last_update": last_full_update(),
        "cpu_mode": saved_cpu_mode(),
        "epp": cpu_epp_summary(),
        "live": platform_api.running_live_iso(),
    }
    report["elapsed"] = time.monotonic() - started
    return report


class ReportWorker(QThread):
    ready = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            self.ready.emit(collect_report())
        except Exception as exc:  # shown in the UI, never crash the app
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class UpdateCountWorker(QThread):
    ready = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None
        self.stopped = False

    def stop(self):
        # checkupdates syncs databases over the network; never let it hold
        # the window open (destroying a running QThread aborts the app).
        self.stopped = True
        if self.process is not None and self.process.poll() is None:
            self.process.kill()

    def run(self):
        tool = shutil.which("checkupdates")
        if not tool:
            self.ready.emit(None)
            return
        self.process = subprocess.Popen(
            [tool], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
        )
        stdout, _ = self.process.communicate()
        if self.stopped:
            return
        # checkupdates: 0 = updates listed, 2 = none, other = error.
        if self.process.returncode == 2:
            self.ready.emit([])
        elif self.process.returncode == 0:
            self.ready.emit([line for line in stdout.splitlines() if line.strip()])
        else:
            self.ready.emit(None)


# ---------------------------------------------------------------- window
def percent(fraction):
    return f"{fraction * 100:.0f}%"


class ControlCenter(NanoShell):
    APP_NAME = APP_NAME
    BRAND_SUB = "CONTROL CENTER"
    EYEBROW = "NANOOS  /  CONTROL CENTER"
    FOOTER = "NANOOS CONTROL CENTER"
    MENU = [
        "Overview", "Performance", *(["Gaming"] if GAMING else []), "Kernels & Boot",
        "Storage", "Snapshots", "Updates", "System",
    ]
    NAV_ICONS = {
        "Overview": "utilities-system-monitor",
        "Performance": "preferences-system-performance",
        "Gaming": "applications-games",
        "Kernels & Boot": ["preferences-system-linux", "cpu"],
        "Storage": "drive-harddisk",
        "Snapshots": "document-save-all",
        "Updates": "system-software-update",
        "System": "computer",
    }
    START_PAGE = "Overview"
    LOG_PLACEHOLDER = "Output from updates, installs and CPU Boost changes appears here."

    DESCRIPTIONS = {
        "Overview": "Your NanoOS system at a glance, live.",
        "Kernels & Boot": "Installed kernels, their drivers, and what the boot menu starts by default.",
        "Performance": "Choose how eagerly the CPU boosts. Modes use AMD P-State EPP and are kept across reboots.",
        "Gaming": "The NanoOS gaming toolkit and its status.",
        "Storage": "Disks, partitions and how full they are.",
        "Snapshots": "Roll back a bad update with filesystem snapshots (Btrfs + snapper).",
        "Updates": "Everything waiting to be updated, NanoOS first. Updates run with live output below.",
        "System": "Kernel, boot and security details.",
    }

    def __init__(self):
        self.report = None
        self.updates = "checking"      # "checking" | None (unavailable) | list
        self.worker = None
        self.update_worker = None
        self.keep_status = False
        self.sampler = live.LiveSampler()
        self.nvidia_process = None
        self.gpu_reading = None
        super().__init__()
        self.live_timer = QTimer(self)
        self.live_timer.setInterval(1000)
        self.live_timer.timeout.connect(self.live_tick)
        self.live_timer.start()
        self.live_tick()
        self.refresh()

    # ------------------------------------------------------------ pages
    def build_pages(self):
        self.build_dashboard()
        for name in self.MENU:
            page, layout = self.new_page(name)
            layout.addWidget(ActionCard("Reading system status…", "This takes a moment."))
            layout.addStretch(1)
            self.add_page(name, page)

    def new_page(self, name):
        page, layout = self.page_header(name, self.DESCRIPTIONS[name],
                                        action=("Refresh", self.refresh))
        return page, layout

    def info(self, layout, title, value, icon=None):
        """A value card with the same Copy action Welcome uses."""
        value = str(value) if value not in (None, "") else "Unavailable"
        card = ActionCard(
            title, value, "Copy",
            lambda value=value, title=title: self.copy_value(title, value),
            icon=icon,
        )
        layout.addWidget(card)
        return card

    # ------------------------------------------------------------ dashboard
    def build_dashboard(self):
        """Live tiles. Created once and moved into each rebuilt Overview."""
        self.dashboard = QWidget()
        grid = QGridLayout(self.dashboard)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)
        self.tile_cpu = StatTile("Processor", "preferences-devices-cpu")
        self.tile_gpu = StatTile("Graphics", "video-display", color="#8de0b0")
        self.tile_memory = StatTile("Memory", "media-flash", color="#b59cf0")
        self.tile_network = StatTile("Network", "network-wired", maximum=None, color="#f2c66d")
        for index, tile in enumerate((self.tile_cpu, self.tile_gpu, self.tile_memory, self.tile_network)):
            grid.addWidget(tile, index // 2, index % 2)
        self.gpu_mode = "nvidia" if live.nvidia_present() and shutil.which("nvidia-smi") else \
            "amd" if self.sampler.amd_gpu else None

    def dashboard_visible(self):
        return (self.isVisible() and not self.isMinimized()
                and self.current_page_name() == "Overview")

    def live_tick(self):
        # Sample only while the dashboard is on screen; the CPU and network
        # readings are deltas, so take one silently to prime them.
        if not self.dashboard_visible():
            self.sampler.cpu_percent()
            self.sampler.network_rates()
            return
        cpu = self.sampler.cpu_percent()
        peak, average = self.sampler.cpu_clock_ghz()
        temp = self.sampler.cpu_temp()
        if cpu is not None:
            details = [f"{average:.2f} GHz avg" if average else "",
                       f"{temp:.0f} °C" if temp is not None else ""]
            self.tile_cpu.update_value(f"{cpu:.0f}%", "  ·  ".join(d for d in details if d), cpu)
        used, total, swap_used, swap_total = self.sampler.memory()
        if total:
            detail = f"{human_bytes(used)} of {human_bytes(total)}"
            if swap_used > 64 * 1024 * 1024:
                detail += f"  ·  swap {human_bytes(swap_used)}"
            self.tile_memory.update_value(f"{used / total * 100:.0f}%", detail, used / total * 100)
        down, up = self.sampler.network_rates()
        if down is not None:
            self.tile_network.update_value(
                f"↓ {live.rate_text(down)}", f"↑ {live.rate_text(up)}", down)
        self.sample_gpu()

    def sample_gpu(self):
        if self.gpu_mode == "amd":
            self.show_gpu(self.sampler.amd_gpu_sample())
        elif self.gpu_mode == "nvidia":
            if self.nvidia_process is not None:
                return  # previous query still running; never pile them up
            process = QProcess(self)
            process.finished.connect(lambda *_a, p=process: self.nvidia_done(p))
            process.errorOccurred.connect(lambda *_a, p=process: self.nvidia_done(p, failed=True))
            self.nvidia_process = process
            process.start("nvidia-smi", live.NVIDIA_QUERY)
        else:
            self.tile_gpu.update_value("–", "No GPU load reading on this system")

    def nvidia_done(self, process, failed=False):
        if self.nvidia_process is not process:
            return
        self.nvidia_process = None
        text = "" if failed else process.readAllStandardOutput().data().decode(errors="replace")
        process.deleteLater()
        self.show_gpu(live.parse_nvidia(text))

    def show_gpu(self, reading):
        if not reading or reading.get("load") is None:
            self.tile_gpu.update_value("–", "GPU reading unavailable")
            return
        details = []
        if reading.get("temp") is not None:
            details.append(f"{reading['temp']:.0f} °C")
        if reading.get("vram_total"):
            details.append(f"VRAM {human_bytes(reading['vram_used'] or 0)} of {human_bytes(reading['vram_total'])}")
        if reading.get("power") is not None:
            details.append(f"{reading['power']:.0f} W")
        self.tile_gpu.update_value(f"{reading['load']:.0f}%", "  ·  ".join(details), reading["load"])

    # ------------------------------------------------------------ data flow
    def refresh(self):
        if self.worker is not None and self.worker.isRunning():
            return
        if not self.keep_status:
            self.status.setText("Reading system status…")
        self.worker = ReportWorker(self)
        self.worker.ready.connect(self.render)
        self.worker.failed.connect(
            lambda message: self.status.setText("Could not read system status: " + message)
        )
        self.worker.start()
        self.check_updates()

    def check_updates(self):
        if self.update_worker is not None and self.update_worker.isRunning():
            return
        self.updates = "checking"
        if self.report is not None:
            self.build_updates(self.report)
            self.build_overview(self.report)
        self.update_worker = UpdateCountWorker(self)
        self.update_worker.ready.connect(self.updates_checked)
        self.update_worker.start()

    def updates_checked(self, updates):
        self.updates = updates
        if self.report is not None:
            self.build_updates(self.report)
            self.build_overview(self.report)
            self.lock_if_busy()

    def render(self, report):
        self.report = report
        for builder in (
            self.build_overview, self.build_performance,
            *([self.build_gaming] if GAMING else []),
            self.build_boot, self.build_storage, self.build_snapshots, self.build_updates,
            self.build_system,
        ):
            builder(report)
        self.footer_label.setText(
            f"NANOOS CONTROL CENTER  ·  {VERSION}\nUPDATED {time.strftime('%H:%M:%S')}"
        )
        self.apply_start_page()
        if self.keep_status:
            self.keep_status = False      # leave the task result visible
        elif not self.task_running():
            self.status.setText(f"{self.current_page_name()}  ·  Ready")
        self.lock_if_busy()

    def apply_start_page(self):
        """`nanoos-control-center --page Updates` opens that page once."""
        wanted = getattr(self, "requested_page", None)
        if wanted and wanted in self.pages:
            self.requested_page = None
            self.show_page(wanted)

    def lock_if_busy(self):
        # Rebuilt pages contain fresh, enabled buttons; keep them locked
        # while an administrator task is still running.
        if self.task_running():
            self.set_action_controls_enabled(False)

    def on_task_finished(self, title, success):
        self.keep_status = True
        self.refresh()

    # ------------------------------------------------------------ Overview
    def updates_summary(self):
        if self.updates == "checking":
            return "Checking for updates…"
        if self.updates is None:
            return "Update check unavailable (needs pacman-contrib)."
        if not self.updates:
            return "NanoOS is up to date."
        count = len(self.updates)
        return f"{count} update{'s' if count != 1 else ''} available."

    def build_overview(self, r):
        page, layout = self.new_page("Overview")
        live_media = "  ·  running from live media" if r["live"] else ""
        layout.addWidget(ActionCard(
            r["os"],
            f"Kernel {r['kernel'].get('running') or 'unknown'}  ·  up {r['uptime']}  ·  "
            f"signed in as {r['user']}{live_media}",
            icon="nanoos",
        ))
        layout.addWidget(self.dashboard)

        layout.addWidget(self.group_label("Hardware"))
        cpu = r["cpu"]
        self.info(layout, "Processor",
                  f"{cpu.get('model', 'Unknown')}  ·  {cpu.get('architecture', '')}"
                  + (f"  ·  {ZEN_NAMES[r['cpu_profile']]}" if r['cpu_profile'] in ZEN_NAMES else ""),
                  icon="preferences-devices-cpu")
        gpus = self.ranked_gpus(r)
        self.info(layout, "Graphics", "   ·   ".join(
            f"{name} (driver: {driver})" if driver else name for name, driver in gpus)
            if gpus else "No GPU detected", icon="video-display")
        usage = r["root_usage"]
        layout.addWidget(ActionCard(
            "System disk",
            f"{human_bytes(usage.used)} of {human_bytes(usage.total)} used  ·  {human_bytes(usage.free)} free",
            "Open Storage", lambda: self.show_page("Storage"),
            fraction=usage.used / usage.total if usage.total else None,
            icon="drive-harddisk",
        ))

        layout.addWidget(self.group_label("Status"))
        mode = dict((key, title) for key, title, _ in CPU_MODES).get(r["cpu_mode"], "")
        epp = r["epp"]
        layout.addWidget(ActionCard(
            "CPU Boost",
            (f"Mode: {mode}" if mode else "No mode chosen yet." if epp.get("available")
             else "Unavailable on this CPU (needs the amd-pstate-epp driver).")
            + (f"  ·  power hint: {epp['current']}" if epp.get("current") else ""),
            "Open Performance", lambda: self.show_page("Performance"),
            icon="preferences-system-performance",
        ))
        updates_card = ActionCard(
            "Updates", self.updates_summary(),
            "Open Updates", lambda: self.show_page("Updates"),
            icon="system-software-update",
        )
        if isinstance(self.updates, list) and self.updates:
            updates_card.set_badge(str(len(self.updates)), "info")
        elif self.updates == []:
            updates_card.set_badge("Up to date", "ok")
        layout.addWidget(updates_card)
        if r["boot"]["reboot_needed"]:
            layout.addWidget(self.restart_card())
        layout.addStretch(1)
        self.add_page("Overview", page)

    def restart_card(self):
        card = ActionCard(
            "Restart to finish updating",
            "The running kernel was updated. Restart to use the new kernel and drivers "
            "(USB devices and new apps may not work until then).",
            "Restart now", lambda: self.launch(["systemctl", "reboot"], "restart"),
            icon="system-reboot",
        )
        card.set_badge("Restart needed", "warn")
        return card

    @staticmethod
    def ranked_gpus(r):
        def rank(gpu):
            name, driver = gpu
            integrated = any(tag in name for tag in ("610M", "Graphics", "Vega", "UHD", "Iris"))
            return 0 if driver == "nvidia" or name.startswith("NVIDIA") else 1 if not integrated else 2
        return sorted(r["gpus"], key=rank)

    # ------------------------------------------------------------ Performance
    def build_performance(self, r):
        page, layout = self.new_page("Performance")
        epp = r["epp"]
        available = bool(epp.get("available"))
        layout.addWidget(self.group_label("CPU Boost mode"))
        for key, title, description in CPU_MODES:
            active = key == r["cpu_mode"]
            if r["live"]:
                note, text, enabled = "Available after NanoOS is installed.", "Apply", False
            elif not available:
                note, text, enabled = "Needs a CPU using the amd-pstate-epp driver.", "Apply", False
            elif active:
                note, text, enabled = "Currently active and kept after reboot.", "Active", False
            else:
                note, text, enabled = "", "Apply", True
            layout.addWidget(ActionCard(
                title, description + (f"  ·  {note}" if note else ""), text,
                lambda key=key, title=title: self.apply_cpu_mode(key, title),
                enabled=enabled,
            ))

        layout.addWidget(self.group_label("Status"))
        self.info(layout, "Power hint (EPP)",
                  f"{epp.get('current') or 'unknown'}  ·  driver: {epp.get('driver') or 'unknown'}")
        sched = r["scheduler"]
        self.info(layout, "Scheduler",
                  ("sched_ext ready" if sched.get("sched_ext_available") else "Default (EEVDF)")
                  + f"  ·  scx_loader: {sched.get('scx_loader', 'unknown')}")
        zen = ZEN_NAMES.get(r["cpu_profile"])
        tuning = [f"{zen} detected" if zen else "Generic x86-64 CPU"]
        if r.get("prefcore") == "enabled":
            tuning.append("preferred-core ranking on (fastest cores first)")
        self.info(layout, "CPU tuning", "  ·  ".join(tuning), icon="preferences-devices-cpu")
        if r.get("x3d_mode"):
            cache = r["x3d_mode"] == "cache"
            card = ActionCard(
                "X3D V-Cache",
                ("Games and apps prefer the cores with the 3D V-Cache." if cache else
                 "Apps prefer the higher-clocked cores. NanoOS Game Mode switches to the "
                 "V-Cache cores automatically while a game runs.")
                + "  ·  Until restart.",
                "Prefer clock speed" if cache else "Prefer V-Cache",
                lambda: self.set_x3d_mode("frequency" if cache else "cache"),
                enabled=not r["live"], icon="media-flash",
            )
            card.set_badge("V-Cache" if cache else "Clock speed", "ok" if cache else "info")
            layout.addWidget(card)
        layout.addStretch(1)
        self.add_page("Performance", page)

    def set_x3d_mode(self, mode):
        helper = "/usr/lib/nanoos-gamemode/nanoos-gamemode-helper"
        title = "X3D: " + ("V-Cache cores" if mode == "cache" else "clock speed")
        if os.path.isfile(helper):
            self.run_privileged([helper, "x3d", mode], title, verb="Applying")
        else:
            script = ("for f in /sys/bus/platform/drivers/amd_x3d_vcache/*/amd_x3d_mode; "
                      f"do echo {mode} > \"$f\"; done")
            self.run_privileged(["/bin/sh", "-c", script], title, verb="Applying")

    def apply_cpu_mode(self, key, title):
        # One authorization: apply + save the mode, and make sure the boot
        # service that re-applies it is enabled.
        script = (
            f"{shlex.quote(CPU_BOOST)} set {shlex.quote(key)} && "
            "systemctl enable nanoos-cpu-boost.service"
        )
        self.run_privileged(["/bin/sh", "-c", script], f"CPU Boost: {title}", verb="Applying")

    # ------------------------------------------------------------ Gaming
    def build_gaming(self, r):
        page, layout = self.new_page("Gaming")
        installed = r["packages"]
        missing = [package for package, _, _ in GAMING_TOOLS if package not in installed]

        layout.addWidget(self.group_label("NanoOS apps"))
        layout.addWidget(ActionCard(
            "NanoOS Game Mode",
            "Per-game performance profiles and gaming optimizations.",
            "Launch", lambda: self.launch([GAMEMODE_APP], "NanoOS Game Mode"),
            enabled=os.path.isfile(GAMEMODE_APP),
        ))
        if os.path.isfile(WELCOME_APP):
            layout.addWidget(ActionCard(
                "NanoOS Welcome",
                "Install more gaming components, kernels, software and desktops.",
                "Launch", lambda: self.launch([WELCOME_APP], "NanoOS Welcome"),
            ))

        layout.addWidget(self.group_label("Gaming tools"))
        if missing:
            layout.addWidget(ActionCard(
                f"Install all missing tools ({len(missing)})",
                ", ".join(missing),
                "Install", lambda: self.install_packages(missing, "gaming tools"),
                enabled=not r["live"],
            ))
        icons = {"nanoos-gamemode": "nanoos-gamemode", "obs-studio": "com.obsproject.Studio"}
        for package, title, description in GAMING_TOOLS:
            present = package in installed
            card = ActionCard(
                title, description, "Install",
                lambda package=package, title=title: self.install_packages([package], title),
                enabled=not r["live"],
                icon=[icons.get(package, package), "applications-games"],
            )
            if present:
                card.set_badge("Installed", "ok")
                card.set_action(visible=False)
            layout.addWidget(card)
        layout.addStretch(1)
        self.add_page("Gaming", page)

    def launch(self, program, title):
        if QProcess.startDetached(program[0], program[1:]):
            self.status.setText(f"Opened {title}.")
        else:
            self.status.setText(f"Could not start {title}.")

    def install_packages(self, packages, title):
        pacman = shutil.which("pacman") or "/usr/bin/pacman"
        self.run_privileged(
            [pacman, "-S", "--needed", "--noconfirm", *packages], title, verb="Installing",
        )

    # ------------------------------------------------------------ Kernels & Boot
    def build_boot(self, r):
        page, layout = self.new_page("Kernels & Boot")
        boot = r["boot"]
        can_change = boot["grub"] and not r["live"] and os.path.isfile(BOOT_CONFIG)
        if boot["reboot_needed"]:
            layout.addWidget(self.restart_card())
        layout.addWidget(self.group_label("Installed kernels"))
        default = boot["default"]
        for kernel in boot["kernels"]:
            parts = [f"Version {kernel['version']}",
                     "headers installed" if kernel["headers"] else "no headers"]
            if kernel["nvidia"] is not None:
                parts.append("NVIDIA driver built" if kernel["nvidia"] else "NVIDIA driver missing")
            card = ActionCard(
                kernel["title"], "  ·  ".join(parts), "Boot by default",
                lambda name=kernel["name"], title=kernel["title"]: self.set_boot_default(name, title),
                enabled=can_change, icon=["preferences-system-linux", "cpu"],
            )
            if kernel["nvidia"] is False or (boot["dkms"] and not kernel["headers"]):
                card.set_badge("Driver missing", "bad")
            elif kernel["running"]:
                card.set_badge("Running", "ok")
            if kernel["name"] == default:
                card.set_badge("Running · Default" if kernel["running"] else "Default", "ok")
                card.set_action(visible=False)
            layout.addWidget(card)
        if boot["dkms"] and any(not k["headers"] or k["nvidia"] is False for k in boot["kernels"]):
            layout.addWidget(ActionCard(
                "Repair kernel drivers",
                "Install the missing headers so DKMS rebuilds the driver for every kernel.",
                "Repair", lambda: self.repair_drivers(boot), enabled=not r["live"],
                icon="tools-wizard",
            ))
        if os.path.isfile(WELCOME_APP):
            layout.addWidget(ActionCard(
                "Install another kernel",
                "LTS, Zen, Hardened and real-time kernels are one click away in NanoOS Welcome.",
                "Open Welcome", lambda: self.launch([WELCOME_APP], "NanoOS Welcome"),
                icon="nanoos-welcome",
            ))

        layout.addWidget(self.group_label("Boot menu"))
        default_card = ActionCard(
            "Default kernel",
            (KERNEL_NAMES.get(default, default) + " starts unless you pick another one.") if default
            else "The first menu entry starts (the newest default kernel).",
            "Use first entry" if default else None,
            lambda: self.set_boot_default("auto", "First entry"),
            enabled=can_change, icon="system-run",
        )
        layout.addWidget(default_card)
        timeout = boot["timeout"]
        layout.addWidget(ActionCard(
            "Menu timeout",
            f"The boot menu waits {timeout} s before starting the default." if timeout
            else "Boot menu timeout not set.",
            "Change", self.change_boot_timeout, enabled=can_change, icon="chronometer",
        ))
        if boot["display"]:
            layout.addWidget(ActionCard(
                "Menu resolution",
                boot["display"].replace(" -> ", "  →  "),
                "Re-detect", lambda: self.run_privileged([GRUB_DISPLAY], "Boot menu resolution"),
                enabled=not r["live"], icon="video-display",
            ))
        if not boot["grub"]:
            layout.addWidget(ActionCard("GRUB not detected",
                                        "Boot settings are only available with the GRUB boot loader."))
        layout.addStretch(1)
        self.add_page("Kernels & Boot", page)

    def set_boot_default(self, kernel, title):
        self.run_privileged([BOOT_CONFIG, "default", kernel], f"Default kernel: {title}", verb="Applying")

    def change_boot_timeout(self):
        current = (self.report or {}).get("boot", {}).get("timeout") or "5"
        choices = ["0", "1", "2", "3", "5", "10", "15", "30"]
        value, ok = QInputDialog.getItem(
            self, "Boot menu timeout", "Seconds before the default entry starts:",
            choices, choices.index(current) if current in choices else 4, False,
        )
        if ok and value != current:
            self.run_privileged([BOOT_CONFIG, "timeout", value], f"Boot menu timeout {value} s",
                                verb="Applying")

    def repair_drivers(self, boot):
        missing = [f"{k['name']}-headers" for k in boot["kernels"] if not k["headers"]]
        if missing:
            self.install_packages(missing, "Kernel driver repair")
        else:
            # Headers are there but a module is missing: rebuild with DKMS.
            self.run_privileged(["dkms", "autoinstall"], "Kernel driver repair")

    # ------------------------------------------------------------ Storage
    def build_storage(self, r):
        page, layout = self.new_page("Storage")
        layout.addWidget(self.group_label("Usage"))
        for title, usage in (("System ( / )", r["root_usage"]), ("Home", r["home_usage"])):
            fraction = usage.used / usage.total if usage.total else 0
            layout.addWidget(ActionCard(
                title,
                f"{human_bytes(usage.used)} of {human_bytes(usage.total)} used "
                f"({percent(fraction)})  ·  {human_bytes(usage.free)} free",
                fraction=fraction,
            ))

        layout.addWidget(self.group_label("Disks"))

        def partitions(node, out):
            for child in node.get("children", []) or []:
                parts = [child.get("path") or child.get("name", ""), str(child.get("size") or "")]
                if child.get("fstype"):
                    parts.append(child["fstype"])
                if child.get("mountpoint"):
                    parts.append("mounted at " + child["mountpoint"])
                out.append("  ".join(part for part in parts if part))
                partitions(child, out)
            return out

        for device in r["storage"].get("blockdevices", []):
            name = str(device.get("name", ""))
            if device.get("type") != "disk" or name.startswith(("zram", "loop")):
                continue
            title = "  ·  ".join(part for part in (
                device.get("path") or name, str(device.get("size") or ""),
                (device.get("model") or "").strip(),
                (device.get("pttype") or "").upper(),
            ) if part)
            lines = partitions(device, [])
            description = "\n".join(lines) if lines else "No partitions."
            layout.addWidget(ActionCard(
                title, description, "Copy value",
                lambda value=title + "\n" + description, title=title: self.copy_value(title, value),
            ))
        layout.addStretch(1)
        self.add_page("Storage", page)

    # ------------------------------------------------------------ Snapshots
    def build_snapshots(self, r):
        page, layout = self.new_page("Snapshots")
        snap = r["snapshots"]
        fs = snap.get("filesystem", "unknown")
        self.info(layout, "Root filesystem", fs, icon="drive-harddisk")
        if not snap.get("snapper"):
            if fs == "btrfs":
                layout.addWidget(ActionCard(
                    "Enable snapshots",
                    "Your system uses Btrfs, so snapshots are possible. Install snapper and "
                    "snap-pac for automatic snapshots before every update.",
                    "Install", lambda: self.install_packages(["snapper", "snap-pac"], "snapshot tools"),
                    enabled=not r["live"],
                ))
            else:
                layout.addWidget(ActionCard(
                    "Snapshots unavailable",
                    f"Snapshots need a Btrfs root filesystem; this system uses {fs}. "
                    "Choose Btrfs in the NanoOS installer to use them.",
                ))
        else:
            layout.addWidget(ActionCard(
                "snapper",
                "Active." if snap.get("available")
                else "Installed, but there is no usable configuration for /.",
                "Show list", lambda: self.show_text(snap.get("output", "") or "(no snapshots)"),
            ))
        layout.addStretch(1)
        self.add_page("Snapshots", page)

    def show_text(self, text):
        self.log.setPlainText(text)
        self.toggle_output(True)

    # ------------------------------------------------------------ Updates
    def build_updates(self, r):
        page, layout = self.new_page("Updates")
        updates = parse_updates(self.updates) if isinstance(self.updates, list) else []
        last = r.get("last_update")
        summary = self.updates_summary() + (f"  ·  last update {last}" if last else "")
        if r["live"]:
            summary += "  ·  Updates are disabled on the live installer."
        main = ActionCard(
            "System update", summary, "Update now", self.run_update,
            enabled=not r["live"] and self.updates != "checking",
            icon="system-software-update",
        )
        if updates:
            main.set_badge(f"{len(updates)} available", "info")
        elif self.updates == []:
            main.set_badge("Up to date", "ok")
        layout.addWidget(main)
        if r["boot"]["reboot_needed"]:
            layout.addWidget(self.restart_card())
        if self.updates is None and not shutil.which("checkupdates"):
            layout.addWidget(ActionCard(
                "Enable update checks",
                "The update list needs pacman-contrib (checkupdates).",
                "Install", lambda: self.install_packages(["pacman-contrib"], "pacman-contrib"),
                enabled=not r["live"], icon="package-x-generic",
            ))
        layout.addWidget(ActionCard(
            "Check for updates",
            "Look for new packages without installing anything.",
            "Check again", self.check_updates,
            enabled=self.updates != "checking", icon="view-refresh",
        ))

        groups = {"nanoos": [], "core": [], "other": []}
        for name, old, new in updates:
            groups[update_group(name)].append((name, old, new))
        if groups["nanoos"]:
            layout.addWidget(self.group_label(f"NanoOS ({len(groups['nanoos'])})"))
            for name, old, new in groups["nanoos"]:
                layout.addWidget(ActionCard(
                    name, f"{old}  →  {new}", icon=["nanoos", "package-x-generic"],
                    badge=("NanoOS", "info"),
                ))
        if groups["core"]:
            layout.addWidget(self.group_label(f"Kernel, drivers and core system ({len(groups['core'])})"))
            for name, old, new in groups["core"]:
                card = ActionCard(name, f"{old}  →  {new}", icon=["preferences-system-linux", "package-x-generic"])
                if re.fullmatch(r"linux(-[a-z0-9]+)*", name) or name.startswith(("nvidia", "systemd", "glibc")):
                    card.set_badge("Restart after", "warn")
                layout.addWidget(card)
        if groups["other"]:
            other = groups["other"]
            layout.addWidget(self.group_label(f"Apps and libraries ({len(other)})"))
            shown = other[:60]
            text = "\n".join(f"{name}   {old}  →  {new}" for name, old, new in shown)
            if len(other) > len(shown):
                text += f"\n… and {len(other) - len(shown)} more"
            layout.addWidget(ActionCard(
                f"{len(other)} package{'s' if len(other) != 1 else ''}", text,
                "Show all", lambda: self.show_text("\n".join(
                    f"{name}  {old} -> {new}" for name, old, new in other)),
                icon="package-x-generic",
            ))
        layout.addStretch(1)
        self.add_page("Updates", page)

    def run_update(self):
        pacman = shutil.which("pacman") or "/usr/bin/pacman"
        self.run_privileged([pacman, "-Syu", "--noconfirm"], "NanoOS update", verb="Running")

    # ------------------------------------------------------------ System
    def build_system(self, r):
        page, layout = self.new_page("System")
        kernel = r["kernel"]
        running = kernel.get("running") or "unknown"
        self.info(layout, "Running kernel",
                  running + ("  ·  NanoOS Fluffy kernel" if "nanoos-fluffy" in running
                             else "  ·  NanoOS Gaming kernel" if "nanoos" in running else ""))
        packages = [name for name in (kernel.get("installed") or [])
                    if not name.startswith("linux-firmware") and name != "linux-api-headers"]
        self.info(layout, "Installed kernel packages", "   ·   ".join(packages) or "None found")
        fw = r["firmware"]
        self.info(layout, "Firmware",
                  fw["mode"] + (f" {fw['uefi_bits']}-bit" if fw.get("uefi_bits") else ""))
        self.info(layout, "Secure Boot", r["secure_boot"].get("status") or "unknown", icon="security-high")
        self.info(layout, "Boot manager", ", ".join(r["boot_managers"]) or "Not detected", icon="system-run")
        repos = r["mirrors"]
        self.info(layout, "NanoOS repositories",
                  "Configured" if any(entry.get("nanoos") for entry in repos.values())
                  else "Not configured")
        layout.addStretch(1)
        self.add_page("System", page)

    # ------------------------------------------------------------ shutdown
    def shutdown(self):
        """Stop background work before Qt destroys the threads."""
        self.live_timer.stop()
        if self.nvidia_process is not None:
            self.nvidia_process.kill()
            self.nvidia_process.waitForFinished(1000)
        for worker in (self.worker, self.update_worker):
            if worker is not None and worker.isRunning():
                if hasattr(worker, "stop"):
                    worker.stop()
                worker.wait(5000)

    def closeEvent(self, event):
        super().closeEvent(event)
        if event.isAccepted():
            self.shutdown()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("NanoOS")
    # Lets KDE/Wayland match the window to org.nanoos.ControlCenter.desktop.
    app.setDesktopFileName(DESKTOP_ID)
    app.setWindowIcon(QIcon.fromTheme("nanoos-control-center"))
    window = ControlCenter()
    if "--page" in sys.argv[1:-1]:
        window.requested_page = sys.argv[sys.argv.index("--page") + 1]
        window.apply_start_page()
    app.aboutToQuit.connect(window.shutdown)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
