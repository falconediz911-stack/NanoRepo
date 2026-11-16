#!/usr/bin/env python3
"""NanoOS Control Center.

System overview, CPU Boost modes, gaming tools, storage, snapshots,
updates and boot details. Built on the shared NanoOS UI kit so it looks
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
    from PySide6.QtCore import QProcess, QThread, Signal
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
except ImportError:
    print("NanoOS Control Center requires PySide6 (pacman -S pyside6).", file=sys.stderr)
    sys.exit(1)

import nanoos_platform as platform_api
from nanoos_ui import ActionCard, NanoButton, NanoShell

APP_NAME = "NanoOS Control Center"
VERSION = "V2"
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
        "gpus": gpu_summary(platform_api.gpu_info()),
        "storage": platform_api.storage_info(),
        "kernel": platform_api.kernel_status(),
        "scheduler": platform_api.scheduler_status(),
        "snapshots": platform_api.snapshot_status(),
        "mirrors": platform_api.mirror_status(),
        "secure_boot": platform_api.secure_boot_status(),
        "boot_managers": platform_api.boot_manager_status(),
        "packages": pacman_installed(),
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
    FOOTER = f"NANOOS CONTROL CENTER  ·  {VERSION}"
    MENU = [
        "Overview", "Performance", *(["Gaming"] if GAMING else []), "Storage",
        "Snapshots", "Updates", "System",
    ]
    START_PAGE = "Overview"
    LOG_PLACEHOLDER = "Output from updates, installs and CPU Boost changes appears here."

    DESCRIPTIONS = {
        "Overview": "Your NanoOS system at a glance.",
        "Performance": "Choose how eagerly the CPU boosts. Modes use AMD P-State EPP and are kept across reboots.",
        "Gaming": "The NanoOS gaming toolkit and its status.",
        "Storage": "Disks, partitions and how full they are.",
        "Snapshots": "Roll back a bad update with filesystem snapshots (Btrfs + snapper).",
        "Updates": "Keep NanoOS current. Updates run with live output in the panel below.",
        "System": "Kernel, boot and security details.",
    }

    def __init__(self):
        self.report = None
        self.updates = "checking"      # "checking" | None (unavailable) | list
        self.worker = None
        self.update_worker = None
        self.keep_status = False
        super().__init__()
        self.refresh()

    # ------------------------------------------------------------ pages
    def build_pages(self):
        for name in self.MENU:
            page, layout = self.new_page(name)
            layout.addWidget(ActionCard("Reading system status…", "This takes a moment."))
            layout.addStretch(1)
            self.add_page(name, page)

    def new_page(self, name):
        page, layout = self.page_header(name, self.DESCRIPTIONS[name])
        refresh = NanoButton("Refresh system information", "secondary")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh)
        return page, layout

    def info(self, layout, title, value):
        """A value card with the same 'Copy value' action Welcome uses."""
        value = str(value) if value not in (None, "") else "Unavailable"
        layout.addWidget(ActionCard(
            title, value, "Copy value",
            lambda value=value, title=title: self.copy_value(title, value),
        ))

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
            self.build_storage, self.build_snapshots, self.build_updates,
            self.build_system,
        ):
            builder(report)
        self.footer_label.setText(
            f"NANOOS CONTROL CENTER  ·  {VERSION}\nUPDATED {time.strftime('%H:%M:%S')}"
        )
        if self.keep_status:
            self.keep_status = False      # leave the task result visible
        elif not self.task_running():
            self.status.setText(f"{self.current_page_name()}  ·  Ready")
        self.lock_if_busy()

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
            return "Update check unavailable (install pacman-contrib for update counts)."
        if not self.updates:
            return "NanoOS is up to date."
        count = len(self.updates)
        return f"{count} update{'s' if count != 1 else ''} available."

    def build_overview(self, r):
        page, layout = self.new_page("Overview")
        live = "  ·  running from live media" if r["live"] else ""
        layout.addWidget(ActionCard(
            r["os"],
            f"Kernel {r['kernel'].get('running') or 'unknown'}  ·  up {r['uptime']}  ·  "
            f"signed in as {r['user']}{live}",
            "Open System", lambda: self.show_page("System"),
        ))

        layout.addWidget(self.group_label("Hardware"))
        cpu = r["cpu"]
        self.info(layout, "Processor",
                  f"{cpu.get('model', 'Unknown')}  ·  {cpu.get('architecture', '')}  ·  "
                  f"tuning profile: {r['cpu_profile']}")
        gpus = self.ranked_gpus(r)
        if gpus:
            self.info(layout, "Graphics", "   ·   ".join(
                f"{name} (driver: {driver})" if driver else name for name, driver in gpus))
        else:
            self.info(layout, "Graphics", "No GPU detected")

        used, total = r["memory"]
        layout.addWidget(ActionCard(
            "Memory",
            f"{human_bytes(used)} of {human_bytes(total)} used  ·  {human_bytes(total - used)} available",
            fraction=used / total if total else None,
        ))
        usage = r["root_usage"]
        layout.addWidget(ActionCard(
            "System disk",
            f"{human_bytes(usage.used)} of {human_bytes(usage.total)} used  ·  {human_bytes(usage.free)} free",
            "Open Storage", lambda: self.show_page("Storage"),
            fraction=usage.used / usage.total if usage.total else None,
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
        ))
        layout.addWidget(ActionCard(
            "Updates", self.updates_summary(),
            "Open Updates", lambda: self.show_page("Updates"),
        ))
        layout.addStretch(1)
        self.add_page("Overview", page)

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
        self.info(layout, "CPU tuning",
                  "Zen 5 optimized builds (znver5)" if r["cpu_profile"] == "zen5"
                  else "Generic x86-64 builds")
        layout.addStretch(1)
        self.add_page("Performance", page)

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
        for package, title, description in GAMING_TOOLS:
            present = package in installed
            layout.addWidget(ActionCard(
                title,
                f"{description}  ·  {'Installed' if present else 'Not installed'}",
                "Installed" if present else "Install",
                lambda package=package, title=title: self.install_packages([package], title),
                enabled=not present and not r["live"],
            ))
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
        self.info(layout, "Root filesystem", fs)
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
        has_updates = isinstance(self.updates, list) and bool(self.updates)
        layout.addWidget(ActionCard(
            "System update",
            self.updates_summary()
            + ("  ·  Updates are disabled on the live installer." if r["live"] else ""),
            "Update now", self.run_update,
            enabled=not r["live"] and self.updates != "checking",
        ))
        if has_updates:
            layout.addWidget(ActionCard(
                "Available updates",
                "See every package and version that would be upgraded.",
                "Show list", lambda: self.show_text("\n".join(self.updates)),
            ))
        layout.addWidget(ActionCard(
            "Check for updates",
            "Look for new packages without installing anything.",
            "Check again", self.check_updates,
            enabled=self.updates != "checking",
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
        self.info(layout, "Secure Boot", r["secure_boot"].get("status") or "unknown")
        self.info(layout, "Boot manager", ", ".join(r["boot_managers"]) or "Not detected")
        repos = r["mirrors"]
        self.info(layout, "NanoOS repositories",
                  "Configured" if any(entry.get("nanoos") for entry in repos.values())
                  else "Not configured")
        layout.addStretch(1)
        self.add_page("System", page)

    # ------------------------------------------------------------ shutdown
    def shutdown(self):
        """Stop background work before Qt destroys the threads."""
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
    app.aboutToQuit.connect(window.shutdown)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
