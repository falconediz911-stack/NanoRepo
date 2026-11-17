"""NanoOS Game Mode core: profiles, saved state and gamemode.ini.

Shared by the Game Mode app (gamemode.py) and the background game watcher
(nanoos-gamemode-watch), so both always write the same configuration.
Pure Python: importing it does not load Qt.
"""

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "nanoos"
STATE_FILE = CONFIG_DIR / "gamemode.json"
GAMEMODE_CONFIG = Path.home() / ".config" / "gamemode.ini"
HELPER_PATH = "/usr/lib/nanoos-gamemode/nanoos-gamemode-helper"

PROFILE_DATA = {
    "Balanced": {
        "desiredgov": "powersave",
        "desiredprof": "balanced",
        "desired_epp": "balance_performance",
        "desired_platform": "balanced",
        "renice": "0",
        "ioprio": "off",
        "softrealtime": "off",
    },
    "Performance": {
        "desiredgov": "performance",
        "desiredprof": "performance",
        "desired_epp": "performance",
        "desired_platform": "performance",
        "renice": "5",
        "ioprio": "0",
        "softrealtime": "off",
    },
    "Gaming": {
        "desiredgov": "performance",
        "desiredprof": "performance",
        "desired_epp": "performance",
        "desired_platform": "performance",
        "renice": "10",
        "ioprio": "0",
        "softrealtime": "off",
    },
}

# Games without a profile of their own get this one automatically
# (the "auto_profiles" setting turns that off).
AUTO_PROFILE = "Gaming"


def load_state():
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def game_key(source, launch_target):
    """Same key the Game Mode app stores per-game profiles under."""
    return f"{source}|{launch_target}"


def profile_for_game(state, key):
    """(profile, automatic) for a game key, or (None, False) when the game
    should be left alone."""
    assignments = state.get("game_profiles")
    assigned = assignments.get(key, "") if isinstance(assignments, dict) else ""
    if assigned in PROFILE_DATA:
        return assigned, False
    if state.get("auto_profiles", True):
        return AUTO_PROFILE, True
    return None, False


def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8").split()
    except OSError:
        return []


def render_gamemode_ini(state, profile_name=None):
    """gamemode.ini text for `profile_name` (default: the selected profile)
    with the switches saved in `state`."""
    profile = PROFILE_DATA.get(profile_name or state.get("profile"), PROFILE_DATA["Gaming"])
    desiredprof = "performance" if state.get("gpu_performance", True) else "balanced"
    ioprio = "0" if state.get("io_optimization", True) else "off"
    renice = profile["renice"] if state.get("scheduler_optimization", True) else "0"
    inhibit = "1" if state.get("screensaver_inhibit", True) else "0"

    # gamemode.ini only takes effect while GameMode is active, so it must
    # always carry the profile's governor, limited to ones the kernel offers.
    governors = _read("/sys/devices/system/cpu/cpufreq/policy0/scaling_available_governors")
    desiredgov = profile["desiredgov"]
    if governors and desiredgov not in governors:
        desiredgov = "performance" if "performance" in governors else governors[0]

    # Platform profile (laptops / handhelds), only when exposed.
    platform_line = ""
    if desiredprof in _read("/sys/firmware/acpi/platform_profile_choices"):
        platform_line = f"desiredprof={desiredprof}\n"

    return f"""[general]
reaper_freq=5
desiredgov={desiredgov}
{platform_line}softrealtime={profile["softrealtime"]}
renice={renice}
ioprio={ioprio}
inhibit_screensaver={inhibit}
disable_splitlock=1
"""
