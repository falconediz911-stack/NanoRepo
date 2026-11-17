#!/usr/bin/env python3
"""NanoOS Welcome: first-run guide and one-click setup (gaming tools,
kernels, software, desktops). Built on the shared NanoOS UI kit."""

import re
import shlex
import shutil
import socket
import subprocess
import sys
from pathlib import Path


from PySide6.QtCore import Qt, QProcess
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QVBoxLayout,
)

from nanoos_ui import ActionCard, NanoButton, NanoShell

APP_NAME = "NanoOS Welcome"
DESKTOP_ID = "org.nanoos.Welcome"
CONTROL_CENTER = "/usr/bin/nanoos-control-center"


def _nanoos_edition():
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if line.startswith("NAME="):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return "NanoOS"


# NanoOS Basic has no gaming apps; every other NanoOS install is Gaming.
EDITION = _nanoos_edition()
GAMING = EDITION != "NanoOS Basic"
NANOOS_KERNEL = "NanoOS Gaming Kernel" if GAMING else "NanoOS Fluffy Kernel"
VERSION = "V2"


class WelcomeWindow(NanoShell):
    APP_NAME = f"{APP_NAME}"
    BRAND_SUB = "WELCOME CENTER"
    EYEBROW = "NANOOS  /  WELCOME"
    FOOTER = f"NANOOS WELCOME  ·  {VERSION}"
    MENU = [
        "Welcome", *(["Gaming Components"] if GAMING else []), "Kernels", "Software", "Coding",
        "Desktop Environments", "Desktop Components", "Window Managers",
        "System", "Preferences", "About NanoOS",
    ]
    START_PAGE = "Welcome"
    LOG_PLACEHOLDER = "Installation output appears here when you open the output panel."

    def build_pages(self):
        self.add_pages()

    def copy_system_value(self, label, value):
        self.copy_value(label, value)

    def launch_app(self, program, title):
        if QProcess.startDetached(program[0], program[1:]):
            self.status.setText(f"Opened {title}.")
        else:
            self.status.setText(f"Could not start {title}.")

    def reset_first_run_guide(self):
        answer = QMessageBox.question(
            self,
            "Reset first-run guide?",
            "The NanoOS Welcome introduction will appear the next time this app starts. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            NanoOSFirstRun.MARKER.unlink(missing_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, "Could not reset guide", str(exc))
            return
        self.status.setText("First-run guide reset. It will appear on the next launch.")

    def add_pages(self):
        # -------------------------------------------------
        # Welcome
        # -------------------------------------------------

        page, layout = self.page_header(
            "Welcome to NanoOS",
            ("Set up your NanoOS environment: gaming tools, kernels, software and desktops, one click each."
             if GAMING else
             "Set up your NanoOS environment: kernels, software and desktops, one click each."),
        )

        welcome_items = [
            *([(
                "Gaming Components",
                "Install the gaming stack and useful compatibility tools.",
                lambda: self.show_page("Gaming Components"),
            )] if GAMING else []),
            (
                "Kernels",
                "Install standard, LTS, performance, hardened, or RT kernels.",
                lambda: self.show_page("Kernels"),
            ),
            (
                "Software",
                "Install everyday desktop applications and system tools.",
                lambda: self.show_page("Software"),
            ),
            (
                "Coding",
                "Build the NanoCoding development environment.",
                lambda: self.show_page("Coding"),
            ),
            (
                "Desktop Environments",
                "Install KDE Plasma, GNOME, COSMIC, XFCE and more.",
                lambda: self.show_page("Desktop Environments"),
            ),
            (
                "Window Managers",
                "Install modern Wayland compositors and window managers.",
                lambda: self.show_page("Window Managers"),
            ),
            (
                "Desktop Components",
                "Install X11, XWayland, display managers, audio, portals, networking and other desktop infrastructure.",
                lambda: self.show_page("Desktop Components"),
            ),
        ]

        # The other NanoOS apps, one click away.
        apps = [
            (title, description, program)
            for title, description, program in (
                ("NanoOS Control Center",
                 "System overview, CPU Boost modes, storage, updates and boot details.",
                 [CONTROL_CENTER]),
                ("NanoOS Game Mode",
                 "Per-game performance profiles and gaming optimizations.",
                 ["/usr/bin/nanoos-gamemode"]),
            )
            if Path(program[-1]).is_file()
        ]
        if apps:
            layout.addWidget(self.group_label("NanoOS apps"))
            for title, description, program in apps:
                layout.addWidget(ActionCard(
                    title, description, "Launch",
                    lambda program=program, title=title: self.launch_app(program, title),
                ))
            layout.addWidget(self.group_label("Set up your system"))
        for title, description, callback in welcome_items:
            layout.addWidget(
                ActionCard(
                    title,
                    description,
                    "Open",
                    callback,
                )
            )

        layout.addStretch()
        self.add_page("Welcome", page)


        # -------------------------------------------------
        # Gaming Components
        # -------------------------------------------------

        gaming = [
            ("NanoOS Game Mode", "Per-game performance profiles and gaming optimizations.", ["nanoos-gamemode"]),
            ("Steam", "Valve's PC gaming platform.", ["steam"]),
            ("GameMode", "Game performance optimization daemon.", ["gamemode"]),
            ("Gamescope", "SteamOS-style micro-compositor.", ["gamescope"]),
            ("MangoHud", "Gaming performance overlay.", ["mangohud"]),
            ("OBS Studio", "Recording and streaming.", ["obs-studio"]),
            ("Lutris", "Game library and launcher.", ["lutris"]),
            ("Prism Launcher", "Minecraft launcher for custom instances.", ["prismlauncher"]),
            ("Wine", "Windows compatibility layer.", ["wine"]),
            ("Winetricks", "Helper for Wine environments.", ["winetricks"]),
            ("Vulkan Tools", "Vulkan utilities and diagnostics.", ["vulkan-tools"]),
            ("Mesa Utilities", "OpenGL and graphics utilities.", ["mesa-utils"]),
            ("32-bit Vulkan Loader", "32-bit Vulkan support.", ["lib32-vulkan-icd-loader"]),
            ("32-bit Mesa", "32-bit Mesa graphics libraries.", ["lib32-mesa"]),
        ]

        if GAMING:
            self.add_install_page(
                "Gaming Components",
                "Gaming software and graphics tools for the NanoOS gaming experience.",
                gaming,
            )


        # -------------------------------------------------
        # Kernels
        # -------------------------------------------------

        page, layout = self.page_header(
            "Kernels",
            "Install additional kernels without removing the kernel you already use. "
        "The GRUB boot menu is updated after every kernel install.",
        )

        kernels = [
            ("Linux", "Standard Arch Linux kernel.", ["linux"]),
            ("Linux LTS", "Long-term-support Linux kernel.", ["linux-lts"]),
            ("Linux Zen", "Kernel tuned toward desktop responsiveness.", ["linux-zen"]),
            ("Linux Hardened", "Security-hardened Linux kernel.", ["linux-hardened"]),
            ("Linux RT", "Real-time Linux kernel.", ["linux-rt"]),
            ("Linux RT LTS", "Real-time long-term-support kernel.", ["linux-rt-lts"]),
        ]

        for title, description, packages in kernels:
            layout.addWidget(
                ActionCard(
                    title,
                    description,
                    "Install",
                    lambda p=packages, t=title:
                        self.install_kernel(p, t),
                )
            )

        layout.addWidget(
            ActionCard(
                NANOOS_KERNEL,
                f"Install a locally built {NANOOS_KERNEL} .pkg.tar.zst package.",
                "Choose",
                self.install_local_kernel,
            )
        )

        layout.addWidget(
            ActionCard(
                "Repair Kernel Drivers",
                "Install missing headers so the NVIDIA (DKMS) driver is built for every installed kernel.",
                "Repair",
                self.repair_kernel_drivers,
            )
        )

        layout.addWidget(
            ActionCard(
                "Kernel Headers",
                "Install Linux, LTS, Zen, Hardened, and RT headers individually when needed for development.",
                "Install",
                lambda: self.install_packages(
                    [
                        "linux-headers",
                        "linux-lts-headers",
                        "linux-zen-headers",
                        "linux-hardened-headers",
                        "linux-rt-headers",
                        "linux-rt-lts-headers",
                    ],
                    "Kernel Headers",
                ),
            )
        )

        layout.addStretch()
        self.add_page("Kernels", page)


        # -------------------------------------------------
        # Software
        # -------------------------------------------------

        software = [
            ("Firefox", "Fast modern web browser.", ["firefox"]),
            ("Chromium", "Open-source Chromium browser.", ["chromium"]),
            ("Thunderbird", "Email and calendar client.", ["thunderbird"]),

            ("Kitty", "Fast GPU-accelerated terminal.", ["kitty"]),
            ("Dolphin", "Modern file manager.", ["dolphin"]),
            ("Ark", "Archive manager.", ["ark"]),

            ("Fastfetch", "System information utility.", ["fastfetch"]),
            ("btop", "Interactive system monitor.", ["btop"]),
            ("htop", "Interactive process viewer.", ["htop"]),
            ("tmux", "Terminal multiplexer.", ["tmux"]),
            ("ripgrep", "Fast recursive text search.", ["ripgrep"]),
            ("fd", "Fast file finder.", ["fd"]),
            ("fzf", "Command-line fuzzy finder.", ["fzf"]),
            ("jq", "Command-line JSON processor.", ["jq"]),
            ("7-Zip", "Archive utility.", ["7zip"]),
            ("unzip", "ZIP extraction utility.", ["unzip"]),
            ("rsync", "Fast file synchronization tool.", ["rsync"]),
            ("curl", "Command-line data transfer tool.", ["curl"]),
            ("wget", "Network downloader.", ["wget"]),

            ("VLC", "Media player.", ["vlc"]),
            ("MPV", "Lightweight media player.", ["mpv"]),
            ("GIMP", "Image editor.", ["gimp"]),
            ("Inkscape", "Vector graphics editor.", ["inkscape"]),
            ("Krita", "Digital painting application.", ["krita"]),
            ("Blender", "3D creation suite.", ["blender"]),
            ("Kdenlive", "Video editor.", ["kdenlive"]),
            ("LibreOffice", "Full office suite.", ["libreoffice-fresh"]),

            ("Git", "Version control.", ["git"]),
            ("Podman", "Container engine.", ["podman"]),
            ("Docker", "Container platform.", ["docker"]),
            ("GParted", "Partition editor.", ["gparted"]),
            ("KDE Partition Manager", "KDE partition management tool.", ["partitionmanager"]),
        ]

        self.add_install_page(
            "Software",
            "A larger collection of useful desktop, media, system, and utility applications.",
            software,
        )


        # -------------------------------------------------
        # Coding
        # -------------------------------------------------

        coding = [
            ("NanoCoding Core", "Git, build tools, Neovim, Python and pip.", ["base-devel", "git", "neovim", "python", "python-pip"]),
            ("GCC", "GNU C/C++ compiler toolchain.", ["gcc"]),
            ("Clang", "LLVM C/C++ compiler.", ["clang"]),
            ("CMake", "Cross-platform build system.", ["cmake"]),
            ("Ninja", "Fast build system.", ["ninja"]),
            ("Python", "Python development environment.", ["python", "python-pip"]),
            ("Node.js", "Node.js runtime.", ["nodejs"]),
            ("npm", "Node.js package manager.", ["npm"]),
            ("Rust", "Rust toolchain manager.", ["rustup"]),
            ("Go", "Go programming language.", ["go"]),
            ("Java", "OpenJDK development environment.", ["jdk-openjdk"]),
            ("Neovim", "Modern terminal editor.", ["neovim"]),
            ("Docker + Podman", "Container development tools.", ["docker", "podman"]),
        ]

        self.add_install_page(
            "Coding",
            "Build the NanoCoding workflow with development tools and language runtimes.",
            coding,
        )


        # -------------------------------------------------
        # Desktop Environments
        # -------------------------------------------------

        desktops = [
            ("KDE Plasma", "Full-featured KDE Plasma desktop.", ["plasma"]),
            ("GNOME", "Full GNOME desktop group.", ["gnome"]),
            ("COSMIC", "Modern COSMIC desktop environment.", ["cosmic"]),
            ("XFCE", "Lightweight and modular desktop.", ["xfce4"]),
            ("XFCE Goodies", "Extra XFCE utilities and plugins.", ["xfce4-goodies"]),
            ("Cinnamon", "Modern traditional-style desktop.", ["cinnamon"]),
            ("MATE", "Lightweight traditional desktop.", ["mate"]),
            ("MATE Extra", "Additional MATE applications.", ["mate-extra"]),
            ("Budgie", "Modern desktop environment.", ["budgie"]),
            ("LXQt", "Lightweight Qt desktop.", ["lxqt"]),
            ("LXDE", "Lightweight GTK desktop.", ["lxde"]),
            ("Pantheon", "elementary-style desktop environment.", ["pantheon"]),
            ("Deepin", "Full Deepin desktop group.", ["deepin"]),
            ("Deepin Extra", "Additional Deepin desktop applications.", ["deepin-extra"]),
        ]

        self.add_install_page(
            "Desktop Environments",
            "Install the desktop environment you want to use with NanoOS.",
            desktops,
        )


        # -------------------------------------------------
        # Desktop Components
        # -------------------------------------------------

        desktop_components = [
            (
                "Xorg / X11",
                "Install the complete X.Org X11 server group.",
                ["xorg"],
            ),
            (
                "XWayland",
                "Run X11 applications inside Wayland sessions.",
                ["xorg-xwayland"],
            ),
            (
                "X11 Applications",
                "Install the Arch X11 application utilities group.",
                ["xorg-apps"],
            ),
            (
                "X11 Drivers",
                "Install the X.Org driver group.",
                ["xorg-drivers"],
            ),
            (
                "X11 Fonts",
                "Install the X.Org font group.",
                ["xorg-fonts"],
            ),

            (
                "SDDM",
                "Modern Qt-based graphical display manager.",
                ["sddm"],
            ),
            (
                "GDM",
                "GNOME display manager and login screen.",
                ["gdm"],
            ),
            (
                "LightDM",
                "Lightweight graphical display manager.",
                ["lightdm"],
            ),

            (
                "PipeWire",
                "Modern low-latency audio and media framework.",
                ["pipewire", "pipewire-audio", "pipewire-alsa"],
            ),
            (
                "PulseAudio Compatibility",
                "PulseAudio replacement compatibility through PipeWire.",
                ["pipewire-pulse"],
            ),
            (
                "WirePlumber",
                "PipeWire session and policy manager.",
                ["wireplumber"],
            ),

            (
                "Desktop Portals",
                "Base XDG desktop portal infrastructure.",
                ["xdg-desktop-portal"],
            ),
            (
                "GTK Portal",
                "GTK portal backend for file dialogs, screenshots and more.",
                ["xdg-desktop-portal-gtk"],
            ),
            (
                "KDE Portal",
                "KDE portal backend for Plasma-based sessions.",
                ["xdg-desktop-portal-kde"],
            ),
            (
                "GNOME Portal",
                "GNOME portal backend.",
                ["xdg-desktop-portal-gnome"],
            ),
            (
                "Hyprland Portal",
                "Portal backend for Hyprland.",
                ["xdg-desktop-portal-hyprland"],
            ),
            (
                "wlroots Portal",
                "Portal backend for wlroots-based Wayland sessions.",
                ["xdg-desktop-portal-wlr"],
            ),

            (
                "Polkit",
                "Desktop authorization and privilege-control framework.",
                ["polkit"],
            ),
            (
                "NetworkManager",
                "Modern desktop network management.",
                ["networkmanager"],
            ),
            (
                "Bluetooth",
                "Bluetooth stack with BlueZ and desktop management tools.",
                ["bluez", "bluez-utils", "blueman"],
            ),
            (
                "Power Management",
                "Desktop power management support.",
                ["upower", "power-profiles-daemon"],
            ),
            (
                "Printing",
                "CUPS printing system.",
                ["cups"],
            ),
            (
                "Avahi",
                "Local-network service discovery.",
                ["avahi"],
            ),
            (
                "Desktop File Integration",
                "User directories and desktop utility helpers.",
                ["xdg-user-dirs", "xdg-utils"],
            ),
        ]

        self.add_install_page(
            "Desktop Components",
            "Core desktop infrastructure for NanoOS. Wayland is already included with NanoOS and intentionally has no install option.",
            desktop_components,
        )


        # -------------------------------------------------
        # Window Managers
        # -------------------------------------------------

        wm = [
            ("Hyprland", "Dynamic Wayland compositor.", ["hyprland"]),
            ("Sway", "i3-compatible Wayland compositor.", ["sway"]),
            ("Niri", "Scrollable-tiling Wayland compositor.", ["niri"]),
            ("River", "Non-monolithic Wayland compositor.", ["river"]),
            ("MangoWM", "Lightweight high-performance tiling Wayland compositor.", ["mangowm"]),
            ("Labwc", "Stacking Wayland compositor inspired by Openbox.", ["labwc"]),
            ("Wayfire", "3D Wayland compositor based on wlroots.", ["wayfire"]),
            ("Weston", "Reference Wayland compositor.", ["weston"]),
            ("Cage", "Kiosk Wayland compositor.", ["cage"]),
            ("Qtile", "Python-based tiling window manager.", ["qtile"]),
            ("i3", "Lightweight X11 tiling window manager.", ["i3-wm"]),
            ("Openbox", "Lightweight X11 stacking window manager.", ["openbox"]),
            ("Waybar", "Status bar for Wayland compositors.", ["waybar"]),
            ("Rofi Wayland", "Application launcher for Wayland.", ["rofi"]),
            ("Kitty", "Modern terminal commonly used in tiling workflows.", ["kitty"]),
            ("Hyprland Starter Stack", "Hyprland, Waybar, Kitty and Rofi.", ["hyprland", "waybar", "kitty", "rofi"]),
        ]

        self.add_install_page(
            "Window Managers",
            "Install modern compositors and supporting tools for custom NanoOS sessions.",
            wm,
        )


        # -------------------------------------------------
        # System
        # -------------------------------------------------

        page, layout = self.page_header(
            "System",
            "Quick information about the system running NanoOS Welcome.",
        )

        for title, description in self.get_system_info():
            layout.addWidget(
                ActionCard(
                    title,
                    description,
                    "Refresh",
                    self.refresh_system,
                )
            )

        layout.addStretch()
        self.add_page("System", page)


        # -------------------------------------------------
        # About
        # -------------------------------------------------

        page, layout = self.page_header(
            "About NanoOS",
            "The modern NanoOS Welcome experience.",
        )

        about = [
            (
                "NanoOS Welcome V2",
                "A modern first-party setup center for NanoOS.",
            ),
            (
                "Patchy Patchy",
                "Welcome changes are maintained through nanooswelcomepatch.py.",
            ),
            (
                "Design",
                "Rounded surfaces, clean spacing, smooth scrolling, and modern controls.",
            ),
        ]

        for title, description in about:
            layout.addWidget(
                ActionCard(
                    title,
                    description,
                    "OK",
                    lambda: None,
                )
            )

        layout.addStretch()
        self.add_page("About NanoOS", page)

        self.add_preferences_page()


    def add_preferences_page(self):
        page, layout = self.page_header(
            "Preferences",
            "Small controls for how NanoOS Welcome behaves. These settings do not change your system configuration.",
        )
        layout.addWidget(ActionCard(
            "First-run introduction",
            "Reset the welcome guide so it appears again on the next launch.",
            "Reset guide",
            self.reset_first_run_guide,
        ))
        layout.addWidget(ActionCard(
            "Installation output",
            "Open or hide the live output panel beneath the page area. The panel opens automatically during package operations.",
            "Show output",
            lambda: self.toggle_output(True),
        ))
        layout.addWidget(ActionCard(
            "System information",
            "Refresh the current hostname, CPU, architecture, kernel, and package-backend details.",
            "Open system",
            lambda: self.show_page("System"),
        ))
        layout.addStretch(1)
        self.add_page("Preferences", page)

    def add_install_page(self, name, description, items):
        page, layout = self.page_header(
            name,
            description,
        )

        for title, card_description, packages in items:
            layout.addWidget(
                ActionCard(
                    title,
                    card_description,
                    "Install",
                    lambda p=packages, t=title:
                        self.install_packages(p, t),
                )
            )

        layout.addStretch()
        self.add_page(name, page)

    def get_system_info(self):
        kernel = self.command_output(["uname", "-r"]).strip() or "Unavailable"
        architecture = self.command_output(["uname", "-m"]).strip() or "Unavailable"
        # `hostname` is in inetutils, which a base install doesn't include.
        hostname = socket.gethostname() or "Unavailable"
        cpu = "Unavailable"
        try:
            with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if line.startswith("model name"):
                        cpu = line.split(":", 1)[1].strip() or cpu
                        break
        except OSError:
            pass
        pacman = shutil.which("pacman") or "/usr/bin/pacman"
        return [
            ("Hostname", hostname),
            ("Kernel", kernel),
            ("Architecture", architecture),
            ("CPU", cpu),
            ("Package Backend", f"pacman · {pacman} (non-interactive GUI installs)"),
        ]

    def refresh_system(self):
        # Rebuild the System page so its values are actually re-read.
        page, layout = self.page_header(
            "System",
            "Live host information from the machine running NanoOS Welcome.",
        )
        refresh_button = NanoButton("Refresh system information", "secondary")
        refresh_button.clicked.connect(self.refresh_system)
        layout.addWidget(refresh_button)
        for title, description in self.get_system_info():
            layout.addWidget(ActionCard(
                title, description, "Copy value",
                lambda value=description, label=title: self.copy_value(label, value),
            ))
        layout.addStretch(1)
        self.add_page("System", page)
        self.show_page("System")

    def command_output(self, command):
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=3,
            )
            return result.stdout
        except Exception:
            return ""

    def install_packages(self, packages, title):
        if not packages:
            self.status.setText("No packages were selected.")
            return
        pacman = shutil.which("pacman") or "/usr/bin/pacman"
        self.run_privileged(
            [pacman, "-S", "--needed", "--noconfirm", *list(packages)],
            title, verb="Installing",
        )

    def install_local_kernel(self):
        if self.task_running():
            self.status.setText("Another operation is already running.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select {NANOOS_KERNEL} Package",
            str(Path.home()),
            "Arch Packages (*.pkg.tar.zst *.pkg.tar.xz);;All Files (*)",
        )
        if not path:
            return
        package_path = Path(path)
        if not package_path.is_file():
            self.status.setText("The selected package file no longer exists.")
            return
        pacman = shutil.which("pacman") or "/usr/bin/pacman"
        self.run_kernel_transaction(
            [pacman, "-U", "--noconfirm", str(package_path)],
            f"{NANOOS_KERNEL} package",
        )

    # ------------------------------------------------------------ kernels
    GRUB_HOOK = Path("/etc/pacman.d/hooks/99-nanoos-grub.hook")

    KERNEL_EXTRAS = ("-headers", "-docs", "-firmware", "-api-headers")

    @staticmethod
    def installed_packages():
        try:
            result = subprocess.run(["pacman", "-Qq"], capture_output=True, text=True, check=False)
        except OSError:
            return set()
        return set(result.stdout.split())

    def dkms_in_use(self, installed=None):
        installed = self.installed_packages() if installed is None else installed
        return any(name.endswith("-dkms") for name in installed)

    def kernel_headers_for(self, kernels):
        """Headers so DKMS drivers (NVIDIA) get built for these kernels."""
        return [
            name + "-headers" for name in kernels
            if name.startswith("linux") and not name.endswith(self.KERNEL_EXTRAS)
        ]

    def install_kernel(self, packages, title):
        pacman = shutil.which("pacman") or "/usr/bin/pacman"
        packages = list(packages)
        if self.dkms_in_use():
            # Without headers DKMS cannot build the NVIDIA driver for the new
            # kernel and its initramfs ends up without the graphics driver.
            packages += [h for h in self.kernel_headers_for(packages) if h not in packages]
        self.run_kernel_transaction(
            [pacman, "-S", "--needed", "--noconfirm", *packages], title
        )

    def repair_kernel_drivers(self):
        installed = self.installed_packages()
        kernels = [
            name for name in installed
            if re.fullmatch(r"linux(-[a-z0-9]+)*", name) and not name.endswith(self.KERNEL_EXTRAS)
            and name not in ("linux-firmware",) and not name.startswith("linux-firmware")
        ]
        missing = [h for h in self.kernel_headers_for(kernels) if h not in installed]
        if not self.dkms_in_use(installed):
            self.status.setText("No DKMS drivers installed; nothing to repair.")
            return
        if not missing:
            self.status.setText("Every installed kernel already has its headers.")
            return
        self.install_kernel(missing, "Kernel driver repair")

    def run_kernel_transaction(self, pacman_command, title):
        """Install a kernel, then regenerate the GRUB menu so it can be
        booted. Both steps run in one administrator action."""
        if self.GRUB_HOOK.is_file():
            # The NanoOS pacman hook regenerates GRUB itself (and its output
            # appears in this panel); running it twice only costs time.
            self.run_privileged(pacman_command, title, verb="Installing")
            return
        grub_step = (
            'if [ -f /boot/grub/grub.cfg ] && command -v grub-mkconfig >/dev/null; then '
            'echo; echo "==> Updating the GRUB boot menu…"; '
            'grub-mkconfig -o /boot/grub/grub.cfg; '
            'else echo; echo "==> GRUB not detected; boot menu left unchanged."; fi'
        )
        script = shlex.join(pacman_command) + " && { " + grub_step + "; }"
        self.run_privileged(["/bin/sh", "-c", script], title, verb="Installing")

    def on_task_finished(self, title, success):
        if success and "==> Updating the GRUB boot menu" in self.log.toPlainText():
            self.status.setText(f"{title} installed · GRUB boot menu updated.")
        elif success and "NanoOS: updating the GRUB boot menu" in self.log.toPlainText():
            self.status.setText(f"{title} installed · GRUB boot menu updated.")


