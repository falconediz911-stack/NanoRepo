"""Start a NanoOS app as its own process with the user's NanoOS theme.

Installed by the nanoos-gamemode package. The apps are written in the default
Glacier colours; other themes are applied by recolouring a per-user cached
copy at start-up, so package updates never undo the chosen theme.
"""
import ctypes
import hashlib
import os
import runpy
import sys
from pathlib import Path

APP_DIR = Path("/usr/lib/nanoos-gamemode")
THEMED_FILES = ("gamemode.py",)


def _set_process_name(name):
    try:
        ctypes.CDLL(None, use_errno=True).prctl(15, name.encode()[:15], 0, 0, 0)  # PR_SET_NAME
    except Exception:
        pass


def _theme():
    try:
        return Path("/etc/nanoos/theme").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _themed_dir():
    sys.path.insert(0, str(APP_DIR))
    import nanoos_theme

    theme = nanoos_theme.theme_name(_theme())
    if theme == nanoos_theme.DEFAULT:
        return APP_DIR
    stamp = hashlib.sha256()
    for path in [APP_DIR / name for name in THEMED_FILES] + [Path(nanoos_theme.__file__)]:
        name = path.name
        stat = path.stat()
        stamp.update(f"{name}:{stat.st_mtime_ns}:{stat.st_size}".encode())
    cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    target = cache / "nanoos-gamemode" / f"{theme}-{stamp.hexdigest()[:16]}"
    if not (target / "ready").exists():
        try:
            target.mkdir(parents=True, exist_ok=True)
            for name in THEMED_FILES:
                text = (APP_DIR / name).read_text(encoding="utf-8")
                (target / name).write_text(nanoos_theme.recolor_text(text, theme), encoding="utf-8")
            (target / "ready").write_text("ok\n", encoding="utf-8")
        except OSError:
            return APP_DIR
    return target


def run(script, process_name):
    _set_process_name(process_name)
    source = _themed_dir()
    sys.path[:0] = [str(source), str(APP_DIR)]
    sys.argv[0] = process_name
    runpy.run_path(str(source / script), run_name="__main__")