class NanoOSFirstRun(QDialog):
    MARKER = Path.home() / ".config" / "nanoos-welcome" / "first-launch-complete"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to NanoOS")
        self.setModal(True)
        self.setMinimumSize(600, 420)
        self.resize(800, 520)
        self.setStyleSheet("""
            QDialog { background: #09121b; border: 1px solid #294353; }
            QLabel#eyebrow { color: #70def5; font-size: 11px; font-weight: 850; letter-spacing: 2px; }
            QLabel#title { color: #f4f9fc; font-size: 36px; font-weight: 850; }
            QLabel#subtitle { color: #a7bbc8; font-size: 15px; }
            QLabel#card { background: #101e2a; border: 1px solid #294252; border-radius: 18px; padding: 18px; color: #d9e9f2; font-size: 14px; }
            QPushButton#startButton { background: #69d9f1; color: #07131a; border: 1px solid #8ae7fa; border-radius: 13px; padding: 12px 24px; font-size: 14px; font-weight: 850; }
            QPushButton#startButton:hover { background: #86e8fa; }
            QPushButton#startButton:pressed { background: #42c1dd; }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(38, 34, 38, 30)
        root.setSpacing(15)
        eyebrow = QLabel("N A N O O S   /   FIRST RUN")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Welcome to NanoOS")
        title.setObjectName("title")
        title.setWordWrap(True)
        subtitle = QLabel(
            ("Your setup center brings gaming tools, kernels, everyday software, "
             if GAMING else "Your setup center brings kernels, everyday software, ")
            + "coding environments, desktops, and system components into one place."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        card = QLabel("Choose what you need, review the install output, and keep control of every package operation.")
        card.setObjectName("card")
        card.setWordWrap(True)
        root.addWidget(eyebrow)
        root.addWidget(title)
        root.addWidget(subtitle)
        root.addSpacing(4)
        root.addWidget(card)
        root.addStretch(1)
        footer = QHBoxLayout()
        footer.addStretch(1)
        start_button = QPushButton("Get Started  →")
        start_button.setObjectName("startButton")
        start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        start_button.clicked.connect(self.finish_first_run)
        footer.addWidget(start_button)
        root.addLayout(footer)

    def finish_first_run(self):
        try:
            self.MARKER.parent.mkdir(parents=True, exist_ok=True)
            self.MARKER.write_text("NanoOS Welcome first launch completed.\n", encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Welcome setup",
                "The welcome completion marker could not be saved. "
                "The app can still continue, but this introduction may appear again.\n\n"
                f"Details: {exc}",
            )
        self.accept()

    @classmethod
    def should_show(cls):
        return not cls.MARKER.exists()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("NanoOS")
    # Lets KDE/Wayland match the window to org.nanoos.Welcome.desktop (name + icon).
    app.setDesktopFileName(DESKTOP_ID)
    app.setWindowIcon(QIcon.fromTheme("nanoos-welcome"))

    if NanoOSFirstRun.should_show():
        first_run = NanoOSFirstRun()
        if first_run.exec() != QDialog.DialogCode.Accepted:
            return

    window = WelcomeWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

# NANOOS_WELCOME_SCROLL_SPEED_V4
